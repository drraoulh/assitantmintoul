"""AGENT 2 — Knowledge & Retrieval orchestrator."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.knowledge_retriever import KnowledgeRetriever
from app.services.agents.knowledge.models import KnowledgeResult
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

        places, place_ms = self._places.retrieve(query, intent)
        places = validate_places(places, known_ids=self._known_ids)

        knowledge, know_ms = await self._knowledge.retrieve(query, intent)

        src_started = time.perf_counter()
        sources = resolve_sources(places, knowledge, self._index.places)
        source_ms = (time.perf_counter() - src_started) * 1000.0

        missing = detect_missing(places, knowledge, intent.intent)
        confidence = compute_confidence(places, knowledge, intent.intent)
        web_needed = should_request_web(intent.intent, missing, confidence)
        if intent.needs_web or intent.needs_booking:
            web_needed = True

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
            confidence=round(confidence, 3),
            request_id=rid,
            place_retrieval_ms=round(place_ms, 3),
            knowledge_retrieval_ms=round(know_ms, 3),
            source_resolution_ms=round(source_ms, 3),
            total_agent2_ms=round(total_ms, 3),
            source=source,  # type: ignore[arg-type]
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
