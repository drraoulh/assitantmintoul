from __future__ import annotations

import asyncio
import logging

from app.services.search.base import WebSearchHit, WebSearchService
from app.services.search.duckduckgo import DuckDuckGoSearchService
from app.services.search.open_web import OpenWebSearchService
from app.services.search.wikipedia import WikipediaSearchService

logger = logging.getLogger(__name__)


class CompositeWebSearchService(WebSearchService):
    """Broad open-web search first, then Wikipedia / Instant Answer extras."""

    def __init__(
        self,
        services: list[WebSearchService] | None = None,
    ) -> None:
        self._services = services or [
            # Organic results across the public web (sites, blogs, social pages…).
            OpenWebSearchService(),
            WikipediaSearchService(),
            DuckDuckGoSearchService(),
        ]

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        if max_results <= 0:
            return []

        # Give the open web most of the budget; keep a couple slots for wiki/IA.
        open_budget = max(max_results, min(max_results + 2, 8))
        results = await asyncio.gather(
            *[
                service.search(query, max_results=open_budget)
                for service in self._services
            ],
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
