"""Async voice turn over WebSocket — STT → route → RAG → stream LLM → stream TTS."""

from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_ai_service, get_speech_service
from app.services.ai.huggingface import HuggingFaceAIService
from app.services.metrics.latency import PhaseTimer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def _split_ready_sentences(buffer: str) -> tuple[list[str], str]:
    """Return complete sentences and the leftover incomplete tail.

    Phase 1: flush earlier so Fish TTS can start while the LLM still streams.
    - Prefer punctuation boundaries.
    - Else flush a clause once the buffer reaches ~90 chars (was 140).
    - Never emit fragments shorter than 28 chars (Fish quality floor).
    """
    parts = _SENTENCE_END.split(buffer)
    if len(parts) == 1:
        if len(buffer) >= 90 and (" " in buffer):
            cut = buffer.rfind(" ", 0, 85)
            if cut >= 28:
                return [buffer[:cut].strip()], buffer[cut:].lstrip()
        return [], buffer
    *complete, tail = parts
    ready = [p.strip() for p in complete if len(p.strip()) >= 28]
    leftover = " ".join(
        [*(p.strip() for p in complete if 0 < len(p.strip()) < 28), tail.strip()]
    ).strip()
    return ready, leftover


async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
    try:
        await ws.send_json(payload)
    except Exception:
        logger.debug("voice ws send failed", exc_info=True)


