"""Brave Search API — independent index."""

from __future__ import annotations

import httpx

from app.services.web_search.models import WebSearchResult
from app.services.web_search.source_parser import parse_result
from app.services.web_search.web_search_service import WebSearchProvider


class BraveProvider(WebSearchProvider):
    name = "brave"

    def __init__(self, api_key: str, *, timeout_s: float = 10.0) -> None:
        self._key = api_key
        self._timeout = timeout_s

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
        out: list[WebSearchResult] = []
        for rank, row in enumerate((data.get("web") or {}).get("results") or []):
            item = parse_result(
                title=row.get("title"),
                url=row.get("url"),
                snippet=row.get("description"),
                published_at=row.get("page_age") or row.get("age"),
                raw_score=1.0 / (1 + rank),
                provider=self.name,
            )
            if item:
                out.append(item)
        return out[:max_results]
