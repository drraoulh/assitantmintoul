"""Explainable place scoring for Agent 2."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.agents.knowledge.place_store import PlaceRecord, fold


@dataclass(frozen=True)
class ScoreBreakdown:
    score: float
    reasons: list[str]


def score_place(
    place: PlaceRecord,
    *,
    intent: str,
    query: str,
    city: str | None = None,
    region: str | None = None,
    place_name_hint: str | None = None,
    interests: list[str] | None = None,
) -> ScoreBreakdown:
    """Higher score = better structured match. Transparent additive weights."""
    q = fold(query)
    reasons: list[str] = []
    score = 0.0

    names = [
        fold(place.name),
        fold(place.name_fr or ""),
        fold(place.name_en or ""),
        fold(place.slug or ""),
    ]
    names = [n for n in names if n]

    # Exact / strong name match
    hint = fold(place_name_hint or "")
    for name in names:
        if hint and (hint == name or hint in name or name in hint):
            score += 0.55
            reasons.append("exact_name_match")
            break
        if name and len(name) >= 4 and name in q:
            score += 0.50
            reasons.append("query_contains_place_name")
            break

    # Mount Cameroon EN/FR alias (documented bilingual names only)
    if any("mont cameroun" in n or "mount cameroon" in n for n in names):
        if "mont cameroun" in q or "mount cameroon" in q:
            if "exact_name_match" not in reasons and "query_contains_place_name" not in reasons:
                score += 0.50
                reasons.append("bilingual_name_match")

    # City / region
    if city and place.city and fold(city) == fold(place.city):
        score += 0.25
        reasons.append("city_match")
    elif city and place.city and fold(city) in fold(place.city):
        score += 0.18
        reasons.append("city_partial")

    if region and place.region:
        from app.services.agents.knowledge.place_retriever import region_matches

        if region_matches(region, place.region):
            score += 0.15
            reasons.append("region_match")

    # Category / eco / culture
    cat_blob = fold(" ".join(place.categories))
    eco_blob = fold(" ".join(place.eco_tags) + " " + (place.eco_info or ""))
    cult_blob = fold((place.cultural_info or "") + " " + (place.cultural_zone or ""))

    if intent == "NATURE":
        if any(k in eco_blob or k in cat_blob for k in ("nature", "eco", "parc", "park", "garden", "wildlife", "forest", "natural")):
            score += 0.22
            reasons.append("nature_category_or_eco")
        if any(k in fold(" ".join(place.activities)) for k in ("hik", "trek", "wildlife", "nature", "forest")):
            score += 0.08
            reasons.append("nature_activity")

    if intent == "CULTURE":
        if cult_blob.strip():
            score += 0.22
            reasons.append("cultural_info_present")
        if interests and any(fold(i) == "culture" for i in interests):
            if "sawa" in q and "sawa" in cult_blob:
                score += 0.2
                reasons.append("cultural_zone_keyword")
            elif any(k in cult_blob for k in ("sawa", "bamil", "fang", "culture", "patrimoine")):
                score += 0.12
                reasons.append("culture_keyword")
        if "sawa" in q and "sawa" in cult_blob:
            score += 0.15
            reasons.append("sawa_match")

    if intent == "FOOD":
        if any(k in cat_blob or k in fold(place.description or "") for k in ("food", "cuisine", "gastr", "restaurant", "plat")):
            score += 0.2
            reasons.append("food_category")

    if intent in {"HOTEL", "BOOKING"}:
        if any(k in cat_blob or k in q for k in ("hotel", "hôtel", "lodg", "heberg")):
            score += 0.2
            reasons.append("hotel_category")

    if intent in {"ITINERARY", "BUDGET_TRIP", "PLACE_SEARCH"}:
        if city and place.city and fold(city) == fold(place.city):
            score += 0.05
        if place.estimated_cost_xaf is not None and intent == "BUDGET_TRIP":
            score += 0.08
            reasons.append("has_cost")

    # Soft text overlap (capped — never invents places)
    blob = place.searchable_blob()
    tokens = [t for t in q.split() if len(t) >= 4]
    hits = sum(1 for t in tokens if t in blob)
    if hits:
        bonus = min(0.12, 0.03 * hits)
        score += bonus
        reasons.append(f"text_overlap:{hits}")

    return ScoreBreakdown(score=min(1.0, score), reasons=reasons)


def passes_hard_filter(place: PlaceRecord, intent: str, query: str) -> bool:
    """Minimum relevance gate per intent — reject popular-but-irrelevant places."""
    q = fold(query)
    cat = fold(" ".join(place.categories))
    eco = fold(" ".join(place.eco_tags) + " " + (place.eco_info or ""))
    cult = fold((place.cultural_info or "") + " " + (place.cultural_zone or ""))
    desc = fold(place.description or "")
    acts = fold(" ".join(place.activities))
    name = fold(place.name)

    if intent == "NATURE":
        return any(
            k in eco or k in cat or k in acts or k in desc or k in name
            for k in (
                "nature",
                "eco",
                "parc",
                "park",
                "garden",
                "natural",
                "wildlife",
                "forest",
                "foret",
                "reserve",
                "réserve",
                "hik",
                "trek",
                "mont",
                "volcan",
            )
        )

    if intent == "CULTURE":
        if "sawa" in q:
            # Prefer Sawa matches; still allow other cultural places as weak candidates
            # only when they carry cultural_info (knowledge_chunks cover Sawa docs).
            return (
                "sawa" in cult
                or "sawa" in desc
                or "sawa" in name
                or bool(cult.strip())
            )
        return bool(cult.strip()) or any(
            k in cat or k in cult for k in ("culture", "museum", "musee", "patrimoine", "chief", "palace")
        )

    if intent == "FOOD":
        # Prefer knowledge; places only if food-related.
        # Use word-ish checks — bare "plat" must not match "plateaux".
        import re

        blob = f"{cat} {desc} {name}"
        # Hotels are not restaurants for FOOD intent (even if they mention a restaurant).
        if any(k in cat or k in name for k in ("hotel", "hôtel", "lodg", "resort", "auberge", "camping")):
            return False
        return any(
            k in blob
            for k in ("food", "cuisine", "gastr", "restaurant", "ndole", "ndolé", "marché", "market", "achu", "koki")
        ) or bool(re.search(r"\bplats?\b", blob))

    if intent in {"HOTEL", "BOOKING"}:
        return any(k in cat or k in desc or k in name for k in ("hotel", "hôtel", "lodg", "resort", "auberge"))

    if intent == "PLACE_DETAILS":
        # Name must appear somehow (caller also scores).
        return True

    return True
