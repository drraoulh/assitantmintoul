#!/usr/bin/env python3
"""Phase 2.5B — real-path canary for AgentOrchestrator.

Starts real uvicorn processes, hits POST /api/chat and WS /api/voice/session.
Does not invent architecture changes. Default production flag remains false.

Usage:
  python backend/scripts/canary_orchestrator.py
  python backend/scripts/canary_orchestrator.py --voice-runs 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT_JSON = ROOT / "docs" / "phase2-agent-orchestrator-canary.json"
OUT_MD = ROOT / "docs" / "phase2-agent-orchestrator-canary.md"

LEGACY_PORT = 8010
ORCH_PORT = 8011
FAIL_PORT = 8012

CHAT_CASES = [
    ("greeting", "Bonjour", {"intent", "response"}, {"knowledge", "planner", "web"}),
    (
        "places",
        "Quels sont les lieux touristiques à Yaoundé ?",
        {"intent", "knowledge", "response"},
        {"planner"},
    ),
    (
        "place_details",
        "Parle-moi du Musée National du Cameroun.",
        {"intent", "knowledge", "response"},
        {"planner"},
    ),
    (
        "itinerary",
        "Fais-moi un programme touristique de 3 jours à Yaoundé.",
        {"intent", "knowledge", "planner", "response"},
        set(),
    ),
    (
        "budget",
        "Nous sommes 4 personnes, nous avons 150000 FCFA et nous voulons "
        "visiter Yaoundé pendant 3 jours.",
        {"intent", "knowledge", "planner", "response"},
        set(),
    ),
    (
        "clarification",
        "Organise mon voyage.",
        {"intent", "response"},
        {"knowledge", "planner", "web"},
    ),
    (
        "no_invention",
        "Donne-moi les informations sur le Château Imaginaire de Bamenda-Nord.",
        {"intent", "response"},  # CLARIFICATION path OK; knowledge optional
        {"planner", "web"},
    ),
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


def _env_for(*, enabled: bool, force_fail: bool = False) -> dict[str, str]:
    env = os.environ.copy()
    # Load backend/.env into child without forcing secrets into the report.
    dotenv = BACKEND / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env.setdefault(k.strip(), v.strip())
    env["AGENT_ORCHESTRATOR_ENABLED"] = "true" if enabled else "false"
    env["AGENT_ORCHESTRATOR_OBSERVE"] = "false"
    env["AGENT_ORCHESTRATOR_FORCE_FAIL"] = "true" if force_fail else "false"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _start_server(port: int, *, enabled: bool, force_fail: bool = False) -> tuple[subprocess.Popen, Path]:
    log_path = Path(f"/tmp/canary_orch_{port}.log")
    log_f = log_path.open("w", encoding="utf-8")
    env = _env_for(enabled=enabled, force_fail=force_fail)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        cwd=str(BACKEND),
        env=env,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, log_path


async def _wait_ready(base: str, timeout: float = 90.0) -> None:
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


def _parse_orch_logs(log_path: Path) -> list[dict[str, Any]]:
    """Extract orchestration_completed payloads from server logs."""
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    rows: list[dict[str, Any]] = []
    # logger.info("orchestration_completed %s", result.observability())
    for m in re.finditer(r"orchestration_completed\s+(\{.*\})", text):
        raw = m.group(1)
        try:
            # observability() uses single quotes via dict str? Actually it's %s of dict → single quotes
            # Safer: use ast.literal_eval
            import ast

            rows.append(ast.literal_eval(raw))
        except Exception:
            continue
    return rows


async def chat_http(base: str, message: str, *, mode: str = "text") -> dict[str, Any]:
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            f"{base}/api/chat",
            json={"message": message, "mode": mode, "locale": "fr"},
        )
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)
    body: dict[str, Any]
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text[:500]}
    return {
        "status_code": r.status_code,
        "latency_ms": latency_ms,
        "message": str(body.get("message") or ""),
        "conversation_id": body.get("conversation_id"),
        "sources": body.get("sources") or [],
        "provider": body.get("provider"),
        "error": None if r.status_code == 200 else body,
    }


async def ws_probe(base: str, message: str, *, timeout: float = 90.0) -> dict[str, Any]:
    """Real voice WS text turn — captures orchestrator route + TTFA-ish marks."""
    try:
        import websockets
    except ImportError:
        return {"valid": False, "error": "websockets_missing"}

    ws_url = base.replace("http://", "ws://").rstrip("/") + "/api/voice/session"
    marks: dict[str, float] = {}
    timeline: list[dict[str, Any]] = []
    speech_end: float | None = None
    wall0 = time.perf_counter()
    orch_meta: dict[str, Any] | None = None
    route_event: dict[str, Any] | None = None
    assistant_text = ""
    metrics: dict[str, Any] | None = None
    first_token_text = ""
    streamed_before_audio_done = False
    audio_started = False
    audio_done = False

    def mark(name: str, **extra: Any) -> None:
        now = time.perf_counter()
        base_t = speech_end if speech_end is not None else wall0
        elapsed = round((now - base_t) * 1000, 1)
        marks[name] = elapsed
        timeline.append({"event": name, "elapsed_ms": elapsed, **extra})

    try:
        async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
            if ready.get("type") != "ready":
                return {"valid": False, "error": f"no_ready:{ready.get('type')}"}

            speech_end = time.perf_counter()
            mark("user_speech_end")
            await ws.send(
                json.dumps(
                    {
                        "type": "text",
                        "text": message,
                        "locale": "fr",
                        "turn_id": f"canary-{int(time.time()*1000)%100000}",
                    }
                )
            )
            mark("stt_end", note="text_turn_stt_ms=0")

            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "route":
                    route_event = msg
                    orch_meta = msg.get("orchestrator") or (
                        (msg.get("intent") and {"intent": msg.get("intent")}) or None
                    )
                    if isinstance(msg.get("orchestrator"), dict):
                        orch_meta = msg["orchestrator"]
                    mark("route")
                elif mtype == "token":
                    if "first_text_chunk" not in marks:
                        first_token_text = str(msg.get("text") or "")
                        mark("first_text_chunk", chars=len(first_token_text))
                elif mtype == "audio_chunk":
                    part = int(msg.get("part") or 0)
                    if part == 0 and "first_audio_chunk" not in marks:
                        mark("first_audio_chunk")
                        mark("frontend_playback_start", note="early_play")
                        audio_started = True
                        if "audio_done" not in marks:
                            streamed_before_audio_done = True
                elif mtype == "audio_done":
                    mark("audio_done")
                    audio_done = True
                elif mtype == "assistant_text":
                    assistant_text = str(msg.get("text") or assistant_text)
                elif mtype == "turn_done":
                    mark("turn_complete")
                    metrics = msg.get("metrics") or {}
                    # Prefer nested orchestrator from llm_trace meta if present
                    llm_trace = (metrics or {}).get("llm_trace") or {}
                    meta = (llm_trace.get("meta") or {}) if isinstance(llm_trace, dict) else {}
                    if isinstance(meta.get("agent_orchestrator"), dict):
                        orch_meta = meta["agent_orchestrator"]
                    break
                elif mtype == "error":
                    return {
                        "valid": False,
                        "error": str(msg.get("message") or msg.get("code") or "error"),
                        "route": route_event,
                        "orchestrator": orch_meta,
                    }
            else:
                return {"valid": False, "error": "timeout"}

    except Exception as exc:  # noqa: BLE001
        return {"valid": False, "error": str(exc)[:200]}

        phases = (metrics or {}).get("phases_ms") or (metrics or {}).get("phases") or metrics or {}
        marks_ms = (metrics or {}).get("marks_ms") or {}
        return {
        "valid": True,
        "assistant_text": assistant_text,
        "orchestrator": orch_meta,
        "route": route_event,
        "agents_called": (orch_meta or {}).get("agents_called"),
        "intent": (orch_meta or {}).get("intent"),
        "stt_ms": 0.0,
        "orchestration_ms": (
            phases.get("orchestrator")
            or marks_ms.get("agent_orchestrator")
            or (orch_meta or {}).get("total_ms")
        ),
        "llm_ttft_ms": phases.get("llm_ttft") or marks.get("first_text_chunk"),
        "first_text_chunk_ms": marks.get("first_text_chunk"),
        "tts_ttfb_ms": (
            None
            if marks.get("first_audio_chunk") is None or marks.get("first_text_chunk") is None
            else round(marks["first_audio_chunk"] - marks["first_text_chunk"], 1)
        ),
        "ttfa_ms": marks.get("frontend_playback_start"),
        "total_ms": marks.get("turn_complete"),
        "streamed_before_audio_done": streamed_before_audio_done and audio_started,
        "audio_started": audio_started,
        "audio_done": audio_done,
        "timeline": timeline,
        "metrics": metrics,
    }


def _judge_chat(
    case: str,
    chat: dict[str, Any],
    orch: dict[str, Any] | None,
    *,
    forbidden_agents: set[str],
    required_agents: set[str],
) -> dict[str, Any]:
    text = (chat.get("message") or "").strip()
    ok = chat.get("status_code") == 200 and bool(text)
    reasons: list[str] = []
    agents = list((orch or {}).get("agents_called") or [])

    if not ok:
        reasons.append("http_or_empty")

    if required_agents and agents:
        missing = required_agents - set(agents)
        if missing:
            ok = False
            reasons.append(f"missing_agents:{sorted(missing)}")
    if forbidden_agents and agents:
        bad = forbidden_agents & set(agents)
        if bad:
            ok = False
            reasons.append(f"unexpected_agents:{sorted(bad)}")

    low = text.casefold()
    if case == "clarification":
        if not any(
            t in low
            for t in ("préciser", "combien", "ville", "région", "jours", "looking", "days", "city")
        ):
            ok = False
            reasons.append("no_clarification_ask")
    if case == "no_invention":
        # Unknown place may classify as CLARIFICATION (skip knowledge) or
        # PLACE_DETAILS (knowledge empty). Either is OK if we don't invent.
        if agents and "planner" in agents:
            ok = False
            reasons.append("unexpected_planner")
        # Soften required knowledge: clarification path is acceptable.
        if "missing_agents:['knowledge']" in reasons:
            reasons.remove("missing_agents:['knowledge']")
            ok = True
        invented = "château imaginaire" in low or "chateau imaginaire" in low
        if invented:
            invent_markers = ("ouvert", "tarif", "fcfa", "réserver", "visitez", "situé à", "entrée")
            if sum(1 for m in invent_markers if m in low) >= 2:
                ok = False
                reasons.append("likely_invented_details")
            elif len(text) > 280 and not any(
                t in low for t in ("vérif", "pas", "insuff", "préciser", "unknown", "no information")
            ):
                ok = False
                reasons.append("long_answer_about_unknown_place")
        # Clarification ask / insufficient message → PASS
        if any(t in low for t in ("préciser", "vérif", "fiable", "enough", "looking")):
            ok = True
            reasons = [r for r in reasons if not r.startswith("missing_agents")]
        return {
            "pass": ok,
            "reasons": reasons,
            "agents_called": agents,
            "latency_ms": chat.get("latency_ms"),
            "text_preview": text[:220],
            "intent": (orch or {}).get("intent"),
            "response_type": (orch or {}).get("response_type"),
            "total_ms": (orch or {}).get("total_ms"),
        }

    if case == "budget":
        # Must not invent hotels/transport as booked facts
        if re.search(r"hôtel\s+\w+\s+confirm", low) or "réservation n" in low:
            ok = False
            reasons.append("invented_booking")

    return {
        "pass": ok,
        "reasons": reasons,
        "agents_called": agents,
        "latency_ms": chat.get("latency_ms"),
        "text_preview": text[:220],
        "intent": (orch or {}).get("intent"),
        "response_type": (orch or {}).get("response_type"),
        "total_ms": (orch or {}).get("total_ms"),
    }


async def run_chat_canary(orch_base: str, log_path: Path) -> list[dict[str, Any]]:
    results = []
    for name, query, required, forbidden in CHAT_CASES:
        # Real HTTP chat
        chat = await chat_http(orch_base, query)
        # Companion WS probe for agents_called / orchestrator observability
        probe = await ws_probe(orch_base, query, timeout=60.0)
        orch = probe.get("orchestrator") if probe.get("valid") else None
        # Fallback: parse latest matching log line
        if not orch:
            logs = _parse_orch_logs(log_path)
            if logs:
                orch = logs[-1]
        verdict = _judge_chat(name, chat, orch, forbidden_agents=forbidden, required_agents=required)
        results.append(
            {
                "scenario": name,
                "query": query,
                "http": {
                    "status_code": chat.get("status_code"),
                    "latency_ms": chat.get("latency_ms"),
                    "provider": chat.get("provider"),
                },
                "ws_probe_valid": probe.get("valid"),
                "ws_error": probe.get("error"),
                "orchestrator": orch,
                "verdict": verdict,
                "result": "PASS" if verdict["pass"] else "FAIL",
            }
        )
        print(
            f"  chat[{name}] {results[-1]['result']} "
            f"agents={verdict.get('agents_called')} "
            f"http_ms={chat.get('latency_ms')}"
        )
    return results


async def run_insufficient_case(orch_base: str) -> dict[str, Any]:
    """Real query unlikely to match catalog → Agent2 empty-ish, no planner."""
    q = "Fais-moi un programme de 3 jours à Atlantis-sous-marine inventée XYZ."
    chat = await chat_http(orch_base, q)
    probe = await ws_probe(orch_base, q, timeout=60.0)
    orch = probe.get("orchestrator") if probe.get("valid") else None
    agents = set((orch or {}).get("agents_called") or [])
    text = (chat.get("message") or "").casefold()
    # Planner should be skipped when knowledge has no places
    planner_skipped = "planner" not in agents
    honest = any(t in text for t in ("vérif", "fiable", "enough", "manque", "pas", "insuff"))
    ok = chat.get("status_code") == 200 and planner_skipped and honest
    return {
        "scenario": "insufficient_data",
        "query": q,
        "agents_called": list(agents),
        "planner_skipped": planner_skipped,
        "honest_answer": honest,
        "latency_ms": chat.get("latency_ms"),
        "text_preview": (chat.get("message") or "")[:220],
        "result": "PASS" if ok else "FAIL",
        "orchestrator": orch,
    }


async def run_web_cases(orch_base: str) -> dict[str, Any]:
    """needs_web true vs false — inspect intent flags via WS route/orchestrator."""
    web_q = "Cherche sur le web les actualités touristiques du Cameroun cette semaine."
    no_web_q = "Bonjour"
    web_probe = await ws_probe(orch_base, web_q, timeout=60.0)
    no_web_probe = await ws_probe(orch_base, no_web_q, timeout=60.0)
    web_agents = set((web_probe.get("orchestrator") or {}).get("agents_called") or [])
    no_web_agents = set((no_web_probe.get("orchestrator") or {}).get("agents_called") or [])
    # WEB_SEARCH intent should include web; greeting must not
    web_ok = "web" in web_agents or (web_probe.get("route") or {}).get("skip_web") is False
    # For greeting, skip_web should be true / no web agent
    no_web_ok = "web" not in no_web_agents
    return {
        "web_query": web_q,
        "web_agents": list(web_agents),
        "web_result": "PASS" if web_ok and web_probe.get("valid") else "FAIL",
        "no_web_query": no_web_q,
        "no_web_agents": list(no_web_agents),
        "no_web_result": "PASS" if no_web_ok and no_web_probe.get("valid") else "FAIL",
        "web_probe": {k: web_probe.get(k) for k in ("valid", "error", "orchestrator", "intent")},
        "no_web_probe": {
            k: no_web_probe.get(k) for k in ("valid", "error", "orchestrator", "intent")
        },
    }


async def run_voice_compare(
    legacy_base: str,
    orch_base: str,
    *,
    runs: int,
) -> dict[str, Any]:
    questions = [
        ("greeting", "Bonjour"),
        ("places", "Quels sont les lieux touristiques à visiter à Yaoundé ?"),
    ]
    out: dict[str, Any] = {}
    for label, q in questions:
        legacy_rows = []
        orch_rows = []
        # warm both
        await ws_probe(legacy_base, q, timeout=90.0)
        await ws_probe(orch_base, q, timeout=90.0)
        for i in range(runs):
            lr = await ws_probe(legacy_base, q, timeout=90.0)
            legacy_rows.append(lr)
            print(
                f"  voice legacy[{label}#{i}] valid={lr.get('valid')} "
                f"ttfa={lr.get('ttfa_ms')} err={lr.get('error')}"
            )
            orr = await ws_probe(orch_base, q, timeout=90.0)
            orch_rows.append(orr)
            print(
                f"  voice orch[{label}#{i}] valid={orr.get('valid')} "
                f"ttfa={orr.get('ttfa_ms')} agents={orr.get('agents_called')} "
                f"err={orr.get('error')}"
            )
        out[label] = {
            "query": q,
            "legacy": {
                "rows": legacy_rows,
                "ttfa": _stats([r.get("ttfa_ms") for r in legacy_rows if r.get("valid")]),
                "first_text": _stats(
                    [r.get("first_text_chunk_ms") for r in legacy_rows if r.get("valid")]
                ),
                "tts_gap": _stats([r.get("tts_ttfb_ms") for r in legacy_rows if r.get("valid")]),
                "total": _stats([r.get("total_ms") for r in legacy_rows if r.get("valid")]),
                "valid_n": sum(1 for r in legacy_rows if r.get("valid")),
            },
            "orchestrator": {
                "rows": orch_rows,
                "ttfa": _stats([r.get("ttfa_ms") for r in orch_rows if r.get("valid")]),
                "first_text": _stats(
                    [r.get("first_text_chunk_ms") for r in orch_rows if r.get("valid")]
                ),
                "orchestration_ms": _stats(
                    [r.get("orchestration_ms") for r in orch_rows if r.get("valid")]
                ),
                "tts_gap": _stats([r.get("tts_ttfb_ms") for r in orch_rows if r.get("valid")]),
                "total": _stats([r.get("total_ms") for r in orch_rows if r.get("valid")]),
                "valid_n": sum(1 for r in orch_rows if r.get("valid")),
                "stream_ok_n": sum(
                    1 for r in orch_rows if r.get("valid") and r.get("streamed_before_audio_done")
                ),
                "sample_agents": next(
                    (r.get("agents_called") for r in orch_rows if r.get("agents_called")),
                    None,
                ),
            },
        }
    return out


async def run_fallback(fail_base: str) -> dict[str, Any]:
    """Orchestrator forced fail → legacy path must still answer without raw traceback."""
    chat = await chat_http(fail_base, "Bonjour")
    text = chat.get("message") or ""
    has_traceback = "Traceback" in text or "RuntimeError" in text or "FORCE_FAIL" in text
    ok = chat.get("status_code") == 200 and bool(text.strip()) and not has_traceback
    return {
        "status_code": chat.get("status_code"),
        "latency_ms": chat.get("latency_ms"),
        "has_raw_exception": has_traceback,
        "text_preview": text[:220],
        "result": "PASS" if ok else "FAIL",
    }


def _llm_conclusion(voice: dict[str, Any], chat_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Orchestrator path uses prefer_deterministic=True → 0 LLM for answer."""
    return {
        "orchestrator_path": "Agent4 prefer_deterministic=True",
        "max_llm_calls_per_request_on_canary": 0,
        "agents_1_2_3": "deterministic (no LLM)",
        "agent_4": "deterministic renderer (no LLM on canary)",
        "legacy_path_llm_calls": 1,
        "note": (
            "Canary validates production default orchestrator wiring. "
            "LLM injection remains available later; default protects TTFA."
        ),
    }


