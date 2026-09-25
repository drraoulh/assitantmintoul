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

from app.services.agents.knowledge.national_facts import (
    NATIONAL_FACTS_SOURCE,
    answer_national_fact,
)
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
    "IS_NATIONAL_CAPITAL",
    "IS_NOT_EQUIVALENT",
    "NATIONAL_FACT",
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
        elif rid == "sud-ouest":
            idx.alias_to_region["south-west"] = rid
            idx.alias_to_region["southwest"] = rid
            idx.alias_to_region["south west"] = rid
            idx.alias_to_region["region du sud-ouest"] = rid
            idx.alias_to_region["region sud-ouest"] = rid
        elif rid == "nord-ouest":
            idx.alias_to_region["north-west"] = rid
            idx.alias_to_region["northwest"] = rid
            idx.alias_to_region["north west"] = rid
            idx.alias_to_region["region du nord-ouest"] = rid
            idx.alias_to_region["region nord-ouest"] = rid
        elif rid == "extreme-nord":
            idx.alias_to_region["far north"] = rid
            idx.alias_to_region["far-north"] = rid
            idx.alias_to_region["extreme nord"] = rid
            idx.alias_to_region["region de l extreme-nord"] = rid
            idx.alias_to_region["region extreme-nord"] = rid
        elif rid == "adamaoua":
            idx.alias_to_region["adamawa"] = rid
            idx.alias_to_region["region de l adamaoua"] = rid
            idx.alias_to_region["region adamaoua"] = rid
        elif rid == "nord":
            idx.alias_to_region["north region"] = rid
            idx.alias_to_region["region du nord"] = rid
            idx.alias_to_region["region nord"] = rid
        elif rid == "est":
            idx.alias_to_region["east"] = rid
            idx.alias_to_region["east region"] = rid
            idx.alias_to_region["region de l est"] = rid
            idx.alias_to_region["region est"] = rid
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


_EST_REGION_CUE = re.compile(r"(?:\bl['’ ]\s*est\b|\bregion\s+(?:de\s+l['’ ]\s*)?est\b|\beast\b)")


def _find_region_in_query(q: str, idx: GeographyIndex) -> str | None:
    aliases = sorted(idx.alias_to_region.keys(), key=len, reverse=True)
    for alias in aliases:
        if not alias or not re.search(rf"\b{re.escape(alias)}\b", q):
            continue
        # « est » is usually the verb (« quelle est… »); require an explicit region cue.
        if alias == "est" and not _EST_REGION_CUE.search(q):
            continue
        return idx.alias_to_region[alias]
    return None


_NATIONAL_CAPITAL = re.compile(
    r"capitale\s+(?:du\s+|de\s+)?(?:cameroun|pays)|capital\s+(?:city\s+)?of\s+cameroon|"
    r"cameroon['’]?s\s+capital"
)


