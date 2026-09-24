#!/usr/bin/env python3
"""Phase 1.5 — isolated LLM latency benchmark (does NOT change production).

Compares Hugging Face Inference Provider chat models under identical
voice-mode conditions (same grounded system prompt, RAG context, temperature,
max_tokens, streaming). Only the ``model`` field differs.

Usage (from repo root, with backend/.env secrets):

  python backend/scripts/benchmark_llm_latency.py
  python backend/scripts/benchmark_llm_latency.py --runs 3
  python backend/scripts/benchmark_llm_latency.py --models 'Qwen/Qwen3.5-9B:fastest,meta-llama/Llama-3.1-8B-Instruct:fastest'

Outputs:
  docs/latency-phase15-llm-benchmark.json
  docs/latency-phase15-llm-benchmark.md  (summary tables)

Never invents metrics for HTTP 402/404/429/timeouts — those runs are FAILED.
Production HF_MODEL_ID is never modified.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

OUT_JSON = ROOT / "docs" / "latency-phase15-llm-benchmark.json"
OUT_MD = ROOT / "docs" / "latency-phase15-llm-benchmark.md"

# Production baseline + candidates known to appear on router.huggingface.co/v1/models
# for this account (verified via GET /models). Availability is re-checked at runtime.
DEFAULT_MODEL_CANDIDATES = [
    "Qwen/Qwen3.5-9B:fastest",  # production baseline
    "meta-llama/Llama-3.1-8B-Instruct:fastest",
    "google/gemma-3-4b-it:fastest",
    "Qwen/Qwen3-4B-Instruct-2507:fastest",
]

QUESTIONS = [
    ("food", "Quels plats camerounais dois-je goûter ?"),
    ("nature", "Propose-moi une activité nature au Cameroun."),
    ("yaounde", "Que puis-je visiter à Yaoundé ?"),
    ("culture", "Parle-moi de la culture camerounaise."),
    ("trip3", "Je viens au Cameroun pendant 3 jours. Que peux-tu me proposer ?"),
]


@dataclass
class RunResult:
    model: str
    question_id: str
    question: str
    run_i: int
    cold: bool
    valid: bool
    error: str | None = None
    http_status: int | None = None
    llm_start_ms: float | None = None
    llm_first_token_ms: float | None = None
    wall_to_first_token_ms: float | None = None
    first_phrase_ready_ms: float | None = None
    time_to_first_phrase_ms: float | None = None
    llm_end_ms: float | None = None
    total_generation_ms: float | None = None
    output_chars: int = 0
    stream_chunks: int = 0
    first_phrase: str = ""
    reply: str = ""
    tokens_per_sec: float | None = None
    phases_ms: dict[str, float] = field(default_factory=dict)


def _stats(values: list[float | None]) -> dict[str, float | int | None]:
    clean = [float(v) for v in values if v is not None and v >= 0]
    if not clean:
        return {"avg": None, "median": None, "min": None, "max": None, "p95": None, "n": 0}
    clean_sorted = sorted(clean)
    n = len(clean_sorted)
    p95 = clean_sorted[min(n - 1, max(0, int(round(0.95 * (n - 1)))))]
    return {
        "avg": round(statistics.mean(clean_sorted), 1),
        "median": round(statistics.median(clean_sorted), 1),
        "min": round(clean_sorted[0], 1),
        "max": round(clean_sorted[-1], 1),
        "p95": round(p95, 1) if n >= 5 else None,
        "n": n,
    }


def _score_reply(question: str, reply: str, kb_preview: str) -> dict[str, int | str]:
    """Lightweight 1–5 heuristic scorer (same rules for every model). Not LLM-as-judge."""
    text = (reply or "").strip()
    if not text:
        return {
            "groundedness": 1,
            "relevance": 1,
            "correctness": 1,
            "brevity": 1,
            "french_quality": 1,
            "cameroon_tourism": 1,
            "notes": "empty",
        }

    lower = text.casefold()
    q_lower = question.casefold()
    kb_lower = (kb_preview or "").casefold()

    # Relevance: overlap with question theme keywords
    themes = {
        "plats": ["plat", "cuisine", "manger", "ndolé", "poulet", "poisson", "sauce"],
        "nature": ["nature", "parc", "mont", "randonnée", "safari", "waza", "lob"],
        "yaound": ["yaound", "musée", "monument", "ville", "visite"],
        "culture": ["culture", "tradition", "langue", "musique", "danse", "peuple"],
        "jours": ["jour", "itinéraire", "visite", "proposer", "journée"],
    }
    theme_hits = 0
    for key, words in themes.items():
        if key in q_lower:
            theme_hits = sum(1 for w in words if w.strip().casefold() in lower)
            break
    relevance = 5 if theme_hits >= 3 else 4 if theme_hits >= 2 else 3 if theme_hits >= 1 else 2

    # Groundedness: share tokens with KB snippet when KB present
    kb_tokens = {t for t in kb_lower.replace(",", " ").split() if len(t) > 4}
    reply_tokens = {t for t in lower.replace(",", " ").split() if len(t) > 4}
    overlap = len(kb_tokens & reply_tokens) if kb_tokens else 0
    if not kb_tokens:
        groundedness = 3
    elif overlap >= 4:
        groundedness = 5
    elif overlap >= 2:
        groundedness = 4
    elif overlap >= 1:
        groundedness = 3
    else:
        groundedness = 2

    # Brevity for voice (~140 max tokens ≈ short paragraph)
    n = len(text)
    if 40 <= n <= 280:
        brevity = 5
    elif n <= 400:
        brevity = 4
    elif n <= 600:
        brevity = 3
    else:
        brevity = 2

    # French quality: crude signals
    fr_markers = [" le ", " la ", " les ", " de ", " du ", " des ", " pour ", " une ", " vous "]
    fr_hits = sum(1 for m in fr_markers if m in f" {lower} ")
    en_markers = [" the ", " you ", " and ", " with ", " visit "]
    en_hits = sum(1 for m in en_markers if m in f" {lower} ")
    if fr_hits >= 4 and en_hits <= 1:
        french = 5
    elif fr_hits >= 2:
        french = 4
    elif en_hits > fr_hits:
        french = 2
    else:
        french = 3

    cameroon = 5 if any(
        w in lower
        for w in ("cameroun", "yaound", "douala", "ndolé", "waza", "kribi", "bafoussam")
    ) else 3

    # Correctness: cannot verify facts offline — neutral 3 unless empty/off-topic
    correctness = 3 if relevance >= 3 else 2

    return {
        "groundedness": groundedness,
        "relevance": relevance,
        "correctness": correctness,
        "brevity": brevity,
        "french_quality": french,
        "cameroon_tourism": cameroon,
        "notes": f"overlap={overlap},theme_hits={theme_hits},chars={n}",
    }


async def build_fixed_messages(
    questions: list[tuple[str, str]],
) -> dict[str, dict[str, Any]]:
    """Build one grounded message payload per question (shared across all models)."""
    from app.services.ai.grounding import build_grounded_system_prompt
    from app.services.ai.prompts import locale_user_suffix
    from app.services.ai.routing import route_query
    from app.services.metrics.latency import PhaseTimer
    from app.services.rag.factory import get_rag_service
    from app.services.search.factory import get_web_search_service
    from app.core.config import get_settings

    settings = get_settings()
    rag = get_rag_service()
    web = get_web_search_service()
    if callable(getattr(rag, "warm", None)):
        await rag.warm()

    fixed: dict[str, dict[str, Any]] = {}
    for qid, text in questions:
        timer = PhaseTimer(f"ground:{qid}")
        route = route_query(text)
        grounding = await build_grounded_system_prompt(
            text,
            history=[],
            rag_service=rag,
            web_search_service=web,
            rag_top_k=max(2, settings.rag_top_k - 1),
            web_search_max_results=min(2, settings.web_search_max_results),
            web_search_timeout_seconds=settings.voice_web_search_timeout_seconds,
            brief=True,
            skip_kb=route.skip_kb,
            skip_web=route.skip_web,
            locale="fr",
            timer=timer,
        )
        messages = [
            {"role": "system", "content": grounding.system_prompt},
            {"role": "user", "content": f"{text}{locale_user_suffix('fr')}"},
        ]
        kb_preview = grounding.system_prompt[-800:]
        fixed[qid] = {
            "question": text,
            "messages": messages,
            "route": {
                "kind": route.kind,
                "skip_kb": route.skip_kb,
                "skip_web": route.skip_web,
            },
            "kb_chunks": len(grounding.chunks),
            "system_chars": len(grounding.system_prompt),
            "kb_preview": kb_preview,
            "grounding_phases_ms": grounding.phases_ms,
        }
        print(
            f"[ground] {qid}: chunks={len(grounding.chunks)} "
            f"sys_chars={len(grounding.system_prompt)} "
            f"phases={grounding.phases_ms}"
        )
    return fixed


async def run_one_stream(
    *,
    model: str,
    qid: str,
    question: str,
    messages: list[dict[str, str]],
    run_i: int,
    cold: bool,
    kb_preview: str,
) -> RunResult:
    """Stream one completion via the same HF client path as production."""
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.speech.voice_chunker import (
        append_token,
        flush_remainder,
        split_ready_phrases,
    )

    # Fresh service instance with ONLY model overridden — all other settings from .env.
    ai = HuggingFaceAIService(model=model)
    result = RunResult(
        model=model,
        question_id=qid,
        question=question,
        run_i=run_i,
        cold=cold,
        valid=False,
    )

    wall0 = time.perf_counter()
    result.llm_start_ms = 0.0
    buf = ""
    first_flush = True
    reply_parts: list[str] = []
    chunks = 0

    try:
        async for token in ai._stream_tokens(messages, brief=True):
            now = time.perf_counter()
            piece = str(token or "")
            if not piece:
                continue
            chunks += 1
            if result.llm_first_token_ms is None:
                result.llm_first_token_ms = round((now - wall0) * 1000, 1)
                result.wall_to_first_token_ms = result.llm_first_token_ms
            reply_parts.append(piece)
            buf = append_token(buf, piece)
            ready, buf = split_ready_phrases(buf, first_chunk=first_flush)
            if ready and result.first_phrase_ready_ms is None:
                result.first_phrase = ready[0]
                result.first_phrase_ready_ms = round((now - wall0) * 1000, 1)
                result.time_to_first_phrase_ms = result.first_phrase_ready_ms
                first_flush = False
        # flush remainder if never soft-flushed
        if result.first_phrase_ready_ms is None:
            for part in flush_remainder(buf):
                result.first_phrase = part
                result.first_phrase_ready_ms = round((time.perf_counter() - wall0) * 1000, 1)
                result.time_to_first_phrase_ms = result.first_phrase_ready_ms
                break

        end = time.perf_counter()
        result.llm_end_ms = round((end - wall0) * 1000, 1)
        result.total_generation_ms = result.llm_end_ms
        result.reply = "".join(reply_parts).strip()
        result.output_chars = len(result.reply)
        result.stream_chunks = chunks
        if result.total_generation_ms and result.total_generation_ms > 0 and result.output_chars:
            # Approx tokens ≈ chars/4 for throughput estimate only.
            approx_tokens = max(1, result.output_chars / 4)
            result.tokens_per_sec = round(
                approx_tokens / (result.total_generation_ms / 1000.0), 2
            )

        if not result.reply:
            result.error = "empty_response"
            result.valid = False
        elif result.wall_to_first_token_ms is None:
            result.error = "no_first_token"
            result.valid = False
        else:
            result.valid = True
    except Exception as exc:  # noqa: BLE001
        msg = str(exc) or type(exc).__name__
        result.error = msg
        result.valid = False
        low = msg.lower()
        if "402" in msg or "credit" in low or "depleted" in low:
            result.error = "FAILED — HTTP 402 (credits depleted)"
            result.http_status = 402
        elif "404" in msg or "not found" in low or "not supported" in low:
            result.error = f"FAILED — unavailable: {msg[:160]}"
            result.http_status = 404
        elif "429" in msg or "busy" in low or "rate" in low:
            result.error = "FAILED — HTTP 429 / provider busy"
            result.http_status = 429
        elif "timeout" in low:
            result.error = "FAILED — timeout"
        result.llm_end_ms = round((time.perf_counter() - wall0) * 1000, 1)

    return result


async def probe_model(model: str) -> dict[str, Any]:
    """Tiny non-stream ping to classify availability before full runs."""
    import httpx
    from app.core.config import get_settings

    settings = get_settings()
    token = (settings.huggingface_hub_token or settings.hf_token).strip()
    base = settings.hf_api_base_url.rstrip("/")
    body = {
        "model": model,
        "messages": [{"role": "user", "content": "Réponds: OK"}],
        "max_tokens": 4,
        "temperature": 0.45,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    try:
        async with httpx.AsyncClient(base_url=base, timeout=40.0) as client:
            r = await client.post(
                "/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
        payload: dict[str, Any] = {}
        try:
            payload = r.json()
        except Exception:
            payload = {}
        err = ""
        if isinstance(payload.get("error"), dict):
            err = str(payload["error"].get("message") or "")
        choices = payload.get("choices") or []
        text = ""
        if choices:
            text = str((choices[0].get("message") or {}).get("content") or "")
        available = r.status_code == 200 and bool(text.strip())
        return {
            "model": model,
            "http_status": r.status_code,
            "available": available,
            "error": err[:200],
            "sample": text[:40],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "model": model,
            "http_status": None,
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
            "sample": "",
        }


def write_markdown(payload: dict[str, Any]) -> None:
    lines: list[str] = [
        "# Phase 1.5 — LLM latency benchmark",
        "",
        "Isolated HF Inference Providers comparison. **Production model unchanged.**",
        "",
        f"- Provider base: `{payload.get('hf_api_base_url')}`",
        f"- Production baseline: `{payload.get('production_model')}`",
        f"- Voice params: temperature=0.45, max_tokens="
        f"`{payload.get('voice_max_tokens')}`, stream=True, brief/voice grounding",
        f"- Runs requested per model×question: {payload.get('runs_requested')}",
        "",
        "## Availability probe",
        "",
        "| Model | HTTP | Available | Note |",
        "|-------|-----:|:---------:|------|",
    ]
    for row in payload.get("availability", []):
        lines.append(
            f"| `{row['model']}` | {row.get('http_status')} | "
            f"{'yes' if row.get('available') else 'no'} | "
            f"{(row.get('error') or row.get('sample') or '')[:80]} |"
        )

    lines += [
        "",
        "## Latency summary (valid runs only)",
        "",
        "| Model | Valid | Fail | TTFT avg | TTFT median | First phrase avg | Generation avg | Errors |",
        "|-------|------:|-----:|---------:|------------:|-----------------:|---------------:|--------|",
    ]
    for model, summary in (payload.get("per_model") or {}).items():
        ttft = summary.get("wall_to_first_token_ms") or {}
        phrase = summary.get("time_to_first_phrase_ms") or {}
        gen = summary.get("total_generation_ms") or {}
        err = ", ".join(summary.get("error_counts", {}).keys()) or "—"
        lines.append(
            f"| `{model}` | {summary.get('valid_n', 0)} | {summary.get('failed_n', 0)} | "
            f"{ttft.get('avg')} | {ttft.get('median')} | {phrase.get('avg')} | "
            f"{gen.get('avg')} | {err[:40]} |"
        )

    lines += [
        "",
        "## Cold vs warm TTFT",
        "",
        "| Model | Cold n | Cold avg | Warm n | Warm avg |",
        "|-------|-------:|---------:|-------:|---------:|",
    ]
    for model, summary in (payload.get("per_model") or {}).items():
        c = summary.get("cold_ttft_ms") or {}
        w = summary.get("warm_ttft_ms") or {}
        lines.append(
            f"| `{model}` | {c.get('n', 0)} | {c.get('avg')} | {w.get('n', 0)} | {w.get('avg')} |"
        )

    lines += [
        "",
        "## Qualitative (1–5 heuristic, same rules for all models)",
        "",
        "| Model | Groundedness | Relevance | Correctness | French | Voice brevity | Cameroon |",
        "|-------|-------------:|----------:|------------:|-------:|--------------:|---------:|",
    ]
    for model, summary in (payload.get("per_model") or {}).items():
        q = summary.get("quality_avg") or {}
        if not q:
            lines.append(f"| `{model}` | — | — | — | — | — | — |")
            continue
        lines.append(
            f"| `{model}` | {q.get('groundedness')} | {q.get('relevance')} | "
            f"{q.get('correctness')} | {q.get('french_quality')} | "
            f"{q.get('brevity')} | {q.get('cameroon_tourism')} |"
        )

    lines += [
        "",
        "## Conclusion",
        "",
        payload.get("conclusion") or "See JSON for raw runs.",
        "",
        "## Notes",
        "",
        "- Greeting cache bypassed (no « Bonjour » questions).",
        "- Grounding/RAG computed **once per question** and reused for every model.",
        "- HTTP 402/404/429 recorded as FAILED — never estimated.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


async def main_async(args: argparse.Namespace) -> int:
    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    runs = max(1, int(args.runs))

    print("=== Phase 1.5 LLM latency benchmark ===")
    print(f"production model (unchanged): {settings.hf_model_id}")
    print(f"candidates: {models}")
    print(f"runs/question: {runs}")

    availability = []
    for model in models:
        row = await probe_model(model)
        availability.append(row)
        print(
            f"[probe] {model}: status={row['http_status']} "
            f"available={row['available']} err={row['error'][:80]}"
        )

    fixed = await build_fixed_messages(QUESTIONS)

    all_runs: list[RunResult] = []
    seen_model_request: set[str] = set()
    models_exhausted: set[str] = set()

    # Interleave by question so each model gets similar warm/cold mix timing,
    # but still mark first successful/attempted request per model as cold.
    for qid, question in QUESTIONS:
        payload = fixed[qid]
        messages = payload["messages"]
        for model in models:
            probe = next(p for p in availability if p["model"] == model)
            if model in models_exhausted or (
                args.skip_unavailable and not probe["available"]
            ):
                for i in range(runs):
                    all_runs.append(
                        RunResult(
                            model=model,
                            question_id=qid,
                            question=question,
                            run_i=i,
                            cold=False,
                            valid=False,
                            error=(
                                f"FAILED — skipped after probe/exhaustion "
                                f"HTTP {probe.get('http_status')}: "
                                f"{(probe.get('error') or 'unavailable')[:120]}"
                            ),
                            http_status=probe.get("http_status") or 402,
                        )
                    )
                continue

            for i in range(runs):
                cold = model not in seen_model_request
                seen_model_request.add(model)
                print(f"\n--- {model} | {qid}[{i}] cold={cold} ---")
                result = await run_one_stream(
                    model=model,
                    qid=qid,
                    question=question,
                    messages=messages,
                    run_i=i,
                    cold=cold,
                    kb_preview=payload["kb_preview"],
                )
                # Brief retry once on transient 402 (credits sometimes flicker).
                if (
                    not result.valid
                    and result.http_status == 402
                    and not args.no_retry_402
                ):
                    await asyncio.sleep(2.0)
                    result = await run_one_stream(
                        model=model,
                        qid=qid,
                        question=question,
                        messages=messages,
                        run_i=i,
                        cold=cold,
                        kb_preview=payload["kb_preview"],
                    )
                    if result.valid:
                        print("  (recovered after 402 retry)")
                all_runs.append(result)
                if result.valid:
                    print(
                        f"  TTFT={result.wall_to_first_token_ms}ms "
                        f"phrase={result.time_to_first_phrase_ms}ms "
                        f"total={result.total_generation_ms}ms "
                        f"chars={result.output_chars} "
                        f"phrase={result.first_phrase!r}"
                    )
                else:
                    print(f"  INVALID: {result.error}")
                    if result.http_status == 402:
                        models_exhausted.add(model)
                        for j in range(i + 1, runs):
                            all_runs.append(
                                RunResult(
                                    model=model,
                                    question_id=qid,
                                    question=question,
                                    run_i=j,
                                    cold=False,
                                    valid=False,
                                    error="FAILED — HTTP 402 (credits depleted) [skipped]",
                                    http_status=402,
                                )
                            )
                        break

    # Aggregate
    per_model: dict[str, Any] = {}
    for model in models:
        model_runs = [r for r in all_runs if r.model == model]
        valid = [r for r in model_runs if r.valid]
        failed = [r for r in model_runs if not r.valid]
        error_counts: dict[str, int] = {}
        for r in failed:
            key = (r.error or "unknown")[:80]
            error_counts[key] = error_counts.get(key, 0) + 1

        quality_rows = []
        for r in valid:
            quality_rows.append(
                _score_reply(
                    r.question,
                    r.reply,
                    fixed[r.question_id]["kb_preview"],
                )
            )
        quality_avg = None
        if quality_rows:
            keys = [
                "groundedness",
                "relevance",
                "correctness",
                "brevity",
                "french_quality",
                "cameroon_tourism",
            ]
            quality_avg = {
                k: round(statistics.mean(float(row[k]) for row in quality_rows), 2)
                for k in keys
            }

        cold_vals = [r.wall_to_first_token_ms for r in valid if r.cold]
        warm_vals = [r.wall_to_first_token_ms for r in valid if not r.cold]
        per_model[model] = {
            "valid_n": len(valid),
            "failed_n": len(failed),
            "wall_to_first_token_ms": _stats([r.wall_to_first_token_ms for r in valid]),
            "time_to_first_phrase_ms": _stats([r.time_to_first_phrase_ms for r in valid]),
            "total_generation_ms": _stats([r.total_generation_ms for r in valid]),
            "output_chars": _stats([float(r.output_chars) for r in valid]),
            "tokens_per_sec": _stats([r.tokens_per_sec for r in valid]),
            "cold_ttft_ms": _stats(cold_vals),
            "warm_ttft_ms": _stats(warm_vals),
            "error_counts": error_counts,
            "quality_avg": quality_avg,
            "sample_replies": [
                {
                    "question_id": r.question_id,
                    "reply": r.reply[:240],
                    "first_phrase": r.first_phrase,
                }
                for r in valid[:5]
            ],
        }

    # Conclusion (data-driven, no invented numbers)
    conclusion_parts = []
    baseline = settings.hf_model_id
    baseline_stats = per_model.get(baseline) or per_model.get(models[0], {})
    base_ttft = (baseline_stats.get("wall_to_first_token_ms") or {}).get("avg")
    if base_ttft is None:
        conclusion_parts.append(
            "Aucun run valide obtenu pour le modèle de production — "
            "surtout HTTP 402 (crédits HF épuisés). "
            "**Aucune estimation TTFT inventée.** "
            "Relancer ce script quand les crédits Inference Providers seront disponibles."
        )
    else:
        conclusion_parts.append(
            f"Baseline `{baseline}` TTFT avg = {base_ttft} ms "
            f"(n={baseline_stats['wall_to_first_token_ms']['n']})."
        )
        for model, summary in per_model.items():
            if model == baseline:
                continue
            ttft = (summary.get("wall_to_first_token_ms") or {}).get("avg")
            if ttft is None:
                conclusion_parts.append(
                    f"`{model}`: pas de mesure valide ({summary.get('error_counts')})."
                )
                continue
            delta = round(base_ttft - ttft, 1)
            direction = "plus rapide" if delta > 0 else "plus lent"
            conclusion_parts.append(
                f"`{model}` TTFT avg = {ttft} ms ({abs(delta)} ms {direction} vs baseline)."
            )
        conclusion_parts.append(
            "Phase 1.6 pourra changer le modèle de production seulement si un candidat "
            "réduit clairement wall_to_first_token sans régression qualitative majeure."
        )

    payload = {
        "phase": "1.5",
        "hf_api_base_url": settings.hf_api_base_url,
        "production_model": settings.hf_model_id,
        "voice_max_tokens": settings.llm_voice_max_tokens,
        "temperature": 0.45,
        "runs_requested": runs,
        "models": models,
        "questions": QUESTIONS,
        "availability": availability,
        "grounding_fixed": {
            qid: {
                "kb_chunks": fixed[qid]["kb_chunks"],
                "system_chars": fixed[qid]["system_chars"],
                "route": fixed[qid]["route"],
                "grounding_phases_ms": fixed[qid]["grounding_phases_ms"],
            }
            for qid in fixed
        },
        "per_model": per_model,
        "runs": [asdict(r) for r in all_runs],
        "conclusion": " ".join(conclusion_parts),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown(payload)
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(payload["conclusion"])
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1.5 LLM latency benchmark")
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_MODEL_CANDIDATES),
        help="Comma-separated HF model ids (OpenAI-compatible router)",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Valid-run target per model×question (default 3; use 5 when credits allow)",
    )
    parser.add_argument(
        "--skip-unavailable",
        action="store_true",
        default=True,
        help="Skip full runs when probe shows model unavailable (default true)",
    )
    parser.add_argument(
        "--no-skip-unavailable",
        action="store_false",
        dest="skip_unavailable",
        help="Attempt full runs even if probe failed",
    )
    parser.add_argument(
        "--no-retry-402",
        action="store_true",
        default=False,
        help="Do not retry once after HTTP 402",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
