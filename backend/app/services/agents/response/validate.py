"""Soft grounding checks for Agent 4 outputs."""

from __future__ import annotations

import re
import unicodedata


def fold(text: str) -> str:
    lowered = (text or "").casefold()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def contains_invented_place(text: str, allowed_names: set[str], suspects: set[str]) -> bool:
    """Return True if a known-suspect place name appears but is not allowed."""
    folded_text = fold(text)
    allowed_folded = {fold(n) for n in allowed_names if n}
    for name in suspects:
        key = fold(name)
        if len(key) < 3:
            continue
        if key in folded_text and key not in allowed_folded:
            # word-ish presence
            if re.search(rf"\b{re.escape(key)}\b", folded_text):
                return True
    return False


def voice_text_is_clean(text: str) -> bool:
    """Voice-friendly: no markdown tables/headings/bullets/urls/emoji-ish."""
    if not text:
        return False
    forbidden = ["```", "|---", "http://", "https://", "*", "# "]
    if any(tok in text for tok in forbidden):
        return False
    if re.search(r"^[\-\*]\s", text, re.MULTILINE):
        return False
    if re.search(r"^#{1,3}\s", text, re.MULTILINE):
        return False
    return True


def claims_road_distance(text: str) -> bool:
    folded = fold(text)
    return any(
        phrase in folded
        for phrase in (
            "par la route",
            "by road",
            "driving distance",
            "en voiture sur",
        )
    )
