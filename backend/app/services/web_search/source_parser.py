"""Normalize raw provider rows into ``WebSearchResult``.

Only title / snippet / url / date ever leave this module — never page HTML.
Snippets that look like prompt-injection attempts are logged for audit but
kept (the LLM receives them inside ``<web_result>`` delimiters as untrusted data).
"""

from __future__ import annotations

import html
import logging
import re
from urllib.parse import urlparse

from app.services.web_search.models import WebSearchResult

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_SUSPICIOUS_RE = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"
    r"|disregard\s+(?:the\s+)?(?:previous|above|system)"
    r"|ignore\s+les\s+instructions"
    r"|oublie\s+(?:toutes\s+)?(?:les\s+)?instructions"
    r"|(?:^|\s)(?:system|assistant)\s*:"
    r"|</?\s*web_result"
    r"|you\s+are\s+now\s+",
    re.IGNORECASE,
)

_NEWS = (
    "cameroon-tribune", "journalducameroun", "actucameroun", "camer.be",
    "cameroon-info", "datacameroon", "bbc.", "rfi.fr", "france24", "jeuneafrique",
    "africanews", "lemonde.fr", "reuters", "apnews", "aljazeera", "voaafrique",
    "crtv.cm", "mimimefoinfos", "lebledparle", "stopblablacam",
)
_WIKI = ("wikipedia.org", "wikivoyage.org", "wikiwand", "kiddle.co", "britannica.com")
_BUSINESS = (
    "tripadvisor", "booking.com", "expedia", "hotels.com", "airbnb", "google.com/maps",
    "jumia", "facebook.com", "instagram.com", "yelp", "trip.com", "kayak",
)
_BLOG = ("blogspot", "wordpress", "medium.com", "substack", "blog")


def extract_domain(url: str) -> str:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def classify_source_type(domain: str, url: str = "") -> str:
    d = (domain or "").lower()
    u = (url or "").lower()
    if d.endswith(".gov.cm") or d.endswith(".gouv.cm") or ".gov" in d or ".gouv." in d:
        return "official"
    if d.endswith("unesco.org") or d.endswith(".int") or d.endswith(".edu"):
        return "official"
    if any(k in d for k in _WIKI):
        return "wiki"
    if any(k in d for k in _NEWS):
        return "news"
    if any(k in d or k in u for k in _BUSINESS):
        return "business"
    if any(k in d or k in u for k in _BLOG):
        return "blog"
    return "unknown"


def clean_text(raw: str | None, *, limit: int = 600) -> str:
    text = html.unescape(_TAG_RE.sub(" ", raw or ""))
    text = " ".join(text.split())
    return text[:limit]


def looks_like_injection(text: str) -> bool:
    return bool(_SUSPICIOUS_RE.search(text or ""))


def parse_result(
    *,
    title: str | None,
    url: str | None,
    snippet: str | None,
    published_at: str | None = None,
    raw_score: float | None = None,
    provider: str = "",
) -> WebSearchResult | None:
    url_c = (url or "").strip()
    title_c = clean_text(title, limit=160)
    snippet_c = clean_text(snippet)
    if not url_c.startswith(("http://", "https://")):
        return None
    if not title_c and not snippet_c:
        return None
    domain = extract_domain(url_c)
    if looks_like_injection(f"{title_c} {snippet_c}"):
        logger.warning(
            "[WEB] suspicious_snippet domain=%s url=%s", domain, url_c[:160]
        )
    return WebSearchResult(
        title=title_c or domain or "Web",
        url=url_c,
        domain=domain,
        snippet=snippet_c,
        source_type=classify_source_type(domain, url_c),
        published_at=(published_at or None),
        raw_score=raw_score,
        provider=provider,
    )


def dedupe_by_url(results: list[WebSearchResult]) -> list[WebSearchResult]:
    seen: set[str] = set()
    out: list[WebSearchResult] = []
    for r in results:
        key = r.url.split("#", 1)[0].rstrip("/").casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out
