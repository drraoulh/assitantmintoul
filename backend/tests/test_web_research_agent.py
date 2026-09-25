"""Tests for Web Research Agent — validation, cache, orchestrator hook."""

from __future__ import annotations

import pytest

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.knowledge.source_validator import should_request_web
from app.services.agents.orchestrator.orchestrator import AgentOrchestrator
from app.services.agents.web_research.agent import WebResearchAgent
from app.services.agents.web_research.cache import cache_clear
from app.services.agents.web_research.models import WebEvidence
from app.services.agents.web_research.search import build_search_queries
from app.services.agents.web_research.validator import (
    extract_domain,
    is_answerable,
    source_tier,
    validate_evidence,
)
from app.services.search.base import WebSearchHit, WebSearchService


class FakeWeb(WebSearchService):
    def __init__(self, hits: list[WebSearchHit] | None = None) -> None:
        self.hits = hits or []
        self.calls = 0

    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        self.calls += 1
        return self.hits[:max_results]


def test_source_tier_institutional():
    assert source_tier("mintoul.gov.cm") == 1
    assert source_tier("www.unesco.org") == 1
    assert source_tier("tourismo-cameroun.com") == 2
    assert source_tier("en.wikipedia.org") == 3
    assert source_tier("random-blog.example") == 4


def test_validate_rejects_empty_snippets():
    items = validate_evidence(
        [
            WebEvidence(title="A", url="https://mintoul.gov.cm/x", snippet="short", tier=1),
            WebEvidence(
                title="B",
                url="https://mintoul.gov.cm/food",
                domain="mintoul.gov.cm",
                snippet="La gastronomie du Sud-Ouest camerounais repose sur le poisson et le plantain.",
                relevance_score=0.8,
                tier=1,
            ),
        ],
        query="nourriture traditionnelle Sud-Ouest Cameroun",
    )
    assert len(items) == 1
    assert is_answerable(items) is True


def test_validate_rejects_offtopic_france_hits():
    items = validate_evidence(
        [
            WebEvidence(
                title="Cannes",
                url="https://fr.wikipedia.org/wiki/Cannes",
                domain="fr.wikipedia.org",
                snippet="Cannes est une commune française de la Côte d'Azur dans le Sud-Ouest.",
                relevance_score=0.6,
                tier=3,
            ),
            WebEvidence(
                title="Ngondo",
                url="https://fr.wikipedia.org/wiki/Ngondo",
                domain="fr.wikipedia.org",
                snippet=(
                    "Le ngondo est une fête traditionnelle et rituelle camerounaise "
                    "articulée autour d'un festival culturel du peuple Sawa."
                ),
                relevance_score=0.7,
                tier=3,
            ),
        ],
        query="Recherche sur Internet les festivals du Sud-Ouest Cameroun",
        intent="WEB_SEARCH",
    )
    assert len(items) == 1
    assert "cameroun" in items[0].snippet.casefold() or "camerounaise" in items[0].snippet.casefold()
    assert is_answerable(items) is True


def test_build_queries_food_southwest():
    intent = IntentResult(
        intent="FOOD",
        location="Sud-Ouest",
        region="Sud-Ouest",
        needs_knowledge=True,
        confidence=0.8,
    )
    qs = build_search_queries(
        "C'est quoi la nourriture traditionnelle au Sud-Ouest ?",
        intent,
        missing=["knowledge_chunks"],
    )
    assert qs
    joined = " ".join(qs).casefold()
    assert "cameroun" in joined or "cameroon" in joined
    assert any("food" in q.casefold() or "cuisine" in q.casefold() or "plat" in q.casefold() for q in qs)


def test_intent_events_and_explicit_web():
    from app.services.agents.intent.router import classify_intent

    fest = classify_intent(
        "Recherche sur Internet les festivals du Sud-Ouest.",
        locale="fr",
        mode="text",
    )
    assert fest.intent == "WEB_SEARCH"
    assert fest.needs_web is True

    month = classify_intent(
        "Quels événements touristiques ont lieu ce mois-ci ?",
        locale="fr",
        mode="text",
    )
    assert month.intent == "WEB_SEARCH"
    assert month.needs_web is True

    capital = classify_intent(
        "Quelle est la capitale du Cameroun ?",
        locale="fr",
        mode="text",
    )
    assert capital.intent == "SIMPLE_QA"
    assert capital.needs_web is False

    food = classify_intent(
        "C'est quoi la nourriture traditionnelle au Sud-Ouest ?",
        locale="fr",
        mode="text",
    )
    assert food.intent == "FOOD"
    assert food.location == "Sud-Ouest" or food.region == "Sud-Ouest"


