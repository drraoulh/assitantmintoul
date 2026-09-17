from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.search.base import WebSearchHit, WebSearchService
from app.services.search.wikipedia import enrich_cameroon_query

logger = logging.getLogger(__name__)


class DuckDuckGoSearchService(WebSearchService):
    """DuckDuckGo Instant Answer API (no API key)."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._client = client
        self._timeout = timeout_seconds

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        q = enrich_cameroon_query(query)
        try:
            payload = await self._fetch(q)
        except Exception:
            logger.warning("DuckDuckGo search failed for %r", q, exc_info=True)
            return []

        hits: list[WebSearchHit] = []
        abstract = str(payload.get("AbstractText") or "").strip()
        heading = str(payload.get("Heading") or q).strip()
        abstract_url = str(payload.get("AbstractURL") or "").strip()
        if abstract:
            hits.append(
                WebSearchHit(
                    title=heading or "DuckDuckGo",
                    snippet=abstract[:700],
                    url=abstract_url,
                    source="duckduckgo-abstract",
                )
            )

        related = payload.get("RelatedTopics") or []
        for item in related:
            if len(hits) >= max_results:
                break
            if not isinstance(item, dict):
                continue
            # Nested topic groups contain "Topics".
            if "Topics" in item and isinstance(item["Topics"], list):
                for nested in item["Topics"]:
                    if len(hits) >= max_results:
                        break
                    hit = self._related_hit(nested)
                    if hit is not None:
                        hits.append(hit)
                continue
            hit = self._related_hit(item)
            if hit is not None:
                hits.append(hit)

        answer = str(payload.get("Answer") or "").strip()
        if answer and len(hits) < max_results:
            hits.append(
                WebSearchHit(
                    title=f"Réponse rapide: {heading or q}",
                    snippet=answer[:700],
                    url=abstract_url,
                    source="duckduckgo-answer",
                )
            )
        return hits[:max_results]

    @staticmethod
    def _related_hit(item: Any) -> WebSearchHit | None:
        if not isinstance(item, dict):
            return None
        text = str(item.get("Text") or "").strip()
        url = str(item.get("FirstURL") or "").strip()
        if not text:
            return None
        title = text.split(" - ", maxsplit=1)[0][:120]
        return WebSearchHit(
            title=title,
            snippet=text[:700],
            url=url,
            source="duckduckgo-related",
        )

    async def _fetch(self, query: str) -> dict[str, Any]:
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        timeout = httpx.Timeout(self._timeout, connect=5.0)
        headers = {"Accept": "application/json", "User-Agent": "CameroonAITourGuide/0.3"}
        if self._client is not None:
            response = await self._client.get(
                "https://api.duckduckgo.com/",
                params=params,
                headers=headers,
                timeout=timeout,
            )
        else:
            async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                response = await client.get("https://api.duckduckgo.com/", params=params)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
