"""Re-encode knowledge JSON files that contain UTF-8 → cp1252 mojibake.

Usage (from backend/):
  python -m scripts.fix_mojibake          # rewrite files in place
  python -m scripts.fix_mojibake --check  # exit 1 if any file still needs fixing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.text_encoding import has_mojibake, repair_mojibake  # noqa: E402

DATA_DIRS = (BACKEND.parent / "data" / "tourist_sites", BACKEND / "data")

# The import that double-encoded these texts also dropped the space that
# followed an accented word ("Situéau", "muséenational"), and a later
# FR→EN pass translated "Situé" into a glued "Located".
_GLUED = {
    "Situéprèsde": "Situé près de",
    "Situéderrière": "Situé derrière",
    "Situédans": "Situé dans",
    "Situéau": "Situé au",
    "Locatedprèsde": "Located near",
    "Locatedderrière": "Located behind",
    "Locateddans": "Located in",
    "Locatedau": "Located at",
    "Réputépour": "Réputé pour",
    "Yaoundéest": "Yaoundé est",
    "Yaoundéis": "Yaoundé is",
    "OLEMBéet": "OLEMBÉ et",
    "Elabédans": "Elabé dans",
    "équipésdu": "équipés du",
    "conçupour": "conçu pour",
    "côtéde": "côté de",
    "Universitéde": "Université de",
    "meubléede": "meublée de",
    "meubléspenséspour": "meublés pensés pour",
    "meubléshaut": "meublés haut",
    "muséenational": "musée national",
    "oùle": "où le",
    "appréciépar": "apprécié par",
    "proximitéavec": "proximité avec",
    "proximitédu": "proximité du",
    "simplicitédans": "simplicité dans",
    "variétéde": "variété de",
}
_GLUED_RE = re.compile("|".join(re.escape(k) for k in sorted(_GLUED, key=len, reverse=True)))


def fix_text(text: str) -> str:
    if not has_mojibake(text):
        return text
    return _GLUED_RE.sub(lambda m: _GLUED[m.group()], repair_mojibake(text))


def _walk(value: Any) -> Any:
    if isinstance(value, str):
        return fix_text(value)
    if isinstance(value, list):
        return [_walk(v) for v in value]
    if isinstance(value, dict):
        return {fix_text(k): _walk(v) for k, v in value.items()}
    return value


def iter_json_files() -> list[Path]:
    return sorted(p for d in DATA_DIRS if d.exists() for p in d.rglob("*.json"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    dirty: list[Path] = []
    for path in iter_json_files():
        raw = path.read_text(encoding="utf-8")
        if not has_mojibake(raw):
            continue
        dirty.append(path)
        if args.check:
            continue
        fixed = _walk(json.loads(raw))
        path.write_text(json.dumps(fixed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"fixed {path.relative_to(BACKEND.parent)}")

    if args.check and dirty:
        for path in dirty:
            print(f"mojibake: {path.relative_to(BACKEND.parent)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
