from __future__ import annotations

from app.core.exceptions import SpeechUnavailableError
from app.services.speech.base import SpeechService


class CompositeSpeechService(SpeechService):
    """STT + TTS adapters composed behind a single SpeechService."""

    def __init__(
        self,
        stt: SpeechService,
        tts: SpeechService | None = None,
    ) -> None:
        self._stt = stt
        self._tts = tts

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        filename: str | None = None,
    ) -> tuple[str, str | None]:
        return await self._stt.transcribe(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            filename=filename,
        )

    async def synthesize(self, text: str) -> bytes:
        if self._tts is None:
            raise SpeechUnavailableError(
                "Text-to-speech is disabled. "
                "Set TTS_PROVIDER=fish and FISH_AUDIO_API_KEY."
            )
        return await self._tts.synthesize(text)
