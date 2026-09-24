"""Phase 2.5 — Agent Orchestrator integration tests."""

from __future__ import annotations

import asyncio
import statistics
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.agent import KnowledgeAgent
from app.services.agents.knowledge.models import KnowledgeResult, PlaceEvidence
from app.services.agents.knowledge.place_store import PlaceIndex, PlaceRecord
from app.services.agents.orchestrator import AgentOrchestrator, run_orchestration
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.models import FinalResponse
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
            cultural_info="Patrimoine culturel national.",
            categories=["Museum"],
            estimated_cost_xaf=2000,
            recommended_duration_hours=2.0,
            latitude=3.8667,
            longitude=11.5167,
            is_published=True,
            source_id="src-mintoul",
            source_name="MINTOUL",
        ),
        PlaceRecord(
            place_id="place-yaounde-2",
            name="Monument de la Réunification",
            city="Yaoundé",
            region="Centre",
            description="Monument emblématique de Yaoundé.",
            categories=["Monument"],
            estimated_cost_xaf=0,
            recommended_duration_hours=1.0,
            latitude=3.8570,
            longitude=11.5110,
            is_published=True,
            source_id="src-mintoul",
        ),
        PlaceRecord(
            place_id="place-yaounde-3",
            name="Bois Sainte-Anastasie",
            city="Yaoundé",
            region="Centre",
            description="Parc urbain de Yaoundé.",
            categories=["Park", "Natural"],
            eco_tags=["nature"],
            estimated_cost_xaf=1000,
            recommended_duration_hours=2.0,
            latitude=3.8700,
            longitude=11.5200,
            is_published=True,
        ),
        PlaceRecord(
            place_id="place-yaounde-4",
            name="Cathédrale Notre-Dame",
            city="Yaoundé",
            region="Centre",
            description="Cathédrale de Yaoundé.",
            categories=["Culture", "Monument"],
            estimated_cost_xaf=0,
            recommended_duration_hours=1.0,
            latitude=3.8630,
            longitude=11.5180,
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
    ]


def _agent() -> AgentOrchestrator:
    index = PlaceIndex(places=_fixture_places())
    rag = LocalRAGService(
        chunks=[
            KnowledgeChunk(
                id="doc:cam:1",
                title="Cameroun",
                text="Le Cameroun est un pays d'Afrique centrale.",
                source="data/documents/overview.md",
            )
        ]
    )
    return AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(index, rag=rag),
        prefer_deterministic=True,
        booking_available=False,
    )


def _run(coro):
    return asyncio.run(coro)


# --- Test 1: Greeting ---
def test_greeting_skips_knowledge_and_planner():
    orch = _agent()
    result = _run(orch.run("Bonjour", mode="text", locale="fr", request_id="t1"))
    assert "intent" in result.agents_called
    assert "response" in result.agents_called
    assert "knowledge" not in result.agents_called
    assert "planner" not in result.agents_called
    assert result.timings.knowledge_ms is None
    assert result.timings.planner_ms is None
    assert result.final_response.text.strip()
    assert result.timings.total_ms is not None


# --- Test 2: Place search ---
def test_place_search_calls_knowledge_not_planner():
    orch = _agent()
    result = _run(
        orch.run(
            "Quels sont les lieux touristiques à Yaoundé ?",
            mode="text",
            locale="fr",
            request_id="t2",
        )
    )
    assert result.agents_called == ["intent", "knowledge", "response"]
    assert result.intent.intent == "PLACE_SEARCH"
    assert result.knowledge is not None
    assert result.knowledge.places
    assert result.plan is None
    assert result.timings.planner_ms is None
    names = " ".join(p.name for p in result.knowledge.places).casefold()
    assert "yaound" in names or "musée" in names or "monument" in names


