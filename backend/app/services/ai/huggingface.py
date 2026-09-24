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
                return ChatResponse(
                    conversation_id=str(event.get("conversation_id")),
                    role="assistant",
                    message=str(event.get("text") or full),
                    provider="huggingface",
                    sources=sources,
                )
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

            with timer.phase("routing"):
                route = route_query(message)
            trace.mark("routing_done", kind=route.kind, skip_kb=route.skip_kb)

            # Phase 2.1 progressive observe — never changes which route is used.
            if get_settings().intent_router_observe:
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
            "max_tokens": self._voice_max_tokens if brief else self._max_tokens,
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
