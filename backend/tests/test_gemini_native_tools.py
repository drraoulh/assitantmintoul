"""Gemini native tools — Gemini decides; backend does not pre-classify needs_web."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import get_settings
from app.services.agents.intent.router import classify_intent
from app.services.agents.knowledge.gemini_merge import merge_gemini_into_knowledge
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.orchestrator import AgentOrchestrator
from app.services.agents.response.agent import ResponseGenerator
from app.services.gemini.gemini_config import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_TOOL_NAMES,
    load_gemini_config,
)
from app.services.gemini.gemini_tools import (
    UNVERIFIED_NOTICE_FR,
    ensure_unverified_notice,
    extract_tools_used,
    extract_web_and_maps,
    native_tool_declarations,
)
from app.services.gemini.gemini_types import (
    GeminiGenerateRequest,
    GeminiMapResult,
    GeminiResult,
    GeminiServiceError,
    GeminiWebSource,
)


@pytest.fixture(autouse=True)
def _reset_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_model_comes_from_central_config(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    get_settings.cache_clear()
    cfg = load_gemini_config()
    assert cfg.model == "gemini-3.5-flash-lite"
    assert cfg.model == DEFAULT_GEMINI_MODEL
    client_src = Path(__file__).resolve().parents[1] / "app" / "services" / "gemini" / "gemini_client.py"
    assert "gemini-3.5-flash-lite" not in client_src.read_text(encoding="utf-8")


def test_flags_default_off():
    from app.core.config import Settings

    assert Settings.model_fields["gemini_chat_enabled"].default is False
    assert Settings.model_fields["gemini_tools_enabled"].default is False
    assert Settings.model_fields["gemini_voice_enabled"].default is False
    assert Settings.model_fields["gemini_fallback_to_qwen"].default is True


def test_native_tools_declared_not_forced():
    tools = native_tool_declarations(list(DEFAULT_TOOL_NAMES))
    assert {"googleSearch": {}} in tools
    assert {"googleMaps": {}} in tools
    assert native_tool_declarations([]) == []


def test_extract_tools_used_from_grounding():
    payload = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Palais des Sultans à Foumban."}]},
                "groundingMetadata": {
                    "webSearchQueries": ["que visiter à Foumban"],
                    "groundingChunks": [
                        {
                            "web": {
                                "title": "Palais des Rois Bamoun",
                                "uri": "https://example.org/foumban",
                            }
                        },
                        {
                            "maps": {
                                "title": "Palais de Foumban",
                                "placeId": "ChIJxxxx",
                                "uri": "https://maps.google.com/?cid=1",
                            }
                        },
                    ],
                },
            }
        ]
    }
    assert extract_tools_used(payload) == ["google_search", "google_maps"]
    web, maps = extract_web_and_maps(payload)
    assert web[0]["url"] == "https://example.org/foumban"
    assert maps[0]["place_id"] == "ChIJxxxx"


def test_greeting_payload_has_empty_tools_used():
    payload = {"candidates": [{"content": {"parts": [{"text": "Bonjour !"}]}}]}
    assert extract_tools_used(payload) == []


def test_unverified_notice_only_without_tools():
    text = ensure_unverified_notice("Le mont Cameroun est un volcan.", [], "fr")
    assert UNVERIFIED_NOTICE_FR in text
    sourced = ensure_unverified_notice("Palais royal à Foumban.", ["google_search"], "fr")
    assert UNVERIFIED_NOTICE_FR not in sourced


def test_merge_gemini_into_knowledge_structure():
    base = KnowledgeResult(query="Que visiter à Foumban ?", intent="PLACE_SEARCH")
    gemini = GeminiResult(
        text="Visitez le palais royal de Foumban.",
        model=DEFAULT_GEMINI_MODEL,
        tools_used=["google_search"],
        web_sources=[
            GeminiWebSource(title="Palais", url="https://example.org/palais"),
        ],
        map_results=[GeminiMapResult(title="Palais de Foumban", place_id="p1")],
    )
    merged = merge_gemini_into_knowledge(base, gemini)
    assert merged.answer_context
    assert merged.gemini_answer.startswith("Visitez")
    assert merged.tools_used == ["google_search"]
    assert merged.web_sources
    assert merged.map_results
    assert merged.sources


@pytest.mark.asyncio
async def test_agent4_uses_gemini_answer_without_qwen():
    intent = classify_intent("Que visiter à Foumban ?", locale="fr")
    knowledge = KnowledgeResult(
        query="Que visiter à Foumban ?",
        intent=intent.intent,
        gemini_answer="À Foumban, le palais royal des sultans bamoun est le site majeur.",
        tools_used=["google_search"],
        sources=[],
        confidence=0.8,
    )

    async def _boom(_messages):
        raise AssertionError("Qwen must not be called when Gemini already answered")

    agent = ResponseGenerator(llm_complete=_boom, prefer_deterministic=False)
    result = await agent.generate(
        "Que visiter à Foumban ?",
        intent,
        knowledge,
        response_mode="text",
        locale="fr",
        request_id="g1",
    )
    assert "palais" in result.text.casefold()
    assert result.tools_used == ["google_search"]
    assert result.fallback_used is False


@pytest.mark.asyncio
async def test_agent1_extracts_foumban_without_forcing_tools():
    result = classify_intent("Que visiter à Foumban ?", locale="fr")
    assert (result.location or result.city or "").casefold().find("foumban") >= 0
    greeting = classify_intent("Bonjour", locale="fr")
    assert greeting.reason.endswith("greeting") or greeting.intent == "SIMPLE_QA"


@pytest.mark.asyncio
async def test_orchestrator_gemini_off_does_not_call_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_CHAT_ENABLED", "false")
    get_settings.cache_clear()
    orch = AgentOrchestrator(prefer_deterministic=True)
    with patch(
        "app.services.gemini.service.GeminiService.generate",
        new_callable=AsyncMock,
    ) as mocked:
        result = await orch.run("Bonjour", locale="fr", request_id="off1")
    mocked.assert_not_called()
    assert "gemini" not in result.agents_called
    assert result.tools_used == []
    assert result.final_response.text


@pytest.mark.asyncio
async def test_orchestrator_gemini_observes_tools_used(monkeypatch):
    monkeypatch.setenv("GEMINI_CHAT_ENABLED", "true")
    monkeypatch.setenv("GEMINI_TOOLS_ENABLED", "true")
    get_settings.cache_clear()

    fake = GeminiResult(
        text="À Foumban, visitez le palais royal des sultans bamoun.",
        model=DEFAULT_GEMINI_MODEL,
        tools_used=["google_search"],
        web_sources=[GeminiWebSource(title="Palais", url="https://example.org/palais")],
    )
    orch = AgentOrchestrator(prefer_deterministic=True)
    with patch(
        "app.services.gemini.service.GeminiService.generate",
        new_callable=AsyncMock,
        return_value=fake,
    ) as mocked:
        result = await orch.run("Que visiter à Foumban ?", locale="fr", request_id="on1")
    mocked.assert_called_once()
    request = mocked.call_args.args[0]
    assert isinstance(request, GeminiGenerateRequest)
    assert set(request.enabled_tools) == {"google_search", "google_maps"}
    assert result.tools_used == ["google_search"]
    assert "palais" in result.final_response.text.casefold()
    assert result.knowledge and result.knowledge.web_sources
    assert "web_research" not in result.agents_called


@pytest.mark.asyncio
async def test_orchestrator_greeting_does_not_require_a_tool(monkeypatch):
    monkeypatch.setenv("GEMINI_CHAT_ENABLED", "true")
    monkeypatch.setenv("GEMINI_TOOLS_ENABLED", "true")
    get_settings.cache_clear()

    fake = GeminiResult(
        text="Bonjour ! Je peux vous aider à préparer un séjour au Cameroun.",
        model=DEFAULT_GEMINI_MODEL,
        tools_used=[],
    )
    orch = AgentOrchestrator(prefer_deterministic=True)
    with patch(
        "app.services.gemini.service.GeminiService.generate",
        new_callable=AsyncMock,
        return_value=fake,
    ) as mocked:
        result = await orch.run("Bonjour", locale="fr", request_id="hi1")
    mocked.assert_called_once()
    # Observe only — do not force google_search for a greeting.
    assert result.tools_used == []
    assert "bonjour" in result.final_response.text.casefold()
    assert "web_research" not in result.agents_called


@pytest.mark.asyncio
async def test_gemini_failure_falls_back_to_qwen_once(monkeypatch):
    monkeypatch.setenv("GEMINI_CHAT_ENABLED", "true")
    monkeypatch.setenv("GEMINI_FALLBACK_TO_QWEN", "true")
    get_settings.cache_clear()

    orch = AgentOrchestrator(prefer_deterministic=True)
    with patch(
        "app.services.gemini.service.GeminiService.generate",
        new_callable=AsyncMock,
        side_effect=GeminiServiceError("quota", status_code=429),
    ) as mocked:
        result = await orch.run("Que visiter à Foumban ?", locale="fr", request_id="fb1")
    mocked.assert_called_once()
    assert result.final_response.text
    assert result.tools_used == []
    assert "gemini" in result.agents_called
    # One user-facing answer only — no second Gemini call.
    assert mocked.call_count == 1
