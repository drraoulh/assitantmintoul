"""Configurable Top-K and truncation for Agent 2."""

from __future__ import annotations

from typing import Mapping

from app.services.agents.intent.models import IntentName

# Intent → max places returned (Agent 3 will refine itineraries later).
PLACE_TOP_K: Mapping[str, int] = {
    "SIMPLE_QA": 0,
    "TOURISM_INFO": 3,
    "PLACE_SEARCH": 8,
    "PLACE_DETAILS": 3,
    "ITINERARY": 12,
    "BUDGET_TRIP": 12,
    "NATURE": 8,
    "CULTURE": 8,
    "FOOD": 5,
    "HOTEL": 6,
    "BOOKING": 6,
    "VISION": 0,
    "WEB_SEARCH": 0,
    "CLARIFICATION": 0,
    "TRAVEL_ROUTE": 6,
    "IMAGE_SEARCH": 0,
}

KNOWLEDGE_TOP_K: Mapping[str, int] = {
    "SIMPLE_QA": 4,
    "TOURISM_INFO": 5,
    "PLACE_SEARCH": 3,
    "PLACE_DETAILS": 3,
    "ITINERARY": 4,
    "BUDGET_TRIP": 3,
    "NATURE": 3,
    "CULTURE": 5,
    "FOOD": 6,
    "HOTEL": 2,
    "BOOKING": 2,
    "VISION": 0,
    "WEB_SEARCH": 4,
    "CLARIFICATION": 2,
    "TRAVEL_ROUTE": 3,
    "IMAGE_SEARCH": 2,
}

# Max characters kept per knowledge chunk evidence (context size control).
KNOWLEDGE_CONTENT_MAX_CHARS = 600


def place_top_k(intent: IntentName | str, override: int | None = None) -> int:
    if override is not None:
        return max(0, override)
    return int(PLACE_TOP_K.get(str(intent), 5))


def knowledge_top_k(intent: IntentName | str, override: int | None = None) -> int:
    if override is not None:
        return max(0, override)
    return int(KNOWLEDGE_TOP_K.get(str(intent), 4))
