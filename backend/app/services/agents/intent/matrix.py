"""Central routing matrix — which capabilities each intent needs.

Easy to edit without touching the classifier.
Optional planner for thematic intents is controlled via ``optional_planner``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.services.agents.intent.models import Intent, IntentName


@dataclass(frozen=True)
class CapabilityFlags:
    needs_knowledge: bool = False
    needs_places: bool = False
    needs_planner: bool = False
    needs_web: bool = False
    needs_booking: bool = False
    needs_vision: bool = False
    # When True, planner may be set if duration/budget slots are present.
    optional_planner: bool = False
    optional_web: bool = False
    optional_places: bool = False


# Intent → default capability matrix (Phase 2.1).
ROUTING_MATRIX: Mapping[IntentName, CapabilityFlags] = {
    Intent.SIMPLE_QA.value: CapabilityFlags(needs_knowledge=True),
    Intent.TOURISM_INFO.value: CapabilityFlags(
        needs_knowledge=True,
        optional_web=True,
    ),
    Intent.PLACE_SEARCH.value: CapabilityFlags(
        needs_knowledge=True,
        needs_places=True,
    ),
    Intent.PLACE_DETAILS.value: CapabilityFlags(
        needs_knowledge=True,
        needs_places=True,
    ),
    Intent.ITINERARY.value: CapabilityFlags(
        needs_knowledge=True,
        needs_places=True,
        needs_planner=True,
    ),
    Intent.BUDGET_TRIP.value: CapabilityFlags(
        needs_knowledge=True,
        needs_places=True,
        needs_planner=True,
    ),
    Intent.NATURE.value: CapabilityFlags(
        needs_knowledge=True,
        needs_places=True,
        optional_planner=True,
    ),
    Intent.CULTURE.value: CapabilityFlags(
        needs_knowledge=True,
        needs_places=True,
        optional_planner=True,
        optional_web=True,
    ),
    Intent.FOOD.value: CapabilityFlags(
        needs_knowledge=True,
        optional_places=True,
        optional_web=True,
    ),
    Intent.HOTEL.value: CapabilityFlags(
        needs_knowledge=True,
        needs_places=True,
        optional_web=True,
    ),
    Intent.BOOKING.value: CapabilityFlags(
        needs_places=True,
        needs_web=True,
        needs_booking=True,
    ),
    Intent.VISION.value: CapabilityFlags(needs_vision=True),
    Intent.WEB_SEARCH.value: CapabilityFlags(needs_web=True),
    Intent.CLARIFICATION.value: CapabilityFlags(needs_knowledge=True),
}


def apply_matrix(
    intent: IntentName,
    *,
    duration_days: int | None = None,
    budget_xaf: int | None = None,
    city: str | None = None,
    location: str | None = None,
    force_web: bool = False,
) -> CapabilityFlags:
    """Resolve final capability flags for an intent + extracted slots."""
    base = ROUTING_MATRIX.get(intent, CapabilityFlags(needs_knowledge=True))
    needs_planner = base.needs_planner
    needs_web = base.needs_web or force_web
    needs_places = base.needs_places

    if base.optional_planner and (duration_days is not None or budget_xaf is not None):
        needs_planner = True
    if base.optional_web and force_web:
        needs_web = True
    if base.optional_places and (city or location):
        needs_places = True

    return CapabilityFlags(
        needs_knowledge=base.needs_knowledge,
        needs_places=needs_places,
        needs_planner=needs_planner,
        needs_web=needs_web,
        needs_booking=base.needs_booking,
        needs_vision=base.needs_vision,
        optional_planner=base.optional_planner,
        optional_web=base.optional_web,
        optional_places=base.optional_places,
    )
