"""General factual questions about Cameroon get a direct answer, never a clarification."""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import get_settings
from app.services.agents.intent.router import classify_intent
from app.services.agents.knowledge.national_facts import (
    answer_national_fact,
    is_general_fact_query,
    is_volatile_fact_query,
)
from app.services.agents.orchestrator.orchestrator import AgentOrchestrator
from app.services.agents.web_research.cache import cache_clear
from app.services.web_search.models import WebSearchResult
from app.services.web_search.source_parser import parse_result
from app.services.web_search.web_search_service import WebSearchProvider, WebSearchService


class FakeProvider(WebSearchProvider):
    name = "fake"

    def __init__(self, rows: list[WebSearchResult]) -> None:
        self.rows = rows
        self.queries: list[str] = []

    async def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        self.queries.append(query)
        await asyncio.sleep(0)
        return self.rows[:max_results]


def _row(title: str, url: str, snippet: str) -> WebSearchResult:
    parsed = parse_result(title=title, url=url, snippet=snippet, provider="fake")
    assert parsed is not None
    return parsed


PRESIDENT_ROWS = [
    _row(
        "Paul Biya | Britannica",
        "https://www.britannica.com/biography/Paul-Biya",
        "Paul Biya is a politician who has served as president of Cameroon since 1982.",
    ),
    _row(
        "Présidence de la République du Cameroun",
        "https://www.prc.cm/fr/le-president",
        "Paul Biya est le président de la République du Cameroun depuis le 6 novembre 1982.",
    ),
]


@pytest.fixture(autouse=True)
def _geo_on(monkeypatch):
    monkeypatch.setenv("KNOWLEDGE_GEOGRAPHY_ENABLED", "true")
    get_settings.cache_clear()
    cache_clear()
    yield
    cache_clear()
    get_settings.cache_clear()


@pytest.mark.parametrize(
    "query",
    [
        "Qui est le président du Cameroun ?",
        "Qui est le président du Cameroun",
        "Le président du Cameroun c'est qui ?",
        "président du Cameroun ?",
        "Quel est le premier ministre du Cameroun ?",
        "Combien d'habitants au Cameroun ?",
        "Who is the president of Cameroon?",
        "How many people live in Cameroon?",
        "Quand le Cameroun est-il devenu indépendant ?",
        "Quelle langue parle-t-on au Cameroun ?",
        "Quel est l'hymne national du Cameroun ?",
        "Qui a gagné la CAN 2017 ?",
    ],
)
def test_general_questions_are_not_clarifications(query: str) -> None:
    result = classify_intent(query, locale="fr")
    assert result.intent == "SIMPLE_QA"
    assert result.confidence >= 0.6
    assert result.reason == "general_fact"


@pytest.mark.parametrize(
    "query",
    ["Qui est le président du Cameroun ?", "Combien d'habitants au Cameroun ?", "Who is the prime minister of Cameroon?"],
)
def test_volatile_facts_force_web(query: str) -> None:
    assert is_volatile_fact_query(query)
    result = classify_intent(query, locale="fr")
    assert result.needs_web and result.web_reason == "FORCED_CURRENT_INFORMATION"


@pytest.mark.parametrize(
    "query",
    ["Quels hôtels à Douala ?", "Que visiter au Cameroun ?", "Organise-moi 3 jours à Kribi", "Bonjour"],
)
def test_trip_requests_are_not_general_facts(query: str) -> None:
    assert not is_general_fact_query(query)
    assert classify_intent(query, locale="fr").reason != "general_fact"


def test_stable_fact_table() -> None:
    assert answer_national_fact("Quel est l'hymne national du Cameroun ?").key == "anthem"
    assert answer_national_fact("Quelles sont les langues officielles du Cameroun ?").key == "official_languages"
    assert answer_national_fact("Quelle est la devise du Cameroun ?").key == "motto"
    assert answer_national_fact("Qui est le président du Cameroun ?") is None


@pytest.mark.asyncio
async def test_president_question_gets_direct_web_answer() -> None:
    provider = FakeProvider(PRESIDENT_ROWS)
    orch = AgentOrchestrator(web_search=WebSearchService(provider), prefer_deterministic=True)
    result = await orch.run("Qui est le président du Cameroun ?", locale="fr")
    text = result.final_response.text
    assert provider.queries, "volatile facts must be checked online"
    assert "Paul Biya" in text
    assert "depuis le 6 novembre 1982" in text, "French snippet preferred for a French question"
    assert "indiquez-moi une ville" not in text
    assert "Site:" not in text and "Place De L'indépendance" not in text


@pytest.mark.asyncio
async def test_direct_answer_prefers_reference_sites_over_social_media() -> None:
    rows = [
        _row(
            "President Paul Biya | Facebook",
            "https://www.facebook.com/PresidentPaulBiya",
            "President Paul Biya. 1123298 followers · 678 talking about this. Président de la République du Cameroun.",
        ),
        *PRESIDENT_ROWS,
    ]
    orch = AgentOrchestrator(web_search=WebSearchService(FakeProvider(rows)), prefer_deterministic=True)
    result = await orch.run("Qui est le président du Cameroun ?", locale="fr")
    text = result.final_response.text
    assert "followers" not in text and "facebook.com" not in text
    assert "Paul Biya" in text


@pytest.mark.asyncio
async def test_president_question_without_web_is_honest_not_clarifying() -> None:
    orch = AgentOrchestrator(web_search=WebSearchService(FakeProvider([])), prefer_deterministic=True)
    result = await orch.run("Qui est le président du Cameroun ?", locale="fr")
    text = result.final_response.text
    assert "pas pu vérifier" in text
    assert "préciser" not in text.casefold() and "ville" not in text.casefold()


@pytest.mark.asyncio
async def test_stable_fact_answered_from_kb_without_web() -> None:
    provider = FakeProvider(PRESIDENT_ROWS)
    orch = AgentOrchestrator(web_search=WebSearchService(provider), prefer_deterministic=True)
    result = await orch.run("Quand le Cameroun est-il devenu indépendant ?", locale="fr")
    assert "1er janvier 1960" in result.final_response.text
