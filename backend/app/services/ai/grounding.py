from __future__ import annotations

import asyncio
import logging
import re
import time
import unicodedata
from dataclasses import dataclass, field

from app.services.ai.prompts import (
    LOCALE_PROMPTS,
    SYSTEM_PROMPT,
    TEXT_STYLE_PROMPT,
    VOICE_STYLE_PROMPT,
)
from app.services.metrics.latency import PhaseTimer
from app.services.rag.base import PlaceholderRAGService, RAGService
from app.services.rag.chunk import KnowledgeChunk
from app.services.rag.context import build_system_prompt, format_knowledge_context, format_web_context
from app.services.search.base import PlaceholderWebSearchService, WebSearchService

logger = logging.getLogger(__name__)

_LIVE_NEED = re.compile(
    r"\b("
    r"prix|tarif|horaires?|ouvert|ouverte|fermeture|aujourd.?hui|actu|"
    r"actualit|visa|gr[eè]ve|interdit|s[eé]curit[eé]|202[4-9]|maintenant"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class GroundingResult:
    system_prompt: str
    chunks: list[KnowledgeChunk] = field(default_factory=list)
    phases_ms: dict[str, float] = field(default_factory=dict)


def build_retrieval_query(message: str, history: list[dict[str, str]]) -> str:
    recent_user = " ".join(
        turn["content"]
        for turn in history[-4:]
        if turn.get("role") == "user"
    )
    return f"{recent_user} {message}".strip()


def _fold(text: str) -> str:
    lowered = text.casefold()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def knowledge_covers_query(query: str, chunks: list[KnowledgeChunk]) -> bool:
    """True when local KB is enough and live web can be skipped for speed."""
    if len(chunks) < 2:
        return False
    if _LIVE_NEED.search(query):
        return False
    folded_query = _fold(query)
    tokens = [tok for tok in re.findall(r"[a-z0-9]{4,}", folded_query)]
    if not tokens:
        return len(chunks) >= 3
    haystack = _fold(
        " ".join(
            f"{chunk.title} {chunk.city or ''} {chunk.region or ''} {chunk.text[:240]}"
            for chunk in chunks[:4]
        )
    )
    hits = sum(1 for token in tokens if token in haystack)
    return hits >= max(1, min(3, len(tokens) // 2))


async def build_grounded_system_prompt(
    message: str,
    history: list[dict[str, str]],
    *,
    rag_service: RAGService,
    web_search_service: WebSearchService,
    rag_top_k: int = 4,
    web_search_max_results: int = 3,
    web_search_timeout_seconds: float = 4.0,
    brief: bool = False,
    skip_kb: bool = False,
    skip_web: bool = False,
    locale: str = "fr",
    timer: PhaseTimer | None = None,
) -> GroundingResult:
    """Assemble system prompt with local KB + optional live web hits.

    RAG runs first. Web search is skipped when the KB already covers the query,
    otherwise it is hard time-boxed so slow providers cannot stall the answer.
    Simple routed queries can skip both legs entirely.
    """
    started = time.perf_counter()
    phases: dict[str, float] = {}
    query = build_retrieval_query(message, history)
    chunks: list[KnowledgeChunk] = []
    kb_text = ""
    web_text = ""
    # Voice gets a tighter KB budget → fewer LLM input tokens → faster TTFT.
    kb_max_chars = 360 if brief else 480
    web_max_chars = 240 if brief else 300
    kb_max_chunks = min(rag_top_k, 3 if brief else 4)

    if skip_kb:
        phases["rag"] = 0.0
        phases["web"] = 0.0
        prompt_t0 = time.perf_counter()
        prompt = build_system_prompt(SYSTEM_PROMPT, "", "")
        if brief:
            prompt = f"{prompt.rstrip()}\n\n{VOICE_STYLE_PROMPT}\n"
        else:
            prompt = f"{prompt.rstrip()}\n\n{TEXT_STYLE_PROMPT}\n"
        locale_block = LOCALE_PROMPTS.get(locale) or LOCALE_PROMPTS["fr"]
        # Locale hard rule last — models weight the final instruction most.
        prompt = f"{prompt.rstrip()}\n\n{locale_block}"
        phases["prompt"] = round((time.perf_counter() - prompt_t0) * 1000, 1)
        phases["grounding"] = round((time.perf_counter() - started) * 1000, 1)
        logger.info(
            "Grounding: skipped (route=simple) (%.0fms)",
            phases["grounding"],
        )
        _stamp_timer(timer, phases)
        return GroundingResult(system_prompt=prompt, chunks=[], phases_ms=phases)

    if not isinstance(rag_service, PlaceholderRAGService):
        rag_t0 = time.perf_counter()
        try:
            chunks = await rag_service.retrieve_chunks(query, top_k=rag_top_k)
            kb_text = format_knowledge_context(
                chunks,
                max_chars=kb_max_chars,
                max_chunks=kb_max_chunks,
            )
        except Exception:
            logger.exception("RAG retrieval failed; continuing without KB context")
        phases["rag"] = round((time.perf_counter() - rag_t0) * 1000, 1)
    else:
        phases["rag"] = 0.0

    skip_web_search = (
        skip_web
        or web_search_max_results <= 0
        or isinstance(web_search_service, PlaceholderWebSearchService)
        or knowledge_covers_query(query, chunks)
    )
    if skip_web_search:
        phases["web"] = 0.0
        logger.info(
            "Grounding: kb=%s chunks, web=skipped rag=%.0fms (%.0fms)",
            len(chunks),
            phases["rag"],
            (time.perf_counter() - started) * 1000,
        )
    else:
        web_t0 = time.perf_counter()
        try:
            hits = await asyncio.wait_for(
                web_search_service.search(query, max_results=web_search_max_results),
                timeout=web_search_timeout_seconds,
            )
            web_text = format_web_context(hits, max_chars=web_max_chars)
            phases["web"] = round((time.perf_counter() - web_t0) * 1000, 1)
            logger.info(
                "Grounding: kb=%s chunks, web=%s hits rag=%.0fms web=%.0fms (%.0fms)",
                len(chunks),
                len(hits),
                phases["rag"],
                phases["web"],
                (time.perf_counter() - started) * 1000,
            )
        except (TimeoutError, asyncio.TimeoutError):
            phases["web"] = round((time.perf_counter() - web_t0) * 1000, 1)
            logger.info(
                "Web search over %.1fs budget; answering with KB only",
                web_search_timeout_seconds,
            )
        except Exception:
            phases["web"] = round((time.perf_counter() - web_t0) * 1000, 1)
            logger.exception("Web search failed; continuing without web context")

    prompt_t0 = time.perf_counter()
    prompt = build_system_prompt(SYSTEM_PROMPT, kb_text, web_text)
    if brief:
        prompt = f"{prompt.rstrip()}\n\n{VOICE_STYLE_PROMPT}\n"
    else:
        prompt = f"{prompt.rstrip()}\n\n{TEXT_STYLE_PROMPT}\n"
    locale_block = LOCALE_PROMPTS.get(locale) or LOCALE_PROMPTS["fr"]
    # Locale hard rule last — models weight the final instruction most.
    prompt = f"{prompt.rstrip()}\n\n{locale_block}"
    phases["prompt"] = round((time.perf_counter() - prompt_t0) * 1000, 1)
    phases["grounding"] = round((time.perf_counter() - started) * 1000, 1)
    _stamp_timer(timer, phases)
    return GroundingResult(system_prompt=prompt, chunks=chunks, phases_ms=phases)


def _stamp_timer(timer: PhaseTimer | None, phases: dict[str, float]) -> None:
    if timer is None:
        return
    for name, ms in phases.items():
        timer.mark(name, ms)
