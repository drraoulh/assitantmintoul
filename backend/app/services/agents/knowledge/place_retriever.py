"""Structured place retrieval — city/region/name/eco/culture filters."""

from __future__ import annotations

import time

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import PlaceEvidence
from app.services.agents.knowledge.place_store import PlaceIndex, PlaceRecord, fold
from app.services.agents.knowledge.scoring import passes_hard_filter, score_place
from app.services.agents.knowledge.topk import place_top_k


class PlaceRetriever:
    """Search published places only. Never invents place_id / costs / activities."""

    def __init__(self, index: PlaceIndex) -> None:
        self._index = index

    def retrieve(
        self,
        query: str,
        intent: IntentResult,
        *,
        top_k: int | None = None,
        include_unpublished: bool = False,
    ) -> tuple[list[PlaceEvidence], float]:
        started = time.perf_counter()
        limit = place_top_k(intent.intent, top_k)
        place_intents = {
            "PLACE_SEARCH",
            "PLACE_DETAILS",
            "ITINERARY",
            "BUDGET_TRIP",
            "NATURE",
            "CULTURE",
            "HOTEL",
            "BOOKING",
            "FOOD",
            "TOURISM_INFO",
        }
        if limit <= 0 or (
            not intent.needs_places and intent.intent not in place_intents
        ):
            return [], (time.perf_counter() - started) * 1000.0

        city = intent.city
        region = intent.region
        place_hint = intent.location if intent.intent == "PLACE_DETAILS" else None

        candidates: list[tuple[float, list[str], PlaceRecord]] = []
        for place in self._index.places:
            if not include_unpublished and not place.is_published:
                continue

            # Location hard filter when city is explicit (structured city match).
            if city and intent.intent in {
                "PLACE_SEARCH",
                "ITINERARY",
                "BUDGET_TRIP",
                "HOTEL",
                "BOOKING",
            }:
                if not place.city or fold(city) not in fold(place.city):
                    continue

            if region and intent.intent in {"PLACE_SEARCH", "ITINERARY", "NATURE"} and not city:
                if not place.region or fold(region) not in fold(place.region):
                    continue

            if not passes_hard_filter(place, intent.intent, query):
                continue

            breakdown = score_place(
                place,
                intent=intent.intent,
                query=query,
                city=city,
                region=region,
                place_name_hint=place_hint,
                interests=intent.interests,
            )
            min_score = 0.15 if intent.intent != "PLACE_DETAILS" else 0.35
            if intent.intent == "PLACE_SEARCH" and city:
                min_score = 0.20
            if intent.intent in {"ITINERARY", "BUDGET_TRIP"} and city:
                min_score = 0.20
            if breakdown.score < min_score:
                continue
            candidates.append((breakdown.score, breakdown.reasons, place))

        candidates.sort(key=lambda item: item[0], reverse=True)
        evidences = [
            _to_evidence(place, score, reasons)
            for score, reasons, place in candidates[:limit]
        ]
        elapsed = (time.perf_counter() - started) * 1000.0
        return evidences, elapsed


def _to_evidence(place: PlaceRecord, score: float, reasons: list[str]) -> PlaceEvidence:
    categories = list(place.categories)
    source_ids = [place.source_id] if place.source_id else []
    return PlaceEvidence(
        place_id=place.place_id,
        name=place.name,
        city=place.city,
        region=place.region,
        description=_clip(place.description, 400),
        cultural_info=_clip(place.cultural_info, 300),
        eco_info=_clip(place.eco_info, 300),
        activities=list(place.activities),
        category=categories,
        eco_tags=list(place.eco_tags),
        cultural_zone=place.cultural_zone,
        estimated_cost_xaf=place.estimated_cost_xaf,  # None if unknown — never invent
        recommended_duration_hours=place.recommended_duration_hours,
        best_period=place.best_period,
        latitude=place.latitude,
        longitude=place.longitude,
        source_ids=source_ids,
        evidence_score=round(min(1.0, score), 3),
        is_published=place.is_published,
        match_reasons=reasons,
    )


def _clip(text: str | None, max_chars: int) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"
