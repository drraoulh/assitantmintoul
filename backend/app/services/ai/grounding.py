from __future__ import annotations

import asyncio
import logging

from app.services.ai.prompts import SYSTEM_PROMPT, VOICE_STYLE_PROMPT
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
    web_search_timeout_seconds: float = 6.0,
    brief: bool = False,
) -> str:
    """Assemble system prompt with local KB + optional live web hits.

    Retrieval and web search run together, and the web leg is time-boxed so a
    slow provider cannot stall the answer.
    """
    query = build_retrieval_query(message, history)

    async def knowledge_context() -> str:
        if isinstance(rag_service, PlaceholderRAGService):
            return ""
        try:
            chunks = await rag_service.retrieve_chunks(query, top_k=rag_top_k)
            return format_knowledge_context(chunks)
        except Exception:
            logger.exception("RAG retrieval failed; continuing without KB context")
            return ""

    async def web_context() -> str:
        if web_search_max_results <= 0 or isinstance(
            web_search_service,
            PlaceholderWebSearchService,
        ):
            return ""
        try:
            hits = await asyncio.wait_for(
                web_search_service.search(query, max_results=web_search_max_results),
                timeout=web_search_timeout_seconds,
            )
            return format_web_context(hits)
        except (TimeoutError, asyncio.TimeoutError):
            logger.info(
                "Web search over %.1fs budget; answering without web context",
                web_search_timeout_seconds,
            )
            return ""
        except Exception:
            logger.exception("Web search failed; continuing without web context")
            return ""

    kb_text, web_text = await asyncio.gather(knowledge_context(), web_context())
    prompt = build_system_prompt(SYSTEM_PROMPT, kb_text, web_text)
    if brief:
        return f"{prompt.rstrip()}\n\n{VOICE_STYLE_PROMPT}\n"
    return prompt
