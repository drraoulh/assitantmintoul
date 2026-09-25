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
    missing: list[str] | None = None,  # noqa: ARG001 — kept for callers
) -> list[str]:
    """Compatibility wrapper — see ``query_builder.build_queries``."""
    from app.services.agents.web_research.query_builder import build_queries

    return build_queries(user_query, intent)
