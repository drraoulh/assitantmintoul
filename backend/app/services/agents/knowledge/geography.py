"""Structured Cameroon geography graph (Phase 2.8).

Qwen-free, deterministic lookups for admin relationships.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from app.services.agents.knowledge.place_store import fold

_DATA_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "geography" / "cameroon_admin.json"
)

GeoRelation = Literal[
    "BELONGS_TO",
    "HAS_CAPITAL",
    "CONTAINS",
    "LOCATED_IN",
    "NEAR",
    "PART_OF_REGION",
    "PART_OF_DIVISION",
    "IS_REGION_CAPITAL",
    "IS_NOT_EQUIVALENT",
]


@dataclass(frozen=True)
class GeoFact:
    subject: str
    relation: GeoRelation
    object: str
    text_fr: str
    text_en: str
    source: str | None = None
    entity_ids: tuple[str, ...] = ()

    def as_evidence_content(self, *, language: str = "fr") -> str:
        body = self.text_en if language == "en" else self.text_fr
        if self.source:
            return f"{body} (source: {self.source})"
        return body


@dataclass
class GeographyIndex:
    country: dict[str, Any]
    regions: dict[str, dict[str, Any]]
    divisions: dict[str, dict[str, Any]]
    cities: dict[str, dict[str, Any]]
    localities: dict[str, dict[str, Any]]
    alias_to_city: dict[str, str] = field(default_factory=dict)
    alias_to_region: dict[str, str] = field(default_factory=dict)
    alias_to_division: dict[str, str] = field(default_factory=dict)
    alias_to_locality: dict[str, str] = field(default_factory=dict)


@lru_cache(maxsize=1)
def load_geography() -> GeographyIndex:
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    regions = {r["id"]: r for r in raw.get("regions", [])}
    divisions = {d["id"]: d for d in raw.get("divisions", [])}
    cities = {c["id"]: c for c in raw.get("cities", [])}
    localities = {loc["id"]: loc for loc in raw.get("localities", [])}

    idx = GeographyIndex(
        country=raw.get("country") or {},
        regions=regions,
        divisions=divisions,
        cities=cities,
        localities=localities,
    )
    for cid, city in cities.items():
        for alias in [city.get("name_fr"), city.get("name_en"), *city.get("aliases", [])]:
            if alias:
                idx.alias_to_city[fold(str(alias))] = cid
        idx.alias_to_city[fold(cid)] = cid
    for rid, region in regions.items():
        for alias in [region.get("name_fr"), region.get("name_en")]:
            if alias:
                idx.alias_to_region[fold(str(alias))] = rid
        if rid == "ouest":
            idx.alias_to_region["west"] = rid
            idx.alias_to_region["west region"] = rid
            idx.alias_to_region["region de l ouest"] = rid
            idx.alias_to_region["region ouest"] = rid
        idx.alias_to_region[fold(rid)] = rid
    for did, div in divisions.items():
        for alias in [div.get("name_fr"), div.get("name_en")]:
            if alias:
                idx.alias_to_division[fold(str(alias))] = did
        idx.alias_to_division[fold(did)] = did
    for lid, loc in localities.items():
        for alias in [loc.get("name_fr"), loc.get("name_en")]:
            if alias:
                idx.alias_to_locality[fold(str(alias))] = lid
        idx.alias_to_locality[fold(lid)] = lid
    return idx


def clear_geography_cache() -> None:
    load_geography.cache_clear()


def resolve_city_id(name: str | None, index: GeographyIndex | None = None) -> str | None:
    if not name:
        return None
    idx = index or load_geography()
    return idx.alias_to_city.get(fold(name))


def resolve_region_id(name: str | None, index: GeographyIndex | None = None) -> str | None:
    if not name:
        return None
    idx = index or load_geography()
    return idx.alias_to_region.get(fold(name))


def city_admin_chain(city_name: str, index: GeographyIndex | None = None) -> dict[str, Any] | None:
    idx = index or load_geography()
    cid = resolve_city_id(city_name, idx)
    if not cid:
        return None
    city = idx.cities[cid]
    division = idx.divisions.get(city.get("division_id") or "")
    region = idx.regions.get(city.get("region_id") or "")
    return {
        "city_id": cid,
        "city": city.get("name_fr"),
        "division_id": city.get("division_id"),
        "division": (division or {}).get("name_fr"),
        "region_id": city.get("region_id"),
        "region": (region or {}).get("name_fr"),
        "is_region_capital": bool(city.get("is_region_capital")),
        "country": idx.country.get("name_fr"),
    }


def _find_city_in_query(q: str, idx: GeographyIndex) -> str | None:
    # Longer aliases first to avoid partial misses
    aliases = sorted(idx.alias_to_city.keys(), key=len, reverse=True)
    for alias in aliases:
        if alias and re.search(rf"\b{re.escape(alias)}\b", q):
            return idx.alias_to_city[alias]
    return None


def _find_region_in_query(q: str, idx: GeographyIndex) -> str | None:
    aliases = sorted(idx.alias_to_region.keys(), key=len, reverse=True)
    for alias in aliases:
        if alias and re.search(rf"\b{re.escape(alias)}\b", q):
            return idx.alias_to_region[alias]
    return None


def answer_geo_query(query: str, *, language: str = "fr") -> list[GeoFact]:
    """Deterministic answers for simple geography questions."""
    idx = load_geography()
    q = fold(query)
    lang = "en" if (language or "fr").lower().startswith("en") else "fr"

    # Region ≈ city confusion (Ouest == Bafoussam?)
    if (
        ("ouest" in q or "west" in q)
        and "bafoussam" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Ouest",
                relation="IS_NOT_EQUIVALENT",
                object="Bafoussam",
                text_fr=(
                    "Pas exactement. L’Ouest est une région du Cameroun, "
                    "et Bafoussam en est le chef-lieu."
                ),
                text_en=(
                    "Not exactly. The West is a region of Cameroon, "
                    "and Bafoussam is its capital (chef-lieu)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("ouest", "bafoussam"),
            )
        ]

    # Capital / chef-lieu of a region
    if re.search(r"capitale|chef[- ]lieu|capital\s+of", q):
        rid = _find_region_in_query(q, idx)
        if rid and rid in idx.regions:
            region = idx.regions[rid]
            city = idx.cities.get(region.get("capital_city_id") or "")
            if city:
                cname = city["name_en"] if lang == "en" else city["name_fr"]
                rname = region["name_en"] if lang == "en" else region["name_fr"]
                if lang == "en":
                    text_en = f"{cname} is the capital (chef-lieu) of the {rname} region of Cameroon."
                    text_fr = f"{cname} est le chef-lieu de la région {rname}."
                else:
                    if rid == "ouest":
                        text_fr = "Bafoussam est le chef-lieu de la région de l’Ouest du Cameroun."
                    else:
                        text_fr = f"{cname} est le chef-lieu de la région {rname} du Cameroun."
                    text_en = f"{cname} is the capital of the {rname} region."
                return [
                    GeoFact(
                        subject=cname,
                        relation="IS_REGION_CAPITAL",
                        object=rname,
                        text_fr=text_fr,
                        text_en=text_en,
                        source=region.get("source"),
                        entity_ids=(city["id"], rid),
                    )
                ]

    # Lac Baleng / Baleng locality
    if "lac baleng" in q or re.search(r"\bbaleng\b", q):
        return [
            GeoFact(
                subject="Lac Baleng",
                relation="LOCATED_IN",
                object="Baleng / Bafoussam / Mifi / Ouest",
                text_fr=(
                    "Le Lac Baleng se trouve à Baleng, dans les environs de Bafoussam "
                    "(département de la Mifi, région de l’Ouest)."
                ),
                text_en=(
                    "Lake Baleng is in Baleng, near Bafoussam "
                    "(Mifi department, West region)."
                ),
                source="Sites touristiques Ouest / localité Baleng",
                entity_ids=("baleng", "bafoussam", "mifi", "ouest"),
            )
        ]

    # Lac / Mont Mbapit
    if "mbapit" in q:
        return [
            GeoFact(
                subject="Mbapit",
                relation="LOCATED_IN",
                object="Mbapit / Foumban / Noun / Ouest",
                text_fr=(
                    "Le lac et le mont Mbapit se trouvent à Mbapit, entre Foumbot et Foumban "
                    "(département du Noun, région de l’Ouest)."
                ),
                text_en=(
                    "Lake and Mount Mbapit are at Mbapit, between Foumbot and Foumban "
                    "(Noun department, West region)."
                ),
                source="Sites touristiques Ouest / localité Mbapit",
                entity_ids=("mbapit", "foumban", "noun", "ouest"),
            )
        ]

    city_id = _find_city_in_query(q, idx)
    if city_id:
        city = idx.cities[city_id]
        region = idx.regions.get(city.get("region_id") or "")
        division = idx.divisions.get(city.get("division_id") or "")
        cname = city["name_en"] if lang == "en" else city["name_fr"]

        if re.search(r"d[eé]partement|division|department", q) and division:
            dname = division["name_en"] if lang == "en" else division["name_fr"]
            if lang == "en":
                text_en = f"{cname} is in the {dname} department."
                text_fr = f"{cname} se trouve dans le département de {dname}."
            else:
                if division["id"] == "mifi":
                    text_fr = f"{cname} se trouve dans le département de la Mifi."
                elif division["id"] == "menoua":
                    text_fr = f"{cname} se trouve dans le département de la Menoua."
                else:
                    text_fr = f"{cname} se trouve dans le département du {dname}."
                text_en = f"{cname} is in the {dname} department."
            return [
                GeoFact(
                    subject=cname,
                    relation="PART_OF_DIVISION",
                    object=dname,
                    text_fr=text_fr,
                    text_en=text_en,
                    source=city.get("source"),
                    entity_ids=(city_id, division["id"]),
                )
            ]

        if region and re.search(
            r"r[eé]gion|region|where|o[uù]\b|dans\s+quel|se\s+trouve",
            q,
        ):
            rname = region["name_en"] if lang == "en" else region["name_fr"]
            rid = region["id"]
            if lang == "en":
                text_en = f"{cname} is in the {rname} region of Cameroon."
                text_fr = f"{cname} se trouve dans la région {rname}."
            else:
                if rid == "ouest":
                    text_fr = f"{cname} se trouve dans la région de l’Ouest du Cameroun."
                else:
                    text_fr = f"{cname} se trouve dans la région {rname} du Cameroun."
                text_en = f"{cname} is in the {rname} region of Cameroon."
            return [
                GeoFact(
                    subject=cname,
                    relation="PART_OF_REGION",
                    object=rname,
                    text_fr=text_fr,
                    text_en=text_en,
                    source=city.get("source"),
                    entity_ids=(city_id, rid),
                )
            ]

    return []


def nearby_place_city_keys(city_name: str, index: GeographyIndex | None = None) -> set[str]:
    """Folded city/locality names allowed as IN_CITY or NEARBY for a hub city."""
    idx = index or load_geography()
    cid = resolve_city_id(city_name, idx)
    if not cid:
        return {fold(city_name)} if city_name else set()
    city = idx.cities[cid]
    keys = {fold(city.get("name_fr") or ""), fold(city.get("name_en") or ""), fold(cid)}
    div_id = city.get("division_id")
    for loc in idx.localities.values():
        if loc.get("city_id") == cid or (div_id and loc.get("division_id") == div_id):
            keys.add(fold(loc.get("name_fr") or ""))
            keys.add(fold(loc.get("name_en") or ""))
    # Bafoussam II / municipality variants often appear as city field
    if cid == "bafoussam":
        keys.update({"bafoussam ii", "bafoussam 2", "bafoussam i"})
    return {k for k in keys if k}


def is_nearby_query(query: str) -> bool:
    q = fold(query)
    return any(
        tok in q
        for tok in (
            "autour",
            "alentours",
            "environs",
            "proche",
            "nearby",
            "near ",
            "around",
            "proximite",
            "proximité",
        )
    )


def is_geo_simple_query(query: str) -> bool:
    q = fold(query)
    patterns = (
        r"dans\s+quelle\s+r[eé]gion",
        r"which\s+region",
        r"capitale\s+de",
        r"chef[- ]lieu",
        r"capital\s+of",
        r"d[eé]partement",
        r"department",
        r"c[' ]?est\s+bafoussam",
        r"ouest.{0,30}bafoussam",
        r"bafoussam.{0,30}ouest",
        r"lac\s+baleng\s+(est\s+)?o[uù]",
        r"where\s+is\s+(?:lake\s+)?baleng",
        r"(?:lac|mont|lake|mount)?\s*mbapit",
        r"o[uù]\s+est\s+(?:le\s+|la\s+|l['’])?(?:lac|mont|lake|mount)?\s*mbapit",
        r"where\s+is\s+(?:lake\s+|mount\s+)?mbapit",
    )
    if any(re.search(p, q) for p in patterns):
        return True
    # "Où est … ?" / "where is …" for entities we can answer from the geo graph
    if re.search(r"\b(?:o[uù]\s+est|where\s+is|se\s+trouve|localisation)\b", q):
        if answer_geo_query(query):
            return True
    return False
