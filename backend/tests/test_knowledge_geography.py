"""Phase 2.8 — geography graph + hierarchical retrieval tests."""

from __future__ import annotations

import asyncio
import os
import time

import pytest

from app.services.agents.intent.router import IntentRouter
from app.services.agents.knowledge.agent import KnowledgeAgent
from app.services.agents.knowledge.geography import (
    answer_geo_query,
    city_admin_chain,
    is_geo_simple_query,
    load_geography,
)
from app.services.agents.knowledge.place_store import PlaceIndex
from app.services.agents.orchestrator import AgentOrchestrator
from app.services.agents.response.agent import ResponseGenerator


@pytest.fixture()
def geo_on(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_GEOGRAPHY_ENABLED", "true")
    monkeypatch.setenv("GROUNDING_ENFORCEMENT_ENABLED", "true")
    from app.core.config import get_settings
    from app.services.agents.knowledge.culture_packs import clear_culture_cache
    from app.services.agents.knowledge.geography import clear_geography_cache

    get_settings.cache_clear()
    clear_geography_cache()
    clear_culture_cache()
    yield
    get_settings.cache_clear()
    clear_geography_cache()
    clear_culture_cache()
    monkeypatch.delenv("KNOWLEDGE_GEOGRAPHY_ENABLED", raising=False)
    monkeypatch.delenv("GROUNDING_ENFORCEMENT_ENABLED", raising=False)
    get_settings.cache_clear()


def test_bafoussam_belongs_to_ouest():
    chain = city_admin_chain("Bafoussam")
    assert chain is not None
    assert chain["region"] == "Ouest"
    assert chain["division"] == "Mifi"
    assert chain["is_region_capital"] is True


def test_ouest_capital_is_bafoussam():
    facts = answer_geo_query("Quelle est la capitale de l'Ouest ?", language="fr")
    assert facts
    assert "Bafoussam" in facts[0].text_fr
    assert "Ouest" in facts[0].text_fr


def test_ouest_is_not_bafoussam():
    facts = answer_geo_query("La région de l'Ouest c'est Bafoussam nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"
    assert "Pas exactement" in facts[0].text_fr


def test_bafoussam_department_mifi():
    facts = answer_geo_query("Bafoussam est dans quel département ?", language="fr")
    assert facts
    assert "Mifi" in facts[0].text_fr


def test_foumban_region_ouest():
    facts = answer_geo_query("Dans quelle région se trouve Foumban ?", language="fr")
    assert facts
    assert "Ouest" in facts[0].text_fr


def test_lac_baleng_location():
    facts = answer_geo_query("Lac Baleng est où ?", language="fr")
    assert facts
    assert "Baleng" in facts[0].text_fr
    assert "Bafoussam" in facts[0].text_fr


@pytest.mark.asyncio
async def test_visit_bafoussam_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Bafoussam que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    names = [p.name for p in result.knowledge.places]
    cities = {fold_city(p.city) for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    # Must not dump Foumban as "in Bafoussam"
    assert not any("foumban" in n.casefold() for n in names) or any(
        "bafoussam" in (p.city or "").casefold() for p in result.knowledge.places
    )
    assert "foumban" not in cities
    text = result.final_response.text.casefold()
    assert "vérif" in text or "lieu" in text or "bafoussam" in text


def fold_city(name: str | None) -> str:
    return (name or "").casefold()


@pytest.mark.asyncio
async def test_around_bafoussam_can_include_nearby(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Que visiter autour de Bafoussam ?",
        mode="text",
        locale="fr",
    )
    scopes = {p.location_scope for p in result.knowledge.places}
    # Either nearby places present or at least Bafoussam hub places
    assert result.knowledge.places
    assert "IN_CITY" in scopes or "NEARBY" in scopes or result.knowledge.verified_places_count >= 1


@pytest.mark.asyncio
async def test_ouest_region_query_can_include_regional(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter l'Ouest du Cameroun.",
        mode="text",
        locale="fr",
    )
    # Region query: may include Foumban / Dschang / Bafoussam
    regions = {(p.region or "").casefold() for p in result.knowledge.places}
    assert not result.knowledge.places or "ouest" in regions or result.intent.region == "Ouest"


@pytest.mark.asyncio
async def test_geo_simple_skips_planner(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Bafoussam est dans quelle région ?",
        mode="text",
        locale="fr",
    )
    assert "planner" not in result.agents_called
    assert "Ouest" in result.final_response.text
    assert result.intent.intent == "SIMPLE_QA"


@pytest.mark.asyncio
async def test_geo_latency_warm(geo_on):
    # Warm
    load_geography()
    answer_geo_query("Bafoussam est dans quelle région ?", language="fr")
    t0 = time.perf_counter()
    for _ in range(20):
        answer_geo_query("Bafoussam est dans quelle région ?", language="fr")
    avg_ms = ((time.perf_counter() - t0) / 20) * 1000
    assert avg_ms < 5.0  # pure structured lookup


def test_intent_geo_is_simple_qa():
    router = IntentRouter()
    intent = router.classify("Bafoussam est dans quelle région ?", locale="fr")
    assert intent.intent == "SIMPLE_QA"
    assert intent.needs_planner is False


def test_is_geo_simple_query_detection():
    assert is_geo_simple_query("Quelle est la capitale de l'Ouest ?")
    assert is_geo_simple_query("La région de l'Ouest c'est Bafoussam nor ?")


@pytest.mark.asyncio
async def test_no_invented_restaurants_still(geo_on):
    agent = ResponseGenerator(prefer_deterministic=True)
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    ctx = await orch.prepare("Donne-moi 10 restaurants de Bafoussam", mode="text", locale="fr")
    final = await agent.generate(
        "Donne-moi 10 restaurants de Bafoussam",
        ctx.intent,
        ctx.knowledge,
        ctx.plan,
        locale="fr",
    )
    text = final.text.casefold()
    assert "african food by emy" not in text
    assert "taste of afrka" not in text


def test_ten_regions_loaded():
    idx = load_geography()
    assert len(idx.regions) == 10
    assert "bafoussam" in idx.alias_to_city


def test_ouest_has_eight_divisions():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    idx = load_geography()
    ouest_divs = [d for d in idx.divisions.values() if d.get("region_id") == "ouest"]
    assert len(ouest_divs) == 8


def test_mbapit_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est le lac Mbapit ?", language="fr")
    assert facts
    assert "Foumban" in facts[0].text_fr or "Mbapit" in facts[0].text_fr


def test_ouest_culture_food_evidence(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
    )

    clear_culture_cache()
    ev = culture_evidence_for_query("Quels plats typiques de l’Ouest ?", language="fr")
    assert ev
    blob = " ".join(e.content.casefold() for e in ev)
    assert "achu" in blob
    assert any(e.source_id == "culture:ouest" for e in ev)


def test_ouest_no_invented_restaurant_names_in_culture():
    from app.services.agents.knowledge.culture_packs import clear_culture_cache, _load_ouest

    clear_culture_cache()
    pack = _load_ouest()
    assert pack["restaurants_policy"]["verified_named_restaurants"] == []


def test_intent_extracts_bandjoun_and_mbouda():
    from app.services.agents.intent.extractors import extract_slots

    assert extract_slots("Visiter Bandjoun").city == "Bandjoun"
    assert extract_slots("Je vais à Mbouda").city == "Mbouda"
    assert extract_slots("Bangangté ce week-end").city == "Bangangté"


def test_ou_est_does_not_mean_est_region():
    from app.services.agents.intent.extractors import extract_slots

    slots = extract_slots("Où est le lac Mbapit ?")
    assert slots.region != "Est"
    assert slots.place_name == "Lac Mbapit"


def test_bamoun_sets_ouest_region():
    from app.services.agents.intent.extractors import extract_slots

    slots = extract_slots("Parle-moi des traditions Bamoun")
    assert slots.region == "Ouest"


def test_mbapit_is_geo_simple():
    from app.services.agents.knowledge.geography import is_geo_simple_query

    assert is_geo_simple_query("Où est le lac Mbapit ?")


@pytest.mark.asyncio
async def test_visit_foumban_returns_palace(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Que visiter à Foumban ?",
        mode="text",
        locale="fr",
    )
    names = " ".join(p.name.casefold() for p in result.knowledge.places)
    assert result.knowledge.verified_places_count >= 1
    assert "palais" in names or "mbapit" in names or "foumban" in names


@pytest.mark.asyncio
async def test_ouest_food_query_injects_culture(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Quels plats typiques de l’Ouest camerounais ?",
        mode="text",
        locale="fr",
    )
    sources = {s.source_id for s in result.knowledge.sources}
    assert "culture:ouest" in sources or any(
        (k.source_id or "") == "culture:ouest" for k in result.knowledge.knowledge
    )
    text = result.final_response.text.casefold()
    assert "achu" in text or "koki" in text or "restaurant" in text or "plat" in text