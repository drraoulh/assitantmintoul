from __future__ import annotations

import asyncio
import logging

from app.services.search.base import WebSearchHit, WebSearchService
from app.services.search.duckduckgo import DuckDuckGoSearchService
from app.services.search.wikipedia import WikipediaSearchService

logger = logging.getLogger(__name__)


class CompositeWebSearchService(WebSearchService):
    """Merge Wikipedia + DuckDuckGo results for broader coverage."""

    def __init__(
        self,
        services: list[WebSearchService] | None = None,
    ) -> None:
        self._services = services or [
            WikipediaSearchService(),
            DuckDuckGoSearchService(),
        ]

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        if max_results <= 0:
            return []

        results = await asyncio.gather(
            *[service.search(query, max_results=max_results) for service in self._services],
            return_exceptions=True,
        )

        merged: list[WebSearchHit] = []
        seen: set[str] = set()
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Web search provider failed: %s", result)
                continue
            for hit in result:
                key = (hit.url or hit.title).strip().casefold()
                if not key or key in seen:
                    continue
                seen.add(key)
                merged.append(hit)
                if len(merged) >= max_results:
                    return merged
        return merged
