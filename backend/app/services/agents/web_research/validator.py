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
    "tourismeouestcameroun.com",
    "ortoc",
)

# Tier 3 — specialized guides / encyclopedic
_TIER3 = (
    "wikipedia.org",
    "wikivoyage.org",
    "britannica.com",
    "lonelyplanet.com",
    "roughguides.com",
)

_CAMEROON_MARKERS = (
    "cameroun",
    "cameroon",
    "cameroonese",
    "cameroonian",
    "yaoundé",
    "yaounde",
    "douala",
    "buea",
    "limbe",
    "limbé",
    "kribi",
    "bamenda",
    "bafoussam",
    "mintoul",
    "mount cameroon",
    "mont cameroun",
)

# Strong signals the hit is about France / Europe "Sud-Ouest", not Cameroon.
_OFFTOPIC_MARKERS = (
    "cannes",
    "alpes-maritimes",
    "côte d'azur",
    "cote d'azur",
    "périgueux",
    "perigord",
    "nouvelle-aquitaine",
    "bordeaux",
    "occitanie",
    "île-de-france",
    "ile-de-france",
    "quai branly",
    "république centrafricaine",
    "central african",
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
    if d.endswith(".gov.cm") or d.endswith(".cm"):
        # Prefer cm institutional hosts
        for end in _TIER1:
            if d == end or d.endswith("." + end) or end in d:
                return 1
        if d.endswith(".gov.cm"):
            return 1
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
    # Cameroon relevance boost / penalty
    if any(m in blob for m in _CAMEROON_MARKERS) or domain.endswith(".cm"):
        bonus += 0.08
    if any(m in blob for m in _OFFTOPIC_MARKERS):
        bonus -= 0.25
    return max(0.05, min(0.95, base + bonus)), tier


_NEIGHBOR_ONLY = (
    "république fédérale du nigeria",
    "republique federale du nigeria",
    "république du tchad",
    "republique du tchad",
    "central african republic",
    "république centrafricaine",
)

_TOPIC_HINTS = {
    "FOOD": (
        "cuisine",
        "gastronomie",
        "plat",
        "food",
        "dish",
        "manger",
        "ndolé",
        "ndole",
        "eru",
        "plantain",
        "manioc",
        "poisson",
    ),
    "WEB_SEARCH": (
        "festival",
        "événement",
        "evenement",
        "event",
        "foire",
        "concert",
        "tourisme",
        "tourism",
        "culture",
    ),
    "CULTURE": ("culture", "festival", "patrimoine", "heritage", "tradition"),
}


def _topic_overlap(blob: str, intent: str, query: str) -> bool:
    hints = _TOPIC_HINTS.get(intent) or ()
    if hints and any(h in blob for h in hints):
        return True
    # Fall back to meaningful query tokens (>3 chars), excluding stopwords
    stop = {
        "quoi",
        "cest",
        "c'est",
        "les",
        "des",
        "une",
        "pour",
        "dans",
        "avec",
        "sur",
        "internet",
        "recherche",
        "quels",
        "quelle",
        "ont",
        "lieu",
        "this",
        "what",
        "the",
        "and",
        "for",
    }
    tokens = [
        t
        for t in query.casefold().replace("?", " ").replace("'", " ").split()
        if len(t) > 3 and t not in stop
    ]
    if not tokens:
        return True
    hits = sum(1 for t in tokens if t in blob)
    return hits >= max(1, min(2, len(tokens) // 3))


def _is_cameroon_relevant(
    ev: WebEvidence,
    *,
    query: str,
    intent: str = "",
) -> bool:
    """Reject European / unrelated hits when the user asked about Cameroon tourism."""
    q = (query or "").casefold()
    needs_cm = (
        "cameroun" in q
        or "cameroon" in q
        or "sud-ouest" in q
        or "south-west" in q
        or "southwest" in q
        or "mintoul" in q
        or bool(intent)
    )
    if not needs_cm:
        return True
    blob = f"{ev.title} {ev.snippet} {ev.domain}".casefold()
    if any(m in blob for m in _OFFTOPIC_MARKERS):
        if not any(m in blob for m in _CAMEROON_MARKERS) and not (ev.domain or "").endswith(
            ".cm"
        ):
            return False
    # Neighbor-country pages that barely mention Cameroon
    if any(m in blob for m in _NEIGHBOR_ONLY) and "cameroun" not in blob and "cameroon" not in blob:
        return False
    cm_ok = any(m in blob for m in _CAMEROON_MARKERS) or (ev.domain or "").endswith(".cm")
    if not cm_ok and ev.tier <= 2 and (
        "tourismo" in (ev.domain or "")
        or "tourism237" in (ev.domain or "")
        or "cameroun" in (ev.domain or "")
    ):
        cm_ok = True
    if not cm_ok:
        return False
    # Topic must roughly match (avoid crisis / biography pages for food/festival)
    if intent in _TOPIC_HINTS or any(
        t in q for t in ("nourriture", "food", "festival", "événement", "evenement", "cuisine")
    ):
        topic_intent = intent or (
            "FOOD"
            if any(t in q for t in ("nourriture", "food", "cuisine", "gastronomie"))
            else "WEB_SEARCH"
        )
        if not _topic_overlap(blob, topic_intent, q):
            return False
    return True


def validate_evidence(
    items: list[WebEvidence],
    *,
    query: str = "",
    intent: str = "",
) -> list[WebEvidence]:
    """Keep only usable evidence; tier-4 alone cannot make answerable."""
    kept: list[WebEvidence] = []
    seen_urls: set[str] = set()
    for ev in items:
        url = (ev.url or "").strip()
        snippet = (ev.snippet or "").strip()
        if not snippet or len(snippet) < 24:
            continue
        if not _is_cameroon_relevant(ev, query=query, intent=intent):
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
    # Tier-4 community alone is never enough for important claims
    strong = [e for e in evidence if e.tier <= 3]
    if not strong:
        return False
    # Need at least one tier 1–3 source that survived relevance filter
    if any(e.tier <= 2 for e in strong):
        return True
    # Tier-3 encyclopedic OK if relevance already filtered
    return len(strong) >= 1


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
