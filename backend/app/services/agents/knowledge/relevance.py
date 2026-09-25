"""Keep only evidence that is on-topic for a narrow intent.

Lexical RAG matches a hotel question on the city name alone, which used to
pull museums, districts and generic « Culture et savoir-vivre » notes into
hotel answers. Narrow intents therefore keep only chunks / places about
their own topic.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeEvidence, PlaceEvidence

_HOTEL_TERMS = re.compile(
    r"\b(?:h[oô]tels?|motels?|auberges?|lodges?|r[ée]sidences?\s+h[oô]teli[eè]res?|"
    r"h[ée]bergements?|chambres?\s+d['’]h[oô]tes?|guest\s*houses?|"
    r"accommodations?|lodging|appart?[- ]?h[oô]tels?|campements?|resorts?)\b",
    re.IGNORECASE,
)
_HOTEL_CATEGORIES = {"hotel", "lodging", "accommodation", "hostel", "guesthouse", "resort", "campement"}
_CITY_FIELD = re.compile(r"\bVille\s*:\s*([^\n]+?)\s+R[ée]gion\s*:", re.IGNORECASE)


def _fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


def _is_hotel_chunk(chunk: KnowledgeEvidence) -> bool:
    cid = chunk.chunk_id or ""
    if cid.startswith("culture-hotel-"):
        return True
    if (chunk.source_id or "").startswith("culture:"):
        return False
    head = f"{chunk.title or ''}\n{(chunk.content or '')[:400]}"
    return bool(_HOTEL_TERMS.search(head))


def _other_city(chunk: KnowledgeEvidence, city: str | None) -> bool:
    if not city:
        return False
    if chunk.city:
        return _fold(chunk.city) != _fold(city)
    match = _CITY_FIELD.search(chunk.content or "")
    return bool(match) and _fold(match.group(1)) != _fold(city)


def _is_hotel_place(place: PlaceEvidence) -> bool:
    if {_fold(c) for c in place.category} & _HOTEL_CATEGORIES:
        return True
    return bool(_HOTEL_TERMS.search(place.name or ""))


def filter_knowledge_for_intent(
    intent: IntentResult, chunks: list[KnowledgeEvidence]
) -> list[KnowledgeEvidence]:
    if intent.intent != "HOTEL":
        return chunks
    return [c for c in chunks if _is_hotel_chunk(c) and not _other_city(c, intent.city)]


def filter_places_for_intent(intent: IntentResult, places: list[PlaceEvidence]) -> list[PlaceEvidence]:
    if intent.intent != "HOTEL":
        return places
    return [p for p in places if _is_hotel_place(p)]
