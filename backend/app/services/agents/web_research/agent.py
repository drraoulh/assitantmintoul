"""AGENT WEB RESEARCH — specialized evidence gatherer (not Agent 5).

Runs at most once per orchestration when KB is insufficient or web is required.
Does NOT write the final user-facing answer — Agent 4 does.
"""

from __future__ import annotations

import asyncio
import logging
import time

from app.core.config import get_settings
from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.web_research.cache import cache_get, cache_set
from app.services.agents.web_research.models import WebEvidence, WebResearchResult
from app.services.agents.web_research.search import build_search_queries
from app.services.agents.web_research.validator import (
    extract_domain,
    extract_key_facts,
    is_answerable,
    score_hit,
    validate_evidence,
)
from app.services.search.base import WebSearchHit, WebSearchService

logger = logging.getLogger(__name__)


class WebResearchAgent:
    """Single specialized web researcher — search → validate → evidence."""

    def __init__(
        self,
        web_search: WebSearchService | None = None,
        *,
        timeout_seconds: float | None = None,
        max_results: int = 5,
        cache_ttl_seconds: float = 1800.0,
    ) -> None:
        self._web = web_search
        settings = get_settings()
        self._timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else float(
                getattr(settings, "web_research_timeout_seconds", None)
                or max(8.0, settings.web_search_timeout_seconds)
            )
        )
        self._max = max_results
        self._ttl = cache_ttl_seconds

    async def research(
        self,
        user_query: str,
        intent: IntentResult,
        *,
        knowledge: KnowledgeResult | None = None,
        conversation_context: str | None = None,
        request_id: str | None = None,
    ) -> WebResearchResult:
        started = time.perf_counter()
        missing = list(knowledge.missing_information) if knowledge else []
        cached = cache_get(user_query, intent.intent)
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

        queries = build_search_queries(user_query, intent, missing=missing)
        if conversation_context and intent.location:
            # Keep context tiny — location reminder only
            pass

        evidence: list[WebEvidence] = []
        timed_out = False
        try:
            evidence = await asyncio.wait_for(
                self._gather(queries, user_query),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            timed_out = True
            logger.warning(
                "web_research_timeout request_id=%s timeout=%s",
                request_id,
                self._timeout,
            )
        except Exception:  # noqa: BLE001
            logger.exception("web_research_failed request_id=%s", request_id)

        evidence = validate_evidence(evidence)
        facts = extract_key_facts(evidence)
        answerable = is_answerable(evidence) and bool(facts)
        confidence = 0.0
        if evidence:
            confidence = max(e.relevance_score for e in evidence) * (
                0.9 if any(e.tier <= 2 for e in evidence) else 0.7
            )
        warnings: list[str] = []
        if timed_out:
            warnings.append("web_research_timeout")
        if not answerable:
            warnings.append("insufficient_credible_sources")
        if evidence and all(e.tier >= 4 for e in evidence):
            warnings.append("only_community_sources")

        result = WebResearchResult(
            query=user_query,
            search_queries=queries,
            answerable=answerable,
            evidence=evidence,
            key_facts=facts,
            warnings=warnings,
            confidence=round(min(0.92, confidence), 3),
            timed_out=timed_out,
            request_id=request_id,
            research_ms=round((time.perf_counter() - started) * 1000.0, 3),
        )
        if answerable and not timed_out:
            cache_set(user_query, intent.intent, result, ttl_seconds=self._ttl)
        return result

    async def _gather(self, queries: list[str], user_query: str) -> list[WebEvidence]:
        assert self._web is not None
        collected: list[WebEvidence] = []
        # Run primary query first, then up to 2 more — still one agent call path
        for q in queries[:3]:
            hits = await self._web.search(q, max_results=self._max)
            for hit in hits:
                collected.append(self._hit_to_evidence(hit, user_query))
            # Early stop if we already have strong evidence
            strong = [e for e in collected if e.tier <= 2]
            if len(strong) >= 2:
                break
        return collected

    @staticmethod
    def _hit_to_evidence(hit: WebSearchHit, query: str) -> WebEvidence:
        score, tier = score_hit(
            title=hit.title or "",
            snippet=hit.snippet or "",
            url=hit.url or "",
            query=query,
        )
        domain = extract_domain(hit.url or "")
        return WebEvidence(
            title=(hit.title or domain or "Web")[:160],
            url=hit.url or "",
            domain=domain,
            snippet=(hit.snippet or "")[:600],
            content=None,
            relevance_score=score,
            source_type=hit.source or "web",
            verified=False,
            tier=tier,
        )


async def run_web_research(
    user_query: str,
    intent: IntentResult,
    *,
    knowledge: KnowledgeResult | None = None,
    web_search: WebSearchService | None = None,
    request_id: str | None = None,
) -> WebResearchResult:
    agent = WebResearchAgent(web_search=web_search)
    return await agent.research(
        user_query,
        intent,
        knowledge=knowledge,
        request_id=request_id,
    )
