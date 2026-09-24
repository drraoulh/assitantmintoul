"""Explainable place scoring for the tourism planner."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import PlaceEvidence


def _fold(text: str | None) -> str:
    return (text or "").casefold()


def _interest_flags(place: PlaceEvidence) -> set[str]:
    flags: set[str] = set()
    blob = " ".join(
        [
            _fold(place.eco_info),
            _fold(" ".join(place.eco_tags)),
            _fold(" ".join(place.category)),
            _fold(place.cultural_info),
            _fold(place.cultural_zone),
            _fold(place.description),
            _fold(" ".join(place.activities)),
            _fold(place.name),
        ]
    )
    if any(
        k in blob
        for k in (
            "nature",
            "eco",
            "parc",
            "park",
            "natural",
            "wildlife",
            "forest",
            "hik",
            "trek",
            "garden",
            "mont",
        )
    ):
        flags.add("nature")
    if any(
        k in blob
        for k in (
            "culture",
            "museum",
            "musee",
            "patrimoine",
            "sawa",
            "palace",
            "chief",
            "monument",
        )
    ):
        flags.add("culture")
    if any(k in blob for k in ("food", "cuisine", "gastr", "restaurant", "plat", "ndole")):
        flags.add("food")
    if any(k in blob for k in ("hotel", "hôtel", "lodg", "auberge")):
        flags.add("hotel")
    return flags


@dataclass
class ScoredPlace:
    place: PlaceEvidence
    total: float
    breakdown: dict[str, float] = field(default_factory=dict)
    interests: set[str] = field(default_factory=set)


def score_place_for_plan(
    place: PlaceEvidence,
    intent: IntentResult,
    *,
    distance_penalty: float = 0.0,
) -> ScoredPlace:
    interests = _interest_flags(place)
    breakdown: dict[str, float] = {
        "evidence": float(place.evidence_score or 0.0) * 0.35,
        "interest_match": 0.0,
        "location_score": 0.0,
        "eco_score": 0.0,
        "culture_score": 0.0,
        "budget_score": 0.0,
        "distance_penalty": -abs(distance_penalty),
    }

    wanted = [i.casefold() for i in intent.interests]
    if intent.intent == "NATURE" and "nature" not in wanted:
        wanted.append("nature")
    if intent.intent == "CULTURE" and "culture" not in wanted:
        wanted.append("culture")
    if intent.intent == "FOOD" and "food" not in wanted:
        wanted.append("food")

    if wanted:
        hits = sum(1 for w in wanted if w in interests)
        breakdown["interest_match"] = min(0.35, 0.18 * hits)
    elif intent.intent in {"ITINERARY", "BUDGET_TRIP", "PLACE_SEARCH"}:
        breakdown["interest_match"] = 0.05

    if intent.city and place.city and _fold(intent.city) in _fold(place.city):
        breakdown["location_score"] = 0.25
    elif intent.region and place.region and _fold(intent.region) in _fold(place.region):
        breakdown["location_score"] = 0.15

    if "nature" in interests:
        breakdown["eco_score"] = 0.12 if (place.eco_tags or place.eco_info) else 0.06
    if "culture" in interests:
        breakdown["culture_score"] = (
            0.12 if (place.cultural_info or place.cultural_zone) else 0.06
        )

    if intent.budget_xaf is not None and place.estimated_cost_xaf is not None:
        if place.estimated_cost_xaf <= intent.budget_xaf:
            breakdown["budget_score"] = 0.08
        else:
            breakdown["budget_score"] = -0.15
    elif place.estimated_cost_xaf is not None:
        breakdown["budget_score"] = 0.03

    total = sum(breakdown.values())
    return ScoredPlace(
        place=place,
        total=round(total, 4),
        breakdown={k: round(v, 4) for k, v in breakdown.items()},
        interests=interests,
    )


def place_matches_interest(place: PlaceEvidence, interest: str) -> bool:
    return interest.casefold() in _interest_flags(place)
