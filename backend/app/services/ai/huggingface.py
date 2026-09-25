from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import (
    GenerationFailedError,
    GenerationTimeoutError,
    HuggingFaceAuthError,
    HuggingFaceUnavailableError,
)
from app.core.http import shared_async_client
from app.schemas.chat import ChatResponse, ChatSource
from app.services.agents.response.structured_ui import build_structured_ui, log_chat_observability
from app.services.ai.base import AIService
from app.services.ai.context import sources_from_knowledge
from app.services.ai.grounding import build_grounded_system_prompt
from app.services.ai.prompts import locale_user_suffix
from app.services.ai.routing import route_query
from app.services.conversation.base import ConversationStore
from app.services.conversation.memory import InMemoryConversationStore
from app.services.metrics.latency import PhaseTimer
from app.services.metrics.llm_stream_trace import LlmStreamTrace
from app.services.rag.base import RAGService
from app.services.rag.factory import get_rag_service
from app.services.search.base import WebSearchService
from app.services.search.factory import get_web_search_service

logger = logging.getLogger(__name__)

ROUTE_MAX_TOKENS = 640

# When the provider refuses (quota / auth) or hangs, stop calling it for a while so
# every request falls back to the deterministic answer at once instead of waiting.
_QUOTA_PAUSE_S = 600.0
_TIMEOUT_PAUSE_S = 120.0
_llm_paused_until = 0.0
_llm_pause_reason = ""


def _pause_llm(seconds: float, reason: str) -> None:
    global _llm_paused_until, _llm_pause_reason
    _llm_paused_until = time.monotonic() + seconds
    _llm_pause_reason = reason
    logger.warning("llm_paused reason=%s seconds=%.0f", reason, seconds)


def _raise_if_llm_paused() -> None:
    remaining = _llm_paused_until - time.monotonic()
    if remaining > 0:
        raise HuggingFaceUnavailableError(
            f"LLM paused after {_llm_pause_reason} ({remaining:.0f}s left)"
        )


def _serialize_ui(ui: dict[str, Any]) -> dict[str, Any]:
    """JSON-ready dump of structured UI models."""
    out: dict[str, Any] = {}
    for key, value in ui.items():
        if isinstance(value, list):
            out[key] = [
                item.model_dump() if hasattr(item, "model_dump") else item for item in value
            ]
        elif hasattr(value, "model_dump"):
            out[key] = value.model_dump()
        else:
            out[key] = value
    return out


# Phase 1: short-TTL cache for exact simple/chitchat replies (locale + brief).
# Never caches grounded tourism answers (prices/hours can go stale).
_SIMPLE_REPLY_TTL_S = 300.0
_SIMPLE_REPLY_CACHE: dict[str, tuple[float, str]] = {}
_SIMPLE_REPLY_MAX = 64


def _simple_cache_key(message: str, locale: str, brief: bool) -> str:
    compact = " ".join(message.strip().casefold().split())
    return f"{locale}|{'v' if brief else 't'}|{compact}"


def _simple_reply_cache_get(message: str, locale: str, brief: bool) -> str | None:
    key = _simple_cache_key(message, locale, brief)
    entry = _SIMPLE_REPLY_CACHE.get(key)
    if entry is None:
        return None
    expires_at, text = entry
    if expires_at < time.time():
        _SIMPLE_REPLY_CACHE.pop(key, None)
        return None
    return text


def _simple_reply_cache_set(message: str, locale: str, brief: bool, reply: str) -> None:
    if not reply.strip():
        return
    if len(_SIMPLE_REPLY_CACHE) >= _SIMPLE_REPLY_MAX:
        _SIMPLE_REPLY_CACHE.pop(next(iter(_SIMPLE_REPLY_CACHE)), None)
    key = _simple_cache_key(message, locale, brief)
    _SIMPLE_REPLY_CACHE[key] = (time.time() + _SIMPLE_REPLY_TTL_S, reply.strip())