def test_should_request_web_food_missing_kb():
    assert should_request_web("FOOD", ["knowledge_chunks"], 0.2) is True
    assert should_request_web("SIMPLE_QA", [], 0.9) is False


@pytest.mark.asyncio
async def test_web_research_agent_returns_evidence():
    cache_clear()
    web = FakeWeb(
        [
            WebSearchHit(
                title="Gastronomie Cameroun",
                snippet=(
                    "Dans le Sud-Ouest, la cuisine traditionnelle met en avant "
                    "le poisson fumé, le plantain et le manioc selon les sources touristiques."
                ),
                url="https://www.mintoul.gov.cm/gastronomie",
                source="open_web",
            )
        ]
    )
    agent = WebResearchAgent(web, timeout_seconds=5, cache_ttl_seconds=60)
    intent = IntentResult(intent="FOOD", location="Sud-Ouest", needs_knowledge=True, confidence=0.7)
    result = await agent.research(
        "C'est quoi la nourriture traditionnelle au Sud-Ouest ?",
        intent,
        knowledge=KnowledgeResult(
            query="food",
            intent="FOOD",
            missing_information=["knowledge_chunks"],
            web_needed=True,
            confidence=0.2,
            source="empty",
        ),
        request_id="test1",
    )
    assert result.answerable is True
    assert result.evidence
    assert web.calls >= 1


@pytest.mark.asyncio
async def test_orchestrator_calls_web_research_when_kb_thin(monkeypatch):
    cache_clear()
    monkeypatch.setenv("WEB_KNOWLEDGE_FALLBACK_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    web = FakeWeb(
        [
            WebSearchHit(
                title="Southwest Cameroon food",
                snippet=(
                    "Traditional dishes in Southwest Cameroon include preparations "
                    "with fish, plantain, and cassava leaves (eru) in coastal communities."
                ),
                url="https://en.wikipedia.org/wiki/Cuisine_of_Cameroon",
            )
        ]
    )

    # Force Agent 2 empty via monkeypatch on KnowledgeAgent.retrieve
    async def empty_retrieve(self, query, intent, request_id=None):  # noqa: ANN001
        return KnowledgeResult(
            query=query,
            intent=intent.intent,
            places=[],
            knowledge=[],
            sources=[],
            missing_information=["knowledge_chunks"],
            web_needed=True,
            confidence=0.15,
            source="empty",
            knowledge_completeness="NONE",
            request_id=request_id,
        )

    monkeypatch.setattr(
        "app.services.agents.knowledge.agent.KnowledgeAgent.retrieve",
        empty_retrieve,
    )

    orch = AgentOrchestrator(web_search=web, prefer_deterministic=True)
    result = await orch.run(
        "C'est quoi la nourriture traditionnelle au Sud-Ouest ?",
        mode="text",
        locale="fr",
        request_id="sw-food",
    )
    assert "web_research" in result.agents_called
    assert result.knowledge is not None
    assert any("web evidence" in (k.content or "") for k in result.knowledge.knowledge)
    assert result.final_response is not None
    text = (result.final_response.text or "").casefold()
    # Must not be the old empty refusal loop
    assert text.count("ne sont pas disponibles") <= 1
    get_settings.cache_clear()


def test_extract_domain():
    assert extract_domain("https://www.Mintoul.gov.cm/path") == "mintoul.gov.cm"


def test_greeting_is_not_itinerary_clarification():
    from app.services.agents.intent.router import classify_intent
    from app.services.agents.knowledge.models import KnowledgeResult
    from app.services.agents.response.fallback import render_deterministic

    intent = classify_intent("Bonjour", locale="fr", mode="text")
    assert intent.reason == "greeting"
    assert intent.needs_web is False
    text = render_deterministic(
        "Bonjour", intent, KnowledgeResult(query="Bonjour", intent=intent.intent), None
    )
    assert text.startswith("Bonjour")
    assert "budget" not in text.casefold()


