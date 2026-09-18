from __future__ import annotations

import logging
from collections.abc import Mapping
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
from app.schemas.chat import ChatResponse
from app.services.ai.base import AIService
from app.services.ai.grounding import build_grounded_system_prompt
from app.services.conversation.base import ConversationStore
from app.services.conversation.memory import InMemoryConversationStore
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
        if not self._token:
            raise HuggingFaceAuthError()

        thread_id = await self._store.start(conversation_id)
        history = await self._store.get_messages(thread_id)
        history_window = self._voice_history_n if brief else self._history_n
        # Voice turns trade a little context for latency.
        system_prompt = await build_grounded_system_prompt(
            message,
            history,
            rag_service=self._rag,
            web_search_service=self._web,
            rag_top_k=max(2, self._rag_top_k - 1) if brief else self._rag_top_k,
            web_search_max_results=min(2, self._web_max) if brief else self._web_max,
            web_search_timeout_seconds=(
                self._voice_web_timeout if brief else self._web_timeout
            ),
            brief=brief,
        )

        payload_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            *history[-history_window:],
            {"role": "user", "content": message},
        ]
        reply = await self._complete(payload_messages, brief=brief)

        await self._store.add_message(thread_id, "user", message)
        await self._store.add_message(thread_id, "assistant", reply)

        return ChatResponse(
            conversation_id=thread_id,
            role="assistant",
            message=reply,
            provider="huggingface",
        )

    async def _complete(
        self,
        messages: list[dict[str, str]],
        *,
        brief: bool = False,
    ) -> str:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.45,
            "max_tokens": self._voice_max_tokens if brief else self._max_tokens,
            "stream": False,
            # Qwen3.x thinking models otherwise return empty content + reasoning.
            "chat_template_kwargs": {"enable_thinking": False},
        }

        try:
            response = await self._post("/chat/completions", body)
        except httpx.ConnectError as exc:
            logger.warning("Hugging Face connection failed: %s", exc)
            raise HuggingFaceUnavailableError() from exc
        except httpx.TimeoutException as exc:
            logger.warning("Hugging Face timed out: %s", exc)
            raise GenerationTimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.warning("Hugging Face HTTP error: %s", exc)
            raise HuggingFaceUnavailableError() from exc

        return self._parse_response(response)

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
            # Some reasoning models put the visible answer in alternate fields.
            content = str(
                message.get("reasoning_content")
                or message.get("reasoning")
                or ""
            ).strip()
        if not content:
            raise GenerationFailedError()
        return content
