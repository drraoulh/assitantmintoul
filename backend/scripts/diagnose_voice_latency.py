"""Phase 1.1 — voice latency diagnostic (no architecture changes).

Runs isolated STT / TTS / text / full-voice-pipeline probes and writes
docs/latency-voice-diag.json. Marks HF 402 runs as invalid.

Usage (from repo root, secrets loaded):

  python backend/scripts/diagnose_voice_latency.py
"""

from __future__ import annotations

import asyncio
import base64
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

VOICE_PHRASE = "Bonjour, propose-moi une activité nature au Cameroun."
TEXT_PHRASE = "Quels plats camerounais dois-je goûter ?"
FIXTURE = Path("/tmp/voice_diag_fixture.mp3")
N = 5


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [v for v in values if v is not None and v >= 0]
    if not clean:
        return {"avg": None, "min": None, "max": None, "n": 0}
    return {
        "avg": round(statistics.mean(clean), 1),
        "min": round(min(clean), 1),
        "max": round(max(clean), 1),
        "n": len(clean),
    }


async def ensure_fixture(speech) -> bytes:
    if FIXTURE.exists() and FIXTURE.stat().st_size > 1000:
        return FIXTURE.read_bytes()
    chunks: list[bytes] = []
    async for chunk in speech.synthesize_stream(VOICE_PHRASE):
        chunks.append(chunk)
    audio = b"".join(chunks)
    FIXTURE.write_bytes(audio)
    return audio


async def measure_stt(speech, audio: bytes, n: int = N) -> list[dict]:
    rows = []
    for i in range(n):
        t0 = time.perf_counter()
        text, lang = await speech.transcribe(audio, mime_type="audio/mpeg", filename="fixture.mp3")
        ms = (time.perf_counter() - t0) * 1000
        rows.append({"i": i, "stt_ms": round(ms, 1), "text": (text or "")[:80], "lang": lang})
        print(f"STT[{i}] {ms:.0f}ms → {(text or '')[:50]!r}")
    return rows


async def measure_tts(speech, text: str, n: int = N) -> list[dict]:
    rows = []
    for i in range(n):
        t0 = time.perf_counter()
        ttfb = None
        total_bytes = 0
        async for chunk in speech.synthesize_stream(text[:180]):
            if ttfb is None and chunk:
                ttfb = (time.perf_counter() - t0) * 1000
            total_bytes += len(chunk)
        total = (time.perf_counter() - t0) * 1000
        rows.append(
            {
                "i": i,
                "ttfb_ms": round(ttfb or -1, 1),
                "total_ms": round(total, 1),
                "bytes": total_bytes,
            }
        )
        print(f"TTS[{i}] ttfb={ttfb:.0f}ms total={total:.0f}ms bytes={total_bytes}")
    return rows


async def measure_text(ai, message: str, n: int = N) -> list[dict]:
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.metrics.latency import PhaseTimer

    rows = []
    for i in range(n):
        timer = PhaseTimer(f"text:{i}")
        reply = ""
        invalid = False
        reason = ""
        if isinstance(ai, HuggingFaceAIService):
            async for event in ai.stream_response(message, brief=False, timer=timer):
                if event.get("type") == "token":
                    reply += str(event.get("text") or "")
                elif event.get("type") == "done":
                    reply = str(event.get("text") or reply)
                elif event.get("type") == "error":
                    invalid = True
                    reason = str(event.get("message") or event.get("code") or "error")
                    if "402" in reason or "credits" in reason.lower() or "depleted" in reason.lower():
                        reason = "HF_402"
                    break
        else:
            with timer.phase("llm"):
                response = await ai.generate_response(message, brief=False)
                reply = response.message
        rows.append(
            {
                "i": i,
                "invalid": invalid,
                "reason": reason,
                "reply_preview": reply[:100],
                "metrics": timer.as_dict(),
            }
        )
        m = timer.phases
        print(
            f"TEXT[{i}] invalid={invalid} ttft={m.get('llm_ttft')} llm={m.get('llm')} "
            f"rag={m.get('rag')} total={timer.total_ms:.0f}"
        )
    return rows


