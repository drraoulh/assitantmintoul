"""Phase 1.2 — measure time-to-first-audio for the overlapped voice pipeline.

Mirrors WS turn: STT → LLM stream + early chunker → first Fish TTS fragment.
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

PHRASES = [
    ("bonjour", "Bonjour"),
    ("food", "Quels plats camerounais dois-je goûter ?"),
    ("nature", "Propose-moi une activité nature au Cameroun."),
    ("yaounde", "Que puis-je visiter à Yaoundé ?"),
    ("culture", "Parle-moi de la culture camerounaise."),
]


async def run_one(ai, speech, label: str, text: str, *, with_stt_audio: bytes | None) -> dict:
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.metrics.latency import PhaseTimer
    from app.services.speech.voice_chunker import (
        append_token,
        flush_remainder,
        split_ready_phrases,
    )

    timer = PhaseTimer(f"p12:{label}")
    marks: dict[str, float] = {"request_received": 0.0}
    wall0 = time.perf_counter()

    def mark(name: str) -> None:
        marks[name] = round((time.perf_counter() - wall0) * 1000, 1)

    invalid = False
    reason = ""
    user_text = text

    if with_stt_audio is not None:
        mark("stt_start")
        with timer.phase("stt"):
            user_text, _ = await speech.transcribe(
                with_stt_audio, mime_type="audio/mpeg", filename="f.mp3"
            )
        mark("stt_end")
        if not user_text:
            return {"label": label, "invalid": True, "reason": "empty_stt"}

    if not isinstance(ai, HuggingFaceAIService):
        return {"label": label, "invalid": True, "reason": "non_hf"}

    mark("llm_start")
    buf = ""
    first_flush = True
    first_token = False
    first_frag: str | None = None
    reply = ""
    tts_requests = 0

    async for event in ai.stream_response(user_text, brief=True, locale="fr", timer=timer):
        etype = event.get("type")
        if etype == "token":
            piece = str(event.get("text") or "")
            if not first_token:
                mark("llm_first_token")
                first_token = True
            reply += piece
            buf = append_token(buf, piece)
            ready, buf = split_ready_phrases(buf, first_chunk=first_flush)
            if ready and first_frag is None:
                first_frag = ready[0]
                mark("tts_first_fragment")
                first_flush = False
        elif etype == "done":
            mark("llm_end")
            reply = str(event.get("text") or reply)
            for part in flush_remainder(buf):
                if first_frag is None:
                    first_frag = part
                    mark("tts_first_fragment")
            break
        elif etype == "error":
            invalid = True
            reason = str(event.get("message") or "")
            if "402" in reason or "credit" in reason.lower() or "depleted" in reason.lower():
                reason = "HF_402"
            break

    if invalid:
        return {"label": label, "invalid": True, "reason": reason, "marks_ms": marks, "metrics": timer.as_dict()}

    frag = first_frag or reply[:80] or "Bonjour"
    mark("tts_start")
    t0 = time.perf_counter()
    async for chunk in speech.synthesize_stream(frag):
        if chunk:
            timer.mark("tts_ttfb", (time.perf_counter() - t0) * 1000)
            mark("tts_first_byte")
            mark("audio_first_chunk_sent")
            marks["time_to_first_audio"] = marks["audio_first_chunk_sent"]
            timer.mark("time_to_first_audio", marks["time_to_first_audio"])
            break
    # drain rest quickly for total TTS first request
    async for _ in speech.synthesize_stream(frag):
        pass
    mark("tts_end")
    tts_requests = 1
    timer.mark("tts_requests", float(tts_requests))
    mark("turn_end")

    return {
        "label": label,
        "invalid": False,
        "first_frag": frag,
        "first_frag_chars": len(frag),
        "reply_preview": reply[:120],
        "marks_ms": marks,
        "metrics": timer.as_dict(),
    }


async def main() -> None:
    from app.api.deps import get_ai_service, get_speech_service
    from app.core.config import get_settings
    from app.services.rag.factory import get_rag_service

    get_settings.cache_clear()
    speech = get_speech_service()
    ai = get_ai_service()
    rag = get_rag_service()
    if callable(getattr(rag, "warm", None)):
        await rag.warm()

    # Optional STT on nature phrase using fixture if present
    fixture = Path("/tmp/voice_diag_fixture.mp3")
    audio = fixture.read_bytes() if fixture.exists() else None

    results = []
    # Two rounds when possible (= up to 10) — stop early on HF_402 streak
    hf402 = 0
    for round_i in range(2):
        for label, phrase in PHRASES:
            use_audio = audio if label == "nature" and audio else None
            # For nature with audio, still pass the intended phrase as STT may drift;
            # measure_stt path uses audio transcript as user_text.
            row = await run_one(ai, speech, f"{label}_r{round_i}", phrase, with_stt_audio=use_audio)
            results.append(row)
            print(
                f"{row['label']}: invalid={row.get('invalid')} "
                f"ttfa={row.get('marks_ms', {}).get('time_to_first_audio')} "
                f"frag_chars={row.get('first_frag_chars')} "
                f"ttft={row.get('metrics', {}).get('phases_ms', {}).get('llm_ttft')} "
                f"reason={row.get('reason', '')}"
            )
            if row.get("reason") == "HF_402":
                hf402 += 1
                if hf402 >= 3:
                    break
            else:
                hf402 = 0
        if hf402 >= 3:
            break

    valid = [r for r in results if not r.get("invalid")]

    def col(key: str) -> list[float]:
        vals = []
        for r in valid:
            marks = r.get("marks_ms") or {}
            phases = (r.get("metrics") or {}).get("phases_ms") or {}
            if key in marks:
                vals.append(float(marks[key]))
            elif key in phases:
                vals.append(float(phases[key]))
        return vals

    def stats(vals: list[float]) -> dict:
        if not vals:
            return {"avg": None, "min": None, "max": None, "n": 0}
        return {
            "avg": round(statistics.mean(vals), 1),
            "min": round(min(vals), 1),
            "max": round(max(vals), 1),
            "n": len(vals),
        }

    summary = {
        "STT": stats(col("stt")),
        "LLM_TTFT": stats(col("llm_ttft")),
        "LLM_total": stats(col("llm")),
        "TTS_TTFB": stats(col("tts_ttfb")),
        "First_audio_TTFA": stats(col("time_to_first_audio")),
        "tts_first_fragment_at": stats(col("tts_first_fragment")),
        "first_frag_chars": stats([float(r["first_frag_chars"]) for r in valid if "first_frag_chars" in r]),
        "TOTAL": stats([float(r["metrics"]["total_ms"]) for r in valid]),
        "valid_n": len(valid),
        "invalid_n": len(results) - len(valid),
    }
    payload = {"label": "phase1.2-after", "summary": summary, "results": results}
    out = ROOT / "docs" / "latency-phase12-after.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    asyncio.run(main())
