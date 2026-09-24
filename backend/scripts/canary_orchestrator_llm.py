#!/usr/bin/env python3
"""Phase 2.5C — ONE real voice-path validation with Orchestrator + Qwen.

Starts a single uvicorn with:
  AGENT_ORCHESTRATOR_ENABLED=true
  AGENT_ORCHESTRATOR_USE_LLM=true

Runs exactly one WS text turn (voice pipeline; STT skipped to save HF quota for Qwen).
Stops immediately on HTTP 402 — no retries.

Usage:
  python backend/scripts/canary_orchestrator_llm.py
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
OUT_MD = ROOT / "docs" / "phase2-agent-orchestrator-canary-llm.md"
OUT_JSON = ROOT / "docs" / "phase2-agent-orchestrator-canary-llm.json"
PORT = 8021

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
    env["AGENT_ORCHESTRATOR_OBSERVE"] = "false"
    env["AGENT_ORCHESTRATOR_FORCE_FAIL"] = "false"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _start() -> tuple[subprocess.Popen, Path]:
    log_path = Path(f"/tmp/canary_orch_llm_{PORT}.log")
    log_f = log_path.open("w", encoding="utf-8")
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
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, log_path


def _stop(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


async def _wait_ready(base: str, timeout: float = 120.0) -> None:
    deadline = time.perf_counter() + timeout
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.perf_counter() < deadline:
            try:
                r = await client.get(f"{base}/api/health")
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.4)
    raise RuntimeError(f"server not ready: {base}")


async def _probe_hf_auth() -> dict[str, Any]:
    """One tiny non-chat probe — models list only (cheap). Do not call chat here."""
    tok = None
    for line in (BACKEND / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("HUGGINGFACE_HUB_TOKEN="):
            tok = line.split("=", 1)[1].strip()
            break
    if not tok:
        return {"hf_authentication": "FAIL", "reason": "missing_token"}
    try:
        r = await httpx.AsyncClient(timeout=20.0).get(
            "https://router.huggingface.co/v1/models",
            headers={"Authorization": f"Bearer {tok}"},
        )
        return {
            "hf_authentication": "OK" if r.status_code == 200 else "FAIL",
            "http_status": r.status_code,
        }
    except Exception as exc:  # noqa: BLE001
        return {"hf_authentication": "FAIL", "reason": type(exc).__name__}


async def run_one_voice_turn(base: str) -> dict[str, Any]:
    import websockets

    ws_url = base.replace("http://", "ws://").rstrip("/") + "/api/voice/session"
    marks: dict[str, float] = {}
    speech_end: float | None = None
    orch: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    assistant_text = ""
    error: str | None = None
    first_audio_before_done = False
    audio_started = False

    def mark(name: str) -> None:
        now = time.perf_counter()
        base_t = speech_end if speech_end is not None else now
        marks[name] = round((now - base_t) * 1000.0, 1)

    async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
        ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if ready.get("type") != "ready":
            return {"valid": False, "error": f"no_ready:{ready.get('type')}"}

        speech_end = time.perf_counter()
        mark("user_speech_end")
        await ws.send(
            json.dumps(
                {
                    "type": "text",
                    "text": QUERY,
                    "locale": "fr",
                    "turn_id": "phase25c-one",
                }
            )
        )
        mark("stt_end")  # text turn — STT skipped (quota)

        deadline = time.perf_counter() + 180
        while time.perf_counter() < deadline:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=120))
            mtype = msg.get("type")
            if mtype == "route":
                orch = msg.get("orchestrator")
                mark("route")
            elif mtype == "token":
                if "first_text_chunk" not in marks:
                    mark("first_text_chunk")
            elif mtype == "audio_chunk":
                if int(msg.get("part") or 0) == 0 and "first_audio_chunk" not in marks:
                    mark("first_audio_chunk")
                    mark("frontend_playback_start")
                    audio_started = True
                    if "audio_done" not in marks:
                        first_audio_before_done = True
            elif mtype == "audio_done":
                mark("audio_done")
            elif mtype == "assistant_text":
                assistant_text = str(msg.get("text") or "")
            elif mtype == "turn_done":
                mark("turn_complete")
                metrics = msg.get("metrics") or {}
                llm_trace = (metrics or {}).get("llm_trace") or {}
                meta = (llm_trace.get("meta") or {}) if isinstance(llm_trace, dict) else {}
                if isinstance(meta.get("agent_orchestrator"), dict):
                    orch = meta["agent_orchestrator"]
                break
            elif mtype == "error":
                error = str(msg.get("message") or msg.get("code") or "error")
                # Detect 402 without retry
                if "402" in error or "depleted" in error.lower() or "credit" in error.lower():
                    return {
                        "valid": False,
                        "stopped_on_402": True,
                        "error": error[:240],
                        "orchestrator": orch,
                        "marks": marks,
                    }
                return {
                    "valid": False,
                    "error": error[:240],
                    "orchestrator": orch,
                    "marks": marks,
                }
        else:
            return {"valid": False, "error": "timeout", "orchestrator": orch}

    phases = (metrics or {}).get("phases_ms") or {}
    llm_info = (orch or {}).get("llm") or {}
    agents = list((orch or {}).get("agents_called") or [])
    http_status = llm_info.get("http_status")
    stopped_402 = http_status == 402 or (
        isinstance(llm_info.get("error"), str) and "402" in str(llm_info.get("error"))
    )

    return {
        "valid": True,
        "stopped_on_402": bool(stopped_402),
        "query": QUERY,
        "stt_ms": 0.0,
        "stt_note": "text_turn_proxy — STT skipped once to preserve HF quota for Qwen",
        "agents_called": agents,
        "intent": (orch or {}).get("intent"),
        "agent1_ms": phases.get("intent_router") or (orch or {}).get("intent_ms"),
        "agent2_ms": phases.get("knowledge_agent") or (orch or {}).get("knowledge_ms"),
        "agent3_ms": phases.get("tourism_planner") or (orch or {}).get("planner_ms"),
        "agent4_ms": phases.get("response_agent") or (orch or {}).get("response_ms"),
        "orchestrator_ms": phases.get("orchestrator") or (orch or {}).get("total_ms"),
        "qwen_ttft_ms": llm_info.get("ttft_ms"),
        "qwen_total_ms": llm_info.get("total_ms") or phases.get("llm"),
        "llm_calls": llm_info.get("calls"),
        "hf_http_status": http_status,
        "qwen_model": llm_info.get("model") or "Qwen/Qwen3.5-9B:fastest",
        "fallback_used": llm_info.get("fallback_used"),
        "tts_ttfb_ms": phases.get("tts_ttfb"),
        "ttfa_ms": marks.get("frontend_playback_start"),
        "first_text_chunk_ms": marks.get("first_text_chunk"),
        "first_audio_before_audio_done": first_audio_before_done and audio_started,
        "assistant_preview": (assistant_text or "")[:280],
        "orchestrator": orch,
        "marks": marks,
        "metrics": metrics,
    }


def _write_report(payload: dict[str, Any]) -> None:
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    turn = payload.get("turn") or {}
    auth = payload.get("hf_auth") or {}
    status = payload.get("status", "FAIL")
    agents = turn.get("agents_called") or []
    qwen_status = payload.get("qwen_status", "FAIL")
    lines = [
        "# Phase 2.5C — Orchestrator + Qwen real voice-path validation",
        "",
        "PHASE 2.5C — RESULT",
        "",
        f"Status: **{status}**",
        "",
        "Pipeline:",
        "STT (text-turn proxy) → Agent 1 → Agent 2 → Agent 3 → Agent 4 → Qwen → TTS",
        "",
        f"Qwen: **{qwen_status}**",
        "",
        f"LLM calls: **{turn.get('llm_calls')}**",
        "",
        f"Qwen TTFT: **{turn.get('qwen_ttft_ms')} ms**",
        "",
        f"Qwen total: **{turn.get('qwen_total_ms')} ms**",
        "",
        f"TTS TTFB: **{turn.get('tts_ttfb_ms')} ms**",
        "",
        f"TTFA: **{turn.get('ttfa_ms')} ms**",
        "",
        f"First audio before audio_done: "
        f"**{'YES' if turn.get('first_audio_before_audio_done') else 'NO'}**",
        "",
        f"Fallback: **{payload.get('fallback_status', 'n/a')}**",
        "",
        f"Quota: **{payload.get('quota', 'n/a')}**",
        "",
        "## Checklist",
        "",
        f"- [{'x' if 'intent' in agents else ' '}] Agent 1 exécuté",
        f"- [{'x' if 'knowledge' in agents else ' '}] Agent 2 exécuté",
        f"- [{'x' if 'planner' in agents else ' '}] Agent 3 exécuté",
        f"- [{'x' if 'response' in agents else ' '}] Agent 4 exécuté",
        f"- [{'x' if (turn.get('llm_calls') or 0) >= 1 else ' '}] Qwen réellement appelé",
        f"- [{'x' if (turn.get('llm_calls') or 0) <= 1 else ' '}] exactement ≤1 appel LLM",
        f"- [{'x' if turn.get('tts_ttfb_ms') is not None or turn.get('first_audio_before_audio_done') else ' '}] TTS réellement appelé",
        f"- [{'x' if turn.get('first_audio_before_audio_done') else ' '}] premier chunk audio avant audio_done",
        "",
        "## Measures",
        "",
        f"- STT total: {turn.get('stt_ms')} ms ({turn.get('stt_note')})",
        f"- Agent 1: {turn.get('agent1_ms')} ms",
        f"- Agent 2: {turn.get('agent2_ms')} ms",
        f"- Agent 3: {turn.get('agent3_ms')} ms",
        f"- Agent 4: {turn.get('agent4_ms')} ms",
        f"- Orchestrator total: {turn.get('orchestrator_ms')} ms",
        f"- Qwen TTFT: {turn.get('qwen_ttft_ms')} ms",
        f"- Qwen total: {turn.get('qwen_total_ms')} ms",
        f"- TTS TTFB: {turn.get('tts_ttfb_ms')} ms",
        f"- TTFA: {turn.get('ttfa_ms')} ms",
        f"- HF HTTP status: {turn.get('hf_http_status')}",
        f"- HF authentication: {auth.get('hf_authentication')}",
        f"- Model: `{turn.get('qwen_model')}`",
        f"- Intent: `{turn.get('intent')}`",
        f"- Agents: `{agents}`",
        "",
        "## Answers",
        "",
        f"- A. Full path works: **{payload.get('answer_a')}**",
        f"- B. Qwen called: **{payload.get('answer_b')}**",
        f"- C. TTS after first tokens/chunks: **{payload.get('answer_c')}**",
        f"- D. First audio before audio_done: **{payload.get('answer_d')}**",
        f"- E. Obvious latency regression: **{payload.get('answer_e')}**",
        f"- F. HF calls consumed: **{payload.get('hf_calls_consumed')}**",
        "",
        "## Conclusion",
        "",
        payload.get("conclusion_text", ""),
        "",
        "## Safety",
        "",
        "- Default flags remain `AGENT_ORCHESTRATOR_ENABLED=false`, "
        "`AGENT_ORCHESTRATOR_USE_LLM=false`.",
        "- No HF token / secrets printed.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


async def main_async() -> int:
    auth = await _probe_hf_auth()
    print("HF authentication:", auth.get("hf_authentication"))
    if auth.get("hf_authentication") != "OK":
        payload = {
            "status": "FAIL",
            "hf_auth": auth,
            "qwen_status": "FAIL",
            "quota": "UNKNOWN",
            "conclusion_text": "Validation impossible — HF authentication failed before the turn.",
            "turn": {},
            "answer_a": "NO",
            "answer_b": "NO",
            "answer_c": "NO",
            "answer_d": "NO",
            "answer_e": "n/a",
            "hf_calls_consumed": 0,
            "fallback_status": "n/a",
        }
        _write_report(payload)
        return 1

    proc = None
    try:
        print("Starting one canary server (ENABLED=true, USE_LLM=true)…")
        proc, log_path = _start()
        base = f"http://127.0.0.1:{PORT}"
        await _wait_ready(base)
        print("ONE voice turn — no retries…")
        turn = await run_one_voice_turn(base)
        print("turn valid=", turn.get("valid"), "402=", turn.get("stopped_on_402"))
        print("agents=", turn.get("agents_called"), "llm_calls=", turn.get("llm_calls"))
        print("hf_status=", turn.get("hf_http_status"), "ttfa=", turn.get("ttfa_ms"))

        agents = set(turn.get("agents_called") or [])
        llm_calls = turn.get("llm_calls")
        http_status = turn.get("hf_http_status")
        qwen_called = isinstance(llm_calls, int) and llm_calls >= 1
        qwen_ok = qwen_called and http_status == 200 and not turn.get("fallback_used")
        stopped_402 = bool(turn.get("stopped_on_402") or http_status == 402)

        if stopped_402:
            qwen_status = "402"
            quota = "EXHAUSTED" if http_status == 402 else "LIMITED"
            # Fallback: got assistant audio/text without crash?
            fallback_ok = bool(turn.get("valid")) and bool(
                turn.get("assistant_preview") or turn.get("first_audio_before_audio_done")
            )
            status = "PASS WITH QUOTA LIMIT"
            conclusion = (
                "Validation partielle : Qwen a retourné HTTP 402. "
                "Aucun retry. Fallback Agent 4 / chemin vocal "
                f"{'OK' if fallback_ok else 'FAIL'}."
            )
        elif not turn.get("valid"):
            qwen_status = "FAIL"
            quota = "UNKNOWN"
            fallback_ok = False
            status = "FAIL"
            conclusion = f"Turn failed: {turn.get('error')}"
        elif not ({"intent", "knowledge", "planner", "response"} <= agents):
            qwen_status = "PASS" if qwen_ok else "FAIL"
            quota = "OK" if http_status == 200 else "LIMITED"
            fallback_ok = bool(turn.get("fallback_used"))
            status = "FAIL"
            conclusion = f"Missing agents in pipeline: {sorted(agents)}"
        elif not qwen_ok:
            qwen_status = "FAIL"
            quota = "LIMITED" if http_status not in (200, None) else "OK"
            fallback_ok = bool(turn.get("fallback_used"))
            status = "FAIL"
            conclusion = "Agents ran but Qwen was not confirmed successful."
        else:
            qwen_status = "PASS"
            quota = "OK"
            fallback_ok = True  # not needed
            # TTFA vs ~1100ms baseline — flag only if grossly worse (>3s)
            ttfa = turn.get("ttfa_ms")
            regress = isinstance(ttfa, (int, float)) and ttfa > 3000
            status = "PASS WITH ISSUES" if regress else "PASS"
            conclusion = (
                "Chemin complet validé : Agent1→2→3→4→Qwen→TTS avec "
                f"TTFA={ttfa} ms, LLM calls={llm_calls}, "
                f"first audio before audio_done="
                f"{turn.get('first_audio_before_audio_done')}."
            )

        ttfa = turn.get("ttfa_ms")
        payload = {
            "phase": "2.5C",
            "status": status,
            "hf_auth": auth,
            "qwen_status": qwen_status,
            "quota": quota,
            "fallback_status": (
                "PASS"
                if stopped_402 and fallback_ok
                else ("PASS" if not stopped_402 and turn.get("valid") else "FAIL")
            ),
            "turn": turn,
            "log_path": str(log_path),
            "answer_a": "YES" if turn.get("valid") and {"intent", "response"} <= agents else "NO",
            "answer_b": "YES" if qwen_called else "NO",
            "answer_c": "YES" if turn.get("first_text_chunk_ms") is not None and turn.get("first_audio_before_audio_done") else "NO",
            "answer_d": "YES" if turn.get("first_audio_before_audio_done") else "NO",
            "answer_e": (
                "YES"
                if isinstance(ttfa, (int, float)) and ttfa > 3000
                else "NO"
            ),
            "hf_calls_consumed": 1 if qwen_called else 0,
            "conclusion_text": conclusion,
            "defaults_restored": {
                "AGENT_ORCHESTRATOR_ENABLED": False,
                "AGENT_ORCHESTRATOR_USE_LLM": False,
            },
        }
        _write_report(payload)
        print("Wrote", OUT_MD)
        print("STATUS:", status)
        return 0 if status in {"PASS", "PASS WITH ISSUES", "PASS WITH QUOTA LIMIT"} else 1
    finally:
        _stop(proc)


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
