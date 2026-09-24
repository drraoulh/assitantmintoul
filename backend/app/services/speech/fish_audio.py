from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import SpeechUnavailableError, SynthesisFailedError
from app.core.http import shared_async_client
from app.services.speech.base import SpeechService
import time

logger = logging.getLogger(__name__)

_MAX_TTS_CHARS = 2500


class FishAudioTTSService(SpeechService):
    """Natural TTS via Fish Audio (S2.1 Pro / free tier). STT is not supported."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._client = client

    @property
    def endpoint(self) -> str:
        base = self._settings.fish_audio_base_url.rstrip("/")
        return f"{base}/v1/tts"

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str | None = None,
    ) -> tuple[str, str | None]:
        raise SpeechUnavailableError(
            "Fish Audio is TTS-only. Set SPEECH_PROVIDER=huggingface or whisper for STT."
        )

    def _prepare(self, text: str) -> tuple[dict[str, object], dict[str, str]]:
        cleaned = (text or "").strip()
        if not cleaned:
            raise SynthesisFailedError("Empty text for speech synthesis.")
        if len(cleaned) > _MAX_TTS_CHARS:
            cleaned = cleaned[:_MAX_TTS_CHARS].rstrip() + "…"

        api_key = self._settings.fish_audio_api_key.strip()
        if not api_key:
            raise SpeechUnavailableError(
                "FISH_AUDIO_API_KEY is missing. "
                "Create a key at https://fish.audio/app/api-keys/ "
                "then set it in backend/.env."
            )

        payload: dict[str, object] = {
            "text": cleaned,
            "format": "mp3",
            "mp3_bitrate": 128,
            "normalize": True,
            "latency": "balanced",
            "prosody": {
                "speed": 1.0,
                "volume": 0,
                "normalize_loudness": True,
            },
        }
        reference_id = self._settings.fish_audio_reference_id.strip()
        if reference_id:
            payload["reference_id"] = reference_id

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "model": self._settings.fish_audio_model.strip() or "s2.1-pro-free",
            "Accept": "*/*",
        }
        return payload, headers

    async def synthesize(self, text: str) -> bytes:
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text):
            chunks.append(chunk)
        audio = b"".join(chunks)
        if not audio:
            raise SynthesisFailedError("Fish Audio returned empty audio.")
        return audio

    async def synthesize_stream(
        self,
        text: str,
        *,
        trace: dict | None = None,
    ) -> AsyncIterator[bytes]:
        payload, headers = self._prepare(text)
        timeout = httpx.Timeout(
            self._settings.fish_audio_timeout_seconds,
            connect=10.0,
        )
        client = self._client or shared_async_client(
            timeout_seconds=self._settings.fish_audio_timeout_seconds,
        )

        t0 = time.perf_counter()
        if trace is not None:
            trace["tts_request_start"] = t0

        try:
            async with client.stream(
                "POST",
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=timeout,
            ) as response:
                if trace is not None:
                    trace["tts_connection_established"] = time.perf_counter()
                    trace["connection_latency_ms"] = round(
                        (trace["tts_connection_established"] - t0) * 1000, 1
                    )
                if response.status_code == 401:
                    raise SpeechUnavailableError(
                        "Fish Audio rejected the API key. Check FISH_AUDIO_API_KEY."
                    )
                if response.status_code == 402:
                    raise SpeechUnavailableError(
                        "Fish Audio credits are exhausted. Top up or switch TTS_PROVIDER=none."
                    )
                if response.status_code >= 400:
                    detail = await response.aread()
                    logger.warning(
                        "Fish Audio TTS error status=%s detail=%s",
                        response.status_code,
                        detail[:300],
                    )
                    raise SynthesisFailedError(
                        "Fish Audio could not synthesize speech."
                    )

                first = True
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if chunk:
                        if first and trace is not None:
                            now = time.perf_counter()
                            trace["tts_first_byte"] = now
                            trace["ttfb_ms"] = round((now - t0) * 1000, 1)
                            first = False
                        yield chunk
                if trace is not None:
                    trace["tts_complete"] = time.perf_counter()
                    trace["total_tts_ms"] = round(
                        (trace["tts_complete"] - t0) * 1000, 1
                    )
        except httpx.TimeoutException as exc:
            raise SynthesisFailedError(
                "Fish Audio took too long to synthesize speech."
            ) from exc
        except httpx.HTTPError as exc:
            logger.exception("Fish Audio TTS request failed")
            raise SpeechUnavailableError(
                "Could not reach Fish Audio TTS API."
            ) from exc
