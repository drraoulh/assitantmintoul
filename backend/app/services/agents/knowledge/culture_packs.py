"""Region culture packs (Phase 2.8+) — dishes, traditions, markets. No invented restaurants."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.agents.knowledge.models import KnowledgeEvidence
from app.services.agents.knowledge.place_store import fold

_DATA = Path(__file__).resolve().parents[4] / "data" / "geography"

# region_id → query tokens that activate the pack
_PACK_TRIGGERS: dict[str, tuple[str, ...]] = {
    "ouest": (
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
    ),
    "littoral": (
        "littoral",
        "douala",
        "duala",
        "edea",
        "edéa",
        "nkongsamba",
        "melong",
        "yabassi",
        "mouanko",
        "sawa",
        "ndole",
        "ndolé",
        "wouri",
        "bonanjo",
        "akwa",
        "bonapriso",
        "deido",
        "manoka",
        "ekom",
    ),
    "centre": (
        "region du centre",
        "région du centre",
        "centre du cameroun",
        "yaounde",
        "yaoundé",
        "mbalmayo",
        "mfou",
        "soa",
        "monatele",
        "monatélé",
        "ewondo",
        "fang-beti",
        "mokolo",
        "mefou",
        "ebogo",
        "reunification",
        "réunification",
        "nsimalen",
        "poulet dg",
        "bastos",
    ),
    "sud": (
        "region du sud",
        "région du sud",
        "sud du cameroun",
        "kribi",
        "ebolowa",
        "sangmelima",
        "sangmélima",
        "campo",
        "ambam",
        "lobe",
        "lobé",
        "batanga",
        "nkolandom",
        "poisson braise",
        "poisson braisé",
    ),
    "sud-ouest": (
        "sud-ouest",
        "sud ouest",
        "south-west",
        "southwest",
        "south west",
        "limbe",
        "limbé",
        "buea",
        "kumba",
        "mundemba",
        "mamfe",
        "tiko",
        "korup",
        "barombi",
        "mont cameroun",
        "mount cameroon",
        "eru",
        "okok",
        "sable noir",
        "black sand",
        "pidgin",
        "fako",
    ),
    "nord-ouest": (
        "nord-ouest",
        "nord ouest",
        "north-west",
        "northwest",
        "north west",
        "bamenda",
        "bafut",
        "oku",
        "kumbo",
        "wum",
        "fundong",
        "ndop",
        "nkambe",
        "mbengwi",
        "lac oku",
        "lac kuk",
        "lamnso",
        "nso",
    ),
    "extreme-nord": (
        "extreme-nord",
        "extreme nord",
        "extrême-nord",
        "extrême nord",
        "far north",
        "far-north",
        "maroua",
        "waza",
        "rhumsiki",
        "roumsiki",
        "kapsiki",
        "mandara",
        "maga",
        "mofou",
        "kousseri",
        "kousséri",
        "yagoua",
        "mora",
        "kaele",
        "kaélé",
        "soya",
        "brochette",
    ),
    "adamaoua": (
        "adamaoua",
        "adamawa",
        "ngaoundere",
        "ngaoundéré",
        "banyo",
        "meiganga",
        "tibati",
        "tignere",
        "tignère",
        "lac tison",
        "ngan-ha",
        "ngan ha",
        "lancrenon",
        "hotel oasis",
        "hôtel oasis",
        "lamidat de ngaoundere",
        "lamidat de ngaoundéré",
        "palais du lamido",
    ),
    "nord": (
        "region du nord",
        "région du nord",
        "nord du cameroun",
        "garoua",
        "figuil",
        "tchollire",
        "tcholliré",
        "touboro",
        "guider",
        "poli",
        "benoue",
        "bénoué",
        "faro",
        "bouba",
        "ndjida",
        "lagdo",
        "dirif",
        "shalom city",
        "ribadou",
        "motel plaza",
        "new town palace",
    ),
    "est": (
        "region de l est",
        "région de l'est",
        "région de l est",
        "est du cameroun",
        "east region",
        "east cameroon",
        "bertoua",
        "batouri",
        "abong-mbang",
        "abong mbang",
        "yokadouma",
        "moloundou",
        "somalomo",
        "lobeke",
        "lobéké",
        "reserve du dja",
        "réserve du dja",
        "parc dja",
    ),
}


_COMPOUND_OUEST = (
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

_COMPOUND_NORD = (
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


def _trigger_hits(q: str, region_id: str, tokens: tuple[str, ...]) -> bool:
    """Match pack tokens without letting bare ouest/nord hit compound regions."""
    compound_ouest = any(c in q for c in _COMPOUND_OUEST)
    compound_nord = any(c in q for c in _COMPOUND_NORD)
    for tok in tokens:
        if tok not in q:
            continue
        if region_id == "ouest" and tok in {"ouest", "west"} and compound_ouest:
            continue
        if region_id == "nord" and tok in {"nord", "north"} and compound_nord:
            continue
        return True
    return False


@lru_cache(maxsize=16)
def _load_pack(region_id: str) -> dict:
    path = _DATA / f"{region_id}_culture.json"
    return json.loads(path.read_text(encoding="utf-8"))


def clear_culture_cache() -> None:
    _load_pack.cache_clear()


def _intent_flags(q: str) -> dict[str, bool]:
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
            "ndole",
            "ndolé",
            "poulet",
            "poisson",
            "eru",
            "okok",
            "soya",
            "brochette",
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
            "sawa",
            "ewondo",
            "fang",
            "beti",
            "pidgin",
            "peul",
            "lamidat",
            "danse",
            "masque",
            "protocole",
            "langue",
            "language",
            "patrimoine",
            "musee",
            "musée",
            "monument",
        )
    )
    want_craft = any(
        t in q for t in ("artisan", "sculpture", "bronze", "marché", "market", "craft", "tissu", "wax")
    )
    want_hotel = any(t in q for t in ("hotel", "hôtel", "heberg", "héberg", "dormir", "stay"))
    want_nature = any(
        t in q
        for t in ("lac", "chute", "cascade", "mont", "nature", "randonn", "falaise", "mangrove", "plage", "fleuve", "ile", "île", "parc")
    )
    want_practical = any(
        t in q
        for t in ("itineraire", "itinéraire", "comment aller", "climat", "saison", "corridor", "aeroport", "aéroport")
    )
    broad = any(
        t in q for t in ("visiter", "visite", "touris", "que faire", "propos", "decouvrir", "découvrir")
    )
    return {
        "food": want_food,
        "trad": want_trad,
        "craft": want_craft,
        "hotel": want_hotel,
        "nature": want_nature,
        "practical": want_practical,
        "broad": broad,
    }


def _pack_evidence(region_id: str, pack: dict, *, language: str, flags: dict[str, bool]) -> list[KnowledgeEvidence]:
    lang = "en" if (language or "fr").lower().startswith("en") else "fr"
    source_id = f"culture:{region_id}"
    out: list[KnowledgeEvidence] = []

    overview = pack.get("overview") or {}
    if flags["broad"] or flags["trad"]:
        text = overview.get("text_en") if lang == "en" else overview.get("text_fr")
        if text:
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-overview-{region_id}",
                    content=str(text),
                    source_id=source_id,
                    title=f"{region_id} overview",
                    score=0.88,
                )
            )

    if flags["food"] or flags["broad"]:
        for dish in pack.get("dishes", []):
            text = dish.get("text_en") if lang == "en" else dish.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-dish-{region_id}-{dish.get('id')}",
                    content=str(text or ""),
                    source_id=source_id,
                    title=dish.get("name_fr") or dish.get("name_en"),
                    score=0.8,
                )
            )
        policy = pack.get("restaurants_policy") or {}
        pol = policy.get("text_en") if lang == "en" else policy.get("text_fr")
        if pol and flags["food"]:
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-resto-policy-{region_id}",
                    content=str(pol),
                    source_id=source_id,
                    title=f"Restaurants {region_id} (policy)",
                    score=0.9,
                )
            )

    if flags["trad"] or flags["broad"]:
        for trad in pack.get("traditions", []):
            text = trad.get("text_en") if lang == "en" else trad.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-trad-{region_id}-{trad.get('id')}",
                    content=str(text or ""),
                    source_id=source_id,
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
                    chunk_id=f"culture-lang-{region_id}-{fold(str(lang_row.get('name') or 'x'))[:20]}",
                    content=content,
                    source_id=source_id,
                    title=lang_row.get("name"),
                    score=0.75,
                )
            )

    if flags["craft"] or flags["broad"]:
        for craft in pack.get("markets_and_crafts", []):
            text = craft.get("text_en") if lang == "en" else craft.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-craft-{region_id}-{craft.get('id')}",
                    content=str(text or ""),
                    source_id=source_id,
                    title=craft.get("name_fr") or craft.get("name_en"),
                    score=0.8,
                )
            )

    if flags["nature"] or flags["broad"]:
        for nat in pack.get("nature_highlights", []):
            text = nat.get("text_en") if lang == "en" else nat.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-nature-{region_id}-{nat.get('id')}",
                    content=str(text or ""),
                    source_id=source_id,
                    title=nat.get("title_fr") or nat.get("title_en"),
                    score=0.78,
                )
            )

    if flags["practical"] or flags["broad"]:
        for tip in pack.get("practical", []):
            text = tip.get("text_en") if lang == "en" else tip.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-practical-{region_id}-{tip.get('id')}",
                    content=str(text or ""),
                    source_id=source_id,
                    title=tip.get("title_fr") or tip.get("title_en"),
                    score=0.77,
                )
            )

    if flags["hotel"]:
        hotels = pack.get("hotels_verified") or []
        for hotel in hotels:
            text = hotel.get("text_en") if lang == "en" else hotel.get("text_fr")
            out.append(
                KnowledgeEvidence(
                    chunk_id=f"culture-hotel-{region_id}-{hotel.get('id')}",
                    content=f"{hotel.get('name')}: {text}",
                    source_id=source_id,
                    title=hotel.get("name"),
                    score=0.85,
                )
            )
        if not hotels:
            policy = pack.get("hotels_policy") or {}
            pol = policy.get("text_en") if lang == "en" else policy.get("text_fr")
            if pol:
                out.append(
                    KnowledgeEvidence(
                        chunk_id=f"culture-hotel-policy-{region_id}",
                        content=str(pol),
                        source_id=source_id,
                        title=f"Hotels {region_id} (policy)",
                        score=0.9,
                    )
                )

    return out


def culture_evidence_for_query(query: str, *, language: str = "fr") -> list[KnowledgeEvidence]:
    """Return structured culture/food evidence for matching region packs."""
    q = fold(query)
    flags = _intent_flags(q)
    out: list[KnowledgeEvidence] = []

    for region_id, tokens in _PACK_TRIGGERS.items():
        if not _trigger_hits(q, region_id, tokens):
            continue
        try:
            pack = _load_pack(region_id)
        except (OSError, json.JSONDecodeError, FileNotFoundError):
            continue
        out.extend(_pack_evidence(region_id, pack, language=language, flags=flags))

    seen: set[str] = set()
    unique: list[KnowledgeEvidence] = []
    for ev in out:
        if ev.chunk_id in seen:
            continue
        seen.add(ev.chunk_id)
        unique.append(ev)
    return unique[:16]


# Back-compat for tests that imported _load_ouest
def _load_ouest() -> dict:
    return _load_pack("ouest")
