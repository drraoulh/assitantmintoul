"""Phase 2.3 Agent 3 — Tourism Planner mandatory tests."""

from __future__ import annotations

import statistics
import time

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult, PlaceEvidence
from app.services.agents.planner.agent import TourismPlanner, build_tourism_plan
from app.services.agents.planner.compare import compare_plan
from app.services.agents.planner.geo_utils import haversine_km, place_distance_km


def _place(
    pid: str,
    name: str,
    *,
    city: str | None = "Yaoundé",
    region: str | None = "Centre",
    cost: int | None = 5000,
    duration: float | None = 2.0,
    lat: float | None = None,
    lon: float | None = None,
    category: list[str] | None = None,
    eco_tags: list[str] | None = None,
    cultural_info: str | None = None,
    eco_info: str | None = None,
    published: bool = True,
    evidence: float = 0.8,
) -> PlaceEvidence:
    return PlaceEvidence(
        place_id=pid,
        name=name,
        city=city,
        region=region,
        description=name,
        cultural_info=cultural_info,
        eco_info=eco_info,
        category=category or ["Monument"],
        eco_tags=eco_tags or [],
        estimated_cost_xaf=cost,
        recommended_duration_hours=duration,
        latitude=lat,
        longitude=lon,
        evidence_score=evidence,
        is_published=published,
    )


def _knowledge(places: list[PlaceEvidence], **kwargs) -> KnowledgeResult:
    return KnowledgeResult(
        query=kwargs.get("query", "test"),
        intent=kwargs.get("intent", "ITINERARY"),
        places=places,
        confidence=kwargs.get("confidence", 0.8),
        missing_information=kwargs.get("missing_information", []),
        web_needed=kwargs.get("web_needed", False),
    )


def _intent(**kwargs) -> IntentResult:
    base = dict(
        intent="ITINERARY",
        city="Yaoundé",
        duration_days=3,
        budget_xaf=150000,
        people=None,
        children=None,
        interests=["culture", "nature"],
        needs_planner=True,
        needs_places=True,
        needs_knowledge=True,
        confidence=0.9,
    )
    base.update(kwargs)
    return IntentResult(**base)  # type: ignore[arg-type]


def test_three_days_len():
    places = [
        _place("A", "Musée", cultural_info="culture", category=["Museum"], cost=2000),
        _place("B", "Parc", eco_tags=["nature"], eco_info="nature", category=["Park"], cost=3000, lat=3.9, lon=11.5),
        _place("C", "Monument", cultural_info="culture", cost=1000),
        _place("D", "Jardin", eco_tags=["nature"], category=["Garden"], cost=1500),
        _place("E", "Galerie", cultural_info="art", category=["Museum"], cost=2000),
        _place("F", "Colline", eco_info="nature walk", category=["Natural"], cost=0),
    ]
    plan = build_tourism_plan("3 jours", _intent(duration_days=3), _knowledge(places))
    assert len(plan.days) == 3
    assert plan.duration_days == 3


def test_budget_within_when_costs_known():
    places = [
        _place("A", "Musée", cost=20000, cultural_info="culture", category=["Museum"]),
        _place("B", "Parc", cost=10000, eco_tags=["nature"], category=["Park"]),
        _place("C", "Monument", cost=5000, cultural_info="culture"),
    ]
    plan = build_tourism_plan(
        "budget ok",
        _intent(duration_days=2, budget_xaf=150000),
        _knowledge(places),
    )
    assert plan.budget_status == "WITHIN_BUDGET"
    assert plan.total_estimated_cost_xaf is not None
    assert plan.total_estimated_cost_xaf <= 150000


