"""Phase 2.7 — grounding enforcement & hallucination guard tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult, PlaceEvidence
from app.services.agents.planner.models import PlanDay, PlanItem, TourismPlan
from app.services.agents.response.agent import ResponseGenerator
from app.services.agents.response.context import build_structured_context
from app.services.agents.response.evidence import (
    build_allowed_evidence,
    evidence_is_insufficient_for_llm,
)
from app.services.agents.response.fallback import render_deterministic
from app.services.agents.response.grounding_enforcement import (
    HALLUCINATION_WATCHLIST,
    validate_grounding,
)
from app.services.agents.response.prompts import agent4_system_prompt


def _food_intent(**kwargs) -> IntentResult:
    base = dict(
        intent="FOOD",
        city="Yaoundé",
        needs_knowledge=True,
        needs_places=True,
        confidence=0.9,
        language="en",
    )
    base.update(kwargs)
    return IntentResult(**base)


def _empty_knowledge(intent: str = "FOOD") -> KnowledgeResult:
    return KnowledgeResult(
        query="q",
        intent=intent,
        places=[],
        source="empty",
        confidence=0.1,
        missing_information=["matching_places"],
    )


def test_unknown_restaurant_no_invention(monkeypatch):
    monkeypatch.setenv("GROUNDING_ENFORCEMENT_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    intent = _food_intent()
    knowledge = _empty_knowledge()
    assert evidence_is_insufficient_for_llm(intent, knowledge, None) is True

    async def boom(_messages):
        raise AssertionError("LLM must not be called")

    agent = ResponseGenerator(llm_complete=boom, prefer_deterministic=False)

    async def _run():
        return await agent.generate(
            "I want to eat fish.",
            intent,
            knowledge,
            None,
            response_mode="text",
            locale="en",
        )

    final = asyncio.run(_run())
    text = final.text.casefold()
    assert "african food by emy" not in text
    assert "taste of afrka" not in text
    assert final.fallback_used is True
    assert final.grounding_ok is True
    get_settings.cache_clear()
    monkeypatch.delenv("GROUNDING_ENFORCEMENT_ENABLED", raising=False)
    get_settings.cache_clear()


def test_known_restaurant_may_be_mentioned():
    knowledge = KnowledgeResult(
        query="fish",
        intent="FOOD",
        places=[
            PlaceEvidence(
                place_id="r1",
                name="Restaurant A",
                city="Yaoundé",
                category=["restaurant"],
                is_published=True,
            )
        ],
        source="structured",
        confidence=0.8,
    )
    text = render_deterministic(
        "I want to eat fish.",
        _food_intent(),
        knowledge,
        None,
        language="en",
    )
    assert "Restaurant A" in text
    ev = build_allowed_evidence(_food_intent(), knowledge, None)
    report = validate_grounding(text, ev, enforcement_enabled=True)
    assert report.ok is True


def test_unknown_place_mbingo_rejected():
    knowledge = KnowledgeResult(
        query="foumban",
        intent="ITINERARY",
        places=[
            PlaceEvidence(
                place_id="p1",
                name="Palais des Rois Bamoun",
                city="Foumban",
                is_published=True,
            )
        ],
        source="structured",
        confidence=0.8,
    )
    ev = build_allowed_evidence(
        IntentResult(intent="ITINERARY", city="Foumban", confidence=0.9),
        knowledge,
        None,
    )
    bad = "Visitez aussi les ruines de Mbingo et le village de Kimbi."
    report = validate_grounding(bad, ev, enforcement_enabled=True)
    assert report.ok is False
    assert report.critical is True
    kinds = {v.kind for v in report.violations}
    assert "unauthorized_place" in kinds


def test_itinerary_whitelist_rejects_kimbi():
    plan = TourismPlan(
        plan_type="ITINERARY",
        duration_days=2,
        feasibility="FEASIBLE",
        selected_places=["p1", "p2"],
        days=[
            PlanDay(
                day=1,
                title="Jour 1",
                places=[
                    PlanItem(place_id="p1", place_name="Palace", order=1),
                ],
            ),
            PlanDay(
                day=2,
                title="Jour 2",
                places=[
                    PlanItem(place_id="p2", place_name="Museum", order=1),
                ],
            ),
        ],
        confidence=0.8,
    )
    knowledge = KnowledgeResult(
        query="foumban",
        intent="ITINERARY",
        places=[
            PlaceEvidence(place_id="p1", name="Palace", is_published=True),
            PlaceEvidence(place_id="p2", name="Museum", is_published=True),
        ],
        source="structured",
        confidence=0.8,
    )
    ev = build_allowed_evidence(
        IntentResult(intent="ITINERARY", duration_days=2, confidence=0.9),
        knowledge,
        plan,
    )
    assert "palace" in ev.place_names_folded
    assert "museum" in ev.place_names_folded
    text = "Day 1 Palace. Day 2 Museum. Also visit Kimbi."
    report = validate_grounding(text, ev, enforcement_enabled=True)
    assert any(v.detail == "kimbi" for v in report.violations)


def test_unknown_price_invented():
    knowledge = KnowledgeResult(
        query="prix",
        intent="PLACE_DETAILS",
        places=[
            PlaceEvidence(
                place_id="p1",
                name="Musée",
                estimated_cost_xaf=None,
                is_published=True,
            )
        ],
        source="structured",
        confidence=0.7,
        missing_information=["estimated_cost_xaf"],
    )
    ev = build_allowed_evidence(
        IntentResult(intent="PLACE_DETAILS", confidence=0.9),
        knowledge,
        None,
    )
    report = validate_grounding(
        "L'entrée coûte probablement 2000 FCFA.",
        ev,
        enforcement_enabled=True,
    )
    assert report.ok is False
    assert any(v.kind == "unauthorized_price" for v in report.violations)


def test_known_price_allowed():
    knowledge = KnowledgeResult(
        query="prix",
        intent="PLACE_DETAILS",
        places=[
            PlaceEvidence(
                place_id="p1",
                name="Musée",
                estimated_cost_xaf=5000,
                is_published=True,
            )
        ],
        source="structured",
        confidence=0.8,
    )
    ev = build_allowed_evidence(
        IntentResult(intent="PLACE_DETAILS", confidence=0.9),
        knowledge,
        None,
    )
    report = validate_grounding(
        "Le coût estimé est de 5000 FCFA.",
        ev,
        enforcement_enabled=True,
    )
    assert report.ok is True


def test_unknown_opening_hours():
    knowledge = KnowledgeResult(
        query="horaires",
        intent="PLACE_DETAILS",
        places=[
            PlaceEvidence(place_id="p1", name="Musée", is_published=True),
        ],
        source="structured",
        confidence=0.7,
        missing_information=["opening_hours"],
    )
    ev = build_allowed_evidence(
        IntentResult(intent="PLACE_DETAILS", confidence=0.9),
        knowledge,
        None,
    )
    report = validate_grounding(
        "Le site est ouvert de 8h à 18h.",
        ev,
        enforcement_enabled=True,
    )
    assert any(v.kind == "unauthorized_hours" for v in report.violations)


def test_unknown_activity_not_in_evidence_context():
    ctx = build_structured_context(
        "activités",
        IntentResult(intent="PLACE_DETAILS", confidence=0.9),
        KnowledgeResult(
            query="a",
            intent="PLACE_DETAILS",
            places=[
                PlaceEvidence(
                    place_id="p1",
                    name="Palais",
                    activities=["visite guidée"],
                    is_published=True,
                )
            ],
            source="structured",
            confidence=0.8,
        ),
        None,
    )
    allowed_acts = ctx["allowed_evidence"]["known_activities"]
    assert any("visite" in a.casefold() for a in allowed_acts)
    assert "pêche sous-marine" not in " ".join(allowed_acts).casefold()


def test_geographic_distance_wording():
    plan = TourismPlan(
        plan_type="ITINERARY",
        duration_days=1,
        feasibility="FEASIBLE",
        selected_places=["p1", "p2"],
        days=[
            PlanDay(
                day=1,
                title="Jour 1",
                places=[
                    PlanItem(place_id="p1", place_name="A", order=1),
                    PlanItem(
                        place_id="p2",
                        place_name="B",
                        order=2,
                        distance_from_previous_km=12.4,
                    ),
                ],
            )
        ],
        confidence=0.8,
    )
    knowledge = KnowledgeResult(
        query="plan",
        intent="ITINERARY",
        places=[
            PlaceEvidence(place_id="p1", name="A", is_published=True),
            PlaceEvidence(place_id="p2", name="B", is_published=True),
        ],
        source="structured",
        confidence=0.8,
    )
    text = render_deterministic(
        "itinéraire",
        IntentResult(intent="ITINERARY", duration_days=1, confidence=0.9),
        knowledge,
        plan,
        language="fr",
        response_mode="text",
    )
    assert "vol d'oiseau" in text.casefold()
    assert "par la route" not in text.casefold()
    ev = build_allowed_evidence(
        IntentResult(intent="ITINERARY", confidence=0.9),
        knowledge,
        plan,
    )
    road = "Ensuite 12,4 km par la route vers B."
    report = validate_grounding(road, ev, enforcement_enabled=True)
    assert any(v.kind == "distance_mislabel" for v in report.violations)


def test_unknown_hotel_insufficient():
    intent = IntentResult(
        intent="HOTEL",
        city="Yaoundé",
        needs_places=True,
        confidence=0.9,
        language="fr",
    )
    knowledge = _empty_knowledge("HOTEL")
    assert evidence_is_insufficient_for_llm(intent, knowledge, None) is True
    text = render_deterministic(
        "hôtel",
        intent,
        knowledge,
        None,
        language="fr",
    )
    assert "vérif" in text.casefold() or "disponib" in text.casefold() or "peu" in text.casefold()


def test_unknown_availability():
    ev = build_allowed_evidence(
        IntentResult(intent="BOOKING", confidence=0.9),
        _empty_knowledge("BOOKING"),
        None,
    )
    report = validate_grounding(
        "Il reste 3 chambres disponibles demain.",
        ev,
        enforcement_enabled=True,
    )
    assert any(v.kind == "unauthorized_availability" for v in report.violations)


def test_africa_in_miniature_blocked_when_absent():
    ev = build_allowed_evidence(
        IntentResult(intent="TOURISM_INFO", confidence=0.9),
        KnowledgeResult(
            query="cameroun",
            intent="TOURISM_INFO",
            places=[],
            knowledge=[],
            source="empty",
            confidence=0.2,
        ),
        None,
    )
    assert not ev.allowed_slogans
    report = validate_grounding(
        "Le Cameroun est l'Afrique en miniature.",
        ev,
        enforcement_enabled=True,
    )
    assert any(v.kind == "unauthorized_slogan" for v in report.violations)


def test_web_evidence_allows_restaurant_x():
    from app.services.agents.knowledge.models import KnowledgeEvidence

    knowledge = KnowledgeResult(
        query="resto",
        intent="WEB_SEARCH",
        places=[],
        knowledge=[
            KnowledgeEvidence(
                chunk_id="w1",
                content="[web evidence — unverified] Restaurant X serves grilled fish.",
                source_id="https://example.com/x",
                title="web",
                score=0.35,
            )
        ],
        source="hybrid",
        confidence=0.5,
        web_needed=True,
    )
    # Web snippet is not a PlaceEvidence — LLM may mention Restaurant X from chunk.
    # Deterministic validator mainly blocks watchlist + catalog; Restaurant X not watchlisted.
    ev = build_allowed_evidence(
        IntentResult(intent="WEB_SEARCH", needs_web=True, confidence=0.9),
        knowledge,
        None,
    )
    assert ev.has_web_evidence is True
    report = validate_grounding(
        "You can try Restaurant X for grilled fish.",
        ev,
        enforcement_enabled=True,
    )
    # Not in watchlist / catalog → ok for this lightweight check
    assert report.ok is True
    # Watchlisted invention still blocked
    bad = validate_grounding(
        "Try African Food By Emy instead.",
        ev,
        enforcement_enabled=True,
    )
    assert bad.ok is False


def test_empty_knowledge_insufficient():
    text = render_deterministic(
        "lieux inconnus",
        IntentResult(intent="PLACE_SEARCH", city="Nowhere", confidence=0.9),
        _empty_knowledge("PLACE_SEARCH"),
        None,
        language="fr",
    )
    assert "vérif" in text.casefold() or "peu" in text.casefold()


def test_prompt_says_not_knowledge_source():
    prompt = agent4_system_prompt(language="en", response_mode="voice")
    assert "NOT a tourism knowledge source" in prompt or "NOT a knowledge source" in prompt
    assert "Never invent" in prompt or "never invent" in prompt.casefold()


def test_feature_flag_off_skips_enforcement(monkeypatch):
    monkeypatch.delenv("GROUNDING_ENFORCEMENT_ENABLED", raising=False)
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert get_settings().grounding_enforcement_enabled is False
    ev = build_allowed_evidence(
        IntentResult(intent="FOOD", confidence=0.9),
        _empty_knowledge(),
        None,
    )
    report = validate_grounding(
        "Try African Food By Emy in Yaoundé.",
        ev,
        enforcement_enabled=False,
    )
    assert report.ok is True
    assert report.enforcement_enabled is False
    get_settings.cache_clear()


def test_llm_replaced_on_critical_grounding(monkeypatch):
    monkeypatch.setenv("GROUNDING_ENFORCEMENT_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    knowledge = KnowledgeResult(
        query="foumban",
        intent="ITINERARY",
        places=[
            PlaceEvidence(
                place_id="p1",
                name="Palais des Rois Bamoun",
                is_published=True,
            )
        ],
        source="structured",
        confidence=0.8,
    )
    intent = IntentResult(
        intent="PLACE_SEARCH",
        city="Foumban",
        needs_places=True,
        confidence=0.9,
        language="fr",
    )

    async def invent(_messages):
        return "Visitez aussi Kimbi et les ruines de Mbingo."

    agent = ResponseGenerator(llm_complete=invent, prefer_deterministic=False)

    async def _run():
        return await agent.generate(
            "lieux à Foumban",
            intent,
            knowledge,
            None,
            response_mode="text",
            locale="fr",
        )

    final = asyncio.run(_run())
    assert "kimbi" not in final.text.casefold()
    assert "mbingo" not in final.text.casefold()
    assert final.fallback_used is True
    assert final.grounding_ok is True
    get_settings.cache_clear()
    monkeypatch.delenv("GROUNDING_ENFORCEMENT_ENABLED", raising=False)
    get_settings.cache_clear()


def test_streaming_regression_tokens_before_done_still_holds():
    """Sanity: Phase 2.6 overlap test module still importable / contract intact."""
    from app.services.ai.huggingface import HuggingFaceAIService

    assert hasattr(HuggingFaceAIService, "_stream_via_orchestrator_true_stream")


def test_max_one_llm_call_on_grounding_replace(monkeypatch):
    monkeypatch.setenv("GROUNDING_ENFORCEMENT_ENABLED", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    calls = {"n": 0}

    async def invent(_messages):
        calls["n"] += 1
        return "Try African Food By Emy for fish."

    agent = ResponseGenerator(llm_complete=invent, prefer_deterministic=False)
    knowledge = KnowledgeResult(
        query="fish",
        intent="FOOD",
        places=[
            PlaceEvidence(place_id="r1", name="Restaurant A", is_published=True),
        ],
        source="structured",
        confidence=0.8,
    )

    async def _run():
        return await agent.generate(
            "I want to eat fish.",
            _food_intent(),
            knowledge,
            None,
            response_mode="text",
            locale="en",
        )

    final = asyncio.run(_run())
    assert calls["n"] == 1
    assert "african food by emy" not in final.text.casefold()
    get_settings.cache_clear()
    monkeypatch.delenv("GROUNDING_ENFORCEMENT_ENABLED", raising=False)
    get_settings.cache_clear()


def test_watchlist_covers_observed_hallucinations():
    assert "mbingo" in HALLUCINATION_WATCHLIST
    assert "kimbi" in HALLUCINATION_WATCHLIST
    assert "african food by emy" in HALLUCINATION_WATCHLIST


def test_context_includes_allowed_evidence():
    ctx = build_structured_context(
        "q",
        IntentResult(intent="PLACE_SEARCH", city="Yaoundé", confidence=0.9),
        KnowledgeResult(
            query="q",
            intent="PLACE_SEARCH",
            places=[
                PlaceEvidence(place_id="1", name="Musée National", is_published=True),
            ],
            source="structured",
            confidence=0.8,
        ),
        None,
    )
    assert "allowed_evidence" in ctx
    assert "1" in ctx["allowed_evidence"]["allowed_place_ids"]
    assert "Musée National" in ctx["allowed_evidence"]["allowed_place_names"]
