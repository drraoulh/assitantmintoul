"""AGENT 3 — Tourism Planner orchestrator (deterministic)."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult, PlaceEvidence
from app.services.agents.planner.budget_utils import assess_budget
from app.services.agents.planner.geo_utils import order_by_nearest, place_distance_km
from app.services.agents.planner.models import PlanDay, PlanItem, TourismPlan
from app.services.agents.planner.scoring import (
    ScoredPlace,
    place_matches_interest,
    score_place_for_plan,
)

logger = logging.getLogger(__name__)

# Soft caps: places per day / max selected.
_MAX_PER_DAY = 4
_MAX_SELECTED = 15


class TourismPlanner:
    """Rules + data first. Never invents places, prices, hours, or activities."""

    def plan(
        self,
        query: str,
        intent: IntentResult,
        knowledge: KnowledgeResult,
        *,
        request_id: str | None = None,
    ) -> TourismPlan:
        t0 = time.perf_counter()
        rid = request_id or intent.request_id or knowledge.request_id or uuid.uuid4().hex[:12]
        warnings: list[str] = []
        missing: list[str] = list(knowledge.missing_information)
        constraints: list[str] = []

        # --- STEP 1–2: filter / dedupe ---
        t_filter = time.perf_counter()
        places = _dedupe_published(knowledge.places)
        filtering_ms = (time.perf_counter() - t_filter) * 1000.0

        plan_type = _plan_type(intent)
        if not places:
            return _empty_plan(
                plan_type=plan_type,
                intent=intent,
                missing=missing + (["matching_places"] if "matching_places" not in missing else []),
                warnings=warnings + ["Aucune évidence de lieu fournie par Agent 2."],
                request_id=rid,
                filtering_ms=filtering_ms,
                total_ms=(time.perf_counter() - t0) * 1000.0,
                needs_web=knowledge.web_needed or intent.needs_web,
            )

        # Duration
        duration_missing = intent.duration_days is None
        if duration_missing:
            if "duration_days" not in missing:
                missing.append("duration_days")
            # Do not silently invent a multi-day trip — pack into 1 selection day.
            duration_days = 1
            warnings.append(
                "Durée non précisée : sélection regroupée sur 1 jour (durée manquante)."
            )
        else:
            duration_days = max(1, int(intent.duration_days or 1))
            constraints.append("duration")

        if intent.budget_xaf is not None:
            constraints.append("budget")
        if intent.city:
            constraints.append("city")
        if intent.region:
            constraints.append("region")
        for interest in intent.interests:
            constraints.append(interest)
        if intent.intent in {"NATURE", "CULTURE", "FOOD"}:
            constraints.append(intent.intent.lower())

        # --- STEP 3–4: score ---
        t_score = time.perf_counter()
        scored = [score_place_for_plan(p, intent) for p in places]
        scored.sort(key=lambda s: s.total, reverse=True)
        scoring_ms = (time.perf_counter() - t_score) * 1000.0

        # Soft geo penalty for short trips spanning far regions
        t_geo = time.perf_counter()
        if duration_days <= 2 and intent.city:
            # Prefer same-city already handled in scoring; extra filter for wild jumps
            same_city = [
                s
                for s in scored
                if s.place.city and intent.city.casefold() in s.place.city.casefold()
            ]
            if same_city:
                scored = same_city + [s for s in scored if s not in same_city]

        # Select with interest coverage + budget awareness
        selected_scored = _select_places(
            scored,
            intent=intent,
            duration_days=duration_days,
        )
        selected = [s.place for s in selected_scored]

        # Group by city/region then assign days
        days = _assign_days(selected_scored, duration_days=duration_days, intent=intent)
        geo_ms = (time.perf_counter() - t_geo) * 1000.0

        # --- STEP 9: budget ---
        t_budget = time.perf_counter()
        budget = assess_budget(
            selected,
            intent.budget_xaf,
            people=intent.people,
            children=intent.children,
        )
        warnings.extend(budget.warnings)
        if any(p.estimated_cost_xaf is None for p in selected):
            if "estimated_cost_xaf" not in missing:
                missing.append("estimated_cost_xaf")
        warnings.append("transport cost unavailable")
        budget_ms = (time.perf_counter() - t_budget) * 1000.0

        # Interests coverage
        wanted = _wanted_interests(intent)
        covered = [
            w for w in wanted if any(place_matches_interest(p, w) for p in selected)
        ]
        not_covered = [w for w in wanted if w not in covered]

        # Feasibility
        feasibility = _feasibility(
            selected=selected,
            duration_days=duration_days,
            duration_missing=duration_missing,
            budget_status=budget.budget_status,
            intent=intent,
        )

        confidence = _confidence(
            selected=selected,
            knowledge=knowledge,
            intent=intent,
            covered=covered,
            wanted=wanted,
            budget_status=budget.budget_status,
            duration_missing=duration_missing,
        )

        selected_ids = [p.place_id for p in selected]
        # Anti-hallucination assert
        allowed = {p.place_id for p in knowledge.places if p.is_published}
        selected_ids = [pid for pid in selected_ids if pid in allowed]

        total_ms = (time.perf_counter() - t0) * 1000.0
        planning_ms = max(0.0, total_ms - filtering_ms - scoring_ms - geo_ms - budget_ms)

        plan = TourismPlan(
            plan_type=plan_type,
            duration_days=duration_days,
            currency="XAF",
            total_estimated_cost_xaf=budget.total_estimated_cost_xaf,
            known_cost_xaf=budget.known_cost_xaf,
            budget_xaf=intent.budget_xaf,
            budget_status=budget.budget_status,
            feasibility=feasibility,
            days=days,
            selected_places=selected_ids,
            interests_covered=covered,
            interests_not_covered=not_covered,
            constraints_applied=_unique(constraints),
            warnings=_unique(warnings),
            missing_information=_unique(missing),
            needs_web=bool(knowledge.web_needed or intent.needs_web),
            confidence=round(confidence, 3),
            request_id=rid,
            filtering_ms=round(filtering_ms, 3),
            scoring_ms=round(scoring_ms, 3),
            geo_ms=round(geo_ms, 3),
            budget_ms=round(budget_ms, 3),
            planning_ms=round(planning_ms, 3),
            total_planner_ms=round(total_ms, 3),
        )
        logger.info("tourism_planner %s", plan.observability())
        return plan


def build_tourism_plan(
    query: str,
    intent: IntentResult,
    knowledge: KnowledgeResult,
    *,
    request_id: str | None = None,
) -> TourismPlan:
    return TourismPlanner().plan(query, intent, knowledge, request_id=request_id)


def _dedupe_published(places: list[PlaceEvidence]) -> list[PlaceEvidence]:
    seen: set[str] = set()
    out: list[PlaceEvidence] = []
    for place in places:
        if not place.place_id or not place.is_published:
            continue
        if place.place_id in seen:
            continue
        seen.add(place.place_id)
        out.append(place)
    return out


def _plan_type(intent: IntentResult) -> str:
    if intent.intent == "BUDGET_TRIP":
        return "BUDGET_TRIP"
    if intent.intent == "NATURE":
        return "NATURE_CIRCUIT"
    if intent.intent == "CULTURE":
        return "CULTURE_CIRCUIT"
    if intent.intent in {"ITINERARY"} or intent.needs_planner:
        return "ITINERARY"
    if intent.intent in {"PLACE_SEARCH", "PLACE_DETAILS"}:
        return "PLACE_SELECTION"
    return "ITINERARY"


def _wanted_interests(intent: IntentResult) -> list[str]:
    wanted = [i.casefold() for i in intent.interests]
    if intent.intent == "NATURE" and "nature" not in wanted:
        wanted.append("nature")
    if intent.intent == "CULTURE" and "culture" not in wanted:
        wanted.append("culture")
    if intent.intent == "FOOD" and "food" not in wanted:
        wanted.append("food")
    return _unique(wanted)


def _select_places(
    scored: list[ScoredPlace],
    *,
    intent: IntentResult,
    duration_days: int,
) -> list[ScoredPlace]:
    if not scored:
        return []
    capacity = min(_MAX_SELECTED, max(duration_days * _MAX_PER_DAY, duration_days))
    wanted = _wanted_interests(intent)
    selected: list[ScoredPlace] = []
    selected_ids: set[str] = set()

    # Ensure at least one place per interest when available.
    for interest in wanted:
        for item in scored:
            if item.place.place_id in selected_ids:
                continue
            if interest in item.interests:
                selected.append(item)
                selected_ids.add(item.place.place_id)
                break

    for item in scored:
        if len(selected) >= capacity:
            break
        if item.place.place_id in selected_ids:
            continue
        # Skip hotels for pure nature/culture itineraries unless asked.
        if intent.intent in {"NATURE", "CULTURE"} and "hotel" in item.interests and not wanted:
            continue
        selected.append(item)
        selected_ids.add(item.place.place_id)

    # Budget trim: keep at least one place per interest; drop extras that don't fit.
    # If protected places alone exceed budget → keep them (OVER_BUDGET assessed later).
    if intent.budget_xaf is not None and selected:
        if all(s.place.estimated_cost_xaf is not None for s in selected):
            protected_ids: set[str] = set()
            for interest in wanted:
                for item in selected:
                    if interest in item.interests and item.place.place_id not in protected_ids:
                        protected_ids.add(item.place.place_id)
                        break
            kept = [s for s in selected if s.place.place_id in protected_ids]
            running = sum(int(s.place.estimated_cost_xaf or 0) for s in kept)
            for item in sorted(
                [s for s in selected if s.place.place_id not in protected_ids],
                key=lambda s: s.total,
                reverse=True,
            ):
                cost = int(item.place.estimated_cost_xaf or 0)
                if running + cost <= intent.budget_xaf:
                    kept.append(item)
                    running += cost
            if not kept:
                kept = selected[:1]
            selected = sorted(kept, key=lambda s: s.total, reverse=True)

    return selected[:capacity]


def _assign_days(
    selected: list[ScoredPlace],
    *,
    duration_days: int,
    intent: IntentResult,
) -> list[PlanDay]:
    if not selected:
        return [
            PlanDay(day=i, title=f"Jour {i}", places=[], notes=["Aucun lieu disponible."])
            for i in range(1, duration_days + 1)
        ]

    # Group by city (prefer), else region, else "Cameroun"
    groups: dict[str, list[ScoredPlace]] = defaultdict(list)
    for item in selected:
        key = (item.place.city or item.place.region or "Cameroun").strip()
        groups[key].append(item)

    # Sort groups: intent city first, then by size
    def group_key(name: str) -> tuple[int, int, str]:
        prefer = 0
        if intent.city and intent.city.casefold() in name.casefold():
            prefer = -1
        return (prefer, -len(groups[name]), name)

    group_names = sorted(groups.keys(), key=group_key)

    # Flatten into city-coherent buckets
    buckets: list[list[ScoredPlace]] = [[] for _ in range(duration_days)]
    day_idx = 0
    for gname in group_names:
        items = groups[gname]
        # Keep group together; spill to next days if too many
        for item in items:
            # Find a day that already has this city or the least loaded day
            preferred = None
            for i, bucket in enumerate(buckets):
                if bucket and (bucket[0].place.city or bucket[0].place.region or "") == (
                    item.place.city or item.place.region or ""
                ):
                    if len(bucket) < _MAX_PER_DAY:
                        preferred = i
                        break
            if preferred is None:
                # least loaded under cap
                candidates = [i for i, b in enumerate(buckets) if len(b) < _MAX_PER_DAY]
                preferred = min(candidates, key=lambda i: len(buckets[i])) if candidates else day_idx % duration_days
            buckets[preferred].append(item)
            day_idx += 1

    days: list[PlanDay] = []
    for i, bucket in enumerate(buckets, start=1):
        ordered_places = order_by_nearest([s.place for s in bucket])
        score_by_id = {s.place.place_id: s for s in bucket}
        items: list[PlanItem] = []
        prev: PlaceEvidence | None = None
        known_day_cost = 0
        unknown_day_cost = False
        duration_sum = 0.0
        has_duration = False
        for order, place in enumerate(ordered_places, start=1):
            dist = place_distance_km(prev, place) if prev else None
            scored = score_by_id.get(place.place_id)
            reason_parts = []
            if scored:
                reason_parts = [
                    f"{k}={v}" for k, v in scored.breakdown.items() if abs(v) > 0.001
                ]
            items.append(
                PlanItem(
                    place_id=place.place_id,
                    place_name=place.name,
                    order=order,
                    estimated_duration_hours=place.recommended_duration_hours,
                    estimated_cost_xaf=place.estimated_cost_xaf,
                    distance_from_previous_km=dist,
                    category=list(place.category),
                    eco_tags=list(place.eco_tags),
                    reason="; ".join(reason_parts) if reason_parts else None,
                    city=place.city,
                    region=place.region,
                    score_breakdown=dict(scored.breakdown) if scored else {},
                )
            )
            if place.estimated_cost_xaf is None:
                unknown_day_cost = True
            else:
                known_day_cost += int(place.estimated_cost_xaf)
            if place.recommended_duration_hours is not None:
                duration_sum += float(place.recommended_duration_hours)
                has_duration = True
            prev = place

        cities = [p.city for p in ordered_places if p.city]
        day_city = cities[0] if cities and all(c == cities[0] for c in cities) else (
            cities[0] if cities else None
        )
        notes: list[str] = []
        if any(it.distance_from_previous_km is not None for it in items):
            notes.append("Distances = distance géographique (pas routière).")
        if unknown_day_cost:
            notes.append("Coût journalier partiel : certains tarifs manquent.")

        days.append(
            PlanDay(
                day=i,
                title=f"Jour {i}" + (f" — {day_city}" if day_city else ""),
                city=day_city,
                places=items,
                estimated_day_cost_xaf=None if unknown_day_cost else (known_day_cost if items else 0),
                estimated_duration_hours=round(duration_sum, 2) if has_duration else None,
                notes=notes,
            )
        )
    return days


def _feasibility(
    *,
    selected: list[PlaceEvidence],
    duration_days: int,
    duration_missing: bool,
    budget_status: str,
    intent: IntentResult,
) -> str:
    if not selected:
        return "INSUFFICIENT_DATA"
    if budget_status == "OVER_BUDGET" and intent.budget_xaf is not None:
        # Still produced a plan but marked not feasible on budget
        return "NOT_FEASIBLE"
    if duration_missing or budget_status == "PARTIAL":
        return "PARTIAL"
    if len(selected) < duration_days and intent.needs_planner:
        return "PARTIAL"
    return "FEASIBLE"


def _confidence(
    *,
    selected: list[PlaceEvidence],
    knowledge: KnowledgeResult,
    intent: IntentResult,
    covered: list[str],
    wanted: list[str],
    budget_status: str,
    duration_missing: bool,
) -> float:
    if not selected:
        return 0.15
    base = 0.45 + 0.2 * min(1.0, knowledge.confidence)
    if wanted:
        base += 0.2 * (len(covered) / len(wanted))
    else:
        base += 0.1
    if budget_status == "WITHIN_BUDGET":
        base += 0.1
    elif budget_status == "OVER_BUDGET":
        base -= 0.15
    elif budget_status == "PARTIAL":
        base -= 0.05
    if duration_missing:
        base -= 0.08
    if intent.city and all(
        p.city and intent.city.casefold() in p.city.casefold() for p in selected
    ):
        base += 0.08
    return max(0.05, min(0.95, base))


def _empty_plan(
    *,
    plan_type: str,
    intent: IntentResult,
    missing: list[str],
    warnings: list[str],
    request_id: str,
    filtering_ms: float,
    total_ms: float,
    needs_web: bool,
) -> TourismPlan:
    duration = intent.duration_days if intent.duration_days and intent.duration_days > 0 else 0
    return TourismPlan(
        plan_type="EMPTY" if not intent.duration_days else plan_type,
        duration_days=duration,
        budget_xaf=intent.budget_xaf,
        budget_status="UNKNOWN",
        feasibility="INSUFFICIENT_DATA",
        days=[],
        selected_places=[],
        interests_covered=[],
        interests_not_covered=_wanted_interests(intent),
        constraints_applied=[],
        warnings=_unique(warnings),
        missing_information=_unique(missing),
        needs_web=needs_web,
        confidence=0.15,
        request_id=request_id,
        filtering_ms=round(filtering_ms, 3),
        scoring_ms=0.0,
        geo_ms=0.0,
        budget_ms=0.0,
        planning_ms=0.0,
        total_planner_ms=round(total_ms, 3),
    )


def _unique(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        if item and item not in out:
            out.append(item)
    return out
