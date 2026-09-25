"""AGENT WEB RESEARCH — specialized evidence gatherer (not Agent 5).

Runs at most once per orchestration when KB is insufficient or web is required.
Does NOT write the final user-facing answer — Agent 4 does.

Pipeline: query builder → parallel provider search (per-query + global
timeouts, partial results kept) → Cameroon relevance validation → ranker
(top 5, low-confidence flagged) → cache.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.core.config import get_settings
from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.web_research.cache import cache_get, cache_set, ttl_for
from app.services.agents.web_research.models import WebEvidence, WebResearchResult
from app.services.agents.web_research.query_builder import (
    build_queries,
    is_route_research,
    route_query_phases,
)
from app.services.agents.web_research.ranker import MAX_SOURCES, rank
from app.services.agents.web_research.route import select_destination, select_transport
from app.services.agents.web_research.validator import (
    extract_key_facts,
    filter_mentions,
    filter_regional,
    is_answerable,
    score_hit,
    validate_evidence,
)
from app.services.search.base import WebSearchService as LegacyWebSearchService
from app.services.web_search.models import WebSearchResult
from app.services.web_search.providers.keyless_provider import KeylessProvider
from app.services.web_search.web_search_service import (
    WebSearchProvider,
    WebSearchService,
    run_parallel,
)

logger = logging.getLogger(__name__)

# Transport and destination activities are both needed for a route answer.
MAX_ROUTE_SOURCES = 7


def _provider_for(web: LegacyWebSearchService) -> WebSearchProvider:
    if isinstance(web, WebSearchService):
        return web.provider
    return KeylessProvider(backend=web)


class WebResearchAgent:
    """Single specialized web researcher — search → validate → rank → evidence."""

    def __init__(
        self,
        web_search: LegacyWebSearchService | None = None,
        *,
        timeout_seconds: float | None = None,
        max_results: int = 5,
        cache_ttl_seconds: float | None = None,
        per_query_timeout_seconds: float | None = None,
    ) -> None:
        self._web = web_search
        settings = get_settings()
        self._timeout = float(
            timeout_seconds
            if timeout_seconds is not None
            else settings.web_research_timeout_seconds
        )
        self._per_query = min(
            self._timeout,
            float(per_query_timeout_seconds or settings.web_search_query_timeout_seconds),
        )
        self._max = max_results
        self._ttl_override = cache_ttl_seconds

    async def research(
        self,
        user_query: str,
        intent: IntentResult,
        *,
        knowledge: KnowledgeResult | None = None,
        conversation_context: str | None = None,  # noqa: ARG002 — region already resolved by Agent 1
        request_id: str | None = None,
        llm_queries: list[str] | None = None,
    ) -> WebResearchResult:
        started = time.perf_counter()
        region = intent.region or intent.city
        route = not llm_queries and is_route_research(intent)
        if route:
            # Same wording, different trip (« retourner à Yaoundé » from Foumban or Kribi).
            region = f"{intent.origin or ''}->{intent.destination}"
        cached = cache_get(user_query, intent.intent, region)
        if cached is not None:
            cached.cache_hit = True
            cached.request_id = request_id
            cached.research_ms = round((time.perf_counter() - started) * 1000.0, 3)
            return cached

        if self._web is None:
            return WebResearchResult(
                query=user_query,
                answerable=False,
                warnings=["web_search_unavailable"],
                request_id=request_id,
                research_ms=round((time.perf_counter() - started) * 1000.0, 3),
            )

        if route:
            return await self._research_route(user_query, intent, region, started, request_id)

        queries = build_queries(user_query, intent, llm_queries=llm_queries)
        raw: list[WebSearchResult] = []
        timed_out = False
        try:
            raw, timed_out = await run_parallel(
                _provider_for(self._web),
                queries,
                max_results=self._max,
                per_query_timeout_s=self._per_query,
                global_timeout_s=self._timeout,
            )
        except Exception:  # noqa: BLE001
            logger.exception("web_research_failed request_id=%s", request_id)
        if timed_out:
            logger.warning(
                "web_research_timeout request_id=%s timeout=%s partial=%s",
                request_id,
                self._timeout,
                len(raw),
            )

        evidence = [self._to_evidence(r, user_query) for r in raw]
        evidence = validate_evidence(
            evidence, query=user_query, intent=intent.intent, places=(intent.city or "",)
        )
        if intent.intent == "FOOD" and intent.dish:
            evidence = filter_mentions(evidence, intent.dish)
        elif intent.intent == "FOOD":
            evidence = filter_regional(evidence, intent.region, topic="FOOD")
        evidence = rank(
            evidence,
            " ".join([user_query, region or ""]),
            alt_queries=queries,
            limit=MAX_ROUTE_SOURCES if intent.destination else MAX_SOURCES,
        )
        facts = extract_key_facts([e for e in evidence if not e.low_confidence])
        answerable = is_answerable(evidence) and bool(facts)
        confidence = max((e.rank_score for e in evidence), default=0.0)
        warnings: list[str] = []
        if timed_out:
            warnings.append("web_research_timeout")
        if not answerable:
            warnings.append("insufficient_credible_sources")
        if evidence and all(e.tier >= 4 for e in evidence):
            warnings.append("only_community_sources")
        if evidence and all(e.low_confidence for e in evidence):
            warnings.append("only_low_confidence_sources")

        result = WebResearchResult(
            query=user_query,
            search_queries=queries,
            raw_results_count=len(raw),
            answerable=answerable,
            evidence=evidence,
            key_facts=facts,
            warnings=warnings,
            confidence=round(min(0.92, confidence), 3),
            timed_out=timed_out,
            request_id=request_id,
            research_ms=round((time.perf_counter() - started) * 1000.0, 3),
            provider=getattr(_provider_for(self._web), "name", ""),
        )
        if answerable and not timed_out:
            ttl = self._ttl_override or ttl_for(intent.intent, intent.web_reason)
            cache_set(user_query, intent.intent, result, ttl_seconds=ttl, region=region)
        return result

    async def _search(self, queries: list[str]) -> tuple[list[WebSearchResult], bool]:
        if not queries:
            return [], False
        try:
            return await run_parallel(
                _provider_for(self._web),
                queries,
                max_results=self._max,
                per_query_timeout_s=self._per_query,
                global_timeout_s=self._timeout,
            )
        except Exception:  # noqa: BLE001
            logger.exception("web_research_failed queries=%s", queries)
            return [], False

    async def _research_route(
        self,
        user_query: str,
        intent: IntentResult,
        cache_region: str,
        started: float,
        request_id: str | None,
    ) -> WebResearchResult:
        """Phase A (origin → destination transport) and Phase B (destination) are
        searched with separate queries and selected with separate rules."""
        dest = intent.destination or ""
        transport_q, destination_q = route_query_phases(intent)
        (raw_t, to_t), (raw_d, to_d) = await asyncio.gather(
            self._search(transport_q), self._search(destination_q)
        )
        timed_out = to_t or to_d
        places = tuple(p for p in (intent.origin, dest) if p)

        transport = [self._to_evidence(r, " ".join(transport_q)) for r in raw_t]
        transport = validate_evidence(transport, query=user_query, intent=intent.intent, places=places, limit=12)
        transport = rank(transport, " ".join([user_query, dest]), alt_queries=transport_q, limit=12)
        transport = select_transport(transport, intent.origin, dest)

        seen = {e.url for e in transport}
        destination = [
            self._to_evidence(r, " ".join(destination_q)) for r in raw_d if r.url not in seen
        ]
        destination = validate_evidence(destination, query=user_query, intent=intent.intent, places=(dest,), limit=12)
        destination = rank(destination, " ".join([user_query, dest]), alt_queries=destination_q, limit=12)
        destination = select_destination(destination, dest)

        evidence = [*transport, *destination]
        facts = extract_key_facts([e for e in evidence if not e.low_confidence])
        answerable = bool(transport) and bool(facts)
        warnings: list[str] = []
        if timed_out:
            warnings.append("web_research_timeout")
        if not transport:
            warnings.append("no_route_specific_source")
        if destination_q and not destination:
            warnings.append("no_destination_source")
        result = WebResearchResult(
            query=user_query,
            search_queries=[*transport_q, *destination_q],
            transport_queries=transport_q,
            destination_queries=destination_q,
            raw_results_count=len(raw_t) + len(raw_d),
            answerable=answerable,
            evidence=evidence,
            key_facts=facts,
            warnings=warnings,
            confidence=round(min(0.92, max((e.rank_score for e in evidence), default=0.0)), 3),
            timed_out=timed_out,
            request_id=request_id,
            research_ms=round((time.perf_counter() - started) * 1000.0, 3),
            provider=getattr(_provider_for(self._web), "name", ""),
        )
        logger.info(
            "web_research_route request_id=%s origin=%s destination=%s transport_queries=%s "
            "destination_queries=%s raw_transport=%s raw_destination=%s selected_transport=%s "
            "selected_destination=%s",
            request_id,
            intent.origin,
            dest,
            transport_q,
            destination_q,
            len(raw_t),
            len(raw_d),
            [f"{e.domain}:{e.route_match}" for e in transport],
            [e.domain for e in destination],
        )
        if answerable and not timed_out:
            ttl = self._ttl_override or ttl_for(intent.intent, intent.web_reason)
            cache_set(user_query, intent.intent, result, ttl_seconds=ttl, region=cache_region)
        return result

    @staticmethod
    def _to_evidence(result: WebSearchResult, query: str) -> WebEvidence:
        relevance, tier = score_hit(
            title=result.title, snippet=result.snippet, url=result.url, query=query
        )
        return WebEvidence(
            title=(result.title or result.domain or "Web")[:160],
            url=result.url,
            domain=result.domain,
            snippet=result.snippet[:600],
            content=None,
            relevance_score=relevance,
            source_type=result.source_type,
            verified=False,
            tier=tier,
            published_at=result.published_at,
            provider=result.provider,
        )


async def run_web_research(
    user_query: str,
    intent: IntentResult,
    *,
    knowledge: KnowledgeResult | None = None,
    web_search: LegacyWebSearchService | None = None,
    request_id: str | None = None,
) -> WebResearchResult:
    agent = WebResearchAgent(web_search=web_search)
    return await agent.research(
        user_query,
        intent,
        knowledge=knowledge,
        request_id=request_id,
    )
