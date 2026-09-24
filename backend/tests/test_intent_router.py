"""Mandatory Phase 2.1 Agent 1 — Intent & Router tests."""

from __future__ import annotations

import statistics
import time

from app.services.agents.intent import IntentResult, classify_intent
from app.services.agents.intent.bridge import dual_route_observe, intent_to_legacy_route
from app.services.agents.intent.matrix import ROUTING_MATRIX, apply_matrix


def test_simple_qa_capitale():
    result = classify_intent("Quelle est la capitale du Cameroun ?")
    assert result.intent == "SIMPLE_QA"
    assert result.needs_knowledge is True
    assert result.needs_places is False
    assert result.needs_planner is False
    assert result.city is None
    assert result.confidence >= 0.6


def test_place_search_yaounde():
    result = classify_intent("Que visiter à Yaoundé ?")
    assert result.intent == "PLACE_SEARCH"
    assert result.city == "Yaoundé"
    assert result.needs_places is True
    assert result.needs_knowledge is True


def test_itinerary_three_days_yaounde():
    result = classify_intent("Je viens à Yaoundé pendant 3 jours.")
    assert result.intent == "ITINERARY"
    assert result.city == "Yaoundé"
    assert result.duration_days == 3
    assert result.needs_planner is True
    assert result.needs_places is True


def test_budget_trip_family():
    result = classify_intent(
        "Nous sommes 4 avec 150000 FCFA pour 3 jours à Yaoundé."
    )
    assert result.intent in {"BUDGET_TRIP", "ITINERARY"}
    assert result.city == "Yaoundé"
    assert result.people == 4
    assert result.budget_xaf == 150000
    assert result.duration_days == 3
    assert result.needs_planner is True


def test_food_dishes():
    result = classify_intent("Quels plats camerounais dois-je goûter ?")
    assert result.intent == "FOOD"
    assert result.needs_knowledge is True
    assert result.city is None


def test_culture_sawa():
    result = classify_intent("Je veux découvrir la culture Sawa.")
    assert result.intent == "CULTURE"
    assert "culture" in result.interests
    assert result.needs_knowledge is True


def test_nature_activity():
    result = classify_intent("Propose-moi une activité nature au Cameroun.")
    assert result.intent == "NATURE"
    assert result.needs_places is True
    assert result.city is None  # must not invent a city


def test_place_details_mont_cameroun():
    result = classify_intent("Parle-moi du Mont Cameroun.")
    assert result.intent == "PLACE_DETAILS"
    assert result.needs_knowledge is True
    assert result.needs_places is True


def test_booking_hotel_yaounde():
    result = classify_intent("Je veux réserver un hôtel à Yaoundé.")
    assert result.intent == "BOOKING"
    assert result.city == "Yaoundé"
    assert result.needs_booking is True
    # Router must never claim booking is completed — only flag the need.
    assert result.needs_booking is True


def test_ambiguous_low_confidence_no_invention():
    result = classify_intent("Je veux quelque chose de bien au Cameroun.")
    assert result.confidence < 0.60
    assert result.city is None
    assert result.location in {None, "Cameroun"} or result.location is None
    # Must not invent a city/place for an ambiguous ask.
    assert result.city is None
    assert result.intent in {"CLARIFICATION", "TOURISM_INFO"}
    assert result.needs_planner is False


def test_does_not_invent_city_for_generic_cameroon():
    result = classify_intent("Que visiter au Cameroun ?")
    assert result.intent == "PLACE_SEARCH"
    assert result.city is None
    assert result.budget_xaf is None
    assert result.people is None


def test_routing_matrix_itinerary():
    caps = apply_matrix("ITINERARY", duration_days=3, city="Yaoundé")
    assert caps.needs_knowledge and caps.needs_places and caps.needs_planner


def test_routing_matrix_complete():
    required = {
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
    }
    assert required <= set(ROUTING_MATRIX.keys())


def test_intent_result_observability_has_no_user_text():
    result = classify_intent("Quelle est la capitale du Cameroun ?", request_id="abc123")
    payload = result.observability()
    blob = str(payload).lower()
    assert "capitale" not in blob
    assert payload["request_id"] == "abc123"
    assert "intent" in payload
    assert "router_latency_ms" in payload


def test_voice_mode_is_fast():
    samples: list[float] = []
    text = "Je viens à Yaoundé pendant 3 jours."
    # Warm once.
    classify_intent(text, mode="voice")
    for _ in range(50):
        t0 = time.perf_counter()
        result = classify_intent(text, mode="voice")
        samples.append((time.perf_counter() - t0) * 1000.0)
        assert result.intent == "ITINERARY"
    median = statistics.median(samples)
    # Rules path must stay far below voice budget (50ms soft limit).
    assert median < 20.0, f"voice router median too slow: {median:.2f}ms"
    assert result.router_latency_ms is not None
    assert result.router_latency_ms < 50.0


def test_legacy_bridge_does_not_raise():
    result = classify_intent("Bonjour")
    legacy = intent_to_legacy_route(result)
    assert legacy.kind in {"simple", "grounded"}
    dual = dual_route_observe("Que visiter à Douala ?")
    assert "legacy" in dual and "agent1" in dual


def test_intent_result_model_roundtrip():
    result = IntentResult(
        intent="SIMPLE_QA",
        needs_knowledge=True,
        confidence=0.9,
    )
    assert result.interests == []
    assert result.needs_booking is False
