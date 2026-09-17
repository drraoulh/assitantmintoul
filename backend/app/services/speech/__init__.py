from app.services.speech.base import PlaceholderSpeechService, SpeechService
from app.services.speech.composite import CompositeSpeechService
from app.services.speech.factory import create_speech_service
from app.services.speech.fish_audio import FishAudioTTSService
from app.services.speech.huggingface import HuggingFaceSpeechService
from app.services.speech.whisper import WhisperSpeechService

__all__ = [
    "SpeechService",
    "PlaceholderSpeechService",
    "CompositeSpeechService",
    "WhisperSpeechService",
    "HuggingFaceSpeechService",
    "FishAudioTTSService",
    "create_speech_service",
]
