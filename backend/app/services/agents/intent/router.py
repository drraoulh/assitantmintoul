"""Hybrid Intent Router — rules first, optional LLM only when ambiguous.

Voice / low-latency mode stays rules-only so TTFA is not inflated.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Literal

from app.services.agents.intent.extractors import extract_slots
from app.services.agents.intent.matrix import apply_matrix
from app.services.agents.intent.models import IntentResult
from app.services.agents.intent.rules import classify_with_rules
from app.services.agents.web_research.policy import forced_web_reason

logger = logging.getLogger(__name__)

_OPEN_QUESTION = re.compile(
    r"^\s*(?:qu['’]est[- ]ce\s+que?|c['’]est\s+quoi|qui|quand|combien|"
    r"pourquoi|comment\s+(?:se|s['’]|on|est)|quel(?:le)?s?\s+(?:est|sont|était)|que\s+signifie|"
    r"parle[sz]?[- ]moi|raconte[sz]?[- ]moi|explique[sz]?[- ]moi|dis[- ]moi|"
    r"what\s+(?:is|are|was)|who|when|how\s+(?:many|much)|why|tell\s+me\s+about|explain)\b"
    r".{6,}"
    r"|\bc['’]est\s+(?:qui|quoi|quand)\b",
    re.IGNORECASE,
)
_NATIONAL_SCOPE = re.compile(r"\b(?:au|du|le|in|of)\s+(?:cameroun|cameroon)\b", re.IGNORECASE)

def _region_of(city: str) -> str | None:
    try:
        from app.services.agents.knowledge.geography import city_admin_chain

        chain = city_admin_chain(city)
    except Exception:  # noqa: BLE001 — geography data is optional here
        return None
    return (chain or {}).get("region")


CONFIDENCE_THRESHOLD = 0.60
# Soft ceiling for voice: stay well under a second; rules path is typically <5ms.
VOICE_MAX_ROUTER_MS = 50.0


class IntentRouter:
    """AGENT 1 — Intent & Router.

    Does not draft the final user-facing answer.
    """

    def __init__(
        self,
        *,
        mode: Literal["text", "voice"] = "text",
        allow_llm_fallback: bool = False,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
    ) -> None:
        self.mode = mode
        self.allow_llm_fallback = allow_llm_fallback and mode != "voice"
        self.confidence_threshold = confidence_threshold

    def classify(
        self,
        message: str,
        *,
        locale: str | None = None,
        has_image: bool = False,
        request_id: str | None = None,
        conversation_context: str | None = None,
    ) -> IntentResult:
        started = time.perf_counter()
        rid = request_id or uuid.uuid4().hex[:12]

        # Merge tiny conversation hint (location) for anaphora: "Et la nourriture ?"
        enriched = message
        if conversation_context and conversation_context.strip():
            enriched = f"{conversation_context.strip()}\n{message}"

        slots = extract_slots(enriched, locale=locale)
        # Prefer slots from current message when present
        current_slots = extract_slots(message, locale=locale)
        if current_slots.city:
            slots.city = current_slots.city
            slots.region = current_slots.region
            slots.location = current_slots.location or current_slots.city
        elif not current_slots.region and _NATIONAL_SCOPE.search(message):
            slots.city = None
            slots.region = None
            slots.location = None
        if current_slots.region:
            slots.region = current_slots.region
            slots.location = current_slots.location or slots.location
        if current_slots.location and current_slots.region:
            slots.location = current_slots.location
        # Route / dish / visual cues only come from what the user just said.
        slots.origin = current_slots.origin
        slots.destination = current_slots.destination
        slots.dish = current_slots.dish
        slots.wants_images = current_slots.wants_images
        slots.wants_activities = current_slots.wants_activities
        if current_slots.destination:
            slots.city = current_slots.destination
            slots.location = current_slots.destination
            slots.region = _region_of(current_slots.destination) or current_slots.region

        hit = classify_with_rules(message, slots, has_image=has_image)
        intent = hit.intent
        confidence = hit.confidence
        reason = hit.reason
        source: Literal["rules", "hybrid", "llm", "fallback"] = "rules"

        # Low confidence → clarification, except real open questions, which go to
        # KB + optional web instead of asking the user to rephrase.
        if confidence < self.confidence_threshold and _OPEN_QUESTION.search(message):
            intent = "TOURISM_INFO"
            reason = f"open_question:{hit.reason}"
            confidence = self.confidence_threshold
            source = "fallback"
        elif confidence < self.confidence_threshold:
            intent = "CLARIFICATION"
            # Keep extracted slots only if explicitly present (extractors already do).
            reason = f"low_confidence:{hit.reason}"
            source = "fallback"

        # Optional LLM path — disabled by default and never on voice hot path.
        if (
            self.allow_llm_fallback
            and hit.confidence < self.confidence_threshold
            and hit.intent != "CLARIFICATION"
        ):
            # Placeholder for Phase 2.x LLM classifier; keep rules result for now.
            source = "hybrid"
            reason = f"{reason}|llm_skipped_phase21"

        force_web = intent == "WEB_SEARCH"
        caps = apply_matrix(
            intent,  # type: ignore[arg-type]
            duration_days=slots.duration_days,
            budget_xaf=slots.budget_xaf,
            city=slots.city,
            location=slots.location,
            force_web=force_web,
        )

        # Interests: ensure culture/nature tags from classified intent.
        interests = list(slots.interests)
        if intent == "CULTURE" and "culture" not in interests:
            interests.append("culture")
        if intent == "NATURE" and "nature" not in interests:
            interests.append("nature")
        if intent == "FOOD" and "food" not in interests:
            interests.append("food")

        needs_web = caps.needs_web
        web_reason: str | None = None
        # Regional gastronomy: KB packs list only a few dishes, so complement with
        # sourced web evidence. Voice skips this to keep TTFA low.
        if intent == "FOOD" and self.mode != "voice" and (slots.region or slots.city):
            needs_web = True
            web_reason = "REGIONAL_GASTRONOMY"
        needs_places = caps.needs_places
        if intent == "TRAVEL_ROUTE" and slots.wants_activities and slots.destination:
            needs_places = True
        forced = forced_web_reason(intent, message, is_route=bool(slots.destination))
        if forced:
            needs_web = True
            web_reason = forced

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        result = IntentResult(
            intent=intent,  # type: ignore[arg-type]
            location=slots.location,
            region=slots.region,
            city=slots.city,
            duration_days=slots.duration_days,
            budget_xaf=slots.budget_xaf,
            people=slots.people,
            children=slots.children,
            interests=interests,
            travel_style=slots.travel_style,
            start_date=slots.start_date,
            end_date=slots.end_date,
            language=slots.language,
            needs_knowledge=caps.needs_knowledge,
            needs_places=needs_places,
            needs_planner=caps.needs_planner,
            needs_web=needs_web,
            web_reason=web_reason,
            needs_booking=caps.needs_booking,
            needs_vision=caps.needs_vision,
            confidence=confidence if intent != "CLARIFICATION" else min(confidence, 0.59),
            reason=reason,
            request_id=rid,
            router_latency_ms=round(elapsed_ms, 3),
            source=source,
            origin=slots.origin,
            destination=slots.destination,
            dish=slots.dish,
            wants_images=slots.wants_images or intent == "IMAGE_SEARCH",
            wants_activities=slots.wants_activities,
        )

        if self.mode == "voice" and elapsed_ms > VOICE_MAX_ROUTER_MS:
            logger.warning(
                "intent_router_slow request_id=%s latency_ms=%.1f",
                rid,
                elapsed_ms,
            )
        else:
            logger.info("intent_router %s", result.observability())

        return result


def classify_intent(
    message: str,
    *,
    locale: str | None = None,
    mode: Literal["text", "voice"] = "text",
    has_image: bool = False,
    request_id: str | None = None,
    allow_llm_fallback: bool = False,
    conversation_context: str | None = None,
) -> IntentResult:
    """Module-level entry point for Agent 1."""
    router = IntentRouter(mode=mode, allow_llm_fallback=allow_llm_fallback)
    return router.classify(
        message,
        locale=locale,
        has_image=has_image,
        request_id=request_id,
        conversation_context=conversation_context,
    )
