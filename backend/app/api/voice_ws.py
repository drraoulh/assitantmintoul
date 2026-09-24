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
from app.services.metrics.llm_stream_trace import LlmStreamTrace
from app.services.metrics.ttfa_trace import TurnChronology

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")


def _split_ready_sentences(
    buffer: str,
    *,
    first_chunk: bool = False,
) -> tuple[list[str], str]:
    """Delegate to Phase 1.2 voice_chunker (early first-phrase flush)."""
    from app.services.speech.voice_chunker import split_ready_phrases

    return split_ready_phrases(buffer, first_chunk=first_chunk)


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

    async def cancel_turn(*, notify: bool = True) -> None:
        """Cancel the in-flight turn.

        Only emit ``interrupted`` when a turn was actually running. Emitting on
        every new utterance (including the first) made the client void its
        stream-idle waiter and cut early-play audio mid-sentence.
        """
        nonlocal turn_task
        interrupt_event.set()
        had_running = turn_task is not None and not turn_task.done()
        if had_running:
            turn_task.cancel()
            try:
                await turn_task
            except (asyncio.CancelledError, Exception):
                pass
        turn_task = None
        if notify and had_running:
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
        chrono = TurnChronology(turn_id=timer.turn_id)
        marks: dict[str, float] = {"request_received": 0.0}
        wall0 = chrono.wall0

        def mark(name: str, **extra: Any) -> float:
            elapsed = chrono.mark(name, **extra)
            marks[name] = elapsed
            return elapsed

        await _send(websocket, {"type": "status", "phase": "starting", "turn_id": timer.turn_id})
        mark("turn_start")

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
            mark("llm_start")

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
                    websocket,
                    speech,
                    response.message,
                    timer,
                    interrupt_event,
                    marks,
                    wall0,
                    chrono,
                )
                mark("turn_end")
                _log_voice_perf(timer, marks, chrono)
                timer.log()
                await _send(
                    websocket,
                    {
                        "type": "turn_done",
                        "metrics": {
                            **timer.as_dict(),
                            "marks_ms": marks,
                            "ttfa_chronology": chrono.as_dict(),
                        },
                        "conversation_id": conversation_id,
                        "turn_id": timer.turn_id,
                    },
                )
                return

            reply_parts: list[str] = []
            tts_queue: asyncio.Queue[tuple[int, str, float] | None] = asyncio.Queue()
            tts_task = asyncio.create_task(
                _tts_worker(
                    websocket,
                    speech,
                    tts_queue,
                    timer,
                    interrupt_event,
                    marks,
                    wall0,
                    chrono,
                )
            )
            sentence_buffer = ""
            first_token_marked = False
            first_tts_enqueue_marked = False
            first_chunker_text = False
            generating_status_sent = False
            tts_seq = 0
            llm_trace_payload: dict[str, Any] | None = None
            llm_trace = LlmStreamTrace(
                turn_id=timer.turn_id,
                model=getattr(ai, "_model", "") or "",
            )

            try:
                async for event in ai.stream_response(
                    user_text,
                    conversation_id,
                    brief=True,
                    locale=locale,
                    timer=timer,
                    turn_id=timer.turn_id,
                    llm_trace=llm_trace,
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
                            mark("llm_first_token", chars=len(piece))
                            first_token_marked = True
                        reply_parts.append(piece)
                        from app.services.speech.voice_chunker import append_token

                        sentence_buffer = append_token(sentence_buffer, piece)
                        if not first_chunker_text and sentence_buffer.strip():
                            mark(
                                "chunker_first_text",
                                chars=len(sentence_buffer),
                                sequence_id=0,
                            )
                            first_chunker_text = True
                        await _send(
                            websocket,
                            {"type": "token", "text": piece, "turn_id": timer.turn_id},
                        )
                        ready, sentence_buffer = _split_ready_sentences(
                            sentence_buffer,
                            first_chunk=not first_tts_enqueue_marked,
                        )
                        for sentence in ready:
                            put_at = time.perf_counter()
                            if not first_tts_enqueue_marked:
                                mark(
                                    "chunker_first_flush",
                                    chars=len(sentence),
                                    sequence_id=tts_seq,
                                )
                                mark(
                                    "tts_first_fragment",
                                    chars=len(sentence),
                                    sequence_id=tts_seq,
                                )
                                first_tts_enqueue_marked = True
                            mark(
                                "tts_queue_put",
                                sequence_id=tts_seq,
                                chars=len(sentence),
                            )
                            await tts_queue.put((tts_seq, sentence, put_at))
                            tts_seq += 1
                        if not generating_status_sent:
                            generating_status_sent = True
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
                        if isinstance(event.get("llm_trace"), dict):
                            llm_trace_payload = event["llm_trace"]
                        from app.services.speech.voice_chunker import flush_remainder

                        for sentence in flush_remainder(sentence_buffer):
                            put_at = time.perf_counter()
                            if not first_tts_enqueue_marked:
                                mark(
                                    "chunker_first_flush",
                                    chars=len(sentence),
                                    sequence_id=tts_seq,
                                )
                                mark(
                                    "tts_first_fragment",
                                    chars=len(sentence),
                                    sequence_id=tts_seq,
                                )
                                first_tts_enqueue_marked = True
                            mark(
                                "tts_queue_put",
                                sequence_id=tts_seq,
                                chars=len(sentence),
                            )
                            await tts_queue.put((tts_seq, sentence, put_at))
                            tts_seq += 1
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
                        if isinstance(event.get("llm_trace"), dict):
                            llm_trace_payload = event["llm_trace"]
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
            _log_voice_perf(timer, marks, chrono)
            timer.log()
            await _send(
                websocket,
                {
                    "type": "turn_done",
                    "metrics": {
                        **timer.as_dict(),
                        "marks_ms": marks,
                        "ttfa_chronology": chrono.as_dict(),
                        "llm_trace": llm_trace_payload,
                    },
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
        await cancel_turn(notify=False)


async def _tts_worker(
    websocket: WebSocket,
    speech: Any,
    queue: asyncio.Queue,
    timer: PhaseTimer,
    interrupt_event: asyncio.Event,
    marks: dict[str, float] | None = None,
    wall0: float | None = None,
    chrono: TurnChronology | None = None,
) -> None:
    """Synthesize phrases in order while the LLM keeps producing (overlapped).

    Queue items are ``(sequence_id, text, put_at)``, ``(sequence_id, text)``,
    bare ``str``, or ``None`` sentinel.
    Audio always carries monotonically increasing ``index`` / ``sequence_id``.
    """
    index = 0
    first = True
    tts_request_count = 0
    marks = marks if marks is not None else {}
    wall0 = wall0 if wall0 is not None else time.perf_counter()
    worker_started = False

    def mark(name: str, **extra: Any) -> None:
        if chrono is not None:
            marks[name] = chrono.mark(name, **extra)
        else:
            marks[name] = round((time.perf_counter() - wall0) * 1000, 1)

    while True:
        item = await queue.get()
        if item is None:
            break
        if interrupt_event.is_set():
            break
        got_at = time.perf_counter()
        put_at: float | None = None
        if isinstance(item, tuple):
            if len(item) == 3:
                seq_id, sentence, put_at = item[0], str(item[1]), float(item[2])
            else:
                seq_id, sentence = item[0], str(item[1])
        else:
            seq_id = index
            sentence = str(item)
        sentence = sentence.strip()
        if not sentence:
            continue

        queue_wait_ms = (
            round((got_at - put_at) * 1000, 1) if put_at is not None else None
        )

        if not worker_started:
            mark(
                "tts_worker_start",
                sequence_id=seq_id,
                queue_wait_ms=queue_wait_ms,
                tts_worker_wait_ms=queue_wait_ms,
            )
            worker_started = True
        elif first:
            mark(
                "tts_worker_dequeued",
                sequence_id=seq_id,
                queue_wait_ms=queue_wait_ms,
            )

        if first:
            mark(
                "tts_start",
                sequence_id=seq_id,
                queue_wait_ms=queue_wait_ms,
                chars=len(sentence),
            )
            mark(
                "tts_first_request",
                sequence_id=seq_id,
                queue_wait_ms=queue_wait_ms,
                chars=len(sentence),
            )
        tts_request_count += 1
        await _send(websocket, {"type": "status", "phase": "speaking"})
        try:
            phase_name = "tts_first" if first else f"tts_{index}"
            begin = time.perf_counter()
            chunk_index = 0
            fish_trace: dict[str, Any] = {}
            fish_marks_ingested = False
            async for audio_chunk in speech.synthesize_stream(
                sentence, trace=fish_trace
            ):
                if interrupt_event.is_set():
                    break
                if not fish_marks_ingested and fish_trace.get("tts_request_start") is not None:
                    if chrono is not None:
                        # Live Fish marks up to first byte (may still be pending).
                        if "tts_request_start" not in {
                            e["event"] for e in chrono.events
                        }:
                            chrono.mark(
                                "tts_request_start",
                                sequence_id=seq_id,
                                at=float(fish_trace["tts_request_start"]),
                            )
                            marks["tts_request_start"] = chrono.events[-1]["elapsed_ms"]
                        conn = fish_trace.get("tts_connection_established")
                        if conn is not None and not any(
                            e["event"] == "tts_connection_established"
                            for e in chrono.events
                        ):
                            chrono.mark(
                                "tts_connection_established",
                                sequence_id=seq_id,
                                at=float(conn),
                                connection_latency_ms=fish_trace.get(
                                    "connection_latency_ms"
                                ),
                            )
                    fish_marks_ingested = True

                if not audio_chunk:
                    continue

                created_at = time.perf_counter()
                if first and fish_trace.get("tts_first_byte") is not None and chrono is not None:
                    if not any(e["event"] == "tts_ttfb" for e in chrono.events):
                        ttfb_at = float(fish_trace["tts_first_byte"])
                        chrono.mark(
                            "tts_ttfb",
                            sequence_id=seq_id,
                            at=ttfb_at,
                            ttfb_ms=fish_trace.get("ttfb_ms"),
                        )
                        chrono.mark(
                            "tts_first_audio_byte",
                            sequence_id=seq_id,
                            at=ttfb_at,
                            ttfb_ms=fish_trace.get("ttfb_ms"),
                            bytes=len(audio_chunk),
                        )
                        marks["tts_ttfb"] = chrono.events[-2]["elapsed_ms"]
                        marks["tts_first_audio_byte"] = chrono.events[-1]["elapsed_ms"]

                if first:
                    mark(
                        "audio_chunk_created",
                        sequence_id=seq_id,
                        bytes=len(audio_chunk),
                        part=chunk_index,
                    )

                encoded = base64.b64encode(audio_chunk).decode("ascii")
                send_ts = time.time()
                payload = {
                    "type": "audio_chunk",
                    "format": "mp3",
                    "index": index,
                    "sequence_id": seq_id,
                    "part": chunk_index,
                    "data": encoded,
                    "text": sentence if chunk_index == 0 else "",
                    "turn_id": timer.turn_id,
                    "backend_send_timestamp": send_ts,
                    "backend_send_elapsed_ms": round(
                        (created_at - wall0) * 1000, 1
                    ),
                }
                await _send(websocket, payload)
                if first and chunk_index == 0:
                    mark(
                        "audio_chunk_sent_ws",
                        sequence_id=seq_id,
                        bytes=len(audio_chunk),
                        backend_send_timestamp=send_ts,
                    )

                chunk_index += 1
                if first:
                    ttfb = (time.perf_counter() - begin) * 1000
                    timer.mark("tts_ttfb", ttfb)
                    timer.mark(
                        "first_audio",
                        (time.perf_counter() - timer.started_at) * 1000,
                    )
                    mark("tts_first_byte")
                    mark("audio_first_chunk_sent")
                    marks["time_to_first_audio"] = marks["audio_first_chunk_sent"]
                    timer.mark("time_to_first_audio", marks["time_to_first_audio"])
                    first = False
            if fish_trace.get("tts_complete") is not None and chrono is not None:
                if not any(e["event"] == "tts_response_complete" for e in chrono.events):
                    chrono.mark(
                        "tts_response_complete",
                        sequence_id=seq_id,
                        at=float(fish_trace["tts_complete"]),
                        total_tts_ms=fish_trace.get("total_tts_ms"),
                    )
                    marks["tts_response_complete"] = chrono.events[-1]["elapsed_ms"]
            elapsed = (time.perf_counter() - begin) * 1000
            timer.mark(phase_name, elapsed)
            await _send(
                websocket,
                {
                    "type": "audio_done",
                    "index": index,
                    "sequence_id": seq_id,
                    "turn_id": timer.turn_id,
                    "backend_send_timestamp": time.time(),
                },
            )
            if index == 0:
                mark("audio_done_sent", sequence_id=seq_id)
            index += 1
        except Exception as exc:  # noqa: BLE001
            logger.exception("TTS worker failed")
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
    timer.mark("tts_requests", float(tts_request_count))


async def _emit_tts(
    websocket: WebSocket,
    speech: Any,
    text: str,
    timer: PhaseTimer,
    interrupt_event: asyncio.Event,
    marks: dict[str, float] | None = None,
    wall0: float | None = None,
    chrono: TurnChronology | None = None,
) -> None:
    from app.services.speech.voice_chunker import flush_remainder, split_ready_phrases

    queue: asyncio.Queue = asyncio.Queue()
    buf = text
    seq = 0
    first = True
    while buf:
        ready, buf = split_ready_phrases(buf, first_chunk=first)
        if not ready:
            break
        for part in ready:
            await queue.put((seq, part, time.perf_counter()))
            seq += 1
            first = False
    for part in flush_remainder(buf):
        await queue.put((seq, part, time.perf_counter()))
        seq += 1
    if seq == 0 and text.strip():
        await queue.put((0, text.strip(), time.perf_counter()))
    await queue.put(None)
    await _tts_worker(
        websocket, speech, queue, timer, interrupt_event, marks, wall0, chrono
    )


def _log_voice_perf(
    timer: PhaseTimer,
    marks: dict[str, float],
    chrono: TurnChronology | None = None,
) -> None:
    """Emit a dedicated [VOICE PERF] chronology for Phase 1.x diagnostics."""
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
        f"[VOICE PERF] TTS REQ    {phases.get('tts_requests', 0):.0f}",
        f"[VOICE PERF] FIRST AUDIO {phases.get('first_audio', marks.get('audio_first_chunk_sent', 0)):.0f} ms",
        f"[VOICE PERF] TTFA       {phases.get('time_to_first_audio', marks.get('time_to_first_audio', 0)):.0f} ms",
        f"[VOICE PERF] TOTAL      {timer.total_ms:.0f} ms",
    ]
    for line in lines:
        logger.info("%s", line)
    if chrono is not None:
        for line in chrono.chronology_lines():
            logger.info("[TTFA CHRONO] %s", line)
        gaps = chrono.biggest_gaps(3)
        if gaps:
            biggest = gaps[0]
            logger.info(
                "[TTFA CHRONO] BIGGEST LATENCY GAP: %s → %s = %.0f ms",
                biggest["from"],
                biggest["to"],
                biggest["delta_ms"],
            )