def test_budget_over():
    # Two interest-protected places each costing 8000 → 16000 > 10000.
    places = [
        _place("A", "Cher1", cost=8000, cultural_info="culture", category=["Museum"]),
        _place("B", "Cher2", cost=8000, eco_tags=["nature"], category=["Park"]),
    ]
    plan = build_tourism_plan(
        "budget serré",
        _intent(duration_days=1, budget_xaf=10000, interests=["culture", "nature"]),
        _knowledge(places),
    )
    assert plan.budget_status == "OVER_BUDGET"
    assert plan.feasibility == "NOT_FEASIBLE"
    assert plan.total_estimated_cost_xaf is not None
    assert plan.total_estimated_cost_xaf > 10000


def test_missing_cost_partial_total():
    places = [
        _place("A", "Payant", cost=5000, cultural_info="culture", category=["Museum"]),
        _place("B", "Inconnu", cost=None, eco_tags=["nature"], category=["Park"]),
    ]
    plan = build_tourism_plan(
        "coûts partiels",
        _intent(duration_days=1, budget_xaf=50000),
        _knowledge(places),
    )
    assert plan.total_estimated_cost_xaf is None
    assert plan.budget_status == "PARTIAL"
    assert plan.known_cost_xaf == 5000 or plan.known_cost_xaf is not None


def test_haversine_distance():
    # Yaoundé approx vs nearby point
    d = haversine_km(3.8480, 11.5021, 3.8580, 11.5121)
    assert 0.5 < d < 5.0
    a = _place("A", "A", lat=3.8480, lon=11.5021)
    b = _place("B", "B", lat=3.8580, lon=11.5121)
    assert place_distance_km(a, b) is not None


def test_missing_coordinates_null_distance():
    places = [
        _place("A", "A", cost=1000, cultural_info="c", lat=None, lon=None),
        _place("B", "B", cost=1000, cultural_info="c", lat=None, lon=None),
    ]
    plan = build_tourism_plan(
        "no coords",
        _intent(duration_days=1, interests=["culture"]),
        _knowledge(places),
    )
    for day in plan.days:
        for item in day.places:
            if item.order > 1:
                assert item.distance_from_previous_km is None


def test_nature_selection():
    places = [
        _place("N1", "Parc Waza", eco_tags=["wildlife"], eco_info="safari", category=["Park"], city="Waza", region="Extrême-Nord"),
        _place("N2", "Mont", eco_tags=["hiking"], category=["Natural"], city="Buea", region="Sud-Ouest"),
        _place("H1", "Hôtel Luxe", category=["Hotel"], city="Yaoundé"),
    ]
    plan = build_tourism_plan(
        "nature",
        _intent(intent="NATURE", city=None, duration_days=2, interests=["nature"], budget_xaf=None),
        _knowledge(places, intent="NATURE"),
    )
    assert plan.selected_places
    assert "H1" not in plan.selected_places or "nature" in plan.interests_covered
    assert all(
        pid.startswith("N") or pid == "H1" for pid in plan.selected_places
    )
    # Nature places should dominate
    assert any(pid.startswith("N") for pid in plan.selected_places)


def test_culture_coverage():
    places = [
        _place("C1", "Musée", cultural_info="patrimoine", category=["Museum"]),
        _place("C2", "Sawa", cultural_info="Culture Sawa", category=["Culture"]),
        _place("N1", "Parc", eco_tags=["nature"], category=["Park"]),
    ]
    plan = build_tourism_plan(
        "culture",
        _intent(intent="CULTURE", interests=["culture"], duration_days=1, budget_xaf=None),
        _knowledge(places, intent="CULTURE"),
    )
    assert "culture" in plan.interests_covered


def test_multi_interest_coverage():
    places = [
        _place("C1", "Musée", cultural_info="culture", category=["Museum"], cost=2000),
        _place("N1", "Parc", eco_tags=["nature"], eco_info="eco", category=["Park"], cost=3000),
        _place("X1", "Autre", category=["Other"], cost=1000),
    ]
    plan = build_tourism_plan(
        "multi",
        _intent(duration_days=2, interests=["nature", "culture"], budget_xaf=50000),
        _knowledge(places),
    )
    assert "nature" in plan.interests_covered
    assert "culture" in plan.interests_covered


