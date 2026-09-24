"""Allowed evidence whitelist for Agent 4 grounding (Phase 2.7).

Qwen is formulation-only. Every specific tourism claim must map to this set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.validate import fold


@dataclass
class AllowedEvidence:
    """Compact source-of-truth passed to prompts and the deterministic validator."""

    place_ids: set[str] = field(default_factory=set)
    place_names: set[str] = field(default_factory=set)
    place_names_folded: set[str] = field(default_factory=set)
    known_costs_xaf: set[int] = field(default_factory=set)
    known_activities: set[str] = field(default_factory=set)
    known_urls: set[str] = field(default_factory=set)
    known_source_ids: set[str] = field(default_factory=set)
    known_distances_km: set[float] = field(default_factory=set)
    distance_type: str = "geographic"  # crow-flies unless road evidence exists
    allowed_slogans: set[str] = field(default_factory=set)
    has_verified_places: bool = False
    has_web_evidence: bool = False
    has_plan_places: bool = False
    missing_tags: list[str] = field(default_factory=list)

    def as_prompt_dict(self) -> dict[str, Any]:
        return {
            "allowed_place_ids": sorted(self.place_ids),
            "allowed_place_names": sorted(self.place_names),
            "known_costs_xaf": sorted(self.known_costs_xaf),
            "known_activities": sorted(self.known_activities)[:24],
            "known_urls": sorted(self.known_urls)[:8],
            "known_distances_km": sorted(self.known_distances_km),
            "distance_type": self.distance_type,
            "allowed_slogans": sorted(self.allowed_slogans),
            "has_verified_places": self.has_verified_places,
            "has_web_evidence": self.has_web_evidence,
            "has_plan_places": self.has_plan_places,
            "missing_information": list(self.missing_tags)[:12],
            "rules": [
                "Mention ONLY places whose place_id/name appears in allowed_* lists.",
                "For itineraries use ONLY tourism_plan places.",
                "Never invent restaurants, hotels, prices, hours, activities, or availability.",
                "If a cost/hour/activity is missing, say it is not available in verified context.",
                "Distances are geographic (à vol d'oiseau / crow flies) unless distance_type says otherwise.",
                "Do not add Cameroon slogans (e.g. Africa in miniature) unless listed in allowed_slogans.",
            ],
        }


def build_allowed_evidence(
    intent: IntentResult,
    knowledge: KnowledgeResult,
    plan: TourismPlan | None,
) -> AllowedEvidence:
    ev = AllowedEvidence()
    missing: list[str] = list(knowledge.missing_information)
    if plan:
        missing.extend(plan.missing_information)

    for place in knowledge.places:
        if place.place_id:
            ev.place_ids.add(place.place_id)
        if place.name:
            ev.place_names.add(place.name)
            ev.place_names_folded.add(fold(place.name))
        if place.estimated_cost_xaf is not None:
            ev.known_costs_xaf.add(int(place.estimated_cost_xaf))
        for act in place.activities or []:
            if act:
                ev.known_activities.add(act.strip())
                ev.known_activities.add(fold(act))

    for chunk in knowledge.knowledge:
        content = chunk.content or ""
        if content.lstrip().lower().startswith("[web evidence"):
            ev.has_web_evidence = True
        # slogans only if explicitly present in evidence text
        folded = fold(content)
        if "africa in miniature" in folded or "afrique en miniature" in folded:
            ev.allowed_slogans.add("Africa in miniature")
            ev.allowed_slogans.add("Afrique en miniature")
        # Geo facts may mention admin names — whitelist them for grounding
        if (chunk.chunk_id or "").startswith("geo-") or (chunk.source_id or "") == "geo:cameroon_admin":
            for token in (
                "Bafoussam",
                "Ouest",
                "West",
                "Mifi",
                "Foumban",
                "Dschang",
                "Baleng",
                "Bamougoum",
                "Cameroun",
                "Cameroon",
                "Lac Baleng",
                "Noun",
                "Menoua",
            ):
                if fold(token) in folded:
                    ev.place_names.add(token)
                    ev.place_names_folded.add(fold(token))

    for src in knowledge.sources:
        if src.source_id:
            ev.known_source_ids.add(src.source_id)
        if src.url:
            ev.known_urls.add(src.url)

    if plan:
        for pid in plan.selected_places or []:
            if pid:
                ev.place_ids.add(pid)
        for day in plan.days:
            for item in day.places:
                if item.place_id:
                    ev.place_ids.add(item.place_id)
                if item.place_name:
                    ev.place_names.add(item.place_name)
                    ev.place_names_folded.add(fold(item.place_name))
                if item.estimated_cost_xaf is not None:
                    ev.known_costs_xaf.add(int(item.estimated_cost_xaf))
                if item.distance_from_previous_km is not None:
                    ev.known_distances_km.add(float(item.distance_from_previous_km))
        if plan.total_estimated_cost_xaf is not None:
            ev.known_costs_xaf.add(int(plan.total_estimated_cost_xaf))
        if plan.known_cost_xaf is not None:
            ev.known_costs_xaf.add(int(plan.known_cost_xaf))
        if plan.budget_xaf is not None:
            ev.known_costs_xaf.add(int(plan.budget_xaf))

    # City / region from intent are location filters, not tourist sites — allow as names.
    if intent.city:
        ev.place_names.add(intent.city)
        ev.place_names_folded.add(fold(intent.city))
    if intent.region:
        ev.place_names.add(intent.region)
        ev.place_names_folded.add(fold(intent.region))

    ev.has_verified_places = bool(knowledge.places)
    ev.has_plan_places = bool(plan and plan.selected_places)
    ev.missing_tags = list(dict.fromkeys(missing))
    return ev


def evidence_is_insufficient_for_llm(
    intent: IntentResult,
    knowledge: KnowledgeResult,
    plan: TourismPlan | None,
    *,
    user_query: str | None = None,
) -> bool:
    """Pre-generation gate: skip Qwen when there is nothing verified to formulate."""
    intent_name = intent.intent or ""
    # Clarifications / greetings / simple QA can use LLM lightly if desired,
    # but fact-heavy tourism intents with empty evidence must not.
    fact_heavy = intent_name in {
        "FOOD",
        "HOTEL",
        "BOOKING",
        "PLACE_SEARCH",
        "PLACE_DETAILS",
        "ITINERARY",
        "BUDGET_TRIP",
        "NATURE",
        "CULTURE",
        "TOURISM_INFO",
        "WEB_SEARCH",
    }
    interests = {fold(i) for i in (intent.interests or [])}
    qfold = fold(user_query or "")
    foodish = bool(
        interests
        & {"food", "restaurant", "cuisine", "gastronomie", "fish", "poisson"}
    ) or any(
        tok in qfold
        for tok in (
            "eat fish",
            "manger du poisson",
            "restaurant",
            "where to eat",
            "ou manger",
            "où manger",
        )
    )
    if intent_name == "BOOKING":
        return True  # always deterministic booking message
    if foodish and not knowledge.places and not knowledge.knowledge:
        return True
    if not fact_heavy:
        return False
    if plan is not None and plan.feasibility == "INSUFFICIENT_DATA" and not plan.selected_places:
        if not knowledge.places and not knowledge.knowledge:
            return True
    if intent_name in {"FOOD", "HOTEL"} and not knowledge.places and not knowledge.knowledge:
        return True
    if intent_name in {"ITINERARY", "BUDGET_TRIP"}:
        if plan is None or not plan.selected_places:
            if not knowledge.places:
                return True
    if intent_name in {"PLACE_SEARCH", "PLACE_DETAILS", "NATURE", "CULTURE", "TOURISM_INFO"}:
        if not knowledge.places and not knowledge.knowledge:
            return True
    return False
