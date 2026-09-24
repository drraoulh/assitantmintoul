"""Unit tests for Phase 1.6 LlmStreamTrace (no network)."""

from __future__ import annotations

import time

from app.services.metrics.llm_stream_trace import LlmStreamTrace


def test_prepare_provider_parse_metrics():
    t = LlmStreamTrace(turn_id="voice-test-1", model="Qwen/Qwen3.5-9B:fastest")
    t.mark("llm_start")
    time.sleep(0.01)
    t.mark("prompt_ready")
    t.note_provider_call_started()
    assert t.llm_prepare_ms is not None
    assert t.llm_prepare_ms >= 8
    time.sleep(0.02)
    t.note_response_headers(200)
    assert t.provider_ttfh_ms is not None
    assert t.provider_ttfh_ms >= 15
    t.note_first_stream_event(kind="sse_data")
    time.sleep(0.005)
    t.note_first_token(chars=2)
    assert t.app_ttft_ms is not None
    assert t.stream_parse_ms is not None
    assert t.app_ttft_ms >= t.llm_prepare_ms
    t.note_first_phrase_ready(text="Bonjour le Cameroun,")
    t.note_llm_end()
    d = t.as_dict()
    assert d["provider_attempt_count"] == 1
    assert d["fallback_used"] is False
    assert any(e["event"] == "first_token" for e in d["events"])


def test_fallback_increments_retry():
    t = LlmStreamTrace(turn_id="voice-test-2")
    t.mark("llm_start")
    t.note_provider_call_started()
    t.note_response_headers(503)
    t.note_fallback("stream_http_503_to_non_stream")
    t.note_provider_call_started()
    assert t.fallback_used is True
    assert t.retry_count == 1
    assert t.provider_attempt_count == 2
