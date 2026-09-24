"""Slot extraction — never invent values that are not explicit in the text."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def fold(text: str) -> str:
    lowered = (text or "").casefold().strip()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# Known Cameroon cities (folded → display). Only extract if explicitly present.
_CITIES: dict[str, str] = {
    "yaounde": "Yaoundé",
    "douala": "Douala",
    "kribi": "Kribi",
    "limbe": "Limbé",
    "buea": "Buea",
    "bafoussam": "Bafoussam",
    "bamenda": "Bamenda",
    "garoua": "Garoua",
    "maroua": "Maroua",
    "ngaoundere": "Ngaoundéré",
    "ebolowa": "Ebolowa",
    "bertoua": "Bertoua",
    "dschang": "Dschang",
    "foumban": "Foumban",
    "mbouda": "Mbouda",
    "bafang": "Bafang",
    "baham": "Baham",
    "bandjoun": "Bandjoun",
    "bangangte": "Bangangté",
    "batcham": "Batcham",
    "bana": "Bana",
    "penka-michel": "Penka-Michel",
    "penka michel": "Penka-Michel",
    "batoufam": "Batoufam",
    "foumbot": "Foumbot",
    "santchou": "Santchou",
    "edea": "Edéa",
    "nkongsamba": "Nkongsamba",
    "melong": "Melong",
    "yabassi": "Yabassi",
    "mouanko": "Mouanko",
}

_REGIONS: dict[str, str] = {
    "centre": "Centre",
    "littoral": "Littoral",
    "ouest": "Ouest",
    "west": "Ouest",
    "west region": "Ouest",
    "sud-ouest": "Sud-Ouest",
    "sud ouest": "Sud-Ouest",
    "south-west": "Sud-Ouest",
    "southwest": "Sud-Ouest",
    "nord-ouest": "Nord-Ouest",
    "nord ouest": "Nord-Ouest",
    "north-west": "Nord-Ouest",
    "northwest": "Nord-Ouest",
    "extreme-nord": "Extrême-Nord",
    "extreme nord": "Extrême-Nord",
    "far north": "Extrême-Nord",
    "adamaoua": "Adamaoua",
    "adamawa": "Adamaoua",
    "sud": "Sud",
    "south": "Sud",
    "nord": "Nord",
    "north": "Nord",
    "est": "Est",
    "east": "Est",
}

# Bare "est" is also the French verb — never match it with a plain substring.
_REGION_SAFE_SUBSTRING = {
    "est": re.compile(
        r"(?:\bl['’]est\b|\br[eé]gion\s+(?:de\s+l['’])?est\b|\beast(?:\s+region)?\b|"
        r"\bdans\s+l['’]est\b|\bvers\s+l['’]est\b)",
        re.IGNORECASE,
    ),
}

# Cultural area cues → region (no city invented).
_OUEST_CULTURE = re.compile(
    r"\b(bamoun|bamum|bamil[eé]k[eé]|grassfields|chefferies?\s+de\s+l['’]?ouest)\b",
    re.IGNORECASE,
)
_LITTORAL_CULTURE = re.compile(
    r"\b(sawa|ndol[eé]|wouri|bonanjo|duala)\b",
    re.IGNORECASE,
)

# Named places often asked about specifically (PLACE_DETAILS).
_KNOWN_PLACES: dict[str, str] = {
    "mont cameroun": "Mont Cameroun",
    "mont cameroon": "Mont Cameroun",
    "musee national": "Musée National",
    "museum national": "Musée National",
    "monument de la reunification": "Monument de la Réunification",
    "chutes de la lobé": "Chutes de la Lobé",
    "chutes de la lobe": "Chutes de la Lobé",
    "parc de waza": "Parc de Waza",
    "reserve du dja": "Réserve du Dja",
    "lac tchad": "Lac Tchad",
    "lac baleng": "Lac Baleng",
    "lake baleng": "Lac Baleng",
    "lac mbapit": "Lac Mbapit",
    "lake mbapit": "Lac Mbapit",
    "mont mbapit": "Mont Mbapit",
    "palais royal de foumban": "Palais royal de Foumban",
    "palais des rois bamoun": "Palais royal de Foumban",
    "chefferie de bandjoun": "Chefferie de Bandjoun",
    "chutes de la mouankeu": "Chutes De La Mouankeu",
    "chutes de la metche": "Chutes De La Métché",
    "chutes de la métché": "Chutes De La Métché",
    "haras de balatchi": "Le Haras De Balatchi",
    "falaise de foreke": "La Falaise De Foreke",
    "falaise de foréké": "La Falaise De Foreke",
    "quartier bonanjo": "Quartier Bonanjo (Douala)",
    "bonanjo": "Quartier Bonanjo (Douala)",
    "palais de la culture": "Palais De La Culture Du Peuple Sawa",
    "musee maritime": "Musée Maritime De Douala",
    "musée maritime": "Musée Maritime De Douala",
    "chutes d'ekom": "Chutes d’Ekom-Nkam",
    "chutes d ekom": "Chutes d’Ekom-Nkam",
    "ekom-nkam": "Chutes d’Ekom-Nkam",
    "ekom nkam": "Chutes d’Ekom-Nkam",
    "pont du wouri": "Pont Du Wouri",
    "fleuve wouri": "Fleuve Wouri",
    "ile de manoka": "Ile De Manoka",
    "île de manoka": "Ile De Manoka",
    "rhumsiki": "Rhumsiki",
    "korup": "Korup",
}

_DURATION = re.compile(
    r"\b(?P<n>\d{1,2})\s*(?:jours?|days?|j\.?)\b"
    r"|\b(?:pendant|for|during)\s+(?P<n2>\d{1,2})\s*(?:jours?|days?)\b"
    r"|\b(?:une|1)\s+semaine\b"
    r"|\b(?:a|à|for)\s+(?P<n3>\d{1,2})\s*(?:jours?|days?)\b",
    re.IGNORECASE,
)

_WEEK = re.compile(r"\b(?:une|1|one)\s+semaine\b|\bone\s+week\b", re.IGNORECASE)

_BUDGET = re.compile(
    r"(?P<amount>\d[\d\s.,]{2,})\s*(?:fcfa|xaf|f\s*cfa|francs?(?:\s+cfa)?)"
    r"|(?:budget(?:\s+de)?|avec)\s*(?P<amount2>\d[\d\s.,]{2,})",
    re.IGNORECASE,
)

_PEOPLE = re.compile(
    r"\b(?:nous\s+sommes|we\s+are|famille\s+de|family\s+of|groupe\s+de|"
    r"group\s+of)\s*(?P<n>\d{1,2})\b"
    r"|\b(?P<n2>\d{1,2})\s*(?:personnes?|people|pers\.?|adultes?)\b"
    r"|\bnous\s+sommes\s+(?P<n3>\d{1,2})\b",
    re.IGNORECASE,
)

_CHILDREN = re.compile(
    r"\b(?P<n>\d{1,2})\s*(?:enfants?|children|kids?)\b",
    re.IGNORECASE,
)


@dataclass
class ExtractedSlots:
    location: str | None = None
    region: str | None = None
    city: str | None = None
    duration_days: int | None = None
    budget_xaf: int | None = None
    people: int | None = None
    children: int | None = None
    interests: list[str] = field(default_factory=list)
    travel_style: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    language: str | None = None
    place_name: str | None = None


def _parse_int_amount(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", raw or "")
    if not digits:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    # Ignore tiny numbers that are clearly not budgets (e.g. "3 jours").
    if value < 1000:
        return None
    return value


def extract_slots(message: str, *, locale: str | None = None) -> ExtractedSlots:
    """Extract only explicitly stated parameters. Missing → None / []."""
    raw = (message or "").strip()
    folded = fold(raw)
    slots = ExtractedSlots()
    if locale in {"fr", "en"}:
        slots.language = locale

    for key, label in sorted(_CITIES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", folded):
            slots.city = label
            slots.location = label
            break

    for key, label in sorted(_REGIONS.items(), key=lambda kv: len(kv[0]), reverse=True):
        safe = _REGION_SAFE_SUBSTRING.get(key)
        if safe is not None:
            if not safe.search(folded):
                continue
        elif key not in folded:
            continue
        slots.region = label
        if slots.location is None:
            slots.location = label
        break

    if slots.region is None and _OUEST_CULTURE.search(raw):
        slots.region = "Ouest"
        if slots.location is None:
            slots.location = "Ouest"

    if slots.region is None and _LITTORAL_CULTURE.search(raw):
        slots.region = "Littoral"
        if slots.location is None:
            slots.location = "Littoral"

    for key, label in sorted(_KNOWN_PLACES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if key in folded:
            slots.place_name = label
            if slots.location is None:
                slots.location = label
            break
    if _WEEK.search(raw):
        slots.duration_days = 7
    else:
        match = _DURATION.search(raw)
        if match:
            n = match.group("n") or match.group("n2") or match.group("n3")
            if n:
                days = int(n)
                if 1 <= days <= 60:
                    slots.duration_days = days

    for match in _BUDGET.finditer(raw):
        amount = _parse_int_amount(match.group("amount") or match.group("amount2") or "")
        if amount is not None:
            slots.budget_xaf = amount
            break

    people_match = _PEOPLE.search(raw)
    if people_match:
        n = people_match.group("n") or people_match.group("n2") or people_match.group("n3")
        if n:
            count = int(n)
            if 1 <= count <= 50:
                slots.people = count

    children_match = _CHILDREN.search(raw)
    if children_match:
        count = int(children_match.group("n"))
        if 0 <= count <= 20:
            slots.children = count

    interests: list[str] = []
    if re.search(r"\b(nature|ecotourisme|eco-?tourisme|parc|parcs)\b", folded):
        interests.append("nature")
    if re.search(r"\b(culture|culturel|patrimoine|sawa|bamil[eé]k[eé]|fang)\b", folded):
        interests.append("culture")
    if re.search(r"\b(plage|plages|mer|ocean|océan)\b", folded):
        interests.append("beach")
    if re.search(r"\b(gastronomie|cuisine|plat|plats|ndol[eé]|manger|food)\b", folded):
        interests.append("food")
    if re.search(r"\b(hotel|hôtel|hebergement|hébergement)\b", folded):
        interests.append("hotel")
    if re.search(
        r"\b(autour|alentours|environs|proche|nearby|around|proximit[eé])\b",
        folded,
    ):
        interests.append("nearby")
    slots.interests = interests
    slots.interests = interests

    if re.search(r"\b(luxe|premium|haut\s+de\s+gamme)\b", folded):
        slots.travel_style = "luxury"
    elif re.search(r"\b(backpack|budget|pas\s+cher|economique|économique)\b", folded):
        slots.travel_style = "budget"
    elif re.search(r"\b(famille|family)\b", folded):
        slots.travel_style = "family"

    return slots
