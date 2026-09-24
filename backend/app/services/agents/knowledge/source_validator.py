"""Anti-hallucination validation — only keep evidences grounded in retrieval."""

from __future__ import annotations

from app.services.agents.knowledge.models import (
    KnowledgeEvidence,
    KnowledgeResult,
    PlaceEvidence,
    SourceEvidence,
)
from app.services.agents.knowledge.place_store import PlaceRecord


def validate_places(
    places: list[PlaceEvidence],
    *,
    known_ids: set[str] | None = None,
) -> list[PlaceEvidence]:
    """Drop any place not present in the known published index."""
    if known_ids is None:
        return [p for p in places if p.place_id and p.is_published]
    return [
        p
        for p in places
        if p.place_id in known_ids and p.is_published
    ]


def resolve_sources(
    places: list[PlaceEvidence],
    knowledge: list[KnowledgeEvidence],
    index_places: list[PlaceRecord],
) -> list[SourceEvidence]:
    """Build SourceEvidence only from retrieved place/chunk metadata — no invented URLs."""
    by_id = {p.place_id: p for p in index_places}
    seen: dict[str, SourceEvidence] = {}

    for place in places:
        record = by_id.get(place.place_id)
        if record and record.source_id:
            sid = record.source_id
            if sid not in seen:
                seen[sid] = SourceEvidence(
                    source_id=sid,
                    name=record.source_name,
                    url=record.source_url,  # may be None — never invent
                    source_type="place",
                )
        for sid in place.source_ids:
            if sid not in seen:
                seen[sid] = SourceEvidence(
                    source_id=sid,
                    name=None,
                    url=None,
                    source_type="place",
                )

    for chunk in knowledge:
        if not chunk.source_id:
            continue
        sid = chunk.source_id
        if sid not in seen:
            seen[sid] = SourceEvidence(
                source_id=sid,
                name=chunk.title,
                url=None,
                source_type="knowledge_chunk",
            )
    return list(seen.values())


def detect_missing(
    places: list[PlaceEvidence],
    knowledge: list[KnowledgeEvidence],
    intent: str,
) -> list[str]:
    missing: list[str] = []
    if not places and intent in {
        "PLACE_SEARCH",
        "PLACE_DETAILS",
        "NATURE",
        "ITINERARY",
        "BUDGET_TRIP",
        "HOTEL",
        "BOOKING",
    }:
        missing.append("matching_places")

    if not knowledge and intent in {"SIMPLE_QA", "TOURISM_INFO", "FOOD", "CULTURE"}:
        missing.append("knowledge_chunks")

    if places:
        if any(p.estimated_cost_xaf is None for p in places):
            if intent in {"BUDGET_TRIP", "BOOKING", "HOTEL", "PLACE_DETAILS"}:
                missing.append("estimated_cost_xaf")
        if intent in {"PLACE_DETAILS", "BOOKING", "HOTEL"}:
            missing.append("opening_hours")
            missing.append("current_price")

    if intent in {"BOOKING", "HOTEL", "WEB_SEARCH"}:
        missing.append("live_availability")

    # Deduplicate preserving order
    out: list[str] = []
    for item in missing:
        if item not in out:
            out.append(item)
    return out


def compute_confidence(
    places: list[PlaceEvidence],
    knowledge: list[KnowledgeEvidence],
    intent: str,
) -> float:
    if not places and not knowledge:
        return 0.15

    best_place = max((p.evidence_score for p in places), default=0.0)
    best_know = max((k.score for k in knowledge), default=0.0)

    if intent in {"PLACE_DETAILS", "PLACE_SEARCH", "NATURE", "CULTURE"} and places:
        if best_place >= 0.7:
            return min(0.95, 0.55 + best_place * 0.4)
        return min(0.75, 0.35 + best_place * 0.4)

    if intent in {"SIMPLE_QA", "FOOD", "TOURISM_INFO"} and knowledge:
        return min(0.9, 0.45 + best_know * 0.4)

    if places and knowledge:
        return min(0.92, 0.4 + 0.3 * best_place + 0.25 * best_know)

    if places:
        return min(0.8, 0.3 + best_place * 0.5)

    return min(0.7, 0.25 + best_know * 0.4)


def should_request_web(intent: str, missing: list[str], confidence: float) -> bool:
    if intent in {"BOOKING", "WEB_SEARCH"}:
        return True
    if intent == "HOTEL" and ("matching_places" in missing or "live_availability" in missing):
        return True
    if confidence < 0.35 and intent not in {"CLARIFICATION", "VISION"}:
        return True
    return False


def finalize_result(result: KnowledgeResult) -> KnowledgeResult:
    """Ensure anti-hallucination contract on the outbound payload."""
    result.places = [p for p in result.places if p.place_id and p.is_published]
    # Never fill null costs
    for place in result.places:
        # estimated_cost_xaf stays None when unknown
        if place.activities is None:
            place.activities = []
    return result
