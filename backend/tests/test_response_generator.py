"""Phase 2.4 Agent 4 — Response Generator mandatory tests."""

from __future__ import annotations

import asyncio
import re

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import (
    KnowledgeEvidence,
    KnowledgeResult,
    PlaceEvidence,
    SourceEvidence,
)
from app.services.agents.planner.models import PlanDay, PlanItem, TourismPlan
from app.services.agents.response.agent import ResponseGenerator, generate_response
from app.services.agents.response.compare import compare_response
from app.services.agents.response.context import allowed_place_names, build_structured_context
from app.services.agents.response.validate import (
    claims_road_distance,
    contains_invented_place,
    voice_text_is_clean,
)


def _intent(**kwargs) -> IntentResult:
    base = dict(
        intent="ITINERARY",
        confidence=0.9,
        needs_knowledge=True,
        needs_places=True,
        needs_planner=True,
        language="fr",
    )
    base.update(kwargs)
    return IntentResult(**base)  # type: ignore[arg-type]


def _place(pid: str, name: str, **kwargs) -> PlaceEvidence:
    data = dict(
        place_id=pid,
        name=name,
        city="Yaoundé",
        category=["Museum"],
        evidence_score=0.8,
        is_published=True,
    )
    data.update(kwargs)
    return PlaceEvidence(**data)  # type: ignore[arg-type]


def _knowledge(places=None, knowledge=None, **kwargs) -> KnowledgeResult:
    return KnowledgeResult(
        query=kwargs.get("query", "q"),
        intent=kwargs.get("intent", "ITINERARY"),
        places=places or [],
        knowledge=knowledge or [],
        sources=kwargs.get("sources", []),
        missing_information=kwargs.get("missing_information", []),
        confidence=kwargs.get("confidence", 0.8),
    )


def _plan(**kwargs) -> TourismPlan:
    days = kwargs.pop(
        "days",
        [
            PlanDay(
                day=1,
                title="Jour 1",
                places=[
                    PlanItem(place_id="A", place_name="Place A", order=1, estimated_cost_xaf=5000, estimated_duration_hours=2),
                ],
            ),
            PlanDay(
                day=2,
                title="Jour 2",
                places=[
                    PlanItem(place_id="B", place_name="Place B", order=1, estimated_cost_xaf=3000),
                ],
            ),
        ],
    )
    base = dict(
        plan_type="ITINERARY",
        duration_days=2,
        budget_status="WITHIN_BUDGET",
        feasibility="FEASIBLE",
        days=days,
        selected_places=["A", "B"],
        known_cost_xaf=8000,
        total_estimated_cost_xaf=8000,
        budget_xaf=150000,
        confidence=0.85,
    )
    base.update(kwargs)
    return TourismPlan(**base)  # type: ignore[arg-type]


def _run(coro):
    return asyncio.run(coro)


def test_simple_question_short_no_plan_noise():
    intent = _intent(intent="SIMPLE_QA", needs_planner=False, needs_places=False)
    knowledge = _knowledge(
        knowledge=[
            KnowledgeEvidence(
                chunk_id="k1",
                content="La capitale du Cameroun est Yaoundé.",
                title="Capitale",
                score=0.9,
            )
        ],
        intent="SIMPLE_QA",
    )
    final = _run(
        generate_response(
            "Quelle est la capitale du Cameroun ?",
            intent,
            knowledge,
            None,
            prefer_deterministic=True,
        )
    )
    assert final.response_type == "SIMPLE_ANSWER"
    assert "yaoundé" in final.text.casefold() or "yaounde" in final.text.casefold()
    assert "Jour 1" not in final.text
    assert len(final.text) < 600


def test_place_details_only_present_info():
    place = _place(
        "A",
        "Place A",
        description="Un musée national.",
        cultural_info="Patrimoine culturel.",
        estimated_cost_xaf=5000,
        recommended_duration_hours=2,
    )
    final = _run(
        generate_response(
            "Parle-moi de Place A.",
            _intent(intent="PLACE_DETAILS", needs_planner=False),
            _knowledge(places=[place], intent="PLACE_DETAILS"),
            None,
        )
    )
    assert "Place A" in final.text
    assert "5000" in final.text or "5 000" in final.text or "5000" in final.text.replace(" ", "")
    assert "08:00" not in final.text
    assert "taxi" not in final.text.casefold()


