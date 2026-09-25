"""Rule-based intent classifier (fast path for voice / low latency)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.agents.intent.extractors import ExtractedSlots, fold


@dataclass(frozen=True)
class RuleHit:
    intent: str
    confidence: float
    reason: str


_SIMPLE_QA = re.compile(
    r"\b("
    r"capitale|capital|monnaie|currency|devise|"
    r"combien\s+de\s+r[eé]gions|how\s+many\s+regions|"
    r"quel(?:le)?\s+est\s+(?:la\s+)?capitale|"
    r"what\s+is\s+the\s+capital|"
    r"dans\s+quelle\s+r[eé]gion|which\s+region|"
    r"chef[- ]lieu|"
    r"d[eé]partement\s+de|dans\s+quel\s+d[eé]partement|"
    r"population|superficie|official\s+language|langue\s+officielle"
    r")\b",
    re.IGNORECASE,
)

_TOURISM_INFO = re.compile(
    r"\b("
    r"tourisme\s+au\s+cameroun|tourism\s+in\s+cameroon|"
    r"pourquoi\s+visiter|why\s+visit|"
    r"parle[- ]moi\s+du\s+tourisme|tell\s+me\s+about\s+tourism"
    r")\b",
    re.IGNORECASE,
)

_PLACE_SEARCH = re.compile(
    r"\b("
    r"que\s+visiter|quoi\s+visiter|what\s+to\s+visit|where\s+to\s+go|"
    r"lieux?\s+touristiques?|tourist\s+(?:sites?|spots?|places?)|"
    r"endroits?\s+[aà]\s+visiter|sites?\s+[aà]\s+visiter|"
    r"que\s+faire\s+[aà]|what\s+to\s+do\s+in|"
    r"donne[- ]moi\s+des\s+endroits|recommend(?:\s+me)?\s+places?"
    r")\b",
    re.IGNORECASE,
)

_PLACE_DETAILS = re.compile(
    r"\b("
    r"parle[- ]moi\s+(?:du|de\s+la|des|de\s+l['’])|"
    r"tell\s+me\s+about|"
    r"que\s+(?:peut[- ]on|peut[- ]on|peut[- ]on)\s+faire\s+(?:au|à|a|dans)|"
    r"combien\s+co[uû]te\s+(?:la\s+)?visite|"
    r"how\s+much\s+(?:is|does)\s+(?:the\s+)?(?:visit|entry|ticket)"
    r")\b",
    re.IGNORECASE,
)

_ITINERARY = re.compile(
    r"\b("
    r"itin[eé]raire|itinerary|circuit|organise[- ]moi|organize|"
    r"planifie|plan\s+(?:me\s+)?(?:a|an|my)|"
    r"je\s+(?:viens|vais|veux\s+visiter).{0,40}\d+\s*jours?|"
    r"pendant\s+\d+\s*jours?|for\s+\d+\s*days?|"
    r"\d+\s*jours?\s+[aà]|days?\s+in|"
    r"semaine\s+[aà]|week\s+in|"
    r"que\s+peux[- ]tu\s+me\s+proposer|what\s+can\s+you\s+(?:suggest|propose)"
    r")\b",
    re.IGNORECASE,
)

_BUDGET = re.compile(
    r"\b(fcfa|xaf|budget|francs?(?:\s+cfa)?)\b",
    re.IGNORECASE,
)

_NATURE = re.compile(
    r"\b("
    r"nature|ecotourisme|eco-?tourism|parc(?:s)?\s+(?:national|naturel)|"
    r"wildlife|faune|foret|forêt|randonn[eé]e|hiking|"
    r"activit[eé]\s+nature|circuit\s+nature|nature\s+(?:trip|activity)"
    r")\b",
    re.IGNORECASE,
)

_CULTURE = re.compile(
    r"\b("
    r"culture|culturel|patrimoine|heritage|aires?\s+culturelles?|"
    r"sawa|bamil[eé]k[eé]|fang|tradition|festival"
    r")\b",
    re.IGNORECASE,
)

_FOOD = re.compile(
    r"\b("
    r"nourriture|plats?|gastronomie|cuisine|ndol[eé]|eru|achu|kondre|"
    r"manger|food|dish(?:es)?|spécialit[eé]s?|specialit(?:y|ies)|"
    r"ou\s+manger|où\s+manger|where\s+to\s+eat"
    r")\b",
    re.IGNORECASE,
)

_HOTEL = re.compile(
    r"\b("
    r"h[oô]tels?|hotels?|o[uù]\s+dormir|where\s+to\s+(?:sleep|stay)|"
    r"h[eé]bergement|accommodation|lodging"
    r")\b",
    re.IGNORECASE,
)

_BOOKING = re.compile(
    r"\b("
    r"r[eé]server|book(?:ing)?|r[eé]servation|"
    r"disponibilit[eé]s?|availability|disponibles?"
    r")\b",
    re.IGNORECASE,
)

_VISION = re.compile(
    r"\b("
    r"qu['’]est[- ]ce\s+que\s+c['’]est|what\s+is\s+this|"
    r"analyse\s+(?:cette\s+)?image|analyze\s+(?:this\s+)?image|"
    r"photo|image\s+(?:d['’]un|of\s+a)"
    r")\b",
    re.IGNORECASE,
)

_WEB = re.compile(
    r"\b("
    r"actualit[eé]|news|aujourd['’]hui|today|cette\s+semaine|"
    r"ce\s+mois(?:[- ]ci)?|this\s+month|"
    r"horaires?\s+actuels?|current\s+(?:hours|schedule|price)|"
    r"ouvert\s+maintenant|open\s+now|prix\s+actuel|"
    r"recherche\s+sur\s+(?:internet|le\s+web|google)|"
    r"cherche\s+sur\s+(?:internet|le\s+web|google)|"
    r"search\s+(?:the\s+)?(?:web|internet)|"
    r"sur\s+internet|on\s+the\s+web|google\s+(?:moi|me)"
    r")\b",
    re.IGNORECASE,
)

# Fresh / external tourism facts that should prefer Web Research.
_EVENTS_FRESH = re.compile(
    r"\b("
    r"[eé]v[eé]nements?(?:\s+touristiques?)?|"
    r"festivals?|foires?|concerts?|"
    r"tourist(?:ic)?\s+events?|festivals?"
    r")\b",
    re.IGNORECASE,
)

_AMBIGUOUS = re.compile(
    r"\b("
    r"quelque\s+chose\s+de\s+bien|something\s+(?:nice|good|cool)|"
    r"surprise[- ]moi|surprise\s+me|je\s+sais\s+pas|i\s+don['’]?t\s+know|"
    r"n['’]importe\s+quoi|whatever|un\s+truc\s+sympa"
    r")\b",
    re.IGNORECASE,
)


def classify_with_rules(
    message: str,
    slots: ExtractedSlots,
    *,
    has_image: bool = False,
) -> RuleHit:
    raw = (message or "").strip()
    folded = fold(raw)

    if has_image or (_VISION.search(raw) and "image" in folded):
        return RuleHit("VISION", 0.92, "vision_or_image")

    if not raw:
        return RuleHit("CLARIFICATION", 0.3, "empty")

    # Phase 2.8 — geographic relation Qs before tourism search / itinerary
    from app.services.agents.knowledge.geography import is_geo_simple_query

    if is_geo_simple_query(raw) or (
        _SIMPLE_QA.search(raw)
        and (
            slots.city
            or slots.region
            or "bafoussam" in folded
            or "ouest" in folded
            or "west" in folded
            or "douala" in folded
            or "littoral" in folded
            or "yaounde" in folded
            or "yaoundé" in folded
            or "kribi" in folded
            or "ebolowa" in folded
        )
    ):
        return RuleHit("SIMPLE_QA", 0.93, "geographic_relation_qa")

    if _AMBIGUOUS.search(raw) and not (
        slots.city or slots.duration_days or slots.budget_xaf or slots.place_name
    ):
        return RuleHit("CLARIFICATION", 0.35, "ambiguous_request")

    if _BOOKING.search(raw):
        return RuleHit("BOOKING", 0.9, "booking_keywords")

    if slots.budget_xaf is not None and (
        slots.duration_days is not None or slots.people is not None or _ITINERARY.search(raw)
    ):
        return RuleHit("BUDGET_TRIP", 0.9, "budget_and_trip_slots")

    if slots.budget_xaf is not None and _BUDGET.search(raw):
        # Budget mentioned with trip context words.
        if re.search(r"\b(jours?|days?|voyage|trip|visiter|yaounde|douala)\b", folded):
            return RuleHit("BUDGET_TRIP", 0.85, "budget_with_travel_context")

    if _ITINERARY.search(raw) or (
        slots.duration_days is not None
        and (
            slots.city is not None
            or re.search(r"\b(visiter|cameroun|cameroon|proposer|propose)\b", folded)
        )
    ):
        # Prefer BUDGET_TRIP if budget already known.
        if slots.budget_xaf is not None:
            return RuleHit("BUDGET_TRIP", 0.88, "itinerary_with_budget")
        return RuleHit("ITINERARY", 0.88, "itinerary_or_duration_city")

    # Explicit web / freshness BEFORE culture (festival alone used to steal WEB_SEARCH).
    if _WEB.search(raw):
        return RuleHit("WEB_SEARCH", 0.9, "freshness_keywords")

    # Festivals / tourist events often need live or external sources.
    if _EVENTS_FRESH.search(raw):
        return RuleHit("WEB_SEARCH", 0.86, "events_need_web")

    if _HOTEL.search(raw) and not _FOOD.search(raw):
        return RuleHit("HOTEL", 0.86, "hotel_keywords")

    if _FOOD.search(raw):
        return RuleHit("FOOD", 0.88, "food_keywords")

    if _NATURE.search(raw):
        return RuleHit("NATURE", 0.87, "nature_keywords")

    if _CULTURE.search(raw):
        return RuleHit("CULTURE", 0.87, "culture_keywords")

    if slots.place_name and (
        _PLACE_DETAILS.search(raw)
        or re.search(r"\b(parle|tell|visite|visit|co[uû]te|cost)\b", folded)
    ):
        return RuleHit("PLACE_DETAILS", 0.9, "named_place_details")

    if _PLACE_DETAILS.search(raw) and slots.place_name:
        return RuleHit("PLACE_DETAILS", 0.88, "place_details_pattern")

    if _PLACE_SEARCH.search(raw):
        return RuleHit("PLACE_SEARCH", 0.9, "place_search_pattern")

    if _TOURISM_INFO.search(raw):
        return RuleHit("TOURISM_INFO", 0.85, "tourism_info")

    if _SIMPLE_QA.search(raw):
        return RuleHit("SIMPLE_QA", 0.9, "factual_qa")

    if slots.place_name:
        return RuleHit("PLACE_DETAILS", 0.75, "known_place_mention")

    if slots.city and re.search(r"\b(visiter|visite|que\s+faire|what\s+to)\b", folded):
        return RuleHit("PLACE_SEARCH", 0.78, "city_visit_hint")

    if slots.region and re.search(
        r"\b(visiter|visite|que\s+faire|what\s+to|sites?|lieux?|tourisme|tourism)\b",
        folded,
    ):
        return RuleHit("PLACE_SEARCH", 0.82, "region_visit_hint")

    # Vague Cameroon mention without actionable slots.
    if re.search(r"\bcameroun|cameroon\b", folded) and len(folded.split()) <= 12:
        if not (slots.city or slots.region or slots.duration_days or slots.budget_xaf):
            return RuleHit("CLARIFICATION", 0.45, "vague_cameroon")

    return RuleHit("TOURISM_INFO", 0.55, "fallback_tourism_info")
