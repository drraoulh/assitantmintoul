"""Phase 2.2 Agent 2 — Knowledge & Retrieval mandatory tests."""

from __future__ import annotations

import statistics
import time

from app.services.agents.intent import classify_intent
from app.services.agents.knowledge.agent import KnowledgeAgent
from app.services.agents.knowledge.compare import compare_retrieval
from app.services.agents.knowledge.models import PlaceEvidence
from app.services.agents.knowledge.place_store import PlaceIndex, PlaceRecord
from app.services.agents.knowledge.source_validator import validate_places
from app.services.rag.chunk import KnowledgeChunk
from app.services.rag.local import LocalRAGService


def _fixture_places() -> list[PlaceRecord]:
    return [
        PlaceRecord(
            place_id="place-yaounde-1",
            name="Musée National du Cameroun",
            name_fr="Musée National du Cameroun",
            name_en="National Museum of Cameroon",
            city="Yaoundé",
            region="Centre",
            description="Musée national à Yaoundé.",
            cultural_info="Patrimoine culturel national à Yaoundé.",
            categories=["Museum"],
            estimated_cost_xaf=2000,
            recommended_duration_hours=2.0,
            is_published=True,
            source_id="src-mintoul",
            source_name="MINTOUL",
            source_url="https://mintoul.gov.cm/",
        ),
        PlaceRecord(
            place_id="place-yaounde-2",
            name="Monument de la Réunification",
            city="Yaoundé",
            region="Centre",
            description="Monument emblématique de Yaoundé.",
            cultural_info="Mémoire de la réunification.",
            categories=["Monument"],
            estimated_cost_xaf=None,
            is_published=True,
            source_id="src-mintoul",
        ),
        PlaceRecord(
            place_id="place-mont-cameroun",
            name="Mont Cameroun",
            name_fr="Mont Cameroun",
            name_en="Mount Cameroon",
            slug="mont-cameroun",
            city="Buea",
            region="Sud-Ouest",
            description="Massif volcanique actif, site d'écotourisme.",
            eco_info="Trek et nature ; guide local recommandé.",
            activities=["hiking", "nature visit"],
            categories=["Natural"],
            eco_tags=["ecotourism", "hiking"],
            is_published=True,
            source_id="src-eco",
            source_name="Écotourisme",
            source_url="https://mintoul.gov.cm/tourisme/ecotourisme/",
        ),
        PlaceRecord(
            place_id="place-waza",
            name="Parc national de Waza",
            city="Waza",
            region="Extrême-Nord",
            description="Parc animalier du Nord.",
            eco_info="Safari et faune.",
            activities=["wildlife viewing"],
            categories=["Park"],
            eco_tags=["wildlife", "park"],
            estimated_cost_xaf=5000,
            is_published=True,
        ),
        PlaceRecord(
            place_id="place-sawa-douala",
            name="Espace culturel Sawa",
            city="Douala",
            region="Littoral",
            description="Espace dédié à la culture Sawa du littoral.",
            cultural_info="Culture Sawa, traditions maritimes du Littoral.",
            cultural_zone="Sawa",
            categories=["Culture"],
            is_published=True,
        ),
        PlaceRecord(
            place_id="place-unpublished",
            name="Site secret non publié",
            city="Yaoundé",
            region="Centre",
            description="Ne doit jamais apparaître.",
            categories=["Monument"],
            is_published=False,
        ),
        PlaceRecord(
            place_id="place-hotel-yde",
            name="Hôtel du Centre",
            city="Yaoundé",
            region="Centre",
            description="Hébergement à Yaoundé.",
            categories=["Hotel"],
            estimated_cost_xaf=45000,
            is_published=True,
        ),
    ]


def _fixture_chunks() -> list[KnowledgeChunk]:
    return [
        KnowledgeChunk(
            id="doc:food:1",
            title="Gastronomie camerounaise",
            text=(
                "Plats camerounais à goûter : ndolé, eru, achu, poisson braisé, "
                "kondre. Spécialités de l'Ouest et du Littoral."
            ),
            source="data/documents/food.md",
            category="food",
            tags=["food", "cuisine"],
        ),
        KnowledgeChunk(
            id="doc:culture:sawa",
            title="Cultures du littoral",
            text=(
                "Cultures Sawa, forêt humide, liens maritimes. "
                "Douala et Kribi illustrent littoral urbain et balnéaire."
            ),
            source="data/documents/history_culture.md",
            category="culture",
            tags=["culture", "sawa"],
        ),
        KnowledgeChunk(
            id="doc:nature:1",
            title="Parcs et nature",
            text="Parcs nationaux : Waza, Korup, Mont Cameroun, réserve du Dja.",
            source="data/documents/national_parks_wildlife.md",
            category="nature",
            tags=["nature", "park"],
        ),
        KnowledgeChunk(
            id="place:mont",
            title="Mont Cameroun",
            text="Lieu: Mont Cameroun. Ville: Buea. Trek nature.",
            source="supabase/places",
            city="Buea",
            region="Sud-Ouest",
            category="Natural",
        ),
    ]