def test_itinerary_only_a_and_b():
    plan = _plan()
    knowledge = _knowledge(places=[_place("A", "Place A"), _place("B", "Place B")])
    final = _run(
        generate_response("itinéraire", _intent(duration_days=2), knowledge, plan)
    )
    assert "Place A" in final.text and "Place B" in final.text
    assert "Place C" not in final.text
    allowed = allowed_place_names(knowledge, plan)
    assert not contains_invented_place(final.text, allowed, {"Place C", "Parc XYZ"})


def test_no_invention_extra_place():
    knowledge = _knowledge(places=[_place("A", "Place A"), _place("B", "Place B")])
    plan = _plan()
    final = _run(generate_response("plan", _intent(), knowledge, plan))
    assert "Place C" not in final.text


def test_missing_cost_not_invented():
    place = _place("A", "Place A", estimated_cost_xaf=None, description="Site culturel.")
    plan = _plan(
        days=[
            PlanDay(
                day=1,
                title="Jour 1",
                places=[PlanItem(place_id="A", place_name="Place A", order=1, estimated_cost_xaf=None)],
            )
        ],
        selected_places=["A"],
        budget_status="PARTIAL",
        known_cost_xaf=0,
        total_estimated_cost_xaf=None,
        missing_information=["estimated_cost_xaf"],
    )
    final = _run(
        generate_response(
            "coût?",
            _intent(),
            _knowledge(places=[place], missing_information=["estimated_cost_xaf"]),
            plan,
        )
    )
    # Must not invent a specific fake price like 2500 for Place A
    assert not re.search(r"\b2500\b", final.text)
    assert not re.search(r"\b2\s*000\b", final.text)


def test_missing_opening_hours_not_invented():
    place = _place("A", "Place A", description="Musée.")
    final = _run(
        generate_response(
            "horaires?",
            _intent(intent="PLACE_DETAILS"),
            _knowledge(
                places=[place],
                missing_information=["opening_hours"],
                intent="PLACE_DETAILS",
            ),
            None,
        )
    )
    assert "08:00" not in final.text and "8h" not in final.text.casefold()


def test_budget_partial_wording():
    plan = _plan(
        budget_status="PARTIAL",
        known_cost_xaf=100000,
        total_estimated_cost_xaf=None,
        budget_xaf=150000,
    )
    knowledge = _knowledge(places=[_place("A", "Place A"), _place("B", "Place B")])
    final = _run(generate_response("budget", _intent(budget_xaf=150000), knowledge, plan))
    assert "100000" in final.text.replace(" ", "") or "100 000" in final.text
    assert "confirmé" in final.text.casefold() or "cannot be confirmed" in final.text.casefold() or "ne peut" in final.text.casefold()


def test_over_budget_wording():
    plan = _plan(
        budget_status="OVER_BUDGET",
        known_cost_xaf=180000,
        total_estimated_cost_xaf=180000,
        budget_xaf=150000,
    )
    knowledge = _knowledge(places=[_place("A", "Place A"), _place("B", "Place B")])
    final = _run(generate_response("budget", _intent(budget_xaf=150000), knowledge, plan))
    assert "dépassent" in final.text.casefold() or "exceed" in final.text.casefold()


def test_distance_as_crow_flies_not_road():
    plan = _plan(
        days=[
            PlanDay(
                day=1,
                title="Jour 1",
                places=[
                    PlanItem(place_id="A", place_name="Place A", order=1),
                    PlanItem(
                        place_id="B",
                        place_name="Place B",
                        order=2,
                        distance_from_previous_km=12.4,
                    ),
                ],
            )
        ]
    )
    knowledge = _knowledge(places=[_place("A", "Place A"), _place("B", "Place B")])
    final = _run(generate_response("distance", _intent(), knowledge, plan))
    assert "12.4" in final.text or "12,4" in final.text
    assert not claims_road_distance(final.text)
    assert "vol d'oiseau" in final.text.casefold() or "crow flies" in final.text.casefold()


def test_empty_knowledge_no_places_invented():
    final = _run(
        generate_response(
            "Que visiter ?",
            _intent(),
            _knowledge(places=[], knowledge=[]),
            TourismPlan(
                plan_type="EMPTY",
                duration_days=0,
                feasibility="INSUFFICIENT_DATA",
                budget_status="UNKNOWN",
                confidence=0.1,
            ),
        )
    )
    assert final.response_type == "INSUFFICIENT_INFORMATION"
    assert "Place A" not in final.text


