from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.search.base import WebSearchHit, WebSearchService
from app.services.search.wikipedia import enrich_cameroon_query

logger = logging.getLogger(__name__)


class OpenWebSearchService(WebSearchService):
    """Organic open-web search (not limited to Wikipedia).

    Uses the `ddgs` client to pull ranked results from the public web:
    tourism sites, blogs, news, TripAdvisor, Facebook pages that are indexed,
    Instagram posts that appear in search, etc.
    """

    def __init__(self, *, timeout_seconds: float = 12.0) -> None:
        self._timeout = timeout_seconds

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        q = enrich_cameroon_query(query)
        if max_results <= 0:
            return []

        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(self._search_sync, q, max_results),
                timeout=self._timeout,
            )
        except TimeoutError:
            logger.info("Open-web search timed out for %r", q)
            return []
        except Exception:
            logger.warning("Open-web search failed for %r", q, exc_info=True)
            return []

        hits: list[WebSearchHit] = []
        seen: set[str] = set()
        for item in raw:
            hit = self._to_hit(item)
            if hit is None:
                continue
            key = (hit.url or hit.title).strip().casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            hits.append(hit)
            if len(hits) >= max_results:
                break
        return hits

    def _search_sync(self, query: str, max_results: int) -> list[dict[str, Any]]:
        from ddgs import DDGS

        # Request a few extras: some rows can be empty / duplicates.
        with DDGS() as client:
            rows = list(
                client.text(
                    query,
                    region="wt-wt",
                    safesearch="moderate",
                    max_results=max(max_results + 4, 8),
                )
            )
        return [row for row in rows if isinstance(row, dict)]

    @staticmethod
    def _to_hit(item: dict[str, Any]) -> WebSearchHit | None:
        title = str(item.get("title") or "").strip()
        url = str(item.get("href") or item.get("url") or "").strip()
        snippet = str(item.get("body") or item.get("snippet") or "").strip()
        if not title and not snippet:
            return None
        host = _host_label(url)
        return WebSearchHit(
            title=title or host or "Résultat web",
            snippet=snippet[:700],
            url=url,
            source=f"web:{host}" if host else "web",
        )


def _host_label(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host
