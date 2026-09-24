#!/usr/bin/env python3
"""Benchmark Agent 3 Tourism Planner latency — Phase 2.3."""

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
from app.services.agents.planner.agent import TourismPlanner

SAMPLES = [
    "Je viens à Yaoundé pendant 3 jours, culture et nature, budget 150000 FCFA.",
    "Propose-moi un circuit nature au Cameroun.",
    "Je veux découvrir la culture Sawa.",
    "Voyage de 3 jours avec 150000 FCFA à Yaoundé.",
]


def main() -> int:
    knowledge_agent = KnowledgeAgent.from_catalog()
    planner = TourismPlanner()

    rows = []
    totals = []
    for text in SAMPLES * 3:
        intent = classify_intent(text)
        knowledge = knowledge_agent.retrieve_sync(text, intent)
        t0 = time.perf_counter()
        plan = planner.plan(text, intent, knowledge)
        ms = (time.perf_counter() - t0) * 1000.0
        totals.append(ms)
        rows.append(
            {
                "intent": intent.intent,
                "feasibility": plan.feasibility,
                "budget_status": plan.budget_status,
                "days": len(plan.days),
                "selected": len(plan.selected_places),
                "total_ms": round(ms, 3),
                "reported_ms": plan.total_planner_ms,
            }
        )

    summary = {
        "n": len(totals),
        "mean_ms": round(statistics.mean(totals), 3),
        "median_ms": round(statistics.median(totals), 3),
        "p95_ms": round(sorted(totals)[int(0.95 * (len(totals) - 1))], 3),
        "max_ms": round(max(totals), 3),
        "strategy": "rules_data_first_no_llm",
        "samples_preview": rows[:4],
    }
    out = ROOT.parent / "docs" / "phase2-agent3-tourism-planner-latency.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
