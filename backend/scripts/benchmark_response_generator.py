#!/usr/bin/env python3
"""Benchmark Agent 4 Response Generator (deterministic path) — Phase 2.4."""

from __future__ import annotations

import asyncio
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
from app.services.agents.response.agent import ResponseGenerator

SAMPLES = [
    "Quelle est la capitale du Cameroun ?",
    "Que puis-je visiter à Yaoundé ?",
    "Je viens à Yaoundé pendant 3 jours, culture et nature, budget 150000 FCFA.",
    "Propose-moi une activité nature au Cameroun.",
]


async def _one(agent4, knowledge_agent, planner, text: str) -> dict:
    intent = classify_intent(text)
    knowledge = await knowledge_agent.retrieve(text, intent)
    plan = None
    if intent.needs_planner or intent.intent in {"ITINERARY", "BUDGET_TRIP", "NATURE"}:
        plan = planner.plan(text, intent, knowledge)
    t0 = time.perf_counter()
    final = await agent4.generate(text, intent, knowledge, plan, response_mode="text")
    ms = (time.perf_counter() - t0) * 1000.0
    return {
        "response_type": final.response_type,
        "language": final.language,
        "fallback_used": final.fallback_used,
        "total_ms": round(ms, 3),
        "prompt_build_ms": final.prompt_build_ms,
        "chars": len(final.text),
    }


def main() -> int:
    knowledge_agent = KnowledgeAgent.from_catalog()
    planner = TourismPlanner()
    agent4 = ResponseGenerator(prefer_deterministic=True)

    async def run_all():
        rows = []
        for text in SAMPLES * 3:
            rows.append(await _one(agent4, knowledge_agent, planner, text))
        return rows

    rows = asyncio.run(run_all())
    totals = [r["total_ms"] for r in rows]
    summary = {
        "n": len(totals),
        "mean_ms": round(statistics.mean(totals), 3),
        "median_ms": round(statistics.median(totals), 3),
        "p95_ms": round(sorted(totals)[int(0.95 * (len(totals) - 1))], 3),
        "path": "deterministic_renderer_no_llm",
        "samples_preview": rows[:4],
    }
    out = ROOT.parent / "docs" / "phase2-agent4-response-generator-latency.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
