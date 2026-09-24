from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.core.exceptions import SpeechUnavailableError


class SpeechService(ABC):
    """Speech-to-text and text-to-speech adapters.

    STT: Whisper (local faster-whisper or Hugging Face cloud).
    TTS: Fish Audio (s2.1-pro-free) when TTS_PROVIDER=fish.
    """

    @abstractmethod
    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str | None = None,
    ) -> tuple[str, str | None]:
        """Convert recorded audio into text and optional detected language."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Convert assistant text into audio bytes."""

    async def synthesize_stream(
        self,
        text: str,
        *,
        trace: dict | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield audio bytes as soon as the TTS provider streams them.

        Optional ``trace`` dict is filled with Fish timing marks (diagnostic).
        Default: buffer the full synthesize() result as a single chunk.
        """
        audio = await self.synthesize(text)
        if trace is not None:
            now = __import__("time").perf_counter()
            trace.setdefault("tts_request_start", now)
            trace.setdefault("tts_connection_established", now)
            if audio:
                trace.setdefault("tts_first_byte", now)
            trace["tts_complete"] = __import__("time").perf_counter()
        if audio:
            yield audio


class PlaceholderSpeechService(SpeechService):
    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str | None = None,
    ) -> tuple[str, str | None]:
        raise SpeechUnavailableError(
            "Speech recognition is disabled. Set SPEECH_PROVIDER=whisper."
        )

    async def synthesize(self, text: str) -> bytes:
        raise SpeechUnavailableError(
            "Text-to-speech is disabled. Set TTS_PROVIDER=fish and FISH_AUDIO_API_KEY."
        )