# --- Test 3: Place details ---
def test_place_details_uses_verified_source_only():
    orch = _agent()
    result = _run(
        orch.run(
            "Parle-moi du Musée National.",
            mode="text",
            locale="fr",
            request_id="t3",
        )
    )
    assert "intent" in result.agents_called
    assert "knowledge" in result.agents_called
    assert "planner" not in result.agents_called
    assert "response" in result.agents_called
    assert result.knowledge is not None
    # Only if present in sources — fixture includes Musée National.
    assert any("Musée" in p.name or "Museum" in (p.name or "") for p in result.knowledge.places)
    assert "Site secret" not in result.final_response.text


# --- Test 4: Itinerary ---
def test_itinerary_calls_all_four_agents():
    orch = _agent()
    result = _run(
        orch.run(
            "Fais-moi un programme de 3 jours à Yaoundé.",
            mode="text",
            locale="fr",
            request_id="t4",
        )
    )
    assert result.agents_called == ["intent", "knowledge", "planner", "response"]
    assert result.intent.needs_planner is True
    assert result.plan is not None
    assert result.plan.duration_days == 3
    known_ids = {p.place_id for p in (result.knowledge.places if result.knowledge else [])}
    for pid in result.plan.selected_places:
        assert pid in known_ids


# --- Test 5: Budget ---
def test_budget_trip_preserves_known_limits():
    orch = _agent()
    result = _run(
        orch.run(
            "Nous sommes 4 personnes avec 150000 FCFA pour 3 jours à Yaoundé.",
            mode="text",
            locale="fr",
            request_id="t5",
        )
    )
    assert result.agents_called == ["intent", "knowledge", "planner", "response"]
    assert result.intent.intent == "BUDGET_TRIP"
    assert result.plan is not None
    assert result.plan.budget_xaf == 150000
    assert result.plan.budget_status in {
        "WITHIN_BUDGET",
        "OVER_BUDGET",
        "PARTIAL",
        "UNKNOWN",
    }
    # Do not invent costs beyond knowledge places.
    for day in result.plan.days:
        for item in day.places:
            assert item.place_id in {
                p.place_id for p in (result.knowledge.places if result.knowledge else [])
            }


# --- Test 6: Clarification ---
def test_clarification_skips_knowledge_and_planner():
    orch = _agent()
    result = _run(
        orch.run("Organise mon voyage.", mode="text", locale="fr", request_id="t6")
    )
    assert result.intent.intent == "CLARIFICATION"
    assert "knowledge" not in result.agents_called
    assert "planner" not in result.agents_called
    assert "response" in result.agents_called
    text = result.final_response.text.casefold()
    assert any(
        token in text
        for token in ("préciser", "combien", "ville", "région", "jours", "looking", "days", "city")
    )


# --- Test 7: Insufficient knowledge → skip planner ---
def test_insufficient_knowledge_skips_planner():
    orch = _agent()

    empty = KnowledgeResult(
        query="itinéraire",
        intent="ITINERARY",
        places=[],
        knowledge=[],
        sources=[],
        missing_information=["matching_places"],
        confidence=0.1,
        source="empty",
    )

    async def _fake_retrieve(query, intent, request_id=None):
        return empty

    with patch.object(orch, "_run_knowledge", side_effect=_fake_retrieve):
        # Force needs_planner path via intent classify — use a query that needs planner
        # but inject empty knowledge.
        intent = IntentResult(
            intent="ITINERARY",
            city="Yaoundé",
            duration_days=3,
            needs_knowledge=True,
            needs_places=True,
            needs_planner=True,
            confidence=0.9,
            request_id="t7",
        )
        with patch(
            "app.services.agents.orchestrator.orchestrator.classify_intent",
            return_value=intent,
        ):
            result = _run(orch.run("3 jours à Yaoundé", request_id="t7"))

    assert "knowledge" in result.agents_called
    assert "planner" not in result.agents_called
    assert "response" in result.agents_called
    assert result.plan is None
    assert result.final_response.response_type in {
        "INSUFFICIENT_INFORMATION",
        "ITINERARY",
        "SIMPLE_ANSWER",
    }
    assert "vérif" in result.final_response.text.casefold() or "enough" in result.final_response.text.casefold() or "fiable" in result.final_response.text.casefold()


