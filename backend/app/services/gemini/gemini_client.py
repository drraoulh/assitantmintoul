"""Low-level Gemini generateContent client (one HTTP call per attempt)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.gemini.gemini_config import GeminiRuntimeConfig
from app.services.gemini.gemini_tools import native_tool_declarations
from app.services.gemini.gemini_types import GeminiGenerateRequest, GeminiServiceError

logger = logging.getLogger(__name__)


def build_generate_payload(
    request: GeminiGenerateRequest,
    *,
    include_tools: bool,
) -> dict[str, Any]:
    contents: list[dict[str, Any]] = []
    for turn in request.conversation[-8:]:
        role = str(turn.get("role") or "")
        text = str(turn.get("content") or "").strip()
        if not text:
            continue
        mapped = "user" if role == "user" else "model"
        contents.append({"role": mapped, "parts": [{"text": text}]})
    user_parts = [request.user_message.strip()]
    if request.kb_context and request.kb_context.strip():
        user_parts.insert(
            0,
            "Local knowledge (Supabase / catalog), not invented:\n"
            + request.kb_context.strip()[:4000],
        )
    contents.append({"role": "user", "parts": [{"text": "\n\n".join(user_parts)}]})

    payload: dict[str, Any] = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.35,
            "maxOutputTokens": 768,
        },
    }
    if include_tools:
        tools = native_tool_declarations(request.enabled_tools)
        if tools:
            payload["tools"] = tools
    return payload


class GeminiClient:
    def __init__(
        self,
        config: GeminiRuntimeConfig,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config
        self._client = client

    def endpoint(self, model: str) -> str:
        return f"{self._config.base_url}/models/{model}:generateContent"

    async def generate_content(
        self,
        request: GeminiGenerateRequest,
        *,
        model: str,
        system_prompt: str,
        include_tools: bool,
    ) -> httpx.Response:
        if not self._config.api_key:
            raise GeminiServiceError("GEMINI_API_KEY is missing.", status_code=401)

        payload = build_generate_payload(request, include_tools=include_tools)
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._config.api_key,
        }
        timeout = httpx.Timeout(self._config.timeout_seconds, connect=8.0)
        try:
            if self._client is not None:
                return await self._client.post(
                    self.endpoint(model),
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await client.post(
                    self.endpoint(model),
                    headers=headers,
                    json=payload,
                    timeout=timeout,
                )
        except httpx.TimeoutException as exc:
            raise GeminiServiceError(
                "Gemini timed out.",
                status_code=504,
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("gemini_http_error error=%s", type(exc).__name__)
            raise GeminiServiceError(
                "Could not reach the Gemini API.",
                status_code=503,
            ) from exc
