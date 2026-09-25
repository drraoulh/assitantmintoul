"""Source ranker — weighted score, no domain rejected a priori.

score = 0.35·relevance + 0.25·credibility + 0.20·freshness
      + 0.15·domain_quality + 0.05·directness

Sources under LOW_CONFIDENCE_THRESHOLD are kept but flagged so Agent 4 hedges.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from app.services.agents.web_research.models import WebEvidence

WEIGHTS = {
    "relevance": 0.35,
    "credibility": 0.25,
    "freshness": 0.20,
    "domain_quality": 0.15,
    "directness": 0.05,
}
LOW_CONFIDENCE_THRESHOLD = 0.25
# Credibility/freshness alone can lift an off-topic page above the threshold,
# so a source that barely overlaps the question is also flagged.
MIN_RELEVANCE = 0.2
MAX_SOURCES = 5

_CREDIBILITY_BY_TIER = {1: 0.95, 2: 0.8, 3: 0.55, 4: 0.3}
_CREDIBILITY_BY_TYPE = {"official": 0.95, "wiki": 0.7, "news": 0.7, "business": 0.5, "blog": 0.4}
_LOW_QUALITY_HOSTS = ("pinterest.", "tiktok.", "quora.", "scribd.", "slideshare.")
_STOP = {
    "les", "des", "du", "de", "la", "le", "et", "en", "au", "aux", "un", "une", "est",
    "quel", "quelle", "quels", "quelles", "the", "and", "for", "what", "which", "are",
    "cameroun", "cameroon", "c'est", "quoi", "pour", "dans", "sur", "moi", "mois-ci",
    "ce", "ci", "this", "month", "region", "région",
}
_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_REL_RE = re.compile(r"(\d+)\s+(minute|hour|heure|day|jour|week|semaine|month|mois|year|an)s?\b")
_REL_DAYS = {
    "minute": 0, "hour": 0, "heure": 0, "day": 1, "jour": 1, "week": 7,
    "semaine": 7, "month": 30, "mois": 30, "year": 365, "an": 365,
}


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _stem(token: str) -> str:
    if len(token) > 4 and token[-1] in "sx":
        return token[:-1]
    return token


def _terms(text: str) -> set[str]:
    return {
        _stem(t) for t in _TOKEN_RE.findall(_fold(text)) if len(t) > 2 and t not in _STOP
    }


def semantic_overlap(text: str, query: str) -> float:
    q = _terms(query)
    if not q:
        return 0.5
    return len(q & _terms(text)) / len(q)


_FR_MONTHS = ("janv", "fevr", "mars", "avr", "mai", "juin", "juil", "aout", "sept", "oct", "nov", "dec")
_FR_DATE_RE = re.compile(r"(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})")


def _age_days(published_at: str | None, now: datetime) -> float | None:
    if not published_at:
        return None
    raw = published_at.strip()
    rel = _REL_RE.search(_fold(raw))
    if rel:
        return int(rel.group(1)) * _REL_DAYS[rel.group(2)]
    dt: datetime | None = None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%b %d, %Y", "%d %b %Y", "%a, %d %b %Y %H:%M:%S %Z"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        fr = _FR_DATE_RE.search(_fold(raw))
        if fr:
            month = next(
                (i for i, m in enumerate(_FR_MONTHS, 1) if fr.group(2).startswith(m)), None
            )
            if month:
                try:
                    dt = datetime(int(fr.group(3)), month, int(fr.group(1)))
                except ValueError:
                    dt = None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 86400.0)


def freshness_score(published_at: str | None, *, now: datetime | None = None) -> float:
    age = _age_days(published_at, now or datetime.now(timezone.utc))
    if age is None:
        return 0.5
    if age <= 30:
        return 1.0
    if age >= 730:
        return 0.2
    return round(1.0 - 0.8 * (age - 30) / 700.0, 3)


def credibility(ev: WebEvidence) -> float:
    by_type = _CREDIBILITY_BY_TYPE.get(ev.source_type or "", 0.0)
    return max(by_type, _CREDIBILITY_BY_TIER.get(ev.tier, 0.5))


def domain_quality(ev: WebEvidence) -> float:
    reputable = ev.url.startswith("https://") and not any(
        h in (ev.domain or "") for h in _LOW_QUALITY_HOSTS
    )
    return 0.8 if reputable else 0.4


def directness(ev: WebEvidence, query: str) -> float:
    q = _terms(query)
    return 1.0 if q and (q & _terms(ev.title)) else 0.5


def score(ev: WebEvidence, query: str, *, now: datetime | None = None) -> float:
    w = WEIGHTS
    value = (
        w["relevance"] * semantic_overlap(f"{ev.title} {ev.snippet}", query)
        + w["credibility"] * credibility(ev)
        + w["freshness"] * freshness_score(ev.published_at, now=now)
        + w["domain_quality"] * domain_quality(ev)
        + w["directness"] * directness(ev, query)
    )
    return round(min(1.0, max(0.0, value)), 4)


def rank(
    evidence: list[WebEvidence],
    query: str,
    *,
    limit: int = MAX_SOURCES,
    now: datetime | None = None,
) -> list[WebEvidence]:
    for ev in evidence:
        ev.rank_score = score(ev, query, now=now)
        ev.low_confidence = (
            ev.rank_score < LOW_CONFIDENCE_THRESHOLD
            or semantic_overlap(f"{ev.title} {ev.snippet}", query) < MIN_RELEVANCE
        )
    return sorted(evidence, key=lambda e: -e.rank_score)[:limit]
