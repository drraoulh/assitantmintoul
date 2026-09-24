from __future__ import annotations

import asyncio
import logging

from app.services.search.base import WebSearchHit, WebSearchService
from app.services.search.duckduckgo import DuckDuckGoSearchService
from app.services.search.open_web import OpenWebSearchService
from app.services.search.wikipedia import WikipediaSearchService

logger = logging.getLogger(__name__)


class CompositeWebSearchService(WebSearchService):
    """Fan out independent providers in parallel; stop early when full.

    Phase 1 parallelisation (documented):
    - Open-web, Wikipedia and Instant Answer are independent → start together.
    - As soon as ``max_results`` unique hits are collected, remaining tasks are
      cancelled so a slow filler cannot stall the grounding budget.
    - Functional merge/dedupe behaviour is unchanged.
    """

    def __init__(
        self,
        services: list[WebSearchService] | None = None,
        *,
        open_web: WebSearchService | None = None,
        fillers: list[WebSearchService] | None = None,
    ) -> None:
        if services is not None:
            self._services = list(services)
        else:
            primary = open_web or OpenWebSearchService()
            extras = fillers or [
                WikipediaSearchService(),
                DuckDuckGoSearchService(),
            ]
            self._services = [primary, *extras]

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        if max_results <= 0 or not self._services:
            return []

        tasks = [
            asyncio.create_task(service.search(query, max_results=max_results))
            for service in self._services
        ]
        merged: list[WebSearchHit] = []
        seen: set[str] = set()

        def _absorb(hits: list[WebSearchHit] | BaseException) -> None:
            if isinstance(hits, BaseException):
                if not isinstance(hits, asyncio.CancelledError):
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
            for finished in asyncio.as_completed(tasks):
                try:
                    result = await finished
                except asyncio.CancelledError:
                    continue
                except Exception as exc:  # noqa: BLE001
                    _absorb(exc)
                    continue
                _absorb(result)
                if len(merged) >= max_results:
                    break
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        return merged[:max_results]
