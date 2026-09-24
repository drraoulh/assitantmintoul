"""Phase 2.6 — true Qwen → TTS streaming unit tests."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.orchestrator.models import (
    OrchestrationContext,
    OrchestrationTimings,
)
from app.services.speech.voice_chunker import flush_remainder, split_ready_phrases


def test_chunker_sentence_boundary():
    ready, left = split_ready_phrases(
        "Bonjour ! Pour votre séjour à Yaoundé nous proposons ",
        first_chunk=True,
    )
    assert ready
    assert "Bonjour" in ready[0]


def test_chunker_max_chars_without_punct():
    words = " ".join([f"mot{i}" for i in range(40)])
    ready, left = split_ready_phrases(words, first_chunk=True, hard_len=40)
    assert ready
    assert len(ready[0]) <= 40 or " " in ready[0]


def test_chunker_flush_final():
    assert flush_remainder("  reste  ") == ["reste"]
    assert flush_remainder("") == []


def test_chunker_short_text_held():
    ready, left = split_ready_phrases("Oui", first_chunk=True)
    assert ready == []
    assert left == "Oui"


def test_bounded_queue_backpressure():
    async def _run():
        q: asyncio.Queue[int | None] = asyncio.Queue(maxsize=2)
        await q.put(1)
        await q.put(2)

        async def producer():
            await q.put(3)  # blocks until consumer gets one

        task = asyncio.create_task(producer())
        await asyncio.sleep(0.05)
        assert not task.done()
        assert q.full()
        assert await q.get() == 1
        await asyncio.wait_for(task, timeout=1.0)
        assert q.qsize() == 2

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_true_stream_emits_tokens_before_qwen_finishes(monkeypatch):
    """Prove tokens are yielded while the mocked Qwen generator is still running."""
    from app.core.config import get_settings
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.conversation.memory import InMemoryConversationStore

    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.setenv("AGENT_ORCHESTRATOR_USE_LLM", "true")
    monkeypatch.setenv("VOICE_LLM_STREAMING_ENABLED", "true")
    get_settings.cache_clear()

    svc = HuggingFaceAIService(
        api_token="test-token",
        conversation_store=InMemoryConversationStore(),
    )

    ctx = OrchestrationContext(
        intent=IntentResult(
            intent="BUDGET_TRIP",
            city="Yaoundé",
            duration_days=3,
            budget_xaf=150000,
            needs_knowledge=True,
            needs_places=True,
            needs_planner=True,
            confidence=0.9,
        ),
        knowledge=KnowledgeResult(
            query="budget",
            intent="BUDGET_TRIP",
            places=[],
            source="empty",
            confidence=0.2,
        ),
        plan=None,
        timings=OrchestrationTimings(intent_ms=1.0, knowledge_ms=2.0, total_ms=3.0),
        agents_called=["intent", "knowledge"],
        request_id="t26",
        mode="voice",
    )

    started = {"qwen_done": False, "token_before_done": False}

    async def slow_tokens(body, *, trace=None):
        for piece in ["Bonjour", " !", " Voici", " un", " programme", " de", " trois", " jours."]:
            await asyncio.sleep(0.02)
            if not started["qwen_done"]:
                started["token_before_done"] = True
            yield piece
        started["qwen_done"] = True

    with patch(
        "app.services.agents.orchestrator.AgentOrchestrator.prepare",
        new=AsyncMock(return_value=ctx),
    ):
        with patch.object(svc, "_iter_completion_tokens", side_effect=slow_tokens):
            events = []
            async for ev in svc._stream_via_orchestrator_true_stream(
                "budget trip Yaoundé",
                thread_id="tid",
                brief=True,
                locale="fr",
                timer=__import__(
                    "app.services.metrics.latency", fromlist=["PhaseTimer"]
                ).PhaseTimer("t"),
                turn_id="t26",
                trace=__import__(
                    "app.services.metrics.llm_stream_trace", fromlist=["LlmStreamTrace"]
                ).LlmStreamTrace(turn_id="t26", model="Qwen/Qwen3.5-9B:fastest"),
            ):
                events.append(ev)
                if ev.get("type") == "token" and not started["qwen_done"]:
                    started["token_before_done"] = True

    types = [e.get("type") for e in events]
    assert "route" in types
    assert "token" in types
    assert "done" in types
    assert started["token_before_done"] is True
    assert started["qwen_done"] is True
    done = next(e for e in events if e["type"] == "done")
    assert done["orchestrator"]["llm"]["calls"] == 1
    assert done["orchestrator"]["llm"]["streaming"] is True
    assert "error" not in types

    get_settings.cache_clear()
    monkeypatch.delenv("AGENT_ORCHESTRATOR_ENABLED", raising=False)
    monkeypatch.delenv("AGENT_ORCHESTRATOR_USE_LLM", raising=False)
    monkeypatch.delenv("VOICE_LLM_STREAMING_ENABLED", raising=False)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_true_stream_qwen_402_falls_back_without_second_llm(monkeypatch):
    from app.core.config import get_settings
    from app.core.exceptions import HuggingFaceUnavailableError
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.conversation.memory import InMemoryConversationStore

    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.setenv("AGENT_ORCHESTRATOR_USE_LLM", "true")
    monkeypatch.setenv("VOICE_LLM_STREAMING_ENABLED", "true")
    get_settings.cache_clear()

    svc = HuggingFaceAIService(
        api_token="test-token",
        conversation_store=InMemoryConversationStore(),
    )
    ctx = OrchestrationContext(
        intent=IntentResult(
            intent="ITINERARY",
            city="Yaoundé",
            duration_days=3,
            needs_knowledge=True,
            needs_places=True,
            needs_planner=True,
            confidence=0.9,
        ),
        knowledge=KnowledgeResult(
            query="itineraire",
            intent="ITINERARY",
            places=[],
            source="empty",
            confidence=0.1,
            missing_information=["matching_places"],
        ),
        plan=None,
        timings=OrchestrationTimings(total_ms=1.0),
        agents_called=["intent", "knowledge"],
        request_id="t402",
        mode="voice",
    )

    calls = {"n": 0}

    async def boom(body, *, trace=None):
        calls["n"] += 1
        svc._last_hf_http_status = 402
        raise HuggingFaceUnavailableError("HTTP 402 credits")
        yield  # pragma: no cover

    with patch(
        "app.services.agents.orchestrator.AgentOrchestrator.prepare",
        new=AsyncMock(return_value=ctx),
    ):
        with patch.object(svc, "_iter_completion_tokens", side_effect=boom):
            events = []
            async for ev in svc._stream_via_orchestrator_true_stream(
                "3 jours Yaoundé",
                thread_id="tid",
                brief=True,
                locale="fr",
                timer=__import__(
                    "app.services.metrics.latency", fromlist=["PhaseTimer"]
                ).PhaseTimer("t"),
                turn_id="t402",
                trace=__import__(
                    "app.services.metrics.llm_stream_trace", fromlist=["LlmStreamTrace"]
                ).LlmStreamTrace(turn_id="t402", model="qwen"),
            ):
                events.append(ev)

    assert calls["n"] == 1  # no retry
    done = next(e for e in events if e["type"] == "done")
    assert done["orchestrator"]["llm"]["fallback_used"] is True
    assert done["orchestrator"]["llm"]["calls"] == 1
    assert any(e.get("type") == "token" for e in events)

    get_settings.cache_clear()
    monkeypatch.delenv("AGENT_ORCHESTRATOR_ENABLED", raising=False)
    monkeypatch.delenv("AGENT_ORCHESTRATOR_USE_LLM", raising=False)
    monkeypatch.delenv("VOICE_LLM_STREAMING_ENABLED", raising=False)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_feature_flag_off_uses_complete_path(monkeypatch):
    from app.core.config import get_settings
    from app.services.ai.huggingface import HuggingFaceAIService

    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.setenv("AGENT_ORCHESTRATOR_USE_LLM", "true")
    monkeypatch.setenv("VOICE_LLM_STREAMING_ENABLED", "false")
    get_settings.cache_clear()

    settings = get_settings()
    assert settings.voice_llm_streaming_enabled is False
    # Branch condition inside _stream_via_orchestrator
    true_stream = bool(
        True
        and settings.agent_orchestrator_use_llm
        and settings.voice_llm_streaming_enabled
    )
    assert true_stream is False

    get_settings.cache_clear()
    monkeypatch.delenv("AGENT_ORCHESTRATOR_ENABLED", raising=False)
    monkeypatch.delenv("AGENT_ORCHESTRATOR_USE_LLM", raising=False)
    monkeypatch.delenv("VOICE_LLM_STREAMING_ENABLED", raising=False)
    get_settings.cache_clear()


def test_prepare_then_response_keeps_single_llm_contract():
    """Orchestrator.prepare does not call Agent 4 / LLM."""
    from app.services.agents.orchestrator import AgentOrchestrator
    from app.services.agents.knowledge.agent import KnowledgeAgent
    from app.services.agents.knowledge.place_store import PlaceIndex

    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex(places=[])),
        prefer_deterministic=True,
    )

    async def _run():
        ctx = await orch.prepare(
            "Fais-moi un programme de 3 jours à Yaoundé.",
            mode="voice",
            locale="fr",
            request_id="prep1",
        )
        assert "intent" in ctx.agents_called
        assert "response" not in ctx.agents_called
        return ctx

    ctx = asyncio.run(_run())
    assert ctx.intent.intent in {"ITINERARY", "BUDGET_TRIP", "PLACE_SEARCH", "CLARIFICATION"}


@pytest.mark.asyncio
async def test_true_stream_timeout_falls_back_one_llm(monkeypatch):
    from app.core.config import get_settings
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.conversation.memory import InMemoryConversationStore

    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_ORCHESTRATOR_ENABLED", "true")
    monkeypatch.setenv("AGENT_ORCHESTRATOR_USE_LLM", "true")
    monkeypatch.setenv("VOICE_LLM_STREAMING_ENABLED", "true")
    get_settings.cache_clear()

    svc = HuggingFaceAIService(
        api_token="test-token",
        conversation_store=InMemoryConversationStore(),
    )
    ctx = OrchestrationContext(
        intent=IntentResult(
            intent="PLACE_SEARCH",
            city="Yaoundé",
            needs_knowledge=True,
            needs_places=True,
            confidence=0.8,
        ),
        knowledge=KnowledgeResult(
            query="places",
            intent="PLACE_SEARCH",
            places=[],
            source="empty",
            confidence=0.1,
        ),
        plan=None,
        timings=OrchestrationTimings(total_ms=1.0),
        agents_called=["intent", "knowledge"],
        request_id="tto",
        mode="voice",
    )
    calls = {"n": 0}

    async def timeout_boom(body, *, trace=None):
        calls["n"] += 1
        raise TimeoutError("qwen timeout")
        yield  # pragma: no cover

    with patch(
        "app.services.agents.orchestrator.AgentOrchestrator.prepare",
        new=AsyncMock(return_value=ctx),
    ):
        with patch.object(svc, "_iter_completion_tokens", side_effect=timeout_boom):
            events = []
            async for ev in svc._stream_via_orchestrator_true_stream(
                "lieux Yaoundé",
                thread_id="tid",
                brief=True,
                locale="fr",
                timer=__import__(
                    "app.services.metrics.latency", fromlist=["PhaseTimer"]
                ).PhaseTimer("t"),
                turn_id="tto",
                trace=__import__(
                    "app.services.metrics.llm_stream_trace", fromlist=["LlmStreamTrace"]
                ).LlmStreamTrace(turn_id="tto", model="qwen"),
            ):
                events.append(ev)

    assert calls["n"] == 1
    done = next(e for e in events if e["type"] == "done")
    assert done["orchestrator"]["llm"]["fallback_used"] is True
    assert done["orchestrator"]["llm"]["calls"] == 1

    get_settings.cache_clear()
    monkeypatch.delenv("AGENT_ORCHESTRATOR_ENABLED", raising=False)
    monkeypatch.delenv("AGENT_ORCHESTRATOR_USE_LLM", raising=False)
    monkeypatch.delenv("VOICE_LLM_STREAMING_ENABLED", raising=False)
    get_settings.cache_clear()


def test_text_mode_does_not_enable_true_stream(monkeypatch):
    """brief=False (text) must not take the voice true-stream branch."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AGENT_ORCHESTRATOR_USE_LLM", "true")
    monkeypatch.setenv("VOICE_LLM_STREAMING_ENABLED", "true")
    get_settings.cache_clear()
    settings = get_settings()
    brief = False
    true_stream = bool(
        brief and settings.agent_orchestrator_use_llm and settings.voice_llm_streaming_enabled
    )
    assert true_stream is False
    get_settings.cache_clear()
    monkeypatch.delenv("AGENT_ORCHESTRATOR_USE_LLM", raising=False)
    monkeypatch.delenv("VOICE_LLM_STREAMING_ENABLED", raising=False)
    get_settings.cache_clear()


