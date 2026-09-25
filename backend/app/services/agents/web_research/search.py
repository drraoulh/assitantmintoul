"""Build grounded search queries for the Web Research Agent."""

from __future__ import annotations

from app.services.agents.intent.models import IntentResult

# Map Cameroon region labels → English/French search variants (avoid FR "Sud-Ouest").
_REGION_QUERY: dict[str, tuple[str, str]] = {
    "sud-ouest": ("South-West Cameroon", "Sud-Ouest Cameroun"),
    "south-west": ("South-West Cameroon", "Sud-Ouest Cameroun"),
    "southwest": ("South-West Cameroon", "Sud-Ouest Cameroun"),
    "nord-ouest": ("North-West Cameroon", "Nord-Ouest Cameroun"),
    "north-west": ("North-West Cameroon", "Nord-Ouest Cameroun"),
    "ouest": ("West Cameroon", "Ouest Cameroun"),
    "west": ("West Cameroon", "Ouest Cameroun"),
    "littoral": ("Littoral Cameroon", "Littoral Cameroun"),
    "centre": ("Centre Cameroon", "Centre Cameroun"),
    "sud": ("South Cameroon", "Sud Cameroun"),
    "south": ("South Cameroon", "Sud Cameroun"),
    "nord": ("North Cameroon", "Nord Cameroun"),
    "north": ("North Cameroon", "Nord Cameroun"),
    "extrême-nord": ("Far North Cameroon", "Extrême-Nord Cameroun"),
    "extreme-nord": ("Far North Cameroon", "Extrême-Nord Cameroun"),
    "adamaoua": ("Adamawa Cameroon", "Adamaoua Cameroun"),
    "est": ("East Cameroon", "Est Cameroun"),
    "east": ("East Cameroon", "Est Cameroun"),
}


def _region_variants(location: str) -> tuple[str, str]:
    key = (location or "").strip().casefold().replace("é", "e")
    key = key.replace("south west", "southwest").replace("south-west", "southwest")
    for alias, variants in _REGION_QUERY.items():
        if alias in key or key == alias:
            return variants
    loc = (location or "").strip()
    if loc:
        return (f"{loc} Cameroon", f"{loc} Cameroun")
    return ("Cameroon", "Cameroun")


def _ensure_cameroon_scope(query: str) -> str:
    """Disambiguate European 'Sud-Ouest' / 'Southwest' toward Cameroon."""
    q = " ".join((query or "").split())
    folded = q.casefold()
    if "cameroun" in folded or "cameroon" in folded:
        return q
    # Rewrite bare Sud-Ouest / Southwest toward Cameroon SW
    if "sud-ouest" in folded or "sud ouest" in folded or "southwest" in folded or "south-west" in folded:
        return f"{q} Cameroun Cameroon".strip()
    return f"{q} Cameroun".strip()


def build_search_queries(
    user_query: str,
    intent: IntentResult,
    *,
    missing: list[str] | None = None,
) -> list[str]:
    """Return 1–4 focused queries. Prefer institutional site operators when useful."""
    q = _ensure_cameroon_scope((user_query or "").strip())
    location = intent.location or intent.region or intent.city or ""
    en_loc, fr_loc = _region_variants(location)
    queries: list[str] = []

    if q:
        queries.append(q)

    intent_name = intent.intent

    if intent_name == "FOOD":
        queries.append(f"traditional food cuisine {en_loc}")
        queries.append(f"plats traditionnels gastronomie {fr_loc}")
        queries.append(f"site:mintoul.gov.cm gastronomie {fr_loc}")
    elif intent_name in {"CULTURE", "TOURISM_INFO"}:
        queries.append(f"culture tourisme {fr_loc}")
        queries.append(f"site:gov.cm tourisme {fr_loc}")
    elif intent_name == "WEB_SEARCH":
        queries.append(_ensure_cameroon_scope(user_query))
        if location:
            queries.append(f"festivals events {en_loc}")
            queries.append(f"festivals événements {fr_loc}")
        else:
            queries.append(f"{user_query} Cameroun tourisme")
        queries.append(f"site:mintoul.gov.cm {fr_loc or 'Cameroun'}")
    else:
        if location and location.casefold() not in q.casefold():
            queries.append(f"{q} {fr_loc}")

    if missing and "knowledge_chunks" in missing:
        queries.append(f"{intent_name.lower()} {en_loc} tourism")

    # Deduplicate preserving order
    out: list[str] = []
    for item in queries:
        cleaned = " ".join(item.split())
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out[:4]
