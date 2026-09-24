"""Phase 1.3 — TTFA chronology diagnostic (instrumentation only, no architecture changes).

Backend-only path:
  LLM first token → chunker flush → TTS queue → Fish first audio byte

WS path (no browser player):
  backend audio_chunk send → client receive → audio_done (= current play gate)

Usage (repo root, secrets in backend/.env):

  python backend/scripts/diagnose_ttfa_phase13.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

QUESTIONS = [
    ("food", "Quels plats camerounais dois-je goûter ?"),
    ("nature", "Propose-moi une activité nature au Cameroun."),
    ("yaounde", "Que puis-je visiter à Yaoundé ?"),
]

# Prefer ≥5 valid turns per question when HF credits allow.
N_PER_QUESTION = 5
OUT = ROOT / "docs" / "latency-ttfa-phase13.json"


def _stats(values: list[float | None]) -> dict:
    clean = [float(v) for v in values if v is not None and v >= 0]
    if not clean:
        return {"avg": None, "min": None, "max": None, "n": 0}
    return {
        "avg": round(statistics.mean(clean), 1),
        "min": round(min(clean), 1),
        "max": round(max(clean), 1),
        "n": len(clean),
    }


def _elapsed(chrono, name: str) -> float | None:
    for e in chrono.events:
        if e["event"] == name:
            return float(e["elapsed_ms"])
    return None


def _gap(chrono, a: str, b: str) -> float | None:
    ea, eb = _elapsed(chrono, a), _elapsed(chrono, b)
    if ea is None or eb is None:
        return None
    return round(eb - ea, 1)


async def run_backend_only(ai, speech, label: str, text: str, run_i: int) -> dict:
    """Mirror production: overlapped LLM stream + queue + first Fish audio byte."""
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.metrics.latency import PhaseTimer
    from app.services.metrics.ttfa_trace import TurnChronology
    from app.services.speech.voice_chunker import (
        append_token,
        flush_remainder,
        split_ready_phrases,
    )

    if not isinstance(ai, HuggingFaceAIService):
        return {"label": label, "run": run_i, "invalid": True, "reason": "non_hf"}

    turn_id = f"p13-{label}-{run_i}"
    timer = PhaseTimer(f"p13:{label}:{run_i}")
    timer.turn_id = turn_id
    chrono = TurnChronology(turn_id=turn_id)

    chrono.mark("turn_start")
    chrono.mark("llm_start")

    buf = ""
    first_flush = True
    first_token = False
    first_text = False
    first_frag: str | None = None
    put_at: float | None = None
    reply = ""
    invalid = False
    reason = ""

    async for event in ai.stream_response(text, brief=True, locale="fr", timer=timer):
        etype = event.get("type")
        if etype == "token":
            piece = str(event.get("text") or "")
            if not first_token:
                chrono.mark("llm_first_token", chars=len(piece))
                first_token = True
            reply += piece
            buf = append_token(buf, piece)
            if not first_text and buf.strip():
                chrono.mark("chunker_first_text", chars=len(buf))
                first_text = True
            ready, buf = split_ready_phrases(buf, first_chunk=first_flush)
            if ready and first_frag is None:
                first_frag = ready[0]
                put_at = time.perf_counter()
                chrono.mark("chunker_first_flush", chars=len(first_frag), sequence_id=0)
                chrono.mark("tts_queue_put", chars=len(first_frag), sequence_id=0)
                first_flush = False
                # Do NOT break — keep streaming so we don't cancel HF mid-turn,
                # but we only TTS the first fragment for this probe.
        elif etype == "done":
            chrono.mark("llm_end")
            reply = str(event.get("text") or reply)
            if first_frag is None:
                for part in flush_remainder(buf):
                    first_frag = part
                    put_at = time.perf_counter()
                    chrono.mark("chunker_first_flush", chars=len(part), sequence_id=0)
                    chrono.mark("tts_queue_put", chars=len(part), sequence_id=0)
                    break
            break
        elif etype == "error":
            invalid = True
            reason = str(event.get("message") or "")
            low = reason.lower()
            if "402" in reason or "credit" in low or "depleted" in low:
                reason = "HF_402"
            break

    if invalid:
        return {
            "label": label,
            "run": run_i,
            "invalid": True,
            "reason": reason,
            "chronology": chrono.as_dict(),
            "metrics": timer.as_dict(),
        }

    frag = (first_frag or reply[:80] or "").strip()
    if not frag:
        return {
            "label": label,
            "run": run_i,
            "invalid": True,
            "reason": "empty_fragment",
            "chronology": chrono.as_dict(),
        }

    got_at = time.perf_counter()
    queue_wait_ms = round((got_at - (put_at or got_at)) * 1000, 1)
    chrono.mark(
        "tts_worker_start",
        sequence_id=0,
        queue_wait_ms=queue_wait_ms,
        tts_worker_wait_ms=queue_wait_ms,
    )

    fish: dict = {}
    first_byte = False
    total_bytes = 0
    async for chunk in speech.synthesize_stream(frag, trace=fish):
        if not chunk:
            continue
        total_bytes += len(chunk)
        if not first_byte:
            if fish.get("tts_request_start") is not None:
                chrono.mark(
                    "tts_request_start",
                    sequence_id=0,
                    at=float(fish["tts_request_start"]),
                )
            if fish.get("tts_connection_established") is not None:
                chrono.mark(
                    "tts_connection_established",
                    sequence_id=0,
                    at=float(fish["tts_connection_established"]),
                    connection_latency_ms=fish.get("connection_latency_ms"),
                )
            if fish.get("tts_first_byte") is not None:
                chrono.mark(
                    "tts_ttfb",
                    sequence_id=0,
                    at=float(fish["tts_first_byte"]),
                    ttfb_ms=fish.get("ttfb_ms"),
                )
                chrono.mark(
                    "tts_first_audio_byte",
                    sequence_id=0,
                    at=float(fish["tts_first_byte"]),
                    ttfb_ms=fish.get("ttfb_ms"),
                    bytes=len(chunk),
                )
            chrono.mark("audio_chunk_created", sequence_id=0, bytes=len(chunk))
            chrono.mark("audio_chunk_sent_ws", sequence_id=0, bytes=len(chunk))
            first_byte = True
            # Drain remaining bytes of this first request without a second Fish call.
            continue
    if fish.get("tts_complete") is not None:
        chrono.mark(
            "tts_response_complete",
            sequence_id=0,
            at=float(fish["tts_complete"]),
            total_tts_ms=fish.get("total_tts_ms"),
        )
    chrono.mark("audio_done_sent", sequence_id=0)
    chrono.mark("turn_end")

    kpis = {
        "A_time_to_first_text_ms": _gap(chrono, "llm_start", "llm_first_token"),
        "B_time_to_first_tts_request_ms": _gap(
            chrono, "llm_first_token", "tts_request_start"
        ),
        "C_tts_first_audio_ms": fish.get("ttfb_ms"),
        "D_backend_audio_delivery_ms": None,  # filled by WS probe
        "E_frontend_playback_ms": None,  # filled by WS probe estimate
        "F_ttfa_from_llm_start_ms": _elapsed(chrono, "tts_first_audio_byte"),
        "llm_first_token_to_first_audio_ms": _gap(
            chrono, "llm_first_token", "tts_first_audio_byte"
        ),
        "chunker_wait_ms": _gap(chrono, "llm_first_token", "chunker_first_flush"),
        "queue_wait_ms": queue_wait_ms,
        "connection_latency_ms": fish.get("connection_latency_ms"),
        "tts_ttfb_ms": fish.get("ttfb_ms"),
        "total_tts_first_request_ms": fish.get("total_tts_ms"),
        "first_frag_chars": len(frag),
        "first_audio_bytes": total_bytes,
    }

    return {
        "label": label,
        "run": run_i,
        "invalid": False,
        "question": text,
        "first_frag": frag,
        "reply_preview": reply[:160],
        "kpis": kpis,
        "chronology": chrono.as_dict(),
        "fish_trace": {
            k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in fish.items()
            if not isinstance(v, float) or k.endswith("_ms")
        },
        "metrics": timer.as_dict(),
        "biggest_gap": (chrono.biggest_gaps(1) or [None])[0],
    }


async def run_ws_probe(label: str, text: str, run_i: int, base_http: str) -> dict:
    """WebSocket client: measure backend send → frontend receive → audio_done gate."""
    try:
        import websockets
    except ImportError:
        return {
            "label": label,
            "run": run_i,
            "invalid": True,
            "reason": "websockets_missing",
        }

    ws_url = base_http.replace("https://", "wss://").replace("http://", "ws://")
    if not ws_url.endswith("/"):
        ws_url = ws_url.rstrip("/")
    ws_url = f"{ws_url}/api/voice/session"

    marks: dict[str, float] = {}
    wall0 = time.perf_counter()
    events: list[dict] = []
    chronology = None
    invalid = False
    reason = ""

    def mark(name: str, **extra):
        elapsed = round((time.perf_counter() - wall0) * 1000, 1)
        marks[name] = elapsed
        row = {"event": name, "elapsed_ms": elapsed, **extra}
        events.append(row)
        return elapsed

    try:
        async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            if ready.get("type") != "ready":
                return {
                    "label": label,
                    "run": run_i,
                    "invalid": True,
                    "reason": f"no_ready:{ready.get('type')}",
                }
            mark("ws_ready")
            await ws.send(
                json.dumps(
                    {
                        "type": "text",
                        "text": text,
                        "locale": "fr",
                        "turn_id": f"ws-{label}-{run_i}",
                    }
                )
            )
            mark("text_sent")
            deadline = time.perf_counter() + 90
            while time.perf_counter() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=60)
                recv_at = time.time()
                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "token" and "first_token" not in marks:
                    mark("frontend_first_token")
                elif mtype == "audio_chunk":
                    part = msg.get("part") or 0
                    if part == 0 and "ws_audio_received" not in marks:
                        backend_ts = msg.get("backend_send_timestamp")
                        transit = None
                        if isinstance(backend_ts, (int, float)):
                            transit = round((recv_at - float(backend_ts)) * 1000, 1)
                        mark(
                            "ws_audio_received",
                            backend_to_frontend_ms=transit,
                            backend_send_elapsed_ms=msg.get("backend_send_elapsed_ms"),
                            sequence_id=msg.get("sequence_id"),
                        )
                elif mtype == "audio_done" and "audio_done_received" not in marks:
                    # Current frontend starts player only after audio_done.
                    mark(
                        "audio_done_received",
                        note="current_frontend_play_gate",
                    )
                    mark("first_audio_play_command_estimate")
                elif mtype == "turn_done":
                    mark("turn_done")
                    chronology = (msg.get("metrics") or {}).get("ttfa_chronology")
                    break
                elif mtype == "error":
                    invalid = True
                    reason = str(msg.get("message") or msg.get("code") or "error")
                    low = reason.lower()
                    if "402" in reason or "credit" in low:
                        reason = "HF_402"
                    break
            await ws.send(json.dumps({"type": "close"}))
    except Exception as exc:  # noqa: BLE001
        return {
            "label": label,
            "run": run_i,
            "invalid": True,
            "reason": f"ws_error:{exc}",
        }

    if invalid:
        return {
            "label": label,
            "run": run_i,
            "invalid": True,
            "reason": reason,
            "client_marks_ms": marks,
        }

    kpis = {
        "D_backend_audio_delivery_ms": next(
            (
                e.get("backend_to_frontend_ms")
                for e in events
                if e["event"] == "ws_audio_received"
            ),
            None,
        ),
        "E_frontend_playback_gate_ms": (
            marks["audio_done_received"] - marks["ws_audio_received"]
            if "audio_done_received" in marks and "ws_audio_received" in marks
            else None
        ),
        "ws_ttfa_first_chunk_ms": marks.get("ws_audio_received"),
        "ws_play_gate_ms": marks.get("audio_done_received"),
    }
    return {
        "label": label,
        "run": run_i,
        "invalid": False,
        "question": text,
        "client_marks_ms": marks,
        "client_events": events,
        "server_chronology": chronology,
        "kpis": kpis,
        "note": (
            "Frontend currently buffers until audio_done before playBase64Mp3; "
            "E approximates wait first_chunk→play_command (not browser decode)."
        ),
    }


async def main() -> None:
    from app.api.deps import get_ai_service, get_speech_service
    from app.core.config import get_settings
    from app.services.rag.factory import get_rag_service

    get_settings.cache_clear()
    settings = get_settings()
    speech = get_speech_service()
    ai = get_ai_service()
    rag = get_rag_service()
    if callable(getattr(rag, "warm", None)):
        await rag.warm()

    print("=== Phase 1.3 TTFA diagnose (NO greeting cache) ===")
    backend_rows: list[dict] = []
    ws_rows: list[dict] = []
    hf402_streak = 0

    for label, question in QUESTIONS:
        for i in range(N_PER_QUESTION):
            print(f"\n--- backend {label}[{i}] {question!r} ---")
            row = await run_backend_only(ai, speech, label, question, i)
            backend_rows.append(row)
            if row.get("invalid"):
                print(f"INVALID: {row.get('reason')}")
                if row.get("reason") == "HF_402":
                    hf402_streak += 1
                    if hf402_streak >= 3:
                        print("Stopping early: HF_402 streak")
                        break
                continue
            hf402_streak = 0
            k = row["kpis"]
            gap = row.get("biggest_gap") or {}
            print(
                f"frag={row['first_frag']!r} chars={k['first_frag_chars']}\n"
                f"  TTFT→chunk={k['chunker_wait_ms']}ms "
                f"TTFT→TTS_req={k['B_time_to_first_tts_request_ms']}ms "
                f"queue={k['queue_wait_ms']}ms "
                f"conn={k['connection_latency_ms']}ms "
                f"TTFB={k['tts_ttfb_ms']}ms "
                f"TTFA(llm_start→audio)={k['F_ttfa_from_llm_start_ms']}ms "
                f"TTFT→audio={k['llm_first_token_to_first_audio_ms']}ms"
            )
            if gap:
                print(f"  BIGGEST: {gap.get('from')} → {gap.get('to')} = {gap.get('delta_ms')} ms")
            for line in [
                f"{e['event']:28} +{e['elapsed_ms']/1000:7.3f}s  (Δ {e['delta_ms']:.0f}ms)"
                for e in row["chronology"]["events"]
            ]:
                print(f"  {line}")
        else:
            continue
        break

    # WS probes: 1–2 per question (enough to separate backend vs play-gate).
    base = f"http://127.0.0.1:{settings.api_port}"
    # Prefer local if running; else skip WS unless EXPLICIT.
    ws_enabled = True
    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.get(f"{base}/api/health")
    except Exception:
        ws_enabled = False
        print("\n[WS] local API not up — skipping WS probes (backend-only still valid)")

    if ws_enabled:
        for label, question in QUESTIONS:
            for i in range(2):
                print(f"\n--- ws {label}[{i}] ---")
                row = await run_ws_probe(label, question, i, base)
                ws_rows.append(row)
                if row.get("invalid"):
                    print(f"INVALID: {row.get('reason')}")
                    if row.get("reason") == "HF_402":
                        break
                    continue
                k = row["kpis"]
                print(
                    f"  D backend→frontend={k['D_backend_audio_delivery_ms']}ms "
                    f"E play_gate(first_chunk→audio_done)={k['E_frontend_playback_gate_ms']}ms "
                    f"first_chunk@{k['ws_ttfa_first_chunk_ms']}ms "
                    f"audio_done@{k['ws_play_gate_ms']}ms"
                )
            else:
                continue
            break

    valid_b = [r for r in backend_rows if not r.get("invalid")]
    valid_w = [r for r in ws_rows if not r.get("invalid")]

    summary = {
        "phase": "1.3",
        "n_backend_valid": len(valid_b),
        "n_backend_invalid": len(backend_rows) - len(valid_b),
        "n_ws_valid": len(valid_w),
        "stats_backend": {
            "A_llm_ttft_ms": _stats(
                [r["kpis"]["A_time_to_first_text_ms"] for r in valid_b]
            ),
            "B_ttft_to_tts_request_ms": _stats(
                [r["kpis"]["B_time_to_first_tts_request_ms"] for r in valid_b]
            ),
            "chunker_wait_ms": _stats([r["kpis"]["chunker_wait_ms"] for r in valid_b]),
            "queue_wait_ms": _stats([r["kpis"]["queue_wait_ms"] for r in valid_b]),
            "C_tts_ttfb_ms": _stats([r["kpis"]["C_tts_first_audio_ms"] for r in valid_b]),
            "connection_latency_ms": _stats(
                [r["kpis"]["connection_latency_ms"] for r in valid_b]
            ),
            "total_tts_first_request_ms": _stats(
                [r["kpis"]["total_tts_first_request_ms"] for r in valid_b]
            ),
            "F_ttfa_llm_start_to_first_audio_ms": _stats(
                [r["kpis"]["F_ttfa_from_llm_start_ms"] for r in valid_b]
            ),
            "llm_first_token_to_first_audio_ms": _stats(
                [r["kpis"]["llm_first_token_to_first_audio_ms"] for r in valid_b]
            ),
            "first_frag_chars": _stats(
                [float(r["kpis"]["first_frag_chars"]) for r in valid_b]
            ),
        },
        "stats_ws": {
            "D_backend_to_frontend_ms": _stats(
                [r["kpis"]["D_backend_audio_delivery_ms"] for r in valid_w]
            ),
            "E_first_chunk_to_audio_done_ms": _stats(
                [r["kpis"]["E_frontend_playback_gate_ms"] for r in valid_w]
            ),
            "ws_first_chunk_ms": _stats(
                [r["kpis"]["ws_ttfa_first_chunk_ms"] for r in valid_w]
            ),
            "ws_audio_done_ms": _stats(
                [r["kpis"]["ws_play_gate_ms"] for r in valid_w]
            ),
        },
    }

    # Biggest recurring gap across valid backend runs
    gap_pairs: dict[str, list[float]] = {}
    for r in valid_b:
        for g in r["chronology"].get("gaps") or []:
            key = f"{g['from']} → {g['to']}"
            gap_pairs.setdefault(key, []).append(float(g["delta_ms"]))
    ranked = sorted(
        (
            {"gap": k, **_stats(v)}
            for k, v in gap_pairs.items()
        ),
        key=lambda x: x["avg"] or 0,
        reverse=True,
    )
    summary["biggest_gaps_ranked"] = ranked[:8]
    if ranked:
        top = ranked[0]
        summary["BIGGEST_LATENCY_GAP"] = (
            f"{top['gap']} = {top['avg']} ms (avg, n={top['n']})"
        )

    payload = {
        "summary": summary,
        "backend_runs": backend_rows,
        "ws_runs": ws_rows,
        "questions": QUESTIONS,
        "notes": [
            "No 'Bonjour' greeting turns — RAG/LLM/TTS forced.",
            "Backend TTFA = llm_start → first Fish audio byte (no browser).",
            "WS E = first audio_chunk receive → audio_done (current play gate).",
            "HF_402 runs marked invalid; never invented.",
        ],
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\nWrote {OUT}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
