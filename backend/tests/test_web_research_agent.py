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
