"""Compare legacy reply vs Agent 4 FinalResponse (diagnostic only)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.agent import ResponseGenerator
from app.services.agents.response.context import allowed_place_names
from app.services.agents.response.validate import contains_invented_place


async def compare_response_async(
    user_query: str,
    intent: IntentResult,
    knowledge: KnowledgeResult,
    tourism_plan: TourismPlan | None = None,
    *,
    legacy_text: str | None = None,
    response_mode: str = "text",
    locale: str | None = None,
) -> dict[str, Any]:
    agent = ResponseGenerator(prefer_deterministic=True)
    final = await agent.generate(
        user_query,
        intent,
        knowledge,
        tourism_plan,
        response_mode=response_mode,
        locale=locale,
    )
    allowed = allowed_place_names(knowledge, tourism_plan)
    return {
        "query": user_query,
        "legacy": {
            "text_chars": len(legacy_text or ""),
            "note": "legacy = current production reply if provided",
        },
        "agent4": final.observability(),
        "agent4_text_preview": (final.text or "")[:240],
        "allowed_place_count": len(allowed),
        "invented_suspect": contains_invented_place(
            final.text,
            allowed,
            suspects={"Place C", "Parc XYZ", "Hotel Fantôme"},
        ),
    }


def compare_response(
    user_query: str,
    intent: IntentResult,
    knowledge: KnowledgeResult,
    tourism_plan: TourismPlan | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return asyncio.run(
        compare_response_async(
            user_query,
            intent,
            knowledge,
            tourism_plan,
            **kwargs,
        )
    )
