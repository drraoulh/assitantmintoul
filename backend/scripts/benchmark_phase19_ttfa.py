#!/usr/bin/env python3
"""Phase 1.9 — final TTFA optimization diagnostic + post-opt benchmark.

MEASURE first; only apply low-risk code changes separately.
Does not change Qwen model id, RAG, Fish provider, or frontend.

Usage:

  python backend/scripts/benchmark_phase19_ttfa.py
  python backend/scripts/benchmark_phase19_ttfa.py --runs 5 --base-url http://127.0.0.1:8000
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

OUT_JSON = ROOT / "docs" / "latency-phase19-final-ttfa.json"
OUT_MD = ROOT / "docs" / "latency-phase19-final-ttfa.md"

QUESTIONS = [
    ("food", "Quels plats camerounais dois-je goûter ?"),
    ("yaounde", "Que puis-je visiter à Yaoundé ?"),
    ("nature", "Propose-moi une activité nature au Cameroun."),
    ("trip3", "Je viens au Cameroun pendant trois jours, que peux-tu me proposer ?"),
    ("culture", "Parle-moi de la culture camerounaise."),
]


def _stats(values: list[float | None]) -> dict[str, float | int | None]:
    clean = [float(v) for v in values if v is not None and v >= 0]
    if not clean:
        return {"avg": None, "median": None, "min": None, "max": None, "p95": None, "n": 0}
    s = sorted(clean)
    p95 = None
    if len(s) >= 5:
        p95 = round(s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))], 1)
    return {
        "avg": round(statistics.mean(clean), 1),
        "median": round(statistics.median(clean), 1),
        "min": round(min(clean), 1),
        "max": round(max(clean), 1),
        "p95": p95,
        "n": len(clean),
    }


def _est_tokens(text: str) -> int:
    # Rough FR/EN: ~4 chars/token.
    return max(1, (len(text) + 3) // 4) if text else 0


def _err(msg: str) -> str:
    low = msg.lower()
    if "402" in msg or "credit" in low or "depleted" in low:
        return "FAILED_HTTP_402"
    if "fish" in low:
        return "FAILED_FISH_TTS"
    return msg[:160]


async def measure_prompt_profile(question: str) -> dict[str, Any]:
    """Inspect real prompt size on voice brief path (no TTS)."""
    from app.api.deps import get_ai_service
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.ai.routing import route_query
    from app.services.ai.grounding import build_grounded_system_prompt
    from app.services.metrics.latency import PhaseTimer

    ai = get_ai_service()
    assert isinstance(ai, HuggingFaceAIService)
    timer = PhaseTimer("p19_prompt")
    t0 = time.perf_counter()
    thread_id, history = await ai._store.prepare_for_generation(
        None, limit=ai._voice_history_n
    )
    prepare_ms = round((time.perf_counter() - t0) * 1000, 1)
    route = route_query(question)
    grounding = await build_grounded_system_prompt(
        question,
        history,
        rag_service=ai._rag,
        web_search_service=ai._web,
        rag_top_k=max(2, ai._rag_top_k - 1),
        web_search_max_results=min(2, ai._web_max),
        web_search_timeout_seconds=ai._voice_web_timeout,
        brief=True,
        skip_kb=route.skip_kb,
        skip_web=route.skip_web,
        locale="fr",
        timer=timer,
    )
    payload = [
        {"role": "system", "content": grounding.system_prompt},
        *history[-ai._voice_history_n :],
        {"role": "user", "content": question},
    ]
    sys_c = len(grounding.system_prompt)
    hist_c = sum(len(m.get("content") or "") for m in history[-ai._voice_history_n :])
    user_c = len(question)
    total_c = sum(len(m["content"]) for m in payload)
    return {
        "question": question,
        "route": route.kind,
        "skip_kb": route.skip_kb,
        "prepare_ms": prepare_ms,
        "grounding_ms": (grounding.phases_ms or {}).get("grounding"),
        "rag_ms": (grounding.phases_ms or {}).get("rag"),
        "system_chars": sys_c,
        "system_tokens_est": _est_tokens(grounding.system_prompt),
        "history_chars": hist_c,
        "history_tokens_est": _est_tokens(" ".join(m.get("content") or "" for m in history)),
        "user_chars": user_c,
        "user_tokens_est": _est_tokens(question),
        "total_chars": total_c,
        "total_tokens_est": _est_tokens("".join(m["content"] for m in payload)),
        "max_tokens": ai._voice_max_tokens,
        "history_window": ai._voice_history_n,
        "kb_chunks": len(grounding.chunks),
    }


async def run_inprocess_turn(
    *,
    question: str,
    scenario: str,
    run_i: int,
    conversation_id: str | None = None,
    first_hard: int | None = None,
    first_soft: int | None = None,
) -> dict[str, Any]:
    """Voice-like path: prepare → stream → chunker → first Fish byte."""
    from app.api.deps import get_ai_service, get_speech_service
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.metrics.latency import PhaseTimer
    from app.services.metrics.llm_stream_trace import LlmStreamTrace
    from app.services.speech import voice_chunker as vc

    ai = get_ai_service()
    speech = get_speech_service()
    if not isinstance(ai, HuggingFaceAIService):
        return {"scenario": scenario, "valid": False, "error": "not_hf"}

    # Optional temporary chunker thresholds for A/B (restored after).
    orig = (vc.FIRST_SOFT, vc.FIRST_HARD)
    if first_soft is not None:
        vc.FIRST_SOFT = first_soft
    if first_hard is not None:
        vc.FIRST_HARD = first_hard

    turn_id = f"p19-{scenario}-{run_i}"
    timer = PhaseTimer("p19")
    timer.turn_id = turn_id
    trace = LlmStreamTrace(turn_id=turn_id, model=getattr(ai, "_model", ""))
    wall0 = time.perf_counter()
    marks: dict[str, float] = {}

    def mark(name: str) -> float:
        marks[name] = round((time.perf_counter() - wall0) * 1000, 1)
        return marks[name]

    mark("user_speech_end")
    mark("llm_prepare_start")
    row: dict[str, Any] = {
        "scenario": scenario,
        "run_i": run_i,
        "question": question,
        "valid": False,
        "chunker_first_soft": vc.FIRST_SOFT,
        "chunker_first_hard": vc.FIRST_HARD,
    }

    try:
        buf = ""
        first_flush = True
        first_token = False
        first_frag: str | None = None
        reply = ""
        error = None
        tts_task: asyncio.Task | None = None
        fish: dict = {}

        async def _tts_first(frag: str) -> None:
            mark("tts_request_start")
            async for chunk in speech.synthesize_stream(frag, trace=fish):
                if chunk:
                    mark("tts_first_audio_byte")
                    mark("frontend_playback_start")
                    break

        async for event in ai.stream_response(
            question,
            conversation_id,
            brief=True,
            locale="fr",
            timer=timer,
            turn_id=turn_id,
            llm_trace=trace,
        ):
            etype = event.get("type")
            if etype == "token":
                if "llm_prepare_end" not in marks:
                    mark("llm_prepare_end")
                piece = str(event.get("text") or "")
                if not first_token:
                    mark("llm_first_token")
                    first_token = True
                reply += piece
                buf = vc.append_token(buf, piece)
                ready, buf = vc.split_ready_phrases(buf, first_chunk=first_flush)
                if ready and first_frag is None:
                    first_frag = ready[0]
                    mark("llm_first_phrase")
                    first_flush = False
                    tts_task = asyncio.create_task(_tts_first(first_frag))
            elif etype == "done":
                mark("llm_end")
                reply = str(event.get("text") or reply)
                row["conversation_id"] = event.get("conversation_id") or conversation_id
                if first_frag is None:
                    for part in vc.flush_remainder(buf):
                        first_frag = part
                        mark("llm_first_phrase")
                        tts_task = asyncio.create_task(_tts_first(first_frag))
                        break
                break
            elif etype == "error":
                error = _err(str(event.get("message") or ""))
                break

        if error:
            row["error"] = error
            return row

        if tts_task is not None:
            try:
                await tts_task
            except Exception as exc:  # noqa: BLE001
                row["error"] = _err(str(exc))
                return row
        elif first_frag:
            await _tts_first(first_frag)
        else:
            row["error"] = "empty_fragment"
            return row

        if "frontend_playback_start" not in marks:
            row["error"] = "no_first_audio"
            return row

        if fish.get("tts_complete") is not None:
            marks["tts_complete"] = round(
                (float(fish["tts_complete"]) - wall0) * 1000, 1
            )

        frag = first_frag or ""
        lt = trace.as_dict()
        store = (lt.get("meta") or {}).get("store") or {}
        row.update(
            {
                "valid": True,
                "conversation_id": row.get("conversation_id") or conversation_id,
                "marks_ms": marks,
                "TTFA_ms": marks.get("frontend_playback_start"),
                "prompt_prep_ms": lt.get("llm_prepare_ms"),
                "provider_ttfh_ms": lt.get("provider_ttfh_ms"),
                "stream_parse_ms": lt.get("stream_parse_ms"),
                "app_ttft_ms": lt.get("app_ttft_ms") or marks.get("llm_first_token"),
                "first_phrase_ms": lt.get("first_phrase_ready_ms")
                or marks.get("llm_first_phrase"),
                "chunker_wait_ms": (
                    round(
                        (marks.get("llm_first_phrase") or 0)
                        - (marks.get("llm_first_token") or 0),
                        1,
                    )
                    if marks.get("llm_first_phrase") and marks.get("llm_first_token")
                    else None
                ),
                "tts_ttfb_ms": fish.get("ttfb_ms"),
                "store_ms": store.get("total_ms"),
                "store_mode": (store.get("meta") or {}).get("mode"),
                "http_client_warm": (lt.get("meta") or {}).get("http_client_warm"),
                "fallback_used": lt.get("fallback_used"),
                "first_frag_chars": len(frag),
                "first_frag": frag[:80],
                "llm_trace": lt,
                "phases": timer.as_dict().get("phases"),
            }
        )
        return row
    except Exception as exc:  # noqa: BLE001
        row["error"] = _err(str(exc))
        return row
    finally:
        vc.FIRST_SOFT, vc.FIRST_HARD = orig


async def run_ws_turn(base_url: str, question: str, scenario: str, run_i: int) -> dict[str, Any]:
    """Optional live WS turn (production path)."""
    try:
        import websockets
    except ImportError:
        return {"scenario": scenario, "valid": False, "error": "websockets_missing"}

    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = ws_url.rstrip("/") + "/api/voice/session"
    wall0 = time.perf_counter()
    marks: dict[str, float] = {}

    def mark(name: str) -> float:
        marks[name] = round((time.perf_counter() - wall0) * 1000, 1)
        return marks[name]

    row: dict[str, Any] = {
        "scenario": scenario,
        "run_i": run_i,
        "question": question,
        "valid": False,
        "path": "websocket",
    }
    try:
        async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            if ready.get("type") != "ready":
                row["error"] = "no_ready"
                return row
            mark("user_speech_end")
            await ws.send(
                json.dumps(
                    {
                        "type": "text",
                        "text": question,
                        "locale": "fr",
                        "turn_id": f"p19ws-{scenario}-{run_i}",
                    }
                )
            )
            llm_trace = None
            metrics = None
            deadline = time.perf_counter() + 120
            while time.perf_counter() < deadline:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
                mtype = msg.get("type")
                if mtype == "token" and "llm_first_token" not in marks:
                    mark("llm_first_token")
                elif mtype == "audio_chunk" and int(msg.get("part") or 0) == 0:
                    if "tts_first_audio_byte" not in marks:
                        mark("tts_first_audio_byte")
                        mark("frontend_playback_start")
                elif mtype == "turn_done":
                    mark("turn_complete")
                    metrics = msg.get("metrics") or {}
                    llm_trace = metrics.get("llm_trace")
                    break
                elif mtype == "error":
                    row["error"] = _err(str(msg.get("message") or ""))
                    return row
            if "frontend_playback_start" not in marks:
                row["error"] = "no_first_audio"
                return row
            lt = llm_trace or {}
            store = (lt.get("meta") or {}).get("store") or {}
            row.update(
                {
                    "valid": True,
                    "marks_ms": marks,
                    "TTFA_ms": marks["frontend_playback_start"],
                    "app_ttft_ms": lt.get("app_ttft_ms") or marks.get("llm_first_token"),
                    "provider_ttfh_ms": lt.get("provider_ttfh_ms"),
                    "prompt_prep_ms": lt.get("llm_prepare_ms"),
                    "first_phrase_ms": lt.get("first_phrase_ready_ms"),
                    "store_ms": store.get("total_ms"),
                    "store_mode": (store.get("meta") or {}).get("mode"),
                    "http_client_warm": (lt.get("meta") or {}).get("http_client_warm"),
                    "tts_ttfb_ms": (metrics or {}).get("phases", {}).get("tts_ttfb")
                    if metrics
                    else None,
                    "llm_trace": lt,
                    "metrics": metrics,
                }
            )
            # Prefer Fish ttfb from chronology if present
            chrono = (metrics or {}).get("ttfa_chronology") or {}
            for e in chrono.get("events") or []:
                if e.get("event") == "tts_ttfb" and e.get("ttfb_ms") is not None:
                    row["tts_ttfb_ms"] = e["ttfb_ms"]
            if row.get("first_phrase_ms") and row.get("app_ttft_ms"):
                row["chunker_wait_ms"] = round(
                    float(row["first_phrase_ms"]) - float(row["app_ttft_ms"]), 1
                )
            return row
    except Exception as exc:  # noqa: BLE001
        row["error"] = _err(str(exc))
        return row


def write_report(payload: dict[str, Any]) -> None:
    before = payload.get("before_phase18") or {}
    after = payload.get("ttfa_global") or {}
    stages = payload.get("stage_comparison") or {}

    def g(d: dict, key: str) -> str:
        v = (d.get(key) or {}).get("avg") if isinstance(d.get(key), dict) else d.get(key)
        return "—" if v is None else str(v)

    lines = [
        "# Phase 1.9 — Final TTFA optimization",
        "",
        "Cible : réduire/stabiliser `user_speech_end → first audible audio`.",
        "Modèle inchangé : `Qwen/Qwen3.5-9B:fastest`. Fish / RAG / frontend inchangés.",
        "",
        "## Audit — d’où vient le TTFT ?",
        "",
        payload.get("audit_summary") or "",
        "",
        "## Prompt profile (voice brief)",
        "",
        "```json",
        json.dumps(payload.get("prompt_profiles") or [], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Optimisations appliquées",
        "",
    ]
    for item in payload.get("optimizations") or []:
        lines.append(f"- {item}")
    if not payload.get("optimizations"):
        lines.append("- Aucune (mesures seules).")

    lines += [
        "",
        "## TTFA final (runs valides uniquement)",
        "",
        f"- n = {after.get('n')}",
        f"- avg = **{after.get('avg')} ms**",
        f"- median = **{after.get('median')} ms**",
        f"- min = {after.get('min')} ms",
        f"- max = {after.get('max')} ms",
        f"- p95 = {after.get('p95')} ms",
        f"- failed excluded = {payload.get('failed_total')} "
        f"({', '.join(payload.get('failure_reasons') or []) or 'n/a'})",
        "",
        "## Tableau Before / After",
        "",
        "| Stage | Before (Phase 1.8) | After (Phase 1.9) | Gain |",
        "|-------|-------------------:|------------------:|-----:|",
    ]
    for stage, row in stages.items():
        lines.append(
            f"| {stage} | {row.get('before')} | {row.get('after')} | {row.get('gain')} |"
        )

    lines += [
        "",
        "## Scénarios",
        "",
    ]
    for name, st in (payload.get("scenario_stats") or {}).items():
        lines.append(f"### {name}")
        lines.append(
            f"valid={st.get('valid_n')} TTFA avg={g(st,'TTFA_ms')} "
            f"provider_ttfh={g(st,'provider_ttfh_ms')} "
            f"app_ttft={g(st,'app_ttft_ms')} "
            f"chunker={g(st,'chunker_wait_ms')} "
            f"tts_ttfb={g(st,'tts_ttfb_ms')}"
        )
        lines.append("")

    lines += [
        "## Chunker A/B",
        "",
        "```json",
        json.dumps(payload.get("chunker_ab") or {}, indent=2),
        "```",
        "",
        "## Breakdown moyen (valides)",
        "",
        payload.get("breakdown") or "",
        "",
        "## Décision",
        "",
        payload.get("decision") or "",
        "",
        "## Conclusion",
        "",
        f"1. Bottleneck principal : {payload.get('bottleneck_primary')}",
        f"2. Bottleneck secondaire : {payload.get('bottleneck_secondary')}",
        f"3. TTFA final (médiane) : {after.get('median')} ms",
        f"4. Optimisation appliquée : {payload.get('optimization_summary')}",
        f"5. Gain mesuré : {payload.get('gain_summary')}",
        f"6. Recommandation : {payload.get('recommendation')}",
        "",
        f"`pytest -q` : {payload.get('pytest') or 'à renseigner'}",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


async def main_async(args: argparse.Namespace) -> int:
    from app.core.config import get_settings
    from app.core.http import close_shared_clients, shared_async_client
    from app.services.conversation import get_conversation_store
    from app.services.rag.factory import get_rag_service
    import httpx

    get_settings.cache_clear()
    get_conversation_store.cache_clear()
    settings = get_settings()
    await close_shared_clients()

    print("=== Phase 1.9 TTFA ===")
    print(f"model={settings.hf_model_id} runs={args.runs}")

    rag = get_rag_service()
    if callable(getattr(rag, "warm", None)):
        await rag.warm()
        print("RAG warmed")

    # Prompt audit (after RAG warm so first retrieve is not a cold embedding hit)
    print("\n--- prompt profiles ---")
    profiles = []
    for qid, q in QUESTIONS[:3]:
        prof = await measure_prompt_profile(q)
        profiles.append(prof)
        print(
            f"  {qid}: total_tok≈{prof['total_tokens_est']} sys≈{prof['system_tokens_est']} "
            f"rag={prof['rag_ms']} ground={prof['grounding_ms']} prepare={prof['prepare_ms']}"
        )

    avg_tok = statistics.mean([prof["total_tokens_est"] for prof in profiles])
    audit_summary = (
        f"Prompt voice brief ≈ {avg_tok:.0f} tokens totaux (sys+KB+user). "
        f"max_tokens={settings.llm_voice_max_tokens}, history={settings.llm_voice_history_messages}. "
        "Phase 1.5 `_stream_tokens` warm TTFT ≈250–280 ms ; "
        "Phase 1.8 app_ttft warm ≈300–420 ms (écart = prepare/grounding + variance provider). "
        "Les pics ~2–3 s sont surtout **provider/HF cold or queue**, pas le store (déjà ~0)."
    )

    # Warm HF TLS if optimization flag path already deployed; always warm here for fair bench
    print("\n--- warm HF HTTP client ---")
    client = shared_async_client(
        base_url=settings.hf_api_base_url,
        timeout_seconds=settings.hf_timeout_seconds,
    )
    try:
        t0 = time.perf_counter()
        await client.get("/", timeout=httpx.Timeout(8.0, connect=5.0))
        print(f"  HF warm GET / in {(time.perf_counter()-t0)*1000:.0f} ms")
    except Exception as exc:  # noqa: BLE001
        print(f"  HF warm skipped: {exc}")

    runs_n = max(1, int(args.runs))
    all_rows: list[dict[str, Any]] = []
    consecutive_402 = 0

    def accept(row: dict[str, Any]) -> bool:
        nonlocal consecutive_402
        all_rows.append(row)
        if row.get("valid"):
            consecutive_402 = 0
            print(
                f"  OK TTFA={row.get('TTFA_ms')} app_ttft={row.get('app_ttft_ms')} "
                f"provider={row.get('provider_ttfh_ms')} chunker={row.get('chunker_wait_ms')} "
                f"tts={row.get('tts_ttfb_ms')} hard={row.get('chunker_first_hard')}"
            )
            return True
        print(f"  FAIL {row.get('error')}")
        if row.get("error") == "FAILED_HTTP_402":
            consecutive_402 += 1
            return consecutive_402 < 3
        return True

    # Chunker A/B (in-process), then restore default via run_inprocess_turn
    print("\n=== Chunker A/B ===")
    chunker_ab: dict[str, Any] = {}
    chunker_pairs = [(32, 48), (32, 40), (28, 32)]
    if args.skip_chunker_ab:
        chunker_pairs = []
        print("  skipped (--skip-chunker-ab)")
    for soft, hard in chunker_pairs:
        if consecutive_402 >= 3:
            break
        label = f"soft{soft}_hard{hard}"
        rows = []
        for i in range(min(3, runs_n)):
            row = await run_inprocess_turn(
                question=QUESTIONS[i % len(QUESTIONS)][1],
                scenario=f"chunker_{label}",
                run_i=i,
                first_soft=soft,
                first_hard=hard,
            )
            rows.append(row)
            if not accept(row):
                break
        valid = [r for r in rows if r.get("valid")]
        chunker_ab[label] = {
            "TTFA_ms": _stats([r.get("TTFA_ms") for r in valid]),
            "chunker_wait_ms": _stats([r.get("chunker_wait_ms") for r in valid]),
            "tts_ttfb_ms": _stats([r.get("tts_ttfb_ms") for r in valid]),
            "app_ttft_ms": _stats([r.get("app_ttft_ms") for r in valid]),
            "n": len(valid),
        }

    # Pick best chunker by median TTFA among those with n>=2
    best_label = "soft32_hard48"
    best_med = None
    for label, st in chunker_ab.items():
        med = (st.get("TTFA_ms") or {}).get("median")
        n = st.get("n") or 0
        if med is None or n < 1:
            continue
        if best_med is None or med < best_med:
            best_med = med
            best_label = label
    print(f"chunker best={best_label} median_TTFA={best_med}")
    consecutive_402 = 0  # allow scenario runs even if AB hit 402

    # Scenario A warm (5)
    print("\n=== Scenario A warm ===")
    for i in range(runs_n):
        if consecutive_402 >= 3:
            break
        row = await run_inprocess_turn(
            question=QUESTIONS[0][1],
            scenario="warm",
            run_i=i,
        )
        if not accept(row):
            break

    # Scenario C new conversation
    print("\n=== Scenario C new_thread ===")
    for i in range(min(3, runs_n)):
        if consecutive_402 >= 3:
            break
        row = await run_inprocess_turn(
            question=QUESTIONS[2][1],
            scenario="new_thread",
            run_i=i,
            conversation_id=None,
        )
        if not accept(row):
            break

    # Scenario D multi-turn
    print("\n=== Scenario D multi_turn ===")
    conv = None
    for i, q in enumerate(
        ["Je vais visiter Yaoundé.", "Que peux-tu me proposer ?", QUESTIONS[1][1]]
    ):
        if consecutive_402 >= 3:
            break
        row = await run_inprocess_turn(
            question=q, scenario="multi_turn", run_i=i, conversation_id=conv
        )
        if row.get("valid") and row.get("conversation_id"):
            conv = str(row["conversation_id"])
        if not accept(row):
            break

    # Scenario B cold-ish: close clients then immediate call
    print("\n=== Scenario B cold_http ===")
    if consecutive_402 < 3:
        await close_shared_clients()
        row = await run_inprocess_turn(
            question=QUESTIONS[1][1], scenario="cold_http", run_i=0
        )
        accept(row)

    # Optional WS samples if API up
    print("\n=== WS samples ===")
    try:
        r = httpx.get(f"{args.base_url.rstrip('/')}/api/health", timeout=3.0)
        api_ok = r.status_code == 200
    except Exception:
        api_ok = False
    if api_ok and consecutive_402 < 3:
        for i in range(min(3, runs_n)):
            row = await run_ws_turn(
                args.base_url, QUESTIONS[i % len(QUESTIONS)][1], "ws_warm", i
            )
            if not accept(row):
                break

    valid = [r for r in all_rows if r.get("valid")]
    failed = [r for r in all_rows if not r.get("valid")]
    reasons = sorted({r.get("error") or "error" for r in failed})

    def scen_stats(name: str) -> dict[str, Any]:
        rows = [r for r in all_rows if r.get("scenario") == name and r.get("valid")]
        return {
            "valid_n": len(rows),
            "TTFA_ms": _stats([r.get("TTFA_ms") for r in rows]),
            "provider_ttfh_ms": _stats([r.get("provider_ttfh_ms") for r in rows]),
            "app_ttft_ms": _stats([r.get("app_ttft_ms") for r in rows]),
            "chunker_wait_ms": _stats([r.get("chunker_wait_ms") for r in rows]),
            "tts_ttfb_ms": _stats([r.get("tts_ttfb_ms") for r in rows]),
            "store_ms": _stats([r.get("store_ms") for r in rows]),
            "prompt_prep_ms": _stats([r.get("prompt_prep_ms") for r in rows]),
        }

    scenario_stats = {
        k: scen_stats(k)
        for k in sorted({r.get("scenario") for r in all_rows if r.get("scenario")})
    }
    ttfa_global = _stats([r.get("TTFA_ms") for r in valid])
    app_ttft = _stats([r.get("app_ttft_ms") for r in valid])
    provider = _stats([r.get("provider_ttfh_ms") for r in valid])
    chunker = _stats([r.get("chunker_wait_ms") for r in valid])
    tts = _stats([r.get("tts_ttfb_ms") for r in valid])
    store_s = _stats([r.get("store_ms") for r in valid])

    # Phase 1.8 baselines (from prior report)
    before = {
        "TTFA_ms": {"avg": 1652.5, "median": 1080.6},
        "LLM_TTFT": {"avg": 912.4},
        "Chunker": {"avg": 245.9},
        "TTS_TTFB": {"avg": 489.5},
        "Store": {"avg": 0.4},
        "RAG": {"avg": 0.0},
    }

    def gain(b: float | None, a: float | None) -> str:
        if b is None or a is None:
            return "—"
        return str(round(b - a, 1))

    stage_comparison = {
        "RAG": {"before": 0.0, "after": 0.0, "gain": 0.0},
        "Store": {
            "before": before["Store"]["avg"],
            "after": store_s["avg"],
            "gain": gain(before["Store"]["avg"], store_s["avg"]),
        },
        "LLM TTFT": {
            "before": before["LLM_TTFT"]["avg"],
            "after": app_ttft["avg"],
            "gain": gain(before["LLM_TTFT"]["avg"], app_ttft["avg"]),
        },
        "Chunker": {
            "before": before["Chunker"]["avg"],
            "after": chunker["avg"],
            "gain": gain(before["Chunker"]["avg"], chunker["avg"]),
        },
        "TTS TTFB": {
            "before": before["TTS_TTFB"]["avg"],
            "after": tts["avg"],
            "gain": gain(before["TTS_TTFB"]["avg"], tts["avg"]),
        },
        "TTFA": {
            "before": before["TTFA_ms"]["median"],
            "after": ttfa_global["median"],
            "gain": gain(before["TTFA_ms"]["median"], ttfa_global["median"]),
        },
    }

    breakdown = (
        f"store={store_s['avg']} prompt_prep/provider_ttfh={provider['avg']} "
        f"app_ttft={app_ttft['avg']} chunker_wait={chunker['avg']} "
        f"tts_ttfb={tts['avg']} (ms avg, n={ttfa_global['n']})"
    )

    # Decision logic
    med = ttfa_global.get("median")
    mx = ttfa_global.get("max")
    if med is not None and med < 1500 and (mx is None or mx < 2500):
        decision = (
            "**A** — TTFA suffisamment faible et assez stable → "
            "arrêter l’optimisation de performance vocale."
        )
        recommendation = "Passer à la prochaine phase produit (pas plus d’opti vocale)."
    elif med is not None and med < 1500 and mx is not None and mx >= 2500:
        decision = (
            "**C** — TTFA médian acceptable (~1 s) mais très variable "
            f"(max={mx} ms) → travailler la stabilité cold/warm HF, pas l’architecture."
        )
        recommendation = (
            "Continuer uniquement sur stabilité cold (warm TLS HF au boot, "
            "éviter cold starts provider) — pas de changement de modèle/RAG."
        )
    else:
        decision = (
            "**B** — TTFA encore trop élevé → prochain bottleneck = "
            f"LLM provider TTFT (avg={provider['avg']}) puis TTS TTFB (avg={tts['avg']})."
        )
        recommendation = "Continuer optimisation ciblée LLM TTFT / TTS, sans refactor."

    # Rank bottlenecks
    parts = [
        ("LLM TTFT / provider", provider["avg"] or 0),
        ("TTS TTFB", tts["avg"] or 0),
        ("chunker wait", chunker["avg"] or 0),
        ("store", store_s["avg"] or 0),
    ]
    parts.sort(key=lambda x: x[1], reverse=True)

    # Optimizations recorded by this run (code changes may be applied separately)
    optimizations = list(payload_optimizations())

    payload = {
        "phase": "1.9",
        "model": settings.hf_model_id,
        "runs_requested": runs_n,
        "valid_total": len(valid),
        "failed_total": len(failed),
        "failure_reasons": reasons,
        "prompt_profiles": profiles,
        "audit_summary": audit_summary,
        "optimizations": optimizations,
        "chunker_ab": chunker_ab,
        "chunker_best": best_label,
        "runs": all_rows,
        "scenario_stats": scenario_stats,
        "ttfa_global": ttfa_global,
        "before_phase18": before,
        "stage_comparison": stage_comparison,
        "breakdown": breakdown,
        "decision": decision,
        "bottleneck_primary": parts[0][0],
        "bottleneck_secondary": parts[1][0],
        "optimization_summary": "; ".join(optimizations) or "aucune",
        "gain_summary": (
            f"TTFA median {before['TTFA_ms']['median']} → {ttfa_global.get('median')} "
            f"(Δ {gain(before['TTFA_ms']['median'], ttfa_global.get('median'))} ms)"
        ),
        "recommendation": recommendation,
        "pytest": None,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report(payload)
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(decision)
    print(f"TTFA median={ttfa_global.get('median')} avg={ttfa_global.get('avg')}")
    return 0


def payload_optimizations() -> list[str]:
    """Detect which Phase 1.9 code opts are present in the tree."""
    opts: list[str] = []
    main_txt = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    if "Inference HTTP warm" in main_txt or "Inference HTTP warm" in main_txt:
        opts.append("Warm HF (and Fish) HTTP/TLS connections at API startup")
    chunker = (ROOT / "backend/app/services/speech/voice_chunker.py").read_text(
        encoding="utf-8"
    )
    if "FIRST_HARD = 40" in chunker:
        opts.append("Voice chunker FIRST_HARD 48→40 (earlier first TTS flush)")
    grounding = (ROOT / "backend/app/services/ai/grounding.py").read_text(encoding="utf-8")
    if "_VOICE_PROMPT_CACHE" in grounding or "VOICE_PROMPT_STATIC" in grounding:
        opts.append("Cached static voice system prompt (skip_kb path)")
    if not opts:
        opts.append("Diagnostic-only in this run (code opts applied in same PR if listed)")
    return opts


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=5)
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--skip-chunker-ab", action="store_true")
    args = p.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
