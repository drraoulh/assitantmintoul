"""Source tier ranking + validation for Web Research evidence."""

from __future__ import annotations

from urllib.parse import urlparse

from app.services.agents.web_research.models import WebEvidence

# Tier 1 — institutional
_TIER1 = (
    "mintoul.gov.cm",
    "diplocam.cm",
    "spm.gov.cm",
    "gov.cm",
    "unesco.org",
    "whc.unesco.org",
    "mincom.gov.cm",
)

# Tier 2 — recognized tourism / culture
_TIER2 = (
    "tourismo-cameroun.com",
    "tourism237.com",
    "visitcameroon",
    "cameroon-tourisme",
)

# Tier 3 — specialized guides / encyclopedic
_TIER3 = (
    "wikipedia.org",
    "wikivoyage.org",
    "britannica.com",
    "lonelyplanet.com",
    "roughguides.com",
)


def extract_domain(url: str) -> str:
    try:
        host = urlparse(url or "").netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:  # noqa: BLE001
        return ""


def source_tier(domain: str) -> int:
    d = (domain or "").lower()
    if not d:
        return 4
    for end in _TIER1:
        if d == end or d.endswith("." + end) or end in d:
            return 1
    for end in _TIER2:
        if end in d:
            return 2
    for end in _TIER3:
        if end in d:
            return 3
    return 4


def score_hit(*, title: str, snippet: str, url: str, query: str) -> tuple[float, int]:
    domain = extract_domain(url)
    tier = source_tier(domain)
    blob = f"{title} {snippet}".casefold()
    q_tokens = [t for t in query.casefold().split() if len(t) > 2]
    overlap = sum(1 for t in q_tokens if t in blob)
    base = {1: 0.85, 2: 0.7, 3: 0.55, 4: 0.35}.get(tier, 0.3)
    bonus = min(0.15, 0.03 * overlap)
    return min(0.95, base + bonus), tier


def validate_evidence(items: list[WebEvidence]) -> list[WebEvidence]:
    """Keep only usable evidence; tier-4 alone cannot make answerable."""
    kept: list[WebEvidence] = []
    seen_urls: set[str] = set()
    for ev in items:
        url = (ev.url or "").strip()
        snippet = (ev.snippet or "").strip()
        if not snippet or len(snippet) < 24:
            continue
        key = url or f"{ev.domain}:{snippet[:40]}"
        if key in seen_urls:
            continue
        seen_urls.add(key)
        # Community blogs must not be marked verified
        ev.verified = ev.tier <= 2 and ev.relevance_score >= 0.55
        kept.append(ev)
    # Prefer higher tier / score
    kept.sort(key=lambda e: (e.tier, -e.relevance_score))
    return kept[:8]


def is_answerable(evidence: list[WebEvidence]) -> bool:
    if not evidence:
        return False
    # Need at least one tier 1–3 source, or two independent sources
    if any(e.tier <= 3 for e in evidence):
        return True
    return len(evidence) >= 2


def extract_key_facts(evidence: list[WebEvidence], *, max_facts: int = 6) -> list[str]:
    """Pull short factual snippets — never invent beyond the source text."""
    facts: list[str] = []
    for ev in evidence:
        text = (ev.snippet or "").strip()
        if not text:
            continue
        # Split on sentence-ish boundaries
        parts = [p.strip() for p in text.replace("•", ".").split(".") if p.strip()]
        for part in parts:
            if len(part) < 28:
                continue
            fact = part[:220]
            if fact not in facts:
                facts.append(fact)
            if len(facts) >= max_facts:
                return facts
    return facts
