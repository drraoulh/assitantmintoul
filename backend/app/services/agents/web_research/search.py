"""Build grounded search queries for the Web Research Agent."""

from __future__ import annotations

from app.services.agents.intent.models import IntentResult


def build_search_queries(
    user_query: str,
    intent: IntentResult,
    *,
    missing: list[str] | None = None,
) -> list[str]:
    """Return 1–4 focused queries. Prefer institutional site operators when useful."""
    q = (user_query or "").strip()
    location = intent.location or intent.region or intent.city or ""
    queries: list[str] = []

    if q:
        queries.append(q)

    intent_name = intent.intent
    loc = location.strip()

    if intent_name == "FOOD":
        if loc:
            queries.append(f"traditional food cuisine {loc} Cameroon")
            queries.append(f"plats traditionnels {loc} Cameroun")
            queries.append(f"site:mintoul.gov.cm gastronomie {loc}")
        else:
            queries.append("traditional Cameroonian cuisine dishes")
            queries.append("plats traditionnels Cameroun gastronomie")
    elif intent_name in {"CULTURE", "TOURISM_INFO"}:
        if loc:
            queries.append(f"culture tourisme {loc} Cameroun")
            queries.append(f"site:gov.cm {loc} Cameroun")
        else:
            queries.append(f"{q} Cameroun culture")
    elif intent_name == "WEB_SEARCH":
        queries.append(q)
        if "site:" not in q.casefold():
            queries.append(f"{q} Cameroun")
    else:
        if loc and loc.casefold() not in q.casefold():
            queries.append(f"{q} {loc} Cameroun")

    if missing and "knowledge_chunks" in missing and loc:
        queries.append(f"{intent_name.lower()} {loc} Cameroon tourism")

    # Deduplicate preserving order
    out: list[str] = []
    for item in queries:
        cleaned = " ".join(item.split())
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out[:4]