def test_insufficient_data_acknowledged():
    plan = TourismPlan(
        plan_type="ITINERARY",
        duration_days=7,
        feasibility="INSUFFICIENT_DATA",
        budget_status="UNKNOWN",
        selected_places=[],
        days=[],
        confidence=0.1,
    )
    final = _run(
        generate_response("7 jours Nord", _intent(duration_days=7), _knowledge([]), plan)
    )
    assert "peu d'informations" in final.text.casefold() or "not have enough" in final.text.casefold() or "trop peu" in final.text.casefold()


def test_french_language():
    final = _run(
        generate_response(
            "Que visiter ?",
            _intent(language="fr", intent="PLACE_SEARCH", city="Yaoundé"),
            _knowledge(places=[_place("A", "Musée National")]),
            None,
            locale="fr",
        )
    )
    assert final.language == "fr"
    assert any(w in final.text.casefold() for w in ("lieu", "vérifi", "musée", "parmi", "option"))


def test_english_language():
    final = _run(
        generate_response(
            "What to visit?",
            _intent(language="en", intent="PLACE_SEARCH", city="Yaoundé"),
            _knowledge(places=[_place("A", "National Museum")]),
            None,
            locale="en",
        )
    )
    assert final.language == "en"
    assert "listed in smartmboa" in final.text.casefold() or "include" in final.text.casefold()


def test_voice_mode_clean():
    plan = _plan()
    knowledge = _knowledge(places=[_place("A", "Place A"), _place("B", "Place B")])
    final = _run(
        generate_response(
            "itinéraire vocal",
            _intent(),
            knowledge,
            plan,
            response_mode="voice",
        )
    )
    assert final.response_mode == "voice"
    assert voice_text_is_clean(final.text)
    assert "http" not in final.text
    assert "|" not in final.text


def test_source_not_invented():
    knowledge = _knowledge(
        places=[_place("A", "Place A")],
        sources=[SourceEvidence(source_id="src-1", name="MINTOUL", url="https://mintoul.gov.cm/")],
    )
    final = _run(
        generate_response(
            "source?",
            _intent(intent="PLACE_DETAILS"),
            knowledge,
            None,
        )
    )
    assert len(final.sources) == 1
    assert final.sources[0].source_id == "src-1"
    assert final.sources[0].url == "https://mintoul.gov.cm/"
    # No second invented source id
    assert all(s.source_id == "src-1" for s in final.sources)


def test_unknown_place_xyz():
    final = _run(
        generate_response(
            "Parle-moi du lieu XYZ.",
            _intent(intent="PLACE_DETAILS"),
            _knowledge(places=[], knowledge=[], intent="PLACE_DETAILS"),
            None,
        )
    )
    assert "volcan" not in final.text.casefold()
    assert "créé au 19" not in final.text.casefold()
    assert final.response_type in {"INSUFFICIENT_INFORMATION", "PLACE_DETAILS", "TOURISM_INFORMATION", "CLARIFICATION"}


def test_context_is_compact():
    places = [_place(f"P{i}", f"Place {i}", description="x" * 800) for i in range(20)]
    ctx = build_structured_context(
        "q",
        _intent(),
        _knowledge(places=places),
        _plan(),
    )
    assert len(ctx["places"]) <= 12
    assert all(len(p.get("description") or "") <= 321 for p in ctx["places"])


def test_compare_response_diagnostic():
    knowledge = _knowledge(places=[_place("A", "Place A"), _place("B", "Place B")])
    report = compare_response("cmp", _intent(), knowledge, _plan())
    assert report["invented_suspect"] is False
    assert "agent4" in report


def test_llm_failure_uses_fallback():
    async def boom(_messages):
        raise RuntimeError("llm down")

    agent = ResponseGenerator(llm_complete=boom, prefer_deterministic=False)
    final = _run(
        agent.generate(
            "itinéraire",
            _intent(),
            _knowledge(places=[_place("A", "Place A"), _place("B", "Place B")]),
            _plan(),
        )
    )
    assert final.fallback_used is True
    assert "Place A" in final.text
