from __future__ import annotations

import pytest

from app.core.text_encoding import has_mojibake, repair_mojibake
from app.services.agents.knowledge.culture_packs import _load_pack, clear_culture_cache
from app.services.tourism.catalog import SiteCatalog
from scripts.fix_mojibake import fix_text, iter_json_files


@pytest.mark.parametrize(
    ("broken", "expected"),
    [
        ("SituÃ© Ã\u00a0 Douala", "Situé à Douala"),
        ("SituÃ© Ã  Douala", "Situé à Douala"),
        ("hÃ´tel cinq Ã©toiles", "hôtel cinq étoiles"),
        ("accÃ¨s Wi-Fi, conÃ§u", "accès Wi-Fi, conçu"),
        ("prix â€“ 10 000 FCFA", "prix – 10 000 FCFA"),
        ("commoditÃ", "commodité"),
    ],
)
def test_repair_mojibake(broken: str, expected: str) -> None:
    assert has_mojibake(broken)
    assert repair_mojibake(broken) == expected


@pytest.mark.parametrize(
    "clean",
    ["Situé à Douala", "Ngaoundéré — Adamaoua", "À Kribi, les chutes de la Lobé", "Ça coûte 5 000 FCFA", ""],
)
def test_clean_text_is_untouched(clean: str) -> None:
    assert not has_mojibake(clean)
    assert repair_mojibake(clean) == clean


def test_fix_text_restores_dropped_spaces() -> None:
    assert fix_text("SituÃ©au boulevard de la libertÃ© Ã  Akwa") == "Situé au boulevard de la liberté à Akwa"
    assert fix_text("le musÃ©enational") == "le musée national"


def test_knowledge_json_files_are_clean_utf8() -> None:
    files = iter_json_files()
    assert files
    dirty = [str(p) for p in files if has_mojibake(p.read_text(encoding="utf-8"))]
    assert dirty == []


def test_catalog_loads_accented_hotel_description() -> None:
    hilton = next(s for s in SiteCatalog().all() if s.name.startswith("Hilton Yaound"))
    text = str(hilton.model_dump())
    assert "Situé à 2 km du monument de la Réunification" in text
    assert not has_mojibake(text)


def test_culture_pack_hotels_are_clean() -> None:
    clear_culture_cache()
    pack = _load_pack("littoral")
    blob = str(pack)
    assert "Situé au boulevard de la liberté à Akwa" in blob
    assert not has_mojibake(blob)