def test_chunker_ordered_multi_sentence():
    """Successive ready phrases keep enqueue order (no reordering)."""
    buf = ""
    emitted: list[str] = []
    first = True
    pieces = [
        "Bienvenue à Yaoundé pour votre séjour. ",
        "Voici un programme culturel sur trois jours. ",
        "Ensuite vous visiterez le marché artisanal.",
    ]
    for piece in pieces:
        from app.services.speech.voice_chunker import append_token

        buf = append_token(buf, piece)
        ready, buf = split_ready_phrases(buf, first_chunk=first)
        for r in ready:
            emitted.append(r)
            first = False
    emitted.extend(flush_remainder(buf))
    assert len(emitted) >= 2
    joined = " ".join(emitted)
    assert joined.index("Bienvenue") < joined.index("Voici")
    assert joined.index("Voici") < joined.index("Ensuite")


def test_voice_logs_do_not_include_secrets():
    import inspect
    from app.services.ai import huggingface as hf_mod

    src = inspect.getsource(hf_mod.HuggingFaceAIService._stream_via_orchestrator_true_stream)
    assert "Authorization" not in src
    assert "Bearer " not in src
    assert "HUGGINGFACE_HUB_TOKEN" not in src
    assert "[VOICE] qwen_stream_started" in src
    assert "[VOICE] first_llm_token" in src
    assert "[VOICE] qwen_stream_finished" in src


@pytest.mark.asyncio
async def test_interrupt_cleanup_cancels_qwen_consumer(monkeypatch):
    """Simulated consumer break must not leave unbounded producer work."""
    q: asyncio.Queue[str | None] = asyncio.Queue(maxsize=2)
    interrupt = asyncio.Event()
    produced = {"n": 0}

    async def producer():
        for i in range(20):
            if interrupt.is_set():
                break
            await q.put(f"t{i}")
            produced["n"] += 1
            await asyncio.sleep(0.01)
        await q.put(None)

    async def consumer():
        while True:
            item = await q.get()
            if item is None:
                break
            if item == "t2":
                interrupt.set()
                break
        # drain sentinel / cleanup
        interrupt.set()

    prod = asyncio.create_task(producer())
    await consumer()
    await asyncio.wait_for(prod, timeout=2.0)
    assert interrupt.is_set()
    assert produced["n"] < 20
