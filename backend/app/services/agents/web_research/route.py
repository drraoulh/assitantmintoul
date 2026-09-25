"""Origin → destination source selection and transport fact extraction.

Transport evidence must concern the requested pair (both towns named); a page about
« Foumban → Cameroun » or « Douala → Kribi » is not an answer to « Yaoundé → Foumban ».
Facts are copied from the snippets (durations, distances, amounts with their own
currency, connection / departure sentences) — nothing is converted or invented.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from app.services.agents.web_research.models import WebEvidence

MAX_TRANSPORT_SOURCES = 4
MAX_DESTINATION_SOURCES = 3


def fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _city_re(city: str) -> str:
    return rf"\b{re.escape(fold(city))}\b"


def _names(blob: str, city: str) -> bool:
    return bool(re.search(_city_re(city), blob))


def _leg(blob: str, a: str, b: str) -> bool:
    a_re, b_re = _city_re(a), _city_re(b)
    return bool(
        re.search(
            rf"(?:\bde|\bd'|\bdepuis|\bfrom|\bentre|\bbetween)\s*{a_re}.{{0,40}}?"
            rf"(?:\ba|\bau|\bvers|\bpour|\bjusqu'?a|\bto|\bet|\band)\s+{b_re}",
            blob,
        )
        or re.search(rf"{a_re}\s*(?:->|→|–|—|-|/|to|a)\s*{b_re}", blob)
    )


def route_direction(ev: WebEvidence, origin: str, dest: str) -> str | None:
    """``direct`` / ``reverse`` / ``both`` (pair named, no direction) / None (off-route)."""
    blob = fold(f"{ev.title} {ev.snippet} {ev.url}")
    if not (_names(blob, origin) and _names(blob, dest)):
        return None
    if _leg(blob, origin, dest):
        return "direct"
    if _leg(blob, dest, origin):
        return "reverse"
    return "both"


_CONCRETE = re.compile(
    r"\d+\s*(?:h\b|heures?|hours?|hrs?|min|km)|(?:fcfa|xaf|f\s?cfa|usd|eur|\$|€|£)|"
    r"\b(?:agences?|agency|gare|motor\s?park|depart|departure|horaires?|schedule|"
    r"correspondance|direct|bus|taxi)\b"
)


def concreteness(ev: WebEvidence) -> int:
    return len(_CONCRETE.findall(fold(f"{ev.title} {ev.snippet}")))


def select_transport(
    evidence: list[WebEvidence], origin: str | None, dest: str, *, limit: int = MAX_TRANSPORT_SOURCES
) -> list[WebEvidence]:
    kept: list[WebEvidence] = []
    for ev in evidence:
        ev.phase = "transport"
        if origin:
            ev.route_match = route_direction(ev, origin, dest)
            if ev.route_match is None:
                continue
            ev.low_confidence = False
        elif not _names(fold(f"{ev.title} {ev.snippet}"), dest):
            continue
        kept.append(ev)
    order = {"direct": 0, "both": 1, None: 1, "reverse": 2}
    kept.sort(key=lambda e: (order.get(e.route_match, 1), -concreteness(e), -e.rank_score))
    return kept[:limit]


_ROUTE_PAGE = re.compile(
    r"\b(?:comment\s+(?:aller|se\s+rendre)|how\s+to\s+get|moyens?\s+d'aller|"
    r"ways?\s+to\s+get|rome2rio|bus\s+tickets?|billets?\s+de\s+bus)\b"
)


def select_destination(
    evidence: list[WebEvidence], dest: str, *, limit: int = MAX_DESTINATION_SOURCES
) -> list[WebEvidence]:
    kept: list[WebEvidence] = []
    for ev in evidence:
        ev.phase = "destination"
        blob = fold(f"{ev.title} {ev.snippet} {ev.url}")
        if not _names(blob, dest) or _ROUTE_PAGE.search(blob):
            continue
        kept.append(ev)
    kept.sort(key=lambda e: -e.rank_score)
    return kept[:limit]


# --- transport facts ---------------------------------------------------------------

_FLIGHT = re.compile(r"\b(?:vols?|avion|flights?|fly|flying|aeroport|airport)\b")
_DURATION = re.compile(
    r"\b(?P<h>\d{1,2})\s*(?:h|hr|hrs|heures?|hours?)\b(?!\s*(?:/|sur|a|on)\s*\d|\s*(?:/|sur)\s*24)\.?\s*(?:et\s+)?"
    r"(?:(?P<m>\d{1,2})\s*(?:min|minutes?|mn|m)\b|(?P<m2>\d{2})\b(?!\s*(?:km|h\b|heures?|fcfa|xaf|\d)))?"
    r"|\b(?P<h3>\d{1,2})\s*h(?P<m3>\d{2})\b"
)
_DISTANCE = re.compile(r"\b(\d{2,4}(?:[.,]\d)?)\s*km\b")
_FOREIGN_PRICE = re.compile(
    r"(us\$|\$|€|£)\s?(\d[\d,.]*)(?:\s*[-–]\s*(?:us\$|\$|€|£)?\s?(\d[\d,.]*))?"
    r"|\b(\d[\d,.]*)(?:\s*[-–]\s*(\d[\d,.]*))?\s*(usd|eur|euros?|gbp|dollars?)\b"
)
_LOCAL_PRICE = re.compile(
    r"\b(\d{1,3}(?:[\s.]\d{3})+|\d{3,6})(?:\s*[-–a]\s*(\d{1,3}(?:[\s.]\d{3})+|\d{3,6}))?\s*"
    r"(?:fcfa|f\s?cfa|xaf|francs?\s+cfa|frs?)\b"
)
_CURRENCY = {"$": "USD", "us$": "USD", "€": "EUR", "£": "GBP", "usd": "USD", "dollar": "USD",
             "dollars": "USD", "eur": "EUR", "euro": "EUR", "euros": "EUR", "gbp": "GBP"}
_CONNECTION = re.compile(
    r"\b(?:pas\s+de\s+(?:liaison|connexion|ligne|bus)\s+direct\w*|no\s+direct|"
    r"correspondances?|changer\s+a|via\s+\w+|puis\s+(?:prendre|le|un)|then\s+take|transfer|"
    r"escale|en\s+passant\s+par)\b"
)
_DEPARTURE = re.compile(
    r"\b(?:gares?\s+routieres?|agences?\s+de\s+voyages?|agences?|travel\s+agenc\w+|motor\s?parks?|"
    r"departs?|departures?|terminal|point\s+de\s+depart|quartier)\b"
)
_MODES = (
    ("bus", re.compile(r"\b(?:bus|autocars?|cars?\s+de\s+ligne|coach(?:es)?)\b")),
    ("taxi", re.compile(r"\b(?:taxis?|clandos?)\b")),
    ("voiture", re.compile(r"\b(?:voitures?|automobile|en\s+auto|car\b|drive|driving|conduire)\b")),
    ("train", re.compile(r"\b(?:trains?|camrail)\b")),
    ("avion", _FLIGHT),
)
_FROM = re.compile(r"\b(?:from|a\s+partir\s+de|des|starting\s+at)\s*$")
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?])\s+|\s+(?:\.\.\.|…|·|\|)\s+|\s;\s")


@dataclass
class TransportFacts:
    modes: dict[str, list[str]] = field(default_factory=dict)
    durations: list[tuple[int, str]] = field(default_factory=list)
    distances: list[tuple[float, str]] = field(default_factory=list)
    # (amount, currency, domain, minimum) — minimum when the source says « from / à partir de ».
    prices: list[tuple[str, str, str, bool]] = field(default_factory=list)
    connections: list[tuple[str, str]] = field(default_factory=list)
    departures: list[tuple[str, str]] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.modes or self.durations or self.distances or self.prices
                    or self.connections or self.departures)


def _amount(raw: str) -> str:
    return raw.strip().rstrip(".,")


def _clauses(text: str) -> list[str]:
    return [c.strip(" -•") for c in _CLAUSE_SPLIT.split(text) if len(c.strip()) > 8]


def extract_transport_facts(items: list[tuple[str, str]]) -> TransportFacts:
    """``items`` = (snippet, domain). Values are copied verbatim, never converted."""
    facts = TransportFacts()
    for text, domain in items:
        for clause in _clauses(text):
            low = fold(clause)
            flight = bool(_FLIGHT.search(low))
            for label, pattern in _MODES:
                if pattern.search(low):
                    doms = facts.modes.setdefault(label, [])
                    if domain not in doms:
                        doms.append(domain)
            if not flight:
                for m in _DURATION.finditer(low):
                    h = int(m.group("h") or m.group("h3"))
                    mins = int(m.group("m") or m.group("m2") or m.group("m3") or 0)
                    if 1 <= h <= 30 and mins < 60:
                        facts.durations.append((h * 60 + mins, domain))
                for m in _DISTANCE.finditer(low):
                    km = float(m.group(1).replace(",", "."))
                    if 10 <= km <= 2000:
                        facts.distances.append((km, domain))
                lowered = clause.casefold()
                for m in _FOREIGN_PRICE.finditer(lowered):
                    if m.group(1):
                        cur, lo, hi = m.group(1), m.group(2), m.group(3)
                    else:
                        lo, hi, cur = m.group(4), m.group(5), m.group(6)
                    amount = f"{_amount(lo)}–{_amount(hi)}" if hi else _amount(lo)
                    minimum = bool(_FROM.search(fold(lowered[max(0, m.start() - 16):m.start()])))
                    facts.prices.append((amount, _CURRENCY.get(cur, cur.upper()), domain, minimum))
                for m in _LOCAL_PRICE.finditer(low):
                    lo, hi = m.group(1), m.group(2)
                    amount = f"{_amount(lo)}–{_amount(hi)}" if hi else _amount(lo)
                    minimum = bool(_FROM.search(low[max(0, m.start() - 16):m.start()]))
                    facts.prices.append((amount, "FCFA", domain, minimum))
            sentence = " ".join(clause.split())[:220]
            if _CONNECTION.search(low):
                if not any(sentence == c for c, _ in facts.connections):
                    facts.connections.append((sentence, domain))
            elif _DEPARTURE.search(low) and not flight:
                if not any(sentence == c for c, _ in facts.departures):
                    facts.departures.append((sentence, domain))
    return facts


def format_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h} h {m:02d}" if m else f"{h} h"
