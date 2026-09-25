"""Pydantic models for Agent 1 — Intent & Router."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Intent(str, Enum):
    """Supported tourist intent taxonomy (Phase 2.1)."""

    SIMPLE_QA = "SIMPLE_QA"
    TOURISM_INFO = "TOURISM_INFO"
    PLACE_SEARCH = "PLACE_SEARCH"
    PLACE_DETAILS = "PLACE_DETAILS"
    ITINERARY = "ITINERARY"
    BUDGET_TRIP = "BUDGET_TRIP"
    NATURE = "NATURE"
    CULTURE = "CULTURE"
    FOOD = "FOOD"
    HOTEL = "HOTEL"
    BOOKING = "BOOKING"
    VISION = "VISION"
    WEB_SEARCH = "WEB_SEARCH"
    CLARIFICATION = "CLARIFICATION"


IntentName = Literal[
    "SIMPLE_QA",
    "TOURISM_INFO",
    "PLACE_SEARCH",
    "PLACE_DETAILS",
    "ITINERARY",
    "BUDGET_TRIP",
    "NATURE",
    "CULTURE",
    "FOOD",
    "HOTEL",
    "BOOKING",
    "VISION",
    "WEB_SEARCH",
    "CLARIFICATION",
]


class IntentResult(BaseModel):
    """Structured output of Agent 1. Never invents missing slots."""

    intent: IntentName
    location: str | None = None
    region: str | None = None
    city: str | None = None
    duration_days: int | None = None
    budget_xaf: int | None = None
    people: int | None = None
    children: int | None = None
    interests: list[str] = Field(default_factory=list)
    travel_style: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    language: str | None = None
    needs_knowledge: bool = False
    needs_places: bool = False
    needs_planner: bool = False
    needs_web: bool = False
    needs_booking: bool = False
    needs_vision: bool = False
    web_reason: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    request_id: str | None = None
    router_latency_ms: float | None = None
    source: Literal["rules", "hybrid", "llm", "fallback"] = "rules"

    @field_validator("interests", mode="before")
    @classmethod
    def _normalize_interests(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        if isinstance(value, (list, tuple)):
            out: list[str] = []
            for item in value:
                text = str(item).strip()
                if text and text not in out:
                    out.append(text)
            return out
        return []

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def observability(self) -> dict[str, object]:
        """Safe metrics payload — no raw user text / PII."""
        return {
            "request_id": self.request_id,
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "router_latency_ms": self.router_latency_ms,
            "needs_knowledge": self.needs_knowledge,
            "needs_places": self.needs_places,
            "needs_planner": self.needs_planner,
            "needs_web": self.needs_web,
            "web_reason": self.web_reason,
            "needs_booking": self.needs_booking,
            "needs_vision": self.needs_vision,
            "source": self.source,
        }
