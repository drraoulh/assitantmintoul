"""Deterministic grounding enforcement for Agent 4 (Phase 2.7).

No second LLM. Fast checks only. Safe for post-stream diagnostics.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from app.services.agents.knowledge.place_store import PlaceIndex
from app.services.agents.response.evidence import AllowedEvidence
from app.services.agents.response.validate import claims_road_distance, fold

# Observed / high-risk invented entities from real canaries (and similar).
_HALLUCINATION_WATCHLIST = {
    "african food by emy",
    "taste of afrka",
    "taste of africa",
    "mbingo",
    "kimbi",
    "ruines de mbingo",
    "village de kimbi",
    "hotel fantome",
    "hôtel fantôme",
    "parc xyz",
    "place c",
}

_PRICE_RE = re.compile(
    r"(?P<num>\d{1,3}(?:[\s.,]\d{3})+|\d{4,7})\s*(?:fcfa|xaf|francs?(?:\s+cfa)?)",
    re.IGNORECASE,
)
_AVAIL_RE = re.compile(
    r"("
    r"il reste\s+\d+\s+chambres?"
    r"|only\s+\d+\s+rooms?\s+left"
    r"|disponible\s+demain"
    r"|available\s+tomorrow"
    r"|fully\s+booked"
    r"|complet\s+ce\s+soir"
    r")",
    re.IGNORECASE,
)
_HOURS_RE = re.compile(
    r"("
    r"ouvert\s+(?:de\s+)?\d{1,2}\s*h(?:\d{0,2})?\s*(?:à|a|-|–)\s*\d{1,2}\s*h"
    r"|open(?:s|ing)?\s+(?:from\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?"
    r"\s*(?:to|-|–)\s*\d{1,2}"
    r"|horaires?\s*:\s*\d"
    r")",
    re.IGNORECASE,
)
_SLOGAN_RE = re.compile(
    r"africa\s+in\s+miniature|afrique\s+en\s+miniature",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)

# Named Cameroonian dishes (folded). A reply may only name one that appears in
# this turn's evidence text (or the user's own question).
_DISH_LEXICON = (
    "mbongo tchobi",
    "mbongo",
    "ndole",
    "eru",
    "okok",
    "achu",
    "koki",
    "kondre",
    "nkui",
    "kati kati",
    "ekwang",
    "nnam ngon",
    "sanga",
    "kwacoco",
    "ekomba",
    "mintoumba",
    "ndomba",
    "folong",
    "pepper soup",
    "corn chaff",
    "water fufu",
    "miondo",
    "bobolo",
    "poulet dg",
    "sauce jaune",
    "taro",
    "okra soup",
    "mbanga soup",
    "kpwem",
    "kwem",
)


@dataclass
class GroundingViolation:
    kind: str
    detail: str


@dataclass
class GroundingReport:
    ok: bool = True
    critical: bool = False
    violations: list[GroundingViolation] = field(default_factory=list)
    validation_ms: float = 0.0
    enforcement_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "critical": self.critical,
            "enforcement_enabled": self.enforcement_enabled,
            "validation_ms": round(self.validation_ms, 3),
            "violations": [{"kind": v.kind, "detail": v.detail} for v in self.violations[:12]],
            "violation_count": len(self.violations),
        }


def validate_grounding(
    text: str,
    evidence: AllowedEvidence,
    *,
    catalog_names: set[str] | None = None,
    enforcement_enabled: bool = True,
) -> GroundingReport:
    """Compare reply text against allowed evidence. Deterministic, no LLM."""
    started = time.perf_counter()
    report = GroundingReport(enforcement_enabled=enforcement_enabled)
    if not enforcement_enabled:
        report.validation_ms = (time.perf_counter() - started) * 1000.0
        return report

    body = text or ""
    folded = fold(body)

    # 1) Watchlist hallucinations
    for name in _HALLUCINATION_WATCHLIST:
        if (
            name in folded
            and name not in evidence.place_names_folded
            and name not in evidence.evidence_text_folded
        ):
            report.violations.append(
                GroundingViolation("unauthorized_place", name)
            )
            report.critical = True

    # 2) Catalog places mentioned but not in whitelist for this turn
    catalog = catalog_names or set()
    for raw in catalog:
        key = fold(raw)
        if len(key) < 4:
            continue
        if key in evidence.place_names_folded or key in evidence.evidence_text_folded:
            continue
        if re.search(rf"\b{re.escape(key)}\b", folded):
            report.violations.append(
                GroundingViolation("unauthorized_catalog_place", raw)
            )
            report.critical = True

    # 3) Prices not in known costs
    for match in _PRICE_RE.finditer(body):
        digits = re.sub(r"[^\d]", "", match.group("num"))
        if not digits:
            continue
        value = int(digits)
        # Ignore tiny numbers (years, hours) and huge noise
        if value < 500 or value > 50_000_000:
            continue
        if value not in evidence.known_costs_xaf:
            report.violations.append(
                GroundingViolation("unauthorized_price", str(value))
            )
            report.critical = True

    # 4) Opening hours invention when tagged missing / never provided
    if "opening_hours" in evidence.missing_tags or not evidence.has_verified_places:
        if _HOURS_RE.search(body):
            # Only flag when we have no hour evidence at all (always today)
            if "opening_hours" in evidence.missing_tags or (
                not evidence.has_verified_places and not evidence.has_web_evidence
            ):
                report.violations.append(
                    GroundingViolation("unauthorized_hours", "opening_hours_claim")
                )
                report.critical = True

    # 5) Availability invention
    if _AVAIL_RE.search(body):
        report.violations.append(
            GroundingViolation("unauthorized_availability", "live_availability_claim")
        )
        report.critical = True

    # 6) Road distance mislabel
    if claims_road_distance(body) and evidence.distance_type == "geographic":
        if evidence.known_distances_km:
            report.violations.append(
                GroundingViolation("distance_mislabel", "road_instead_of_geographic")
            )
            report.critical = True

    # 7) Africa in miniature without evidence
    if _SLOGAN_RE.search(body):
        allowed = {fold(s) for s in evidence.allowed_slogans}
        if "africa in miniature" not in allowed and "afrique en miniature" not in allowed:
            report.violations.append(
                GroundingViolation("unauthorized_slogan", "africa_in_miniature")
            )
            # Soft-critical: strip-worthy but not always replace whole answer
            report.critical = True

    # 8) URLs not in evidence
    for url in _URL_RE.findall(body):
        if url not in evidence.known_urls:
            report.violations.append(
                GroundingViolation("unauthorized_url", url[:120])
            )
            report.critical = True

    # 9) Dishes not present in evidence
    if evidence.evidence_text_folded:
        for dish in _DISH_LEXICON:
            pattern = rf"\b{re.escape(dish)}\b"
            if re.search(pattern, folded) and not re.search(
                pattern, evidence.evidence_text_folded
            ):
                report.violations.append(GroundingViolation("unauthorized_dish", dish))
                report.critical = True

    report.ok = len(report.violations) == 0
    report.validation_ms = (time.perf_counter() - started) * 1000.0
    return report


def catalog_place_names(index: PlaceIndex | None = None) -> set[str]:
    """Published catalog names for unauthorized-mention detection."""
    try:
        idx = index or PlaceIndex.from_catalog()
    except Exception:
        return set()
    names: set[str] = set()
    for place in idx.places:
        if place.name:
            names.add(place.name)
        if place.name_fr:
            names.add(place.name_fr)
        if place.name_en:
            names.add(place.name_en)
    return names


# Expose watchlist for unit tests
HALLUCINATION_WATCHLIST = set(_HALLUCINATION_WATCHLIST)
