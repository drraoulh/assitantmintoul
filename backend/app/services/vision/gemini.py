from __future__ import annotations

import base64
import logging

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import VisionFailedError, VisionUnavailableError
from app.services.vision.base import VisionService

logger = logging.getLogger(__name__)

_MAX_IMAGE_BYTES = 8 * 1024 * 1024

_TOURISM_PROMPT = """Tu es Smartmboa Tour, guide chaleureux du Cameroun.
Analyse cette photo de voyageur.

Réponds en français, concis (80–120 mots max) :
1. Ce que tu vois (monument, plat, lieu, paysage, objet…)
2. Si c'est camerounais : ville/région et site ou plat probable
3. 2 conseils pratiques courts (visite, respect local, sécurité ou dégustation)

Si tu n'es pas sûr, dis-le. N'invente pas. Ton chaleureux et utile."""


class GeminiVisionService(VisionService):
    """Image understanding via Google Gemini generateContent (multimodal)."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def endpoint(self) -> str:
        model = self._settings.gemini_vision_model.strip() or "gemini-3.6-flash"
        base = self._settings.gemini_api_base_url.rstrip("/")
        return f"{base}/models/{model}:generateContent"

    async def identify(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
    ) -> str:
        if not image_bytes:
            raise VisionFailedError("Empty image upload.")
        if len(image_bytes) > _MAX_IMAGE_BYTES:
            raise VisionFailedError(
                "Image is too large. Keep photos under about 8 MB."
            )

        api_key = self._settings.gemini_api_key.strip()
        if not api_key:
            raise VisionUnavailableError(
                "GEMINI_API_KEY is missing. "
                "Create a key at https://aistudio.google.com/apikey "
                "then set it in backend/.env."
            )

        content_type = _normalize_mime(mime_type)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": _TOURISM_PROMPT},
                        {
                            "inline_data": {
                                "mime_type": content_type,
                                "data": base64.b64encode(image_bytes).decode(
                                    "ascii"
                                ),
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.35,
                "maxOutputTokens": 512,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        try:
            response = await self._post(headers=headers, payload=payload)
        except httpx.TimeoutException as exc:
            raise VisionFailedError(
                "Gemini took too long to analyze the image."
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("Gemini vision request failed")
            raise VisionUnavailableError(
                "Could not reach the Gemini API."
            ) from exc

        if response.status_code == 400:
            detail = _safe_error_message(response)
            raise VisionFailedError(
                detail or "Gemini rejected the image. Try another photo."
            )
        if response.status_code in {401, 403}:
            raise VisionUnavailableError(
                "Gemini rejected the API key. Check GEMINI_API_KEY."
            )
        if response.status_code == 429:
            raise VisionUnavailableError(
                "Gemini rate limit reached. Wait a moment and try again."
            )
        if response.status_code >= 400:
            detail = _safe_error_message(response)
            logger.warning(
                "Gemini vision error status=%s detail=%s",
                response.status_code,
                detail,
            )
            raise VisionFailedError(
                detail or "Gemini could not analyze the image."
            )

        text = _extract_text(response)
        if not text:
            raise VisionFailedError(
                "Gemini returned an empty description for this image."
            )
        return text

    async def _post(
        self,
        *,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> httpx.Response:
        timeout = httpx.Timeout(
            self._settings.gemini_timeout_seconds,
            connect=10.0,
        )
        if self._client is not None:
            return await self._client.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=timeout,
            )

        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=timeout,
            )


def _normalize_mime(mime_type: str | None) -> str:
    raw = (mime_type or "").split(";")[0].strip().lower()
    aliases = {
        "image/jpg": "image/jpeg",
        "image/pjpeg": "image/jpeg",
        "image/x-png": "image/png",
        "application/octet-stream": "image/jpeg",
    }
    if raw in aliases:
        return aliases[raw]
    if raw.startswith("image/"):
        return raw
    return "image/jpeg"


def _extract_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""

    if not isinstance(payload, dict):
        return ""

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
            text = part["text"].strip()
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def _safe_error_message(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:300] if text else None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()[:300]
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()[:300]
    return None
