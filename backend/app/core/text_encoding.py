"""Detect and repair UTF-8 text that was decoded as cp1252/latin-1 ("mojibake").

Typical symptom: « SituÃ© Ã  Douala » instead of « Situé à Douala ».
"""

from __future__ import annotations

import re

# cp1252 renderings of UTF-8 lead bytes (0xC2–0xF4) followed by 1–3
# continuation bytes (0x80–0xBF). A space stands for 0xA0 because
# non-breaking spaces were often collapsed to plain spaces downstream.
_CONT = "\u0080-\u00bf\u0152\u0153\u0160\u0161\u0178\u017d\u017e\u0192\u02c6\u02dc\u2013\u2014\u2018-\u201e\u2020-\u2022\u2026\u2030\u2039\u203a\u20ac\u2122"
_RUN = re.compile(f"[\u00c2-\u00f4][{_CONT} ]{{1,3}}")
_MARKERS = re.compile(r"Ã[\u0080-\u00bf]|Ã(?=[ \u00a0]|$)|â€|Â[\u00a0-\u00bf]")


def has_mojibake(text: str) -> bool:
    return bool(text) and bool(_MARKERS.search(text))


def _decode_run(match: re.Match[str]) -> str:
    run = match.group()
    for size in range(len(run), 1, -1):
        head = run[:size]
        try:
            fixed = head.replace(" ", "\u00a0").encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if fixed == "\u00a0" or not fixed.strip():
            continue
        return fixed + run[size:]
    return run


def repair_mojibake(text: str) -> str:
    """Undo one level of UTF-8 → cp1252 double encoding; clean text is unchanged."""
    if not has_mojibake(text):
        return text
    fixed = _RUN.sub(_decode_run, text)
    # "à" is C3 A0; once A0 became a plain space, "Ã " is all that is left.
    fixed = re.sub(r"Ã(?=[ \u00a0])", "à", fixed)
    # A lone trailing "Ã" is a truncated two-byte letter; "é" is by far the most common.
    fixed = re.sub(r"Ã$", "é", fixed)
    return fixed
