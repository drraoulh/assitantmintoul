"""End-to-end chat routing by real user intent (web-first chat).

Every case goes through ``POST /api/chat`` with the Agent Orchestrator on
(deterministic Agent 4, no LLM) and a recording web + image provider, so the
assertions check what the client really receives: routing, web sources,
images, place cards and map.
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import get_settings
from app.services.agents.intent.router import classify_intent
from app.services.ai.huggingface import HuggingFaceAIService
from app.services.conversation.memory import InMemoryConversationStore
from app.services.web_search.models import ImageSearchResult, WebSearchResult
from app.services.web_search.source_parser import parse_result
from app.services.web_search.web_search_service import WebSearchProvider, WebSearchService
from tests.conftest import client_with_ai


def _row(title: str, url: str, snippet: str) -> WebSearchResult:
    parsed = parse_result(title=title, url=url, snippet=snippet, provider="fake")
    assert parsed is not None
    return parsed


ROWS = [
    _row(
        "Voyager de Yaoundé à Buea",
        "https://voyage.example.cm/yaounde-buea",
        "Les bus des agences de voyage relient Yaoundé à Buea via Douala ; départs depuis Mvan.",
    ),
    _row(
        "Douala to Limbe by bus",
        "https://travel.example.com/douala-limbe",
        "Shared taxis and buses leave Douala for Limbe from the Mile 4 motor park, Cameroon.",
    ),
    _row(
        "Things to do in Buea",
        "https://guide.example.com/buea",
        "Hiking Mount Cameroon and visiting the Bismarck fountain are popular things to do in Buea, Cameroon.",
    ),
    _row(
        "Eru — Cameroonian dish",
        "https://food.example.com/eru",
        "Eru is a Cameroonian dish from the South-West region made with okazi leaves and waterleaf.",
    ),
    _row(
        "Where to eat eru in Buea",
        "https://resto.example.com/buea",
        "Mountain Restaurant in Buea serves eru and water fufu, Cameroon cuisine.",
    ),
    _row(
        "Plats du Centre Cameroun",
        "https://food.example.com/centre",
        "Le Nnam ngon et le Kpem sont des plats traditionnels de la région du Centre Cameroun (Yaoundé).",
    ),
]


FOUMBAN_ROWS = [
    _row(
        "Yaoundé à Foumban en bus",
        "https://www.rome2rio.com/fr/s/Yaoundé/Foumban",
        "Le meilleur moyen pour se rendre de Yaoundé à Foumban sans voiture est de bus et Taxi, "
        "ce qui dure 8 h 46 m et coûte $65 - $85.",
    ),
    _row(
        "Foumban à Cameroun",
        "https://www.rome2rio.com/fr/s/Foumban/Cameroun",
        "Il y a 3 façons d'aller de Foumban à Cameroun en taxi, bus ou automobile ; Le meilleur · 7h 57min.",
    ),
    _row(
        "Agence de voyage Yaoundé Foumban",
        "https://bus.example.cm/yaounde-foumban",
        "Les bus de Yaoundé pour Foumban partent de la gare routière de Mvan ; trajet d'environ 5 h 30, "
        "billet à 6 000 FCFA.",
    ),
    _row(
        "Douala Kribi bus",
        "https://travel.example.com/douala-kribi",
        "Buses from Douala to Kribi take about 3 hours, Cameroon.",
    ),
    _row(
        "Que faire à Foumban",
        "https://guide.example.com/foumban",
        "À Foumban, visitez le palais royal des sultans bamoun, le musée des rois et le village des artisans.",
    ),
    _row(
        "Restaurants à Foumban",
        "https://resto.example.com/foumban",
        "Le restaurant Le Bamoun à Foumban sert des plats locaux et des grillades.",
    ),
]


class RecordingProvider(WebSearchProvider):
    name = "fake"

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.image_queries: list[str] = []

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        self.queries.append(query)
        await asyncio.sleep(0)
        # Same pool for every query: validation/relevance must pick the on-topic rows.
        return [*ROWS, *FOUMBAN_ROWS]

    async def search_images(self, query: str, max_results: int = 6) -> list[ImageSearchResult]:
        self.image_queries.append(query)
        return [
            ImageSearchResult(
                image_url=f"https://img.example.com/{i}.jpg",
                page_url=f"https://img.example.com/page/{i}",
                title=f"{query} {i}",
                source_domain="img.example.com",
            )
            for i in range(3)
        ]


@pytest.fixture
def chat(monkeypatch):
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.setenv("AGENT_ORCHESTRATOR_USE_LLM", "false")
    monkeypatch.setenv("KNOWLEDGE_GEOGRAPHY_ENABLED", "true")
    get_settings.cache_clear()
    from app.services.agents.web_research.cache import cache_clear

    cache_clear()
    provider = RecordingProvider()
    service = HuggingFaceAIService(
        api_token="test-token",
        conversation_store=InMemoryConversationStore(),
        web_search_service=WebSearchService(provider),
    )
    client = client_with_ai(service)

    def send(message: str, conversation_id: str | None = None) -> dict:
        provider.queries.clear()
        provider.image_queries.clear()
        body = {"message": message, "locale": "fr"}
        if conversation_id:
            body["conversation_id"] = conversation_id
        response = client.post("/api/chat", json=body)
        assert response.status_code == 200, response.text
        return response.json()

    send.provider = provider  # type: ignore[attr-defined]
    yield send
    get_settings.cache_clear()


def _web_sources(data: dict) -> list[dict]:
    return [s for s in data["ui_sources"] if s["type"] == "WEB"]


def _place_cities(data: dict) -> set[str]:
    return {p["city"] for p in data["places"]}


def test_1_greeting_has_no_places_and_no_web(chat):
    data = chat("Bonjour")
    assert data["routing"]["chat_intent"] == "GREETING"
    assert data["places"] == [] and data["map"] is None
    assert chat.provider.queries == []


def test_2_see_eru_is_gastronomy_with_images_and_no_places(chat):
    data = chat("Je veux voir le Eru")
    routing = data["routing"]
    assert routing["chat_intent"] == "GASTRONOMY"
    assert routing["dish"] == "Eru" and routing["wants_images"] is True
    assert chat.provider.queries and all("Eru" in q for q in chat.provider.queries)
    assert chat.provider.image_queries == ["Eru plat camerounais"]
    assert len(data["images"]) == 3 and data["images"][0]["image_url"].startswith("https://")
    assert _web_sources(data)
    assert "okazi" in data["message"]
    assert data["places"] == [] and data["map"] is None and data["hotels"] == []


def test_3_south_west_dish_uses_web(chat):
    data = chat("Plat traditionnel du Sud-Ouest")
    assert data["routing"]["chat_intent"] == "GASTRONOMY"
    assert chat.provider.queries and all("Sud-Ouest" in q or "South-West" in q for q in chat.provider.queries)
    assert _web_sources(data)
    assert "sources web" in data["message"]
    assert data["places"] == [] and data["map"] is None


def test_4_centre_follow_up_replaces_south_west(chat):
    first = chat("Plat traditionnel du Sud-Ouest")
    data = chat("Et le plat traditionnel du Centre ?", first["conversation_id"])
    assert data["routing"]["chat_intent"] == "GASTRONOMY"
    assert data["routing"]["location"] in {"Centre", None}
    assert all("Sud-Ouest" not in q and "South-West" not in q for q in chat.provider.queries)
    assert any("Centre" in q for q in chat.provider.queries)
    assert "Nnam ngon" in data["message"]
    assert data["places"] == [] and data["map"] is None


def test_5_leave_yaounde_for_buea_is_a_route(chat):
    data = chat("Je veux quitter Yaoundé pour arriver à Buea, que faire ?")
    routing = data["routing"]
    assert routing["chat_intent"] == "TRAVEL_ROUTE"
    assert routing["origin"] == "Yaoundé" and routing["destination"] == "Buea"
    assert data["web_research"]["decision"] == "forced:FORCED_TRAVEL_ROUTE"
    queries = chat.provider.queries
    assert any("transport" in q.casefold() for q in queries)
    assert any("que faire à Buea" in q for q in queries)
    assert _web_sources(data)
    assert "Mvan" in data["message"]
    assert "Yaoundé" not in _place_cities(data)
    assert _place_cities(data) <= {"Buea"}
    marker_titles = [m["title"] for m in data["map"]["markers"]]
    assert marker_titles[:2] == ["Yaoundé", "Buea"]


def test_6_douala_to_limbe_is_a_route_without_douala_places(chat):
    data = chat("Comment aller de Douala à Limbé ?")
    routing = data["routing"]
    assert routing["chat_intent"] == "TRAVEL_ROUTE"
    assert routing["origin"] == "Douala" and routing["destination"] == "Limbé"
    assert chat.provider.queries and _web_sources(data)
    assert "Mile 4" in data["message"]
    assert data["places"] == []


def test_7_what_to_visit_in_buea_lists_buea_places(chat):
    data = chat("Que visiter à Buea ?")
    assert data["routing"]["chat_intent"] == "PLACE_SEARCH"
    assert data["routing"]["location"] == "Buea"
    assert data["places"] and _place_cities(data) == {"Buea"}
    assert data["web_research"]["decision"] == "web_first"
    assert _web_sources(data)


def test_8_where_to_eat_eru_in_buea_is_restaurant_search(chat):
    data = chat("Où manger du Eru à Buea ?")
    routing = data["routing"]
    assert routing["chat_intent"] == "RESTAURANT_SEARCH"
    assert routing["location"] == "Buea" and routing["dish"] == "Eru"
    assert any("restaurant" in q.casefold() for q in chat.provider.queries)
    assert "Mountain Restaurant" in data["message"]
    # Only restaurant leads: the dish description is not listed as a restaurant.
    assert "okazi" not in data["message"]
    assert data["places"] == [] and data["map"] is None


def test_9_photos_of_kribi_calls_image_search(chat):
    data = chat("Montre-moi des photos de Kribi")
    assert data["routing"]["chat_intent"] == "IMAGE_SEARCH"
    assert chat.provider.image_queries == ["Kribi Cameroun"]
    assert len(data["images"]) == 3
    assert data["response_type"] == "IMAGES"
    assert data["places"] == [] and data["map"] is None


def test_10_three_day_trip_is_itinerary_with_route(chat):
    data = chat("Je vais de Yaoundé à Buea pendant 3 jours")
    routing = data["routing"]
    assert routing["chat_intent"] == "ITINERARY"
    assert routing["origin"] == "Yaoundé" and routing["destination"] == "Buea"
    assert routing["duration_days"] == 3
    assert any("transport" in q.casefold() for q in chat.provider.queries)
    assert _web_sources(data)
    assert data["itinerary"] and data["itinerary"]["days"]
    assert _place_cities(data) <= {"Buea"}
    assert "ALLER DE YAOUNDÉ À BUEA" in data["message"]


def test_images_disabled_by_flag(chat, monkeypatch):
    monkeypatch.setenv("CHAT_IMAGE_SEARCH_ENABLED", "false")
    get_settings.cache_clear()
    data = chat("Montre-moi des photos de Kribi")
    assert chat.provider.image_queries == [] and data["images"] == []
    assert "pas trouvé de photos" in data["message"]


@pytest.mark.parametrize(
    ("message", "intent", "origin", "destination"),
    [
        ("Je suis à Yaoundé, que puis-je visiter ?", "PLACE_SEARCH", None, None),
        ("How do I get from Douala to Kribi?", "TRAVEL_ROUTE", "Douala", "Kribi"),
        ("Quelle distance entre Douala et Kribi ?", "TRAVEL_ROUTE", "Douala", "Kribi"),
        ("Je pars de Bafoussam vers Dschang demain", "TRAVEL_ROUTE", "Bafoussam", "Dschang"),
        ("Yaoundé - Kribi en bus, combien de temps ?", "TRAVEL_ROUTE", "Yaoundé", "Kribi"),
    ],
)
def test_route_extraction(message, intent, origin, destination):
    result = classify_intent(message, locale="fr")
    assert result.intent == intent
    assert result.origin == origin
    assert result.destination == destination
    if destination:
        assert result.city == destination


def test_city_mention_alone_does_not_trigger_place_search():
    result = classify_intent("Je veux quitter Yaoundé pour arriver à Buea", locale="fr")
    assert result.intent == "TRAVEL_ROUTE" and result.city == "Buea"


# --- Trajet + destination contextualisation (Yaoundé → Foumban) ---------------


def test_s1_go_to_foumban_from_yaounde_what_to_do(chat):
    data = chat("Je veux aller à Foumban, je suis à Yaoundé, que faire ?")
    routing = data["routing"]
    assert routing["chat_intent"] == "TRAVEL_ROUTE"
    assert routing["origin"] == "Yaoundé" and routing["destination"] == "Foumban"
    web = data["web_research"]
    assert web["transport_queries"] == [
        "Yaoundé Foumban transport bus Cameroon",
        "Yaoundé Foumban agence de voyage bus",
        "Yaoundé Foumban prix transport durée",
    ]
    assert web["destination_queries"] == ["que faire à Foumban Cameroun", "lieux touristiques Foumban Cameroun"]
    assert "Foumban Cameroun" not in chat.provider.queries
    assert web["web_results_count"] > 0
    message = data["message"]
    assert "🚍 ALLER DE YAOUNDÉ À FOUMBAN" in message
    assert "⚠️ Informations à confirmer" in message
    assert "🏛️ QUE FAIRE À FOUMBAN" in message
    # Map and sources are UI blocks (`map`, `ui_sources`), not repeated in the text.
    assert "TRAJET" not in message and "SOURCES" not in message
    assert {s["url"] for s in _web_sources(data)} >= {"https://guide.example.com/foumban"}
    # Off-route pages are not presented as the Yaoundé → Foumban journey.
    assert "Foumban à Cameroun" not in message and "Douala" not in message
    # Divergent durations are shown as a range, foreign fares keep their currency.
    assert "entre environ 5 h 30 et 8 h 46" in message
    assert "environ 65–85 USD" in message and "6 000 FCFA" in message
    assert "Mvan" in message
    assert "palais royal" in message
    assert _place_cities(data) == {"Foumban"}
    assert "Yaoundé" not in _place_cities(data)
    assert [m["title"] for m in data["map"]["markers"]][:2] == ["Yaoundé", "Foumban"]


def test_s2_how_to_go_from_yaounde_to_foumban(chat):
    data = chat("Comment aller de Yaoundé à Foumban ?")
    routing = data["routing"]
    assert routing["chat_intent"] == "TRAVEL_ROUTE"
    assert routing["origin"] == "Yaoundé" and routing["destination"] == "Foumban"
    assert data["web_research"]["destination_queries"] == []
    assert "Yaoundé" not in _place_cities(data)
    assert "QUE FAIRE" not in data["message"]


def test_s3_what_to_do_in_foumban_is_place_search(chat):
    data = chat("Que faire à Foumban ?")
    assert data["routing"]["chat_intent"] == "PLACE_SEARCH"
    assert data["routing"]["location"] == "Foumban"
    assert data["places"] and _place_cities(data) == {"Foumban"}


def test_s4_in_yaounde_what_to_visit_is_place_search(chat):
    data = chat("Je suis à Yaoundé, que visiter ?")
    assert data["routing"]["chat_intent"] == "PLACE_SEARCH"
    assert data["routing"]["location"] == "Yaoundé"
    assert data["places"] and _place_cities(data) == {"Yaoundé"}


def test_s5_on_site_follow_up_targets_destination(chat):
    first = chat("Je vais à Foumban")
    data = chat("Et sur place ?", first["conversation_id"])
    assert data["routing"]["chat_intent"] == "PLACE_SEARCH"
    assert data["routing"]["location"] == "Foumban"
    assert data["places"] and _place_cities(data) == {"Foumban"}


def test_s6_hotels_follow_up_targets_destination(chat):
    first = chat("Je vais à Foumban")
    data = chat("Et les hôtels ?", first["conversation_id"])
    assert data["routing"]["chat_intent"] == "HOTEL_SEARCH"
    assert data["routing"]["location"] == "Foumban"
    assert any("Foumban" in q for q in chat.provider.queries)


def test_s7_want_to_see_foumban_is_image_search(chat):
    data = chat("Je veux voir Foumban")
    assert data["routing"]["chat_intent"] == "IMAGE_SEARCH"
    assert data["routing"]["wants_images"] is True
    assert chat.provider.image_queries == ["Foumban Cameroun"]
    assert len(data["images"]) == 3
    assert all(img["page_url"].startswith("https://") for img in data["images"])


def test_s7b_want_to_see_the_palace_searches_the_palace(chat):
    data = chat("Je veux voir le palais de Foumban")
    assert data["routing"]["chat_intent"] == "IMAGE_SEARCH"
    assert chat.provider.image_queries == ["palais de Foumban Cameroun"]


def test_s8_where_to_eat_in_foumban_is_restaurant_search(chat):
    data = chat("Où manger à Foumban ?")
    routing = data["routing"]
    assert routing["chat_intent"] == "RESTAURANT_SEARCH"
    assert routing["location"] == "Foumban"
    assert chat.provider.queries and _web_sources(data)
    assert "Le Bamoun" in data["message"]


def test_return_trip_follow_up_reverses_the_route(chat):
    first = chat("Je veux aller à Foumban")
    data = chat("Et comment retourner à Yaoundé ?", first["conversation_id"])
    routing = data["routing"]
    assert routing["chat_intent"] == "TRAVEL_ROUTE"
    assert routing["origin"] == "Foumban" and routing["destination"] == "Yaoundé"
    assert data["web_research"]["transport_queries"][0] == "Foumban Yaoundé transport bus Cameroon"
    assert "ALLER DE FOUMBAN À YAOUNDÉ" in data["message"]


def test_restaurants_follow_up_targets_destination(chat):
    first = chat("Je veux aller à Foumban")
    data = chat("Et les restaurants ?", first["conversation_id"])
    assert data["routing"]["chat_intent"] == "RESTAURANT_SEARCH"
    assert data["routing"]["location"] == "Foumban"


def test_visit_origin_before_leaving_is_explicit(chat):
    first = chat("Je veux aller à Foumban, je suis à Yaoundé.")
    data = chat("Que visiter à Yaoundé avant de partir ?", first["conversation_id"])
    assert data["routing"]["chat_intent"] == "PLACE_SEARCH"
    assert data["routing"]["location"] == "Yaoundé"
