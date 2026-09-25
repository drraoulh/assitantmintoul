"""Merge Gemini tool results with Agent 2 / Supabase evidence."""

from __future__ import annotations

from app.services.agents.knowledge.models import (
    KnowledgeEvidence,
    KnowledgeResult,
    SourceEvidence,
)
from app.services.gemini.gemini_types import GeminiResult


def merge_gemini_into_knowledge(
    knowledge: KnowledgeResult,
    gemini: GeminiResult,
) -> KnowledgeResult:
    merged = knowledge.model_copy(deep=True)
    merged.gemini_answer = gemini.text.strip() or None
    merged.answer_context = gemini.text.strip() or merged.answer_context
    merged.tools_used = list(gemini.tools_used)
    merged.warnings = list(dict.fromkeys([*merged.warnings, *gemini.warnings]))

    web_sources: list[SourceEvidence] = []
    for item in gemini.web_sources:
        source = SourceEvidence(
            source_id=f"gemini:web:{item.url or item.title}",
            name=item.title,
            url=item.url,
            source_type="gemini_web",
        )
        web_sources.append(source)
        if not any(existing.url and existing.url == source.url for existing in merged.sources):
            merged.sources.append(source)
    merged.web_sources = web_sources

    map_rows: list[dict[str, str | None]] = []
    for index, item in enumerate(gemini.map_results):
        row = {
            "title": item.title,
            "url": item.url,
            "place_id": item.place_id,
            "snippet": item.snippet,
        }
        map_rows.append(row)
        merged.knowledge.append(
            KnowledgeEvidence(
                chunk_id=f"gemini-maps-{index}",
                content=f"{item.title}: {item.snippet or ''}".strip(": "),
                source_id=f"gemini:maps:{item.place_id or index}",
                title=item.title,
                score=0.82,
            )
        )
        if item.url and not any(s.url == item.url for s in merged.sources):
            merged.sources.append(
                SourceEvidence(
                    source_id=f"gemini:maps:{item.place_id or index}",
                    name=item.title,
                    url=item.url,
                    source_type="gemini_maps",
                )
            )
    merged.map_results = map_rows

    if gemini.tools_used:
        merged.web_needed = False
        merged.confidence = max(merged.confidence, 0.72)
        if merged.source == "empty":
            merged.source = "documents"
        elif merged.places:
            merged.source = "hybrid"
    return merged
