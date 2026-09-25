"""Origin → destination web queries, source selection and transport facts."""

from __future__ import annotations

from app.services.agents.intent.router import classify_intent
from app.services.agents.web_research.models import WebEvidence
from app.services.agents.web_research.query_builder import build_image_query, route_query_phases
from app.services.agents.web_research.route import (
    extract_transport_facts,
    route_direction,
    select_destination,
    select_transport,
)


def _ev(title: str, snippet: str, url: str = "https://example.com/x") -> WebEvidence:
    return WebEvidence(title=title, snippet=snippet, url=url, domain="example.com")


def test_route_queries_name_the_pair_and_split_phases():
    intent = classify_intent("Je veux aller à Foumban, je suis à Yaoundé, que faire ?", locale="fr")
    transport, destination = route_query_phases(intent)
    assert transport == [
        "Yaoundé Foumban transport bus Cameroon",
        "Yaoundé Foumban agence de voyage bus",
        "Yaoundé Foumban prix transport durée",
    ]
    assert destination == ["que faire à Foumban Cameroun", "lieux touristiques Foumban Cameroun"]
    assert all("Yaoundé" in q for q in transport)
    assert all("transport" not in q and "Yaoundé" not in q for q in destination)


def test_pure_route_question_has_no_destination_phase():
    intent = classify_intent("Comment aller de Yaoundé à Foumban ?", locale="fr")
    _, destination = route_query_phases(intent)
    assert destination == []


def test_route_direction():
    assert route_direction(_ev("x", "Bus de Yaoundé à Foumban, 5 h"), "Yaoundé", "Foumban") == "direct"
    assert route_direction(_ev("x", "From Foumban to Yaounde by bus"), "Yaoundé", "Foumban") == "reverse"
    assert route_direction(_ev("x", "3 façons d'aller de Foumban à Cameroun"), "Yaoundé", "Foumban") is None
    assert route_direction(_ev("x", "Buses from Douala to Kribi"), "Yaoundé", "Foumban") is None


def test_select_transport_drops_off_route_and_prefers_direct():
    items = [
        _ev("Foumban à Cameroun", "Il y a 3 façons d'aller de Foumban à Cameroun", "https://a.com/1"),
        _ev("Retour", "Bus de Foumban à Yaoundé tous les matins", "https://a.com/2"),
        _ev("Aller", "Bus de Yaoundé à Foumban : 5 h 30, 6 000 FCFA", "https://a.com/3"),
    ]
    kept = select_transport(items, "Yaoundé", "Foumban")
    assert [e.url for e in kept] == ["https://a.com/3", "https://a.com/2"]
    assert [e.route_match for e in kept] == ["direct", "reverse"]
    assert all(e.phase == "transport" for e in kept)


def test_select_destination_requires_destination_and_skips_route_pages():
    items = [
        _ev("Que faire à Foumban", "Visitez le palais royal de Foumban", "https://a.com/1"),
        _ev("Comment aller à Foumban", "Comment aller à Foumban en bus", "https://a.com/2"),
        _ev("Yaoundé", "Musée national de Yaoundé", "https://a.com/3"),
    ]
    kept = select_destination(items, "Foumban")
    assert [e.url for e in kept] == ["https://a.com/1"]


def test_transport_facts_keep_source_currency_and_ranges():
    facts = extract_transport_facts(
        [
            ("Le meilleur moyen est le bus et taxi, ce qui dure 8 h 46 m et coûte $65 - $85.", "rome2rio.com"),
            ("Trajet d'environ 5 h 30, billet à 6 000 FCFA ; départs de la gare routière de Mvan.", "bus.cm"),
            ("There is no direct connection from Yaoundé to Foumban.", "rome2rio.com"),
            ("Vol Yaoundé Foumban en 1 h", "air.com"),
            ("Distance 268 km, cheapest fares from $14.", "fromto.travel"),
        ]
    )
    assert ("14", "USD", "fromto.travel", True) in facts.prices
    assert sorted(m for m, _ in facts.durations) == [330, 526]
    assert ("65–85", "USD", "rome2rio.com", False) in facts.prices
    assert ("6 000", "FCFA", "bus.cm", False) in facts.prices
    assert any("no direct connection" in c for c, _ in facts.connections)
    assert any("Mvan" in d for d, _ in facts.departures)
    assert {"bus", "taxi", "avion"} <= set(facts.modes)


def test_image_query_uses_the_requested_subject():
    intent = classify_intent("Je veux voir le palais de Foumban", locale="fr")
    assert intent.intent == "IMAGE_SEARCH"
    assert build_image_query(intent) == "palais de Foumban Cameroun"
    assert build_image_query(classify_intent("Montre-moi Foumban", locale="fr")) == "Foumban Cameroun"
