"""Select the web search provider once, from ``WEB_SEARCH_PROVIDER``.

auto (default): serper → tavily → brave, whichever has a key, always backed
by the keyless stack as fallback. Explicit values force a single provider
(still with keyless fallback, so a quota error never silences web research).
"""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.services.web_search.providers.fallback_provider import FallbackProvider
from app.services.web_search.providers.keyless_provider import KeylessProvider
from app.services.web_search.web_search_service import WebSearchProvider, WebSearchService

logger = logging.getLogger(__name__)


def create_provider(settings: Settings) -> WebSearchProvider:
    timeout = float(settings.web_search_query_timeout_seconds)
    choice = (settings.web_search_provider or "auto").strip().lower()
    paid: list[WebSearchProvider] = []

    def _serper() -> None:
        if settings.serper_api_key:
            from app.services.web_search.providers.serper_provider import SerperProvider

            paid.append(SerperProvider(settings.serper_api_key, timeout_s=timeout))

    def _tavily() -> None:
        if settings.tavily_api_key:
            from app.services.web_search.providers.tavily_provider import TavilyProvider

            paid.append(TavilyProvider(settings.tavily_api_key, timeout_s=timeout))

    def _brave() -> None:
        if settings.brave_search_api_key:
            from app.services.web_search.providers.brave_provider import BraveProvider

            paid.append(BraveProvider(settings.brave_search_api_key, timeout_s=timeout))

    builders = {"serper": _serper, "tavily": _tavily, "brave": _brave}
    if choice in builders:
        builders[choice]()
        if not paid:
            logger.warning("[WEB] WEB_SEARCH_PROVIDER=%s but no API key — keyless only", choice)
    elif choice != "keyless":
        for build in (_serper, _tavily, _brave):
            build()

    keyless = KeylessProvider(timeout_s=timeout)
    if not paid:
        return keyless
    return FallbackProvider([*paid, keyless])


def create_web_search_service(settings: Settings) -> WebSearchService:
    provider = create_provider(settings)
    logger.info("[WEB] provider=%s", provider.name)
    return WebSearchService(
        provider,
        max_queries=3,
        timeout_s=float(settings.web_search_query_timeout_seconds),
        global_timeout_s=float(settings.web_research_timeout_seconds),
    )
