#!/usr/bin/env python3
"""Measure Agent 1 (Intent & Router) latency — Phase 2.1.

Usage:
  cd backend && python -m scripts.benchmark_intent_router
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.agents.intent import classify_intent

SAMPLES = [
    "Quelle est la capitale du Cameroun ?",
    "Que visiter à Yaoundé ?",
    "Je viens à Yaoundé pendant 3 jours.",
    "Nous sommes 4 avec 150000 FCFA pour 3 jours à Yaoundé.",
    "Quels plats camerounais dois-je goûter ?",
    "Je veux découvrir la culture Sawa.",
    "Propose-moi une activité nature au Cameroun.",
    "Parle-moi du Mont Cameroun.",
    "Je veux réserver un hôtel à Yaoundé.",
    "Je veux quelque chose de bien au Cameroun.",
]


def main() -> int:
    # Warm-up
    for text in SAMPLES:
        classify_intent(text, mode="voice")

    rows: list[dict] = []
    latencies: list[float] = []
    for text in SAMPLES * 5:
        t0 = time.perf_counter()
        result = classify_intent(text, mode="voice")
        ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(ms)
        rows.append(
            {
                "intent": result.intent,
                "confidence": result.confidence,
                "router_latency_ms": round(ms, 3),
                "reported_ms": result.router_latency_ms,
            }
        )

    summary = {
        "n": len(latencies),
        "mean_ms": round(statistics.mean(latencies), 3),
        "median_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(sorted(latencies)[int(0.95 * (len(latencies) - 1))], 3),
        "max_ms": round(max(latencies), 3),
        "strategy": "hybrid_rules_first_voice_rules_only",
        "samples_preview": rows[:10],
    }
    out_json = ROOT.parent / "docs" / "phase2-agent1-router-latency.json"
    out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
