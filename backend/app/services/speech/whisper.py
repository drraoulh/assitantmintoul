from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.exceptions import SpeechUnavailableError, TranscriptionFailedError
from app.services.speech.base import SpeechService

logger = logging.getLogger(__name__)

_EXTENSIONS = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/aac": ".aac",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
    "video/webm": ".webm",
}


def whisper_model_size(model_id: str) -> str:
    name = model_id.strip().lower().split("/")[-1]
    for size in (
        "large-v3",
        "large-v2",
        "large",
        "medium",
        "small",
        "base",
        "tiny",
    ):
        if size in name:
            return size
    return "small"


def extension_for(mime_type: str, filename: str | None) -> str:
    if filename:
        suffix = Path(filename).suffix.lower()
        if suffix:
            return suffix
    return _EXTENSIONS.get(mime_type.lower().split(";")[0].strip(), ".m4a")


class WhisperSpeechService(SpeechService):
    """Local Whisper STT using faster-whisper (CPU-friendly int8)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._model = None
        self._model_lock = asyncio.Lock()

    @property
    def model_size(self) -> str:
        return whisper_model_size(self._settings.hf_whisper_model_id)

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str | None = None,
    ) -> tuple[str, str | None]:
        if not audio_bytes:
            raise TranscriptionFailedError("Empty audio upload.")

        model = await self._get_model()
        suffix = extension_for(mime_type, filename)

        def _run() -> tuple[str, str | None]:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(audio_bytes)
                temp_path = handle.name
            try:
                segments, info = model.transcribe(
                    temp_path,
                    beam_size=1,
                    vad_filter=True,
                )
                text = " ".join(segment.text.strip() for segment in segments).strip()
                language = getattr(info, "language", None)
                return text, language
            finally:
                Path(temp_path).unlink(missing_ok=True)

        try:
            text, language = await asyncio.to_thread(_run)
        except SpeechUnavailableError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Whisper transcription failed")
            raise TranscriptionFailedError() from exc

        if not text:
            raise TranscriptionFailedError(
                "No speech detected. Hold the mic and speak clearly, then stop."
            )
        return text, language

    async def synthesize(self, text: str) -> bytes:
        raise SpeechUnavailableError(
            "Text-to-speech is disabled. Set TTS_PROVIDER=fish and FISH_AUDIO_API_KEY."
        )

    async def _get_model(self):
        if self._model is not None:
            return self._model

        async with self._model_lock:
            if self._model is not None:
                return self._model

            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise SpeechUnavailableError(
                    "faster-whisper is not installed. "
                    "Run: pip install faster-whisper"
                ) from exc

            size = self.model_size
            device = self._settings.whisper_device
            compute_type = self._settings.whisper_compute_type
            logger.info(
                "Loading Whisper model size=%s device=%s compute_type=%s",
                size,
                device,
                compute_type,
            )

            def _load():
                return WhisperModel(
                    size,
                    device=device,
                    compute_type=compute_type,
                )

            try:
                self._model = await asyncio.to_thread(_load)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to load Whisper model")
                raise SpeechUnavailableError(
                    f"Could not load Whisper model '{size}'. "
                    "Check disk space and internet for the first download."
                ) from exc
            return self._model