# --- Test 8: Agent 3 NOT_FEASIBLE preserved ---
def test_not_feasible_preserved_by_agent4():
    orch = _agent()
    not_feasible = TourismPlan(
        plan_type="ITINERARY",
        duration_days=3,
        feasibility="NOT_FEASIBLE",
        budget_status="OVER_BUDGET",
        budget_xaf=1000,
        selected_places=[],
        days=[],
        warnings=["budget too low for verified places"],
        missing_information=["affordable_places"],
        confidence=0.4,
    )

    intent = IntentResult(
        intent="BUDGET_TRIP",
        city="Yaoundé",
        duration_days=3,
        budget_xaf=1000,
        needs_knowledge=True,
        needs_places=True,
        needs_planner=True,
        confidence=0.9,
    )
    knowledge = KnowledgeResult(
        query="budget",
        intent="BUDGET_TRIP",
        places=[
            PlaceEvidence(
                place_id="place-yaounde-1",
                name="Musée National du Cameroun",
                city="Yaoundé",
                estimated_cost_xaf=2000,
                is_published=True,
                evidence_score=0.9,
            )
        ],
        source="structured",
        confidence=0.8,
    )

    with patch(
        "app.services.agents.orchestrator.orchestrator.classify_intent",
        return_value=intent,
    ):
        with patch.object(
            orch,
            "_run_knowledge",
            AsyncMock(return_value=knowledge),
        ):
            with patch.object(orch._planner, "plan", return_value=not_feasible):
                result = _run(orch.run("budget trip", request_id="t8"))

    assert result.plan is not None
    assert result.plan.feasibility == "NOT_FEASIBLE"
    assert result.plan.budget_status == "OVER_BUDGET"
    text = result.final_response.text.casefold()
    assert "réalisable" in text or "feasible" in text or "budget" in text


# --- Test 9: No invented places ---
def test_no_invented_place_in_response():
    orch = _agent()
    result = _run(
        orch.run(
            "Quels sont les lieux touristiques à Yaoundé ?",
            mode="text",
            locale="fr",
            request_id="t9",
        )
    )
    known_names = {p.name for p in (result.knowledge.places if result.knowledge else [])}
    # Unpublished / fake names must not appear.
    assert "Site secret non publié" not in result.final_response.text
    assert "Disneyland" not in result.final_response.text
    assert "Tour Eiffel" not in result.final_response.text
    # Every place mentioned from knowledge stays within known set when listing.
    for name in known_names:
        # Names from knowledge may appear; that is fine.
        assert name  # placate lint
    allowed = " ".join(known_names).casefold()
    # If response lists a fixture place, it must be in knowledge.
    for token in ("Musée National", "Monument de la Réunification", "Bois Sainte"):
        if token.casefold() in result.final_response.text.casefold():
            assert token.casefold() in allowed or any(
                token.casefold() in n.casefold() for n in known_names
            )


# --- Test 10: Voice streaming contract ---
def test_voice_mode_streams_tokens_via_pipeline_shape():
    """Orchestrator voice path yields FinalResponse text usable as stream tokens."""
    orch = _agent()
    result = _run(
        orch.run("Bonjour", mode="voice", locale="fr", request_id="t10")
    )
    assert result.mode == "voice"
    assert result.final_response.response_mode == "voice"
    text = result.final_response.text.strip()
    assert text
    # Simulate WS fake-stream: word tokens (same as huggingface helper).
    tokens = []
    parts = text.split(" ")
    for i, word in enumerate(parts):
        tokens.append(word if i == 0 else f" {word}")
    assert "".join(tokens).strip() == text
    # Deterministic path: no LLM generation timing expected.
    assert result.final_response.llm_generation_ms is None or result.final_response.fallback_used


