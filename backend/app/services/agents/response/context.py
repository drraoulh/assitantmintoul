"""Compact structured context for Agent 4 (no huge documents)."""

from __future__ import annotations

import json
from typing import Any

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.evidence import build_allowed_evidence

_CONTENT_MAX = 320
_KNOWLEDGE_MAX = 8
_PLACES_MAX = 12

_FOOD_PLACE_HINTS = (
    "march",
    "restaur",
    "gastronom",
    "cuisine",
    "maquis",
    "menu",
    "plats",
    "food",
    "market",
    "dining",
)


def is_food_relevant_place(name: str | None, description: str | None, category: Any) -> bool:
    cats = category if isinstance(category, (list, tuple)) else [category]
    blob = " ".join(
        str(x) for x in [name or "", description or "", *[c for c in cats if c]]
    ).casefold()
    return any(h in blob for h in _FOOD_PLACE_HINTS)


def _chunk_priority(chunk: Any) -> int:
    cid = chunk.chunk_id or ""
    content = (chunk.content or "").casefold()
    if cid.startswith("culture-dish-"):
        return 0
    if "[web evidence" in content:
        return 1
    if (chunk.source_id or "").startswith("culture:"):
        return 2
    if cid.startswith("geo-"):
        return 0
    return 3


_WEB_PREFIXES = (
    ("[web evidence — institutional]", "high"),
    ("[web evidence — unverified]", "medium"),
    ("[web evidence — community]", "low"),
    ("[web evidence — low confidence]", "low"),
)


def wrap_web_content(content: str, source: str | None) -> str:
    """Delimit external web text so the LLM treats it as untrusted data."""
    text = (content or "").strip()
    confidence = "medium"
    for prefix, level in _WEB_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            confidence = level
            break
    text = text.replace("<web_result", "&lt;web_result").replace("</web_result", "&lt;/web_result")
    src = (source or "").replace('"', "")[:160]
    return f'<web_result source="{src}" confidence="{confidence}">{text}</web_result>'


def prioritized_knowledge(knowledge: KnowledgeResult) -> list[Any]:
    """Region packs and web evidence first — they are the most specific proofs."""
    return sorted(knowledge.knowledge, key=_chunk_priority)


def map_response_type(intent: IntentResult, plan: TourismPlan | None) -> str:
    if plan is not None and plan.feasibility == "INSUFFICIENT_DATA" and not plan.selected_places:
        return "INSUFFICIENT_INFORMATION"
    mapping = {
        "SIMPLE_QA": "SIMPLE_ANSWER",
        "TOURISM_INFO": "TOURISM_INFORMATION",
        "PLACE_SEARCH": "PLACE_LIST",
        "PLACE_DETAILS": "PLACE_DETAILS",
        "ITINERARY": "ITINERARY",
        "BUDGET_TRIP": "BUDGET_TRIP",
        "NATURE": "NATURE",
        "CULTURE": "CULTURE",
        "FOOD": "FOOD",
        "HOTEL": "HOTEL",
        "BOOKING": "BOOKING",
        "CLARIFICATION": "CLARIFICATION",
        "VISION": "VISION",
        "WEB_SEARCH": "TOURISM_INFORMATION",
        "TRAVEL_ROUTE": "TRAVEL_ROUTE",
        "IMAGE_SEARCH": "IMAGES",
    }
    return mapping.get(intent.intent, "TOURISM_INFORMATION")


def resolve_language(intent: IntentResult, locale: str | None = None) -> str:
    if intent.language in {"fr", "en"}:
        return intent.language
    if locale and locale.lower().startswith("en"):
        return "en"
    return "fr"


