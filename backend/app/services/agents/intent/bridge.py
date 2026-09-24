"""Progressive bridge: map IntentResult → legacy QueryRoute without replacing it.

The production path still uses ``app.services.ai.routing.route_query``.
This adapter is for dual-run / feature-flag experiments only.
"""

from __future__ import annotations

from app.services.agents.intent.models import IntentResult
from app.services.ai.routing import QueryRoute


def intent_to_legacy_route(result: IntentResult) -> QueryRoute:
    """Best-effort mapping onto the Phase-1 binary skip_kb / skip_web route."""
    if result.intent == "CLARIFICATION":
        # Prefer grounded clarification over hallucinated simple replies.
        return QueryRoute(
            kind="grounded",
            skip_kb=False,
            skip_web=True,
            reason=f"intent:{result.intent}:{result.reason}",
        )

    skip_kb = not result.needs_knowledge and not result.needs_places
    skip_web = not result.needs_web
    # Vision / booking still need some context usually.
    if result.needs_vision:
        skip_kb = True
        skip_web = True
    kind = "simple" if skip_kb and skip_web else "grounded"
    return QueryRoute(
        kind=kind,
        skip_kb=skip_kb,
        skip_web=skip_web,
        reason=f"intent:{result.intent}:conf={result.confidence:.2f}",
    )


def dual_route_observe(message: str) -> dict[str, object]:
    """Run legacy + Agent 1 side-by-side for observability (no behavior change)."""
    from app.services.agents.intent.router import classify_intent
    from app.services.ai.routing import route_query

    legacy = route_query(message)
    intent = classify_intent(message, mode="text")
    mapped = intent_to_legacy_route(intent)
    return {
        "legacy": {
            "kind": legacy.kind,
            "skip_kb": legacy.skip_kb,
            "skip_web": legacy.skip_web,
            "reason": legacy.reason,
        },
        "agent1": intent.observability(),
        "mapped": {
            "kind": mapped.kind,
            "skip_kb": mapped.skip_kb,
            "skip_web": mapped.skip_web,
            "reason": mapped.reason,
        },
        "agreement_skip_kb": legacy.skip_kb == mapped.skip_kb,
    }