def test_booking_without_provider_skips_knowledge():
    orch = _agent()
    result = _run(
        orch.run(
            "Je veux réserver un hôtel à Yaoundé.",
            mode="text",
            locale="fr",
            request_id="t-book",
        )
    )
    assert result.intent.intent == "BOOKING"
    assert "knowledge" not in result.agents_called
    assert "planner" not in result.agents_called
    text = result.final_response.text.casefold()
    assert "disponib" in text or "réservation" in text or "booking" in text or "availability" in text
    assert "confirmé" in text or "confirmed" in text or "pas encore" in text or "not" in text


def test_timings_none_when_skipped():
    orch = _agent()
    result = _run(orch.run("Bonjour", request_id="t-timing"))
    assert result.timings.intent_ms is not None
    assert result.timings.response_ms is not None
    assert result.timings.total_ms is not None
    assert result.timings.knowledge_ms is None
    assert result.timings.planner_ms is None
    assert result.timings.vision_ms is None
    assert result.timings.web_ms is None


def test_module_entry_point():
    result = _run(
        run_orchestration(
            "Bonjour",
            mode="text",
            locale="fr",
            prefer_deterministic=True,
            knowledge_agent=KnowledgeAgent(PlaceIndex(places=_fixture_places())),
        )
    )
    assert isinstance(result.final_response, FinalResponse)
    assert "intent" in result.agents_called


def test_orchestrator_benchmark_paths_are_fast():
    """Deterministic Agent1→4 / 1→2→4 / 1→2→3→4 stay under soft caps (no LLM)."""
    orch = _agent()
    cases = [
        ("Bonjour", {"intent", "response"}),
        ("Quels sont les lieux touristiques à Yaoundé ?", {"intent", "knowledge", "response"}),
        (
            "Fais-moi un programme de 3 jours à Yaoundé.",
            {"intent", "knowledge", "planner", "response"},
        ),
    ]
    for query, expected in cases:
        samples = []
        for _ in range(5):
            t0 = time.perf_counter()
            result = _run(orch.run(query, request_id="bench"))
            samples.append((time.perf_counter() - t0) * 1000.0)
            assert set(expected).issubset(set(result.agents_called))
        median = statistics.median(samples)
        # Soft ceiling: deterministic stack should stay well under 500ms locally.
        assert median < 500.0, f"{query!r} median {median:.1f}ms too slow"


@pytest.mark.asyncio
async def test_huggingface_orchestrator_flag_streams_tokens(monkeypatch):
    """When AGENT_ORCHESTRATOR_ENABLED, stream_response uses orchestrator + token events."""
    from app.core.config import get_settings
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.conversation.memory import InMemoryConversationStore

    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "true")
    get_settings.cache_clear()

    store = InMemoryConversationStore()
    svc = HuggingFaceAIService(
        api_token="test-token",
        conversation_store=store,
        rag_service=LocalRAGService(chunks=[]),
    )

    class _FixtureOrchestrator(AgentOrchestrator):
        def __init__(self, *args, **kwargs):
            super().__init__(
                knowledge_agent=KnowledgeAgent(PlaceIndex(places=_fixture_places())),
                prefer_deterministic=True,
                booking_available=False,
            )

    events: list[dict[str, Any]] = []
    with patch(
        "app.services.agents.orchestrator.AgentOrchestrator",
        _FixtureOrchestrator,
    ):
        async for event in svc.stream_response(
            "Bonjour",
            brief=True,
            locale="fr",
            turn_id="voice-1",
        ):
            events.append(event)

    types = [e.get("type") for e in events]
    assert "route" in types
    assert "token" in types
    assert "done" in types
    assert "error" not in types
    done = next(e for e in events if e["type"] == "done")
    assert done.get("text")
    assert "orchestrator" in done

    get_settings.cache_clear()
    monkeypatch.delenv("AGENT_ORCHESTRATOR_ENABLED", raising=False)
    get_settings.cache_clear()