def answer_geo_query(query: str, *, language: str = "fr") -> list[GeoFact]:
    """Deterministic answers for simple geography questions."""
    idx = load_geography()
    q = fold(query)
    lang = "en" if (language or "fr").lower().startswith("en") else "fr"

    # Region ≈ city confusion (Ouest == Bafoussam? / Littoral == Douala?)
    compound_ouest = any(
        c in q
        for c in (
            "sud-ouest",
            "sud ouest",
            "nord-ouest",
            "nord ouest",
            "south-west",
            "southwest",
            "south west",
            "north-west",
            "northwest",
            "north west",
        )
    )
    _COMPOUND_NORD_GEO = (
        "nord-ouest",
        "nord ouest",
        "north-west",
        "northwest",
        "north west",
        "extreme-nord",
        "extreme nord",
        "far north",
        "far-north",
    )
    if (
        not compound_ouest
        and ("ouest" in q or "west" in q)
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

    if (
        "littoral" in q
        and "douala" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Littoral",
                relation="IS_NOT_EQUIVALENT",
                object="Douala",
                text_fr=(
                    "Pas exactement. Le Littoral est une région du Cameroun, "
                    "et Douala en est le chef-lieu."
                ),
                text_en=(
                    "Not exactly. The Littoral is a region of Cameroon, "
                    "and Douala is its capital (chef-lieu)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("littoral", "douala"),
            )
        ]

    if (
        "centre" in q
        and "yaounde" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Centre",
                relation="IS_NOT_EQUIVALENT",
                object="Yaoundé",
                text_fr=(
                    "Pas exactement. Le Centre est une région du Cameroun, "
                    "et Yaoundé en est le chef-lieu (capitale politique)."
                ),
                text_en=(
                    "Not exactly. The Centre is a region of Cameroon, "
                    "and Yaoundé is its capital (political capital)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("centre", "yaounde"),
            )
        ]

    if (
        ("sud-ouest" in q or "sud ouest" in q or "south-west" in q or "southwest" in q or "south west" in q)
        and "buea" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Sud-Ouest",
                relation="IS_NOT_EQUIVALENT",
                object="Buea",
                text_fr=(
                    "Pas exactement. Le Sud-Ouest est une région du Cameroun, "
                    "et Buea en est le chef-lieu (Limbé est la station balnéaire)."
                ),
                text_en=(
                    "Not exactly. The South-West is a region of Cameroon, "
                    "and Buea is its capital (Limbe is the beach town)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("sud-ouest", "buea", "limbe"),
            )
        ]

    if (
        ("nord-ouest" in q or "nord ouest" in q or "north-west" in q or "northwest" in q or "north west" in q)
        and "bamenda" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Nord-Ouest",
                relation="IS_NOT_EQUIVALENT",
                object="Bamenda",
                text_fr=(
                    "Pas exactement. Le Nord-Ouest est une région du Cameroun, "
                    "et Bamenda en est le chef-lieu."
                ),
                text_en=(
                    "Not exactly. The North-West is a region of Cameroon, "
                    "and Bamenda is its capital (chef-lieu)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("nord-ouest", "bamenda"),
            )
        ]

    if (
        (
            "extreme-nord" in q
            or "extreme nord" in q
            or "far north" in q
            or "far-north" in q
        )
        and "maroua" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Extrême-Nord",
                relation="IS_NOT_EQUIVALENT",
                object="Maroua",
                text_fr=(
                    "Pas exactement. L’Extrême-Nord est une région du Cameroun, "
                    "et Maroua en est le chef-lieu (Waza / Rhumsiki sont des sites majeurs)."
                ),
                text_en=(
                    "Not exactly. The Far North is a region of Cameroon, "
                    "and Maroua is its capital (Waza / Rhumsiki are major sites)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("extreme-nord", "maroua", "waza"),
            )
        ]

    if (
        ("adamaoua" in q or "adamawa" in q)
        and "ngaoundere" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Adamaoua",
                relation="IS_NOT_EQUIVALENT",
                object="Ngaoundéré",
                text_fr=(
                    "Pas exactement. L’Adamaoua est une région du Cameroun, "
                    "et Ngaoundéré en est le chef-lieu."
                ),
                text_en=(
                    "Not exactly. Adamawa is a region of Cameroon, "
                    "and Ngaoundéré is its capital (chef-lieu)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("adamaoua", "ngaoundere"),
            )
        ]

    if (
        not any(c in q for c in _COMPOUND_NORD_GEO)
        and ("nord" in q or re.search(r"\bnorth\b", q))
        and "garoua" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Nord",
                relation="IS_NOT_EQUIVALENT",
                object="Garoua",
                text_fr=(
                    "Pas exactement. Le Nord est une région du Cameroun, "
                    "et Garoua en est le chef-lieu."
                ),
                text_en=(
                    "Not exactly. The North is a region of Cameroon, "
                    "and Garoua is its capital (chef-lieu)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("nord", "garoua"),
            )
        ]

    if (
        re.search(r"\b(?:r[eé]gion\s+de\s+l['’]?est|est\s+du\s+cameroun|east\s+region)\b", q)
        and "bertoua" in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Est",
                relation="IS_NOT_EQUIVALENT",
                object="Bertoua",
                text_fr=(
                    "Pas exactement. L’Est est une région du Cameroun, "
                    "et Bertoua en est le chef-lieu."
                ),
                text_en=(
                    "Not exactly. The East is a region of Cameroon, "
                    "and Bertoua is its capital (chef-lieu)."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("est", "bertoua"),
            )
        ]

    if (
        not compound_ouest
        and ("sud" in q or "south" in q)
        and "kribi" in q
        and "ouest" not in q
        and "west" not in q
        and re.search(r"c[' ]?est|est[- ]ce|nor\b|non\b|equals|same|region|région", q)
    ):
        return [
            GeoFact(
                subject="Sud",
                relation="IS_NOT_EQUIVALENT",
                object="Kribi",
                text_fr=(
                    "Pas exactement. Le Sud est une région du Cameroun "
                    "(chef-lieu Ebolowa) ; Kribi est sa principale station balnéaire."
                ),
                text_en=(
                    "Not exactly. The South is a region of Cameroon "
                    "(capital Ebolowa); Kribi is its main beach resort."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("sud", "kribi", "ebolowa"),
            )
        ]

    if _NATIONAL_CAPITAL.search(q):
        return [
            GeoFact(
                subject="Yaoundé",
                relation="IS_NATIONAL_CAPITAL",
                object="Cameroun",
                text_fr=(
                    "Yaoundé est la capitale politique du Cameroun ; "
                    "Douala en est la capitale économique."
                ),
                text_en=(
                    "Yaoundé is the political capital of Cameroon; "
                    "Douala is its economic capital."
                ),
                source="Découpage administratif officiel (10 régions)",
                entity_ids=("yaounde", "centre"),
            )
        ]

    national = answer_national_fact(query)
    if national is not None:
        return [
            GeoFact(
                subject="Cameroun",
                relation="NATIONAL_FACT",
                object=national.key,
                text_fr=national.text_fr,
                text_en=national.text_en,
                source=NATIONAL_FACTS_SOURCE,
                entity_ids=("cm",),
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
                    elif rid == "littoral":
                        text_fr = "Douala est le chef-lieu de la région du Littoral du Cameroun."
                    elif rid == "centre":
                        text_fr = "Yaoundé est le chef-lieu de la région du Centre du Cameroun (capitale politique)."
                    elif rid == "sud":
                        text_fr = "Ebolowa est le chef-lieu de la région du Sud du Cameroun."
                    elif rid == "sud-ouest":
                        text_fr = "Buea est le chef-lieu de la région du Sud-Ouest du Cameroun."
                    elif rid == "nord-ouest":
                        text_fr = "Bamenda est le chef-lieu de la région du Nord-Ouest du Cameroun."
                    elif rid == "extreme-nord":
                        text_fr = "Maroua est le chef-lieu de la région de l’Extrême-Nord du Cameroun."
                    elif rid == "adamaoua":
                        text_fr = "Ngaoundéré est le chef-lieu de la région de l’Adamaoua du Cameroun."
                    elif rid == "nord":
                        text_fr = "Garoua est le chef-lieu de la région du Nord du Cameroun."
                    elif rid == "est":
                        text_fr = "Bertoua est le chef-lieu de la région de l’Est du Cameroun."
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

    # Lobé falls
    if re.search(r"\blob[eé]\b", q) or "chutes de la lobe" in q or "chutes de la lobé" in q:
        return [
            GeoFact(
                subject="Chutes de la Lobé",
                relation="LOCATED_IN",
                object="Kribi / Océan / Sud",
                text_fr=(
                    "Les chutes de la Lobé se trouvent près de Kribi "
                    "(département de l’Océan, région du Sud)."
                ),
                text_en=(
                    "Lobé Falls are near Kribi "
                    "(Ocean department, South region)."
                ),
                source="Sites touristiques Sud / Kribi",
                entity_ids=("lobe", "kribi", "ocean", "sud"),
            )
        ]

    # Mont Cameroun
    if "mont cameroun" in q or "mount cameroon" in q:
        return [
            GeoFact(
                subject="Mont Cameroun",
                relation="LOCATED_IN",
                object="Buea / Fako / Sud-Ouest",
                text_fr=(
                    "Le Mont Cameroun se trouve près de Buea "
                    "(département du Fako, région du Sud-Ouest)."
                ),
                text_en=(
                    "Mount Cameroon is near Buea "
                    "(Fako department, South-West region)."
                ),
                source="Sites touristiques Sud-Ouest / Buea",
                entity_ids=("mont-cameroun", "buea", "fako", "sud-ouest"),
            )
        ]

    # Korup
    if "korup" in q:
        return [
            GeoFact(
                subject="Parc national de Korup",
                relation="LOCATED_IN",
                object="Mundemba / Ndian / Sud-Ouest",
                text_fr=(
                    "Le parc national de Korup s’atteint depuis Mundemba "
                    "(département du Ndian, région du Sud-Ouest)."
                ),
                text_en=(
                    "Korup National Park is accessed from Mundemba "
                    "(Ndian department, South-West region)."
                ),
                source="Sites touristiques Sud-Ouest / Korup",
                entity_ids=("korup", "mundemba", "ndian", "sud-ouest"),
            )
        ]

    # Palais de Bafut
    if re.search(r"(?:palais|chefferie)\s+(?:de\s+)?bafut|\bbafut\b", q) and re.search(
        r"o[uù]\s+est|where|se\s+trouve|localisation|r[eé]gion|d[eé]partement",
        q,
    ):
        return [
            GeoFact(
                subject="Palais de Bafut",
                relation="LOCATED_IN",
                object="Bafut / Mezam / Nord-Ouest",
                text_fr=(
                    "Le Palais de Bafut se trouve à Bafut "
                    "(département du Mezam, région du Nord-Ouest)."
                ),
                text_en=(
                    "Bafut Palace is in Bafut "
                    "(Mezam department, North-West region)."
                ),
                source="Sites touristiques Nord-Ouest / Bafut",
                entity_ids=("bafut", "mezam", "nord-ouest"),
            )
        ]

    # Lac Oku
    if ("lac oku" in q or re.search(r"\boku\b", q)) and re.search(
        r"o[uù]\s+est|where|se\s+trouve|localisation|r[eé]gion|lac",
        q,
    ):
        return [
            GeoFact(
                subject="Lac Oku",
                relation="LOCATED_IN",
                object="Oku / Boyo / Nord-Ouest",
                text_fr=(
                    "Le lac Oku se trouve à Oku "
                    "(département du Boyo, région du Nord-Ouest)."
                ),
                text_en=(
                    "Lake Oku is at Oku "
                    "(Boyo department, North-West region)."
                ),
                source="Sites touristiques Nord-Ouest / Oku",
                entity_ids=("oku", "boyo", "nord-ouest"),
            )
        ]

    # Waza
    if "waza" in q and re.search(
        r"o[uù]\s+est|where|se\s+trouve|localisation|r[eé]gion|parc",
        q,
    ):
        return [
            GeoFact(
                subject="Parc national de Waza",
                relation="LOCATED_IN",
                object="Waza / Extrême-Nord",
                text_fr=(
                    "Le parc national de Waza se trouve dans la région de l’Extrême-Nord "
                    "(accès typique depuis Maroua — vérifier saison et sécurité)."
                ),
                text_en=(
                    "Waza National Park is in the Far North region "
                    "(typical access from Maroua — check season and security)."
                ),
                source="Sites touristiques Extrême-Nord / Waza",
                entity_ids=("waza", "maroua", "extreme-nord"),
            )
        ]

    # Rhumsiki / Kapsiki
    if ("rhumsiki" in q or "roumsiki" in q or "kapsiki" in q) and re.search(
        r"o[uù]\s+est|where|se\s+trouve|localisation|r[eé]gion",
        q,
    ):
        return [
            GeoFact(
                subject="Rhumsiki",
                relation="LOCATED_IN",
                object="Rhumsiki / Mayo-Tsanaga / Extrême-Nord",
                text_fr=(
                    "Rhumsiki et le pic Kapsiki se trouvent dans les monts Mandara "
                    "(département du Mayo-Tsanaga, région de l’Extrême-Nord)."
                ),
                text_en=(
                    "Rhumsiki and Kapsiki peak are in the Mandara Mountains "
                    "(Mayo-Tsanaga department, Far North region)."
                ),
                source="Sites touristiques Extrême-Nord / Rhumsiki",
                entity_ids=("rhumsiki", "mayo-tsanaga", "extreme-nord"),
            )
        ]

    # Lac Tison
    if "lac tison" in q or "lake tison" in q or (
        "tison" in q and re.search(r"o[uù]\s+est|where|se\s+trouve|localisation|lac", q)
    ):
        return [
            GeoFact(
                subject="Lac Tison",
                relation="LOCATED_IN",
                object="Ngaoundéré / Vina / Adamaoua",
                text_fr=(
                    "Le lac Tison se trouve près de Ngaoundéré "
                    "(département de la Vina, région de l’Adamaoua)."
                ),
                text_en=(
                    "Lake Tison is near Ngaoundéré "
                    "(Vina department, Adamawa region)."
                ),
                source="Sites touristiques Adamaoua / Lac Tison",
                entity_ids=("lac-tison", "ngaoundere", "vina", "adamaoua"),
            )
        ]

    # Parc de la Bénoué
    if re.search(r"benou[eé]", q) and re.search(
        r"parc|o[uù]\s+est|where|se\s+trouve|localisation|r[eé]gion",
        q,
    ):
        return [
            GeoFact(
                subject="Parc national de la Bénoué",
                relation="LOCATED_IN",
                object="Tcholliré / Mayo-Rey / Nord",
                text_fr=(
                    "Le parc national de la Bénoué s’atteint depuis Tcholliré "
                    "(département du Mayo-Rey, région du Nord)."
                ),
                text_en=(
                    "Bénoué National Park is accessed from Tcholliré "
                    "(Mayo-Rey department, North region)."
                ),
                source="Sites touristiques Nord / Bénoué",
                entity_ids=("parc-benoue", "tchollire", "mayo-rey", "nord"),
            )
        ]

    # Réserve du Dja
    if re.search(r"\bdja\b", q) and re.search(
        r"reserve|réserve|parc|o[uù]\s+est|where|se\s+trouve|localisation|r[eé]gion",
        q,
    ):
        return [
            GeoFact(
                subject="Réserve de faune du Dja",
                relation="LOCATED_IN",
                object="Somalomo / Est",
                text_fr=(
                    "La réserve de faune du Dja (patrimoine mondial) s’atteint notamment "
                    "depuis Somalomo, dans la région de l’Est."
                ),
                text_en=(
                    "Dja Faunal Reserve (World Heritage) is accessed notably "
                    "from Somalomo, in the East region."
                ),
                source="Sites touristiques Est / Dja",
                entity_ids=("parc-dja", "somalomo", "est"),
            )
        ]

    # Lobéké
    if "lobeke" in q and re.search(
        r"parc|o[uù]\s+est|where|se\s+trouve|localisation|r[eé]gion",
        q,
    ):
        return [
            GeoFact(
                subject="Parc national de Lobéké",
                relation="LOCATED_IN",
                object="Moloundou / Boumba-et-Ngoko / Est",
                text_fr=(
                    "Le parc national de Lobéké s’atteint depuis Moloundou "
                    "(département du Boumba-et-Ngoko, région de l’Est)."
                ),
                text_en=(
                    "Lobéké National Park is accessed from Moloundou "
                    "(Boumba-et-Ngoko department, East region)."
                ),
                source="Sites touristiques Est / Lobéké",
                entity_ids=("parc-lobeke", "moloundou", "boumba-ngoko", "est"),
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
                elif rid == "littoral":
                    text_fr = f"{cname} se trouve dans la région du Littoral du Cameroun."
                elif rid == "centre":
                    text_fr = f"{cname} se trouve dans la région du Centre du Cameroun."
                elif rid == "sud":
                    text_fr = f"{cname} se trouve dans la région du Sud du Cameroun."
                elif rid == "sud-ouest":
                    text_fr = f"{cname} se trouve dans la région du Sud-Ouest du Cameroun."
                elif rid == "nord-ouest":
                    text_fr = f"{cname} se trouve dans la région du Nord-Ouest du Cameroun."
                elif rid == "extreme-nord":
                    text_fr = f"{cname} se trouve dans la région de l’Extrême-Nord du Cameroun."
                elif rid == "adamaoua":
                    text_fr = f"{cname} se trouve dans la région de l’Adamaoua du Cameroun."
                elif rid == "nord":
                    text_fr = f"{cname} se trouve dans la région du Nord du Cameroun."
                elif rid == "est":
                    text_fr = f"{cname} se trouve dans la région de l’Est du Cameroun."
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
        r"littoral.{0,40}c[' ]?est.{0,20}douala",
        r"douala.{0,40}c[' ]?est.{0,20}littoral",
        r"c[' ]?est\s+douala\s+nor",
        r"r[eé]gion\s+du\s+littoral.{0,30}douala",
        r"douala.{0,30}r[eé]gion\s+du\s+littoral",
        r"r[eé]gion\s+du\s+centre.{0,30}yaounde",
        r"yaounde.{0,30}r[eé]gion\s+du\s+centre",
        r"centre.{0,40}c[' ]?est.{0,20}yaounde",
        r"c[' ]?est\s+yaounde\s+nor",
        r"(?:chutes?\s+de\s+la\s+)?lob[eé]",
        r"sud.{0,40}c[' ]?est.{0,20}kribi",
        r"r[eé]gion\s+du\s+sud.{0,30}kribi",
        r"sud[- ]?ouest.{0,40}c[' ]?est.{0,20}buea",
        r"r[eé]gion\s+du\s+sud[- ]?ouest.{0,30}buea",
        r"buea.{0,40}c[' ]?est.{0,20}sud[- ]?ouest",
        r"nord[- ]?ouest.{0,40}c[' ]?est.{0,20}bamenda",
        r"r[eé]gion\s+du\s+nord[- ]?ouest.{0,30}bamenda",
        r"bamenda.{0,40}c[' ]?est.{0,20}nord[- ]?ouest",
        r"extreme[- ]?nord.{0,40}c[' ]?est.{0,20}maroua",
        r"r[eé]gion\s+(?:de\s+l['’])?extreme[- ]?nord.{0,30}maroua",
        r"maroua.{0,40}c[' ]?est.{0,20}extreme[- ]?nord",
        r"mont\s+cameroun|mount\s+cameroon",
        r"korup",
        r"(?:palais|chefferie)\s+(?:de\s+)?bafut",
        r"lac\s+oku",
        r"(?:parc\s+(?:national\s+)?(?:de\s+)?)?waza",
        r"rhumsiki|kapsiki",
        r"adamaoua.{0,40}c[' ]?est.{0,20}ngaoundere",
        r"r[eé]gion\s+(?:de\s+l['’])?adamaoua.{0,30}ngaoundere",
        r"ngaoundere.{0,40}c[' ]?est.{0,20}adamaoua",
        r"lac\s+tison",
        r"r[eé]gion\s+du\s+nord(?![- ]?ouest).{0,40}garoua",
        r"nord(?![- ]?ouest).{0,40}c[' ]?est.{0,20}garoua",
        r"garoua.{0,40}c[' ]?est.{0,20}nord",
        r"parc.{0,20}benou[eé]|benou[eé].{0,20}parc",
        r"r[eé]gion\s+de\s+l['’]?est.{0,40}bertoua",
        r"bertoua.{0,40}c[' ]?est.{0,20}(?:l['’])?est",
        r"(?:reserve|réserve).{0,10}dja|\bdja\b.{0,20}(?:reserve|réserve)",
        r"lobeke",
    )
    if any(re.search(p, q) for p in patterns):
        return True
    # "Où est … ?" / "where is …" for entities we can answer from the geo graph
    if re.search(r"\b(?:o[uù]\s+est|where\s+is|se\s+trouve|localisation)\b", q):
        if answer_geo_query(query):
            return True
    return False
