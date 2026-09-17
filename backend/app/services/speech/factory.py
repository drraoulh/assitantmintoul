from app.core.config import get_settings
from app.services.speech.base import PlaceholderSpeechService, SpeechService
from app.services.speech.composite import CompositeSpeechService
from app.services.speech.fish_audio import FishAudioTTSService
from app.services.speech.huggingface import HuggingFaceSpeechService
from app.services.speech.whisper import WhisperSpeechService


def _create_stt_service() -> SpeechService:
    settings = get_settings()
    provider = settings.speech_provider.strip().lower()
    if provider in {"whisper", "faster-whisper", "stt", "local"}:
        return WhisperSpeechService(settings=settings)
    if provider in {"huggingface", "hf", "huggingface-whisper"}:
        return HuggingFaceSpeechService(settings=settings)
    if provider in {"placeholder", "none", "off"}:
        return PlaceholderSpeechService()
    raise ValueError(
        f"Unknown SPEECH_PROVIDER '{provider}'. "
        "Use whisper, huggingface, or placeholder."
    )


def _create_tts_service() -> SpeechService | None:
    settings = get_settings()
    provider = settings.tts_provider.strip().lower()
    if provider in {"none", "off", "device", "expo", "placeholder"}:
        return None
    if provider in {"fish", "fish-audio", "fishspeech", "fish-speech"}:
        return FishAudioTTSService(settings=settings)
    raise ValueError(
        f"Unknown TTS_PROVIDER '{provider}'. Use fish or none."
    )


def create_speech_service() -> SpeechService:
    # Fresh settings each call so .env token updates apply under --reload
    get_settings.cache_clear()
    stt = _create_stt_service()
    tts = _create_tts_service()
    if tts is None:
        return stt
    return CompositeSpeechService(stt=stt, tts=tts)
