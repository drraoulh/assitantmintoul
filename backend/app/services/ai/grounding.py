from __future__ import annotations

import logging

from app.services.ai.prompts import SYSTEM_PROMPT
from app.services.rag.base import PlaceholderRAGService, RAGService
from app.services.rag.context import build_system_prompt, format_knowledge_context, format_web_context
from app.services.search.base import PlaceholderWebSearchService, WebSearchService

logger = logging.getLogger(__name__)


def build_retrieval_query(message: str, history: list[dict[str, str]]) -> str:
    recent_user = " ".join(
        turn["content"]
        for turn in history[-4:]
        if turn.get("role") == "user"
    )
    return f"{recent_user} {message}".strip()


async def build_grounded_system_prompt(
    message: str,
    history: list[dict[str, str]],
    *,
    rag_service: RAGService,
    web_search_service: WebSearchService,
    rag_top_k: int = 6,
    web_search_max_results: int = 4,
) -> str:
    """Assemble system prompt with local KB + optional live web hits."""
    query = build_retrieval_query(message, history)
    kb_context = ""
    web_context = ""

    if not isinstance(rag_service, PlaceholderRAGService):
        try:
            chunks = await rag_service.retrieve_chunks(query, top_k=rag_top_k)
            kb_context = format_knowledge_context(chunks)
        except Exception:
            logger.exception("RAG retrieval failed; continuing without KB context")

    if not isinstance(web_search_service, PlaceholderWebSearchService):
        try:
            hits = await web_search_service.search(
                query,
                max_results=web_search_max_results,
            )
            web_context = format_web_context(hits)
        except Exception:
            logger.exception("Web search failed; continuing without web context")

    return build_system_prompt(SYSTEM_PROMPT, kb_context, web_context)
