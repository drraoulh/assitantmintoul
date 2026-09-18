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

    async def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        """Yield audio bytes as soon as the TTS provider streams them.

        Default: buffer the full synthesize() result as a single chunk.
        """
        audio = await self.synthesize(text)
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
