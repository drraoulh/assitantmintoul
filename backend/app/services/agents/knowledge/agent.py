"""AGENT 2 — Knowledge & Retrieval orchestrator (Phase 2.8 geography-aware)."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from app.core.config import get_settings
from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.geography import answer_geo_query
from app.services.agents.knowledge.knowledge_retriever import KnowledgeRetriever
from app.services.agents.knowledge.models import KnowledgeEvidence, KnowledgeResult
from app.services.agents.knowledge.place_retriever import PlaceRetriever
from app.services.agents.knowledge.place_store import PlaceIndex
from app.services.agents.knowledge.source_validator import (
    compute_confidence,
    detect_missing,
    finalize_result,
    resolve_sources,
    should_request_web,
    validate_places,
)
from app.services.rag.base import RAGService

logger = logging.getLogger(__name__)


def _completeness(places_count: int, knowledge_count: int, geo_facts: int) -> str:
    total = places_count + (1 if knowledge_count else 0) + geo_facts
    if places_count >= 5 or total >= 6:
        return "HIGH"
    if places_count >= 2 or geo_facts >= 1:
        return "MEDIUM"
    if places_count == 1 or knowledge_count >= 1:
        return "LOW"
    return "NONE"


class KnowledgeAgent:
    """Structured-first retrieval. No LLM. No invented places/prices/hours."""

    def __init__(
        self,
        place_index: PlaceIndex,
        *,
        rag: RAGService | None = None,
    ) -> None:
        self._index = place_index
        self._places = PlaceRetriever(place_index)
        self._knowledge = KnowledgeRetriever(rag)
        self._known_ids = {p.place_id for p in place_index.places}

    @classmethod
    def from_catalog(cls, rag: RAGService | None = None) -> KnowledgeAgent:
        return cls(PlaceIndex.from_catalog(), rag=rag)

    async def retrieve(
        self,
        query: str,
        intent: IntentResult,
        *,
        request_id: str | None = None,
    ) -> KnowledgeResult:
        started = time.perf_counter()
        rid = request_id or intent.request_id or uuid.uuid4().hex[:12]
        settings = get_settings()
        geo_on = bool(settings.knowledge_geography_enabled)

        places, place_ms = self._places.retrieve(query, intent)
        places = validate_places(places, known_ids=self._known_ids)

        knowledge, know_ms = await self._knowledge.retrieve(query, intent)

        geo_facts_count = 0
        if geo_on:
            language = intent.language or "fr"
            facts = answer_geo_query(query, language=language)
            geo_facts_count = len(facts)
            for i, fact in enumerate(facts):
                knowledge = [
                    *knowledge,
                    KnowledgeEvidence(
                        chunk_id=f"geo-{fact.relation.lower()}-{i}",
                        content=fact.as_evidence_content(language=language),
                        source_id="geo:cameroon_admin",
                        title=f"Geography:{fact.relation}",
                        score=0.95,
                    ),
                ]

        src_started = time.perf_counter()
        sources = resolve_sources(places, knowledge, self._index.places)
        if geo_facts_count:
            from app.services.agents.knowledge.models import SourceEvidence

            if not any(s.source_id == "geo:cameroon_admin" for s in sources):
                sources = [
                    *sources,
                    SourceEvidence(
                        source_id="geo:cameroon_admin",
                        name="Cameroon administrative geography (structured)",
                        url=None,
                        source_type="structured_geo",
                    ),
                ]
        source_ms = (time.perf_counter() - src_started) * 1000.0

        missing = detect_missing(places, knowledge, intent.intent)
        confidence = compute_confidence(places, knowledge, intent.intent)
        if geo_facts_count:
            confidence = max(confidence, 0.85)
        web_needed = should_request_web(intent.intent, missing, confidence)
        if intent.needs_web or intent.needs_booking:
            web_needed = True

        completeness = _completeness(len(places), len(knowledge), geo_facts_count)
        # Soft web fallback signal when tourism KB is thin (orchestrator gated by flag)
        if (
            settings.web_knowledge_fallback_enabled
            and intent.intent in {"PLACE_SEARCH", "TOURISM_INFO", "PLACE_DETAILS", "NATURE", "CULTURE"}
            and completeness in {"NONE", "LOW"}
            and not geo_facts_count
        ):
            web_needed = True
            if "matching_places" not in missing:
                missing = [*missing, "matching_places"]

        if places and knowledge:
            source = "hybrid"
        elif places:
            source = "structured"
        elif knowledge:
            source = "documents"
        else:
            source = "empty"

        total_ms = (time.perf_counter() - started) * 1000.0
        result = KnowledgeResult(
            query=query,
            intent=intent.intent,
            places=places,
            knowledge=knowledge,
            sources=sources,
            missing_information=missing,
            web_needed=web_needed,
            confidence=round(min(0.95, confidence), 3),
            request_id=rid,
            place_retrieval_ms=round(place_ms, 3),
            knowledge_retrieval_ms=round(know_ms, 3),
            source_resolution_ms=round(source_ms, 3),
            total_agent2_ms=round(total_ms, 3),
            source=source,  # type: ignore[arg-type]
            verified_places_count=len(places),
            knowledge_completeness=completeness,  # type: ignore[arg-type]
            geo_facts_count=geo_facts_count,
        )
        result = finalize_result(result)
        logger.info("knowledge_agent %s", result.observability())
        return result

    def retrieve_sync(
        self,
        query: str,
        intent: IntentResult,
        *,
        request_id: str | None = None,
    ) -> KnowledgeResult:
        """Sync wrapper for scripts/tests outside an event loop."""
        return asyncio.run(self.retrieve(query, intent, request_id=request_id))


async def retrieve_knowledge(
    query: str,
    intent: IntentResult,
    *,
    place_index: PlaceIndex | None = None,
    rag: RAGService | None = None,
    request_id: str | None = None,
) -> KnowledgeResult:
    """Async module entry point for Agent 2."""
    agent = KnowledgeAgent(place_index or PlaceIndex.from_catalog(), rag=rag)
    return await agent.retrieve(query, intent, request_id=request_id)


def retrieve_knowledge_sync(
    query: str,
    intent: IntentResult,
    *,
    place_index: PlaceIndex | None = None,
    rag: RAGService | None = None,
    request_id: str | None = None,
) -> KnowledgeResult:
    agent = KnowledgeAgent(place_index or PlaceIndex.from_catalog(), rag=rag)
    return agent.retrieve_sync(query, intent, request_id=request_id)
