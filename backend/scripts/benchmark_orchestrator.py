#!/usr/bin/env python3
"""Benchmark Phase 2.5 Agent Orchestrator (deterministic Agents 1–4, no LLM)."""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.agents.knowledge.agent import KnowledgeAgent  # noqa: E402
from app.services.agents.knowledge.place_store import PlaceIndex, PlaceRecord  # noqa: E402
from app.services.agents.orchestrator import AgentOrchestrator  # noqa: E402


def _places() -> list[PlaceRecord]:
    return [
        PlaceRecord(
            place_id="place-yaounde-1",
            name="Musée National du Cameroun",
            city="Yaoundé",
            region="Centre",
            description="Musée national.",
            categories=["Museum"],
            estimated_cost_xaf=2000,
            recommended_duration_hours=2.0,
            latitude=3.8667,
            longitude=11.5167,
            is_published=True,
        ),
        PlaceRecord(
            place_id="place-yaounde-2",
            name="Monument de la Réunification",
            city="Yaoundé",
            region="Centre",
            categories=["Monument"],
            estimated_cost_xaf=0,
            recommended_duration_hours=1.0,
            latitude=3.857,
            longitude=11.511,
            is_published=True,
        ),
        PlaceRecord(
            place_id="place-yaounde-3",
            name="Bois Sainte-Anastasie",
            city="Yaoundé",
            region="Centre",
            categories=["Park"],
            estimated_cost_xaf=1000,
            recommended_duration_hours=2.0,
            latitude=3.87,
            longitude=11.52,
            is_published=True,
        ),
    ]


CASES = [
    ("greeting", "Bonjour"),
    ("tourism_info", "Quels sont les lieux touristiques à Yaoundé ?"),
    ("itinerary", "Fais-moi un programme de 3 jours à Yaoundé."),
]


async def _bench_one(orch: AgentOrchestrator, label: str, query: str, n: int = 20) -> dict:
    samples: list[dict] = []
    for i in range(n):
        result = await orch.run(query, mode="text", locale="fr", request_id=f"{label}-{i}")
        samples.append(
            {
                "total_ms": result.timings.total_ms,
                "intent_ms": result.timings.intent_ms,
                "knowledge_ms": result.timings.knowledge_ms,
                "planner_ms": result.timings.planner_ms,
                "response_ms": result.timings.response_ms,
                "agents_called": list(result.agents_called),
            }
        )
    totals = [s["total_ms"] or 0.0 for s in samples]

    def _med(key: str) -> float | None:
        vals = [s[key] for s in samples if s[key] is not None]
        return round(statistics.median(vals), 3) if vals else None

    return {
        "label": label,
        "query": query,
        "n": n,
        "agents_called": samples[-1]["agents_called"],
        "total_ms_median": round(statistics.median(totals), 3),
        "total_ms_p95": round(sorted(totals)[max(0, int(0.95 * len(totals)) - 1)], 3),
        "intent_ms_median": _med("intent_ms"),
        "knowledge_ms_median": _med("knowledge_ms"),
        "planner_ms_median": _med("planner_ms"),
        "response_ms_median": _med("response_ms"),
    }


async def main() -> None:
    orch = AgentOrchestrator(
        knowledge_agent=KnowledgeAgent(PlaceIndex(places=_places())),
        prefer_deterministic=True,
    )
    # Warmup
    await orch.run("Bonjour", request_id="warmup")
    rows = []
    for label, query in CASES:
        rows.append(await _bench_one(orch, label, query))
    out = {
        "phase": "2.5",
        "component": "agent_orchestrator",
        "prefer_deterministic": True,
        "cases": rows,
        "wall_ms": round(time.time() * 1000) % 1_000_000,
    }
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    path = docs / "phase2-agent-orchestrator-latency.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    print(f"wrote {path}")


if __name__ == "__main__":
    asyncio.run(main())
