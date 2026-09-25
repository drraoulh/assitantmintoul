"""Keyless provider — existing open-web (ddgs) + Wikipedia + Instant Answer stack.

Used when no paid API key is configured, and as fallback when a paid provider
fails or returns nothing.
"""

from __future__ import annotations

from app.services.search.base import WebSearchService as LegacyWebSearchService
from app.services.web_search.models import WebSearchResult
from app.services.web_search.source_parser import parse_result
from app.services.web_search.web_search_service import WebSearchProvider


class KeylessProvider(WebSearchProvider):
    name = "keyless"

    def __init__(self, *, timeout_s: float = 10.0, backend: LegacyWebSearchService | None = None) -> None:
        if backend is None:
            from app.services.search.composite import CompositeWebSearchService
            from app.services.search.duckduckgo import DuckDuckGoSearchService
            from app.services.search.open_web import OpenWebSearchService
            from app.services.search.wikipedia import WikipediaSearchService

            backend = CompositeWebSearchService(
                services=[
                    OpenWebSearchService(timeout_seconds=timeout_s),
                    WikipediaSearchService(timeout_seconds=min(timeout_s, 8.0)),
                    DuckDuckGoSearchService(timeout_seconds=min(timeout_s, 8.0)),
                ]
            )
        self._backend = backend

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        hits = await self._backend.search(query, max_results=max_results)
        out: list[WebSearchResult] = []
        for rank, hit in enumerate(hits):
            item = parse_result(
                title=hit.title,
                url=hit.url,
                snippet=hit.snippet,
                published_at=getattr(hit, "published_at", None),
                raw_score=1.0 / (1 + rank),
                provider=self.name,
            )
            if item:
                out.append(item)
        return out
