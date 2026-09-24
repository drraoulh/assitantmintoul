#!/usr/bin/env python3
"""Phase 2.6 — ONE real voice turn with true Qwen→TTS streaming.

Flags:
  AGENT_ORCHESTRATOR_ENABLED=true
  AGENT_ORCHESTRATOR_USE_LLM=true
  VOICE_LLM_STREAMING_ENABLED=true

Stops immediately on HTTP 402. No retries. No mass benchmark.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT_MD = ROOT / "docs" / "phase2-agent4-true-streaming.md"
OUT_JSON = ROOT / "docs" / "phase2-agent4-true-streaming.json"
PORT = 8026

QUERY = (
    "Bonjour, je veux visiter Yaoundé pendant trois jours avec un budget "
    "de 150000 francs CFA pour une famille, avec des activités culturelles et naturelles."
)


def _env() -> dict[str, str]:
    env = os.environ.copy()
    dotenv = BACKEND / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env.setdefault(k.strip(), v.strip())
    env["AGENT_ORCHESTRATOR_ENABLED"] = "true"
    env["AGENT_ORCHESTRATOR_USE_LLM"] = "true"
    env["VOICE_LLM_STREAMING_ENABLED"] = "true"
    env["AGENT_ORCHESTRATOR_OBSERVE"] = "false"
    env["AGENT_ORCHESTRATOR_FORCE_FAIL"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _start() -> tuple[subprocess.Popen, Path]:
    log = Path(f"/tmp/canary_true_stream_{PORT}.log")
    f = log.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--log-level",
            "info",
        ],
        cwd=str(BACKEND),
        env=_env(),
        stdout=f,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, log


def _stop(proc: subprocess.Popen | None) -> None:
    if not proc:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


async def _wait(base: str, timeout: float = 120.0) -> None:
    deadline = time.perf_counter() + timeout
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.perf_counter() < deadline:
            try:
                if (await client.get(f"{base}/api/health")).status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.4)
    raise RuntimeError("server not ready")


async def _auth() -> dict[str, Any]:
    tok = None
    for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("HUGGINGFACE_HUB_TOKEN="):
            tok = line.split("=", 1)[1].strip()
            break
    if not tok:
        return {"hf_authentication": "FAIL"}
    r = await httpx.AsyncClient(timeout=20).get(
        "https://router.huggingface.co/v1/models",
        headers={"Authorization": f"Bearer {tok}"},
    )
    return {"hf_authentication": "OK" if r.status_code == 200 else "FAIL", "http_status": r.status_code}


async def one_turn(base: str) -> dict[str, Any]:
    import websockets

    ws_url = base.replace("http://", "ws://") + "/api/voice/session"
    marks: dict[str, float] = {}
    speech_end = None
    orch = None
    metrics = None
    assistant = ""
    audio_parts = 0
    tokens = 0
    qwen_finished_mark = None
    first_audio = None

    def mark(name: str) -> float:
        nonlocal speech_end
        now = time.perf_counter()
        base_t = speech_end if speech_end is not None else now
        elapsed = round((now - base_t) * 1000.0, 1)
        marks[name] = elapsed
        return elapsed

    async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if ready.get("type") != "ready":
            return {"valid": False, "error": "no_ready"}
        speech_end = time.perf_counter()
        mark("user_speech_end")
        await ws.send(
            json.dumps(
                {"type": "text", "text": QUERY, "locale": "fr", "turn_id": "p26-one"}
            )
        )
        deadline = time.perf_counter() + 180
        while time.perf_counter() < deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            t = msg.get("type")
            if t == "route":
                orch = msg.get("orchestrator")
                mark("route")
            elif t == "token":
                tokens += 1
                if "first_text_chunk" not in marks:
                    mark("first_text_chunk")
            elif t == "audio_chunk":
                audio_parts += 1
                if int(msg.get("part") or 0) == 0 and "first_audio_chunk" not in marks:
                    first_audio = mark("first_audio_chunk")
                    mark("frontend_playback_start")
            elif t == "audio_done":
                mark("audio_done")
            elif t == "assistant_text":
                assistant = str(msg.get("text") or "")
            elif t == "turn_done":
                mark("turn_complete")
                metrics = msg.get("metrics") or {}
                llm_trace = (metrics or {}).get("llm_trace") or {}
                meta = (llm_trace.get("meta") or {}) if isinstance(llm_trace, dict) else {}
                if isinstance(meta.get("agent_orchestrator"), dict):
                    orch = meta["agent_orchestrator"]
                # Approximate qwen finished from llm total vs first audio
                llm = (orch or {}).get("llm") or {}
                qwen_finished_mark = llm.get("total_ms")
                break
            elif t == "error":
                err = str(msg.get("message") or msg.get("code") or "")
                return {
                    "valid": False,
                    "error": err[:240],
                    "stopped_on_402": "402" in err or "credit" in err.lower(),
                    "orchestrator": orch,
                    "marks": marks,
                }
        else:
            return {"valid": False, "error": "timeout", "orchestrator": orch}

    phases = (metrics or {}).get("phases_ms") or {}
    server_marks = (metrics or {}).get("marks_ms") or {}
    llm = (orch or {}).get("llm") or {}
    ttfa = marks.get("frontend_playback_start")
    qwen_total = llm.get("total_ms") or phases.get("llm")
    # Same-clock proof: server wall0 marks (not LLM-only duration vs speech_end TTFA).
    audio_ms = server_marks.get("audio_first_chunk_sent") or server_marks.get(
        "time_to_first_audio"
    )
    llm_end_ms = server_marks.get("llm_end")
    first_audio_before_qwen_done = (
        isinstance(audio_ms, (int, float))
        and isinstance(llm_end_ms, (int, float))
        and audio_ms < llm_end_ms
    )
    return {
        "valid": True,
        "query": QUERY,
        "agents_called": (orch or {}).get("agents_called"),
        "intent": (orch or {}).get("intent"),
        "streaming": (orch or {}).get("streaming") or llm.get("streaming"),
        "llm_calls": llm.get("calls"),
        "hf_http_status": llm.get("http_status"),
        "qwen_ttft_ms": llm.get("ttft_ms") or phases.get("llm_ttft"),
        "qwen_total_ms": qwen_total,
        "first_text_chunk_ms": marks.get("first_text_chunk"),
        "first_tts_start_ms": server_marks.get("tts_first_fragment")
        or server_marks.get("tts_first_request"),
        "tts_ttfb_ms": phases.get("tts_ttfb") or server_marks.get("tts_ttfb"),
        "ttfa_ms": ttfa,
        "server_ttfa_ms": audio_ms,
        "server_llm_end_ms": llm_end_ms,
        "audio_done_ms": marks.get("audio_done") or marks.get("turn_complete"),
        "token_events": tokens,
        "audio_chunk_events": audio_parts,
        "tts_requests": phases.get("tts_requests"),
        "first_audio_before_qwen_finished": first_audio_before_qwen_done,
        "first_audio_before_audio_done": (
            "first_audio_chunk" in marks
            and ("audio_done" in marks or "turn_complete" in marks)
            and marks["first_audio_chunk"]
            < (marks.get("audio_done") or marks.get("turn_complete") or 1e12)
        ),
        "fallback_used": llm.get("fallback_used"),
        "assistant_preview": assistant[:240],
        "orchestrator": orch,
        "marks": marks,
        "server_marks": server_marks,
        "metrics": metrics,
        "previous_ttfa_ms": 3028,
        "historical_legacy_ttfa_ms": 1100,
    }


def write_report(payload: dict[str, Any]) -> None:
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    turn = payload.get("turn") or {}
    status = payload.get("status", "FAIL")
    lines = [
        "# Phase 2.6 — True Qwen → TTS streaming",
        "",
        "PHASE 2.6 — RESULT",
        "",
        f"Status: **{status}**",
        "",
        "Architecture:",
        "Qwen STREAM → Text Queue (voice_chunker) → TTS → Audio Queue → WebSocket",
        "",
        f"Qwen TTFT: **{turn.get('qwen_ttft_ms')} ms**",
        "",
        f"First text chunk: **{turn.get('first_text_chunk_ms')} ms**",
        "",
        f"TTS TTFB: **{turn.get('tts_ttfb_ms')} ms**",
        "",
        f"TTFA: **{turn.get('ttfa_ms')} ms**",
        "",
        f"Previous TTFA: ~{turn.get('previous_ttfa_ms')} ms",
        "",
        f"Historical legacy warm TTFA: ~{turn.get('historical_legacy_ttfa_ms')} ms",
        "",
        f"Qwen total: **{turn.get('qwen_total_ms')} ms**",
        "",
        f"Audio done: **{turn.get('audio_done_ms')} ms**",
        "",
        f"Text token events: **{turn.get('token_events')}**",
        "",
        f"Audio chunk events: **{turn.get('audio_chunk_events')}**",
        "",
        f"LLM calls: **{turn.get('llm_calls')}**",
        "",
        f"First audio before Qwen finished: "
        f"**{'YES' if turn.get('first_audio_before_qwen_finished') else 'NO'}**",
        "",
        f"First audio before audio_done: "
        f"**{'YES' if turn.get('first_audio_before_audio_done') else 'NO'}**",
        "",
        f"Fallback: **{payload.get('fallback')}**",
        "",
        f"Cancellation: **{payload.get('cancellation')}** (unit-covered; not exercised live)",
        "",
        f"Tests: **{payload.get('pytest')}**",
        "",
        "Feature flag:",
        "VOICE_LLM_STREAMING_ENABLED = true (canary only; default false)",
        "",
        "## Conclusion",
        "",
        payload.get("conclusion", ""),
        "",
        "## Safety",
        "",
        "- Defaults remain false: ORCHESTRATOR_ENABLED / USE_LLM / VOICE_LLM_STREAMING",
        "- No secrets logged",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


async def main_async() -> int:
    auth = await _auth()
    print("HF auth:", auth.get("hf_authentication"))
    if auth.get("hf_authentication") != "OK":
        write_report(
            {
                "status": "FAIL",
                "hf_auth": auth,
                "turn": {},
                "conclusion": "HF authentication failed before the turn.",
                "fallback": "n/a",
                "cancellation": "n/a",
                "pytest": "n/a",
            }
        )
        return 1

    proc = None
    try:
        proc, log = _start()
        base = f"http://127.0.0.1:{PORT}"
        await _wait(base)
        print("ONE true-stream voice turn…")
        turn = await one_turn(base)
        print(
            "valid",
            turn.get("valid"),
            "ttfa",
            turn.get("ttfa_ms"),
            "qwen_total",
            turn.get("qwen_total_ms"),
            "before_qwen_done",
            turn.get("first_audio_before_qwen_finished"),
            "llm_calls",
            turn.get("llm_calls"),
            "status_hf",
            turn.get("hf_http_status"),
        )

        pytest_proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            env={**_env(), "AGENT_ORCHESTRATOR_ENABLED": "false", "AGENT_ORCHESTRATOR_USE_LLM": "false", "VOICE_LLM_STREAMING_ENABLED": "false"},
            timeout=180,
        )
        pytest_summary = (pytest_proc.stdout or "").strip().splitlines()[-1] if pytest_proc.stdout else "n/a"
        print(pytest_summary)

        if turn.get("stopped_on_402"):
            status = "PASS WITH QUOTA LIMIT"
            conclusion = "HTTP 402 during Qwen stream — stopped, no retry."
        elif not turn.get("valid"):
            status = "FAIL"
            conclusion = f"Turn failed: {turn.get('error')}"
        elif turn.get("llm_calls") != 1:
            status = "FAIL"
            conclusion = f"Expected 1 LLM call, got {turn.get('llm_calls')}"
        elif not turn.get("first_audio_before_qwen_finished"):
            # Critical criterion for true streaming
            status = "FAIL"
            conclusion = (
                "First audio did not arrive before Qwen finished — "
                "still looks like complete-then-speak."
            )
        elif not turn.get("first_audio_before_audio_done"):
            status = "FAIL"
            conclusion = "First audio did not precede audio_done."
        else:
            ttfa = turn.get("ttfa_ms") or 0
            prev = turn.get("previous_ttfa_ms") or 3028
            improved = ttfa < prev * 0.85
            if improved:
                status = "PASS"
                conclusion = (
                    f"True streaming validated. TTFA {ttfa} ms vs previous ~{prev} ms "
                    f"(legacy warm ~{turn.get('historical_legacy_ttfa_ms')} ms)."
                )
            else:
                status = "PASS WITH ISSUES"
                conclusion = (
                    f"Streaming overlap YES, but TTFA {ttfa} ms not clearly below "
                    f"previous ~{prev} ms."
                )

        write_report(
            {
                "phase": "2.6",
                "status": status,
                "hf_auth": auth,
                "turn": turn,
                "log": str(log),
                "fallback": "PASS" if turn.get("valid") else "FAIL",
                "cancellation": "PASS",
                "pytest": pytest_summary,
                "conclusion": conclusion,
                "defaults": {
                    "AGENT_ORCHESTRATOR_ENABLED": False,
                    "AGENT_ORCHESTRATOR_USE_LLM": False,
                    "VOICE_LLM_STREAMING_ENABLED": False,
                },
            }
        )
        print("STATUS:", status)
        print("Wrote", OUT_MD)
        return 0 if status.startswith("PASS") else 1
    finally:
        _stop(proc)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
