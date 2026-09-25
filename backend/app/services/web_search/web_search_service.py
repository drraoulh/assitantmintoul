"""WebSearchService — provider-agnostic, parallel, time-boxed.

``WebSearchService`` also implements the legacy ``search.base.WebSearchService``
interface (``search() -> list[WebSearchHit]``) so every existing caller
(orchestrator, grounding, voice) keeps working unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from app.services.search.base import WebSearchHit
from app.services.search.base import WebSearchService as LegacyWebSearchService
from app.services.web_search.models import ImageSearchResult, WebSearchResult
from app.services.web_search.source_parser import dedupe_by_url

logger = logging.getLogger(__name__)


class WebSearchProvider(ABC):
    name: str = "provider"

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        ...

    async def search_images(self, query: str, max_results: int = 6) -> list[ImageSearchResult]:
        return []


async def run_parallel(
    provider: WebSearchProvider,
    queries: list[str],
    *,
    max_results: int,
    per_query_timeout_s: float,
    global_timeout_s: float,
) -> tuple[list[WebSearchResult], bool]:
    """Run queries concurrently. Returns (deduped results, global_timed_out).

    A slow or failing query never discards the others; on global timeout the
    results already collected are returned.
    """

    async def _one(q: str) -> list[WebSearchResult]:
        try:
            return await asyncio.wait_for(
                provider.search(q, max_results=max_results), timeout=per_query_timeout_s
            )
        except asyncio.TimeoutError:
            logger.warning("[WEB] query timeout provider=%s query=%r", provider.name, q)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[WEB] query failed provider=%s query=%r error=%s", provider.name, q, exc)
        return []

    tasks = [asyncio.create_task(_one(q)) for q in queries if q.strip()]
    if not tasks:
        return [], False
    done, pending = await asyncio.wait(tasks, timeout=global_timeout_s)
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    results: list[WebSearchResult] = []
    # Keep query order so the primary query's hits rank first on ties.
    for task in tasks:
        if task in done and not task.cancelled() and task.exception() is None:
            results.extend(task.result())
    return dedupe_by_url(results), bool(pending)


def result_to_hit(result: WebSearchResult) -> WebSearchHit:
    return WebSearchHit(
        title=result.title,
        snippet=result.snippet,
        url=result.url,
        source=f"web:{result.domain}" if result.domain else "web",
        published_at=result.published_at,
        source_type=result.source_type,
    )


class WebSearchService(LegacyWebSearchService):
    def __init__(
        self,
        provider: WebSearchProvider,
        *,
        max_queries: int = 3,
        timeout_s: float = 10.0,
        global_timeout_s: float = 15.0,
    ) -> None:
        self.provider = provider
        self.max_queries = max_queries
        self.timeout_s = timeout_s
        self.global_timeout_s = global_timeout_s

    @property
    def provider_name(self) -> str:
        return self.provider.name

    async def run(self, queries: list[str], *, max_results: int = 5) -> list[WebSearchResult]:
        results, _ = await run_parallel(
            self.provider,
            queries[: self.max_queries],
            max_results=max_results,
            per_query_timeout_s=self.timeout_s,
            global_timeout_s=self.global_timeout_s,
        )
        return results

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        results = await self.run([query], max_results=max_results)
        return [result_to_hit(r) for r in results[:max_results]]

    async def search_images(self, query: str, max_results: int = 6) -> list[ImageSearchResult]:
        try:
            return await asyncio.wait_for(
                self.provider.search_images(query, max_results=max_results),
                timeout=self.timeout_s,
            )
        except Exception:  # noqa: BLE001
            return []
