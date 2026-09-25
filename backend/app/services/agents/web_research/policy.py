"""When to search the web (N3).

1. Forced by the backend (never left to the LLM): current information,
   hotel search, restaurant search.
2. Forbidden: greetings / small talk / clarification.
3. Optional: every other intent — Qwen decides through a structured
   ``web_search`` tool call.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

FORCED_CURRENT_INFORMATION = "FORCED_CURRENT_INFORMATION"
FORCED_HOTEL_SEARCH = "FORCED_HOTEL_SEARCH"
FORCED_RESTAURANT_SEARCH = "FORCED_RESTAURANT_SEARCH"
FORCED_REASONS = {FORCED_CURRENT_INFORMATION, FORCED_HOTEL_SEARCH, FORCED_RESTAURANT_SEARCH}

_FORBIDDEN_INTENTS = {"CLARIFICATION"}

_RESTAURANT = re.compile(
    r"\b(restaurants?|restos?|maquis|brasseries?|snack[- ]?bars?|o[uù]\s+manger|"
    r"where\s+to\s+eat|places?\s+to\s+eat|eateries|dining|bars?\s+[àa]\s+poissons?)\b",
    re.IGNORECASE,
)

MAX_TOOL_QUERIES = 3

WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Recherche des informations actuelles ou spécifiques sur Internet (prix, "
            "événements, restaurants, hôtels, faits récents). Ne pas utiliser pour les "
            "salutations ou le small talk."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": MAX_TOOL_QUERIES,
                    "description": "1 à 3 requêtes courtes et ciblées, en français et/ou anglais",
                },
                "reason": {
                    "type": "string",
                    "description": "Pourquoi une recherche Web est nécessaire ici",
                },
            },
            "required": ["queries", "reason"],
        },
    },
}

WEB_TOOL_SYSTEM_PROMPT = """Tu es le module de décision de recherche Web de SmartMboa, guide touristique du Cameroun.
Tu reçois la question de l'utilisateur et un résumé de ce que la base de connaissances SmartMboa (KB) contient déjà.
Ta seule tâche : décider s'il faut appeler l'outil web_search. Tu ne rédiges JAMAIS la réponse finale.

Appelle web_search (1 à 3 requêtes courtes, FR et/ou EN, toujours avec « Cameroun » ou la région/ville) quand :
- la KB est vide, faible ou ne couvre pas précisément la question ;
- la question porte sur des informations qui changent (prix, horaires, événements, actualité, ouvertures) ;
- l'utilisateur demande explicitement de chercher ou une source ;
- la question vise un plat, un lieu, une coutume ou un fait précis absent du résumé KB.

N'appelle PAS web_search quand :
- c'est une salutation, un remerciement ou du small talk ;
- la KB répond déjà clairement (ex. un fait géographique stable comme la capitale) ;
- la question est une demande de clarification ou d'itinéraire que la KB couvre.

Si aucune recherche n'est nécessaire, réponds uniquement : NO_SEARCH"""


@dataclass
class WebToolDecision:
    search: bool
    queries: list[str] = field(default_factory=list)
    reason: str = ""


def web_forbidden(intent: str, reason: str | None = None) -> bool:
    return intent in _FORBIDDEN_INTENTS or (reason or "").endswith("greeting")


def forced_web_reason(intent: str, query: str) -> str | None:
    if intent == "WEB_SEARCH":
        return FORCED_CURRENT_INFORMATION
    if intent == "HOTEL":
        return FORCED_HOTEL_SEARCH
    if intent == "FOOD" and _RESTAURANT.search(query or ""):
        return FORCED_RESTAURANT_SEARCH
    return None


def build_decision_messages(user_query: str, kb_summary: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": WEB_TOOL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Question utilisateur : {user_query}\n\nRésumé KB :\n{kb_summary}",
        },
    ]


def _clean_queries(raw: Any) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for q in raw:
        text = " ".join(str(q).split())[:120]
        if text and text not in out:
            out.append(text)
    return out[:MAX_TOOL_QUERIES]


def parse_tool_decision(message: dict[str, Any] | None) -> WebToolDecision:
    """Read an OpenAI-style assistant message (tool_calls or JSON fallback)."""
    if not message:
        return WebToolDecision(search=False, reason="no_message")
    for call in message.get("tool_calls") or []:
        fn = (call or {}).get("function") or {}
        if fn.get("name") != "web_search":
            continue
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        queries = _clean_queries(args.get("queries"))
        if queries:
            return WebToolDecision(True, queries, str(args.get("reason") or "")[:200])
    content = str(message.get("content") or "")
    if "NO_SEARCH" in content.upper():
        return WebToolDecision(search=False, reason="model_declined")
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            data = {}
        args = data.get("arguments", data) if isinstance(data, dict) else {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        queries = _clean_queries(args.get("queries") if isinstance(args, dict) else None)
        if queries:
            return WebToolDecision(True, queries, str(args.get("reason") or "")[:200])
    return WebToolDecision(search=False, reason="no_tool_call")


def kb_summary(knowledge: Any) -> str:
    if knowledge is None:
        return "KB vide."
    titles = [
        (c.title or c.chunk_id or "")[:60]
        for c in (knowledge.knowledge or [])[:6]
    ]
    places = [p.name for p in (knowledge.places or [])[:5] if p.name]
    return (
        f"complétude={knowledge.knowledge_completeness}; "
        f"lieux_vérifiés={len(knowledge.places or [])}; "
        f"extraits={len(knowledge.knowledge or [])}; "
        f"faits_géo={knowledge.geo_facts_count}\n"
        f"titres des extraits : {', '.join(t for t in titles if t) or 'aucun'}\n"
        f"lieux : {', '.join(places) or 'aucun'}"
    )
