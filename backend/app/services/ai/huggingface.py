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
from app.services.ai.routing import route_query
from app.services.conversation.base import ConversationStore
from app.services.conversation.memory import InMemoryConversationStore
from app.services.metrics.latency import PhaseTimer
from app.services.rag.base import RAGService
from app.services.rag.factory import get_rag_service
from app.services.search.base import WebSearchService
from app.services.search.factory import get_web_search_service

logger = logging.getLogger(__name__)


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
    ) -> ChatResponse:
        timer = PhaseTimer("chat")
        full = ""
        async for event in self.stream_response(
            message,
            conversation_id,
            brief=brief,
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
        timer: PhaseTimer | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield route / token / done / error events for voice or SSE clients."""
        timer = timer or PhaseTimer("stream")
        if not self._token:
            yield {"type": "error", "code": "hf_auth", "message": "Missing HF token"}
            return

        try:
            thread_id = await self._store.start(conversation_id)
            history = await self._store.get_messages(thread_id)
            history_window = self._voice_history_n if brief else self._history_n
            route = route_query(message)
            yield {
                "type": "route",
                "kind": route.kind,
                "skip_kb": route.skip_kb,
                "skip_web": route.skip_web,
                "reason": route.reason,
            }

            with timer.phase("grounding"):
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
                )
            sources = sources_from_knowledge(grounding.chunks)

            payload_messages: list[dict[str, str]] = [
                {"role": "system", "content": grounding.system_prompt},
                *history[-history_window:],
                {"role": "user", "content": message},
            ]

            reply_parts: list[str] = []
            first_token = True
            llm_started = time.perf_counter()
            with timer.phase("llm"):
                async for token in self._stream_tokens(payload_messages, brief=brief):
                    if first_token:
                        timer.mark(
                            "llm_ttft",
                            (time.perf_counter() - llm_started) * 1000,
                        )
                        first_token = False
                    reply_parts.append(token)
                    yield {"type": "token", "text": token}

            reply = "".join(reply_parts).strip()
            if not reply:
                yield {
                    "type": "error",
                    "code": "empty_reply",
                    "message": "The language model returned an empty answer.",
                }
                return

            await self._store.add_message(thread_id, "user", message)
            await self._store.add_message(thread_id, "assistant", reply)
            yield {
                "type": "done",
                "conversation_id": thread_id,
                "text": reply,
                "sources": [source.model_dump() for source in sources],
                "metrics": timer.as_dict(),
            }
        except (
            HuggingFaceAuthError,
            HuggingFaceUnavailableError,
            GenerationTimeoutError,
        ) as exc:
            yield {"type": "error", "code": type(exc).__name__, "message": str(exc)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("stream_response failed")
            yield {
                "type": "error",
                "code": "generation_failed",
                "message": str(exc) or "Generation failed",
            }

    async def _stream_tokens(
        self,
        messages: list[dict[str, str]],
        *,
        brief: bool = False,
    ) -> AsyncIterator[str]:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.45,
            "max_tokens": self._voice_max_tokens if brief else self._max_tokens,
            "stream": True,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            async for token in self._iter_sse_tokens(body):
                yield token
        except httpx.ConnectError as exc:
            logger.warning("Hugging Face connection failed: %s", exc)
            raise HuggingFaceUnavailableError() from exc
        except httpx.TimeoutException as exc:
            logger.warning("Hugging Face timed out: %s", exc)
            raise GenerationTimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.warning("Hugging Face HTTP error: %s", exc)
            raise HuggingFaceUnavailableError() from exc

    async def _iter_sse_tokens(self, body: Mapping[str, Any]) -> AsyncIterator[str]:
        timeout = httpx.Timeout(self._timeout_seconds, connect=10.0)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        client = self._client or shared_async_client(
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
        )
        async with client.stream(
            "POST",
            "/chat/completions",
            json=dict(body),
            headers=headers,
            timeout=timeout,
        ) as response:
            if response.status_code >= 400:
                logger.warning(
                    "HF stream HTTP %s; falling back to non-stream",
                    response.status_code,
                )
                await response.aread()
                fallback = dict(body)
                fallback["stream"] = False
                non_stream = await self._post("/chat/completions", fallback)
                text = self._parse_response(non_stream)
                if text:
                    yield text
                return

            content_type = (response.headers.get("content-type") or "").lower()
            # Mock / providers sometimes reply with a full JSON body instead of SSE.
            if "text/event-stream" not in content_type and "json" in content_type:
                raw = await response.aread()
                non_stream = httpx.Response(
                    response.status_code,
                    content=raw,
                    headers=response.headers,
                    request=response.request,
                )
                text = self._parse_response(non_stream)
                if text:
                    yield text
                return

            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
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
