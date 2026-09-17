from __future__ import annotations

import logging
from pathlib import Path

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import (
    SpeechUnavailableError,
    SynthesisFailedError,
    TranscriptionFailedError,
)
from app.services.speech.base import SpeechService
from app.services.speech.whisper import extension_for

logger = logging.getLogger(__name__)

_MAX_TTS_CHARS = 4096
_FILENAME_BY_EXT = {
    ".wav": "audio.wav",
    ".mp3": "audio.mp3",
    ".m4a": "audio.m4a",
    ".mp4": "audio.m4a",
    ".webm": "audio.webm",
    ".ogg": "audio.ogg",
    ".flac": "audio.flac",
    ".aac": "audio.aac",
}


class OpenAISpeechService(SpeechService):
    """STT + TTS via OpenAI Audio API (transcriptions + speech)."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def _api_key(self) -> str:
        return self._settings.openai_api_key.strip()

    @property
    def _base_url(self) -> str:
        return self._settings.openai_base_url.rstrip("/")

    def _auth_headers(self, *, accept: str | None = None) -> dict[str, str]:
        if not self._api_key:
            raise SpeechUnavailableError(
                "OPENAI_API_KEY is missing. "
                "Create a key at https://platform.openai.com/api-keys "
                "then set it in backend/.env."
            )
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if accept:
            headers["Accept"] = accept
        return headers

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str | None = None,
    ) -> tuple[str, str | None]:
        if not audio_bytes:
            raise TranscriptionFailedError("Empty audio upload.")

        suffix = extension_for(mime_type, filename)
        upload_name = filename or _FILENAME_BY_EXT.get(suffix.lower(), f"audio{suffix}")
        if "." not in Path(upload_name).name:
            upload_name = f"{upload_name}{suffix}"

        content_type = (mime_type or "application/octet-stream").split(";")[0].strip()
        if content_type in {"audio/mp4", "video/mp4"}:
            content_type = "audio/m4a"

        data = {
            "model": self._settings.openai_stt_model.strip() or "gpt-4o-mini-transcribe",
            "response_format": "json",
        }
        # Prefer French when uncertain; OpenAI still auto-detects when omitted.
        language = self._settings.openai_stt_language.strip()
        if language:
            data["language"] = language

        files = {
            "file": (upload_name, audio_bytes, content_type or "application/octet-stream"),
        }

        try:
            response = await self._post_multipart(
                path="/audio/transcriptions",
                headers=self._auth_headers(accept="application/json"),
                data=data,
                files=files,
            )
        except httpx.TimeoutException as exc:
            raise TranscriptionFailedError(
                "OpenAI took too long to transcribe the audio."
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("OpenAI STT request failed")
            raise SpeechUnavailableError(
                "Could not reach the OpenAI Audio API."
            ) from exc

        self._raise_for_speech_status(response, kind="stt")

        text, detected = _extract_transcription(response)
        if not text:
            raise TranscriptionFailedError(
                "No speech detected. Hold the mic and speak clearly, then stop."
            )
        return text, detected

    async def synthesize(self, text: str) -> bytes:
        cleaned = (text or "").strip()
        if not cleaned:
            raise SynthesisFailedError("Empty text for speech synthesis.")
        if len(cleaned) > _MAX_TTS_CHARS:
            cleaned = cleaned[:_MAX_TTS_CHARS].rstrip() + "…"

        payload = {
            "model": self._settings.openai_tts_model.strip() or "gpt-4o-mini-tts",
            "input": cleaned,
            "voice": self._settings.openai_tts_voice.strip() or "nova",
            "response_format": "mp3",
        }
        instructions = self._settings.openai_tts_instructions.strip()
        if instructions and "gpt-4o" in str(payload["model"]):
            payload["instructions"] = instructions

        try:
            response = await self._post_json(
                path="/audio/speech",
                headers=self._auth_headers(accept="audio/mpeg"),
                payload=payload,
            )
        except httpx.TimeoutException as exc:
            raise SynthesisFailedError(
                "OpenAI took too long to synthesize speech."
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("OpenAI TTS request failed")
            raise SpeechUnavailableError(
                "Could not reach the OpenAI Audio API."
            ) from exc

        self._raise_for_speech_status(response, kind="tts")
        audio = response.content
        if not audio:
            raise SynthesisFailedError("OpenAI returned empty audio.")
        return audio

    async def _post_multipart(
        self,
        *,
        path: str,
        headers: dict[str, str],
        data: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
    ) -> httpx.Response:
        timeout = httpx.Timeout(
            self._settings.openai_speech_timeout_seconds,
            connect=10.0,
        )
        url = f"{self._base_url}{path}"
        if self._client is not None:
            return await self._client.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=timeout,
            )
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(
                url,
                headers=headers,
                data=data,
                files=files,
                timeout=timeout,
            )

    async def _post_json(
        self,
        *,
        path: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> httpx.Response:
        timeout = httpx.Timeout(
            self._settings.openai_speech_timeout_seconds,
            connect=10.0,
        )
        url = f"{self._base_url}{path}"
        json_headers = {**headers, "Content-Type": "application/json"}
        if self._client is not None:
            return await self._client.post(
                url,
                headers=json_headers,
                json=payload,
                timeout=timeout,
            )
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(
                url,
                headers=json_headers,
                json=payload,
                timeout=timeout,
            )

    def _raise_for_speech_status(
        self,
        response: httpx.Response,
        *,
        kind: str,
    ) -> None:
        if response.status_code < 400:
            return
        detail = _safe_error_message(response)
        logger.warning(
            "OpenAI %s error status=%s detail=%s",
            kind,
            response.status_code,
            detail,
        )
        if response.status_code in {401, 403}:
            raise SpeechUnavailableError(
                "OpenAI rejected the API key. Check OPENAI_API_KEY."
            )
        if response.status_code == 429:
            raise SpeechUnavailableError(
                "OpenAI rate limit reached. Wait a moment and try again."
            )
        if kind == "stt":
            raise TranscriptionFailedError(
                detail or "OpenAI could not transcribe the audio."
            )
        raise SynthesisFailedError(
            detail or "OpenAI could not synthesize speech."
        )


def _extract_transcription(response: httpx.Response) -> tuple[str, str | None]:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text, None

    if isinstance(payload, str):
        return payload.strip(), None
    if isinstance(payload, dict):
        text = payload.get("text")
        language = payload.get("language")
        return (
            text.strip() if isinstance(text, str) else "",
            language.strip() if isinstance(language, str) else None,
        )
    return "", None


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
