"""Compare legacy HybridRAG / LocalRAG vs Agent 2 (diagnostic only)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.agents.intent import classify_intent
from app.services.agents.knowledge.agent import KnowledgeAgent
from app.services.agents.knowledge.place_store import PlaceIndex
from app.services.rag.base import RAGService
from app.services.rag.local import LocalRAGService


async def compare_retrieval_async(
    query: str,
    *,
    place_index: PlaceIndex | None = None,
    rag: RAGService | None = None,
    locale: str | None = "fr",
) -> dict[str, Any]:
    """Side-by-side old TF-IDF chunks vs Agent 2 structured+docs."""
    intent = classify_intent(query, locale=locale, mode="text")
    legacy = rag or LocalRAGService()
    old_chunks = await legacy.retrieve_chunks(query, top_k=4)

    agent = KnowledgeAgent(place_index or PlaceIndex.from_catalog(), rag=legacy)
    new = await agent.retrieve(query, intent)

    return {
        "query": query,
        "intent": intent.observability(),
        "old_retrieval": {
            "chunk_ids": [c.id for c in old_chunks],
            "titles": [c.title for c in old_chunks],
            "count": len(old_chunks),
        },
        "agent2": {
            **new.observability(),
            "place_ids": [p.place_id for p in new.places],
            "place_names": [p.name for p in new.places],
            "chunk_ids": [k.chunk_id for k in new.knowledge],
        },
    }


def compare_retrieval(
    query: str,
    *,
    place_index: PlaceIndex | None = None,
    rag: RAGService | None = None,
    locale: str | None = "fr",
) -> dict[str, Any]:
    return asyncio.run(
        compare_retrieval_async(
            query,
            place_index=place_index,
            rag=rag,
            locale=locale,
        )
    )
