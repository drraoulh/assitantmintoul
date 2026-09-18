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
    """Return complete sentences and the leftover incomplete tail."""
    parts = _SENTENCE_END.split(buffer)
    if len(parts) == 1:
        # Also flush on long clause without punctuation.
        if len(buffer) >= 140 and (" " in buffer):
            cut = buffer.rfind(" ", 0, 120)
            if cut > 40:
                return [buffer[:cut].strip()], buffer[cut:].lstrip()
        return [], buffer
    *complete, tail = parts
    ready = [p.strip() for p in complete if p.strip()]
    return ready, tail.strip()


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

    async def run_turn(*, text: str | None = None, audio_b64: str | None = None, mime: str = "audio/m4a") -> None:
        nonlocal conversation_id
        interrupt_event.clear()
        timer = PhaseTimer("voice_ws")
        await _send(websocket, {"type": "status", "phase": "starting"})

        try:
            user_text = (text or "").strip()
            if audio_b64 and not user_text:
                await _send(websocket, {"type": "status", "phase": "transcribing"})
                with timer.phase("stt"):
                    audio_bytes = base64.b64decode(audio_b64)
                    user_text, language = await speech.transcribe(
                        audio_bytes=audio_bytes,
                        mime_type=mime or "audio/m4a",
                    )
                await _send(
                    websocket,
                    {
                        "type": "transcript",
                        "text": user_text,
                        "language": language,
                        "latency_ms": timer.phases.get("stt"),
                    },
                )

            if not user_text:
                await _send(
                    websocket,
                    {
                        "type": "error",
                        "code": "empty_transcript",
                        "message": "Aucune parole détectée.",
                        "recoverable": True,
                    },
                )
                return

            if interrupt_event.is_set():
                return

            await _send(websocket, {"type": "status", "phase": "thinking"})

            if not isinstance(ai, HuggingFaceAIService):
                # Non-streaming backends: one-shot then TTS.
                with timer.phase("llm"):
                    response = await ai.generate_response(
                        user_text,
                        conversation_id,
                        brief=True,
                    )
                conversation_id = response.conversation_id
                await _send(websocket, {"type": "assistant_text", "text": response.message})
                await _emit_tts(websocket, speech, response.message, timer, interrupt_event)
                timer.log()
                await _send(
                    websocket,
                    {"type": "turn_done", "metrics": timer.as_dict(), "conversation_id": conversation_id},
                )
                return

            reply_parts: list[str] = []
            tts_queue: asyncio.Queue[str | None] = asyncio.Queue()
            tts_task = asyncio.create_task(
                _tts_worker(websocket, speech, tts_queue, timer, interrupt_event)
            )
            sentence_buffer = ""

            try:
                async for event in ai.stream_response(
                    user_text,
                    conversation_id,
                    brief=True,
                    timer=timer,
                ):
                    if interrupt_event.is_set():
                        break
                    etype = event.get("type")
                    if etype == "route":
                        await _send(websocket, {**event})
                        await _send(
                            websocket,
                            {
                                "type": "status",
                                "phase": "retrieving" if not event.get("skip_kb") else "generating",
                            },
                        )
                    elif etype == "token":
                        piece = str(event.get("text") or "")
                        reply_parts.append(piece)
                        sentence_buffer += piece
                        await _send(websocket, {"type": "token", "text": piece})
                        ready, sentence_buffer = _split_ready_sentences(sentence_buffer)
                        for sentence in ready:
                            await tts_queue.put(sentence)
                        await _send(websocket, {"type": "status", "phase": "generating"})
                    elif etype == "done":
                        conversation_id = str(event.get("conversation_id") or conversation_id)
                        full = str(event.get("text") or "".join(reply_parts)).strip()
                        if sentence_buffer.strip():
                            await tts_queue.put(sentence_buffer.strip())
                            sentence_buffer = ""
                        await _send(websocket, {"type": "assistant_text", "text": full})
                    elif etype == "error":
                        await _send(
                            websocket,
                            {
                                "type": "error",
                                "code": event.get("code") or "llm_error",
                                "message": event.get("message") or "LLM error",
                                "recoverable": True,
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

            timer.log()
            await _send(
                websocket,
                {
                    "type": "turn_done",
                    "metrics": timer.as_dict(),
                    "conversation_id": conversation_id,
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
                    await run_turn(
                        text=payload.get("text"),
                        audio_b64=payload.get("audio_base64") or payload.get("data"),
                        mime=str(payload.get("mime_type") or payload.get("mime") or "audio/m4a"),
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
) -> None:
    index = 0
    first = True
    while True:
        sentence = await queue.get()
        if sentence is None:
            break
        if interrupt_event.is_set():
            break
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
                    },
                )
                chunk_index += 1
                if first:
                    timer.mark("tts_ttfb", (time.perf_counter() - begin) * 1000)
                    first = False
            elapsed = (time.perf_counter() - begin) * 1000
            timer.mark(phase_name, elapsed)
            await _send(websocket, {"type": "audio_done", "index": index})
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
                },
            )


async def _emit_tts(
    websocket: WebSocket,
    speech: Any,
    text: str,
    timer: PhaseTimer,
    interrupt_event: asyncio.Event,
) -> None:
    queue: asyncio.Queue[str | None] = asyncio.Queue()
    # Split into sentence-sized pieces for earlier first audio.
    parts = [p.strip() for p in _SENTENCE_END.split(text) if p.strip()] or [text]
    for part in parts:
        await queue.put(part)
    await queue.put(None)
    await _tts_worker(websocket, speech, queue, timer, interrupt_event)
