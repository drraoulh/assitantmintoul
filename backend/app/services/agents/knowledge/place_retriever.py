"""Structured place retrieval — city/region/name/eco/culture + geo hierarchy."""

from __future__ import annotations

import time

from app.core.config import get_settings
from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.geography import (
    city_admin_chain,
    is_nearby_query,
    nearby_place_city_keys,
)
from app.services.agents.knowledge.models import PlaceEvidence
from app.services.agents.knowledge.place_store import PlaceIndex, PlaceRecord, fold
from app.services.agents.knowledge.scoring import passes_hard_filter, score_place
from app.services.agents.knowledge.topk import place_top_k

# Cities that must never be treated as "in Bafoussam"
_NOT_BAFOUSSAM = {
    "foumban",
    "dschang",
    "bandjoun",
    "baham",
    "mbouda",
    "bangangte",
    "bangangté",
    "bafang",
    "batcham",
    "bana",
    "batoufam",
    "penka-michel",
    "foumbot",
    "santchou",
    "noun",
}
_NOT_DOUALA = {
    "edea",
    "edéa",
    "nkongsamba",
    "melong",
    "yabassi",
    "mouanko",
    "kribi",
    "limbe",
    "limbé",
    "buea",
}
_NOT_YAOUNDE = {
    "mbalmayo",
    "mfou",
    "soa",
    "monatele",
    "monatélé",
    "nkolmetet",
    "nkolmétet",
    "douala",
    "bafoussam",
}
_NOT_KRIBI = {
    "ebolowa",
    "sangmelima",
    "sangmélima",
    "campo",
    "ambam",
    "douala",
    "yaounde",
    "yaoundé",
}
_NOT_LIMBE = {
    "buea",
    "kumba",
    "mundemba",
    "mamfe",
    "tiko",
    "douala",
    "kribi",
    "yaounde",
    "yaoundé",
}
_NOT_BUEA = {
    "limbe",
    "limbé",
    "kumba",
    "mundemba",
    "mamfe",
    "douala",
    "kribi",
    "yaounde",
    "yaoundé",
}
_NOT_BAMENDA = {
    "bafut",
    "oku",
    "kumbo",
    "wum",
    "fundong",
    "ndop",
    "nkambe",
    "mbengwi",
    "bafoussam",
    "douala",
    "buea",
}
_NOT_MAROUA = {
    "waza",
    "rhumsiki",
    "maga",
    "boboyo",
    "kola",
    "garoua",
    "douala",
    "yaounde",
    "yaoundé",
    "mokolo",
}
_NOT_NGAOUNDERE = {
    "banyo",
    "meiganga",
    "tibati",
    "tignere",
    "tignère",
    "garoua",
    "maroua",
    "douala",
    "yaounde",
    "yaoundé",
}
_NOT_GAROUA = {
    "figuil",
    "tchollire",
    "tcholliré",
    "touboro",
    "guider",
    "poli",
    "maroua",
    "ngaoundere",
    "ngaoundéré",
    "douala",
    "yaounde",
    "yaoundé",
}
_NOT_BERTOUA = {
    "batouri",
    "abong-mbang",
    "abong mbang",
    "yokadouma",
    "moloundou",
    "somalomo",
    "douala",
    "yaounde",
    "yaoundé",
    "garoua",
}

_REGION_ALIASES = {
    "west": "ouest",
    "east": "est",
    "north": "nord",
    "south": "sud",
    "adamawa": "adamaoua",
    "far north": "extreme-nord",
    "extreme nord": "extreme-nord",
    "north-west": "nord-ouest",
    "northwest": "nord-ouest",
    "nord ouest": "nord-ouest",
    "south-west": "sud-ouest",
    "southwest": "sud-ouest",
    "sud ouest": "sud-ouest",
    "far north": "extreme-nord",
    "far-north": "extreme-nord",
    "extreme nord": "extreme-nord",
    "adamawa": "adamaoua",
}


def _norm_region(value: str | None) -> str:
    raw = fold(value or "").replace("é", "e")
    raw = raw.replace(" ", "-")
    return _REGION_ALIASES.get(raw, raw)


def region_matches(wanted: str | None, place_region: str | None) -> bool:
    """Exact region match — 'Ouest' must not match 'Nord-Ouest' / 'Sud-Ouest'."""
    w = _norm_region(wanted)
    p = _norm_region(place_region)
    if not w or not p:
        return False
    if w == p:
        return True
    # Multi-label place regions e.g. "Sud / Est"
    parts = [ _norm_region(part) for part in (place_region or "").replace("/", ",").split(",") ]
    return w in parts


