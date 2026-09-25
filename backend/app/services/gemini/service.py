"""GeminiService — one generate() call; the model decides whether to use tools."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.services.gemini.gemini_client import GeminiClient
from app.services.gemini.gemini_config import GeminiRuntimeConfig, load_gemini_config
from app.services.gemini.gemini_tools import (
    GEMINI_SYSTEM_PROMPT,
    extract_tools_used,
    extract_web_and_maps,
)
from app.services.gemini.gemini_types import (
    GeminiGenerateRequest,
    GeminiMapResult,
    GeminiResult,
    GeminiServiceError,
    GeminiWebSource,
)

logger = logging.getLogger(__name__)


class GeminiService:
    """Provider-independent interface used by the orchestrator."""

    def __init__(
        self,
        config: GeminiRuntimeConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = config or load_gemini_config()
        self._http = GeminiClient(self._config, client=client)

    async def generate(
        self,
        request: GeminiGenerateRequest,
        *,
        enabled_tools: list[str] | None = None,
    ) -> GeminiResult:
        """Single logical LLM call. Internal tool use is not a second LLM call."""
        payload = request.model_copy(deep=True)
        if enabled_tools is not None:
            payload.enabled_tools = list(enabled_tools)
        include_tools = bool(self._config.tools_enabled and payload.enabled_tools)

        last_error: GeminiServiceError | None = None
        for model in self._config.model_cascade:
            try:
                result = await self._attempt(payload, model=model, include_tools=include_tools)
                if result.ok:
                    if model != self._config.model:
                        result.fallback_used = True
                        result.warnings = list(
                            dict.fromkeys([*result.warnings, f"model_fallback:{model}"])
                        )
                    return result
                last_error = GeminiServiceError(
                    result.error or "empty Gemini response",
                    status_code=result.http_status,
                )
            except GeminiServiceError as exc:
                last_error = exc
                if exc.status_code not in {429, 500, 503, 504} and exc.status_code != 404:
                    break
                logger.warning(
                    "gemini_attempt_failed model=%s status=%s",
                    model,
                    exc.status_code,
                )
                continue

        if last_error is not None:
            raise last_error
        raise GeminiServiceError("Gemini returned an empty response.")

    async def _attempt(
        self,
        request: GeminiGenerateRequest,
        *,
        model: str,
        include_tools: bool,
    ) -> GeminiResult:
        response: httpx.Response | None = None
        attempts = 1 + max(0, self._config.max_retries)
        last_exc: GeminiServiceError | None = None
        for attempt in range(attempts):
            try:
                response = await self._http.generate_content(
                    request,
                    model=model,
                    system_prompt=GEMINI_SYSTEM_PROMPT,
                    include_tools=include_tools,
                )
            except GeminiServiceError as exc:
                last_exc = exc
                if exc.status_code in {429, 503, 504} and attempt + 1 < attempts:
                    await asyncio.sleep(0.8 * (attempt + 1))
                    continue
                raise
            if response.status_code in {429, 503} and attempt + 1 < attempts:
                await asyncio.sleep(0.8 * (attempt + 1))
                continue
            break
        if response is None:
            raise last_exc or GeminiServiceError("Gemini request failed.")

        if response.status_code in {401, 403}:
            raise GeminiServiceError("Gemini rejected the API key.", status_code=response.status_code)
        if response.status_code == 429:
            raise GeminiServiceError("Gemini quota or rate limit reached.", status_code=429)
        if response.status_code == 404:
            raise GeminiServiceError(
                f"Gemini model '{model}' is not available.",
                status_code=404,
            )
        if response.status_code >= 400:
            detail = _safe_error(response)
            raise GeminiServiceError(
                detail or f"Gemini HTTP {response.status_code}",
                status_code=response.status_code,
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise GeminiServiceError("Gemini returned non-JSON.") from exc
        if not isinstance(body, dict):
            raise GeminiServiceError("Gemini returned an invalid payload.")

        text = _extract_text(body)
        tools_used = extract_tools_used(body)
        web_raw, maps_raw = extract_web_and_maps(body)
        warnings: list[str] = []
        if text and not tools_used:
            warnings.append("unverified_internal_knowledge")
        if not text:
            return GeminiResult(
                text="",
                model=model,
                empty=True,
                error="empty Gemini response",
                http_status=response.status_code,
                raw=body,
            )
        return GeminiResult(
            text=text,
            model=model,
            tools_used=tools_used,
            web_sources=[GeminiWebSource.model_validate(item) for item in web_raw],
            map_results=[GeminiMapResult.model_validate(item) for item in maps_raw],
            warnings=warnings,
            http_status=response.status_code,
            raw=body,
        )


def _extract_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""
    first = candidates[0]
    if not isinstance(first, dict):
        return ""
    content = first.get("content")
    if not isinstance(content, dict):
        return ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            piece = part["text"].strip()
            if piece:
                chunks.append(piece)
    return "\n".join(chunks).strip()


def _safe_error(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        text = (response.text or "").strip()
        return text[:240] or None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()[:240]
    return None
