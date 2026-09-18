from __future__ import annotations

import asyncio
import logging

from app.services.search.base import WebSearchHit, WebSearchService
from app.services.search.duckduckgo import DuckDuckGoSearchService
from app.services.search.open_web import OpenWebSearchService
from app.services.search.wikipedia import WikipediaSearchService

logger = logging.getLogger(__name__)


class CompositeWebSearchService(WebSearchService):
    """Open-web first for speed; Wikipedia / Instant Answer only if needed."""

    def __init__(
        self,
        services: list[WebSearchService] | None = None,
        *,
        open_web: WebSearchService | None = None,
        fillers: list[WebSearchService] | None = None,
    ) -> None:
        if services is not None:
            self._open_web = services[0] if services else OpenWebSearchService()
            self._fillers = services[1:]
        else:
            self._open_web = open_web or OpenWebSearchService()
            self._fillers = fillers or [
                WikipediaSearchService(),
                DuckDuckGoSearchService(),
            ]

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        if max_results <= 0:
            return []

        merged: list[WebSearchHit] = []
        seen: set[str] = set()

        def _absorb(hits: list[WebSearchHit] | BaseException) -> None:
            if isinstance(hits, BaseException):
                logger.warning("Web search provider failed: %s", hits)
                return
            for hit in hits:
                key = (hit.url or hit.title).strip().casefold()
                if not key or key in seen:
                    continue
                seen.add(key)
                merged.append(hit)
                if len(merged) >= max_results:
                    return

        try:
            primary = await self._open_web.search(query, max_results=max_results)
        except Exception as exc:
            logger.warning("Open-web search failed: %s", exc)
            primary = []
        _absorb(primary)
        if len(merged) >= max_results or not self._fillers:
            return merged[:max_results]

        remaining = max_results - len(merged)
        filler_results = await asyncio.gather(
            *[service.search(query, max_results=remaining) for service in self._fillers],
            return_exceptions=True,
        )
        for result in filler_results:
            _absorb(result)
            if len(merged) >= max_results:
                break
        return merged[:max_results]