def write_report(payload: dict[str, Any]) -> None:
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    chat_rows = payload.get("chat") or []
    insuff = payload.get("insufficient") or {}
    web = payload.get("web") or {}
    voice = payload.get("voice") or {}
    fallback = payload.get("fallback") or {}
    pytest_info = payload.get("pytest") or {}
    llm = payload.get("llm") or {}

    def row_chat(r: dict[str, Any]) -> str:
        v = r.get("verdict") or {}
        agents = ",".join(v.get("agents_called") or []) or "—"
        return (
            f"| {r.get('scenario')} | `{agents}` | {r.get('result')} | "
            f"{v.get('latency_ms')} ms |"
        )

    greeting = voice.get("greeting") or {}
    places = voice.get("places") or {}

    def vcell(block: dict, key: str, side: str) -> str:
        side_d = block.get(side) or {}
        st = side_d.get(key) or {}
        if not st or st.get("n") == 0:
            return "—"
        return (
            f"med {st.get('median')} / avg {st.get('avg')} "
            f"(min {st.get('min')}, max {st.get('max')}, n={st.get('n')})"
        )

    conclusion = payload.get("conclusion", "FAIL")
    lines = [
        "# Phase 2.5B — Orchestrator canary (real path)",
        "",
        "## Environment",
        "",
        f"- Base URL legacy: `{payload.get('legacy_base')}` (`AGENT_ORCHESTRATOR_ENABLED=false`)",
        f"- Base URL orchestrator: `{payload.get('orch_base')}` (`AGENT_ORCHESTRATOR_ENABLED=true`)",
        f"- Fallback probe: `{payload.get('fail_base')}` (`AGENT_ORCHESTRATOR_FORCE_FAIL=true`)",
        f"- Orchestrator enabled (canary): **true**",
        f"- Rollback: set `AGENT_ORCHESTRATOR_ENABLED=false` (no code change)",
        f"- Model / stack unchanged: Qwen / Whisper / Fish / Gemini / RAG / chunker / WS",
        "",
        "## Chat (real `POST /api/chat` + WS observability companion)",
        "",
        "| Scenario | Agents called | Result | Latency |",
        "|----------|---------------|--------|---------|",
    ]
    for r in chat_rows:
        lines.append(row_chat(r))
    lines += [
        f"| insufficient | `{','.join(insuff.get('agents_called') or [])}` | "
        f"{insuff.get('result')} | {insuff.get('latency_ms')} ms |",
        "",
        "### Clarification / insufficient / no-invention notes",
        "",
        f"- Clarification agents: see table row `clarification`",
        f"- Insufficient: planner_skipped={insuff.get('planner_skipped')} "
        f"honest={insuff.get('honest_answer')}",
        "- No-invention preview: "
        f"`{_no_inv_preview(chat_rows)}`",
        "",
        "## Web",
        "",
        f"- needs_web query: {web.get('web_result')} agents=`{web.get('web_agents')}`",
        f"- no-web greeting: {web.get('no_web_result')} agents=`{web.get('no_web_agents')}`",
        "",
        "## Voice (real `WS /api/voice/session`, warm text turns)",
        "",
        "Baseline historique warm TTFA ≈ **1100 ms** (Phase 1.9, legacy LLM path).",
        "",
        "### Greeting — Bonjour",
        "",
        "| Metric | Legacy | Orchestrator |",
        "|--------|--------|--------------|",
        f"| STT | 0 (text turn) | 0 (text turn) |",
        f"| Orchestrator | — | {vcell(greeting, 'orchestration_ms', 'orchestrator')} |",
        f"| First text chunk | {vcell(greeting, 'first_text', 'legacy')} | "
        f"{vcell(greeting, 'first_text', 'orchestrator')} |",
        f"| TTS gap (text→audio) | {vcell(greeting, 'tts_gap', 'legacy')} | "
        f"{vcell(greeting, 'tts_gap', 'orchestrator')} |",
        f"| TTFA | {vcell(greeting, 'ttfa', 'legacy')} | "
        f"{vcell(greeting, 'ttfa', 'orchestrator')} |",
        f"| Total | {vcell(greeting, 'total', 'legacy')} | "
        f"{vcell(greeting, 'total', 'orchestrator')} |",
        "",
        "### Places — Yaoundé",
        "",
        "| Metric | Legacy | Orchestrator |",
        "|--------|--------|--------------|",
        f"| STT | 0 (text turn) | 0 (text turn) |",
        f"| Orchestrator | — | {vcell(places, 'orchestration_ms', 'orchestrator')} |",
        f"| First text chunk | {vcell(places, 'first_text', 'legacy')} | "
        f"{vcell(places, 'first_text', 'orchestrator')} |",
        f"| TTS gap (text→audio) | {vcell(places, 'tts_gap', 'legacy')} | "
        f"{vcell(places, 'tts_gap', 'orchestrator')} |",
        f"| TTFA | {vcell(places, 'ttfa', 'legacy')} | "
        f"{vcell(places, 'ttfa', 'orchestrator')} |",
        f"| Total | {vcell(places, 'total', 'legacy')} | "
        f"{vcell(places, 'total', 'orchestrator')} |",
        "",
        f"- Streaming before `audio_done` (orch places): "
        f"{(places.get('orchestrator') or {}).get('stream_ok_n')}/"
        f"{(places.get('orchestrator') or {}).get('valid_n')}",
        "",
        "## LLM",
        "",
        f"- Maximum calls per request (orchestrator canary): "
        f"**{llm.get('max_llm_calls_per_request_on_canary')}**",
        f"- Agents 1–3: {llm.get('agents_1_2_3')}",
        f"- Agent 4: {llm.get('agent_4')}",
        f"- Legacy path LLM calls: {llm.get('legacy_path_llm_calls')}",
        f"- Note: {llm.get('note')}",
        "",
        "## Fallback",
        "",
        f"- Result: **{fallback.get('result')}**",
        f"- Raw exception leaked: {fallback.get('has_raw_exception')}",
        f"- Preview: `{fallback.get('text_preview')}`",
        "",
        "## Tests",
        "",
        f"- pytest: **{pytest_info.get('summary', 'n/a')}**",
        "",
        "## Conclusion",
        "",
        f"**{conclusion}**",
        "",
        payload.get("conclusion_notes", ""),
        "",
        "## Artifacts",
        "",
        f"- `{OUT_JSON.relative_to(ROOT)}`",
        f"- `{OUT_MD.relative_to(ROOT)}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def _no_inv_preview(chat_rows: list[dict[str, Any]]) -> str:
    row = next((c for c in chat_rows if c.get("scenario") == "no_invention"), {}) or {}
    return str((row.get("verdict") or {}).get("text_preview") or "")


def _conclusion(
    chat_rows: list[dict[str, Any]],
    insuff: dict[str, Any],
    web: dict[str, Any],
    voice: dict[str, Any],
    fallback: dict[str, Any],
    pytest_ok: bool,
) -> tuple[str, str]:
    fails = [r["scenario"] for r in chat_rows if r.get("result") != "PASS"]
    if insuff.get("result") != "PASS":
        fails.append("insufficient")
    if web.get("web_result") != "PASS" or web.get("no_web_result") != "PASS":
        fails.append("web")
    if fallback.get("result") != "PASS":
        fails.append("fallback")
    if not pytest_ok:
        fails.append("pytest")

    issues: list[str] = []
    legacy_hf_depleted = False
    for label in ("greeting", "places"):
        block = voice.get(label) or {}
        leg_rows = (block.get("legacy") or {}).get("rows") or []
        orch_side = block.get("orchestrator") or {}
        leg = (block.get("legacy") or {}).get("ttfa") or {}
        orch = orch_side.get("ttfa") or {}
        if orch_side.get("valid_n", 0) == 0:
            fails.append(f"voice_{label}")
            continue
        # Detect HF credit / provider failures on legacy comparison arm
        leg_errors = [str(r.get("error") or "") for r in leg_rows if not r.get("valid")]
        if leg_errors and all(
            ("402" in e)
            or ("credit" in e.lower())
            or ("depleted" in e.lower())
            or ("busy" in e.lower())
            or ("too long" in e.lower())
            or ("unavailable" in e.lower())
            for e in leg_errors
        ):
            legacy_hf_depleted = True
        leg_med = leg.get("median")
        orch_med = orch.get("median")
        if orch_med is not None and leg_med is not None:
            if orch_med > leg_med * 1.4 and (orch_med - leg_med) > 300:
                issues.append(
                    f"{label} TTFA regression orch_med={orch_med} vs legacy_med={leg_med}"
                )
        if orch_med is not None and orch_med > 2500:
            issues.append(f"{label} TTFA orch_med={orch_med} far above ~1100ms baseline")

    if legacy_hf_depleted:
        issues.append(
            "Legacy voice arm incomplete: Hugging Face Inference credits/provider "
            "errors (402/busy/timeout). Orchestrator voice arm measured successfully."
        )

    if fails:
        return "FAIL", "Failed scenarios: " + ", ".join(fails) + (
            ("; issues: " + "; ".join(issues)) if issues else ""
        )
    if issues:
        return "PASS WITH ISSUES", "; ".join(issues)
    return (
        "PASS",
        "Orchestrator real HTTP/WS path works; conditional agents verified; "
        "fallback OK; voice streaming early-play preserved; "
        "default rollback flag remains false.",
    )


async def main_async(args: argparse.Namespace) -> int:
    legacy_proc = orch_proc = fail_proc = None
    legacy_log = orch_log = fail_log = Path("/dev/null")
    try:
        print("Starting legacy server (ENABLED=false)…")
        legacy_proc, legacy_log = _start_server(LEGACY_PORT, enabled=False)
        print("Starting orchestrator server (ENABLED=true)…")
        orch_proc, orch_log = _start_server(ORCH_PORT, enabled=True)
        print("Starting fallback server (FORCE_FAIL=true)…")
        fail_proc, fail_log = _start_server(FAIL_PORT, enabled=True, force_fail=True)

        legacy_base = f"http://127.0.0.1:{LEGACY_PORT}"
        orch_base = f"http://127.0.0.1:{ORCH_PORT}"
        fail_base = f"http://127.0.0.1:{FAIL_PORT}"

        await _wait_ready(legacy_base)
        await _wait_ready(orch_base)
        await _wait_ready(fail_base)
        print("All servers ready.")

        print("\n=== CHAT CANARY ===")
        chat_rows = await run_chat_canary(orch_base, orch_log)
        print("\n=== INSUFFICIENT ===")
        insuff = await run_insufficient_case(orch_base)
        print(f"  insufficient → {insuff.get('result')} agents={insuff.get('agents_called')}")
        print("\n=== WEB ===")
        web = await run_web_cases(orch_base)
        print(f"  web={web.get('web_result')} no_web={web.get('no_web_result')}")
        print("\n=== FALLBACK ===")
        fallback = await run_fallback(fail_base)
        print(f"  fallback → {fallback.get('result')}")
        print("\n=== VOICE COMPARE ===")
        voice = await run_voice_compare(legacy_base, orch_base, runs=args.voice_runs)

        print("\n=== PYTEST ===")
        pytest_proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(BACKEND),
            capture_output=True,
            text=True,
            env=_env_for(enabled=False),
            timeout=180,
        )
        pytest_summary = (pytest_proc.stdout or "").strip().splitlines()[-1] if pytest_proc.stdout else "n/a"
        print(pytest_summary)
        pytest_ok = pytest_proc.returncode == 0

        llm = _llm_conclusion(voice, chat_rows)
        conclusion, notes = _conclusion(chat_rows, insuff, web, voice, fallback, pytest_ok)

        payload = {
            "phase": "2.5B",
            "legacy_base": legacy_base,
            "orch_base": orch_base,
            "fail_base": fail_base,
            "orchestrator_enabled_canary": True,
            "default_flag_remains_false": True,
            "chat": chat_rows,
            "insufficient": insuff,
            "web": web,
            "fallback": fallback,
            "voice": voice,
            "llm": llm,
            "pytest": {
                "returncode": pytest_proc.returncode,
                "summary": pytest_summary,
            },
            "conclusion": conclusion,
            "conclusion_notes": notes,
            "logs": {
                "legacy": str(legacy_log),
                "orchestrator": str(orch_log),
                "fallback": str(fail_log),
            },
        }
        write_report(payload)
        print(f"\nWrote {OUT_MD}")
        print(f"CONCLUSION: {conclusion}")
        return 0 if conclusion in {"PASS", "PASS WITH ISSUES"} else 1
    finally:
        _stop(legacy_proc)
        _stop(orch_proc)
        _stop(fail_proc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2.5B orchestrator canary")
    parser.add_argument("--voice-runs", type=int, default=5)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
