"""Try providers in order; move on when one errors or returns nothing."""

from __future__ import annotations

import logging

from app.services.web_search.models import ImageSearchResult, WebSearchResult
from app.services.web_search.web_search_service import WebSearchProvider

logger = logging.getLogger(__name__)


class FallbackProvider(WebSearchProvider):
    def __init__(self, providers: list[WebSearchProvider]) -> None:
        self._providers = providers
        self.name = "+".join(p.name for p in providers)

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        for provider in self._providers:
            try:
                results = await provider.search(query, max_results=max_results)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[WEB] provider=%s failed, falling back: %s", provider.name, exc)
                continue
            if results:
                return results
        return []

    async def search_images(self, query: str, max_results: int = 6) -> list[ImageSearchResult]:
        for provider in self._providers:
            try:
                images = await provider.search_images(query, max_results=max_results)
            except Exception:  # noqa: BLE001
                continue
            if images:
                return images
        return []
