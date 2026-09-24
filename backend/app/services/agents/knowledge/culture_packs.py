"""Region culture packs (Phase 2.8+) — dishes, traditions, markets. No invented restaurants."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.agents.knowledge.models import KnowledgeEvidence
from app.services.agents.knowledge.place_store import fold

_DATA = Path(__file__).resolve().parents[4] / "data" / "geography"


@lru_cache(maxsize=4)
def _load_ouest() -> dict:
    path = _DATA / "ouest_culture.json"
    return json.loads(path.read_text(encoding="utf-8"))


def clear_culture_cache() -> None:
    _load_ouest.cache_clear()


def culture_evidence_for_query(query: str, *, language: str = "fr") -> list[KnowledgeEvidence]:
    """Return structured culture/food evidence when the query targets Ouest themes."""
    q = fold(query)
    ouest_hit = any(
        tok in q
        for tok in (
            "ouest",
            "west",
            "bafoussam",
            "foumban",
            "dschang",
            "bandjoun",
            "mbouda",
            "bafang",
            "bangangte",
            "baham",
            "batcham",
            "batoufam",
            "bana",
            "penka",
            "grassfields",
            "bamoun",
            "bamum",
            "bamileke",
            "bamiléké",
            "achu",
            "koki",
            "chefferie",
            "mbapit",
        )
    )
    if not ouest_hit:
        return []

    pack = _load_ouest()
    lang = "en" if (language or "fr").lower().startswith("en") else "fr"
    out: list[KnowledgeEvidence] = []

    want_food = any(
        t in q
        for t in (
            "plat",
            "manger",
            "food",
            "cuisine",
            "restaurant",
            "gastronomie",
            "achu",
            "koki",
            "cafe",
            "café",
        )
    )
    want_trad = any(
        t in q
        for t in (
            "tradition",
            "culture",
            "chefferie",
            "bamoun",
            "bamum",
            "bamil",
            "danse",
            "masque",
            "protocole",
            "langue",
            "language",
        )
    )
    want_craft = any(
        t in q for t in ("artisan", "sculpture", "bronze", "marché", "market", "craft", "tissu")
    )
    want_hotel = any(t in q for t in ("hotel", "hôtel", "heberg", "héberg", "dormir", "stay"))
    want_nature = any(
        t in q for t in ("lac", "chute", "cascade", "mont", "nature", "randonn", "falaise")
    )
    want_practical = any(
        t in q for t in ("itineraire", "itinéraire", "comment aller", "climat", "saison", "corridor")
    )
    # Broad Ouest tourism → include a short culture blurb
    broad = any(t in q for t in ("visiter", "visite", "touris", "que faire", "propos", "decouvrir", "découvrir"))

    overview = pack.get("overview") or {}
    if broad or want_trad:
        text = overview.get("text_en") if lang == "en" else overview.get("text_fr")
        if text:
            out.append(
                KnowledgeEvidence(
                    chunk_id="culture-overview-ouest",
                    content=str(text),
                    source_id="culture:ouest",
                    title="Ouest overview",
                    score=0.88,
                )
            )

    if want_food or broad:
        for dish in pack.get("dishes", []):
            text = dish.get("text_en") if lang == "en" else dish.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-dish-{dish.get('id')}",
                    content=str(text or ""),
                    source_id="culture:ouest",
                    title=dish.get("name_fr") or dish.get("name_en"),
                    score=0.8,
                )
            )
        policy = pack.get("restaurants_policy") or {}
        pol = policy.get("text_en") if lang == "en" else policy.get("text_fr")
        if pol and want_food:
            out.append(
                KnowledgeEvidence(
                    chunk_id="culture-resto-policy-ouest",
                    content=str(pol),
                    source_id="culture:ouest",
                    title="Restaurants Ouest (policy)",
                    score=0.9,
                )
            )

    if want_trad or broad:
        for trad in pack.get("traditions", []):
            text = trad.get("text_en") if lang == "en" else trad.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-trad-{trad.get('id')}",
                    content=str(text or ""),
                    source_id="culture:ouest",
                    title=trad.get("title_fr") or trad.get("title_en"),
                    score=0.82,
                )
            )
        for lang_row in pack.get("languages", [])[:5]:
            note = lang_row.get("note_en") if lang == "en" else lang_row.get("note_fr")
            content = f"{lang_row.get('name')} ({lang_row.get('area')})"
            if note:
                content = f"{content}: {note}"
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-lang-{fold(str(lang_row.get('name') or 'x'))[:24]}",
                    content=content,
                    source_id="culture:ouest",
                    title=lang_row.get("name"),
                    score=0.75,
                )
            )

    if want_craft or broad:
        for craft in pack.get("markets_and_crafts", []):
            text = craft.get("text_en") if lang == "en" else craft.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-craft-{craft.get('id')}",
                    content=str(text or ""),
                    source_id="culture:ouest",
                    title=craft.get("name_fr") or craft.get("name_en"),
                    score=0.8,
                )
            )

    if want_nature or broad:
        for nat in pack.get("nature_highlights", []):
            text = nat.get("text_en") if lang == "en" else nat.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-nature-{nat.get('id')}",
                    content=str(text or ""),
                    source_id="culture:ouest",
                    title=nat.get("title_fr") or nat.get("title_en"),
                    score=0.78,
                )
            )

    if want_practical or broad:
        for tip in pack.get("practical", []):
            text = tip.get("text_en") if lang == "en" else tip.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-practical-{tip.get('id')}",
                    content=str(text or ""),
                    source_id="culture:ouest",
                    title=tip.get("title_fr") or tip.get("title_en"),
                    score=0.77,
                )
            )

    if want_hotel:
        for hotel in pack.get("hotels_verified", []):
            text = hotel.get("text_en") if lang == "en" else hotel.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-hotel-{hotel.get('id')}",
                    content=f"{hotel.get('name')}: {text}",
                    source_id="culture:ouest",
                    title=hotel.get("name"),
                    score=0.85,
                )
            )

    # Deduplicate by chunk_id while preserving order
    seen: set[str] = set()
    unique: list[KnowledgeEvidence] = []
    for ev in out:
        if ev.chunk_id in seen:
            continue
        seen.add(ev.chunk_id)
        unique.append(ev)
    return unique[:14]