def build_structured_context(
    user_query: str,
    intent: IntentResult,
    knowledge: KnowledgeResult,
    tourism_plan: TourismPlan | None,
    *,
    response_mode: str = "text",
) -> dict[str, Any]:
    """Serialize only what Agent 4 needs — compact and grounded."""
    places = []
    candidate_places = knowledge.places
    if intent.intent == "FOOD":
        candidate_places = [
            p
            for p in knowledge.places
            if is_food_relevant_place(p.name, p.description, p.category)
        ]
    for place in candidate_places[:_PLACES_MAX]:
        places.append(
            {
                "place_id": place.place_id,
                "name": place.name,
                "city": place.city,
                "region": place.region,
                "description": _clip(place.description),
                "cultural_info": _clip(place.cultural_info),
                "eco_info": _clip(place.eco_info),
                "activities": list(place.activities)[:8],
                "category": list(place.category),
                "eco_tags": list(place.eco_tags),
                "estimated_cost_xaf": place.estimated_cost_xaf,
                "recommended_duration_hours": place.recommended_duration_hours,
                "best_period": place.best_period,
            }
        )

    knowledge_items = []
    for chunk in prioritized_knowledge(knowledge)[:_KNOWLEDGE_MAX]:
        content = _clip(chunk.content, _CONTENT_MAX)
        is_web = "[web evidence" in (chunk.content or "")[:40]
        if is_web:
            content = wrap_web_content(content or "", chunk.source_id)
        item = {
            "chunk_id": chunk.chunk_id,
            "title": chunk.title,
            "content": content,
            "source_id": chunk.source_id,
            "provenance": "web" if is_web else "smartmboa",
        }
        tags = (chunk.chunk_id or "").split(":")[3:] if is_web else []
        if "transport" in tags or "destination" in tags:
            item["phase"] = "transport" if "transport" in tags else "destination"
        if "reverse" in tags:
            item["direction"] = "reverse"
        knowledge_items.append(item)

    sources = []
    for src in knowledge.sources[:8]:
        sources.append(
            {
                "source_id": src.source_id,
                "name": src.name,
                "url": src.url,
            }
        )

    plan_payload = None
    if tourism_plan is not None:
        plan_payload = {
            "plan_type": tourism_plan.plan_type,
            "duration_days": tourism_plan.duration_days,
            "budget_xaf": tourism_plan.budget_xaf,
            "budget_status": tourism_plan.budget_status,
            "known_cost_xaf": tourism_plan.known_cost_xaf,
            "total_estimated_cost_xaf": tourism_plan.total_estimated_cost_xaf,
            "feasibility": tourism_plan.feasibility,
            "selected_places": list(tourism_plan.selected_places),
            "interests_covered": list(tourism_plan.interests_covered),
            "interests_not_covered": list(tourism_plan.interests_not_covered),
            "warnings": list(tourism_plan.warnings)[:8],
            "missing_information": list(tourism_plan.missing_information)[:8],
            "days": [
                {
                    "day": day.day,
                    "title": day.title,
                    "city": day.city,
                    "estimated_day_cost_xaf": day.estimated_day_cost_xaf,
                    "notes": list(day.notes)[:4],
                    "places": [
                        {
                            "place_id": item.place_id,
                            "place_name": item.place_name,
                            "order": item.order,
                            "estimated_duration_hours": item.estimated_duration_hours,
                            "estimated_cost_xaf": item.estimated_cost_xaf,
                            "distance_from_previous_km": item.distance_from_previous_km,
                            "distance_type": "geographic",
                            "category": list(item.category),
                            "eco_tags": list(item.eco_tags),
                        }
                        for item in day.places
                    ],
                }
                for day in tourism_plan.days
            ],
        }

    evidence = build_allowed_evidence(intent, knowledge, tourism_plan)
    return {
        "user_query": user_query,
        "response_mode": response_mode,
        "intent": {
            "intent": intent.intent,
            "chat_intent": intent.chat_intent,
            "origin": intent.origin,
            "destination": intent.destination,
            "dish": intent.dish,
            "wants_activities": intent.wants_activities,
            "city": intent.city,
            "region": intent.region,
            "duration_days": intent.duration_days,
            "budget_xaf": intent.budget_xaf,
            "people": intent.people,
            "children": intent.children,
            "interests": list(intent.interests),
            "confidence": intent.confidence,
            "needs_web": intent.needs_web,
        },
        "places": places,
        "knowledge": knowledge_items,
        "sources": sources,
        "missing_information": list(
            dict.fromkeys(
                list(knowledge.missing_information)
                + (list(tourism_plan.missing_information) if tourism_plan else [])
            )
        )[:12],
        "tourism_plan": plan_payload,
        "allowed_evidence": evidence.as_prompt_dict(),
    }


def context_as_prompt_block(context: dict[str, Any]) -> str:
    return (
        "STRUCTURED CONTEXT (authoritative — ONLY source of tourism facts):\n"
        "Use allowed_evidence as the whitelist for named places, costs, activities, URLs.\n"
        + json.dumps(context, ensure_ascii=False, indent=2)
    )


def allowed_place_names(knowledge: KnowledgeResult, plan: TourismPlan | None) -> set[str]:
    names = {p.name for p in knowledge.places if p.name}
    if plan:
        for day in plan.days:
            for item in day.places:
                if item.place_name:
                    names.add(item.place_name)
    return names


def _clip(text: str | None, max_chars: int = _CONTENT_MAX) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1].rstrip() + "…"