async def measure_voice_pipeline(ai, speech, audio: bytes, n: int = N) -> list[dict]:
    """Mirror WS voice turn: STT → stream LLM brief → first TTS sentence."""
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.api.voice_ws import _split_ready_sentences
    from app.services.metrics.latency import PhaseTimer

    rows = []
    for i in range(n):
        timer = PhaseTimer(f"voice:{i}")
        marks: dict[str, float] = {"request_received": 0.0}
        wall0 = time.perf_counter()

        def mark(name: str) -> float:
            marks[name] = round((time.perf_counter() - wall0) * 1000, 1)
            return marks[name]

        invalid = False
        reason = ""
        reply = ""

        mark("stt_start")
        with timer.phase("stt"):
            user_text, _lang = await speech.transcribe(
                audio, mime_type="audio/mpeg", filename="fixture.mp3"
            )
        mark("stt_end")

        if not user_text:
            rows.append({"i": i, "invalid": True, "reason": "empty_transcript", "marks_ms": marks})
            continue

        mark("llm_start")
        first_token = False
        sentence_buffer = ""
        first_tts_fragment = None
        if not isinstance(ai, HuggingFaceAIService):
            invalid = True
            reason = "non_hf"
        else:
            async for event in ai.stream_response(
                user_text, brief=True, locale="fr", timer=timer
            ):
                etype = event.get("type")
                if etype == "token":
                    piece = str(event.get("text") or "")
                    if not first_token:
                        mark("llm_first_token")
                        first_token = True
                    reply += piece
                    sentence_buffer += piece
                    ready, sentence_buffer = _split_ready_sentences(sentence_buffer)
                    if ready and first_tts_fragment is None:
                        first_tts_fragment = ready[0]
                        mark("tts_first_fragment")
                elif etype == "done":
                    mark("llm_end")
                    reply = str(event.get("text") or reply)
                    if sentence_buffer.strip() and first_tts_fragment is None:
                        first_tts_fragment = sentence_buffer.strip()
                        mark("tts_first_fragment")
                elif etype == "error":
                    invalid = True
                    reason = str(event.get("message") or event.get("code") or "error")
                    if "402" in reason or "credits" in reason.lower() or "depleted" in reason.lower():
                        reason = "HF_402"
                    break

        if invalid:
            rows.append(
                {
                    "i": i,
                    "invalid": True,
                    "reason": reason,
                    "marks_ms": marks,
                    "metrics": timer.as_dict(),
                }
            )
            print(f"VOICE[{i}] INVALID {reason}")
            continue

        # TTS first fragment only (matches first-audio sensation)
        frag = first_tts_fragment or (reply[:120] if reply else "Bonjour")
        mark("tts_start")
        tts_begin = time.perf_counter()
        first_byte = None
        async for chunk in speech.synthesize_stream(frag):
            if first_byte is None and chunk:
                first_byte = (time.perf_counter() - tts_begin) * 1000
                timer.mark("tts_ttfb", first_byte)
                mark("tts_first_byte")
                mark("audio_first_chunk_sent")
        mark("tts_end")
        mark("turn_end")
        timer.mark("first_audio", marks.get("audio_first_chunk_sent", 0))

        rows.append(
            {
                "i": i,
                "invalid": False,
                "transcript": (user_text or "")[:100],
                "reply_preview": reply[:120],
                "marks_ms": marks,
                "metrics": timer.as_dict(),
            }
        )
        m = timer.phases
        print(
            f"VOICE[{i}] stt={m.get('stt'):.0f} rag={m.get('rag')} ground={m.get('grounding')} "
            f"ttft={m.get('llm_ttft')} llm={m.get('llm')} tts_ttfb={m.get('tts_ttfb')} "
            f"first_audio={marks.get('audio_first_chunk_sent')} total={timer.total_ms:.0f}"
        )
    return rows


async def cold_vs_warm() -> dict:
    """Rough local cold vs warm (process-level), not Render free spin-up."""
    import httpx
    from app.core.config import get_settings

    settings = get_settings()
    # Local warm: already hydrated this process
    from app.services.rag.factory import get_rag_service

    rag = get_rag_service()
    t0 = time.perf_counter()
    await rag.retrieve_chunks("Que visiter à Yaoundé ?", top_k=4)
    warm_ms = (time.perf_counter() - t0) * 1000

    # External Render health (network + possible cold)
    render_ms = None
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            t1 = time.perf_counter()
            r = await client.get("https://cameroon-ai-tour-guide-api.onrender.com/api/health")
            render_ms = (time.perf_counter() - t1) * 1000
            render_status = r.status_code
    except Exception as exc:  # noqa: BLE001
        render_status = str(exc)
        render_ms = None

    return {
        "local_rag_warm_ms": round(warm_ms, 1),
        "render_health_ms": round(render_ms, 1) if render_ms is not None else None,
        "render_status": render_status,
        "note": (
            "Render Free cold start is not fully reproducible here; "
            "render_health_ms includes network + possible spin-up."
        ),
        "app_env": settings.app_env,
    }