def _agent() -> KnowledgeAgent:
    return KnowledgeAgent(
        PlaceIndex(_fixture_places()),
        rag=LocalRAGService(chunks=_fixture_chunks()),
    )


def test_yaounde_place_search():
    query = "Que puis-je visiter à Yaoundé ?"
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    assert result.places
    assert all(p.city == "Yaoundé" for p in result.places)
    assert all(p.place_id.startswith("place-") for p in result.places)
    assert "place-unpublished" not in {p.place_id for p in result.places}


def test_mont_cameroun_place_details():
    query = "Parle-moi du Mont Cameroun."
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    assert result.places
    top = result.places[0]
    assert top.place_id == "place-mont-cameroun"


def test_nature_has_eco_evidence():
    query = "Propose-moi une activité nature au Cameroun."
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    assert result.places
    for place in result.places:
        has_nature = (
            bool(place.eco_tags)
            or bool(place.eco_info)
            or any(
                "natural" in c.casefold() or "park" in c.casefold()
                for c in place.category
            )
            or any(
                "nature" in a.casefold() or "hik" in a.casefold()
                for a in place.activities
            )
        )
        assert has_nature, place.name


def test_culture_sawa_evidence():
    query = "Je veux découvrir la culture Sawa."
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    cultural = False
    if result.places:
        cultural = any(
            (p.cultural_info and "sawa" in p.cultural_info.casefold())
            or (p.cultural_zone and "sawa" in p.cultural_zone.casefold())
            for p in result.places
        )
    if result.knowledge:
        cultural = cultural or any(
            "sawa" in (k.content or "").casefold() for k in result.knowledge
        )
    assert cultural


def test_food_knowledge():
    query = "Quels plats camerounais dois-je goûter ?"
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    assert result.knowledge
    blob = " ".join(k.content.casefold() for k in result.knowledge)
    assert "ndolé" in blob or "ndole" in blob or "plat" in blob


def test_unknown_place_not_invented():
    query = "Parle-moi du Parc XYZ qui se trouve à Yaoundé."
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    names = " ".join(p.name.casefold() for p in result.places)
    assert "parc xyz" not in names
    known = {p.place_id for p in _fixture_places() if p.is_published}
    assert all(p.place_id in known for p in result.places)


def test_budget_trip_prefers_known_costs():
    query = "Voyage de 3 jours avec 150000 FCFA à Yaoundé."
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    assert result.places
    assert all(p.city == "Yaoundé" for p in result.places)
    for place in result.places:
        if place.place_id == "place-yaounde-2":
            assert place.estimated_cost_xaf is None


def test_unpublished_filtered():
    query = "Que puis-je visiter à Yaoundé ?"
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    assert all(p.place_id != "place-unpublished" for p in result.places)
    fake = PlaceEvidence(
        place_id="place-unpublished",
        name="Secret",
        is_published=False,
    )
    assert validate_places([fake], known_ids={"place-unpublished"}) == []


def test_missing_cost_stays_null():
    intent = classify_intent("Que visiter à Yaoundé ?")
    result = _agent().retrieve_sync("Que visiter à Yaoundé ?", intent)
    monument = next(
        (p for p in result.places if p.place_id == "place-yaounde-2"),
        None,
    )
    assert monument is not None
    assert monument.estimated_cost_xaf is None


def test_no_evidence_low_confidence():
    query = "Horaires actuels du metro de Tokyo aujourd'hui"
    intent = classify_intent(query)
    result = _agent().retrieve_sync(query, intent)
    if not result.places and not result.knowledge:
        assert result.confidence <= 0.35
        assert result.web_needed is True or bool(result.missing_information)
    else:
        assert result.confidence < 0.75


def test_agent2_latency_under_budget():
    query = "Que puis-je visiter à Yaoundé ?"
    intent = classify_intent(query)
    agent = _agent()
    samples: list[float] = []
    result = None
    for _ in range(20):
        t0 = time.perf_counter()
        result = agent.retrieve_sync(query, intent)
        samples.append((time.perf_counter() - t0) * 1000.0)
        assert result.places
    median = statistics.median(samples)
    assert median < 100.0, f"Agent2 median too slow: {median:.1f}ms"
    assert result is not None
    assert result.total_agent2_ms is not None
    assert result.place_retrieval_ms is not None


def test_compare_retrieval_diagnostic():
    report = compare_retrieval(
        "Que puis-je visiter à Yaoundé ?",
        place_index=PlaceIndex(_fixture_places()),
        rag=LocalRAGService(chunks=_fixture_chunks()),
    )
    assert "old_retrieval" in report and "agent2" in report
    assert report["agent2"]["places_count"] >= 1


def test_observability_has_no_raw_query_dump():
    query = "Que puis-je visiter à Yaoundé ?"
    intent = classify_intent(query, request_id="req-42")
    result = _agent().retrieve_sync(query, intent, request_id="req-42")
    payload = result.observability()
    assert payload["request_id"] == "req-42"
    assert "places_count" in payload
    assert "query" not in payload
