#!/usr/bin/env python3
"""Benchmark Agent 2 Knowledge & Retrieval latency — Phase 2.2."""

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
from app.services.agents.knowledge.agent import KnowledgeAgent
from app.services.agents.knowledge.place_store import PlaceIndex

SAMPLES = [
    "Que puis-je visiter à Yaoundé ?",
    "Parle-moi du Mont Cameroun.",
    "Propose-moi une activité nature au Cameroun.",
    "Je veux découvrir la culture Sawa.",
    "Quels plats camerounais dois-je goûter ?",
    "Voyage de 3 jours avec 150000 FCFA à Yaoundé.",
]


def main() -> int:
    agent = KnowledgeAgent.from_catalog()
    # warm
    for text in SAMPLES:
        intent = classify_intent(text)
        agent.retrieve_sync(text, intent)

    rows = []
    totals = []
    place_ms = []
    know_ms = []
    for text in SAMPLES * 3:
        intent = classify_intent(text)
        t0 = time.perf_counter()
        result = agent.retrieve_sync(text, intent)
        elapsed = (time.perf_counter() - t0) * 1000.0
        totals.append(elapsed)
        if result.place_retrieval_ms is not None:
            place_ms.append(result.place_retrieval_ms)
        if result.knowledge_retrieval_ms is not None:
            know_ms.append(result.knowledge_retrieval_ms)
        rows.append(
            {
                "intent": result.intent,
                "places": len(result.places),
                "knowledge": len(result.knowledge),
                "total_ms": round(elapsed, 3),
                "place_ms": result.place_retrieval_ms,
                "knowledge_ms": result.knowledge_retrieval_ms,
            }
        )

    summary = {
        "n": len(totals),
        "mean_total_ms": round(statistics.mean(totals), 3),
        "median_total_ms": round(statistics.median(totals), 3),
        "p95_total_ms": round(sorted(totals)[int(0.95 * (len(totals) - 1))], 3),
        "mean_place_ms": round(statistics.mean(place_ms), 3) if place_ms else None,
        "mean_knowledge_ms": round(statistics.mean(know_ms), 3) if know_ms else None,
        "index_size": len(PlaceIndex.from_catalog()),
        "strategy": "structured_first_tfidf_fallback_no_vector",
        "samples_preview": rows[:6],
    }
    out = ROOT.parent / "docs" / "phase2-agent2-knowledge-latency.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
