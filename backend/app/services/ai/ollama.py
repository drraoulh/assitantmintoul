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
from app.services.ai.prompts import SYSTEM_PROMPT
from app.services.conversation.base import ConversationStore
from app.services.conversation.memory import InMemoryConversationStore
from app.services.rag.base import PlaceholderRAGService, RAGService
from app.services.rag.context import build_system_prompt, format_knowledge_context
from app.services.rag.factory import get_rag_service

logger = logging.getLogger(__name__)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class OllamaAIService(AIService):
    """Local LLM adapter. FastAPI talks to this class; this class talks to Ollama."""

    def __init__(
        self,
        conversation_store: ConversationStore | None = None,
        *,
        rag_service: RAGService | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
        rag_top_k: int | None = None,
    ) -> None:
        settings = get_settings()
        self._store = conversation_store or InMemoryConversationStore()
        self._rag = rag_service if rag_service is not None else get_rag_service()
        self._rag_top_k = (
            rag_top_k if rag_top_k is not None else settings.rag_top_k
        )
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.llm_model
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.ollama_timeout_seconds
        )
        self._client = client

    async def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> ChatResponse:
        thread_id = await self._store.start(conversation_id)
        history = await self._store.get_messages(thread_id)
        system_prompt = await self._grounded_system_prompt(message, history)

        payload_messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": message},
        ]
        reply = await self._complete(payload_messages)

        await self._store.add_message(thread_id, "user", message)
        await self._store.add_message(thread_id, "assistant", reply)

        return ChatResponse(
            conversation_id=thread_id,
            role="assistant",
            message=reply,
            provider="ollama",
        )

    async def _grounded_system_prompt(
        self,
        message: str,
        history: list[dict[str, str]],
    ) -> str:
        if isinstance(self._rag, PlaceholderRAGService):
            return SYSTEM_PROMPT

        # Include a bit of recent user context so follow-ups like
        # "que puis-je visiter ?" still retrieve the right city.
        recent_user = " ".join(
            turn["content"]
            for turn in history[-4:]
            if turn.get("role") == "user"
        )
        query = f"{recent_user} {message}".strip()
        try:
            chunks = await self._rag.retrieve_chunks(query, top_k=self._rag_top_k)
        except Exception:
            logger.exception("RAG retrieval failed; continuing without context")
            return SYSTEM_PROMPT

        context = format_knowledge_context(chunks)
        return build_system_prompt(SYSTEM_PROMPT, context)

    async def _complete(self, messages: list[dict[str, str]]) -> str:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.6,
                "num_ctx": 4096,
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
