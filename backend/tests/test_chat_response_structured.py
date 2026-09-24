"""Phase 3.1 — structured ChatResponse UI builder tests."""

from __future__ import annotations

import time

from app.schemas.chat import ChatResponse
from app.services.agents.knowledge.models import (
    KnowledgeResult,
    PlaceEvidence,
    SourceEvidence,
)
from app.services.agents.planner.models import PlanDay, PlanItem, TourismPlan
from app.services.agents.response.models import FinalResponse, SourceReference
from app.services.agents.response.structured_ui import build_structured_ui


def _place(
    pid: str,
    name: str,
    *,
    lat: float | None = 5.47,
    lon: float | None = 10.42,
    cost: int | None = None,
    category: str = "nature",
    city: str = "Bafoussam",
    region: str = "Ouest",
) -> PlaceEvidence:
    return PlaceEvidence(
        place_id=pid,
        name=name,
        city=city,
        region=region,
        description=f"Description vérifiée de {name}",
        category=[category],
        estimated_cost_xaf=cost,
        latitude=lat,
        longitude=lon,
        source_ids=["src-1"],
        evidence_score=0.9,
    )


def _knowledge(places: list[PlaceEvidence], intent: str = "PLACE_SEARCH") -> KnowledgeResult:
    return KnowledgeResult(
        query="test",
        intent=intent,
        places=places,
        sources=[
            SourceEvidence(
                source_id="src-1",
                name="Catalogue SmartMboa",
                url=None,
                source_type="KB",
            )
        ],
        confidence=0.8,
        source="structured",
        verified_places_count=len(places),
        knowledge_completeness="HIGH",
    )


def test_chat_response_place_list():
    knowledge = _knowledge(
        [
            _place("p1", "Chefferie de Bandjoun"),
            _place("p2", "Chutes de la Métché", lat=5.6, lon=10.3),
            _place("p3", "Musée des Civilisations", lat=None, lon=None),
        ]
    )
    final = FinalResponse(
        text="Voici des lieux autour de Bafoussam.",
        response_type="PLACE_LIST",
        language="fr",
        sources=[SourceReference(source_id="src-1", name="Catalogue")],
    )
    ui = build_structured_ui(final=final, knowledge=knowledge, language="fr")
    assert ui["response_type"] == "PLACE_LIST"
    assert len(ui["places"]) == 3
    assert ui["map"] is not None
    assert len(ui["map"].markers) == 2  # only places with coords
    assert ui["places"][2].latitude is None
    assert ui["structured_build_ms"] is not None
    assert ui["structured_build_ms"] < 50.0


def test_chat_response_place_details():
    knowledge = _knowledge([_place("p1", "Chefferie de Bandjoun")], intent="PLACE_DETAILS")
    final = FinalResponse(
        text="Détail du lieu.",
        response_type="PLACE_DETAILS",
        language="fr",
    )
    ui = build_structured_ui(final=final, knowledge=knowledge)
    assert ui["response_type"] == "PLACE_DETAILS"
    assert len(ui["places"]) == 1
    assert ui["places"][0].name == "Chefferie de Bandjoun"


def test_chat_response_itinerary():
    places = [
        _place("p1", "Lieu A", cost=5000),
        _place("p2", "Lieu B", cost=8000, lat=5.5, lon=10.5),
    ]
    knowledge = _knowledge(places, intent="ITINERARY")
    plan = TourismPlan(
        plan_type="ITINERARY",
        duration_days=3,
        budget_xaf=150_000,
        known_cost_xaf=13_000,
        budget_status="WITHIN_BUDGET",
        feasibility="FEASIBLE",
        selected_places=["p1", "p2"],
        days=[
            PlanDay(
                day=1,
                title="Jour 1",
                places=[
                    PlanItem(
                        place_id="p1",
                        place_name="Lieu A",
                        order=1,
                        estimated_duration_hours=2.0,
                        estimated_cost_xaf=5000,
                    )
                ],
            ),
            PlanDay(
                day=2,
                title="Jour 2",
                places=[
                    PlanItem(
                        place_id="p2",
                        place_name="Lieu B",
                        order=1,
                        estimated_duration_hours=None,
                        estimated_cost_xaf=8000,
                    )
                ],
            ),
        ],
    )
    final = FinalResponse(text="Itinéraire 3 jours.", response_type="ITINERARY")
    ui = build_structured_ui(final=final, knowledge=knowledge, plan=plan)
    assert ui["response_type"] == "ITINERARY"
    assert ui["itinerary"] is not None
    assert len(ui["itinerary"].days) == 2
    assert ui["itinerary"].days[0].items[0].time is None  # never invent
    assert ui["itinerary"].days[0].items[0].duration_minutes == 120
    assert ui["itinerary"].days[1].items[0].duration_minutes is None
    assert ui["budget"] is not None
    assert ui["map"] is not None


