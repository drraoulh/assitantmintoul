from __future__ import annotations

import asyncio
import base64
import logging

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import SpeechUnavailableError, TranscriptionFailedError
from app.core.http import shared_async_client
from app.services.speech.audio_convert import convert_to_wav
from app.services.speech.base import SpeechService

logger = logging.getLogger(__name__)

# Hugging Face ASR rejects some browser/Expo labels (e.g. audio/mp4).
_CONTENT_TYPE_ALIASES = {
    "audio/mp4": "audio/m4a",
    "video/mp4": "audio/m4a",
    "video/webm": "audio/webm",
    "audio/x-caf": "audio/wav",
    "audio/caf": "audio/wav",
    "application/octet-stream": "audio/m4a",
}


def normalize_hf_content_type(mime_type: str | None, filename: str | None = None) -> str:
    raw = (mime_type or "").split(";")[0].strip().lower()
    if filename:
        suffix = filename.rsplit(".", 1)[-1].lower()
        by_ext = {
            "m4a": "audio/m4a",
            "mp4": "audio/m4a",
            "wav": "audio/wav",
            "wave": "audio/wav",
            "mp3": "audio/mpeg",
            "mpeg": "audio/mpeg",
            "ogg": "audio/ogg",
            "webm": "audio/webm",
            "flac": "audio/flac",
            "amr": "audio/amr",
        }
        if suffix in by_ext:
            return by_ext[suffix]
    if raw in _CONTENT_TYPE_ALIASES:
        return _CONTENT_TYPE_ALIASES[raw]
    if raw:
        return raw
    return "audio/m4a"


class HuggingFaceSpeechService(SpeechService):
    """Cloud STT via Hugging Face Inference Providers (Whisper)."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def model_id(self) -> str:
        return self._settings.hf_whisper_model_id.strip()

    @property
    def endpoint(self) -> str:
        base = self._settings.hf_inference_base_url.rstrip("/")
        return f"{base}/models/{self.model_id}"

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str | None = None,
    ) -> tuple[str, str | None]:
        if not audio_bytes:
            raise TranscriptionFailedError("Empty audio upload.")

        token = self._settings.huggingface_hub_token.strip()
        if not token:
            raise SpeechUnavailableError(
                "HUGGINGFACE_HUB_TOKEN is missing. "
                "Create a token at https://huggingface.co/settings/tokens "
                "with Inference Providers access, then set it in backend/.env."
            )

        # Convert webm/m4a/mp3/… → WAV so HF soundfile never sees unsupported containers.
        wav_bytes = await convert_to_wav(
            audio_bytes,
            mime_type=mime_type,
            filename=filename,
        )
        content_type = "audio/wav"
        upload_name = "audio.wav"

        # HF ASR pipeline rejects top-level `language` / `task` query params
        # ("unexpected keyword argument 'language'"). Force FR via generate_kwargs.
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": base64.b64encode(wav_bytes).decode("ascii"),
            "parameters": {
                "generate_kwargs": {
                    "language": "french",
                    "task": "transcribe",
                }
            },
        }

        try:
            response = await self._post_json(headers=headers, payload=payload)
        except httpx.TimeoutException as exc:
            raise TranscriptionFailedError(
                "Hugging Face took too long to transcribe the audio."
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("Hugging Face STT request failed")
            raise SpeechUnavailableError(
                "Could not reach Hugging Face Inference API."
            ) from exc

        if response.status_code == 401:
            raise SpeechUnavailableError(
                "Hugging Face rejected the token. Check HUGGINGFACE_HUB_TOKEN."
            )
        if response.status_code == 503:
            await asyncio.sleep(2.0)
            try:
                response = await self._post_json(headers=headers, payload=payload)
            except httpx.HTTPError as exc:
                raise SpeechUnavailableError(
                    "Could not reach Hugging Face Inference API."
                ) from exc
            if response.status_code == 503:
                raise SpeechUnavailableError(
                    "The Whisper model is loading on Hugging Face. Try again in a few seconds."
                )

        # Older routers may reject JSON+generate_kwargs — fall back to raw WAV bytes.
        if response.status_code >= 400:
            detail = _safe_error_message(response)
            logger.warning(
                "HF STT JSON path status=%s detail=%s; trying raw wav fallback (%s)",
                response.status_code,
                detail,
                upload_name,
            )
            response = await self._post_raw(
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                    "Content-Type": content_type,
                },
                content=wav_bytes,
            )

        if response.status_code >= 400:
            detail = _safe_error_message(response)
            logger.warning(
                "HF STT error status=%s detail=%s",
                response.status_code,
                detail,
            )
            if detail and "model not supported" in detail.lower():
                raise SpeechUnavailableError(
                    f"{detail} Set HF_WHISPER_MODEL_ID=openai/whisper-large-v3-turbo."
                )
            raise TranscriptionFailedError(
                detail or "Hugging Face could not transcribe the audio."
            )

        text = _extract_text(response)
        if not text:
            raise TranscriptionFailedError(
                "No speech detected. Hold the mic and speak clearly, then stop."
            )
        return text, "fr"

    async def synthesize(self, text: str) -> bytes:
        raise SpeechUnavailableError(
            "Text-to-speech is disabled. Set TTS_PROVIDER=fish and FISH_AUDIO_API_KEY."
        )

    async def _post_json(
        self,
        *,
        headers: dict[str, str],
        payload: dict,
    ) -> httpx.Response:
        timeout = httpx.Timeout(
            self._settings.hf_speech_timeout_seconds,
            connect=10.0,
        )
        client = self._client or shared_async_client(
            timeout_seconds=self._settings.hf_speech_timeout_seconds,
        )
        return await client.post(
            self.endpoint,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    async def _post_raw(
        self,
        *,
        headers: dict[str, str],
        content: bytes,
    ) -> httpx.Response:
        timeout = httpx.Timeout(
            self._settings.hf_speech_timeout_seconds,
            connect=10.0,
        )
        client = self._client or shared_async_client(
            timeout_seconds=self._settings.hf_speech_timeout_seconds,
        )
        return await client.post(
            self.endpoint,
            headers=headers,
            content=content,
            timeout=timeout,
        )


def _extract_text(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        raw = response.text.strip()
        return raw

    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        if isinstance(payload.get("text"), str):
            return payload["text"].strip()
        if isinstance(payload.get("error"), str):
            raise TranscriptionFailedError(payload["error"])
    return ""


def _safe_error_message(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str) and error.strip():
            return error.strip()
    return None
