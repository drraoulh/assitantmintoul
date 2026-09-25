"""Turn the user question + resolved context into short web queries (1–3, up to 5 for routes).

- Always carries the last explicit region/city resolved by Agent 1 (which
  already reads conversation context), so follow-ups stay on the right region.
- FR question → one FR query + one EN query (mixed Cameroon sources).
- Current year only for current-information requests.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from app.services.agents.intent.models import IntentResult

MAX_QUERIES = 3
_MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
    "septembre", "octobre", "novembre", "décembre",
)
_THIS_MONTH = re.compile(r"\b(?:ce\s+mois|this\s+month|en\s+ce\s+moment|actuellement|right\s+now)", re.IGNORECASE)

_REGIONS: dict[str, tuple[str, str]] = {
    "sud-ouest": ("Sud-Ouest Cameroun", "South-West Cameroon"),
    "nord-ouest": ("Nord-Ouest Cameroun", "North-West Cameroon"),
    "extreme-nord": ("Extrême-Nord Cameroun", "Far North Cameroon"),
    "littoral": ("Littoral Cameroun", "Littoral Cameroon"),
    "adamaoua": ("Adamaoua Cameroun", "Adamawa Cameroon"),
    "centre": ("région du Centre Cameroun", "Centre Region Cameroon"),
    "ouest": ("Ouest Cameroun", "West Region Cameroon"),
    "nord": ("Nord Cameroun", "North Region Cameroon"),
    "sud": ("Sud Cameroun", "South Region Cameroon"),
    "est": ("Est Cameroun", "East Region Cameroon"),
}

_STOPWORDS = set(
    """
    le la les l un une des de du d au aux et ou en a est c ce cet cette ces ca ça
    qu que qui quoi quel quelle quels quelles comment pourquoi combien y il elle on
    nous vous je j tu me m moi mon ma mes ton ta tes son sa ses pour par sur avec
    dans chez pas plus tres bien peux pouvez peut donne donnez donner dis dites dire
    connais connaissez savoir sais veux voudrais aimerais cherche cherches recherche
    rechercher trouve trouver internet web google stp svp s'il plait merci alors
    sont etait ont fait faire il-y-a y-a-t-il existe-t-il est-ce quels-sont
    the a an of in on at to for is are was what which who how where when can could
    would you me my i please tell about show find search look do does there some any
    it its and or with from by be
    parle parlez parle-moi parlez-moi raconte racontez raconte-moi racontez-moi explique
    expliquez explique-moi expliquez-moi dis-moi dites-moi montre-moi aide-moi tell explain
    qu'est-ce est-ce signifie veut-dire chez
    mois ci mois-ci ce-mois-ci cette-semaine semaine actuellement aujourd hui maintenant recent recents
    recemment actuel actuels actuelle this month week now currently current latest today
    region regions cameroun cameroon
    """.split()
)

_REGION_WORDS = {
    "sud", "ouest", "nord", "est", "centre", "littoral", "adamaoua", "extreme",
    "sud-ouest", "nord-ouest", "extreme-nord", "south", "west", "north", "east",
    "far", "south-west", "north-west", "southwest", "northwest", "adamawa", "central",
}

_FR_EN = {
    "plat": "dish", "plats": "dishes", "traditionnel": "traditional",
    "traditionnelle": "traditional", "traditionnels": "traditional",
    "traditionnelles": "traditional", "nourriture": "food", "cuisine": "cuisine",
    "gastronomie": "gastronomy", "specialite": "specialty", "specialites": "specialties",
    "typique": "typical", "typiques": "typical", "hotel": "hotel", "hotels": "hotels",
    "prix": "prices", "tarif": "rates", "tarifs": "rates", "restaurant": "restaurant",
    "restaurants": "restaurants", "resto": "restaurant", "restos": "restaurants",
    "meilleur": "best", "meilleurs": "best", "meilleure": "best", "meilleures": "best",
    "festival": "festival", "festivals": "festivals", "evenement": "event",
    "evenements": "events", "fete": "festival", "fetes": "festivals", "foire": "fair",
    "concert": "concert", "concerts": "concerts", "marche": "market", "marches": "markets",
    "plage": "beach", "plages": "beaches", "parc": "park", "parcs": "parks",
    "visiter": "visit", "voir": "see", "lieux": "places", "lieu": "place",
    "culture": "culture", "tradition": "tradition", "traditions": "traditions",
    "danse": "dance", "danses": "dances", "musee": "museum", "musees": "museums",
    "chutes": "waterfalls", "cascade": "waterfall", "ou": "where", "manger": "eat",
    "dormir": "stay", "cher": "expensive", "pas-cher": "cheap", "bon": "good",
    "bons": "good", "boissons": "drinks", "boisson": "drink", "recette": "recipe",
    "recettes": "recipes", "histoire": "history", "patrimoine": "heritage",
    "ville": "city", "villes": "cities", "quartier": "district", "ouverture": "opening",
    "horaires": "opening hours", "billet": "ticket", "billets": "tickets",
    "transport": "transport", "securite": "safety", "visa": "visa", "meteo": "weather",
    "saison": "season", "pluies": "rainy season", "artisanat": "crafts",
    "pas_cher": "cheap", "bon_marche": "cheap",
}

_TOKEN_RE = re.compile(r"[\w'’-]+", re.UNICODE)
_PHRASES = (
    (re.compile(r"\bpas\s+ch[eè]re?s?\b", re.IGNORECASE), "pas_cher"),
    (re.compile(r"\bbon\s+march[eé]\b", re.IGNORECASE), "bon_marche"),
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def strip_stopwords(
    user_query: str, *, drop_region_words: bool = False, drop: set[str] | None = None
) -> list[str]:
    tokens: list[str] = []
    text = user_query or ""
    for pattern, repl in _PHRASES:
        text = pattern.sub(repl, text)
    for raw in _TOKEN_RE.findall(text):
        tok = raw.strip("'’-")
        for part in re.split(r"['’]", tok):
            folded = _fold(part)
            if not folded or folded in _STOPWORDS or len(folded) < 2:
                continue
            if drop_region_words and folded in _REGION_WORDS:
                continue
            if drop and folded in drop:
                continue
            tokens.append(part)
    return tokens


def translate_to_en(tokens: list[str]) -> list[str]:
    return [_FR_EN.get(_fold(t), t) for t in tokens]


def _region_labels(intent: IntentResult) -> tuple[str, str]:
    if intent.city:
        return (f"{intent.city} Cameroun", f"{intent.city} Cameroon")
    for value in (intent.region, intent.location):
        key = _fold(value or "").replace(" ", "-")
        if key in _REGIONS:
            return _REGIONS[key]
    place = intent.location or ""
    if place:
        return (f"{place} Cameroun", f"{place} Cameroon")
    return ("Cameroun", "Cameroon")


def needs_freshness(intent: IntentResult) -> bool:
    return intent.intent == "WEB_SEARCH" or (intent.web_reason or "").startswith(
        "FORCED_CURRENT"
    )


def _topic_query(intent: IntentResult, fr_loc: str) -> str | None:
    reason = intent.web_reason or ""
    if reason == "FORCED_RESTAURANT_SEARCH":
        return f"meilleurs restaurants cuisine locale {fr_loc}"
    if intent.intent == "HOTEL":
        return f"hôtels {fr_loc} avis prix"
    if intent.intent == "FOOD":
        return f"plats traditionnels gastronomie {fr_loc}"
    if intent.intent in {"CULTURE", "TOURISM_INFO"} and fr_loc != "Cameroun":
        return f"culture traditions tourisme {fr_loc}"
    return None


MAX_ROUTE_QUERIES = 5
_ROUTE_INTENTS = {"TRAVEL_ROUTE", "ITINERARY", "BUDGET_TRIP"}


def destination_queries(place: str, *, english: bool = False) -> list[str]:
    if english:
        return [f"things to do in {place} Cameroon", f"tourist attractions {place} Cameroon"]
    return [f"que faire à {place} Cameroun", f"lieux touristiques {place} Cameroun"]


def route_query_phases(intent: IntentResult) -> tuple[list[str], list[str]]:
    """(transport, destination) queries for an origin → destination question.

    Phase A always names the pair of towns so results describe that journey;
    Phase B (only when the user also asks what to do / for a stay) targets the
    destination. The two are never mixed in one query.
    """
    dest = intent.destination or ""
    origin = intent.origin or ""
    english = (intent.language or "fr") == "en"
    if origin and english:
        transport = [
            f"{origin} to {dest} bus transport Cameroon",
            f"{origin} {dest} travel agency bus",
            f"{origin} {dest} bus fare travel time",
        ]
    elif origin:
        transport = [
            f"{origin} {dest} transport bus Cameroon",
            f"{origin} {dest} agence de voyage bus",
            f"{origin} {dest} prix transport durée",
        ]
    elif english:
        transport = [f"how to get to {dest} Cameroon bus", f"{dest} Cameroon travel agency bus"]
    else:
        transport = [f"comment aller à {dest} Cameroun transport bus", f"{dest} Cameroun agence de voyage bus"]
    destination: list[str] = []
    if intent.wants_activities or intent.duration_days:
        destination = destination_queries(dest, english=english)
    if intent.duration_days:
        destination[-1:] = [f"{dest} Cameroun itinéraire {intent.duration_days} jours"]
    budget = MAX_ROUTE_QUERIES - len(destination)
    return transport[:budget], destination


def route_queries(intent: IntentResult) -> list[str]:
    transport, destination = route_query_phases(intent)
    return [*transport, *destination][:MAX_ROUTE_QUERIES]


def is_route_research(intent: IntentResult) -> bool:
    return bool(intent.destination) and intent.intent in _ROUTE_INTENTS


def dish_queries(intent: IntentResult) -> list[str]:
    dish = intent.dish or ""
    place = intent.city or ""
    if (intent.web_reason or "") == "FORCED_RESTAURANT_SEARCH" and place:
        return [
            f"restaurant {dish} {place} Cameroun",
            f"où manger {dish} à {place}",
            f"best restaurants {dish} {place} Cameroon",
        ]
    return [
        f"{dish} plat traditionnel camerounais",
        f"{dish} Cameroonian dish",
        f"{dish} Cameroun recette origine",
    ]


def build_image_query(intent: IntentResult, user_query: str = "") -> str:
    if intent.dish:
        return f"{intent.dish} plat camerounais"
    if intent.image_subject:
        folded = _fold(intent.image_subject)
        suffix = "" if "cameroun" in folded or "cameroon" in folded else " Cameroun"
        return f"{intent.image_subject}{suffix}"
    subject = intent.destination or intent.city or intent.location or intent.region
    if subject:
        return f"{subject} Cameroun"
    base = " ".join(strip_stopwords(user_query, drop={"photo", "photos", "image", "images"}))
    return f"{base} Cameroun".strip()


def build_queries(
    user_query: str,
    intent: IntentResult,
    *,
    llm_queries: list[str] | None = None,
    now: datetime | None = None,
) -> list[str]:
    if not llm_queries and intent.destination and intent.intent in _ROUTE_INTENTS:
        return route_queries(intent)
    if not llm_queries and intent.dish and intent.intent == "FOOD":
        return dish_queries(intent)
    if not llm_queries and intent.intent == "PLACE_SEARCH" and intent.city:
        return destination_queries(intent.city, english=(intent.language or "fr") == "en")
    fr_loc, en_loc = _region_labels(intent)
    has_loc = (fr_loc, en_loc) != ("Cameroun", "Cameroon")
    now_eff = now or datetime.now(timezone.utc)
    year = now_eff.year
    period = f"{_MONTHS_FR[now_eff.month - 1]} {year}" if _THIS_MONTH.search(user_query or "") else str(year)
    queries: list[str] = []

    for q in llm_queries or []:
        q = " ".join(str(q).split())[:120]
        folded = _fold(q)
        if not q:
            continue
        if "cameroun" not in folded and "cameroon" not in folded:
            q = f"{q} {fr_loc if has_loc else 'Cameroun'}"
        queries.append(q)

    if not queries:
        place_words = {_fold(w) for w in (intent.city or "").split()}
        base = strip_stopwords(user_query, drop_region_words=has_loc, drop=place_words)
        base_fr = " ".join(base).replace("pas_cher", "pas cher").replace("bon_marche", "bon marché")
        english = (intent.language or "fr") == "en"
        primary = f"{base_fr} {en_loc if english else fr_loc}".strip()
        queries.append(primary)
        if not english:
            base_en = " ".join(translate_to_en(base))
            queries.append(f"{base_en} {en_loc}".strip())
        else:
            queries.append(f"{base_fr} {fr_loc}".strip())
        if needs_freshness(intent):
            queries.append(f"{base_fr} {fr_loc} {period}".strip())
        else:
            topic = _topic_query(intent, fr_loc)
            if topic:
                queries.append(topic)

    out: list[str] = []
    for q in queries:
        cleaned = " ".join(q.split())
        if cleaned and cleaned.casefold() not in {o.casefold() for o in out}:
            out.append(cleaned)
    return out[:MAX_QUERIES]
