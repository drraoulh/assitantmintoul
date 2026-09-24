"""Streaming text chunker for voice TTS (Phase 1.2).

Strategy (documented):
1. Prefer end-of-sentence punctuation (. ! ? …) — even for short sentences (≥12).
2. For the *first* audible chunk only, also flush on soft punctuation (, ; :) or
   a short word-boundary cut so Fish Audio can start ASAP.
3. Never split mid-word.
4. Avoid tiny soft/hard fragments that would spam the TTS API.

Thresholds (Unicode code points):
- Sentence end minimum: 12
- FIRST soft/hard: 32 / 48 (min soft body 20)
- LATER soft/hard: 55 / 80 (min soft body 28)
"""

from __future__ import annotations

import re

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_SOFT_PUNCT = re.compile(r"(?<=[,;:])\s+")

SENTENCE_MIN = 12

FIRST_SOFT_MIN = 20
FIRST_SOFT = 32
FIRST_HARD = 48

LATER_SOFT_MIN = 28
LATER_SOFT = 55
LATER_HARD = 80


def split_ready_phrases(
    buffer: str,
    *,
    first_chunk: bool = False,
) -> tuple[list[str], str]:
    """Return ready TTS phrases and the incomplete leftover buffer."""
    if not buffer:
        return [], ""

    soft_min = FIRST_SOFT_MIN if first_chunk else LATER_SOFT_MIN
    soft_len = FIRST_SOFT if first_chunk else LATER_SOFT
    hard_len = FIRST_HARD if first_chunk else LATER_HARD

    # 1) Hard sentence boundaries — allow shorter spoken sentences.
    parts = _SENTENCE_END.split(buffer)
    if len(parts) > 1:
        *complete, tail = parts
        ready = [p.strip() for p in complete if len(p.strip()) >= SENTENCE_MIN]
        short = [p.strip() for p in complete if 0 < len(p.strip()) < SENTENCE_MIN]
        leftover = " ".join([*short, tail.strip()]).strip()
        if ready:
            return ready, leftover
        buffer = leftover or buffer

    # 2) Soft punctuation — mainly for the opening clause.
    if first_chunk or len(buffer) >= soft_len:
        soft_parts = _SOFT_PUNCT.split(buffer)
        if len(soft_parts) > 1:
            *complete, tail = soft_parts
            ready = [p.strip() for p in complete if len(p.strip()) >= soft_min]
            short = [p.strip() for p in complete if 0 < len(p.strip()) < soft_min]
            leftover = " ".join([*short, tail.strip()]).strip()
            if ready:
                return ready, leftover

    # 3) Hard length flush on a word boundary (never mid-word).
    if len(buffer) >= hard_len and " " in buffer:
        cut = buffer.rfind(" ", 0, hard_len)
        if cut >= soft_min:
            return [buffer[:cut].strip()], buffer[cut:].lstrip()

    return [], buffer


def flush_remainder(buffer: str) -> list[str]:
    """Flush whatever is left at end-of-stream (may be short)."""
    text = (buffer or "").strip()
    return [text] if text else []


def append_token(buffer: str, piece: str) -> str:
    """Append a stream token without gluing words when spaces are missing."""
    if not piece:
        return buffer
    if (
        buffer
        and not buffer[-1].isspace()
        and not piece[0].isspace()
        and (buffer[-1].isalnum() or buffer[-1] in ".!?…,;:")
        and piece[0].isalnum()
    ):
        return f"{buffer} {piece}"
    return buffer + piece