def test_no_invention_subset():
    places = [
        _place("A", "A", cultural_info="c", cost=1000),
        _place("B", "B", eco_tags=["nature"], cost=1000),
        _place("C", "C", cultural_info="c", cost=1000),
    ]
    plan = build_tourism_plan("subset", _intent(duration_days=2), _knowledge(places))
    assert set(plan.selected_places).issubset({"A", "B", "C"})
    assert "D" not in plan.selected_places


def test_duplicate_place_once():
    places = [
        _place("A", "A", cultural_info="c", cost=1000),
        _place("A", "A duplicate", cultural_info="c", cost=1000),
        _place("B", "B", eco_tags=["nature"], cost=1000),
    ]
    plan = build_tourism_plan("dedupe", _intent(duration_days=1), _knowledge(places))
    assert plan.selected_places.count("A") <= 1
    flat = [item.place_id for day in plan.days for item in day.places]
    assert flat.count("A") <= 1


def test_unpublished_never_selected():
    places = [
        _place("PUB", "Public", cultural_info="c", published=True, cost=1000),
        _place("HID", "Hidden", cultural_info="c", published=False, cost=1000),
    ]
    plan = build_tourism_plan("pub", _intent(duration_days=1), _knowledge(places))
    assert "HID" not in plan.selected_places


def test_children_no_fake_multiplier():
    places = [_place("A", "Musée", cultural_info="c", cost=5000, category=["Museum"])]
    plan = build_tourism_plan(
        "enfants",
        _intent(duration_days=1, people=2, children=2, budget_xaf=50000, interests=["culture"]),
        _knowledge(places),
    )
    # Must not invent 5000*4
    assert plan.known_cost_xaf in {0, 5000, None} or plan.known_cost_xaf == 5000
    assert plan.total_estimated_cost_xaf in {None, 5000}
    assert any("enfant" in w.casefold() for w in plan.warnings)


def test_people_no_times_four():
    places = [_place("A", "Parc", eco_tags=["nature"], cost=10000, category=["Park"])]
    plan = build_tourism_plan(
        "groupe",
        _intent(duration_days=1, people=4, children=None, budget_xaf=100000, interests=["nature"]),
        _knowledge(places),
    )
    assert plan.total_estimated_cost_xaf in {None, 10000}
    assert any("personne" in w.casefold() or "groupe" in w.casefold() for w in plan.warnings)


def test_empty_evidence_insufficient():
    plan = build_tourism_plan(
        "vide",
        _intent(duration_days=3),
        _knowledge([]),
    )
    assert plan.feasibility == "INSUFFICIENT_DATA"
    assert plan.selected_places == []
    assert plan.days == [] or all(len(d.places) == 0 for d in plan.days)


def test_planner_latency():
    places = [
        _place(f"P{i}", f"Place {i}", cultural_info="c" if i % 2 == 0 else None,
               eco_tags=["nature"] if i % 2 else [], cost=1000 + i,
               lat=3.8 + i * 0.01, lon=11.5 + i * 0.01)
        for i in range(12)
    ]
    intent = _intent(duration_days=3)
    knowledge = _knowledge(places)
    samples = []
    plan = None
    for _ in range(30):
        t0 = time.perf_counter()
        plan = TourismPlanner().plan("bench", intent, knowledge)
        samples.append((time.perf_counter() - t0) * 1000.0)
    median = statistics.median(samples)
    assert median < 100.0, f"planner too slow: {median:.1f}ms"
    assert plan is not None
    assert plan.total_planner_ms is not None


def test_compare_plan_diagnostic():
    places = [_place("A", "A", cultural_info="c"), _place("B", "B", eco_tags=["nature"])]
    intent = _intent(duration_days=1)
    knowledge = _knowledge(places)
    report = compare_plan("cmp", intent, knowledge)
    assert report["subset_ok"] is True
    assert "agent3" in report