async def main() -> None:
    from app.api.deps import get_ai_service, get_speech_service
    from app.core.config import get_settings
    from app.services.rag.factory import get_rag_service

    get_settings.cache_clear()
    speech = get_speech_service()
    ai = get_ai_service()
    rag = get_rag_service()
    warm = getattr(rag, "warm", None)
    if callable(warm):
        await warm()

    audio = await ensure_fixture(speech)
    print(f"fixture={len(audio)} bytes")

    stt_rows = await measure_stt(speech, audio, N)
    tts_rows = await measure_tts(
        speech,
        "Le Cameroun, Afrique en miniature, offre des paysages de montagne et de forêt.",
        N,
    )
    text_rows = await measure_text(ai, TEXT_PHRASE, N)
    voice_rows = await measure_voice_pipeline(ai, speech, audio, N)
    cold = await cold_vs_warm()

    valid_voice = [r for r in voice_rows if not r.get("invalid")]
    valid_text = [r for r in text_rows if not r.get("invalid")]

    def col(rows: list[dict], *keys: str) -> list[float]:
        out: list[float] = []
        for r in rows:
            cur: object = r
            ok = True
            for k in keys:
                if not isinstance(cur, dict) or k not in cur:
                    ok = False
                    break
                cur = cur[k]
            if ok and isinstance(cur, (int, float)):
                out.append(float(cur))
        return out

    summary = {
        "STT": _stats([r["stt_ms"] for r in stt_rows]),
        "Routing": _stats(col(valid_voice, "metrics", "phases_ms", "routing")),
        "RAG": _stats(col(valid_voice, "metrics", "phases_ms", "rag")),
        "Grounding": _stats(col(valid_voice, "metrics", "phases_ms", "grounding")),
        "LLM_TTFT": _stats(col(valid_voice, "metrics", "phases_ms", "llm_ttft")),
        "LLM_total": _stats(col(valid_voice, "metrics", "phases_ms", "llm")),
        "TTS_TTFB": _stats(col(valid_voice, "metrics", "phases_ms", "tts_ttfb")),
        "TTS_total_first": _stats(
            [
                (r["marks_ms"].get("tts_end", 0) - r["marks_ms"].get("tts_start", 0))
                for r in valid_voice
                if r.get("marks_ms")
            ]
        ),
        "Premier_audio": _stats(
            [r["marks_ms"].get("audio_first_chunk_sent", -1) for r in valid_voice if r.get("marks_ms")]
        ),
        "TOTAL": _stats([r["metrics"]["total_ms"] for r in valid_voice]),
        "TEXT_TTFT": _stats(col(valid_text, "metrics", "phases_ms", "llm_ttft")),
        "TEXT_LLM": _stats(col(valid_text, "metrics", "phases_ms", "llm")),
        "TEXT_TOTAL": _stats([r["metrics"]["total_ms"] for r in valid_text]),
        "TTS_isolated_TTFB": _stats([r["ttfb_ms"] for r in tts_rows]),
        "TTS_isolated_total": _stats([r["total_ms"] for r in tts_rows]),
    }

    payload = {
        "label": "voice-diag-phase1.1",
        "voice_phrase": VOICE_PHRASE,
        "text_phrase": TEXT_PHRASE,
        "n_requested": N,
        "valid_voice_n": len(valid_voice),
        "valid_text_n": len(valid_text),
        "summary": summary,
        "stt": stt_rows,
        "tts_isolated": tts_rows,
        "text": text_rows,
        "voice": voice_rows,
        "cold_vs_warm": cold,
    }
    out = ROOT / "docs" / "latency-voice-diag.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    for k, v in summary.items():
        print(f"{k:20} avg={v['avg']} min={v['min']} max={v['max']} n={v['n']}")
    print("wrote", out)


if __name__ == "__main__":
    asyncio.run(main())
