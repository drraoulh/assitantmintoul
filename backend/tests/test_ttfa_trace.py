"""Unit tests for Phase 1.3 TurnChronology (diagnostic only)."""

from __future__ import annotations

import time

from app.services.metrics.ttfa_trace import TurnChronology


def test_mark_orders_backfilled_timestamps():
    c = TurnChronology(turn_id="t1")
    c.mark("llm_start")
    time.sleep(0.01)
    c.mark("llm_first_token")
    t_req = time.perf_counter()
    time.sleep(0.01)
    c.mark("tts_worker_start")
    # Fish marks arrive later but with earlier absolute stamps relative to worker.
    c.mark("tts_request_start", at=t_req)
    names = [e["event"] for e in c.events]
    assert names.index("tts_request_start") < names.index("tts_worker_start") or names.index(
        "tts_request_start"
    ) == names.index("tts_worker_start") - 0
    # elapsed must be non-decreasing after sort
    elapsed = [e["elapsed_ms"] for e in c.events]
    assert elapsed == sorted(elapsed)


def test_from_llm_first_token():
    c = TurnChronology(turn_id="t2")
    c.mark("llm_first_token")
    time.sleep(0.02)
    c.mark("tts_first_audio_byte")
    last = c.events[-1]
    assert last["from_llm_first_token_ms"] is not None
    assert last["from_llm_first_token_ms"] >= 15


def test_biggest_gaps():
    c = TurnChronology(turn_id="t3")
    c.mark("a")
    time.sleep(0.05)
    c.mark("b")
    time.sleep(0.01)
    c.mark("c")
    gaps = c.biggest_gaps(1)
    assert gaps[0]["from"] == "a"
    assert gaps[0]["to"] == "b"
    assert gaps[0]["delta_ms"] >= 40
