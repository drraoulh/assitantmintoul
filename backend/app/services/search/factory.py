from functools import lru_cache

from app.core.config import get_settings
from app.services.search.base import PlaceholderWebSearchService, WebSearchService
from app.services.search.composite import CompositeWebSearchService


def create_web_search_service() -> WebSearchService:
    settings = get_settings()
    if not settings.web_search_enabled:
        return PlaceholderWebSearchService()
    return CompositeWebSearchService()


@lru_cache
def get_web_search_service() -> WebSearchService:
    return create_web_search_service()
