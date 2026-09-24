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


def test_littoral_admin_and_capital():
    from app.services.agents.knowledge.geography import clear_geography_cache, city_admin_chain

    clear_geography_cache()
    chain = city_admin_chain("Douala")
    assert chain is not None
    assert chain["region"] == "Littoral"
    assert chain["division"] == "Wouri"
    assert chain["is_region_capital"] is True
    idx = load_geography()
    litt_divs = [d for d in idx.divisions.values() if d.get("region_id") == "littoral"]
    assert len(litt_divs) == 4


def test_littoral_not_douala():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("La région du Littoral c’est Douala nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"


def test_littoral_culture_ndole(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
    )

    clear_culture_cache()
    ev = culture_evidence_for_query("Quels plats typiques de Douala ?", language="fr")
    assert ev
    blob = " ".join(e.content.casefold() for e in ev)
    assert "ndol" in blob
    assert any((e.source_id or "") == "culture:littoral" for e in ev)


def test_sawa_sets_littoral_region():
    from app.services.agents.intent.extractors import extract_slots

    assert extract_slots("Culture Sawa à découvrir").region == "Littoral"


@pytest.mark.asyncio
async def test_visit_douala_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Douala que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    cities = {(p.city or "").casefold() for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    assert "nkongsamba" not in cities
    assert "edéa" not in cities and "edea" not in cities


@pytest.mark.asyncio
async def test_littoral_food_query_injects_culture(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Quels plats typiques du Littoral ?",
        mode="text",
        locale="fr",
    )
    assert any((k.source_id or "") == "culture:littoral" for k in result.knowledge.knowledge)
    text = result.final_response.text.casefold()
    assert "ndol" in text or "plat" in text


def test_centre_admin_and_capital():
    from app.services.agents.knowledge.geography import clear_geography_cache, city_admin_chain

    clear_geography_cache()
    chain = city_admin_chain("Yaoundé")
    assert chain is not None
    assert chain["region"] == "Centre"
    assert chain["division"] == "Mfoundi"
    assert chain["is_region_capital"] is True
    idx = load_geography()
    assert len([d for d in idx.divisions.values() if d.get("region_id") == "centre"]) == 4


def test_centre_not_yaounde():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("La région du Centre c’est Yaoundé nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"


def test_centre_culture_poulet(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
    )

    clear_culture_cache()
    ev = culture_evidence_for_query("Quels plats typiques à Yaoundé ?", language="fr")
    assert ev
    blob = " ".join(e.content.casefold() for e in ev)
    assert "poulet" in blob or "mokolo" in blob
    assert any((e.source_id or "") == "culture:centre" for e in ev)


def test_mokolo_sets_centre_region():
    from app.services.agents.intent.extractors import extract_slots

    assert extract_slots("Aller au marché Mokolo").region == "Centre"


@pytest.mark.asyncio
async def test_visit_yaounde_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Yaoundé que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    cities = {(p.city or "").casefold() for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    assert "mbalmayo" not in cities
    assert "mfou" not in cities


@pytest.mark.asyncio
async def test_centre_food_query_injects_culture(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Quels plats typiques à Yaoundé ?",
        mode="text",
        locale="fr",
    )
    assert any((k.source_id or "") == "culture:centre" for k in result.knowledge.knowledge)
    text = result.final_response.text.casefold()
    assert "poulet" in text or "plat" in text or "mokolo" in text


def test_sud_admin_and_kribi():
    from app.services.agents.knowledge.geography import clear_geography_cache, city_admin_chain

    clear_geography_cache()
    chain = city_admin_chain("Kribi")
    assert chain is not None
    assert chain["region"] == "Sud"
    assert chain["division"] == "Océan"
    idx = load_geography()
    assert len([d for d in idx.divisions.values() if d.get("region_id") == "sud"]) == 4
    ebolowa = city_admin_chain("Ebolowa")
    assert ebolowa and ebolowa["is_region_capital"] is True


def test_sud_not_kribi():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("La région du Sud c’est Kribi nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"


def test_lobe_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où sont les chutes de la Lobé ?", language="fr")
    assert facts
    assert "Kribi" in facts[0].text_fr


def test_sud_culture_poisson(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
    )

    clear_culture_cache()
    ev = culture_evidence_for_query("Quels plats typiques à Kribi ?", language="fr")
    assert ev
    blob = " ".join(e.content.casefold() for e in ev)
    assert "poisson" in blob or "fruit" in blob
    assert any((e.source_id or "") == "culture:sud" for e in ev)


def test_centre_has_multiple_hotels():
    from app.services.agents.knowledge.culture_packs import clear_culture_cache, _load_pack

    clear_culture_cache()
    pack = _load_pack("centre")
    assert len(pack.get("hotels_verified") or []) >= 5


@pytest.mark.asyncio
async def test_visit_kribi_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Kribi que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    cities = {(p.city or "").casefold() for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    assert "ebolowa" not in cities


@pytest.mark.asyncio
async def test_yaounde_hotels_query(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Hôtels à Yaoundé ?",
        mode="text",
        locale="fr",
    )
    assert result.knowledge.verified_places_count >= 2
    names = " ".join(p.name.casefold() for p in result.knowledge.places)
    assert "hilton" in names or "hotel" in names or "hôtel" in names or "palace" in names


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

def test_sud_ouest_admin_and_buea():
    from app.services.agents.knowledge.geography import clear_geography_cache, city_admin_chain

    clear_geography_cache()
    chain = city_admin_chain("Buea")
    assert chain is not None
    assert chain["region"] == "Sud-Ouest"
    assert chain["is_region_capital"] is True
    limbe = city_admin_chain("Limbé")
    assert limbe and limbe["region"] == "Sud-Ouest"
    assert limbe["division"] == "Fako"
    idx = load_geography()
    assert len([d for d in idx.divisions.values() if d.get("region_id") == "sud-ouest"]) == 4


def test_sud_ouest_not_buea():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("La région du Sud-Ouest c’est Buea nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"


def test_mont_cameroun_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est le Mont Cameroun ?", language="fr")
    assert facts
    assert "Buea" in facts[0].text_fr
    assert "Sud-Ouest" in facts[0].text_fr


def test_korup_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est le parc de Korup ?", language="fr")
    assert facts
    assert "Mundemba" in facts[0].text_fr or "Ndian" in facts[0].text_fr


def test_sud_ouest_culture_eru(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
    )

    clear_culture_cache()
    ev = culture_evidence_for_query("Quels plats typiques à Limbé ?", language="fr")
    assert ev
    blob = " ".join(e.content.casefold() for e in ev)
    assert "eru" in blob or "okok" in blob or "plantain" in blob
    assert any((e.source_id or "") == "culture:sud-ouest" for e in ev)
    assert not any((e.source_id or "") == "culture:ouest" for e in ev)


def test_sud_ouest_no_invented_hotels():
    from app.services.agents.knowledge.culture_packs import clear_culture_cache, _load_pack

    clear_culture_cache()
    pack = _load_pack("sud-ouest")
    assert pack.get("hotels_verified") == []
    assert pack.get("hotels_policy")
    assert (pack.get("restaurants_policy") or {}).get("verified_named_restaurants") == []


def test_eru_sets_sud_ouest_region():
    from app.services.agents.intent.extractors import extract_slots

    assert extract_slots("Parle-moi de l’eru").region == "Sud-Ouest"
    assert extract_slots("Que visiter à Kumba ?").city == "Kumba"


@pytest.mark.asyncio
async def test_visit_limbe_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Limbé que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    cities = {(p.city or "").casefold() for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    assert "buea" not in cities
    assert "kumba" not in cities


@pytest.mark.asyncio
async def test_sud_ouest_food_query_injects_culture(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Quels plats typiques du Sud-Ouest ?",
        mode="text",
        locale="fr",
    )
    assert any((k.source_id or "") == "culture:sud-ouest" for k in result.knowledge.knowledge)
    text = result.final_response.text.casefold()
    assert "eru" in text or "okok" in text or "plat" in text or "restaurant" in text


def test_nord_ouest_admin_and_bamenda():
    from app.services.agents.knowledge.geography import clear_geography_cache, city_admin_chain

    clear_geography_cache()
    chain = city_admin_chain("Bamenda")
    assert chain is not None
    assert chain["region"] == "Nord-Ouest"
    assert chain["is_region_capital"] is True
    assert chain["division"] == "Mezam"
    bafut = city_admin_chain("Bafut")
    assert bafut and bafut["region"] == "Nord-Ouest"
    idx = load_geography()
    assert len([d for d in idx.divisions.values() if d.get("region_id") == "nord-ouest"]) == 7


def test_nord_ouest_not_bamenda():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("La région du Nord-Ouest c’est Bamenda nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"


def test_bafut_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est le Palais de Bafut ?", language="fr")
    assert facts
    assert "Bafut" in facts[0].text_fr
    assert "Nord-Ouest" in facts[0].text_fr


def test_lac_oku_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est le lac Oku ?", language="fr")
    assert facts
    assert "Oku" in facts[0].text_fr


def test_nord_ouest_culture_achu(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
    )

    clear_culture_cache()
    ev = culture_evidence_for_query("Quels plats typiques à Bamenda ?", language="fr")
    assert ev
    blob = " ".join(e.content.casefold() for e in ev)
    assert "achu" in blob or "plantain" in blob or "marché" in blob or "marche" in blob
    assert any((e.source_id or "") == "culture:nord-ouest" for e in ev)
    assert not any((e.source_id or "") == "culture:ouest" for e in ev)


def test_nord_ouest_no_invented_hotels():
    from app.services.agents.knowledge.culture_packs import clear_culture_cache, _load_pack

    clear_culture_cache()
    pack = _load_pack("nord-ouest")
    assert pack.get("hotels_verified") == []
    assert pack.get("hotels_policy")
    assert (pack.get("restaurants_policy") or {}).get("verified_named_restaurants") == []


def test_bafut_sets_nord_ouest_region():
    from app.services.agents.intent.extractors import extract_slots

    assert extract_slots("Parle-moi du Palais de Bafut").region == "Nord-Ouest"
    assert extract_slots("Que visiter à Kumbo ?").city == "Kumbo"


@pytest.mark.asyncio
async def test_visit_bamenda_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Bamenda que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    cities = {(p.city or "").casefold() for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    assert "bafut" not in cities
    assert "oku" not in cities


@pytest.mark.asyncio
async def test_nord_ouest_food_query_injects_culture(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Quels plats typiques du Nord-Ouest ?",
        mode="text",
        locale="fr",
    )
    assert any((k.source_id or "") == "culture:nord-ouest" for k in result.knowledge.knowledge)
    text = result.final_response.text.casefold()
    assert "achu" in text or "plat" in text or "restaurant" in text or "marché" in text or "marche" in text


def test_extreme_nord_admin_and_maroua():
    from app.services.agents.knowledge.geography import clear_geography_cache, city_admin_chain

    clear_geography_cache()
    chain = city_admin_chain("Maroua")
    assert chain is not None
    assert chain["region"] == "Extrême-Nord"
    assert chain["is_region_capital"] is True
    assert chain["division"] == "Diamaré"
    idx = load_geography()
    assert len([d for d in idx.divisions.values() if d.get("region_id") == "extreme-nord"]) == 6


def test_extreme_nord_not_maroua():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("La région de l’Extrême-Nord c’est Maroua nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"


def test_waza_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est le parc de Waza ?", language="fr")
    assert facts
    assert "Extrême-Nord" in facts[0].text_fr or "Waza" in facts[0].text_fr


def test_rhumsiki_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est Rhumsiki ?", language="fr")
    assert facts
    assert "Extrême-Nord" in facts[0].text_fr or "Mandara" in facts[0].text_fr


def test_extreme_nord_culture_soya(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
    )

    clear_culture_cache()
    ev = culture_evidence_for_query("Quels plats typiques à Maroua ?", language="fr")
    assert ev
    blob = " ".join(e.content.casefold() for e in ev)
    assert "soya" in blob or "brochette" in blob or "mil" in blob
    assert any((e.source_id or "") == "culture:extreme-nord" for e in ev)


def test_extreme_nord_no_invented_hotels():
    from app.services.agents.knowledge.culture_packs import clear_culture_cache, _load_pack

    clear_culture_cache()
    pack = _load_pack("extreme-nord")
    assert pack.get("hotels_verified") == []
    assert pack.get("hotels_policy")


def test_waza_sets_extreme_nord_region():
    from app.services.agents.intent.extractors import extract_slots

    assert extract_slots("Parle-moi du parc de Waza").region == "Extrême-Nord"
    assert extract_slots("Que visiter à Rhumsiki ?").city == "Rhumsiki"


@pytest.mark.asyncio
async def test_visit_maroua_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Maroua que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    cities = {(p.city or "").casefold() for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    assert "waza" not in cities
    assert "rhumsiki" not in cities


@pytest.mark.asyncio
async def test_extreme_nord_food_query_injects_culture(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Quels plats typiques de l’Extrême-Nord ?",
        mode="text",
        locale="fr",
    )
    assert any((k.source_id or "") == "culture:extreme-nord" for k in result.knowledge.knowledge)


def test_adamaoua_admin_and_ngaoundere():
    from app.services.agents.knowledge.geography import clear_geography_cache, city_admin_chain

    clear_geography_cache()
    chain = city_admin_chain("Ngaoundéré")
    assert chain is not None
    assert chain["region"] == "Adamaoua"
    assert chain["is_region_capital"] is True
    assert chain["division"] == "Vina"
    idx = load_geography()
    assert len([d for d in idx.divisions.values() if d.get("region_id") == "adamaoua"]) == 5


def test_adamaoua_not_ngaoundere():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("La région de l’Adamaoua c’est Ngaoundéré nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"


def test_lac_tison_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est le lac Tison ?", language="fr")
    assert facts
    assert "Ngaoundéré" in facts[0].text_fr or "Adamaoua" in facts[0].text_fr


def test_adamaoua_culture_and_hotel(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
        _load_pack,
    )

    clear_culture_cache()
    pack = _load_pack("adamaoua")
    assert len(pack.get("hotels_verified") or []) >= 1
    assert "oasis" in (pack["hotels_verified"][0].get("name") or "").casefold()
    ev = culture_evidence_for_query("Quels plats typiques à Ngaoundéré ?", language="fr")
    assert any((e.source_id or "") == "culture:adamaoua" for e in ev)


def test_lamido_sets_adamaoua_region():
    from app.services.agents.intent.extractors import extract_slots

    assert extract_slots("Parle-moi du lamidat de Ngaoundéré").region == "Adamaoua"
    assert extract_slots("Que visiter à Banyo ?").city == "Banyo"


@pytest.mark.asyncio
async def test_visit_ngaoundere_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Ngaoundéré que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    cities = {(p.city or "").casefold() for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    assert "banyo" not in cities
    assert "meiganga" not in cities


@pytest.mark.asyncio
async def test_ngaoundere_hotel_oasis(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Hôtel à Ngaoundéré ?",
        mode="text",
        locale="fr",
    )
    blob = " ".join(p.name.casefold() for p in result.knowledge.places)
    blob += " " + result.final_response.text.casefold()
    assert "oasis" in blob or result.knowledge.verified_places_count >= 1


def test_nord_admin_and_garoua():
    from app.services.agents.knowledge.geography import clear_geography_cache, city_admin_chain

    clear_geography_cache()
    chain = city_admin_chain("Garoua")
    assert chain is not None
    assert chain["region"] == "Nord"
    assert chain["is_region_capital"] is True
    assert chain["division"] == "Bénoué"
    idx = load_geography()
    assert len([d for d in idx.divisions.values() if d.get("region_id") == "nord"]) == 4


def test_nord_not_garoua():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("La région du Nord c’est Garoua nor ?", language="fr")
    assert facts
    assert facts[0].relation == "IS_NOT_EQUIVALENT"


def test_benoue_park_geo_location():
    from app.services.agents.knowledge.geography import clear_geography_cache

    clear_geography_cache()
    facts = answer_geo_query("Où est le parc de la Bénoué ?", language="fr")
    assert facts
    assert "Tcholliré" in facts[0].text_fr or "Nord" in facts[0].text_fr


def test_nord_culture_and_hotels(geo_on):
    from app.services.agents.knowledge.culture_packs import (
        clear_culture_cache,
        culture_evidence_for_query,
        _load_pack,
    )

    clear_culture_cache()
    pack = _load_pack("nord")
    assert len(pack.get("hotels_verified") or []) >= 4
    ev = culture_evidence_for_query("Quels plats typiques à Garoua ?", language="fr")
    assert any((e.source_id or "") == "culture:nord" for e in ev)
    assert not any((e.source_id or "") == "culture:nord-ouest" for e in ev)


def test_benoue_sets_nord_region():
    from app.services.agents.intent.extractors import extract_slots

    assert extract_slots("Parle-moi du parc de la Bénoué").region == "Nord"
    assert extract_slots("Que visiter à Figuil ?").city == "Figuil"


@pytest.mark.asyncio
async def test_visit_garoua_returns_local_places(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Je veux visiter Garoua que me proposes-tu ?",
        mode="text",
        locale="fr",
    )
    cities = {(p.city or "").casefold() for p in result.knowledge.places}
    assert result.knowledge.verified_places_count >= 1
    assert "figuil" not in cities
    assert "tcholliré" not in cities and "tchollire" not in cities


@pytest.mark.asyncio
async def test_garoua_hotels_query(geo_on):
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex.from_catalog()),
        prefer_deterministic=True,
    )
    result = await orch.run(
        "Hôtels à Garoua ?",
        mode="text",
        locale="fr",
    )
    blob = " ".join(p.name.casefold() for p in result.knowledge.places)
    blob += " " + result.final_response.text.casefold()
    assert result.knowledge.verified_places_count >= 2
    assert "shalom" in blob or "ribadou" in blob or "plaza" in blob or "palace" in blob or "hôtel" in blob
