"""AGENT 4 — Response Generator orchestrator."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.context import (
    allowed_place_names,
    build_structured_context,
    context_as_prompt_block,
    map_response_type,
    resolve_language,
)
from app.services.agents.response.fallback import render_deterministic
from app.services.agents.response.models import FinalResponse, SourceReference
from app.services.agents.response.prompts import agent4_system_prompt

logger = logging.getLogger(__name__)

# Optional LLM: async callable(messages: list[dict]) -> str
LlmComplete = Callable[[list[dict[str, str]]], Awaitable[str]]


class ResponseGenerator:
    """Presentation layer. Grounding > fluency. One LLM call max when provided."""

    def __init__(
        self,
        *,
        llm_complete: LlmComplete | None = None,
        prefer_deterministic: bool = True,
    ) -> None:
        self._llm = llm_complete
        # Default deterministic protects TTFA / tests; set False when enabling LLM path.
        self._prefer_deterministic = prefer_deterministic

    async def generate(
        self,
        user_query: str,
        intent_result: IntentResult,
        knowledge_result: KnowledgeResult,
        tourism_plan: TourismPlan | None = None,
        *,
        response_mode: str = "text",
        locale: str | None = None,
        request_id: str | None = None,
    ) -> FinalResponse:
        started = time.perf_counter()
        rid = (
            request_id
            or intent_result.request_id
            or knowledge_result.request_id
            or (tourism_plan.request_id if tourism_plan else None)
            or uuid.uuid4().hex[:12]
        )
        language = resolve_language(intent_result, locale)
        response_type = map_response_type(intent_result, tourism_plan)

        t_prompt = time.perf_counter()
        context = build_structured_context(
            user_query,
            intent_result,
            knowledge_result,
            tourism_plan,
            response_mode=response_mode,
        )
        system = agent4_system_prompt(language=language, response_mode=response_mode)
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": context_as_prompt_block(context)
                + f"\n\nUser question:\n{user_query}",
            },
        ]
        prompt_build_ms = (time.perf_counter() - t_prompt) * 1000.0

        fallback_used = False
        llm_ttft_ms: float | None = None
        llm_generation_ms: float | None = None
        text: str

        use_llm = self._llm is not None and not self._prefer_deterministic
        if use_llm:
            try:
                t_llm = time.perf_counter()
                text = await self._llm(messages)
                llm_generation_ms = (time.perf_counter() - t_llm) * 1000.0
                llm_ttft_ms = llm_generation_ms  # single-shot complete; no stream TTFT here
                if not (text or "").strip():
                    raise ValueError("empty llm response")
            except Exception:
                logger.exception("agent4_llm_failed_using_fallback")
                text = render_deterministic(
                    user_query,
                    intent_result,
                    knowledge_result,
                    tourism_plan,
                    language=language,
                    response_mode=response_mode,
                )
                fallback_used = True
        else:
            text = render_deterministic(
                user_query,
                intent_result,
                knowledge_result,
                tourism_plan,
                language=language,
                response_mode=response_mode,
            )
            fallback_used = self._llm is not None  # had LLM but preferred deterministic

        # Voice cleanup: strip residual markdown if any
        if response_mode == "voice":
            text = _voice_sanitize(text)

        sources = [
            SourceReference(source_id=s.source_id, name=s.name, url=s.url)
            for s in knowledge_result.sources
            if s.source_id
        ]
        warnings = list(
            dict.fromkeys(
                list(knowledge_result.missing_information)[:4]
                + (list(tourism_plan.warnings)[:4] if tourism_plan else [])
            )
        )
        confidence = _response_confidence(intent_result, knowledge_result, tourism_plan)

        total_ms = (time.perf_counter() - started) * 1000.0
        # Keep reference to messages size for potential diagnostics (no PII log of full text)
        _ = len(messages)

        result = FinalResponse(
            text=text.strip(),
            language=language,
            response_type=response_type,
            response_mode="voice" if response_mode == "voice" else "text",  # type: ignore[arg-type]
            sources=sources,
            warnings=warnings,
            confidence=round(confidence, 3),
            fallback_used=fallback_used or self._prefer_deterministic,
            request_id=rid,
            prompt_build_ms=round(prompt_build_ms, 3),
            llm_ttft_ms=round(llm_ttft_ms, 3) if llm_ttft_ms is not None else None,
            llm_generation_ms=round(llm_generation_ms, 3) if llm_generation_ms is not None else None,
            total_agent4_ms=round(total_ms, 3),
        )
        # Soft check for diagnostics
        allowed = allowed_place_names(knowledge_result, tourism_plan)
        result_meta = {
            **result.observability(),
            "allowed_places_count": len(allowed),
        }
        logger.info("response_generator %s", result_meta)
        return result

    def build_messages(
        self,
        user_query: str,
        intent_result: IntentResult,
        knowledge_result: KnowledgeResult,
        tourism_plan: TourismPlan | None = None,
        *,
        response_mode: str = "text",
        locale: str | None = None,
    ) -> list[dict[str, str]]:
        language = resolve_language(intent_result, locale)
        context = build_structured_context(
            user_query,
            intent_result,
            knowledge_result,
            tourism_plan,
            response_mode=response_mode,
        )
        system = agent4_system_prompt(language=language, response_mode=response_mode)
        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": context_as_prompt_block(context)
                + f"\n\nUser question:\n{user_query}",
            },
        ]


async def generate_response(
    user_query: str,
    intent_result: IntentResult,
    knowledge_result: KnowledgeResult,
    tourism_plan: TourismPlan | None = None,
    *,
    response_mode: str = "text",
    locale: str | None = None,
    request_id: str | None = None,
    llm_complete: LlmComplete | None = None,
    prefer_deterministic: bool = True,
) -> FinalResponse:
    agent = ResponseGenerator(
        llm_complete=llm_complete,
        prefer_deterministic=prefer_deterministic,
    )
    return await agent.generate(
        user_query,
        intent_result,
        knowledge_result,
        tourism_plan,
        response_mode=response_mode,
        locale=locale,
        request_id=request_id,
    )


def _response_confidence(
    intent: IntentResult,
    knowledge: KnowledgeResult,
    plan: TourismPlan | None,
) -> float:
    values = [intent.confidence, knowledge.confidence]
    if plan is not None:
        values.append(plan.confidence)
    return max(0.05, min(0.95, sum(values) / len(values)))


def _voice_sanitize(text: str) -> str:
    cleaned = text.replace("### ", "").replace("## ", "").replace("# ", "")
    cleaned = cleaned.replace("- ", "").replace("* ", "")
    cleaned = cleaned.replace("```", "")
    return " ".join(cleaned.split())