class PlaceRetriever:
    """Search published places only. Never invents place_id / costs / activities."""

    def __init__(self, index: PlaceIndex) -> None:
        self._index = index

    def retrieve(
        self,
        query: str,
        intent: IntentResult,
        *,
        top_k: int | None = None,
        include_unpublished: bool = False,
    ) -> tuple[list[PlaceEvidence], float]:
        started = time.perf_counter()
        limit = place_top_k(intent.intent, top_k)
        place_intents = {
            "PLACE_SEARCH",
            "PLACE_DETAILS",
            "ITINERARY",
            "BUDGET_TRIP",
            "NATURE",
            "CULTURE",
            "HOTEL",
            "BOOKING",
            "FOOD",
            "TOURISM_INFO",
        }
        if limit <= 0 or (
            not intent.needs_places and intent.intent not in place_intents
        ):
            return [], (time.perf_counter() - started) * 1000.0

        city = intent.city
        region = intent.region
        place_hint = intent.location if intent.intent == "PLACE_DETAILS" else None
        geo_on = bool(get_settings().knowledge_geography_enabled)
        want_nearby = geo_on and (
            is_nearby_query(query) or "nearby" in {fold(i) for i in (intent.interests or [])}
        )
        region_only = bool(region) and not city
        nearby_keys = nearby_place_city_keys(city) if (geo_on and city) else set()
        hub = fold(city) if city else ""

        city_filter_intents = {
            "PLACE_SEARCH",
            "ITINERARY",
            "BUDGET_TRIP",
            "HOTEL",
            "BOOKING",
            "TOURISM_INFO",
            "NATURE",
            "CULTURE",
        }
        region_filter_intents = {
            "PLACE_SEARCH",
            "ITINERARY",
            "NATURE",
            "TOURISM_INFO",
            "CULTURE",
            "FOOD",
            "HOTEL",
        }

        candidates: list[tuple[float, list[str], PlaceRecord, str]] = []
        for place in self._index.places:
            if not include_unpublished and not place.is_published:
                continue

            scope = "UNKNOWN"
            place_city = fold(place.city or "")

            if city and intent.intent in city_filter_intents:
                in_hub = bool(place_city and hub and hub in place_city)
                in_nearby = bool(geo_on and place_city and place_city in nearby_keys and not in_hub)
                # Exclude other West cities from Bafoussam city queries
                if hub == "bafoussam" and place_city in _NOT_BAFOUSSAM:
                    continue
                if hub == "douala" and place_city in _NOT_DOUALA:
                    continue
                if hub == "yaoundé" or hub == "yaounde":
                    if place_city in _NOT_YAOUNDE:
                        continue
                if hub == "kribi" and place_city in _NOT_KRIBI:
                    continue
                if hub in {"limbe", "limbé"} and place_city in _NOT_LIMBE:
                    continue
                if hub == "buea" and place_city in _NOT_BUEA:
                    continue
                if hub == "bamenda" and place_city in _NOT_BAMENDA:
                    continue
                if hub == "maroua" and place_city in _NOT_MAROUA:
                    continue
                if hub in {"ngaoundere", "ngaoundéré"} and place_city in _NOT_NGAOUNDERE:
                    continue
                if hub == "garoua" and place_city in _NOT_GAROUA:
                    continue
                if hub == "bertoua" and place_city in _NOT_BERTOUA:
                    continue
                if in_hub:
                    scope = "IN_CITY"
                elif in_nearby and (want_nearby or geo_on):
                    # For plain "visit Bafoussam", include tagged nearby localities
                    # (Baleng, Bamougoum) but not Foumban/Dschang.
                    scope = "NEARBY"
                    if not want_nearby and place_city not in nearby_keys - {hub}:
                        # keep only explicit nearby localities from geo graph
                        if hub == "bafoussam":
                            if place_city not in {"baleng", "bamougoum"} and "bafoussam" not in place_city:
                                continue
                        elif hub == "douala":
                            if place_city not in {
                                "bonanjo",
                                "akwa",
                                "bonapriso",
                                "deido",
                                "bonamoussadi",
                                "manoka",
                            } and "douala" not in place_city:
                                continue
                        elif hub in {"yaounde", "yaoundé"}:
                            if place_city not in {
                                "mokolo",
                                "bastos",
                                "nsimalen",
                                "mvog-mbi",
                            } and "yaounde" not in place_city and "yaoundé" not in place_city:
                                continue
                        elif hub == "kribi":
                            if place_city not in {"lobe", "lobé", "grand-batanga", "grand batanga", "bwambe", "bwambé"} and "kribi" not in place_city:
                                continue
                        elif hub in {"limbe", "limbé"}:
                            if place_city not in {
                                "down beach",
                                "down-beach",
                                "bimbia",
                                "idenau",
                            } and "limbe" not in place_city and "limbé" not in place_city:
                                continue
                        elif hub == "buea":
                            if place_city not in {
                                "debunscha",
                                "mont cameroun",
                            } and "buea" not in place_city:
                                continue
                        elif hub == "bamenda":
                            if place_city not in {
                                "station hill",
                                "station-hill",
                                "fungom",
                            } and "bamenda" not in place_city:
                                continue
                        elif hub == "maroua":
                            if place_city not in {
                                "mandara",
                            } and "maroua" not in place_city:
                                continue
                        elif hub in {"ngaoundere", "ngaoundéré"}:
                            if place_city not in {
                                "beka-hossere",
                                "beka-hosséré",
                                "lac-tison",
                                "lac tison",
                            } and "ngaoundere" not in place_city and "ngaoundéré" not in place_city:
                                continue
                        elif hub == "garoua":
                            if place_city not in {
                                "plateau",
                                "plateau-garoua",
                                "lagdo",
                            } and "garoua" not in place_city:
                                continue
                        elif hub == "bertoua":
                            if place_city not in {
                                "koume",
                                "koumé",
                            } and "bertoua" not in place_city:
                                continue
                        else:
                            continue
                else:
                    continue

            if region_only and intent.intent in region_filter_intents:
                if region_matches(region, place.region):
                    scope = "IN_REGION"
                else:
                    continue

            if not passes_hard_filter(place, intent.intent, query):
                continue

            breakdown = score_place(
                place,
                intent=intent.intent,
                query=query,
                city=city,
                region=region,
                place_name_hint=place_hint,
                interests=intent.interests,
            )
            min_score = 0.15 if intent.intent != "PLACE_DETAILS" else 0.35
            if intent.intent == "PLACE_SEARCH" and city:
                min_score = 0.18
            if intent.intent in {"ITINERARY", "BUDGET_TRIP"} and city:
                min_score = 0.18
            score = breakdown.score
            reasons = list(breakdown.reasons)
            if scope == "NEARBY":
                score = max(0.0, score - 0.03)
                reasons = reasons + ["nearby_scope"]
            if score < min_score:
                continue
            candidates.append((score, reasons, place, scope))

        # Prefer IN_CITY, then NEARBY, then region; within group by score
        candidates.sort(
            key=lambda item: (
                0 if item[3] == "IN_CITY" else 1 if item[3] == "NEARBY" else 2,
                -item[0],
            )
        )
        evidences = [
            _to_evidence(place, score, reasons, scope=scope, city_hub=city)
            for score, reasons, place, scope in candidates[:limit]
        ]
        elapsed = (time.perf_counter() - started) * 1000.0
        return evidences, elapsed


