"""Budget helpers — never invent costs or multiply by people/children."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.agents.knowledge.models import PlaceEvidence
from app.services.agents.planner.models import BudgetStatus


@dataclass(frozen=True)
class BudgetAssessment:
    known_cost_xaf: int
    total_estimated_cost_xaf: int | None
    budget_status: BudgetStatus
    unknown_cost_count: int
    warnings: list[str]


def assess_budget(
    selected: list[PlaceEvidence],
    budget_xaf: int | None,
    *,
    people: int | None = None,
    children: int | None = None,
) -> BudgetAssessment:
    warnings: list[str] = []
    known = 0
    unknown = 0
    for place in selected:
        if place.estimated_cost_xaf is None:
            unknown += 1
            warnings.append(
                f"Le coût de « {place.name} » n'est pas renseigné."
            )
        else:
            known += int(place.estimated_cost_xaf)

    if people is not None and people > 1:
        warnings.append(
            "Le mode de tarification par personne/groupe n'est pas suffisamment documenté."
        )
    if children is not None and children > 0:
        warnings.append(
            "Aucun tarif enfant distinct n'a été appliqué (données absentes)."
        )

    if not selected:
        return BudgetAssessment(
            known_cost_xaf=0,
            total_estimated_cost_xaf=None if budget_xaf is not None else 0,
            budget_status="UNKNOWN",
            unknown_cost_count=0,
            warnings=warnings,
        )

    if unknown > 0:
        status: BudgetStatus = "PARTIAL" if budget_xaf is not None else "PARTIAL"
        return BudgetAssessment(
            known_cost_xaf=known,
            total_estimated_cost_xaf=None,
            budget_status=status,
            unknown_cost_count=unknown,
            warnings=warnings,
        )

    # All costs known
    if budget_xaf is None:
        return BudgetAssessment(
            known_cost_xaf=known,
            total_estimated_cost_xaf=known,
            budget_status="UNKNOWN",
            unknown_cost_count=0,
            warnings=warnings,
        )
    if known <= budget_xaf:
        return BudgetAssessment(
            known_cost_xaf=known,
            total_estimated_cost_xaf=known,
            budget_status="WITHIN_BUDGET",
            unknown_cost_count=0,
            warnings=warnings,
        )
    return BudgetAssessment(
        known_cost_xaf=known,
        total_estimated_cost_xaf=known,
        budget_status="OVER_BUDGET",
        unknown_cost_count=0,
        warnings=warnings,
    )