class HuggingFaceAIService(AIService):
    """Chat via Hugging Face Inference Providers (OpenAI-compatible API).

    Default stack for this project: HF chat + local RAG + optional web search.
    """

    def __init__(
        self,
        conversation_store: ConversationStore | None = None,
        *,
        rag_service: RAGService | None = None,
        web_search_service: WebSearchService | None = None,
        api_base_url: str | None = None,
        model: str | None = None,
        api_token: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
        rag_top_k: int | None = None,
        web_search_max_results: int | None = None,
    ) -> None:
        settings = get_settings()
        self._store = conversation_store or InMemoryConversationStore()
        self._rag = rag_service if rag_service is not None else get_rag_service()
        self._web = (
            web_search_service
            if web_search_service is not None
            else get_web_search_service()
        )
        self._rag_top_k = rag_top_k if rag_top_k is not None else settings.rag_top_k
        self._web_max = (
            web_search_max_results
            if web_search_max_results is not None
            else settings.web_search_max_results
        )
        self._base_url = (api_base_url or settings.hf_api_base_url).rstrip("/")
        self._model = model or settings.hf_model_id
        self._token = (
            api_token
            if api_token is not None
            else (settings.huggingface_hub_token or settings.hf_token)
        ).strip()
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.hf_timeout_seconds
        )
        self._client = client
        self._max_tokens = settings.llm_max_tokens
        self._voice_max_tokens = settings.llm_voice_max_tokens
        self._history_n = settings.llm_history_messages
        self._voice_history_n = settings.llm_voice_history_messages
        self._web_timeout = settings.web_search_timeout_seconds
        self._voice_web_timeout = settings.voice_web_search_timeout_seconds

    async def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
        *,
        brief: bool = False,
        locale: str = "fr",
    ) -> ChatResponse:
        timer = PhaseTimer("chat")
        full = ""
        async for event in self.stream_response(
            message,
            conversation_id,
            brief=brief,
            locale=locale,
            timer=timer,
        ):
            if event.get("type") == "token":
                full += str(event.get("text") or "")
            elif event.get("type") == "done":
                timer.log()
                raw_sources = event.get("sources") or []
                sources = [
                    item if isinstance(item, ChatSource) else ChatSource.model_validate(item)
                    for item in raw_sources
                ]
                ui = event.get("ui") if isinstance(event.get("ui"), dict) else {}
                payload = {
                    "conversation_id": str(event.get("conversation_id")),
                    "role": "assistant",
                    "message": str(event.get("text") or full),
                    "text": str(event.get("text") or full),
                    "provider": "huggingface",
                    "sources": sources,
                    **ui,
                }
                return ChatResponse.model_validate(payload)
            elif event.get("type") == "error":
                code = str(event.get("code") or "")
                detail = str(event.get("message") or "LLM failed")
                if code in {"hf_auth", "HuggingFaceAuthError"}:
                    raise HuggingFaceAuthError(detail)
                if code in {"HuggingFaceUnavailableError", "hf_unavailable"}:
                    raise HuggingFaceUnavailableError(detail)
                if code in {"GenerationTimeoutError", "timeout"}:
                    raise GenerationTimeoutError(detail)
                raise GenerationFailedError(detail)
        raise GenerationFailedError()

    async def stream_response(
        self,
        message: str,
        conversation_id: str | None = None,
        *,
        brief: bool = False,
        locale: str = "fr",
        timer: PhaseTimer | None = None,
        turn_id: str | None = None,
        llm_trace: LlmStreamTrace | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield route / token / done / error events for voice or SSE clients."""
        timer = timer or PhaseTimer("stream")
        trace = llm_trace or LlmStreamTrace(
            turn_id=turn_id or timer.turn_id,
            model=self._model,
        )
        if not trace.model:
            trace.model = self._model
        trace.wall0 = time.perf_counter()
        trace.mark("llm_start")
        if not self._token:
            yield {"type": "error", "code": "hf_auth", "message": "Missing HF token"}
            return

        try:
            history_window = self._voice_history_n if brief else self._history_n
            # Fetch only what the LLM payload will use (SQL LIMIT in Sql store).
            thread_id, history = await self._store.prepare_for_generation(
                conversation_id,
                limit=history_window,
            )
            store_trace = getattr(self._store, "last_trace", None)
            if store_trace is not None:
                trace.set_meta(store=store_trace.as_dict())
                for op in store_trace.ops:
                    timer.mark(f"store_{op.name}", op.duration_ms)
                timer.mark("store_prepare_total", store_trace.total_ms())
            trace.mark(
                "conversation_store_start_done",
                mode=(store_trace.meta.get("mode") if store_trace else None),
            )
            trace.mark(
                "conversation_history_loaded",
                history_len=len(history),
                limit=history_window,
            )

            settings = get_settings()

            # Phase 2.5 — Agent Orchestrator (feature-flagged). Default OFF.
            # On failure: fall through to the existing Phase-1 pipeline.
            if settings.agent_orchestrator_enabled:
                try:
                    async for event in self._stream_via_orchestrator(
                        message,
                        thread_id=thread_id,
                        brief=brief,
                        locale=locale,
                        timer=timer,
                        turn_id=turn_id,
                        trace=trace,
                        history=history,
                    ):
                        yield event
                    return
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "orchestrator_failed_fallback request_id=%s",
                        turn_id,
                    )
                    timer.mark("orchestrator_fallback", 1.0)
                    trace.set_meta(orchestrator_fallback=True)

            with timer.phase("routing"):
                route = route_query(message)
            trace.mark("routing_done", kind=route.kind, skip_kb=route.skip_kb)

            # Phase 2.5 observe — metrics only, deterministic Agent 4, no extra LLM.
            if (
                settings.agent_orchestrator_observe
                and not settings.agent_orchestrator_enabled
            ):
                try:
                    from app.services.agents.orchestrator import AgentOrchestrator

                    orch = AgentOrchestrator(
                        prefer_deterministic=True,
                        web_search=None,  # do not double external web on observe path
                    )
                    orch_result = await orch.run(
                        message,
                        mode="voice" if brief else "text",
                        locale=locale,
                        request_id=turn_id,
                    )
                    timer.mark(
                        "agent_orchestrator",
                        orch_result.timings.total_ms or 0.0,
                    )
                    trace.set_meta(agent_orchestrator=orch_result.observability())
                except Exception:  # noqa: BLE001
                    logger.exception("agent_orchestrator_observe_failed")

            # Phase 2.1 progressive observe — never changes which route is used.
            if settings.intent_router_observe:
                try:
                    from app.services.agents.intent import classify_intent

                    intent = classify_intent(
                        message,
                        locale=locale,
                        mode="voice" if brief else "text",
                        request_id=turn_id,
                    )
                    timer.mark("intent_router", intent.router_latency_ms or 0.0)
                    trace.set_meta(intent_router=intent.observability())
                    yield {
                        "type": "route",
                        "kind": route.kind,
                        "skip_kb": route.skip_kb,
                        "skip_web": route.skip_web,
                        "reason": route.reason,
                        "intent": intent.observability(),
                    }
                except Exception:  # noqa: BLE001
                    logger.exception("intent_router_observe_failed")
                    yield {
                        "type": "route",
                        "kind": route.kind,
                        "skip_kb": route.skip_kb,
                        "skip_web": route.skip_web,
                        "reason": route.reason,
                    }
            else:
                yield {
                    "type": "route",
                    "kind": route.kind,
                    "skip_kb": route.skip_kb,
                    "skip_web": route.skip_web,
                    "reason": route.reason,
                }

            # Phase 2.2 progressive observe — never changes grounding / answer.
            if get_settings().knowledge_agent_observe:
                try:
                    from app.services.agents.intent import classify_intent
                    from app.services.agents.knowledge import retrieve_knowledge

                    intent_obs = classify_intent(
                        message,
                        locale=locale,
                        mode="voice" if brief else "text",
                        request_id=turn_id,
                    )
                    knowledge_obs = await retrieve_knowledge(
                        message,
                        intent_obs,
                        request_id=turn_id,
                    )
                    timer.mark(
                        "knowledge_agent",
                        knowledge_obs.total_agent2_ms or 0.0,
                    )
                    trace.set_meta(knowledge_agent=knowledge_obs.observability())

                    if get_settings().tourism_planner_observe:
                        from app.services.agents.planner import build_tourism_plan

                        plan_obs = build_tourism_plan(
                            message,
                            intent_obs,
                            knowledge_obs,
                            request_id=turn_id,
                        )
                        timer.mark(
                            "tourism_planner",
                            plan_obs.total_planner_ms or 0.0,
                        )
                        trace.set_meta(tourism_planner=plan_obs.observability())
                except Exception:  # noqa: BLE001
                    logger.exception("knowledge_agent_observe_failed")

            elif get_settings().tourism_planner_observe:
                # Planner observe without knowledge observe: still run Agent1→2→3 for metrics.
                try:
                    from app.services.agents.intent import classify_intent
                    from app.services.agents.knowledge import retrieve_knowledge
                    from app.services.agents.planner import build_tourism_plan

                    intent_obs = classify_intent(
                        message,
                        locale=locale,
                        mode="voice" if brief else "text",
                        request_id=turn_id,
                    )
                    knowledge_obs = await retrieve_knowledge(
                        message,
                        intent_obs,
                        request_id=turn_id,
                    )
                    plan_obs = build_tourism_plan(
                        message,
                        intent_obs,
                        knowledge_obs,
                        request_id=turn_id,
                    )
                    timer.mark("tourism_planner", plan_obs.total_planner_ms or 0.0)
                    trace.set_meta(tourism_planner=plan_obs.observability())
                except Exception:  # noqa: BLE001
                    logger.exception("tourism_planner_observe_failed")

            if get_settings().response_agent_observe:
                # Deterministic Agent 4 only — no extra LLM call (protects TTFA).
                try:
                    from app.services.agents.intent import classify_intent
                    from app.services.agents.knowledge import retrieve_knowledge
                    from app.services.agents.planner import build_tourism_plan
                    from app.services.agents.response import generate_response

                    intent_obs = classify_intent(
                        message,
                        locale=locale,
                        mode="voice" if brief else "text",
                        request_id=turn_id,
                    )
                    knowledge_obs = await retrieve_knowledge(
                        message,
                        intent_obs,
                        request_id=turn_id,
                    )
                    plan_obs = None
                    if intent_obs.needs_planner or intent_obs.intent in {
                        "ITINERARY",
                        "BUDGET_TRIP",
                        "NATURE",
                        "CULTURE",
                    }:
                        plan_obs = build_tourism_plan(
                            message,
                            intent_obs,
                            knowledge_obs,
                            request_id=turn_id,
                        )
                    final_obs = await generate_response(
                        message,
                        intent_obs,
                        knowledge_obs,
                        plan_obs,
                        response_mode="voice" if brief else "text",
                        locale=locale,
                        request_id=turn_id,
                        prefer_deterministic=True,
                    )
                    timer.mark("response_agent", final_obs.total_agent4_ms or 0.0)
                    trace.set_meta(response_agent=final_obs.observability())
                except Exception:  # noqa: BLE001
                    logger.exception("response_agent_observe_failed")

            # Safe response cache for exact greetings / chitchat (no KB, no personalization).
            cached = _simple_reply_cache_get(message, locale, brief) if route.skip_kb else None
            if cached:
                timer.mark("rag", 0.0)
                timer.mark("web", 0.0)
                timer.mark("prompt", 0.0)
                timer.mark("grounding", 0.0)
                timer.mark("llm_ttft", 0.0)
                timer.mark("llm", 0.0)
                timer.mark("cache_hit", 1.0)
                trace.set_meta(cache_hit=True)
                trace.mark("cache_hit")
                await self._store.add_messages(
                    thread_id,
                    [("user", message), ("assistant", cached)],
                )
                trace.note_first_token(chars=len(cached))
                trace.note_first_useful_text(text=cached)
                trace.note_first_phrase_ready(text=cached)
                yield {"type": "token", "text": cached}
                trace.note_llm_end()
                yield {
                    "type": "done",
                    "conversation_id": thread_id,
                    "text": cached,
                    "sources": [],
                    "metrics": timer.as_dict(),
                    "llm_trace": trace.as_dict(),
                }
                return

            grounding = await build_grounded_system_prompt(
                message,
                history,
                rag_service=self._rag,
                web_search_service=self._web,
                rag_top_k=max(2, self._rag_top_k - 1) if brief else self._rag_top_k,
                web_search_max_results=(
                    min(2, self._web_max) if brief else self._web_max
                ),
                web_search_timeout_seconds=(
                    self._voice_web_timeout if brief else self._web_timeout
                ),
                brief=brief,
                skip_kb=route.skip_kb,
                skip_web=route.skip_web,
                locale=locale,
                timer=timer,
            )
            sources = sources_from_knowledge(grounding.chunks)
            trace.mark(
                "prompt_ready",
                system_chars=len(grounding.system_prompt),
                kb_chunks=len(grounding.chunks),
                grounding_ms=(grounding.phases_ms or {}).get("grounding"),
                rag_ms=(grounding.phases_ms or {}).get("rag"),
            )

            payload_messages: list[dict[str, str]] = [
                {"role": "system", "content": grounding.system_prompt},
                *history[-history_window:],
                {"role": "user", "content": f"{message}{locale_user_suffix(locale)}"},
            ]
            trace.mark(
                "request_object_created",
                message_count=len(payload_messages),
                history_window=history_window,
            )

            reply_parts: list[str] = []
            first_token = True
            llm_started = time.perf_counter()
            phrase_buf = ""
            first_phrase = True
            from app.services.speech.voice_chunker import (
                append_token,
                flush_remainder,
                split_ready_phrases,
            )

            with timer.phase("llm"):
                async for token in self._stream_tokens(
                    payload_messages,
                    brief=brief,
                    trace=trace,
                ):
                    if first_token:
                        timer.mark(
                            "llm_ttft",
                            (time.perf_counter() - llm_started) * 1000,
                        )
                        # Also record TTFT from stream_response llm_start (includes prepare).
                        timer.mark(
                            "app_ttft",
                            (time.perf_counter() - trace.wall0) * 1000,
                        )
                        first_token = False
                        trace.note_first_token(chars=len(token))
                    reply_parts.append(token)
                    if brief:
                        phrase_buf = append_token(phrase_buf, token)
                        if trace.first_useful_text_ms is None and phrase_buf.strip():
                            trace.note_first_useful_text(text=phrase_buf.strip()[:64])
                        ready, phrase_buf = split_ready_phrases(
                            phrase_buf, first_chunk=first_phrase
                        )
                        if ready and first_phrase:
                            trace.note_first_phrase_ready(text=ready[0])
                            first_phrase = False
                    yield {"type": "token", "text": token}

            if brief and trace.first_phrase_ready_ms is None:
                for part in flush_remainder(phrase_buf):
                    trace.note_first_phrase_ready(text=part)
                    break

            reply = "".join(reply_parts).strip()
            if not reply:
                trace.note_error("empty_reply")
                yield {
                    "type": "error",
                    "code": "empty_reply",
                    "message": "The language model returned an empty answer.",
                    "llm_trace": trace.as_dict(),
                }
                return

            if route.skip_kb:
                _simple_reply_cache_set(message, locale, brief, reply)

            # Persist after stream (single session/commit) — does not block TTFT.
            await self._store.add_messages(
                thread_id,
                [("user", message), ("assistant", reply)],
            )
            if getattr(self._store, "last_trace", None) is not None:
                trace.set_meta(store_persist=self._store.last_trace.as_dict())
            trace.note_llm_end()
            if trace.llm_prepare_ms is not None:
                timer.mark("llm_prepare", trace.llm_prepare_ms)
            if trace.provider_ttfh_ms is not None:
                timer.mark("provider_ttfh", trace.provider_ttfh_ms)
            if trace.stream_parse_ms is not None:
                timer.mark("stream_parse", trace.stream_parse_ms)
            if trace.fallback_used:
                timer.mark("fallback_used", 1.0)
            timer.mark("provider_attempts", float(trace.provider_attempt_count))
            timer.mark("retry_count", float(trace.retry_count))
            yield {
                "type": "done",
                "conversation_id": thread_id,
                "text": reply,
                "sources": [source.model_dump() for source in sources],
                "metrics": timer.as_dict(),
                "llm_trace": trace.as_dict(),
            }
        except (
            HuggingFaceAuthError,
            HuggingFaceUnavailableError,
            GenerationTimeoutError,
        ) as exc:
            trace.note_error(str(exc))
            yield {
                "type": "error",
                "code": type(exc).__name__,
                "message": str(exc),
                "llm_trace": trace.as_dict(),
            }
        except Exception as exc:  # noqa: BLE001
            logger.exception("stream_response failed")
            trace.note_error(str(exc) or "Generation failed")
            yield {
                "type": "error",
                "code": "generation_failed",
                "message": str(exc) or "Generation failed",
                "llm_trace": trace.as_dict(),
            }

    async def _stream_via_orchestrator(
        self,
        message: str,
        *,
        thread_id: str,
        brief: bool,
        locale: str,
        timer: PhaseTimer,
        turn_id: str | None,
        trace: LlmStreamTrace,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Serve a turn through AgentOrchestrator (Agents 1–4).

        Voice + USE_LLM + VOICE_LLM_STREAMING_ENABLED:
            Agents 1–3 prepare, then Qwen tokens stream live into the voice
            chunker/TTS worker (true overlap).

        Otherwise:
            Full Agent 4 result, then token emit (deterministic or complete-then-speak).
        """
        from app.services.agents.orchestrator import AgentOrchestrator
        from app.services.agents.response.agent import ResponseGenerator
        from app.services.agents.response.fallback import render_deterministic
        from app.services.speech.voice_chunker import (
            append_token,
            flush_remainder,
            split_ready_phrases,
        )

        settings = get_settings()
        if settings.agent_orchestrator_force_fail:
            raise RuntimeError("AGENT_ORCHESTRATOR_FORCE_FAIL canary injection")

        use_llm = bool(settings.agent_orchestrator_use_llm)
        true_stream = bool(
            brief and use_llm and settings.voice_llm_streaming_enabled
        )
        conv_ctx = [
            m for m in (history or []) if isinstance(m, dict) and m.get("role") == "user"
        ][-3:]

        if true_stream:
            async for event in self._stream_via_orchestrator_true_stream(
                message,
                thread_id=thread_id,
                brief=brief,
                locale=locale,
                timer=timer,
                turn_id=turn_id,
                trace=trace,
                conversation_context=conv_ctx,
            ):
                yield event
            return

        # --- Legacy orchestrator path: complete Agent 4 then emit tokens ---
        with timer.phase("orchestrator"):
            llm_complete = None
            if use_llm:
                llm_complete = self._make_agent4_llm_complete(brief=brief, trace=trace)
            orch = AgentOrchestrator(
                prefer_deterministic=not use_llm,
                llm_complete=llm_complete,
                web_search=self._web,
                rag=self._rag,
                web_tool_caller=(
                    self._make_web_tool_caller() if use_llm and not brief else None
                ),
            )
            result = await orch.run(
                message,
                mode="voice" if brief else "text",
                locale=locale,
                request_id=turn_id,
                conversation_context=conv_ctx,
            )

        timer.mark("agent_orchestrator", result.timings.total_ms or 0.0)
        if result.timings.intent_ms is not None:
            timer.mark("intent_router", result.timings.intent_ms)
        if result.timings.knowledge_ms is not None:
            timer.mark("knowledge_agent", result.timings.knowledge_ms)
        if result.timings.planner_ms is not None:
            timer.mark("tourism_planner", result.timings.planner_ms)
        if result.timings.response_ms is not None:
            timer.mark("response_agent", result.timings.response_ms)
        orch_obs = result.observability()
        llm_meta = getattr(self, "_last_agent4_llm", None) or {}
        orch_obs["llm"] = {
            "use_llm_flag": use_llm,
            "streaming": False,
            "model": self._model,
            "calls": int(llm_meta.get("calls") or 0),
            "http_status": llm_meta.get("http_status"),
            "ttft_ms": llm_meta.get("ttft_ms"),
            "total_ms": llm_meta.get("total_ms"),
            "fallback_used": result.final_response.fallback_used,
        }
        trace.set_meta(agent_orchestrator=orch_obs)

        intent = result.intent
        skip_kb = intent.intent in {"CLARIFICATION", "SIMPLE_QA"} and not intent.needs_places
        skip_web = not intent.needs_web
        yield {
            "type": "route",
            "kind": "orchestrated",
            "skip_kb": skip_kb,
            "skip_web": skip_web,
            "reason": f"orchestrator:{intent.intent}",
            "intent": intent.observability(),
            "orchestrator": orch_obs,
        }

        reply = (result.final_response.text or "").strip()
        if not reply:
            raise GenerationFailedError("Orchestrator returned an empty answer.")

        sources: list[ChatSource] = []
        for src in result.final_response.sources:
            sources.append(
                ChatSource(
                    title=src.name or src.source_id,
                    organization=None,
                    url=src.url,
                )
            )

        ui = build_structured_ui(
            final=result.final_response,
            knowledge=result.knowledge,
            plan=result.plan,
            vision_summary=result.vision_summary,
            language=result.final_response.language or locale,
            intent=result.intent,
            images=result.images,
        )
        # Enrich legacy ChatSource cards from structured places when possible.
        if not sources and ui.get("places"):
            for place in ui["places"][:8]:
                sources.append(
                    ChatSource(
                        title=place.name,
                        city=place.city,
                        region=place.region,
                        category=place.category,
                        url=place.source_url,
                        image_url=place.image_url,
                    )
                )

        timer.mark("rag", 0.0)
        timer.mark("web", float(result.timings.web_ms or 0.0))
        timer.mark("prompt", 0.0)
        timer.mark("grounding", 0.0)
        timer.mark("llm_ttft", float(result.final_response.llm_ttft_ms or 0.0))
        timer.mark("llm", float(result.final_response.llm_generation_ms or 0.0))
        timer.mark("cache_hit", 0.0)
        if ui.get("structured_build_ms") is not None:
            timer.mark("structured_ui", float(ui["structured_build_ms"]))
        trace.set_meta(orchestrator_enabled=True, structured_ui_ms=ui.get("structured_build_ms"))
        trace.mark("orchestrator_response_ready", chars=len(reply))
        if result.web_research:
            ui["web_research"] = {
                **result.web_research,
                "answer_replaced_by_fallback": result.final_response.replaced_violations,
            }
        log_chat_observability(result.intent, result.knowledge, ui)

        phrase_buf = ""
        first_phrase = True
        parts = reply.split(" ")
        first_token = True
        for i, word in enumerate(parts):
            token = word if i == 0 else f" {word}"
            if first_token:
                timer.mark("app_ttft", (time.perf_counter() - trace.wall0) * 1000)
                first_token = False
                trace.note_first_token(chars=len(token))
            if brief:
                phrase_buf = append_token(phrase_buf, token)
                if trace.first_useful_text_ms is None and phrase_buf.strip():
                    trace.note_first_useful_text(text=phrase_buf.strip()[:64])
                ready, phrase_buf = split_ready_phrases(
                    phrase_buf, first_chunk=first_phrase
                )
                if ready and first_phrase:
                    trace.note_first_phrase_ready(text=ready[0])
                    first_phrase = False
            yield {"type": "token", "text": token}

        if brief and trace.first_phrase_ready_ms is None:
            for part in flush_remainder(phrase_buf):
                trace.note_first_phrase_ready(text=part)
                break

        await self._store.add_messages(
            thread_id,
            [("user", message), ("assistant", reply)],
        )
        if getattr(self._store, "last_trace", None) is not None:
            trace.set_meta(store_persist=self._store.last_trace.as_dict())
        trace.note_llm_end()
        yield {
            "type": "done",
            "conversation_id": thread_id,
            "text": reply,
            "sources": [source.model_dump() for source in sources],
            "ui": _serialize_ui(ui),
            "metrics": timer.as_dict(),
            "llm_trace": trace.as_dict(),
            "orchestrator": orch_obs,
        }

    async def _stream_via_orchestrator_true_stream(
        self,
        message: str,
        *,
        thread_id: str,
        brief: bool,
        locale: str,
        timer: PhaseTimer,
        turn_id: str | None,
        trace: LlmStreamTrace,
        conversation_context: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """True Qwen STREAM → token events (voice WS chunker/TTS overlaps)."""
        from app.services.agents.orchestrator import AgentOrchestrator
        from app.services.agents.response.agent import ResponseGenerator
        from app.services.agents.response.fallback import render_deterministic
        from app.services.agents.response.context import (
            map_response_type,
            resolve_language,
        )
        from app.services.agents.response.models import FinalResponse, SourceReference

        logger.info("[VOICE] qwen_stream_started")
        orch = AgentOrchestrator(
            prefer_deterministic=True,
            web_search=self._web,
            rag=self._rag,
        )
        with timer.phase("orchestrator_prepare"):
            ctx = await orch.prepare(
                message,
                mode="voice" if brief else "text",
                locale=locale,
                request_id=turn_id,
                conversation_context=(
                    "\n".join(
                        str(m.get("content") or "")[:120]
                        for m in (conversation_context or [])
                        if isinstance(m, dict)
                    )[:400]
                    or None
                ),
            )

        timer.mark("agent_orchestrator", ctx.timings.total_ms or 0.0)
        if ctx.timings.intent_ms is not None:
            timer.mark("intent_router", ctx.timings.intent_ms)
        if ctx.timings.knowledge_ms is not None:
            timer.mark("knowledge_agent", ctx.timings.knowledge_ms)
        if ctx.timings.planner_ms is not None:
            timer.mark("tourism_planner", ctx.timings.planner_ms)

        agents_called = list(ctx.agents_called) + ["response"]
        intent = ctx.intent
        knowledge = ctx.knowledge
        plan = ctx.plan

        from app.core.config import get_settings as _gs
        from app.services.agents.response.evidence import (
            build_allowed_evidence,
            evidence_is_insufficient_for_llm,
        )
        from app.services.agents.response.grounding_enforcement import (
            catalog_place_names,
            validate_grounding,
        )

        settings = _gs()
        enforce = bool(settings.grounding_enforcement_enabled)
        skip_llm = enforce and evidence_is_insufficient_for_llm(
            intent, knowledge, plan, user_query=message
        )

        orch_obs: dict[str, Any] = {
            "request_id": ctx.request_id,
            "intent": intent.intent,
            "mode": ctx.mode,
            "agents_called": agents_called,
            "intent_ms": ctx.timings.intent_ms,
            "knowledge_ms": ctx.timings.knowledge_ms,
            "planner_ms": ctx.timings.planner_ms,
            "streaming": True,
            "grounding_enforcement": enforce,
            "llm": {
                "use_llm_flag": True,
                "streaming": True,
                "model": self._model,
                "calls": 0,
                "skipped_insufficient_evidence": skip_llm,
            },
        }
        trace.set_meta(agent_orchestrator=orch_obs)

        skip_kb = intent.intent in {"CLARIFICATION", "SIMPLE_QA"} and not intent.needs_places
        skip_web = not intent.needs_web
        yield {
            "type": "route",
            "kind": "orchestrated_stream",
            "skip_kb": skip_kb,
            "skip_web": skip_web,
            "reason": f"orchestrator_stream:{intent.intent}",
            "intent": intent.observability(),
            "orchestrator": orch_obs,
        }

        # Phase 2.7 — empty fact-heavy evidence: deterministic only (0 LLM calls)
        if skip_llm:
            language = resolve_language(intent, locale)
            text = render_deterministic(
                message,
                intent,
                knowledge,
                plan,
                language=language,
                response_mode="voice" if brief else "text",
            )
            logger.info("[GROUNDING] stream_skip_llm insufficient_evidence")
            reply_parts: list[str] = []
            for i, word in enumerate(text.split(" ")):
                piece = word if i == 0 else f" {word}"
                reply_parts.append(piece)
                yield {"type": "token", "text": piece}
            evidence = build_allowed_evidence(intent, knowledge, plan)
            g_report = validate_grounding(
                text, evidence, catalog_names=set(), enforcement_enabled=enforce
            )
            timer.mark("grounding", g_report.validation_ms)
            timer.mark("llm", 0.0)
            timer.mark("llm_ttft", 0.0)
            timer.mark("response_agent", g_report.validation_ms)
            self._last_agent4_llm = {
                "calls": 0,
                "http_status": None,
                "ttft_ms": None,
                "total_ms": 0.0,
                "model": self._model,
                "streaming": True,
                "skipped_insufficient_evidence": True,
            }
            orch_obs["llm"] = {
                "use_llm_flag": True,
                "streaming": True,
                "model": self._model,
                "calls": 0,
                "skipped_insufficient_evidence": True,
                "fallback_used": True,
                "grounding": g_report.as_dict(),
            }
            await self._store.add_messages(
                thread_id,
                [("user", message), ("assistant", text.strip())],
            )
            trace.note_llm_end()
            stream_ui = build_structured_ui(
                knowledge=knowledge,
                plan=plan,
                vision_summary=ctx.vision_summary,
                language=language,
                intent=intent,
                images=ctx.images,
            )
            stream_ui["response_type"] = map_response_type(intent, plan)
            stream_ui["web_research"] = ctx.web_research
            log_chat_observability(intent, knowledge, stream_ui)
            timer.mark("structured_ui", float(stream_ui.get("structured_build_ms") or 0.0))
            yield {
                "type": "done",
                "conversation_id": thread_id,
                "text": text.strip(),
                "sources": [],
                "ui": _serialize_ui(stream_ui),
                "metrics": timer.as_dict(),
                "llm_trace": trace.as_dict(),
                "orchestrator": orch_obs,
            }
            return

        generator = ResponseGenerator(prefer_deterministic=True)
        messages = generator.build_messages(
            message,
            intent,
            knowledge,
            plan,
            response_mode="voice" if brief else "text",
            locale=locale,
        )

        self._last_agent4_llm = {
            "calls": 1,
            "http_status": None,
            "ttft_ms": None,
            "total_ms": None,
            "model": self._model,
            "streaming": True,
        }
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.45,
            "max_tokens": self._token_budget(brief, messages),
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": False},
        }

        reply_parts = []
        fallback_used = False
        qwen_finished = False
        first_token = True
        llm_started = time.perf_counter()
        text_chunks_emitted = 0

        timer.mark("rag", 0.0)
        timer.mark("web", float(ctx.timings.web_ms or 0.0))
        timer.mark("prompt", 0.0)
        timer.mark("cache_hit", 0.0)
        trace.set_meta(orchestrator_enabled=True, voice_llm_streaming=True)

        try:
            async for token in self._iter_completion_tokens(body, trace=trace):
                if first_token:
                    ttft = (time.perf_counter() - llm_started) * 1000.0
                    timer.mark("llm_ttft", ttft)
                    timer.mark("app_ttft", (time.perf_counter() - trace.wall0) * 1000)
                    self._last_agent4_llm["ttft_ms"] = round(ttft, 1)
                    self._last_agent4_llm["http_status"] = int(
                        getattr(self, "_last_hf_http_status", 200) or 200
                    )
                    first_token = False
                    trace.note_first_token(chars=len(token))
                    logger.info("[VOICE] first_llm_token")
                reply_parts.append(token)
                text_chunks_emitted += 1
                yield {"type": "token", "text": token}
            qwen_finished = True
            logger.info("[VOICE] qwen_stream_finished")
        except Exception as exc:  # noqa: BLE001
            status = getattr(self, "_last_hf_http_status", None)
            self._last_agent4_llm["http_status"] = status
            self._last_agent4_llm["error"] = type(exc).__name__
            self._last_agent4_llm["total_ms"] = round(
                (time.perf_counter() - llm_started) * 1000.0, 1
            )
            logger.exception("[VOICE] qwen_stream_failed using deterministic fallback")
            # Max 1 LLM call — do not retry. Fallback only if nothing spoken yet
            # OR append remaining via deterministic only when empty.
            if not reply_parts:
                fallback_used = True
                language = resolve_language(intent, locale)
                text = render_deterministic(
                    message,
                    intent,
                    knowledge,
                    plan,
                    language=language,
                    response_mode="voice" if brief else "text",
                )
                for i, word in enumerate(text.split(" ")):
                    piece = word if i == 0 else f" {word}"
                    reply_parts.append(piece)
                    yield {"type": "token", "text": piece}
            # If partial tokens already sent, keep them — no second LLM.
            qwen_finished = True

        llm_total = (time.perf_counter() - llm_started) * 1000.0
        self._last_agent4_llm["total_ms"] = round(llm_total, 1)
        self._last_agent4_llm["calls"] = 1
        timer.mark("llm", llm_total)
        timer.mark("response_agent", llm_total)
        timer.mark("text_chunks_count", float(text_chunks_emitted))

        reply = "".join(reply_parts).strip()
        if not reply:
            raise GenerationFailedError("Orchestrator stream returned an empty answer.")

        # Phase 2.7 — non-blocking post-stream grounding (does NOT rewind TTS/audio)
        evidence = build_allowed_evidence(intent, knowledge, plan)
        g_report = validate_grounding(
            reply,
            evidence,
            catalog_names=catalog_place_names() if enforce else set(),
            enforcement_enabled=enforce,
        )
        timer.mark("grounding", g_report.validation_ms)
        if not g_report.ok:
            logger.warning(
                "[GROUNDING] stream_post_check violations=%s (audio already may have started)",
                [v.kind for v in g_report.violations[:6]],
            )

        language = resolve_language(intent, locale)
        response_type = map_response_type(intent, plan)
        sources = [
            SourceReference(source_id=s.source_id, name=s.name, url=s.url)
            for s in knowledge.sources
            if s.source_id
        ]
        final = FinalResponse(
            text=reply,
            language=language,
            response_type=response_type,
            response_mode="voice" if brief else "text",
            sources=sources,
            warnings=list(knowledge.missing_information)[:4]
            + (["grounding_violation"] if not g_report.ok else []),
            confidence=0.7,
            fallback_used=fallback_used,
            request_id=ctx.request_id,
            llm_ttft_ms=self._last_agent4_llm.get("ttft_ms"),
            llm_generation_ms=self._last_agent4_llm.get("total_ms"),
            total_agent4_ms=self._last_agent4_llm.get("total_ms"),
            grounding_ok=g_report.ok,
            grounding_validation_ms=round(g_report.validation_ms, 3),
            grounding_violations=[
                f"{v.kind}:{v.detail}" for v in g_report.violations[:8]
            ],
        )

        orch_obs["response_type"] = final.response_type
        orch_obs["llm"] = {
            "use_llm_flag": True,
            "streaming": True,
            "model": self._model,
            "calls": 1,
            "http_status": self._last_agent4_llm.get("http_status"),
            "ttft_ms": self._last_agent4_llm.get("ttft_ms"),
            "total_ms": self._last_agent4_llm.get("total_ms"),
            "fallback_used": fallback_used,
            "qwen_finished": qwen_finished,
            "text_token_events": text_chunks_emitted,
            "grounding": g_report.as_dict(),
        }
        orch_obs["agents_called"] = agents_called
        trace.set_meta(agent_orchestrator=orch_obs)
        logger.info("[VOICE] final_text_flush chars=%s", len(reply))

        await self._store.add_messages(
            thread_id,
            [("user", message), ("assistant", reply)],
        )
        if getattr(self._store, "last_trace", None) is not None:
            trace.set_meta(store_persist=self._store.last_trace.as_dict())
        trace.note_llm_end()
        stream_ui = build_structured_ui(
            final=final,
            knowledge=knowledge,
            plan=plan,
            vision_summary=ctx.vision_summary,
            language=language,
            intent=intent,
            images=ctx.images,
        )
        stream_ui["web_research"] = ctx.web_research
        log_chat_observability(intent, knowledge, stream_ui)
        timer.mark("structured_ui", float(stream_ui.get("structured_build_ms") or 0.0))
        yield {
            "type": "done",
            "conversation_id": thread_id,
            "text": reply,
            "sources": [
                ChatSource(
                    title=s.name or s.source_id,
                    organization=None,
                    url=s.url,
                ).model_dump()
                for s in sources
            ],
            "ui": _serialize_ui(stream_ui),
            "metrics": timer.as_dict(),
            "llm_trace": trace.as_dict(),
            "orchestrator": orch_obs,
        }

    def _token_budget(self, brief: bool, messages: list[dict[str, str]]) -> int:
        if brief:
            return self._voice_max_tokens
        # Route answers carry a multi-section draft (transport, to confirm, what to do, sources).
        if any('"route_brief"' in (m.get("content") or "") for m in messages[-2:]):
            return max(self._max_tokens, ROUTE_MAX_TOKENS)
        return self._max_tokens

    def _make_web_tool_caller(self):
        """Non-streamed Qwen call exposing the ``web_search`` tool (decision only)."""

        async def _call(
            messages: list[dict[str, Any]], tools: list[dict[str, Any]]
        ) -> dict[str, Any] | None:
            body: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "temperature": 0.0,
                "max_tokens": 160,
                "stream": False,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            response = await self._post("/chat/completions", body)
            if response.status_code >= 400:
                raise GenerationFailedError(
                    f"web tool decision HTTP {response.status_code}"
                )
            payload = response.json()
            choices = payload.get("choices") or []
            if not choices:
                return None
            return choices[0].get("message") or None

        return _call

    def _make_agent4_llm_complete(
        self,
        *,
        brief: bool,
        trace: LlmStreamTrace | None = None,
    ):
        """One Qwen completion for Agent 4. Tracks HF status for canary; no retries."""

        async def _complete(messages: list[dict[str, str]]) -> str:
            self._last_agent4_llm = {
                "calls": 1,
                "http_status": None,
                "ttft_ms": None,
                "total_ms": None,
                "model": self._model,
            }
            body: dict[str, Any] = {
                "model": self._model,
                "messages": messages,
                "temperature": 0.45,
                "max_tokens": self._token_budget(brief, messages),
                "stream": True,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            started = time.perf_counter()
            first_token_at: float | None = None
            parts: list[str] = []
            try:
                async for token in self._iter_completion_tokens(body, trace=trace):
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                        self._last_agent4_llm["ttft_ms"] = round(
                            (first_token_at - started) * 1000.0, 1
                        )
                        self._last_agent4_llm["http_status"] = int(
                            getattr(self, "_last_hf_http_status", 200) or 200
                        )
                    parts.append(token)
            except Exception as exc:
                status = getattr(self, "_last_hf_http_status", None)
                self._last_agent4_llm["http_status"] = status
                self._last_agent4_llm["total_ms"] = round(
                    (time.perf_counter() - started) * 1000.0, 1
                )
                self._last_agent4_llm["error"] = type(exc).__name__
                raise
            text = "".join(parts).strip()
            self._last_agent4_llm["total_ms"] = round(
                (time.perf_counter() - started) * 1000.0, 1
            )
            if not text:
                raise GenerationFailedError("Agent4 Qwen returned empty text")
            return text

        return _complete

    async def _iter_completion_tokens(
        self,
        body: Mapping[str, Any],
        *,
        trace: LlmStreamTrace | None = None,  # noqa: ARG002 — reserved for shared traces
    ) -> AsyncIterator[str]:
        """Stream Qwen tokens; record HTTP status; no automatic retry loops."""
        _raise_if_llm_paused()
        read_timeout = min(self._timeout_seconds, get_settings().llm_read_timeout_seconds)
        timeout = httpx.Timeout(self._timeout_seconds, connect=10.0, read=read_timeout)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        client = self._client or shared_async_client(
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
        )
        try:
            async with client.stream(
                "POST",
                "/chat/completions",
                json=dict(body),
                headers=headers,
                timeout=timeout,
            ) as response:
                self._last_hf_http_status = int(response.status_code)
                if response.status_code >= 400:
                    detail = (await response.aread()).decode("utf-8", errors="replace")[:200]
                    if response.status_code == 402:
                        _pause_llm(_QUOTA_PAUSE_S, "quota_402")
                        raise HuggingFaceUnavailableError(
                            "You have depleted your monthly included credits. "
                            f"HTTP 402. {detail}"
                        )
                    if response.status_code in {401, 403}:
                        _pause_llm(_QUOTA_PAUSE_S, f"auth_{response.status_code}")
                        raise HuggingFaceAuthError(
                            f"Hugging Face rejected the token (HTTP {response.status_code})."
                        )
                    raise GenerationFailedError(
                        f"HF chat HTTP {response.status_code}: {detail}"
                    )
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = payload.get("choices") or []
                        if not choices:
                            continue
                        delta = (choices[0] or {}).get("delta") or {}
                        piece = delta.get("content") or ""
                        if piece:
                            yield str(piece)
        except httpx.TimeoutException as exc:
            _pause_llm(_TIMEOUT_PAUSE_S, "timeout")
            raise GenerationTimeoutError(f"LLM timed out after {read_timeout:.0f}s") from exc

    async def _stream_tokens(
        self,
        messages: list[dict[str, str]],
        *,
        brief: bool = False,
        trace: LlmStreamTrace | None = None,
    ) -> AsyncIterator[str]:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.45,
            "max_tokens": self._token_budget(brief, messages),
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if trace is not None:
            trace.mark(
                "stream_body_ready",
                max_tokens=body["max_tokens"],
                temperature=body["temperature"],
            )
        try:
            async for token in self._iter_sse_tokens(body, trace=trace):
                yield token
        except httpx.ConnectError as exc:
            logger.warning("Hugging Face connection failed: %s", exc)
            if trace is not None:
                trace.note_error(f"ConnectError: {exc}")
            raise HuggingFaceUnavailableError() from exc
        except httpx.TimeoutException as exc:
            logger.warning("Hugging Face timed out: %s", exc)
            if trace is not None:
                trace.note_error(f"Timeout: {exc}")
            raise GenerationTimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.warning("Hugging Face HTTP error: %s", exc)
            if trace is not None:
                trace.note_error(f"HTTPError: {exc}")
            raise HuggingFaceUnavailableError() from exc

    async def _iter_sse_tokens(
        self,
        body: Mapping[str, Any],
        *,
        trace: LlmStreamTrace | None = None,
    ) -> AsyncIterator[str]:
        _raise_if_llm_paused()
        timeout = httpx.Timeout(self._timeout_seconds, connect=10.0)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        if trace is not None:
            trace.mark("headers_ready")
            # Detect whether client is already warm (shared pool).
            key_exists = False
            try:
                from app.core.http import _clients

                key_exists = (self._base_url, self._timeout_seconds) in _clients and not (
                    _clients[(self._base_url, self._timeout_seconds)].is_closed
                )
            except Exception:
                key_exists = False
            trace.set_meta(http_client_warm=key_exists)
            if trace.cold is None:
                trace.cold = not key_exists
            trace.mark(
                "http_client_selected",
                warm=key_exists,
                base_url=self._base_url,
            )

        client = self._client or shared_async_client(
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
        )
        if trace is not None:
            trace.note_provider_call_started()
            trace.note_http_dispatched()

        async with client.stream(
            "POST",
            "/chat/completions",
            json=dict(body),
            headers=headers,
            timeout=timeout,
        ) as response:
            if trace is not None:
                trace.note_response_headers(response.status_code)

            if response.status_code >= 400:
                logger.warning(
                    "HF stream HTTP %s; falling back to non-stream",
                    response.status_code,
                )
                if trace is not None:
                    trace.note_fallback(
                        f"stream_http_{response.status_code}_to_non_stream"
                    )
                await response.aread()
                fallback = dict(body)
                fallback["stream"] = False
                if trace is not None:
                    trace.note_provider_call_started()
                    trace.note_http_dispatched()
                non_stream = await self._post("/chat/completions", fallback)
                if trace is not None:
                    trace.note_response_headers(non_stream.status_code)
                    trace.note_first_stream_event(kind="non_stream_json")
                text = self._parse_response(non_stream)
                if text:
                    if trace is not None:
                        # Entire reply arrives as one chunk after fallback.
                        trace.mark(
                            "non_stream_body_parsed",
                            chars=len(text),
                            note="first_token_equals_full_reply_after_fallback",
                        )
                    yield text
                return

            content_type = (response.headers.get("content-type") or "").lower()
            # Mock / providers sometimes reply with a full JSON body instead of SSE.
            if "text/event-stream" not in content_type and "json" in content_type:
                if trace is not None:
                    trace.note_fallback("content_type_json_instead_of_sse")
                raw = await response.aread()
                non_stream = httpx.Response(
                    response.status_code,
                    content=raw,
                    headers=response.headers,
                    request=response.request,
                )
                if trace is not None:
                    trace.note_first_stream_event(kind="json_body")
                text = self._parse_response(non_stream)
                if text:
                    yield text
                return

            if trace is not None:
                trace.note_stream_iterator_created()

            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                if trace is not None:
                    trace.note_first_stream_event(kind="sse_data")
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except ValueError:
                    continue
                choices = payload.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") if isinstance(choices[0], dict) else {}
                delta = delta or {}
                piece = str(
                    delta.get("content")
                    or choices[0].get("text")
                    or ""
                )
                if piece:
                    yield piece

    async def _post(self, path: str, body: Mapping[str, Any]) -> httpx.Response:
        timeout = httpx.Timeout(self._timeout_seconds, connect=10.0)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        client = self._client or shared_async_client(
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
        )
        return await client.post(
            path,
            json=dict(body),
            headers=headers,
            timeout=timeout,
        )

    def _parse_response(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning(
                "Hugging Face returned non-JSON (status %s)",
                response.status_code,
            )
            raise GenerationFailedError() from exc

        if not isinstance(payload, dict):
            raise GenerationFailedError()

        error = payload.get("error")
        error_text = ""
        if isinstance(error, dict):
            error_text = str(error.get("message") or error)
        elif error is not None:
            error_text = str(error)
        lowered = error_text.lower()

        if response.status_code in {401, 403}:
            raise HuggingFaceAuthError(
                "Hugging Face rejected the token. Check HUGGINGFACE_HUB_TOKEN "
                "and Inference Providers permission."
            )
        if response.status_code == 404 or "not found" in lowered:
            raise HuggingFaceUnavailableError(
                f"Hugging Face model '{self._model}' is unavailable on Inference Providers."
            )
        if "not supported by any provider" in lowered or "no provider" in lowered:
            raise HuggingFaceUnavailableError(
                f"Model '{self._model}' is not enabled for your Hugging Face account. "
                "Open https://huggingface.co/settings/inference-providers and enable a provider, "
                "or set HF_MODEL_ID to a model your providers support "
                "(example: Qwen/Qwen2.5-7B-Instruct:fastest)."
            )
        if response.status_code in {429, 502, 503, 504}:
            raise HuggingFaceUnavailableError(
                "Hugging Face Inference Providers are busy or unavailable. Try again shortly."
            )
        if response.status_code >= 400:
            logger.warning("Hugging Face error %s: %s", response.status_code, error_text)
            raise GenerationFailedError(
                error_text.strip()
                if error_text.strip()
                else "The language model failed to generate a response."
            )

        choices = payload.get("choices") or []
        if not choices:
            raise GenerationFailedError()
        message = choices[0].get("message") if isinstance(choices[0], dict) else {}
        message = message or {}
        content = str(message.get("content") or "").strip()
        if not content:
            content = str(
                message.get("reasoning_content")
                or message.get("reasoning")
                or ""
            ).strip()
        if not content:
            raise GenerationFailedError()
        return content
