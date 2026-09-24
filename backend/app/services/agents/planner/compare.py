"""Diagnostic: compare a free-form legacy note vs Agent 3 TourismPlan."""

from __future__ import annotations

from typing import Any

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.planner.agent import TourismPlanner


def compare_plan(
    query: str,
    intent: IntentResult,
    knowledge: KnowledgeResult,
    *,
    legacy_place_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Side-by-side diagnostic without changing user-facing answers."""
    plan = TourismPlanner().plan(query, intent, knowledge)
    legacy_ids = legacy_place_ids or [p.place_id for p in knowledge.places[:4]]
    return {
        "query": query,
        "legacy": {
            "place_ids": legacy_ids,
            "note": "legacy = raw Agent2 top places / old RAG ids (not a plan)",
        },
        "agent3": {
            **plan.observability(),
            "selected_places": list(plan.selected_places),
            "day_place_ids": [
                [item.place_id for item in day.places] for day in plan.days
            ],
        },
        "subset_ok": set(plan.selected_places).issubset(
            {p.place_id for p in knowledge.places}
        ),
    }
