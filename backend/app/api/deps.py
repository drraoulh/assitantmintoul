from functools import lru_cache

from app.services.ai.base import AIService
from app.services.ai.factory import create_ai_service
from app.services.conversation import get_conversation_store as build_conversation_store
from app.services.conversation.base import ConversationStore
from app.services.rag.base import RAGService
from app.services.rag.factory import get_rag_service as build_rag_service
from app.services.speech.base import SpeechService
from app.services.speech.factory import create_speech_service
from app.services.tourism.catalog import SiteCatalog
from app.services.vision.base import VisionService
from app.services.vision.factory import create_vision_service


@lru_cache
def get_ai_service() -> AIService:
    """Inject the configured AI implementation into routes."""
    return create_ai_service()


def get_conversation_store() -> ConversationStore:
    # Same instance as the AI service so both read the same threads.
    return build_conversation_store()


def get_rag_service() -> RAGService:
    return build_rag_service()


def get_speech_service() -> SpeechService:
    # Do not cache: SPEECH_PROVIDER / HUGGINGFACE_HUB_TOKEN may change in .env
    return create_speech_service()


def get_vision_service() -> VisionService:
    # Do not cache: VISION_PROVIDER / GEMINI_API_KEY may change in .env
    return create_vision_service()


@lru_cache
def get_site_catalog() -> SiteCatalog:
    return SiteCatalog()
