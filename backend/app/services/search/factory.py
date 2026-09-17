from functools import lru_cache

from app.core.config import get_settings
from app.services.search.base import PlaceholderWebSearchService, WebSearchService


def create_web_search_service() -> WebSearchService:
    settings = get_settings()
    if not settings.web_search_enabled:
        return PlaceholderWebSearchService()

    from app.services.search.composite import CompositeWebSearchService
    from app.services.search.duckduckgo import DuckDuckGoSearchService
    from app.services.search.open_web import OpenWebSearchService
    from app.services.search.wikipedia import WikipediaSearchService

    timeout = settings.web_search_timeout_seconds
    return CompositeWebSearchService(
        services=[
            OpenWebSearchService(timeout_seconds=timeout),
            WikipediaSearchService(timeout_seconds=min(timeout, 10.0)),
            DuckDuckGoSearchService(timeout_seconds=min(timeout, 10.0)),
        ]
    )


@lru_cache
def get_web_search_service() -> WebSearchService:
    return create_web_search_service()
