"""Serper.dev (Google SERP) — text + images in the same API family."""

from __future__ import annotations

import httpx

from app.services.web_search.models import ImageSearchResult, WebSearchResult
from app.services.web_search.source_parser import clean_text, extract_domain, parse_result
from app.services.web_search.web_search_service import WebSearchProvider

_BASE = "https://google.serper.dev"


class SerperProvider(WebSearchProvider):
    name = "serper"

    def __init__(self, api_key: str, *, timeout_s: float = 10.0, gl: str = "cm", hl: str = "fr") -> None:
        self._key = api_key
        self._timeout = timeout_s
        self._gl = gl
        self._hl = hl

    async def _post(self, path: str, payload: dict) -> dict:
        async with httpx.AsyncClient(base_url=_BASE, timeout=self._timeout) as client:
            resp = await client.post(
                path,
                json=payload,
                headers={"X-API-KEY": self._key, "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        data = await self._post(
            "/search", {"q": query, "gl": self._gl, "hl": self._hl, "num": max(5, max_results)}
        )
        out: list[WebSearchResult] = []
        for rank, row in enumerate(data.get("organic") or []):
            item = parse_result(
                title=row.get("title"),
                url=row.get("link"),
                snippet=row.get("snippet"),
                published_at=row.get("date"),
                raw_score=1.0 / (1 + rank),
                provider=self.name,
            )
            if item:
                out.append(item)
            if len(out) >= max_results:
                break
        return out

    async def search_images(self, query: str, max_results: int = 6) -> list[ImageSearchResult]:
        data = await self._post("/images", {"q": query, "gl": self._gl, "hl": self._hl})
        out: list[ImageSearchResult] = []
        for row in data.get("images") or []:
            image_url = str(row.get("imageUrl") or "")
            page_url = str(row.get("link") or "")
            if not image_url.startswith("https://") or not page_url:
                continue
            out.append(
                ImageSearchResult(
                    image_url=image_url,
                    thumbnail_url=row.get("thumbnailUrl"),
                    page_url=page_url,
                    title=clean_text(row.get("title"), limit=160),
                    source_domain=row.get("domain") or extract_domain(page_url),
                    alt_text=clean_text(row.get("title"), limit=160) or None,
                )
            )
            if len(out) >= max_results:
                break
        return out