def test_food_region_follow_up_overrides_context_region():
    from app.services.agents.intent.router import classify_intent

    follow_up = classify_intent(
        "Et le plat traditionnel centre ?",
        locale="fr",
        mode="text",
        conversation_context="Plat traditionnel sud ouest",
    )
    assert follow_up.intent == "FOOD"
    assert follow_up.region == "Centre"
    assert follow_up.needs_web is True
    assert follow_up.web_reason == "REGIONAL_GASTRONOMY"

    anaphora = classify_intent(
        "Et la nourriture ?",
        locale="fr",
        mode="text",
        conversation_context="Je veux découvrir le Sud-Ouest",
    )
    assert anaphora.region == "Sud-Ouest"


def test_voice_food_skips_web():
    from app.services.agents.intent.router import classify_intent

    voice = classify_intent("Plat traditionnel du centre", locale="fr", mode="voice")
    assert voice.intent == "FOOD"
    assert voice.needs_web is False


def test_culture_pack_follows_resolved_region():
    from app.services.agents.knowledge.culture_packs import culture_evidence_for_query

    ev = culture_evidence_for_query("Et la nourriture ?", language="fr", region="Centre")
    assert ev
    assert all(e.source_id == "culture:centre" for e in ev)


def test_filter_regional_drops_other_regions():
    from app.services.agents.web_research.validator import filter_regional

    items = [
        WebEvidence(title="Koki", url="https://x/1", snippet="Koki is a dish from the Southwest region of Cameroon."),
        WebEvidence(title="Alloco", url="https://x/2", snippet="L'alloco est un plat ivoirien populaire au Cameroun."),
    ]
    kept = filter_regional(items, "Sud-Ouest")
    assert [e.title for e in kept] == ["Koki"]


def test_national_capital_is_yaounde():
    from app.services.agents.knowledge.geography import answer_geo_query

    facts = answer_geo_query("Quelle est la capitale du Cameroun ?", language="fr")
    assert facts and facts[0].subject == "Yaoundé"
    east = answer_geo_query("Quel est le chef-lieu de la région de l'Est ?", language="fr")
    assert east and east[0].subject == "Bertoua"


def test_food_ui_hides_unrelated_places():
    from app.services.agents.knowledge.models import KnowledgeResult, PlaceEvidence
    from app.services.agents.response.models import FinalResponse
    from app.services.agents.response.structured_ui import build_structured_ui

    knowledge = KnowledgeResult(
        query="food",
        intent="FOOD",
        places=[
            PlaceEvidence(place_id="beach", name="Moland Beach", description="Plage de sable noir.", category=["nature"]),
            PlaceEvidence(place_id="mokolo", name="Marché Mokolo", description="Grand marché de Yaoundé.", category=["market"]),
        ],
    )
    final = FinalResponse(text="x", language="fr", response_type="FOOD", response_mode="text")
    ui = build_structured_ui(final=final, knowledge=knowledge)
    assert [p.name for p in ui["places"]] == ["Marché Mokolo"]


def test_event_search_without_dated_evidence_is_honest():
    from app.services.agents.intent.router import classify_intent
    from app.services.agents.knowledge.models import KnowledgeEvidence
    from app.services.agents.response.fallback import render_deterministic

    q = "Quels festivals ce mois-ci au Cameroun ?"
    intent = classify_intent(q, locale="fr", mode="text")
    assert intent.intent == "WEB_SEARCH"
    knowledge = KnowledgeResult(
        query=q,
        intent=intent.intent,
        knowledge=[
            KnowledgeEvidence(
                chunk_id="doc:history_culture:7",
                content="## Festivals et célébrations (indicatifs)\n- Fêtes nationales.",
            ),
            KnowledgeEvidence(
                chunk_id="doc:travel_tips:0",
                content="# Conseils pratiques\nQue mettre dans le sac.",
            ),
            KnowledgeEvidence(
                chunk_id="web:x:0",
                content="[web evidence — institutional] Présentation générale du Cameroun.",
            ),
        ],
    )
    text = render_deterministic(q, intent, knowledge, None)
    assert "pas trouvé de programme" in text
    assert "Festivals et célébrations" in text
    assert "sac" not in text
    assert "Présentation générale" not in text
