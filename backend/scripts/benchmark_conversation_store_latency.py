#!/usr/bin/env python3
"""Phase 1.7 — benchmark SqlConversationStore prepare latency (BEFORE vs AFTER).

Measures the production Supabase path used before the LLM:

  legacy (Phase 1.6): start session + get_messages session  → ~2 NullPool TLS RTT
  optimized (1.7):    prepare_for_generation               → 0 RTT (new) / 1 RTT (existing)

Usage:

  python backend/scripts/benchmark_conversation_store_latency.py
  python backend/scripts/benchmark_conversation_store_latency.py --runs 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

OUT_JSON = ROOT / "docs" / "latency-phase17-conversation-store.json"
OUT_MD = ROOT / "docs" / "latency-phase17-conversation-store.md"


def _stats(values: list[float | None]) -> dict[str, float | int | None]:
    clean = [float(v) for v in values if v is not None and v >= 0]
    if not clean:
        return {"avg": None, "median": None, "min": None, "max": None, "n": 0}
    return {
        "avg": round(statistics.mean(clean), 1),
        "median": round(statistics.median(clean), 1),
        "min": round(min(clean), 1),
        "max": round(max(clean), 1),
        "n": len(clean),
    }


def _op_ms(trace: Any, name: str) -> float | None:
    if trace is None:
        return None
    for op in getattr(trace, "ops", []) or []:
        if op.name == name:
            return float(op.duration_ms)
    return None


def _sum_ops(trace: Any, *names: str) -> float | None:
    if trace is None:
        return None
    wanted = set(names)
    vals = [op.duration_ms for op in trace.ops if op.name in wanted]
    if not vals:
        return None
    return round(sum(vals), 1)


async def _measure_legacy(store: Any, conversation_id: str | None, limit: int) -> dict[str, Any]:
    t0 = time.perf_counter()
    thread_id, history, trace = await store.prepare_for_generation_legacy(
        conversation_id, limit=limit
    )
    total = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "mode": "legacy",
        "conversation_id": conversation_id,
        "thread_id": thread_id,
        "history_len": len(history),
        "total_store_before_llm_ms": total,
        "db_connection_acquire_ms": _sum_ops(trace, "db_connection_acquire"),
        "conversation_load_ms": _op_ms(trace, "conversation_get"),
        "conversation_create_ms": _op_ms(trace, "conversation_create"),
        "history_load_ms": _sum_ops(trace, "messages_get_full", "messages_get"),
        "commit_ms": _sum_ops(trace, "commit"),
        "session_open_ms": _sum_ops(trace, "session_open"),
        "ops": trace.as_dict()["ops"] if trace else [],
    }


async def _measure_optimized(
    store: Any, conversation_id: str | None, limit: int
) -> dict[str, Any]:
    t0 = time.perf_counter()
    thread_id, history = await store.prepare_for_generation(
        conversation_id, limit=limit
    )
    total = round((time.perf_counter() - t0) * 1000, 1)
    trace = store.last_trace
    return {
        "mode": "optimized",
        "conversation_id": conversation_id,
        "thread_id": thread_id,
        "history_len": len(history),
        "total_store_before_llm_ms": total,
        "db_connection_acquire_ms": _sum_ops(trace, "db_connection_acquire"),
        "conversation_load_ms": _op_ms(trace, "conversation_get"),
        "history_load_ms": _sum_ops(trace, "messages_get", "messages_get_full"),
        "commit_ms": _sum_ops(trace, "commit"),
        "session_open_ms": _sum_ops(trace, "session_open"),
        "prepare_skip_db_ms": _op_ms(trace, "prepare_skip_db_new_thread"),
        "ops": trace.as_dict()["ops"] if trace else [],
        "meta": trace.meta if trace else {},
    }


async def _measure_persist(store: Any, thread_id: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    await store.add_messages(
        thread_id,
        [
            ("user", "Que puis-je visiter à Yaoundé ?"),
            ("assistant", "Le Musée national et le monument de la Réunification."),
        ],
    )
    total = round((time.perf_counter() - t0) * 1000, 1)
    trace = store.last_trace
    return {
        "user_persist_ms": None,  # batched with assistant
        "assistant_persist_ms": None,
        "persist_batch_ms": total,
        "db_connection_acquire_ms": _op_ms(trace, "db_connection_acquire"),
        "commit_ms": _op_ms(trace, "commit"),
        "ops": trace.as_dict()["ops"] if trace else [],
    }


async def _voice_probe(question: str, conversation_id: str | None) -> dict[str, Any]:
    """Optional real voice path probe (may FAILED_HTTP_402)."""
    from app.api.deps import get_ai_service
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.metrics.latency import PhaseTimer
    from app.services.metrics.llm_stream_trace import LlmStreamTrace

    ai = get_ai_service()
    if not isinstance(ai, HuggingFaceAIService):
        return {"valid": False, "error": "not_hf"}

    turn_id = f"p17-{int(time.time())}"
    timer = PhaseTimer("p17")
    timer.turn_id = turn_id
    trace = LlmStreamTrace(turn_id=turn_id, model=getattr(ai, "_model", ""))
    row: dict[str, Any] = {
        "turn_id": turn_id,
        "question": question,
        "valid": False,
        "conversation_id": conversation_id,
    }
    try:
        async for event in ai.stream_response(
            question,
            conversation_id,
            brief=True,
            locale="fr",
            timer=timer,
            turn_id=turn_id,
            llm_trace=trace,
        ):
            if event.get("type") == "done":
                lt = event.get("llm_trace") or trace.as_dict()
                store_meta = (lt.get("meta") or {}).get("store") or {}
                row.update(
                    {
                        "valid": True,
                        "conversation_id": event.get("conversation_id") or conversation_id,
                        "app_ttft_ms": lt.get("app_ttft_ms"),
                        "llm_prepare_ms": lt.get("llm_prepare_ms"),
                        "provider_ttfh_ms": lt.get("provider_ttfh_ms"),
                        "store_prepare_ms": store_meta.get("total_ms"),
                        "store_ops": store_meta.get("ops"),
                        "store_mode": (store_meta.get("meta") or {}).get("mode"),
                        "generation_ms": lt.get("generation_ms"),
                        "error": lt.get("error"),
                    }
                )
            elif event.get("type") == "error":
                msg = str(event.get("message") or "")
                row["error"] = (
                    "FAILED_HTTP_402"
                    if ("402" in msg or "credit" in msg.lower())
                    else msg[:160]
                )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        row["error"] = (
            "FAILED_HTTP_402"
            if ("402" in msg or "credit" in msg.lower())
            else msg[:160]
        )
    return row


def _write_md(payload: dict[str, Any]) -> None:
    before = payload.get("before_stats") or {}
    after = payload.get("after_stats") or {}
    after_existing = payload.get("after_existing_stats") or {}

    def g(stats: dict, key: str) -> str:
        v = (stats.get(key) or {}).get("avg")
        return "—" if v is None else str(v)

    lines = [
        "# Phase 1.7 — Optimisation SqlConversationStore",
        "",
        "Bottleneck Phase 1.6 : ~2.7 s dans `SqlConversationStore` avant HF "
        "(deux sessions NullPool séquentielles vers Supabase pooler).",
        "",
        "Modèle inchangé : `Qwen/Qwen3.5-9B:fastest`. RAG / TTS / frontend inchangés.",
        "",
        "## Cause racine (mesurée)",
        "",
        "Sur Supabase pooler, SQLAlchemy utilise `NullPool` → **chaque** "
        "`async with session` ouvre une nouvelle connexion TLS.",
        "",
        "Avant Phase 1.7, le chemin voice faisait :",
        "",
        "1. `start()` → session #1 (get/create conversation + commit) ≈ 1.2–1.3 s",
        "2. `get_messages()` → session #2 (SELECT messages) ≈ 1.0–1.1 s",
        "",
        "Même historique vide coûtait ~2.3 s. Ce n’était pas la requête SQL elle-même,",
        "mais surtout **`db_connection_acquire`** (2×).",
        "",
        "## Optimisations appliquées",
        "",
        "1. **Lazy start** : nouveau thread (`conversation_id is None`) → **0 DB** avant LLM",
        "2. **`prepare_for_generation`** : un seul round-trip pour un id existant",
        "3. **SQL `LIMIT`** : `ORDER BY created_at DESC LIMIT n` (plus de full fetch + slice Python)",
        "4. **`add_messages`** : user+assistant en **un** commit après le stream",
        "",
        "## A. Timeline BEFORE (legacy, 2 sessions)",
        "",
        "```",
        "llm_start / prepare_start     +0 ms",
        "session#1 connection_acquire  ~1200–1300 ms",
        "conversation_get/create+commit  (inclus)",
        "session#2 connection_acquire  ~1000–1100 ms",
        "messages_get_full             (inclus)",
        "TOTAL store before LLM        ~2300–2500 ms",
        "```",
        "",
        f"Mesures locales legacy avg total = **{g(before, 'total_store_before_llm_ms')} ms** "
        f"(acquire sum avg = {g(before, 'db_connection_acquire_ms')} ms).",
        "",
        "## B. Timeline AFTER (optimized)",
        "",
        "### Nouveau thread (voice turn 1, conversation_id=None)",
        "",
        "```",
        "prepare_skip_db_new_thread    ~0–1 ms",
        "TOTAL store before LLM        ~0–2 ms",
        "```",
        "",
        f"Mesures avg = **{g(after, 'total_store_before_llm_ms')} ms**.",
        "",
        "### Thread existant (conversation_id fourni)",
        "",
        "```",
        "session connection_acquire    ~1 RTT",
        "messages_get LIMIT n          (même connexion)",
        "TOTAL store before LLM        ~1 RTT",
        "```",
        "",
        f"Mesures avg = **{g(after_existing, 'total_store_before_llm_ms')} ms** "
        f"(acquire avg = {g(after_existing, 'db_connection_acquire_ms')} ms).",
        "",
        "## C. Tableau par opération",
        "",
        "| Operation | Before (avg ms) | After new (avg) | After existing (avg) |",
        "|-----------|----------------:|----------------:|---------------------:|",
        f"| connection acquire | {g(before, 'db_connection_acquire_ms')} | {g(after, 'db_connection_acquire_ms')} | {g(after_existing, 'db_connection_acquire_ms')} |",
        f"| conversation load | {g(before, 'conversation_load_ms')} | {g(after, 'conversation_load_ms')} | {g(after_existing, 'conversation_load_ms')} |",
        f"| history load | {g(before, 'history_load_ms')} | {g(after, 'history_load_ms')} | {g(after_existing, 'history_load_ms')} |",
        f"| commit (prepare) | {g(before, 'commit_ms')} | {g(after, 'commit_ms')} | {g(after_existing, 'commit_ms')} |",
        f"| **TOTAL before LLM** | **{g(before, 'total_store_before_llm_ms')}** | **{g(after, 'total_store_before_llm_ms')}** | **{g(after_existing, 'total_store_before_llm_ms')}** |",
        "",
        f"Persist batch (user+assistant, after stream) avg = "
        f"{(payload.get('persist_stats') or {}).get('persist_batch_ms', {}).get('avg')} ms.",
        "",
        "## D. Voice end-to-end",
        "",
    ]

    voice = payload.get("voice_runs") or []
    if voice:
        lines += [
            "| Metric | Before (Phase 1.6) | After (Phase 1.7) |",
            "|--------|-------------------:|------------------:|",
            f"| store before LLM | ~2369.8 | see voice rows |",
            f"| app TTFT (valid) | ~2826.7 | "
            f"{_stats([r.get('app_ttft_ms') for r in voice if r.get('valid')])['avg']} |",
            "",
            "### Voice runs",
            "",
        ]
        for r in voice:
            if r.get("valid"):
                lines.append(
                    f"- `{r.get('turn_id')}` store={r.get('store_prepare_ms')} ms "
                    f"mode={r.get('store_mode')} app_ttft={r.get('app_ttft_ms')} "
                    f"provider={r.get('provider_ttfh_ms')}"
                )
            else:
                lines.append(
                    f"- `{r.get('turn_id')}` FAILED {r.get('error')} "
                    "(non inventé)"
                )
        lines.append("")
    else:
        lines += [
            "Pas de runs voice valides dans cette session (souvent HF 402). "
            "Le gain store est prouvé par le benchmark SQL ci-dessus.",
            "",
            "| Metric | Before (Phase 1.6) | After (store bench) |",
            "|--------|-------------------:|--------------------:|",
            f"| store before LLM (new thread) | ~2369.8 | {g(after, 'total_store_before_llm_ms')} |",
            f"| store before LLM (existing) | ~2369.8 | {g(after_existing, 'total_store_before_llm_ms')} |",
            "",
        ]

    lines += [
        "## E. Tests",
        "",
        f"`pytest -q` : {payload.get('pytest') or 'voir CI / run local'}",
        "",
        "## Verdict",
        "",
        payload.get("verdict") or "",
        "",
        "## Index / pool notes",
        "",
        "- Pool : `NullPool` sur `pooler.supabase.com` (pgbouncer) — inchangé volontairement.",
        "- Index messages : `conversation_id` déjà indexé ; LIMIT+ORDER BY created_at DESC "
        "bénéficierait d’un index composite `(conversation_id, created_at DESC)` en P6 "
        "si les threads deviennent longs (non créé ici faute de preuve Sequential Scan).",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


async def main_async(args: argparse.Namespace) -> int:
    from app.core.config import get_settings
    from app.core.http import close_shared_clients
    from app.services.conversation import get_conversation_store
    from app.services.conversation.postgres import SqlConversationStore
    from app.services.rag.factory import get_rag_service

    get_settings.cache_clear()
    get_conversation_store.cache_clear()
    settings = get_settings()
    await close_shared_clients()

    store = get_conversation_store()
    if not isinstance(store, SqlConversationStore):
        print("ERROR: DATABASE_ENABLED store is not SqlConversationStore")
        return 2

    limit = settings.llm_voice_history_messages
    runs = max(1, int(args.runs))
    print(f"=== Phase 1.7 conversation store bench === runs={runs} limit={limit}")
    print(f"database_enabled={settings.database_enabled} model={settings.hf_model_id}")

    before_rows: list[dict[str, Any]] = []
    after_new_rows: list[dict[str, Any]] = []
    after_existing_rows: list[dict[str, Any]] = []
    persist_rows: list[dict[str, Any]] = []

    # Seed one existing thread for "existing id" AFTER path
    seed_id, _ = await store.prepare_for_generation(None, limit=limit)
    await store.add_messages(
        seed_id,
        [
            ("user", "Que puis-je visiter à Yaoundé ?"),
            ("assistant", "Musée national, mont Fébé, marché Mokolo."),
        ],
    )
    print(f"seeded thread {seed_id}")

    for i in range(runs):
        print(f"\n--- run {i} legacy (BEFORE) ---")
        row = await _measure_legacy(store, None, limit)
        before_rows.append(row)
        print(
            f"  total={row['total_store_before_llm_ms']} "
            f"acquire={row['db_connection_acquire_ms']} "
            f"hist={row['history_load_ms']} commit={row['commit_ms']}"
        )

        print(f"--- run {i} optimized NEW thread (AFTER) ---")
        row = await _measure_optimized(store, None, limit)
        after_new_rows.append(row)
        print(
            f"  total={row['total_store_before_llm_ms']} "
            f"mode={row.get('meta', {}).get('mode')} "
            f"acquire={row['db_connection_acquire_ms']}"
        )

        print(f"--- run {i} optimized EXISTING thread (AFTER) ---")
        row = await _measure_optimized(store, seed_id, limit)
        after_existing_rows.append(row)
        print(
            f"  total={row['total_store_before_llm_ms']} "
            f"acquire={row['db_connection_acquire_ms']} "
            f"hist={row['history_load_ms']}"
        )

        print(f"--- run {i} persist batch ---")
        prow = await _measure_persist(store, seed_id)
        persist_rows.append(prow)
        print(f"  persist_batch={prow['persist_batch_ms']} commit={prow['commit_ms']}")

    before_stats = {
        "total_store_before_llm_ms": _stats(
            [r["total_store_before_llm_ms"] for r in before_rows]
        ),
        "db_connection_acquire_ms": _stats(
            [r["db_connection_acquire_ms"] for r in before_rows]
        ),
        "conversation_load_ms": _stats(
            [r["conversation_load_ms"] for r in before_rows]
        ),
        "history_load_ms": _stats([r["history_load_ms"] for r in before_rows]),
        "commit_ms": _stats([r["commit_ms"] for r in before_rows]),
    }
    after_stats = {
        "total_store_before_llm_ms": _stats(
            [r["total_store_before_llm_ms"] for r in after_new_rows]
        ),
        "db_connection_acquire_ms": _stats(
            [r["db_connection_acquire_ms"] for r in after_new_rows]
        ),
        "conversation_load_ms": _stats(
            [r["conversation_load_ms"] for r in after_new_rows]
        ),
        "history_load_ms": _stats([r["history_load_ms"] for r in after_new_rows]),
        "commit_ms": _stats([r["commit_ms"] for r in after_new_rows]),
    }
    after_existing_stats = {
        "total_store_before_llm_ms": _stats(
            [r["total_store_before_llm_ms"] for r in after_existing_rows]
        ),
        "db_connection_acquire_ms": _stats(
            [r["db_connection_acquire_ms"] for r in after_existing_rows]
        ),
        "conversation_load_ms": _stats(
            [r["conversation_load_ms"] for r in after_existing_rows]
        ),
        "history_load_ms": _stats(
            [r["history_load_ms"] for r in after_existing_rows]
        ),
        "commit_ms": _stats([r["commit_ms"] for r in after_existing_rows]),
    }
    persist_stats = {
        "persist_batch_ms": _stats([r["persist_batch_ms"] for r in persist_rows]),
        "commit_ms": _stats([r["commit_ms"] for r in persist_rows]),
        "db_connection_acquire_ms": _stats(
            [r["db_connection_acquire_ms"] for r in persist_rows]
        ),
    }

    voice_runs: list[dict[str, Any]] = []
    if not args.skip_voice:
        rag = get_rag_service()
        if callable(getattr(rag, "warm", None)):
            await rag.warm()
        questions = [
            "Quels plats camerounais dois-je goûter ?",
            "Que puis-je visiter à Yaoundé ?",
            "Propose-moi une activité nature au Cameroun.",
        ]
        # Turn 1: new conversation (0 DB). Turn 2+: reuse id (1 RTT).
        conv: str | None = None
        for qi, q in enumerate(questions):
            print(f"\n--- voice probe {qi}: {q[:40]}... conv={conv} ---")
            v = await _voice_probe(q, conv)
            voice_runs.append(v)
            print(
                f"  valid={v.get('valid')} store={v.get('store_prepare_ms')} "
                f"app_ttft={v.get('app_ttft_ms')} err={v.get('error')}"
            )
            if v.get("valid"):
                conv = str(v.get("conversation_id") or conv or seed_id)
            elif v.get("error") == "FAILED_HTTP_402":
                print("Stopping voice probes: HF 402")
                break

    b_avg = before_stats["total_store_before_llm_ms"]["avg"]
    a_new = after_stats["total_store_before_llm_ms"]["avg"]
    a_ex = after_existing_stats["total_store_before_llm_ms"]["avg"]
    verdict = (
        f"BEFORE legacy avg={b_avg} ms. "
        f"AFTER new-thread avg={a_new} ms ; existing-thread avg={a_ex} ms. "
    )
    if a_new is not None and a_new < 300:
        verdict += (
            "Objectif <300 ms ATTEINT pour le cas voice turn-1 (conversation_id=None). "
        )
    if a_ex is not None and a_ex < 500:
        verdict += "Objectif <500 ms ATTEINT pour threads existants (1 RTT). "
    if a_ex is not None and a_ex >= 500:
        verdict += (
            "Thread existant encore dominé par 1× NullPool TLS acquire — "
            "pool/infra P6 si besoin d’aller sous 150 ms à chaud. "
        )
    verdict += (
        "Cause des ~2.7 s : 2× connection acquire NullPool, pas le SQL métier. "
        "Pas de changement Qwen/RAG/TTS."
    )

    payload = {
        "phase": "1.7",
        "model": settings.hf_model_id,
        "runs": runs,
        "before_rows": before_rows,
        "after_new_rows": after_new_rows,
        "after_existing_rows": after_existing_rows,
        "persist_rows": persist_rows,
        "before_stats": before_stats,
        "after_stats": after_stats,
        "after_existing_stats": after_existing_stats,
        "persist_stats": persist_stats,
        "voice_runs": voice_runs,
        "verdict": verdict,
        "pytest": None,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_md(payload)
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(verdict)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1.7 conversation store latency")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--skip-voice", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
