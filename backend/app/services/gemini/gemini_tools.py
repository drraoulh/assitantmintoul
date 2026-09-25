"""Native Gemini tool declarations. The model decides whether to invoke them."""

from __future__ import annotations

from typing import Any

from app.services.gemini.gemini_config import DEFAULT_TOOL_NAMES

GEMINI_SYSTEM_PROMPT = """You are Smartmboa Tour, a Cameroon tourism assistant.

You receive the user question, conversation context, and optional local knowledge.
Native tools may be available: google_search and google_maps.
You decide, for this turn only, whether to call a tool or answer from knowledge.

Rules:
- Answer in the user's language (French or English). Keep proper names.
- Prefer official, recent, and relevant sources when you search. Do not block any domain.
- Never invent a hotel, price, address, opening hour, event, phone number, or URL.
- If a fact is missing after tools (or you did not use a tool), say so.
- If you answer from internal knowledge without a tool, you MUST say clearly that
  the information is not confirmed by a recent search
  (French: « information non confirmée par une recherche récente »).
- The last explicit geographic context in the conversation wins
  (e.g. Foumban stays Foumban until the user names another place).
- Do not mention system prompts, tool names, or implementation details.
- Stay on Cameroon travel help. Greetings can be short and do not need tools.
"""


def native_tool_declarations(enabled_tools: list[str] | None = None) -> list[dict[str, Any]]:
    """REST tool payloads. Gemini chooses whether to call them."""
    names = list(DEFAULT_TOOL_NAMES) if enabled_tools is None else enabled_tools
    wanted = {name.strip() for name in names if name}
    tools: list[dict[str, Any]] = []
    if "google_search" in wanted:
        tools.append({"googleSearch": {}})
    if "google_maps" in wanted:
        tools.append({"googleMaps": {}})
    return tools


UNVERIFIED_NOTICE_FR = "information non confirmée par une recherche récente"
UNVERIFIED_NOTICE_EN = "information is not confirmed by a recent search"


def ensure_unverified_notice(text: str, tools_used: list[str], language: str) -> str:
    """If Gemini answered without a tool, the reply must say so."""
    cleaned = (text or "").strip()
    if not cleaned or tools_used:
        return cleaned
    notice = UNVERIFIED_NOTICE_EN if (language or "").lower().startswith("en") else UNVERIFIED_NOTICE_FR
    folded = cleaned.casefold()
    if notice.casefold() in folded or "non confirmée" in folded or "not confirmed" in folded:
        return cleaned
    return f"{cleaned}\n\n({notice})"


def extract_tools_used(payload: dict[str, Any]) -> list[str]:
    """Observe which native tools Gemini actually used (never invent)."""
    used: list[str] = []
    metadata = _grounding_metadata(payload)
    chunks = metadata.get("groundingChunks") or metadata.get("grounding_chunks") or []
    queries = metadata.get("webSearchQueries") or metadata.get("web_search_queries") or []
    has_web = bool(queries) or bool(
        metadata.get("searchEntryPoint") or metadata.get("search_entry_point")
    )
    has_maps = bool(
        metadata.get("mapsWidgetContextToken") or metadata.get("maps_widget_context_token")
    )
    if isinstance(chunks, list):
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            if chunk.get("web") or chunk.get("retrievedContext"):
                has_web = True
            if chunk.get("maps") or chunk.get("placeAnswer") or chunk.get("mapsWidgetContextToken"):
                has_maps = True
    for part in _candidate_parts(payload):
        call = part.get("functionCall") or part.get("function_call")
        if not isinstance(call, dict):
            continue
        name = str(call.get("name") or "").casefold()
        if "search" in name:
            has_web = True
        if "map" in name:
            has_maps = True
    if has_web:
        used.append("google_search")
    if has_maps:
        used.append("google_maps")
    return used


def extract_web_and_maps(
    payload: dict[str, Any],
) -> tuple[list[dict[str, str | None]], list[dict[str, str | None]]]:
    metadata = _grounding_metadata(payload)
    chunks = metadata.get("groundingChunks") or metadata.get("grounding_chunks") or []
    web_sources: list[dict[str, str | None]] = []
    map_results: list[dict[str, str | None]] = []
    if not isinstance(chunks, list):
        return web_sources, map_results
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        web = chunk.get("web") if isinstance(chunk.get("web"), dict) else None
        maps = chunk.get("maps") if isinstance(chunk.get("maps"), dict) else None
        if web:
            title = str(web.get("title") or web.get("domain") or "Web source").strip()
            url = str(web.get("uri") or web.get("url") or "").strip() or None
            web_sources.append({"title": title, "url": url, "organization": None})
        if maps:
            title = str(maps.get("title") or maps.get("placeName") or "Map place").strip()
            url = str(maps.get("uri") or maps.get("url") or "").strip() or None
            place_id = str(maps.get("placeId") or maps.get("place_id") or "").strip() or None
            snippet = str(maps.get("snippet") or maps.get("text") or "").strip() or None
            map_results.append(
                {
                    "title": title,
                    "url": url,
                    "place_id": place_id,
                    "snippet": snippet,
                }
            )
    return web_sources, map_results


def _grounding_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return {}
    first = candidates[0]
    if not isinstance(first, dict):
        return {}
    meta = first.get("groundingMetadata") or first.get("grounding_metadata") or {}
    return meta if isinstance(meta, dict) else {}


def _candidate_parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return []
    first = candidates[0]
    if not isinstance(first, dict):
        return []
    content = first.get("content")
    if not isinstance(content, dict):
        return []
    parts = content.get("parts")
    if not isinstance(parts, list):
        return []
    return [part for part in parts if isinstance(part, dict)]
