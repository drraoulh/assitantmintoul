from functools import lru_cache

from app.core.config import get_settings
from app.services.search.base import PlaceholderWebSearchService, WebSearchService


def create_web_search_service() -> WebSearchService:
    settings = get_settings()
    if not settings.web_search_enabled:
        return PlaceholderWebSearchService()

    from app.services.web_search.factory import create_web_search_service as _create

    return _create(settings)


@lru_cache
def get_web_search_service() -> WebSearchService:
    return create_web_search_service()
