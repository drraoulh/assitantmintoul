"""Measure chat / grounding / TTS latency phases (before/after optimisation).

Usage (from repo root, with API running and .env loaded):

  python backend/scripts/measure_voice_latency.py --label before --out docs/latency-phase1-before.json
  python backend/scripts/measure_voice_latency.py --label after --out docs/latency-phase1-after.json

Does not require a microphone: text turns only (+ optional TTS).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

PROBES = [
    ("simple", "Bonjour"),
    ("food", "Quels plats camerounais dois-je goûter ?"),
    ("kb_city", "Que visiter à Yaoundé ?"),
    ("circuit", "Propose un circuit nature au Cameroun."),
    ("voice_prompt", "Bonjour, que puis-je visiter au Cameroun ?"),
]


async def _warm() -> None:
    """Hydrate RAG + HTTP clients so the first probe is not a cold start."""
    from app.api.deps import get_ai_service, get_speech_service
    from app.services.rag.factory import get_rag_service

    get_speech_service()
    get_ai_service()
    rag = get_rag_service()
    warm = getattr(rag, "warm", None)
    if callable(warm):
        await warm()
    else:
        await rag.retrieve_chunks("warmup", top_k=1)


async def measure_once(label: str, *, with_tts: bool = True) -> dict:
    from app.api.deps import get_ai_service, get_speech_service
    from app.services.ai.huggingface import HuggingFaceAIService
    from app.services.ai.routing import route_query
    from app.services.metrics.latency import PhaseTimer

    await _warm()
    ai = get_ai_service()
    speech = get_speech_service()
    results = []

    for kind, message in PROBES:
        timer = PhaseTimer(f"{label}:{kind}")
        brief = kind in {"simple", "voice_prompt"}
        route = route_query(message)
        with timer.phase("routing"):
            pass
        timer.mark("route_kind_simple", 1.0 if route.skip_kb else 0.0)

        if isinstance(ai, HuggingFaceAIService):
            reply = ""
            async for event in ai.stream_response(
                message,
                brief=brief,
                timer=timer,
            ):
                if event.get("type") == "token":
                    reply += str(event.get("text") or "")
                if event.get("type") == "done":
                    reply = str(event.get("text") or reply)
                if event.get("type") == "error":
                    reply = f"[error] {event.get('message')}"
        else:
            with timer.phase("llm"):
                response = await ai.generate_response(message, brief=brief)
                reply = response.message

        if with_tts:
            try:
                with timer.phase("tts"):
                    begin = time.perf_counter()
                    first = True
                    async for chunk in speech.synthesize_stream(reply[:180] or "Bonjour"):
                        if first and chunk:
                            timer.mark("tts_ttfb", (time.perf_counter() - begin) * 1000)
                            first = False
            except Exception as exc:  # noqa: BLE001
                timer.mark("tts_error", 1)
                reply = f"{reply} [tts:{exc}]"

        timer.log()
        results.append(
            {
                "probe": kind,
                "message": message,
                "route": route.__dict__,
                "reply_preview": (reply or "")[:160],
                "metrics": timer.as_dict(),
                "perf_lines": timer.perf_lines(),
            }
        )

    return {"label": label, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="after")
    parser.add_argument("--out", default="")
    parser.add_argument("--no-tts", action="store_true")
    args = parser.parse_args()
    payload = asyncio.run(measure_once(args.label, with_tts=not args.no_tts))
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
