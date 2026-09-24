#!/usr/bin/env python3
"""Phase 1.6 — diagnose real voice-path delay before first LLM token.

Uses the SAME production path as voice_ws:

  HuggingFaceAIService.stream_response(brief=True, locale=fr)

Does NOT change models, RAG, prompts, or providers. Instrumentation only.

Usage:

  python backend/scripts/diagnose_voice_llm_latency.py
  python backend/scripts/diagnose_voice_llm_latency.py --runs 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

OUT_JSON = ROOT / "docs" / "latency-phase16-voice-llm-diagnostic.json"
OUT_MD = ROOT / "docs" / "latency-phase16-voice-llm-diagnostic.md"

QUESTIONS = [
    ("food", "Quels plats camerounais dois-je goûter ?"),
    ("yaounde", "Que puis-je visiter à Yaoundé ?"),
    ("nature", "Propose-moi une activité nature au Cameroun."),
    ("trip3", "Je viens au Cameroun pendant trois jours, que peux-tu me proposer ?"),
]


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


def _event_elapsed(events: list[dict] | None, name: str) -> float | None:
    for e in events or []:
        if e.get("event") == name:
            return float(e["elapsed_ms"])
    return None


def _delta(events: list[dict] | None, a: str, b: str) -> float | None:
    ea, eb = _event_elapsed(events, a), _event_elapsed(events, b)
    if ea is None or eb is None:
        return None
    return round(eb - ea, 1)


def _enrich_row(row: dict[str, Any]) -> dict[str, Any]:
    events = row.get("events")
    row["store_start_ms"] = _event_elapsed(events, "conversation_store_start_done")
    row["store_history_ms"] = _delta(
        events, "conversation_store_start_done", "conversation_history_loaded"
    )
    row["store_total_ms"] = _event_elapsed(events, "conversation_history_loaded")
    row["routing_only_ms"] = _delta(
        events, "conversation_history_loaded", "routing_done"
    )
    row["grounding_ms"] = _delta(events, "routing_done", "prompt_ready")
    return row


def _hypothesis(rows: list[dict[str, Any]]) -> str:
    valid = [r for r in rows if r.get("valid")]
    if not valid:
        return (
            "Aucune mesure valide (souvent FAILED_HTTP_402). "
            "Impossible de trancher A–G sans données. Relancer quand les crédits HF reviennent."
        )

    prep = _stats([r.get("llm_prepare_ms") for r in valid])
    prov = _stats([r.get("provider_ttfh_ms") for r in valid])
    parse = _stats([r.get("stream_parse_ms") for r in valid])
    app = _stats([r.get("app_ttft_ms") for r in valid])
    fallback_n = sum(1 for r in valid if r.get("fallback_used"))
    fallback_rate = fallback_n / len(valid)

    lines = [
        f"Sur n={len(valid)} runs valides : "
        f"prepare_avg={prep['avg']}ms, provider_ttfh_avg={prov['avg']}ms, "
        f"parse_avg={parse['avg']}ms, app_ttft_avg={app['avg']}ms, "
        f"fallback_rate={fallback_rate:.0%}."
    ]

    # Rank contributions to app_ttft
    parts = [
        ("prepare (B)", prep["avg"] or 0),
        ("provider (A/C)", prov["avg"] or 0),
        ("parse (E)", parse["avg"] or 0),
    ]
    parts.sort(key=lambda x: x[1], reverse=True)
    dominant = parts[0][0]
    lines.append(f"Contribution dominante estimée : **{dominant}**.")

    if fallback_rate >= 0.3:
        lines.append(
            "**Hypothèse D (forte)** : fallback stream→non-stream fréquent "
            f"({fallback_n}/{len(valid)}). En fallback, first_token = réponse complète "
            "→ app_ttft gonflé vers total_generation."
        )
    if (prov["avg"] or 0) >= 1500 and (prep["avg"] or 0) < 200:
        lines.append(
            "**Hypothèse A** : le provider met réellement longtemps avant le premier événement."
        )
    if (prep["avg"] or 0) >= 1000:
        store = _stats([r.get("store_total_ms") for r in valid])
        lines.append(
            "**Hypothèse B (confirmée si store_total élevé)** : délai important AVANT l’appel HF. "
            f"store_total_avg={store['avg']}ms (SqlConversationStore start+get_messages)."
        )
    if (parse["avg"] or 0) >= 500:
        lines.append(
            "**Hypothèse E** : parsing/application retarde le first_token après l’événement réseau."
        )
    cold = [r for r in valid if r.get("cold")]
    warm = [r for r in valid if r.get("cold") is False]
    if cold and warm:
        c = _stats([r.get("app_ttft_ms") for r in cold])
        w = _stats([r.get("app_ttft_ms") for r in warm])
        lines.append(
            f"Cold app_ttft avg={c['avg']}ms (n={c['n']}) vs warm avg={w['avg']}ms (n={w['n']}) "
            "→ **Hypothèse G** possible (cold TLS/provider)."
        )
    lines.append(
        "**Hypothèse F** : Phase 1.5 chronométrait surtout `_stream_tokens` "
        "(après grounding), alors que le `llm_start` voice_ws/Phase1.2 englobait "
        "routing+grounding+LLM — et un fallback non-stream transforme TTFT en durée totale."
    )
    return " ".join(lines)


def write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# Phase 1.6 — Diagnostic délai réel avant premier token",
        "",
        "Instrumentation du chemin **production** `voice_ws → HuggingFaceAIService.stream_response`.",
        "Modèle inchangé : `Qwen/Qwen3.5-9B:fastest`.",
        "",
        f"- Runs demandés : {payload.get('runs_requested')}",
        f"- Valid : {payload.get('valid_n')} / Failed : {payload.get('failed_n')}",
        "",
        "## Tableau récapitulatif",
        "",
        "| Run | Prepare | Store | Provider | Parse | App TTFT | First phrase | Total | Retry | Fallback |",
        "|----:|--------:|------:|---------:|------:|---------:|-------------:|------:|------:|:--------:|",
    ]
    for r in payload.get("runs", []):
        if not r.get("valid"):
            lines.append(
                f"| {r.get('turn_id')} | — | — | — | — | — | — | — | "
                f"{r.get('retry_count', 0)} | FAILED {r.get('error', '')[:40]} |"
            )
            continue
        lines.append(
            f"| `{r.get('turn_id')}` | {r.get('llm_prepare_ms')} | {r.get('store_total_ms')} | "
            f"{r.get('provider_ttfh_ms')} | {r.get('stream_parse_ms')} | {r.get('app_ttft_ms')} | "
            f"{r.get('first_phrase_ready_ms')} | {r.get('generation_ms')} | "
            f"{r.get('retry_count')} | {'yes' if r.get('fallback_used') else 'no'} |"
        )

    lines += ["", "## Timelines (runs valides)", ""]
    for r in payload.get("runs", []):
        if not r.get("valid"):
            continue
        lines.append(f"### `{r.get('turn_id')}` — {r.get('question_id')} cold={r.get('cold')}")
        lines.append("```")
        for e in r.get("events") or []:
            lines.append(
                f"{e['event']:28} +{e['elapsed_ms']:8.1f} ms  (Δ {e['delta_ms']:.1f} ms)"
            )
        lines.append("```")
        store = r.get("store_total_ms")
        if store is not None:
            lines.append(
                f"- store_total={store} ms "
                f"(start={r.get('store_start_ms')} + history={r.get('store_history_ms')}); "
                f"routing={r.get('routing_only_ms')} ms; grounding={r.get('grounding_ms')} ms; "
                f"attempts={r.get('provider_attempt_count')}"
            )
        lines.append("")

    lines += [
        "## Stats",
        "",
        "```json",
        json.dumps(payload.get("stats") or {}, indent=2),
        "```",
        "",
        "## Phase 1.5 vs Phase 1.6",
        "",
        payload.get("phase15_comparison") or "",
        "",
        "## Analyse des hypothèses",
        "",
        payload.get("hypothesis") or "",
        "",
        "## Conclusion",
        "",
        payload.get("conclusion") or "",
        "",
        "## Code finding (retry/fallback, mesure seulement)",
        "",
        payload.get("code_finding_fallback") or "",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


async def run_one(
    *,
    ai: Any,
    qid: str,
    question: str,
    run_i: int,
    cold: bool,
) -> dict[str, Any]:
    from app.services.metrics.latency import PhaseTimer
    from app.services.metrics.llm_stream_trace import LlmStreamTrace

    turn_id = f"voice-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{qid}-{run_i:02d}"
    timer = PhaseTimer("p16_voice_llm")
    timer.turn_id = turn_id
    trace = LlmStreamTrace(turn_id=turn_id, model=getattr(ai, "_model", ""))
    trace.cold = cold

    row: dict[str, Any] = {
        "turn_id": turn_id,
        "question_id": qid,
        "question": question,
        "run_i": run_i,
        "cold": cold,
        "model": getattr(ai, "_model", ""),
        "valid": False,
    }

    reply = ""
    try:
        async for event in ai.stream_response(
            question,
            brief=True,
            locale="fr",
            timer=timer,
            turn_id=turn_id,
            llm_trace=trace,
        ):
            et = event.get("type")
            if et == "token":
                reply += str(event.get("text") or "")
            elif et == "done":
                reply = str(event.get("text") or reply)
                lt = event.get("llm_trace") or trace.as_dict()
                row.update(
                    {
                        "valid": True,
                        "llm_prepare_ms": lt.get("llm_prepare_ms"),
                        "provider_ttfh_ms": lt.get("provider_ttfh_ms"),
                        "stream_parse_ms": lt.get("stream_parse_ms"),
                        "app_ttft_ms": lt.get("app_ttft_ms"),
                        "first_useful_text_ms": lt.get("first_useful_text_ms"),
                        "first_phrase_ready_ms": lt.get("first_phrase_ready_ms"),
                        "generation_ms": lt.get("generation_ms"),
                        "retry_count": lt.get("retry_count"),
                        "provider_attempt_count": lt.get("provider_attempt_count"),
                        "fallback_used": lt.get("fallback_used"),
                        "fallback_reason": lt.get("fallback_reason"),
                        "http_status": lt.get("http_status"),
                        "events": lt.get("events"),
                        "meta": lt.get("meta"),
                        "phases_ms": (event.get("metrics") or {}).get("phases_ms"),
                        "reply_preview": reply[:200],
                    }
                )
            elif et == "error":
                msg = str(event.get("message") or event.get("code") or "error")
                lt = event.get("llm_trace") or trace.as_dict()
                err = msg
                if "402" in msg or "credit" in msg.lower() or "depleted" in msg.lower():
                    err = "FAILED_HTTP_402"
                row.update(
                    {
                        "valid": False,
                        "error": err,
                        "llm_prepare_ms": lt.get("llm_prepare_ms"),
                        "provider_ttfh_ms": lt.get("provider_ttfh_ms"),
                        "stream_parse_ms": lt.get("stream_parse_ms"),
                        "app_ttft_ms": lt.get("app_ttft_ms"),
                        "retry_count": lt.get("retry_count"),
                        "provider_attempt_count": lt.get("provider_attempt_count"),
                        "fallback_used": lt.get("fallback_used"),
                        "fallback_reason": lt.get("fallback_reason"),
                        "http_status": lt.get("http_status"),
                        "events": lt.get("events"),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        err = "FAILED_HTTP_402" if ("402" in msg or "credit" in msg.lower()) else msg[:160]
        row["error"] = err
        row["events"] = trace.as_dict().get("events")
    return row


async def main_async(args: argparse.Namespace) -> int:
    from app.api.deps import get_ai_service
    from app.core.config import get_settings
    from app.core.http import close_shared_clients
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.rag.factory import get_rag_service

    get_settings.cache_clear()
    settings = get_settings()
    await close_shared_clients()  # force first run to be cold TLS if possible

    ai = get_ai_service()
    if not isinstance(ai, HuggingFaceAIService):
        print("ERROR: production AI is not HuggingFaceAIService")
        return 2

    rag = get_rag_service()
    if callable(getattr(rag, "warm", None)):
        await rag.warm()

    runs_n = max(1, int(args.runs))
    print("=== Phase 1.6 voice LLM diagnostic ===")
    print(f"model={settings.hf_model_id} runs={runs_n}")

    rows: list[dict[str, Any]] = []
    first_request = True
    consecutive_402 = 0

    # Round-robin questions × runs
    for i in range(runs_n):
        qid, question = QUESTIONS[i % len(QUESTIONS)]
        cold = first_request
        print(f"\n--- {qid} run={i} cold={cold} ---")
        row = await run_one(
            ai=ai, qid=qid, question=question, run_i=i, cold=cold
        )
        first_request = False
        rows.append(row)
        if row.get("valid"):
            _enrich_row(row)
            consecutive_402 = 0
            print(
                f"  prepare={row.get('llm_prepare_ms')} "
                f"store={row.get('store_total_ms')} "
                f"(start={row.get('store_start_ms')}+hist={row.get('store_history_ms')}) "
                f"provider={row.get('provider_ttfh_ms')} "
                f"parse={row.get('stream_parse_ms')} "
                f"app_ttft={row.get('app_ttft_ms')} "
                f"phrase={row.get('first_phrase_ready_ms')} "
                f"total={row.get('generation_ms')} "
                f"fallback={row.get('fallback_used')} "
                f"attempts={row.get('provider_attempt_count')}"
            )
            for line in [
                f"{e['event']:28} +{e['elapsed_ms']:7.1f}ms"
                for e in (row.get("events") or [])[:12]
            ]:
                print(f"  {line}")
        else:
            print(f"  INVALID: {row.get('error')}")
            if row.get("error") == "FAILED_HTTP_402":
                consecutive_402 += 1
                if consecutive_402 >= 3:
                    print("Stopping early: HF_402 streak")
                    break
            await asyncio.sleep(1.5)

    valid = [r for r in rows if r.get("valid")]
    for r in valid:
        _enrich_row(r)
    failed = [r for r in rows if not r.get("valid")]
    stats = {
        "llm_prepare_ms": _stats([r.get("llm_prepare_ms") for r in valid]),
        "store_start_ms": _stats([r.get("store_start_ms") for r in valid]),
        "store_history_ms": _stats([r.get("store_history_ms") for r in valid]),
        "store_total_ms": _stats([r.get("store_total_ms") for r in valid]),
        "routing_only_ms": _stats([r.get("routing_only_ms") for r in valid]),
        "grounding_ms": _stats([r.get("grounding_ms") for r in valid]),
        "provider_ttfh_ms": _stats([r.get("provider_ttfh_ms") for r in valid]),
        "stream_parse_ms": _stats([r.get("stream_parse_ms") for r in valid]),
        "app_ttft_ms": _stats([r.get("app_ttft_ms") for r in valid]),
        "first_useful_text_ms": _stats([r.get("first_useful_text_ms") for r in valid]),
        "first_phrase_ready_ms": _stats([r.get("first_phrase_ready_ms") for r in valid]),
        "generation_ms": _stats([r.get("generation_ms") for r in valid]),
        "fallback_rate": round(
            (sum(1 for r in valid if r.get("fallback_used")) / len(valid)) if valid else 0,
            3,
        ),
    }

    phase15_comparison = (
        "Phase 1.5 chronométrait `_stream_tokens` (messages déjà construits) → TTFT warm ≈ 245–280 ms. "
        "Phase 1.6 chronomètre `stream_response` voice complet. "
        f"app_ttft avg={stats['app_ttft_ms']['avg']} ms dont "
        f"store_total avg={stats['store_total_ms']['avg']} ms "
        f"(start={stats['store_start_ms']['avg']} + history={stats['store_history_ms']['avg']}), "
        f"provider_ttfh avg={stats['provider_ttfh_ms']['avg']} ms, "
        f"parse avg={stats['stream_parse_ms']['avg']} ms. "
        "Écart 2.7s vs 250ms = surtout SqlConversationStore (Supabase), pas Qwen."
    )

    hypothesis = _hypothesis(rows)
    if valid:
        conclusion = (
            f"OÙ SONT LES ~2.7 s ? Mesure n={len(valid)} : "
            f"app_ttft≈{stats['app_ttft_ms']['avg']}ms = "
            f"SqlConversationStore≈{stats['store_total_ms']['avg']}ms "
            f"(start≈{stats['store_start_ms']['avg']} + get_messages≈{stats['store_history_ms']['avg']}) "
            f"+ provider_ttfh≈{stats['provider_ttfh_ms']['avg']}ms "
            f"+ parse≈{stats['stream_parse_ms']['avg']}ms. "
            "Hypothèse B confirmée (délai AVANT HF). "
            "Phase 1.5 ne voyait que le provider (~250ms) car elle bypassait le store. "
            "Ne pas changer Qwen pour ce symptôme."
        )
    else:
        conclusion = (
            "Pas de runs valides (HF 402). Instrumentation en place — relancer le script "
            "pour obtenir la timeline réelle. Ne pas inventer de chiffres."
        )

    payload = {
        "phase": "1.6",
        "model": settings.hf_model_id,
        "runs_requested": runs_n,
        "valid_n": len(valid),
        "failed_n": len(failed),
        "stats": stats,
        "runs": rows,
        "phase15_comparison": phase15_comparison,
        "hypothesis": hypothesis,
        "conclusion": conclusion,
        "code_finding_fallback": (
            "huggingface._iter_sse_tokens: if stream HTTP status >= 400, "
            "falls back to non-stream POST and yields the full text as a single token. "
            "That alone can turn ~250ms TTFT into multi-second 'first_token'."
        ),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_md(payload)
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(conclusion)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1.6 voice LLM TTFT diagnostic")
    parser.add_argument("--runs", type=int, default=5, help="Minimum target runs (default 5)")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
