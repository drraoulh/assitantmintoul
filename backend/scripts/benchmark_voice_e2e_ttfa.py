#!/usr/bin/env python3
"""Phase 1.8 — end-to-end voice TTFA benchmark (MEASUREMENT ONLY).

Does NOT modify production code (LLM, RAG, store, STT, TTS, frontend, WS).

Primary path: live WebSocket ``/api/voice/session`` (same as production).
``user_speech_end`` ≈ text submit (post-speech). With early-play (Phase 1.4),
``frontend_playback_start`` ≈ first ``audio_chunk`` receive (+0 ms).

  TTFA_ms = frontend_playback_start - user_speech_end

Usage:

  python backend/scripts/benchmark_voice_e2e_ttfa.py
  python backend/scripts/benchmark_voice_e2e_ttfa.py --runs 3 --base-url http://127.0.0.1:8000
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

OUT_JSON = ROOT / "docs" / "latency-phase18-e2e-voice.json"
OUT_MD = ROOT / "docs" / "latency-phase18-e2e-voice.md"

QUESTIONS = [
    ("food", "Quels plats camerounais dois-je goûter ?"),
    ("yaounde", "Que puis-je visiter à Yaoundé ?"),
    ("nature", "Propose-moi une activité nature au Cameroun."),
    ("trip3", "Je viens au Cameroun pendant trois jours, que peux-tu me proposer ?"),
    ("culture", "Parle-moi de la culture camerounaise."),
]

FOLLOWUPS = [
    "Et à Yaoundé ?",
    "Et pour une famille avec deux enfants ?",
]


def _stats(values: list[float | None]) -> dict[str, float | int | None]:
    clean = [float(v) for v in values if v is not None and v >= 0]
    if not clean:
        return {"avg": None, "median": None, "min": None, "max": None, "p95": None, "n": 0}
    clean_sorted = sorted(clean)
    p95 = None
    if len(clean_sorted) >= 5:
        idx = min(len(clean_sorted) - 1, int(round(0.95 * (len(clean_sorted) - 1))))
        p95 = round(clean_sorted[idx], 1)
    return {
        "avg": round(statistics.mean(clean), 1),
        "median": round(statistics.median(clean), 1),
        "min": round(min(clean), 1),
        "max": round(max(clean), 1),
        "p95": p95,
        "n": len(clean),
    }


def _chrono_elapsed(chrono: dict | None, name: str) -> float | None:
    if not chrono:
        return None
    for e in chrono.get("events") or []:
        if e.get("event") == name:
            return float(e["elapsed_ms"])
    return None


def _chrono_gap(chrono: dict | None, a: str, b: str) -> float | None:
    ea, eb = _chrono_elapsed(chrono, a), _chrono_elapsed(chrono, b)
    if ea is None or eb is None:
        return None
    return round(eb - ea, 1)


def _phase(metrics: dict | None, name: str) -> float | None:
    if not metrics:
        return None
    phases = metrics.get("phases") or metrics
    v = phases.get(name)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _classify_error(msg: str) -> str:
    low = msg.lower()
    if "402" in msg or "credit" in low or "depleted" in low:
        return "FAILED_HTTP_402"
    return msg[:160]


async def measure_stt_samples(n: int = 3) -> dict[str, Any]:
    """Isolated STT samples (not on WS text path)."""
    from app.api.deps import get_speech_service

    speech = get_speech_service()
    fixture = Path("/tmp/phase18_stt_fixture.mp3")
    if not fixture.exists() or fixture.stat().st_size < 1000:
        chunks: list[bytes] = []
        async for chunk in speech.synthesize_stream(
            "Propose-moi une activité nature au Cameroun."
        ):
            chunks.append(chunk)
        fixture.write_bytes(b"".join(chunks))
    audio = fixture.read_bytes()
    rows = []
    for i in range(n):
        t0 = time.perf_counter()
        text, lang = await speech.transcribe(
            audio, mime_type="audio/mpeg", filename="fixture.mp3"
        )
        ms = round((time.perf_counter() - t0) * 1000, 1)
        rows.append({"i": i, "stt_ms": ms, "text": (text or "")[:80], "lang": lang})
        print(f"  STT sample[{i}] {ms:.0f} ms → {(text or '')[:40]!r}")
    return {"rows": rows, "stats": _stats([r["stt_ms"] for r in rows])}


async def run_ws_turn(
    *,
    base_url: str,
    question: str,
    scenario: str,
    run_i: int,
    ws: Any | None = None,
    close_after: bool = True,
) -> tuple[dict[str, Any], Any]:
    """One production WS text turn. Returns (row, open_ws_or_None)."""
    try:
        import websockets
    except ImportError:
        return (
            {
                "scenario": scenario,
                "run_i": run_i,
                "valid": False,
                "error": "websockets_missing",
            },
            None,
        )

    ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = ws_url.rstrip("/") + "/api/voice/session"

    own_ws = ws is None
    marks: dict[str, float] = {}
    timeline: list[dict[str, Any]] = []
    wall0 = time.perf_counter()
    speech_end_at: float | None = None

    def mark(name: str, **extra: Any) -> float:
        now = time.perf_counter()
        if speech_end_at is None:
            elapsed = round((now - wall0) * 1000, 1)
        else:
            elapsed = round((now - speech_end_at) * 1000, 1)
        marks[name] = elapsed
        timeline.append({"event": name, "elapsed_ms": elapsed, **extra})
        return elapsed

    row: dict[str, Any] = {
        "scenario": scenario,
        "run_i": run_i,
        "question": question,
        "valid": False,
        "path": "websocket",
    }

    try:
        if own_ws:
            ws = await websockets.connect(ws_url, max_size=8 * 1024 * 1024)
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            if ready.get("type") != "ready":
                row["error"] = f"no_ready:{ready.get('type')}"
                await ws.close()
                return row, None

        # Anchor: end of user speech ≈ submit (text turn proxy).
        speech_end_at = time.perf_counter()
        mark("user_speech_end")
        await ws.send(
            json.dumps(
                {
                    "type": "text",
                    "text": question,
                    "locale": "fr",
                    "turn_id": f"p18-{scenario}-{run_i}",
                }
            )
        )
        mark("stt_start", note="text_turn_stt_skipped")
        mark("stt_end", note="text_turn_stt_ms=0")

        chronology = None
        metrics = None
        llm_trace = None
        conversation_id = None
        deadline = time.perf_counter() + 120
        while time.perf_counter() < deadline:
            raw = await asyncio.wait_for(ws.recv(), timeout=90)
            recv_wall = time.time()
            msg = json.loads(raw)
            mtype = msg.get("type")
            if mtype == "status":
                phase = msg.get("phase")
                if phase == "transcribing" and "stt_status" not in marks:
                    mark("stt_status")
                elif phase == "generating" and "llm_status" not in marks:
                    mark("llm_generating_status")
            elif mtype == "route" and "rag_start" not in marks:
                mark("rag_start", note="route_received")
            elif mtype == "token":
                if "llm_first_token" not in marks:
                    mark("llm_first_token", chars=len(str(msg.get("text") or "")))
                if "first_phrase_ready" not in marks and len(str(msg.get("text") or "")) > 0:
                    # Approximate; refined from llm_trace / chronology when available.
                    pass
            elif mtype == "audio_chunk":
                part = int(msg.get("part") or 0)
                if part == 0 and "tts_first_audio" not in marks:
                    backend_ts = msg.get("backend_send_timestamp")
                    transit = None
                    if isinstance(backend_ts, (int, float)):
                        transit = round((recv_wall - float(backend_ts)) * 1000, 1)
                    mark(
                        "tts_first_audio",
                        sequence_id=msg.get("sequence_id"),
                        backend_to_frontend_audio_ms=transit,
                    )
                    mark("websocket_audio_sent", note="aligned_to_chunk_receive")
                    mark("frontend_audio_received", backend_to_frontend_audio_ms=transit)
                    # Phase 1.4 early-play: play on first audio_chunk.
                    mark(
                        "frontend_playback_start",
                        frontend_receive_to_play_ms=0.0,
                        note="early_play",
                    )
            elif mtype == "audio_done":
                mark("audio_done")
            elif mtype == "turn_done":
                mark("turn_complete")
                metrics = msg.get("metrics") or {}
                chronology = metrics.get("ttfa_chronology")
                llm_trace = metrics.get("llm_trace") or msg.get("llm_trace")
                conversation_id = msg.get("conversation_id")
                break
            elif mtype == "error":
                row["error"] = _classify_error(
                    str(msg.get("message") or msg.get("code") or "error")
                )
                break

        if row.get("error"):
            if close_after and own_ws and ws is not None:
                await ws.close()
            return row, (None if close_after or own_ws else ws)

        if "frontend_playback_start" not in marks:
            row["error"] = "no_first_audio"
            if close_after and own_ws and ws is not None:
                await ws.close()
            return row, (None if close_after or own_ws else ws)

        # Refine from server chronology / llm_trace when present.
        store_ms = None
        rag_ms = _phase(metrics, "rag") or _phase(metrics, "grounding")
        llm_ttft = None
        first_phrase = None
        tts_ttfb = None
        if llm_trace:
            store_meta = (llm_trace.get("meta") or {}).get("store") or {}
            store_ms = store_meta.get("total_ms")
            llm_ttft = llm_trace.get("app_ttft_ms") or llm_trace.get("provider_ttfh_ms")
            first_phrase = llm_trace.get("first_phrase_ready_ms")
            if llm_trace.get("first_phrase_ready_ms") is not None:
                # Re-express relative to speech_end using client llm_first_token delta if needed.
                pass
        if chronology:
            if store_ms is None:
                # conversation_store marks live in llm_trace; chronology may have llm gaps.
                pass
            tts_ttfb = _chrono_gap(chronology, "tts_request_start", "tts_first_audio_byte")
            if tts_ttfb is None:
                tts_ttfb = _chrono_gap(chronology, "tts_start", "tts_first_audio_byte")
            phr = _chrono_elapsed(chronology, "chunker_first_flush") or _chrono_elapsed(
                chronology, "tts_first_fragment"
            )
            if phr is not None and "first_phrase_ready" not in marks:
                # Server chronology is from turn_start, not speech_end — keep client TTFA.
                first_phrase = first_phrase or phr

        ttfa = marks["frontend_playback_start"]
        row.update(
            {
                "valid": True,
                "conversation_id": conversation_id,
                "stt_ms": 0.0,  # text turn
                "conversation_store_ms": store_ms,
                "rag_ms": rag_ms,
                "llm_ttft_ms": llm_ttft or marks.get("llm_first_token"),
                "llm_total_ms": _phase(metrics, "llm"),
                "first_phrase_ms": first_phrase or marks.get("llm_first_token"),
                "tts_ttfb_ms": tts_ttfb,
                "tts_total_ms": _phase(metrics, "tts_first") or _phase(metrics, "tts"),
                "backend_to_frontend_audio_ms": next(
                    (
                        e.get("backend_to_frontend_audio_ms")
                        for e in timeline
                        if e["event"] == "frontend_audio_received"
                    ),
                    None,
                ),
                "frontend_receive_to_play_ms": 0.0,
                "TTFA_ms": ttfa,
                "total_turn_ms": marks.get("turn_complete"),
                "timeline": timeline,
                "server_chronology": chronology,
                "llm_trace": llm_trace,
                "metrics": metrics,
                "store_mode": (
                    ((llm_trace or {}).get("meta") or {}).get("store") or {}
                ).get("meta", {}).get("mode")
                if llm_trace
                else None,
            }
        )
        # Prefer store mode from nested meta
        if llm_trace:
            sm = ((llm_trace.get("meta") or {}).get("store") or {}).get("meta") or {}
            row["store_mode"] = sm.get("mode")

        if close_after:
            try:
                await ws.send(json.dumps({"type": "close"}))
            except Exception:
                pass
            if own_ws:
                await ws.close()
            return row, None
        return row, ws
    except Exception as exc:  # noqa: BLE001
        row["error"] = _classify_error(str(exc))
        if own_ws and ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        return row, None


async def run_cold_inprocess(
    *,
    question: str,
    run_i: int,
    conversation_id: str,
) -> dict[str, Any]:
    """Existing conversation, cache miss (cold) — in-process mirror of voice path."""
    from app.api.deps import get_ai_service, get_speech_service
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.conversation import get_conversation_store
    from app.services.conversation.postgres import SqlConversationStore
    from app.services.metrics.latency import PhaseTimer
    from app.services.metrics.llm_stream_trace import LlmStreamTrace
    from app.services.metrics.ttfa_trace import TurnChronology
    from app.services.speech.voice_chunker import (
        append_token,
        flush_remainder,
        split_ready_phrases,
    )

    ai = get_ai_service()
    speech = get_speech_service()
    store = get_conversation_store()
    if isinstance(store, SqlConversationStore):
        store._cache_invalidate(conversation_id)

    if not isinstance(ai, HuggingFaceAIService):
        return {
            "scenario": "existing_cold",
            "run_i": run_i,
            "valid": False,
            "error": "not_hf",
        }

    turn_id = f"p18-cold-{run_i}"
    timer = PhaseTimer("p18_cold")
    timer.turn_id = turn_id
    chrono = TurnChronology(turn_id=turn_id)
    llm_trace = LlmStreamTrace(turn_id=turn_id, model=getattr(ai, "_model", ""))

    speech_end = time.perf_counter()
    chrono.wall0 = speech_end
    llm_trace.wall0 = speech_end
    chrono.mark("user_speech_end")
    chrono.mark("stt_start", note="text_turn")
    chrono.mark("stt_end", note="stt_ms=0")

    buf = ""
    first_flush = True
    first_token = False
    first_frag: str | None = None
    put_at: float | None = None
    reply = ""
    error = None

    async for event in ai.stream_response(
        question,
        conversation_id,
        brief=True,
        locale="fr",
        timer=timer,
        turn_id=turn_id,
        llm_trace=llm_trace,
    ):
        etype = event.get("type")
        if etype == "token":
            piece = str(event.get("text") or "")
            if not first_token:
                chrono.mark("llm_first_token", chars=len(piece))
                first_token = True
            reply += piece
            buf = append_token(buf, piece)
            ready, buf = split_ready_phrases(buf, first_chunk=first_flush)
            if ready and first_frag is None:
                first_frag = ready[0]
                put_at = time.perf_counter()
                chrono.mark("first_phrase_ready", chars=len(first_frag))
                chrono.mark("tts_queue_put", sequence_id=0)
                first_flush = False
        elif etype == "done":
            chrono.mark("llm_end")
            reply = str(event.get("text") or reply)
            if first_frag is None:
                for part in flush_remainder(buf):
                    first_frag = part
                    put_at = time.perf_counter()
                    chrono.mark("first_phrase_ready", chars=len(part))
                    break
            break
        elif etype == "error":
            error = _classify_error(str(event.get("message") or ""))
            break

    if error:
        return {
            "scenario": "existing_cold",
            "run_i": run_i,
            "valid": False,
            "error": error,
            "timeline": chrono.as_dict().get("events"),
        }

    frag = (first_frag or reply[:80] or "").strip()
    if not frag:
        return {
            "scenario": "existing_cold",
            "run_i": run_i,
            "valid": False,
            "error": "empty_fragment",
        }

    chrono.mark("tts_start", sequence_id=0)
    fish: dict = {}
    first_byte = False
    async for chunk in speech.synthesize_stream(frag, trace=fish):
        if not chunk:
            continue
        if not first_byte:
            if fish.get("tts_first_byte") is not None:
                chrono.mark(
                    "tts_first_audio",
                    sequence_id=0,
                    at=float(fish["tts_first_byte"]),
                    ttfb_ms=fish.get("ttfb_ms"),
                )
            chrono.mark("websocket_audio_sent", sequence_id=0, bytes=len(chunk))
            chrono.mark("frontend_audio_received", sequence_id=0)
            chrono.mark(
                "frontend_playback_start",
                frontend_receive_to_play_ms=0.0,
                note="early_play",
            )
            first_byte = True
    chrono.mark("audio_done")
    chrono.mark("turn_complete")

    store_meta = (llm_trace.as_dict().get("meta") or {}).get("store") or {}
    ttfa = _chrono_elapsed(chrono.as_dict(), "frontend_playback_start")
    return {
        "scenario": "existing_cold",
        "run_i": run_i,
        "question": question,
        "valid": True,
        "path": "inprocess_cold",
        "conversation_id": conversation_id,
        "stt_ms": 0.0,
        "conversation_store_ms": store_meta.get("total_ms"),
        "rag_ms": _phase(timer.as_dict(), "rag") or _phase(timer.as_dict(), "grounding"),
        "llm_ttft_ms": llm_trace.app_ttft_ms,
        "llm_total_ms": _phase(timer.as_dict(), "llm"),
        "first_phrase_ms": llm_trace.first_phrase_ready_ms
        or _chrono_elapsed(chrono.as_dict(), "first_phrase_ready"),
        "tts_ttfb_ms": fish.get("ttfb_ms"),
        "tts_total_ms": fish.get("total_tts_ms"),
        "backend_to_frontend_audio_ms": 0.0,
        "frontend_receive_to_play_ms": 0.0,
        "TTFA_ms": ttfa,
        "total_turn_ms": _chrono_elapsed(chrono.as_dict(), "turn_complete"),
        "timeline": chrono.as_dict().get("events"),
        "store_mode": (store_meta.get("meta") or {}).get("mode"),
        "llm_trace": llm_trace.as_dict(),
        "queue_put_lag_ms": round((time.perf_counter() - (put_at or time.perf_counter())) * 1000, 1),
    }


def _scenario_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in rows if r.get("valid")]
    keys = [
        "stt_ms",
        "conversation_store_ms",
        "rag_ms",
        "llm_ttft_ms",
        "first_phrase_ms",
        "tts_ttfb_ms",
        "backend_to_frontend_audio_ms",
        "frontend_receive_to_play_ms",
        "TTFA_ms",
        "total_turn_ms",
    ]
    out = {"valid_n": len(valid), "failed_n": len(rows) - len(valid)}
    for k in keys:
        out[k] = _stats([r.get(k) for r in valid])
    return out


def _fmt(stats: dict | None, key: str = "avg") -> str:
    if not stats:
        return "—"
    v = stats.get(key)
    return "—" if v is None else str(v)


def write_md(payload: dict[str, Any]) -> None:
    scenarios = payload.get("scenario_stats") or {}
    stt = payload.get("stt_isolated") or {}

    def row(name: str, key: str) -> str:
        s = scenarios.get(key) or {}
        return (
            f"| {name} | {_fmt(s.get('stt_ms'))} | {_fmt(s.get('conversation_store_ms'))} | "
            f"{_fmt(s.get('rag_ms'))} | {_fmt(s.get('llm_ttft_ms'))} | "
            f"{_fmt(s.get('first_phrase_ms'))} | {_fmt(s.get('tts_ttfb_ms'))} | "
            f"{_fmt(s.get('backend_to_frontend_audio_ms'))} | "
            f"{_fmt(s.get('frontend_receive_to_play_ms'))} | "
            f"**{_fmt(s.get('TTFA_ms'))}** |"
        )

    lines = [
        "# Phase 1.8 — End-to-end voice latency (TTFA)",
        "",
        "Mesure uniquement — **aucun changement** LLM / RAG / store / STT / TTS / frontend / WS.",
        "",
        "KPI principal :",
        "",
        "```",
        "TTFA = frontend_playback_start − user_speech_end",
        "```",
        "",
        "Avec early-play (Phase 1.4) : `frontend_playback_start ≈ first audio_chunk receive` (+0 ms).",
        "Tours WS en `type=text` → STT = 0 ms sur le chemin critique "
        f"(STT isolé mesuré à part : avg={((stt.get('stats') or {}).get('avg'))} ms).",
        "",
        f"- Runs demandés / scénario : {payload.get('runs_requested')}",
        f"- Runs valides totaux : {payload.get('valid_total')} / failed : {payload.get('failed_total')}",
        f"- Base URL : `{payload.get('base_url')}`",
        "",
        "## Tableau final (moyennes, ms)",
        "",
        "| Scenario | STT | Store | RAG | LLM TTFT | First phrase | TTS TTFB | Audio network | Playback | TTFA |",
        "|----------|----:|------:|----:|---------:|-------------:|---------:|--------------:|---------:|-----:|",
        row("New thread", "new_thread"),
        row("Multi-turn", "multi_turn"),
        row("Existing cold", "existing_cold"),
        row("Warm", "warm"),
        "",
        "## TTFA global (tous scénarios valides)",
        "",
    ]
    g = payload.get("ttfa_global") or {}
    lines += [
        f"- n = {g.get('n')}",
        f"- avg = **{g.get('avg')} ms**",
        f"- median = **{g.get('median')} ms**",
        f"- min = {g.get('min')} ms",
        f"- max = {g.get('max')} ms",
        f"- p95 = {g.get('p95')} ms",
        "",
        "## Timelines exemples",
        "",
    ]

    for key, title in [
        ("new_thread", "Scenario A — nouveau thread"),
        ("multi_turn", "Scenario B — multi-turn"),
        ("existing_cold", "Scenario C — existing cold"),
        ("warm", "Scenario D — warm"),
    ]:
        sample = next(
            (
                r
                for r in payload.get("runs") or []
                if r.get("scenario") == key and r.get("valid") and r.get("timeline")
            ),
            None,
        )
        lines.append(f"### {title}")
        if not sample:
            failed = [
                r
                for r in payload.get("runs") or []
                if r.get("scenario") == key and not r.get("valid")
            ]
            if failed:
                lines.append(f"Aucun run valide ({failed[0].get('error')}).")
            else:
                lines.append("Aucun run.")
            lines.append("")
            continue
        lines.append(f"Turn `{sample.get('question', '')[:60]}` — TTFA={sample.get('TTFA_ms')} ms")
        lines.append("```")
        for e in sample.get("timeline") or []:
            lines.append(f"{e['event']:28} +{e['elapsed_ms']:8.1f} ms")
        lines.append("```")
        lines.append(
            f"store={sample.get('conversation_store_ms')} mode={sample.get('store_mode')} "
            f"llm_ttft={sample.get('llm_ttft_ms')} tts_ttfb={sample.get('tts_ttfb_ms')} "
            f"network={sample.get('backend_to_frontend_audio_ms')}"
        )
        lines.append("")

    lines += [
        "## Breakdown — contribution au TTFA",
        "",
        payload.get("bottleneck_analysis") or "",
        "",
        "## Comparaison historique",
        "",
        "| Phase | First audio / TTFA | Total turn | Note |",
        "|-------|-------------------:|-----------:|------|",
        "| Initial | ~15–17 s (séquentiel) | ~15–17 s | avant optimisations |",
        "| Phase 1 | grounding ↓ ; TTS encore séquentiel | ~15–17 s | RAG/web |",
        "| Phase 1.2 | TTFA rapporté ~6.5 s (artéfact) | ~8.3 s | overlap LLM→TTS |",
        "| Phase 1.3 | backend first audio ~3552 ms ; play gate ~4625 | — | diagnostic |",
        "| Phase 1.4 early-play | receive→play **808 → 0** ms | TTFA −~0.8 s | play on audio_chunk |",
        "| Phase 1.6 | app_ttft ~2827 (store ~2370) | — | store bottleneck |",
        "| Phase 1.7 | store ~0.1 (new/cached) ; app_ttft ~338 | — | store fix |",
        f"| **Phase 1.8** | **TTFA avg {g.get('avg')} ms** | see runs | E2E mesuré |",
        "",
        "## Nouveau bottleneck",
        "",
        payload.get("new_bottleneck") or "",
        "",
        "## STT isolé (référence)",
        "",
        f"```json\n{json.dumps(stt.get('stats') or {}, indent=2)}\n```",
        "",
        "## Tests",
        "",
        f"`pytest -q` : {payload.get('pytest') or 'à renseigner'}",
        "",
        "## Méthode",
        "",
        "- Pas de modification production.",
        "- Scénarios A/B/D : WebSocket live `/api/voice/session`.",
        "- Scénario C : in-process avec `_cache_invalidate` (cold miss SqlConversationStore).",
        "- `FAILED_HTTP_402` reporté tel quel, jamais inventé.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def analyze_bottleneck(valid: list[dict[str, Any]]) -> tuple[str, str]:
    if not valid:
        return (
            "Pas assez de runs valides pour identifier un bottleneck.",
            "Indéterminé (données insuffisantes / HF 402).",
        )

    # Approximate contribution shares toward TTFA using available segment means.
    segs = {
        "STT": _stats([r.get("stt_ms") for r in valid])["avg"] or 0,
        "conversation_store": _stats([r.get("conversation_store_ms") for r in valid])["avg"] or 0,
        "RAG": _stats([r.get("rag_ms") for r in valid])["avg"] or 0,
        "LLM_TTFT": _stats([r.get("llm_ttft_ms") for r in valid])["avg"] or 0,
        "TTS_TTFB": _stats([r.get("tts_ttfb_ms") for r in valid])["avg"] or 0,
        "network": _stats([r.get("backend_to_frontend_audio_ms") for r in valid])["avg"] or 0,
        "frontend_playback": _stats([r.get("frontend_receive_to_play_ms") for r in valid])["avg"]
        or 0,
    }
    # Chunking ≈ first_phrase - llm_ttft (when both present)
    chunk_vals = []
    for r in valid:
        a, b = r.get("first_phrase_ms"), r.get("llm_ttft_ms")
        if a is not None and b is not None and a >= b:
            chunk_vals.append(a - b)
    segs["chunking"] = (_stats(chunk_vals)["avg"] or 0) if chunk_vals else 0

    ranked = sorted(segs.items(), key=lambda x: x[1], reverse=True)
    lines = ["Contributions moyennes estimées (ms, segments non strictement additifs) :"]
    for name, val in ranked:
        lines.append(f"- {name}: {val:.1f} ms")
    top = ranked[0][0]
    analysis = "\n".join(lines)
    bottleneck = (
        f"**{top}** est le plus grand contributeur mesuré au TTFA "
        f"(~{ranked[0][1]:.0f} ms avg sur n={len(valid)}). "
        "Ne pas optimiser autre chose avant confirmation sur plus de runs."
    )
    return analysis, bottleneck


async def main_async(args: argparse.Namespace) -> int:
    from app.core.config import get_settings
    from app.core.http import close_shared_clients
    from app.services.conversation import get_conversation_store
    from app.services.rag.factory import get_rag_service

    get_settings.cache_clear()
    get_conversation_store.cache_clear()
    settings = get_settings()
    await close_shared_clients()

    base = args.base_url.rstrip("/")
    runs_n = max(1, int(args.runs))
    print("=== Phase 1.8 E2E voice TTFA ===")
    print(f"base={base} runs/scenario={runs_n} model={settings.hf_model_id}")

    # Health
    try:
        import httpx

        r = httpx.get(f"{base}/api/health", timeout=5.0)
        print(f"health={r.status_code}")
        if r.status_code >= 400:
            print("API unhealthy — abort")
            return 2
    except Exception as exc:  # noqa: BLE001
        print(f"API unreachable: {exc}")
        return 2

    rag = get_rag_service()
    if callable(getattr(rag, "warm", None)):
        await rag.warm()
        print("RAG warmed")

    print("\n--- STT isolated samples ---")
    stt_isolated = await measure_stt_samples(n=min(3, runs_n))

    all_rows: list[dict[str, Any]] = []
    consecutive_402 = 0

    def note_row(row: dict[str, Any]) -> bool:
        nonlocal consecutive_402
        all_rows.append(row)
        if row.get("valid"):
            consecutive_402 = 0
            print(
                f"  OK TTFA={row.get('TTFA_ms')} store={row.get('conversation_store_ms')} "
                f"llm_ttft={row.get('llm_ttft_ms')} tts={row.get('tts_ttfb_ms')} "
                f"mode={row.get('store_mode')}"
            )
            return True
        print(f"  FAIL {row.get('error')}")
        if row.get("error") == "FAILED_HTTP_402":
            consecutive_402 += 1
            if consecutive_402 >= 3:
                print("Stopping: HF_402 streak")
                return False
        return True

    # --- A: new thread ---
    print("\n=== Scenario A: new_thread ===")
    for i in range(runs_n):
        qid, q = QUESTIONS[i % len(QUESTIONS)]
        print(f"--- A[{i}] {qid} ---")
        row, _ = await run_ws_turn(
            base_url=base, question=q, scenario="new_thread", run_i=i, close_after=True
        )
        if not note_row(row):
            break

    # --- B: multi-turn on one WS ---
    print("\n=== Scenario B: multi_turn ===")
    if consecutive_402 < 3:
        import websockets

        ws_url = base.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = ws_url.rstrip("/") + "/api/voice/session"
        try:
            ws = await websockets.connect(ws_url, max_size=8 * 1024 * 1024)
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            if ready.get("type") != "ready":
                print("multi_turn: no ready")
                ws = None
            else:
                # First turn establishes conversation
                row, ws = await run_ws_turn(
                    base_url=base,
                    question=QUESTIONS[0][1],
                    scenario="multi_turn",
                    run_i=0,
                    ws=ws,
                    close_after=False,
                )
                row["multi_turn_index"] = 0
                if not note_row(row):
                    ws = None
                # Follow-ups
                for i, fq in enumerate(FOLLOWUPS, start=1):
                    if ws is None or consecutive_402 >= 3:
                        break
                    if i >= runs_n:
                        break
                    print(f"--- B[{i}] followup ---")
                    row, ws = await run_ws_turn(
                        base_url=base,
                        question=fq,
                        scenario="multi_turn",
                        run_i=i,
                        ws=ws,
                        close_after=False,
                    )
                    row["multi_turn_index"] = i
                    if not note_row(row):
                        break
                if ws is not None:
                    try:
                        await ws.send(json.dumps({"type": "close"}))
                        await ws.close()
                    except Exception:
                        pass
        except Exception as exc:  # noqa: BLE001
            print(f"multi_turn ws error: {exc}")

    # --- D: warm (reuse sequential new connections after A/B heated process) ---
    print("\n=== Scenario D: warm ===")
    for i in range(runs_n):
        if consecutive_402 >= 3:
            break
        qid, q = QUESTIONS[(i + 2) % len(QUESTIONS)]
        print(f"--- D[{i}] {qid} ---")
        row, _ = await run_ws_turn(
            base_url=base, question=q, scenario="warm", run_i=i, close_after=True
        )
        if not note_row(row):
            break

    # --- C: existing cold (in-process) ---
    print("\n=== Scenario C: existing_cold ===")
    store = get_conversation_store()
    seed_id, _ = await store.prepare_for_generation(None, limit=3)
    await store.add_messages(
        seed_id,
        [
            ("user", "Que puis-je visiter à Yaoundé ?"),
            ("assistant", "Le Musée national et le monument de la Réunification."),
        ],
    )
    print(f"seeded cold thread {seed_id}")
    for i in range(runs_n):
        if consecutive_402 >= 3:
            break
        qid, q = QUESTIONS[(i + 1) % len(QUESTIONS)]
        print(f"--- C[{i}] {qid} ---")
        row = await run_cold_inprocess(question=q, run_i=i, conversation_id=seed_id)
        if not note_row(row):
            break

    # Aggregate
    by_scenario: dict[str, list[dict]] = {
        "new_thread": [],
        "multi_turn": [],
        "existing_cold": [],
        "warm": [],
    }
    for r in all_rows:
        by_scenario.setdefault(r.get("scenario") or "other", []).append(r)

    scenario_stats = {k: _scenario_stats(v) for k, v in by_scenario.items()}
    valid_all = [r for r in all_rows if r.get("valid")]
    failed_all = [r for r in all_rows if not r.get("valid")]
    ttfa_global = _stats([r.get("TTFA_ms") for r in valid_all])
    analysis, bottleneck = analyze_bottleneck(valid_all)

    payload = {
        "phase": "1.8",
        "model": settings.hf_model_id,
        "base_url": base,
        "runs_requested": runs_n,
        "valid_total": len(valid_all),
        "failed_total": len(failed_all),
        "stt_isolated": stt_isolated,
        "runs": all_rows,
        "scenario_stats": scenario_stats,
        "ttfa_global": ttfa_global,
        "bottleneck_analysis": analysis,
        "new_bottleneck": bottleneck,
        "pytest": None,
        "notes": [
            "Text WS turns: STT=0 on critical path; see stt_isolated for mic-path estimate.",
            "TTFA uses early-play: playback_start = first audio_chunk receive.",
            "Existing cold uses in-process cache invalidate (API WS cannot inject conversation_id).",
        ],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_md(payload)
    print(f"\nWrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print(
        f"VALID={len(valid_all)} TTFA avg={ttfa_global.get('avg')} "
        f"median={ttfa_global.get('median')} "
        f"min={ttfa_global.get('min')} max={ttfa_global.get('max')}"
    )
    print(bottleneck)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 1.8 E2E voice TTFA benchmark")
    parser.add_argument("--runs", type=int, default=3, help="Runs per scenario (default 3)")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="API base URL with /api/voice/session",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