def test_chat_response_budget():
    plan = TourismPlan(
        plan_type="BUDGET_TRIP",
        duration_days=2,
        budget_xaf=100_000,
        known_cost_xaf=40_000,
        feasibility="PARTIAL",
        days=[],
        selected_places=[],
    )
    ui = build_structured_ui(
        final=FinalResponse(text="Budget.", response_type="BUDGET_TRIP"),
        plan=plan,
    )
    assert ui["budget"] is not None
    assert ui["budget"].total_known == 40_000
    statuses = {i.label: i.status for i in ui["budget"].items}
    assert "UNKNOWN" in statuses.values()
    transport = next(i for i in ui["budget"].items if "Transport" in i.label or "transport" in i.label.lower() or i.label == "Transport")
    assert transport.amount is None
    assert transport.status == "UNKNOWN"


def test_chat_response_hotel():
    knowledge = _knowledge(
        [
            _place(
                "h1",
                "Ayila'a Hotel",
                category="hotel",
                cost=25_000,
                lat=5.47,
                lon=10.42,
            )
        ],
        intent="HOTEL",
    )
    final = FinalResponse(text="Hôtel vérifié.", response_type="HOTEL")
    ui = build_structured_ui(final=final, knowledge=knowledge)
    assert ui["response_type"] == "HOTEL"
    assert len(ui["hotels"]) >= 1
    hotel = ui["hotels"][0]
    assert hotel.booking_available is False
    assert hotel.demo_booking is True
    assert hotel.price_status == "INDICATIVE"


def test_chat_response_sources():
    knowledge = _knowledge([_place("p1", "Lieu")])
    knowledge.sources.append(
        SourceEvidence(
            source_id="web-1",
            name="Article",
            url="https://example.org/page",
            source_type="WEB",
        )
    )
    final = FinalResponse(
        text="Infos.",
        response_type="TOURISM_INFORMATION",
        sources=[
            SourceReference(source_id="web-1", name="Article", url="https://example.org/page")
        ],
    )
    ui = build_structured_ui(final=final, knowledge=knowledge)
    assert any(s.url == "https://example.org/page" for s in ui["ui_sources"])
    assert any(s.type == "WEB" for s in ui["ui_sources"])
    # Never invent URLs
    assert all(s.url is None or s.url.startswith("http") for s in ui["ui_sources"])


def test_chat_response_grounding_no_invention():
    knowledge = _knowledge(
        [_place("p1", "Lieu", lat=None, lon=None, cost=None)],
        intent="PLACE_SEARCH",
    )
    ui = build_structured_ui(
        final=FinalResponse(text="x", response_type="PLACE_LIST"),
        knowledge=knowledge,
    )
    assert ui["map"] is None
    assert ui["places"][0].estimated_cost_xaf is None
    assert ui["places"][0].latitude is None


def test_chat_response_missing_coordinates():
    knowledge = _knowledge(
        [
            _place("p1", "Sans coords", lat=None, lon=None),
            _place("p2", "Avec coords", lat=5.1, lon=10.1),
        ]
    )
    ui = build_structured_ui(
        final=FinalResponse(text="x", response_type="PLACE_LIST"),
        knowledge=knowledge,
    )
    assert ui["map"] is not None
    assert len(ui["map"].markers) == 1
    assert ui["map"].markers[0].place_id == "p2"


def test_chat_response_missing_price():
    knowledge = _knowledge([_place("p1", "Lieu", cost=None)], intent="HOTEL")
    ui = build_structured_ui(
        final=FinalResponse(text="x", response_type="HOTEL"),
        knowledge=knowledge,
    )
    if ui["hotels"]:
        assert ui["hotels"][0].price is None
        assert ui["hotels"][0].price_status == "UNKNOWN"


def test_chat_response_schema_backwards_compatible():
    """Expo clients that only read message/sources keep working."""
    resp = ChatResponse(
        conversation_id="c1",
        message="Bonjour",
        provider="huggingface",
        sources=[],
    )
    data = resp.model_dump()
    assert data["message"] == "Bonjour"
    assert data["text"] == "Bonjour"
    assert data["places"] == []
    assert data["map"] is None
    assert data["response_type"] is None


def test_chat_response_structured_payload_overhead():
    places = [_place(f"p{i}", f"Lieu {i}", lat=5.0 + i * 0.01, lon=10.0 + i * 0.01) for i in range(12)]
    knowledge = _knowledge(places)
    plan = TourismPlan(
        plan_type="ITINERARY",
        duration_days=3,
        budget_xaf=150_000,
        known_cost_xaf=20_000,
        days=[
            PlanDay(
                day=1,
                title="J1",
                places=[
                    PlanItem(place_id=p.place_id, place_name=p.name, order=i + 1)
                    for i, p in enumerate(places[:4])
                ],
            )
        ],
        selected_places=[p.place_id for p in places[:4]],
        feasibility="FEASIBLE",
    )
    final = FinalResponse(text="Trip", response_type="ITINERARY")
    t0 = time.perf_counter()
    for _ in range(20):
        ui = build_structured_ui(final=final, knowledge=knowledge, plan=plan)
    avg_ms = ((time.perf_counter() - t0) / 20.0) * 1000.0
    assert ui["structured_build_ms"] < 50.0
    assert avg_ms < 50.0
