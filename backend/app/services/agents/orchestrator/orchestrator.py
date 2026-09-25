"""AGENT Orchestrator — conditional coordinator for Agents 1–4.

Does not invent knowledge, places, or prices.
Does not call the LLM for answering (Agent 4 may, at most once).
Does not replace Agents 1–4 or introduce a second RAG / router.
"""

from __future__ import annotations

import asyncio
import logging
import time
import unicodedata
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from app.core.config import get_settings
from app.services.agents.intent import classify_intent
from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.agent import KnowledgeAgent
from app.services.agents.knowledge.models import (
    KnowledgeEvidence,
    KnowledgeResult,
    SourceEvidence,
)
from app.services.agents.orchestrator.models import (
    OrchestrationContext,
    OrchestrationResult,
    OrchestrationTimings,
)
from app.services.agents.planner import TourismPlanner, build_tourism_plan
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.agent import ResponseGenerator
from app.services.agents.response.models import FinalResponse
from app.services.agents.web_research import WebResearchAgent, WebResearchResult
from app.services.agents.web_research.policy import (
    FORCED_REASONS,
    WEB_SEARCH_TOOL,
    WebToolDecision,
    build_decision_messages,
    kb_summary,
    parse_tool_decision,
    web_forbidden,
)
from app.services.rag.base import RAGService
from app.services.search.base import WebSearchService
from app.services.vision.base import VisionService

logger = logging.getLogger(__name__)

LlmComplete = Callable[[list[dict[str, str]]], Awaitable[str]]
# (messages, tools) -> OpenAI-style assistant message (may contain tool_calls)
WebToolCaller = Callable[[list[dict[str, Any]], list[dict[str, Any]]], Awaitable[dict[str, Any] | None]]
Mode = Literal["text", "voice"]


def _fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def _scope_places(knowledge: KnowledgeResult, intent: IntentResult) -> KnowledgeResult:
    """Food/hotel answers must not show places from another city or region."""
    if intent.intent not in {"FOOD", "HOTEL"} or not (intent.city or intent.region):
        return knowledge
    city, region = _fold(intent.city), _fold(intent.region)
    kept = [
        p
        for p in knowledge.places
        if (city and _fold(p.city) == city) or (region and _fold(p.region) == region)
    ]
    if len(kept) == len(knowledge.places):
        return knowledge
    scoped = knowledge.model_copy(deep=True)
    scoped.places = [p for p in scoped.places if p.place_id in {k.place_id for k in kept}]
    return scoped


