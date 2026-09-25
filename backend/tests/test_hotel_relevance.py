"""Hotel answers only carry hotel evidence — no generic culture / etiquette blocks."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.agents.intent.router import classify_intent
from app.services.agents.knowledge.culture_packs import _intent_flags
from app.services.agents.knowledge.models import KnowledgeEvidence, PlaceEvidence
from app.services.agents.knowledge.place_store import fold
from app.services.agents.knowledge.relevance import (
    filter_knowledge_for_intent,
    filter_places_for_intent,
)
from app.services.agents.orchestrator.orchestrator import AgentOrchestrator
from app.services.agents.web_research.cache import cache_clear
from tests.test_general_facts import FakeProvider
from app.services.web_search.web_search_service import WebSearchService

SAVOIR_VIVRE = KnowledgeEvidence(
    chunk_id="doc:food_culture:3",
    title="Culture et savoir-vivre",
    content="## Culture et savoir-vivre\n- Saluer et prendre le temps d'échanger est apprécié.",
    source_id="documents/food_culture.md",
)
HOTEL_SITE = KnowledgeEvidence(
    chunk_id="site:hotel-du-phare-kribi",
    title="Hôtel Du Phare",
    content="Site: Hôtel Du Phare Ville: Kribi Région: Sud Catégorie: hotel FR: Hôtel face à la mer.",
    source_id="tourist_sites/sud_complete.json",
    city="Kribi",
)
MUSEUM_SITE = KnowledgeEvidence(
    chunk_id="site:musee-maritime",
    title="Musée Maritime De Douala",
    content="Site: Musée Maritime Ville: Douala Région: Littoral Catégorie: museum FR: Musée.",
    source_id="tourist_sites/littoral_complete.json",
)


@pytest.fixture(autouse=True)
def _geo_on(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_GEOGRAPHY_ENABLED", "true")
    get_settings.cache_clear()
    cache_clear()
    yield
    cache_clear()
    get_settings.cache_clear()


def test_hotel_intent_drops_etiquette_and_museum_chunks() -> None:
    intent = classify_intent("Quels hôtels à Kribi ?", locale="fr")
    kept = filter_knowledge_for_intent(intent, [SAVOIR_VIVRE, MUSEUM_SITE, HOTEL_SITE])
    assert [k.chunk_id for k in kept] == ["site:hotel-du-phare-kribi"]


def test_hotel_intent_drops_hotels_from_another_city() -> None:
    intent = classify_intent("Un hôtel à Foumban ?", locale="fr")
    assert filter_knowledge_for_intent(intent, [HOTEL_SITE]) == []


def test_other_intents_keep_culture_chunks() -> None:
    intent = classify_intent("Parle-moi de la culture Sawa", locale="fr")
    assert filter_knowledge_for_intent(intent, [SAVOIR_VIVRE]) == [SAVOIR_VIVRE]


def test_hotel_places_are_hotels_only() -> None:
    intent = classify_intent("Quels hôtels à Douala ?", locale="fr")
    places = [
        PlaceEvidence(place_id="m", name="Musée Maritime De Douala", category=["museum"]),
        PlaceEvidence(place_id="a", name="Quartier Akwa", category=["district"]),
        PlaceEvidence(place_id="k", name="Krystal Palace Douala", category=["hotel"]),
    ]
    assert [p.place_id for p in filter_places_for_intent(intent, places)] == ["k"]


@pytest.mark.parametrize(
    ("query", "flag"),
    [
        ("un hotel bien place a kribi", "nature"),
        ("un hotel facile d'acces a douala", "nature"),
        ("un hotel a kribi pour visiter", "broad"),
    ],
)
def test_culture_pack_flags_need_whole_words(query: str, flag: str) -> None:
    flags = _intent_flags(fold(query))
    assert flags["hotel"] and not flags[flag]


@pytest.mark.parametrize(
    "query",
    ["Quels hôtels à Douala ?", "Où dormir à Yaoundé pour visiter ?", "Un hôtel bien placé à Kribi"],
)
@pytest.mark.asyncio
async def test_hotel_answer_has_no_culture_block(query: str) -> None:
    orch = AgentOrchestrator(web_search=WebSearchService(FakeProvider([])), prefer_deterministic=True)
    result = await orch.run(query, locale="fr")
    text = result.final_response.text
    assert "savoir-vivre" not in text.casefold()
    assert "culture" not in text.casefold()
    assert all(
        (k.chunk_id or "").startswith("culture-hotel-") or "hotel" in fold(k.content or "")
        for k in result.knowledge.knowledge
    )
    assert result.knowledge.places, "the city has verified hotels"
    lodging = ("hotel", "lodge", "residence", "motel", "auberge")
    for place in result.knowledge.places:
        assert "hotel" in [fold(c) for c in place.category] or any(
            w in fold(place.name) for w in lodging
        ), place.name


@pytest.mark.asyncio
async def test_no_verified_hotel_does_not_leak_internal_policy() -> None:
    orch = AgentOrchestrator(web_search=WebSearchService(FakeProvider([])), prefer_deterministic=True)
    result = await orch.run("Je cherche un hôtel à Limbé", locale="fr")
    text = result.final_response.text
    assert "Je n’ai pas encore d’hôtel vérifié à Limbé" in text
    assert "inventer" not in text and "Ayila" not in text
