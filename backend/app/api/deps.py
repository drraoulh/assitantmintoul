from functools import lru_cache

from app.services.ai.base import AIService
from app.services.ai.factory import create_ai_service


@lru_cache
def get_ai_service() -> AIService:
    """Inject the configured AI implementation into routes."""
    return create_ai_service()
