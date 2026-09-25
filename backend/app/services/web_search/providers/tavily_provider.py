"""Tavily — search API designed for LLM agents."""

from __future__ import annotations

import httpx

from app.services.web_search.models import WebSearchResult
from app.services.web_search.source_parser import parse_result
from app.services.web_search.web_search_service import WebSearchProvider


class TavilyProvider(WebSearchProvider):
    name = "tavily"

    def __init__(self, api_key: str, *, timeout_s: float = 10.0) -> None:
        self._key = api_key
        self._timeout = timeout_s

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                    "include_answer": False,
                    "include_raw_content": False,
                },
                headers={"Authorization": f"Bearer {self._key}"},
            )
            resp.raise_for_status()
            data = resp.json()
        out: list[WebSearchResult] = []
        for row in data.get("results") or []:
            item = parse_result(
                title=row.get("title"),
                url=row.get("url"),
                snippet=row.get("content"),
                published_at=row.get("published_date"),
                raw_score=row.get("score"),
                provider=self.name,
            )
            if item:
                out.append(item)
        return out[:max_results]
