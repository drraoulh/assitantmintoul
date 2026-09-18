import logging
import re
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import (
    GenerationFailedError,
    GenerationTimeoutError,
    ModelNotInstalledError,
    OllamaUnavailableError,
)
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

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class OllamaAIService(AIService):
    """Optional local LLM adapter (legacy). Prefer HuggingFaceAIService."""

    def __init__(
        self,
        conversation_store: ConversationStore | None = None,
        *,
        rag_service: RAGService | None = None,
        web_search_service: WebSearchService | None = None,
        base_url: str | None = None,
        model: str | None = None,
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
        self._rag_top_k = (
            rag_top_k if rag_top_k is not None else settings.rag_top_k
        )
        self._web_max = (
            web_search_max_results
            if web_search_max_results is not None
            else settings.web_search_max_results
        )
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.llm_model
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.ollama_timeout_seconds
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
        thread_id = await self._store.start(conversation_id)
        history = await self._store.get_messages(thread_id)
        history_window = self._voice_history_n if brief else self._history_n
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
            provider="ollama",
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
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.6,
                "num_ctx": 4096,
                "num_predict": (
                    self._voice_max_tokens if brief else self._max_tokens
                ),
            },
        }

        try:
            response = await self._post("/api/chat", body)
        except httpx.ConnectError as exc:
            logger.warning("Ollama connection failed: %s", exc)
            raise OllamaUnavailableError() from exc
        except httpx.TimeoutException as exc:
            logger.warning("Ollama timed out: %s", exc)
            raise GenerationTimeoutError() from exc
        except httpx.HTTPError as exc:
            logger.warning("Ollama HTTP error: %s", exc)
            raise OllamaUnavailableError() from exc

        return self._parse_response(response)

    async def _post(self, path: str, body: Mapping[str, Any]) -> httpx.Response:
        timeout = httpx.Timeout(self._timeout_seconds, connect=5.0)
        if self._client is not None:
            return await self._client.post(path, json=dict(body), timeout=timeout)

        async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
            return await client.post(path, json=dict(body))

    def _parse_response(self, response: httpx.Response) -> str:
        payload: dict[str, Any]
        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("Ollama returned non-JSON (status %s)", response.status_code)
            raise GenerationFailedError() from exc

        error_text = str(payload.get("error") or "")
        lowered = error_text.lower()

        if response.status_code == 404 or "not found" in lowered:
            raise ModelNotInstalledError(self._model)
        if response.status_code in {502, 503} or "connection" in lowered:
            raise OllamaUnavailableError()
        if response.status_code >= 400:
            logger.warning("Ollama error %s: %s", response.status_code, error_text)
            raise GenerationFailedError()

        message = payload.get("message") or {}
        content = str(message.get("content") or "").strip()
        content = _THINK_BLOCK.sub("", content).strip()
        if not content:
            raise GenerationFailedError()
        return content