class AgentOrchestrator:
    """Capability-based coordinator. Agents do the work; this only sequences them."""

    def __init__(
        self,
        *,
        knowledge_agent: KnowledgeAgent | None = None,
        tourism_planner: TourismPlanner | None = None,
        response_generator: ResponseGenerator | None = None,
        web_search: WebSearchService | None = None,
        vision: VisionService | None = None,
        rag: RAGService | None = None,
        booking_available: bool = False,
        prefer_deterministic: bool = True,
        llm_complete: LlmComplete | None = None,
        web_search_max_results: int = 3,
        web_tool_caller: WebToolCaller | None = None,
    ) -> None:
        self._knowledge = knowledge_agent
        self._planner = tourism_planner or TourismPlanner()
        self._response = response_generator or ResponseGenerator(
            llm_complete=llm_complete,
            prefer_deterministic=prefer_deterministic,
        )
        self._web = web_search
        self._vision = vision
        self._rag = rag
        self._booking_available = booking_available
        self._prefer_deterministic = prefer_deterministic
        self._llm_complete = llm_complete
        self._web_max = web_search_max_results
        self._web_tool_caller = web_tool_caller
        self.last_web_research: WebResearchResult | None = None

    async def prepare(
        self,
        user_query: str,
        *,
        mode: Mode | str = "text",
        language: str | None = None,
        locale: str | None = None,
        image_context: bytes | None = None,
        image_mime: str = "image/jpeg",
        request_id: str | None = None,
        conversation_context: str | None = None,
    ) -> OrchestrationContext:
        """Run Agents 1–3 only (no Agent 4). Used by true Qwen→TTS streaming."""
        started = time.perf_counter()
        rid = request_id or uuid.uuid4().hex[:12]
        response_mode = "voice" if mode == "voice" else "text"
        locale_eff = locale or language
        agents_called: list[str] = []
        timings = OrchestrationTimings()

        logger.info(
            "orchestration_prepare_started request_id=%s mode=%s",
            rid,
            response_mode,
        )

        t_intent = time.perf_counter()
        intent = classify_intent(
            user_query,
            locale=locale_eff,
            mode="voice" if response_mode == "voice" else "text",
            request_id=rid,
            has_image=bool(image_context),
            conversation_context=conversation_context,
        )
        timings.intent_ms = round((time.perf_counter() - t_intent) * 1000.0, 3)
        agents_called.append("intent")
        logger.info(
            "intent_completed request_id=%s intent=%s intent_ms=%s",
            rid,
            intent.intent,
            timings.intent_ms,
        )

        vision_summary: str | None = None
        knowledge: KnowledgeResult | None = None
        plan: TourismPlan | None = None
        web_hit_count = 0
        web_obs: dict[str, Any] | None = None

        if intent.needs_vision and image_context and self._vision is not None:
            logger.info("vision_started request_id=%s", rid)
            t_vis = time.perf_counter()
            try:
                vision_summary = await self._vision.identify(
                    image_context,
                    mime_type=image_mime,
                )
            except Exception:  # noqa: BLE001
                logger.exception("vision_failed request_id=%s", rid)
                vision_summary = None
            timings.vision_ms = round((time.perf_counter() - t_vis) * 1000.0, 3)
            agents_called.append("vision")

        if self._should_retrieve_knowledge(intent):
            logger.info("knowledge_started request_id=%s", rid)
            t_know = time.perf_counter()
            knowledge = _scope_places(await self._run_knowledge(user_query, intent, rid), intent)
            timings.knowledge_ms = round((time.perf_counter() - t_know) * 1000.0, 3)
            agents_called.append("knowledge")
        else:
            knowledge = self._empty_knowledge(user_query, intent, rid)
            if intent.intent == "BOOKING" and not self._booking_available:
                knowledge.missing_information = list(
                    dict.fromkeys([*knowledge.missing_information, "live_availability"])
                )

        web_decision = await self._decide_web(
            user_query, intent, knowledge, response_mode=response_mode, request_id=rid
        )
        if web_decision is not None:
            label, llm_queries = web_decision
            knowledge, web_hit_count, web_ms = await self._run_web_research(
                user_query,
                intent,
                knowledge,
                rid,
                llm_queries=llm_queries,
                decision=label,
                response_mode=response_mode,
            )
            timings.web_ms = web_ms
            agents_called.append("web_research")
            if self.last_web_research is not None:
                web_obs = self.last_web_research.observability()

        if intent.needs_planner and self._knowledge_usable_for_planner(knowledge):
            logger.info("planner_started request_id=%s", rid)
            t_plan = time.perf_counter()
            plan = self._planner.plan(
                user_query,
                intent,
                knowledge,
                request_id=rid,
            )
            timings.planner_ms = round((time.perf_counter() - t_plan) * 1000.0, 3)
            agents_called.append("planner")
        elif intent.needs_planner and knowledge is not None:
            logger.info(
                "planner_skipped request_id=%s reason=insufficient_knowledge",
                rid,
            )

        timings.total_ms = round((time.perf_counter() - started) * 1000.0, 3)
        return OrchestrationContext(
            intent=intent,
            knowledge=knowledge,
            plan=plan,
            timings=timings,
            agents_called=agents_called,
            request_id=rid,
            mode=response_mode,
            vision_summary=vision_summary,
            web_hit_count=web_hit_count,
            web_research=web_obs,
        )

    async def run(
        self,
        user_query: str,
        *,
        conversation_context: Any = None,
        mode: Mode | str = "text",
        language: str | None = None,
        locale: str | None = None,
        image_context: bytes | None = None,
        image_mime: str = "image/jpeg",
        request_id: str | None = None,
    ) -> OrchestrationResult:
        started = time.perf_counter()
        ctx_hint: str | None = None
        if isinstance(conversation_context, str) and conversation_context.strip():
            ctx_hint = conversation_context.strip()[:400]
        elif isinstance(conversation_context, list):
            # Compact last user turns for location anaphora only
            bits: list[str] = []
            for item in conversation_context[-4:]:
                if isinstance(item, dict) and item.get("role") == "user":
                    bits.append(str(item.get("content") or "")[:120])
                elif isinstance(item, str):
                    bits.append(item[:120])
            ctx_hint = "\n".join(bits)[:400] if bits else None
        ctx = await self.prepare(
            user_query,
            mode=mode,
            language=language,
            locale=locale,
            image_context=image_context,
            image_mime=image_mime,
            request_id=request_id,
            conversation_context=ctx_hint,
        )
        locale_eff = locale or language
        agents_called = list(ctx.agents_called)
        timings = ctx.timings.model_copy()

        logger.info("response_started request_id=%s", ctx.request_id)
        t_resp = time.perf_counter()
        final = await self._run_response(
            user_query,
            ctx.intent,
            ctx.knowledge,
            ctx.plan,
            response_mode=ctx.mode,
            locale=locale_eff,
            request_id=ctx.request_id or "",
            vision_summary=ctx.vision_summary,
        )
        timings.response_ms = round((time.perf_counter() - t_resp) * 1000.0, 3)
        agents_called.append("response")
        logger.info(
            "response_completed request_id=%s response_ms=%s response_type=%s",
            ctx.request_id,
            timings.response_ms,
            final.response_type,
        )

        timings.total_ms = round((time.perf_counter() - started) * 1000.0, 3)
        result = OrchestrationResult(
            intent=ctx.intent,
            knowledge=ctx.knowledge,
            plan=ctx.plan,
            final_response=final,
            timings=timings,
            agents_called=agents_called,
            request_id=ctx.request_id,
            mode=ctx.mode,
            vision_summary=ctx.vision_summary,
            web_hit_count=ctx.web_hit_count,
            web_research=ctx.web_research,
            fallback_used=final.fallback_used,
        )
        logger.info("orchestration_completed %s", result.observability())
        return result

    def _should_retrieve_knowledge(self, intent: IntentResult) -> bool:
        """Skip Agent 2 when it cannot help (greeting/clarification/booking-without-provider)."""
        if intent.intent == "CLARIFICATION":
            return False
        if intent.intent == "BOOKING" and not self._booking_available:
            return False
        if intent.intent == "VISION" and not (intent.needs_knowledge or intent.needs_places):
            return False
        # SIMPLE_QA always retrieves knowledge when geography may answer
        if intent.intent == "SIMPLE_QA":
            return True
        return bool(intent.needs_knowledge or intent.needs_places)

    @staticmethod
    def _knowledge_usable_for_planner(knowledge: KnowledgeResult | None) -> bool:
        if knowledge is None:
            return False
        if not knowledge.places:
            return False
        if knowledge.source == "empty":
            return False
        return True

    async def _run_knowledge(
        self,
        query: str,
        intent: IntentResult,
        request_id: str,
    ) -> KnowledgeResult:
        agent = self._knowledge
        if agent is None:
            agent = KnowledgeAgent.from_catalog(rag=self._rag)
            self._knowledge = agent
        return await agent.retrieve(query, intent, request_id=request_id)

    async def _run_response(
        self,
        user_query: str,
        intent: IntentResult,
        knowledge: KnowledgeResult,
        plan: TourismPlan | None,
        *,
        response_mode: str,
        locale: str | None,
        request_id: str,
        vision_summary: str | None,
    ) -> FinalResponse:
        knowledge_eff = knowledge
        if vision_summary:
            knowledge_eff = knowledge.model_copy(deep=True)
            knowledge_eff.knowledge = [
                *knowledge_eff.knowledge,
                KnowledgeEvidence(
                    chunk_id=f"vision:{request_id}",
                    content=vision_summary.strip(),
                    source_id="vision:gemini",
                    title="Vision analysis",
                    score=0.7,
                ),
            ]
            if knowledge_eff.source == "empty":
                knowledge_eff.source = "documents"

        generator = self._response
        if self._llm_complete is not None and generator is self._response:
            # Ensure injected LLM is used when caller provides one after init.
            generator = ResponseGenerator(
                llm_complete=self._llm_complete,
                prefer_deterministic=self._prefer_deterministic,
            )
        return await generator.generate(
            user_query,
            intent,
            knowledge_eff,
            plan,
            response_mode=response_mode,
            locale=locale,
            request_id=request_id,
        )

    @staticmethod
    def _empty_knowledge(
        query: str,
        intent: IntentResult,
        request_id: str,
    ) -> KnowledgeResult:
        return KnowledgeResult(
            query=query,
            intent=intent.intent,
            places=[],
            knowledge=[],
            sources=[],
            missing_information=[],
            web_needed=False,
            confidence=0.0,
            request_id=request_id,
            source="empty",
        )

    async def _decide_web(
        self,
        user_query: str,
        intent: IntentResult,
        knowledge: KnowledgeResult | None,
        *,
        response_mode: str,
        request_id: str,
    ) -> tuple[str, list[str] | None] | None:
        """Return (decision_label, llm_queries) when web research must run.

        Order: forbidden → forced/routed by Agent 1 → Qwen tool call (text,
        optional intents) → KB-thin fallback.
        """
        if self._web is None or web_forbidden(intent.intent, intent.reason):
            return None
        if intent.needs_web:
            intent.web_reason = intent.web_reason or "EXPLICIT_OR_ROUTING"
            if intent.web_reason in FORCED_REASONS:
                return (f"forced:{intent.web_reason}", None)
            return (f"router:{intent.web_reason}", None)
        settings = get_settings()
        if (
            self._web_tool_caller is not None
            and response_mode == "text"
            and settings.web_tool_calling_enabled
        ):
            decision = await self._ask_web_tool(user_query, knowledge, request_id)
            if decision is not None and decision.search:
                intent.needs_web = True
                intent.web_reason = "LLM_TOOL_CALL"
                return ("llm_tool_call", decision.queries)
            if decision is not None and not (knowledge is not None and knowledge.web_needed):
                return None
        if (
            knowledge is not None
            and knowledge.web_needed
            and settings.web_knowledge_fallback_enabled
        ):
            intent.needs_web = True
            intent.web_reason = "KB_INSUFFICIENT"
            return ("kb_insufficient", None)
        return None

    async def _ask_web_tool(
        self,
        user_query: str,
        knowledge: KnowledgeResult | None,
        request_id: str,
    ) -> WebToolDecision | None:
        assert self._web_tool_caller is not None
        messages = build_decision_messages(user_query, kb_summary(knowledge))
        t0 = time.perf_counter()
        try:
            message = await asyncio.wait_for(
                self._web_tool_caller(messages, [WEB_SEARCH_TOOL]),
                timeout=float(get_settings().web_tool_decision_timeout_seconds),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "web_tool_decision_failed request_id=%s error=%s",
                request_id,
                type(exc).__name__,
            )
            return None
        decision = parse_tool_decision(message)
        logger.info(
            "web_tool_decision request_id=%s search=%s queries=%s reason=%s ms=%.0f",
            request_id,
            decision.search,
            decision.queries,
            decision.reason,
            (time.perf_counter() - t0) * 1000.0,
        )
        return decision

    async def _run_web_research(
        self,
        user_query: str,
        intent: IntentResult,
        knowledge: KnowledgeResult | None,
        request_id: str,
        *,
        llm_queries: list[str] | None = None,
        decision: str = "",
        response_mode: str = "text",
    ) -> tuple[KnowledgeResult, int, float]:
        """Call Web Research Agent at most once; merge validated evidence into KB."""
        logger.info(
            "web_research_started request_id=%s reason=%s",
            request_id,
            intent.web_reason,
        )
        t_web = time.perf_counter()
        settings = get_settings()
        global_timeout = float(
            settings.voice_web_research_timeout_seconds
            if response_mode == "voice"
            else settings.web_research_timeout_seconds
        )
        agent = WebResearchAgent(
            self._web,
            timeout_seconds=global_timeout,
            max_results=max(self._web_max, 5),
        )
        try:
            result = await agent.research(
                user_query,
                intent,
                knowledge=knowledge,
                conversation_context=(
                    f"location={intent.location or intent.region or ''}; "
                    f"missing={','.join((knowledge.missing_information if knowledge else [])[:4])}"
                ),
                request_id=request_id,
                llm_queries=llm_queries,
            )
        except Exception:  # noqa: BLE001
            logger.exception("web_research_failed request_id=%s", request_id)
            result = WebResearchResult(
                query=user_query,
                answerable=False,
                warnings=["web_research_error"],
                request_id=request_id,
            )
        result.decision = decision
        self.last_web_research = result
        web_ms = round((time.perf_counter() - t_web) * 1000.0, 3)
        base = knowledge or self._empty_knowledge(user_query, intent, request_id)
        merged = self._merge_web_research(base, result, user_query, intent, request_id)
        logger.info(
            "web_research_completed request_id=%s decision=%s provider=%s queries=%s "
            "answerable=%s evidence=%s ms=%s",
            request_id,
            decision,
            result.provider,
            result.search_queries,
            result.answerable,
            len(result.evidence),
            web_ms,
        )
        return merged, len(result.evidence), web_ms

    @staticmethod
    def _merge_web_research(
        knowledge: KnowledgeResult,
        research: WebResearchResult,
        query: str,
        intent: IntentResult,
        request_id: str,
    ) -> KnowledgeResult:
        """Attach validated web evidence + sources. Never invent beyond snippets."""
        updated = knowledge.model_copy(deep=True)
        existing_urls = {
            (s.url or "").rstrip("/") for s in updated.sources if s.url
        }
        for i, ev in enumerate(research.evidence):
            snippet = (ev.snippet or "").strip()
            if not snippet:
                continue
            if ev.low_confidence:
                prefix = "[web evidence — low confidence]"
            elif ev.tier <= 2:
                prefix = "[web evidence — institutional]"
            elif ev.tier == 3:
                prefix = "[web evidence — unverified]"
            else:
                prefix = "[web evidence — community]"
            content = f"{prefix} {snippet}"
            if research.key_facts and i == 0:
                facts = " | ".join(research.key_facts[:4])
                content = f"{content}\nKey facts: {facts}"
            updated.knowledge.append(
                KnowledgeEvidence(
                    chunk_id=f"web:{request_id}:{i}",
                    content=content[:900],
                    source_id=ev.url or f"web:{ev.domain or i}",
                    title=(ev.title or ev.domain or "Web")[:120],
                    score=min(0.85, max(0.3, ev.relevance_score)),
                )
            )
            url = (ev.url or "").strip()
            if url and url.rstrip("/") not in existing_urls:
                existing_urls.add(url.rstrip("/"))
                updated.sources.append(
                    SourceEvidence(
                        source_id=url,
                        name=ev.title or ev.domain or "Web",
                        url=url,
                        source_type=f"web_tier_{ev.tier}",
                    )
                )
        if research.timed_out:
            updated.missing_information = list(
                dict.fromkeys([*updated.missing_information, "web_timeout"])
            )
        if research.answerable and updated.source == "empty":
            updated.source = "documents"
        if research.answerable:
            updated.confidence = max(updated.confidence, research.confidence)
            # Clear soft web_needed once research ran
            updated.web_needed = False
            if "knowledge_chunks" in updated.missing_information and research.key_facts:
                updated.missing_information = [
                    m for m in updated.missing_information if m != "knowledge_chunks"
                ]
        updated.query = query or updated.query
        updated.intent = intent.intent
        return updated

    @staticmethod
    def _merge_web_evidence(
        knowledge: KnowledgeResult,
        hits: list,
        query: str,
        intent: IntentResult,
        request_id: str,
    ) -> KnowledgeResult:
        """Legacy adapter kept for tests — prefer _merge_web_research."""
        from app.services.search.base import WebSearchHit

        updated = knowledge.model_copy(deep=True)
        for i, hit in enumerate(hits):
            if not isinstance(hit, WebSearchHit):
                continue
            snippet = (hit.snippet or hit.title or "").strip()
            if not snippet:
                continue
            content = f"[web evidence — unverified] {snippet}"
            updated.knowledge.append(
                KnowledgeEvidence(
                    chunk_id=f"web:{request_id}:{i}",
                    content=content[:800],
                    source_id=hit.url or f"web:{i}",
                    title=(hit.title or "Web")[:120],
                    score=0.35,
                )
            )
        if updated.knowledge and updated.source == "empty":
            updated.source = "documents"
        updated.query = query or updated.query
        updated.intent = intent.intent
        return updated


async def run_orchestration(
    user_query: str,
    *,
    mode: Mode | str = "text",
    locale: str | None = None,
    language: str | None = None,
    request_id: str | None = None,
    image_context: bytes | None = None,
    prefer_deterministic: bool = True,
    knowledge_agent: KnowledgeAgent | None = None,
    web_search: WebSearchService | None = None,
    vision: VisionService | None = None,
    llm_complete: LlmComplete | None = None,
    booking_available: bool = False,
    web_tool_caller: WebToolCaller | None = None,
) -> OrchestrationResult:
    """Module-level entry point used by chat/voice wiring and tests."""
    orch = AgentOrchestrator(
        web_tool_caller=web_tool_caller,
        knowledge_agent=knowledge_agent,
        web_search=web_search,
        vision=vision,
        prefer_deterministic=prefer_deterministic,
        llm_complete=llm_complete,
        booking_available=booking_available,
    )
    return await orch.run(
        user_query,
        mode=mode,
        locale=locale,
        language=language,
        request_id=request_id,
        image_context=image_context,
    )
