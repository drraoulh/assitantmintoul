"""Pydantic models for Agent 3 — Tourism Planner."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

BudgetStatus = Literal["WITHIN_BUDGET", "OVER_BUDGET", "UNKNOWN", "PARTIAL"]
Feasibility = Literal["FEASIBLE", "PARTIAL", "NOT_FEASIBLE", "INSUFFICIENT_DATA"]
PlanType = Literal[
    "ITINERARY",
    "BUDGET_TRIP",
    "NATURE_CIRCUIT",
    "CULTURE_CIRCUIT",
    "PLACE_SELECTION",
    "EMPTY",
]


class PlanItem(BaseModel):
    place_id: str
    place_name: str
    order: int
    estimated_duration_hours: float | None = None
    estimated_cost_xaf: int | None = None
    distance_from_previous_km: float | None = None
    category: list[str] = Field(default_factory=list)
    eco_tags: list[str] = Field(default_factory=list)
    reason: str | None = None
    city: str | None = None
    region: str | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)

    @field_validator("category", "eco_tags", mode="before")
    @classmethod
    def _listify(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []
        if isinstance(value, (list, tuple)):
            out: list[str] = []
            for item in value:
                text = str(item).strip()
                if text and text not in out:
                    out.append(text)
            return out
        return []


class PlanDay(BaseModel):
    day: int
    title: str
    city: str | None = None
    places: list[PlanItem] = Field(default_factory=list)
    estimated_day_cost_xaf: int | None = None
    estimated_duration_hours: float | None = None
    notes: list[str] = Field(default_factory=list)


class TourismPlan(BaseModel):
    """Structured plan only — no conversational prose."""

    plan_type: PlanType | str
    duration_days: int
    currency: str = "XAF"
    total_estimated_cost_xaf: int | None = None
    known_cost_xaf: int | None = None
    budget_xaf: int | None = None
    budget_status: BudgetStatus = "UNKNOWN"
    feasibility: Feasibility = "INSUFFICIENT_DATA"
    days: list[PlanDay] = Field(default_factory=list)
    selected_places: list[str] = Field(default_factory=list)
    interests_covered: list[str] = Field(default_factory=list)
    interests_not_covered: list[str] = Field(default_factory=list)
    constraints_applied: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    needs_web: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    request_id: str | None = None
    filtering_ms: float | None = None
    scoring_ms: float | None = None
    geo_ms: float | None = None
    budget_ms: float | None = None
    planning_ms: float | None = None
    total_planner_ms: float | None = None

    def observability(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "plan_type": self.plan_type,
            "duration_days": self.duration_days,
            "feasibility": self.feasibility,
            "budget_status": self.budget_status,
            "selected_count": len(self.selected_places),
            "days_count": len(self.days),
            "interests_covered": list(self.interests_covered),
            "interests_not_covered": list(self.interests_not_covered),
            "warnings_count": len(self.warnings),
            "missing_information": list(self.missing_information),
            "confidence": round(self.confidence, 3),
            "known_cost_xaf": self.known_cost_xaf,
            "total_estimated_cost_xaf": self.total_estimated_cost_xaf,
            "filtering_ms": self.filtering_ms,
            "scoring_ms": self.scoring_ms,
            "geo_ms": self.geo_ms,
            "budget_ms": self.budget_ms,
            "planning_ms": self.planning_ms,
            "total_planner_ms": self.total_planner_ms,
        }