def _to_evidence(
    place: PlaceRecord,
    score: float,
    reasons: list[str],
    *,
    scope: str = "UNKNOWN",
    city_hub: str | None = None,
) -> PlaceEvidence:
    categories = list(place.categories)
    source_ids = [place.source_id] if place.source_id else []
    chain = None
    if get_settings().knowledge_geography_enabled:
        chain = city_admin_chain(place.city or city_hub or "")
    scope_lit = scope if scope in {"IN_CITY", "NEARBY", "IN_REGION", "UNKNOWN"} else "UNKNOWN"
    return PlaceEvidence(
        place_id=place.place_id,
        name=place.name,
        city=place.city,
        region=place.region,
        description=_clip(place.description, 400),
        cultural_info=_clip(place.cultural_info, 300),
        eco_info=_clip(place.eco_info, 300),
        activities=list(place.activities),
        category=categories,
        eco_tags=list(place.eco_tags),
        cultural_zone=place.cultural_zone,
        estimated_cost_xaf=place.estimated_cost_xaf,
        recommended_duration_hours=place.recommended_duration_hours,
        best_period=place.best_period,
        latitude=place.latitude,
        longitude=place.longitude,
        source_ids=source_ids,
        evidence_score=round(min(1.0, score), 3),
        is_published=place.is_published,
        match_reasons=reasons,
        location_scope=scope_lit,  # type: ignore[arg-type]
        locality=place.city if scope_lit == "NEARBY" else None,
        division=(chain or {}).get("division") if chain else None,
    )


def _clip(text: str | None, max_chars: int) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"