@router.websocket("/voice/session")
async def voice_session(websocket: WebSocket) -> None:
    await websocket.accept()
    await _send(
        websocket,
        {
            "type": "ready",
            "message": "Voice session ready",
            "events": [
                "ready",
                "status",
                "transcript",
                "route",
                "token",
                "assistant_text",
                "audio_chunk",
                "audio_done",
                "turn_done",
                "interrupted",
                "error",
            ],
        },
    )

    speech = get_speech_service()
    ai = get_ai_service()
    conversation_id: str | None = None
    turn_task: asyncio.Task | None = None
    interrupt_event = asyncio.Event()

    async def cancel_turn() -> None:
        nonlocal turn_task
        interrupt_event.set()
        if turn_task and not turn_task.done():
            turn_task.cancel()
            try:
                await turn_task
            except (asyncio.CancelledError, Exception):
                pass
        turn_task = None
        await _send(websocket, {"type": "interrupted"})

    async def run_turn(
        *,
        text: str | None = None,
        audio_b64: str | None = None,
        mime: str = "audio/m4a",
        locale: str = "fr",
        client_turn_id: str | None = None,
    ) -> None:
        nonlocal conversation_id
        interrupt_event.clear()
        timer = PhaseTimer("voice_ws")
        if client_turn_id:
            timer.turn_id = f"{client_turn_id[:8]}-{timer.turn_id}"
        marks: dict[str, float] = {"request_received": 0.0}
        wall0 = time.perf_counter()

        def mark(name: str) -> float:
            elapsed = round((time.perf_counter() - wall0) * 1000, 1)
            marks[name] = elapsed
            return elapsed

        await _send(websocket, {"type": "status", "phase": "starting", "turn_id": timer.turn_id})

        try:
            user_text = (text or "").strip()
            if audio_b64 and not user_text:
                await _send(websocket, {"type": "status", "phase": "transcribing"})
                mark("stt_start")
                with timer.phase("stt"):
                    audio_bytes = base64.b64decode(audio_b64)
                    mark("audio_decoded")
                    user_text, language = await speech.transcribe(
                        audio_bytes=audio_bytes,
                        mime_type=mime or "audio/m4a",
                    )
                mark("stt_end")
                await _send(
                    websocket,
                    {
                        "type": "transcript",
                        "text": user_text,
                        "language": language,
                        "latency_ms": timer.phases.get("stt"),
                        "turn_id": timer.turn_id,
                    },
                )

            if not user_text:
                await _send(
                    websocket,
                    {
                        "type": "error",
                        "code": "empty_transcript",
                        "message": "Aucune parole détectée."
                        if locale != "en"
                        else "No speech detected.",
                        "recoverable": True,
                        "turn_id": timer.turn_id,
                    },
                )
                return

            if interrupt_event.is_set():
                return

            await _send(websocket, {"type": "status", "phase": "thinking"})
            mark("llm_pipeline_start")

            if not isinstance(ai, HuggingFaceAIService):
                # Non-streaming backends: one-shot then TTS.
                with timer.phase("llm"):
                    response = await ai.generate_response(
                        user_text,
                        conversation_id,
                        brief=True,
                        locale=locale,
                    )
                conversation_id = response.conversation_id
                mark("llm_end")
                await _send(
                    websocket,
                    {
                        "type": "assistant_text",
                        "text": response.message,
                        "turn_id": timer.turn_id,
                    },
                )
                mark("tts_start")
                await _emit_tts(
                    websocket, speech, response.message, timer, interrupt_event, marks, wall0
                )
                mark("turn_end")
                _log_voice_perf(timer, marks)
                timer.log()
                await _send(
                    websocket,
                    {
                        "type": "turn_done",
                        "metrics": {**timer.as_dict(), "marks_ms": marks},
                        "conversation_id": conversation_id,
                        "turn_id": timer.turn_id,
                    },
                )
                return

            reply_parts: list[str] = []
            tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
            tts_task = asyncio.create_task(
                _tts_worker(
                    websocket, speech, tts_queue, timer, interrupt_event, marks, wall0
                )
            )
            sentence_buffer = ""
            first_token_marked = False
            first_tts_enqueue_marked = False

            try:
                async for event in ai.stream_response(
                    user_text,
                    conversation_id,
                    brief=True,
                    locale=locale,
                    timer=timer,
                ):
                    if interrupt_event.is_set():
                        break
                    etype = event.get("type")
                    if etype == "route":
                        mark("routing_end")
                        await _send(websocket, {**event, "turn_id": timer.turn_id})
                        await _send(
                            websocket,
                            {
                                "type": "status",
                                "phase": "retrieving" if not event.get("skip_kb") else "generating",
                                "turn_id": timer.turn_id,
                            },
                        )
                    elif etype == "token":
                        piece = str(event.get("text") or "")
                        if not first_token_marked:
                            mark("llm_first_token")
                            first_token_marked = True
                        reply_parts.append(piece)
                        sentence_buffer += piece
                        await _send(
                            websocket,
                            {"type": "token", "text": piece, "turn_id": timer.turn_id},
                        )
                        ready, sentence_buffer = _split_ready_sentences(sentence_buffer)
                        for sentence in ready:
                            if not first_tts_enqueue_marked:
                                mark("tts_first_fragment")
                                first_tts_enqueue_marked = True
                            await tts_queue.put(sentence)
                        await _send(
                            websocket,
                            {
                                "type": "status",
                                "phase": "generating",
                                "turn_id": timer.turn_id,
                            },
                        )
                    elif etype == "done":
                        mark("llm_end")
                        conversation_id = str(event.get("conversation_id") or conversation_id)
                        full = str(event.get("text") or "".join(reply_parts)).strip()
                        if sentence_buffer.strip():
                            if not first_tts_enqueue_marked:
                                mark("tts_first_fragment")
                                first_tts_enqueue_marked = True
                            await tts_queue.put(sentence_buffer.strip())
                            sentence_buffer = ""
                        await _send(
                            websocket,
                            {
                                "type": "assistant_text",
                                "text": full,
                                "turn_id": timer.turn_id,
                            },
                        )
                    elif etype == "error":
                        await _send(
                            websocket,
                            {
                                "type": "error",
                                "code": event.get("code") or "llm_error",
                                "message": event.get("message") or "LLM error",
                                "recoverable": True,
                                "turn_id": timer.turn_id,
                            },
                        )
                        break
            finally:
                await tts_queue.put(None)
                try:
                    await tts_task
                except Exception:
                    logger.exception("TTS worker failed")

            if interrupt_event.is_set():
                return

            mark("turn_end")
            _log_voice_perf(timer, marks)
            timer.log()
            await _send(
                websocket,
                {
                    "type": "turn_done",
                    "metrics": {**timer.as_dict(), "marks_ms": marks},
                    "conversation_id": conversation_id,
                    "turn_id": timer.turn_id,
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("voice turn failed")
            await _send(
                websocket,
                {
                    "type": "error",
                    "code": "turn_failed",
                    "message": str(exc) or "Voice turn failed",
                    "recoverable": True,
                    "turn_id": timer.turn_id,
                },
            )

    try:
        while True:
            message = await websocket.receive_json()
            mtype = str(message.get("type") or "")
            if mtype == "ping":
                await _send(websocket, {"type": "pong"})
                continue
            if mtype == "interrupt":
                await cancel_turn()
                continue
            if mtype in {"audio", "text", "utterance"}:
                await cancel_turn()
                interrupt_event.clear()

                async def _runner(payload: dict[str, Any] = message) -> None:
                    raw_locale = str(payload.get("locale") or "fr").lower()
                    turn_locale = "en" if raw_locale.startswith("en") else "fr"
                    await run_turn(
                        text=payload.get("text"),
                        audio_b64=payload.get("audio_base64") or payload.get("data"),
                        mime=str(payload.get("mime_type") or payload.get("mime") or "audio/m4a"),
                        locale=turn_locale,
                        client_turn_id=str(payload.get("turn_id") or "") or None,
                    )

                turn_task = asyncio.create_task(_runner())
                continue
            if mtype == "close":
                break
            await _send(
                websocket,
                {
                    "type": "error",
                    "code": "unknown_event",
                    "message": f"Unknown event type: {mtype}",
                    "recoverable": True,
                },
            )
    except WebSocketDisconnect:
        logger.info("voice ws disconnected")
    finally:
        await cancel_turn()



async def _tts_worker(
    websocket: WebSocket,
    speech: Any,
    queue: asyncio.Queue[str | None],
    timer: PhaseTimer,
    interrupt_event: asyncio.Event,
    marks: dict[str, float] | None = None,
    wall0: float | None = None,
) -> None:
    index = 0
    first = True
    marks = marks if marks is not None else {}
    wall0 = wall0 if wall0 is not None else time.perf_counter()

    def mark(name: str) -> None:
        marks[name] = round((time.perf_counter() - wall0) * 1000, 1)

    while True:
        sentence = await queue.get()
        if sentence is None:
            break
        if interrupt_event.is_set():
            break
        if first:
            mark("tts_start")
        await _send(websocket, {"type": "status", "phase": "speaking"})
        try:
            phase_name = "tts_first" if first else f"tts_{index}"
            begin = time.perf_counter()
            chunk_index = 0
            async for audio_chunk in speech.synthesize_stream(sentence):
                if interrupt_event.is_set():
                    break
                encoded = base64.b64encode(audio_chunk).decode("ascii")
                await _send(
                    websocket,
                    {
                        "type": "audio_chunk",
                        "format": "mp3",
                        "index": index,
                        "part": chunk_index,
                        "data": encoded,
                        "text": sentence if chunk_index == 0 else "",
                        "turn_id": timer.turn_id,
                    },
                )
                chunk_index += 1
                if first:
                    ttfb = (time.perf_counter() - begin) * 1000
                    timer.mark("tts_ttfb", ttfb)
                    timer.mark("first_audio", (time.perf_counter() - timer.started_at) * 1000)
                    mark("tts_first_byte")
                    mark("audio_first_chunk_sent")
                    first = False
            elapsed = (time.perf_counter() - begin) * 1000
            timer.mark(phase_name, elapsed)
            await _send(
                websocket,
                {"type": "audio_done", "index": index, "turn_id": timer.turn_id},
            )
            index += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("TTS stream failed")
            await _send(
                websocket,
                {
                    "type": "error",
                    "code": "tts_failed",
                    "message": str(exc) or "TTS failed",
                    "recoverable": True,
                    "turn_id": timer.turn_id,
                },
            )
    mark("tts_end")


async def _emit_tts(
    websocket: WebSocket,
    speech: Any,
    text: str,
    timer: PhaseTimer,
    interrupt_event: asyncio.Event,
    marks: dict[str, float] | None = None,
    wall0: float | None = None,
) -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    parts = [p.strip() for p in _SENTENCE_END.split(text) if p.strip()] or [text]
    for part in parts:
        await queue.put(part)
    await queue.put(None)
    await _tts_worker(
        websocket, speech, queue, timer, interrupt_event, marks, wall0
    )


def _log_voice_perf(timer: PhaseTimer, marks: dict[str, float]) -> None:
    """Emit a dedicated [VOICE PERF] chronology for Phase 1.1 diagnostics."""
    phases = timer.phases
    lines = [
        f"[VOICE PERF] turn={timer.turn_id}",
        *[f"[VOICE PERF] {name} = {ms:.1f} ms" for name, ms in marks.items()],
        f"[VOICE PERF] STT        {phases.get('stt', 0):.0f} ms",
        f"[VOICE PERF] ROUTING    {phases.get('routing', 0):.0f} ms",
        f"[VOICE PERF] RAG        {phases.get('rag', 0):.0f} ms",
        f"[VOICE PERF] GROUNDING  {phases.get('grounding', 0):.0f} ms",
        f"[VOICE PERF] LLM TTFT   {phases.get('llm_ttft', 0):.0f} ms",
        f"[VOICE PERF] LLM TOTAL  {phases.get('llm', 0):.0f} ms",
        f"[VOICE PERF] TTS TTFB   {phases.get('tts_ttfb', 0):.0f} ms",
        f"[VOICE PERF] TTS FIRST  {phases.get('tts_first', 0):.0f} ms",
        f"[VOICE PERF] FIRST AUDIO {phases.get('first_audio', marks.get('audio_first_chunk_sent', 0)):.0f} ms",
        f"[VOICE PERF] TOTAL      {timer.total_ms:.0f} ms",
    ]
    for line in lines:
        logger.info("%s", line)
