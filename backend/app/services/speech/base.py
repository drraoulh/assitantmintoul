from abc import ABC, abstractmethod


class SpeechService(ABC):
    """Speech-to-text and text-to-speech adapters.

    Planned: Whisper (STT) and Piper or another open-source TTS model.
    """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        """Convert recorded audio into text."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Convert assistant text into audio bytes."""


class PlaceholderSpeechService(SpeechService):
    async def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
        raise NotImplementedError("Speech-to-text will be added in a later phase.")

    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError("Text-to-speech will be added in a later phase.")
