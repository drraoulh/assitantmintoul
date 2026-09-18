"""Query routing: skip heavy retrieval for greetings and chitchat."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


def _fold(text: str) -> str:
    lowered = text.casefold().strip()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# Short social / filler turns that do not need KB or web search.
_SIMPLE_EXACT = {
    "bonjour",
    "bonsoir",
    "salut",
    "hello",
    "hi",
    "hey",
    "merci",
    "merci beaucoup",
    "ok",
    "okay",
    "daccord",
    "d'accord",
    "oui",
    "non",
    "au revoir",
    "a bientot",
    "bonne journee",
    "bonne soiree",
    "ca va",
    "comment ca va",
    "comment allez vous",
    "qui es tu",
    "qui etes vous",
    "presente toi",
}

_SIMPLE_PREFIX = re.compile(
    r"^(bonjour|bonsoir|salut|hello|hi|hey|merci|ok|okay)\b",
    re.IGNORECASE,
)

_TOURISM_HINT = re.compile(
    r"\b("
    r"visiter|visite|yaounde|douala|kribi|limbe|limbé|waza|dja|"
    r"plage|parc|hotel|hôtel|restaurant|itinéraire|itineraire|prix|tarif|"
    r"monument|musee|musée|voyage|tourisme|region|région|ville|"
    r"comment aller|ou manger|où manger|que faire|que visiter|"
    r"transport|taxi|bus|train|avion|horaire|ouvert|ticket|billet|"
    r"securite|sécurité|arnaque|escroquerie|conseil|recommande|"
    r"nature|histoire|gastronomie|nourriture|ndole|ndolé|culture|"
    r"deux jours|2 jours|week-?end|camfranglais|pidgin|how far|abeg"
    r")\b",
    re.IGNORECASE,
)

@dataclass(frozen=True)
class QueryRoute:
    kind: str  # "simple" | "grounded"
    skip_kb: bool
    skip_web: bool
    reason: str


def route_query(message: str) -> QueryRoute:
    """Decide whether a turn needs RAG/web grounding.

    Simple social turns answer from the system prompt alone — saving
    retrieval + web RTT before the LLM starts streaming.
    """
    raw = (message or "").strip()
    if not raw:
        return QueryRoute("simple", True, True, "empty")

    folded = _fold(raw)
    # Strip trailing punctuation for exact match.
    compact = re.sub(r"[!?.…,;:\s]+$", "", folded).strip()
    compact = re.sub(r"\s+", " ", compact)

    if compact in _SIMPLE_EXACT:
        return QueryRoute("simple", True, True, "greeting_or_chitchat")

    # Very short + greeting prefix, no tourism keywords.
    if len(compact) <= 40 and _SIMPLE_PREFIX.search(raw) and not _TOURISM_HINT.search(raw):
        return QueryRoute("simple", True, True, "short_greeting")

    if len(compact.split()) <= 3 and not _TOURISM_HINT.search(raw):
        # e.g. "merci guide", "ok super"
        if _SIMPLE_PREFIX.search(raw) or compact in {"merci", "super", "parfait", "genial", "génial"}:
            return QueryRoute("simple", True, True, "ack")

    return QueryRoute("grounded", False, False, "needs_knowledge")
