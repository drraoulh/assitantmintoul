"""Unit tests for Phase 1.5 benchmark helpers (no HF network)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_bench():
    path = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_llm_latency.py"
    spec = importlib.util.spec_from_file_location("benchmark_llm_latency", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_stats_empty():
    mod = _load_bench()
    assert mod._stats([])["n"] == 0
    assert mod._stats([None, -1])["n"] == 0


def test_stats_basic():
    mod = _load_bench()
    s = mod._stats([10.0, 20.0, 30.0, 40.0, 50.0])
    assert s["n"] == 5
    assert s["avg"] == 30.0
    assert s["median"] == 30.0
    assert s["min"] == 10.0
    assert s["max"] == 50.0
    assert s["p95"] is not None


def test_score_reply_french_food():
    mod = _load_bench()
    q = "Quels plats camerounais dois-je goûter ?"
    reply = (
        "Au Cameroun, goûtez le ndolé et le poulet DG, deux plats emblématiques "
        "de la cuisine locale pour bien commencer."
    )
    kb = "ndolé poulet dg yaoundé douala gastronomie camerounaise"
    scores = mod._score_reply(q, reply, kb)
    assert scores["relevance"] >= 3
    assert scores["french_quality"] >= 4
    assert scores["cameroon_tourism"] >= 4
    assert scores["brevity"] >= 4


def test_score_empty():
    mod = _load_bench()
    scores = mod._score_reply("test", "", "")
    assert scores["relevance"] == 1
