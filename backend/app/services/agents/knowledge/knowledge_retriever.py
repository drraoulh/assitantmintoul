"""Document / knowledge_chunks retrieval — reuses LocalRAG TF-IDF (no vectors)."""

from __future__ import annotations

import time

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeEvidence
from app.services.agents.knowledge.topk import KNOWLEDGE_CONTENT_MAX_CHARS, knowledge_top_k
from app.services.rag.base import RAGService
from app.services.rag.chunk import KnowledgeChunk
from app.services.rag.local import LocalRAGService


class KnowledgeRetriever:
    """Lexical retrieval over curated chunks. Does not enable pgvector."""

    def __init__(self, rag: RAGService | None = None) -> None:
        self._rag = rag

    def _service(self) -> RAGService:
        if self._rag is None:
            self._rag = LocalRAGService()
        return self._rag

    async def retrieve(
        self,
        query: str,
        intent: IntentResult,
        *,
        top_k: int | None = None,
    ) -> tuple[list[KnowledgeEvidence], float]:
        started = time.perf_counter()
        limit = knowledge_top_k(intent.intent, top_k)
        if limit <= 0:
            return [], (time.perf_counter() - started) * 1000.0
        if not intent.needs_knowledge and intent.intent not in {
            "SIMPLE_QA",
            "TOURISM_INFO",
            "FOOD",
            "CULTURE",
            "WEB_SEARCH",
            "PLACE_DETAILS",
            "PLACE_SEARCH",
            "NATURE",
            "ITINERARY",
            "BUDGET_TRIP",
        }:
            return [], (time.perf_counter() - started) * 1000.0

        if intent.intent in {"PLACE_SEARCH", "NATURE", "ITINERARY", "BUDGET_TRIP"}:
            if not intent.needs_knowledge:
                limit = min(limit, 3)

        search_query = _normalize_query(query, intent)
        raw = await self._service().retrieve_chunks(search_query, top_k=limit)
        evidences = [_chunk_to_evidence(chunk, rank) for rank, chunk in enumerate(raw)]
        elapsed = (time.perf_counter() - started) * 1000.0
        return evidences, elapsed


def _normalize_query(query: str, intent: IntentResult) -> str:
    q = (query or "").strip()
    if intent.intent == "FOOD" and "cameroun" not in q.casefold() and "cameroon" not in q.casefold():
        return f"{q} cuisine camerounaise plats"
    if intent.intent == "CULTURE" and intent.interests:
        return f"{q} {' '.join(intent.interests)}"
    if intent.city:
        return f"{q} {intent.city}"
    return q


def _chunk_to_evidence(chunk: KnowledgeChunk, rank: int) -> KnowledgeEvidence:
    score = max(0.15, 1.0 - rank * 0.12)
    content = (chunk.text or "").strip()
    if len(content) > KNOWLEDGE_CONTENT_MAX_CHARS:
        content = content[: KNOWLEDGE_CONTENT_MAX_CHARS - 1].rstrip() + "…"
    return KnowledgeEvidence(
        chunk_id=chunk.id,
        content=content,
        source_id=chunk.source or None,
        title=chunk.title or None,
        score=round(score, 3),
    )
