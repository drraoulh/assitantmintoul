from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.services.search.base import WebSearchHit, WebSearchService

logger = logging.getLogger(__name__)

_CAMEROON_HINT = re.compile(
    r"cameroun|cameroon|yaound|douala|kribi|limbe|limbé|buea|foumban|"
    r"maroua|garoua|waza|bamenda|ngaound",
    re.IGNORECASE,
)


def enrich_cameroon_query(query: str) -> str:
    cleaned = " ".join(query.split()).strip()
    if not cleaned:
        return "Cameroun tourisme"
    if _CAMEROON_HINT.search(cleaned):
        return cleaned
    return f"{cleaned} Cameroun"


class WikipediaSearchService(WebSearchService):
    """Open search + extracts from French then English Wikipedia."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 12.0,
        user_agent: str = (
            "CameroonAITourGuide/0.4 "
            "(https://github.com/drraoulh/assitantmintoul; educational tourism assistant)"
        ),
    ) -> None:
        self._client = client
        self._timeout = timeout_seconds
        self._user_agent = user_agent

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        q = enrich_cameroon_query(query)
        hits: list[WebSearchHit] = []
        for lang in ("fr", "en"):
            remaining = max_results - len(hits)
            if remaining <= 0:
                break
            hits.extend(await self._search_lang(lang, q, max_results=remaining))
        return hits[:max_results]

    async def _search_lang(
        self,
        lang: str,
        query: str,
        *,
        max_results: int,
    ) -> list[WebSearchHit]:
        api = f"https://{lang}.wikipedia.org/w/api.php"
        try:
            search_payload = await self._get(
                api,
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": max(1, max_results),
                    "format": "json",
                    "utf8": 1,
                },
            )
        except Exception as exc:
            logger.warning(
                "Wikipedia %s search failed for %r: %s",
                lang,
                query[:80],
                exc,
            )
            return []

        results = ((search_payload.get("query") or {}).get("search")) or []
        titles = [str(item.get("title") or "").strip() for item in results]
        titles = [title for title in titles if title][:max_results]
        if not titles:
            return []

        try:
            extract_payload = await self._get(
                api,
                {
                    "action": "query",
                    "prop": "extracts|info",
                    "exintro": 1,
                    "explaintext": 1,
                    "inprop": "url",
                    "titles": "|".join(titles),
                    "format": "json",
                    "utf8": 1,
                },
            )
        except Exception:
            logger.warning("Wikipedia %s extracts failed", lang, exc_info=True)
            return []

        pages = ((extract_payload.get("query") or {}).get("pages")) or {}
        hits: list[WebSearchHit] = []
        # Preserve search ranking by title order.
        by_title = {
            str(page.get("title") or ""): page
            for page in pages.values()
            if isinstance(page, dict)
        }
        for title in titles:
            page = by_title.get(title) or {}
            extract = str(page.get("extract") or "").strip()
            if not extract:
                continue
            if len(extract) > 700:
                extract = extract[:697].rstrip() + "..."
            hits.append(
                WebSearchHit(
                    title=title,
                    snippet=extract,
                    url=str(page.get("fullurl") or f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"),
                    source=f"wikipedia-{lang}",
                )
            )
        return hits

    async def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"User-Agent": self._user_agent, "Accept": "application/json"}
        timeout = httpx.Timeout(self._timeout, connect=5.0)
        if self._client is not None:
            response = await self._client.get(url, params=params, headers=headers, timeout=timeout)
        else:
            async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return {}
        return payload
