"""Deterministic KnowledgeResult / TourismPlan → ChatResponse UI payloads.

No LLM. Overhead target < 50 ms. Never invents coordinates, prices, or URLs.
"""

from __future__ import annotations

import time
from typing import Any

from app.schemas.chat_ui import (
    ActionUI,
    BookingUI,
    BudgetItemUI,
    BudgetUI,
    HotelUI,
    ItineraryDayUI,
    ItineraryItemUI,
    ItineraryUI,
    MapCenterUI,
    MapMarkerUI,
    MapUI,
    PlaceUI,
    SourceUI,
    VisionUI,
)
from app.services.agents.knowledge.models import KnowledgeResult, PlaceEvidence
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.models import FinalResponse

_HOTEL_HINTS = ("hotel", "hôtel", "heberg", "héberg", "lodge", "resort", "auberge", "inn")


def build_structured_ui(
    *,
    final: FinalResponse | None = None,
    knowledge: KnowledgeResult | None = None,
    plan: TourismPlan | None = None,
    vision_summary: str | None = None,
    language: str = "fr",
) -> dict[str, Any]:
    """Return a dict of ChatResponse structured fields + ``structured_build_ms``."""
    t0 = time.perf_counter()

    response_type = (
        (final.response_type if final else None)
        or (knowledge.intent if knowledge else None)
        or "SIMPLE_ANSWER"
    )
    # Normalize intent-ish leftovers to Agent 4 response types when needed.
    response_type = _normalize_response_type(str(response_type), plan)

    places = _places_ui(knowledge)
    hotels = _hotels_ui(places, knowledge, response_type)
    # Hotel intents: keep places as hotel places too for cards.
    if response_type == "HOTEL" and hotels and not places:
        places = [
            PlaceUI(
                id=h.id,
                name=h.name,
                description=h.description,
                category="hotel",
                city=None,
                region=None,
                latitude=None,
                longitude=None,
                image_url=h.image_url,
                source_url=h.source_url,
                estimated_cost_xaf=h.price,
            )
            for h in hotels
        ]

    map_ui = _map_ui(places)
    itinerary = _itinerary_ui(plan, language=language)
    budget = _budget_ui(plan, language=language)
    booking = _booking_ui(response_type, language=language)
    vision = _vision_ui(vision_summary, places)
    ui_sources = _sources_ui(final, knowledge)
    actions = _actions_ui(places, map_ui, itinerary, hotels, ui_sources, language=language)

    # Drop empty collections that confuse clients for non-tourism answers.
    if response_type in {"SIMPLE_ANSWER", "CLARIFICATION"} and not places:
        map_ui = None
        itinerary = None
        budget = None

    elapsed = round((time.perf_counter() - t0) * 1000.0, 3)
    return {
        "response_type": response_type,
        "places": places,
        "map": map_ui,
        "itinerary": itinerary,
        "budget": budget,
        "hotels": hotels,
        "booking": booking,
        "vision": vision,
        "ui_sources": ui_sources,
        "actions": actions,
        "structured_build_ms": elapsed,
    }


def apply_structured_ui(chat_fields: dict[str, Any], ui: dict[str, Any]) -> dict[str, Any]:
    """Merge UI payload into a ChatResponse constructor kwargs dict."""
    out = dict(chat_fields)
    out.update(ui)
    if out.get("text") is None and out.get("message"):
        out["text"] = out["message"]
    return out


def _normalize_response_type(raw: str, plan: TourismPlan | None) -> str:
    mapping = {
        "PLACE_SEARCH": "PLACE_LIST",
        "SIMPLE_QA": "SIMPLE_ANSWER",
        "TOURISM_INFO": "TOURISM_INFORMATION",
        "WEB_SEARCH": "TOURISM_INFORMATION",
    }
    value = mapping.get(raw, raw)
    if plan is not None and plan.plan_type in {"ITINERARY", "BUDGET_TRIP"} and value in {
        "PLACE_LIST",
        "TOURISM_INFORMATION",
        "NATURE",
        "CULTURE",
    }:
        if plan.plan_type == "BUDGET_TRIP":
            return "BUDGET_TRIP"
        return "ITINERARY"
    allowed = {
        "SIMPLE_ANSWER",
        "TOURISM_INFORMATION",
        "PLACE_LIST",
        "PLACE_DETAILS",
        "ITINERARY",
        "BUDGET_TRIP",
        "NATURE",
        "CULTURE",
        "FOOD",
        "HOTEL",
        "BOOKING",
        "VISION",
        "CLARIFICATION",
        "INSUFFICIENT_INFORMATION",
    }
    return value if value in allowed else "TOURISM_INFORMATION"


def _image_url_for(place_id: str) -> str | None:
    """Look up a verified catalog image — never invent."""
    try:
        from app.services.tourism.factory import get_site_catalog

        catalog = get_site_catalog()
        site = catalog.get(place_id)
        if site and site.images:
            url = str(site.images[0]).strip()
            return url or None
    except Exception:
        return None
    return None


def _source_url_for(place: PlaceEvidence, knowledge: KnowledgeResult | None) -> str | None:
    if not knowledge:
        return None
    for sid in place.source_ids:
        for src in knowledge.sources:
            if src.source_id == sid and src.url:
                return src.url
    return None


def _places_ui(knowledge: KnowledgeResult | None) -> list[PlaceUI]:
    if not knowledge:
        return []
    out: list[PlaceUI] = []
    for place in knowledge.places:
        category = place.category[0] if place.category else None
        lat = place.latitude if _finite(place.latitude) else None
        lon = place.longitude if _finite(place.longitude) else None
        # Both coords required — never emit a half-pair.
        if lat is None or lon is None:
            lat, lon = None, None
        out.append(
            PlaceUI(
                id=place.place_id,
                name=place.name,
                description=place.description,
                category=category,
                city=place.city,
                region=place.region,
                latitude=lat,
                longitude=lon,
                image_url=_image_url_for(place.place_id),
                source_url=_source_url_for(place, knowledge),
                estimated_cost_xaf=place.estimated_cost_xaf,
            )
        )
    return out


def _is_hotel(place: PlaceUI | PlaceEvidence) -> bool:
    if isinstance(place, PlaceUI):
        blob = " ".join(
            filter(None, [place.category or "", place.name, place.description or ""])
        ).casefold()
    else:
        blob = " ".join(
            filter(
                None,
                [
                    place.name,
                    place.description or "",
                    " ".join(place.category),
                ],
            )
        ).casefold()
    return any(h in blob for h in _HOTEL_HINTS)


def _hotels_ui(
    places: list[PlaceUI],
    knowledge: KnowledgeResult | None,
    response_type: str,
) -> list[HotelUI]:
    candidates = [p for p in places if _is_hotel(p)]
    if not candidates and response_type == "HOTEL":
        candidates = list(places)
    hotels: list[HotelUI] = []
    for p in candidates:
        price_status: str = "UNKNOWN"
        if p.estimated_cost_xaf is not None:
            price_status = "INDICATIVE"
        location = ", ".join(filter(None, [p.city, p.region])) or None
        hotels.append(
            HotelUI(
                id=p.id,
                name=p.name,
                location=location,
                image_url=p.image_url,
                description=p.description,
                price=p.estimated_cost_xaf,
                price_status=price_status,  # type: ignore[arg-type]
                amenities=[],
                booking_available=False,
                demo_booking=True,
                source_url=p.source_url,
            )
        )
    return hotels


def _map_ui(places: list[PlaceUI]) -> MapUI | None:
    markers: list[MapMarkerUI] = []
    for p in places:
        if p.latitude is None or p.longitude is None:
            continue
        markers.append(
            MapMarkerUI(
                place_id=p.id,
                latitude=p.latitude,
                longitude=p.longitude,
                title=p.name,
            )
        )
    if not markers:
        return None
    return MapUI(
        enabled=True,
        center=MapCenterUI(latitude=markers[0].latitude, longitude=markers[0].longitude),
        markers=markers,
    )


def _itinerary_ui(plan: TourismPlan | None, *, language: str) -> ItineraryUI | None:
    if plan is None or not plan.days:
        return None
    if plan.plan_type == "EMPTY" and not plan.selected_places:
        return None
    title = (
        "Votre itinéraire"
        if language != "en"
        else "Your itinerary"
    )
    if plan.duration_days:
        title = (
            f"Votre voyage — {plan.duration_days} jour(s)"
            if language != "en"
            else f"Your trip — {plan.duration_days} day(s)"
        )
    days: list[ItineraryDayUI] = []
    for day in plan.days:
        items: list[ItineraryItemUI] = []
        for item in day.places:
            duration_minutes = None
            if item.estimated_duration_hours is not None:
                duration_minutes = int(round(item.estimated_duration_hours * 60))
            items.append(
                ItineraryItemUI(
                    time=None,  # never invent schedules
                    place_id=item.place_id,
                    title=item.place_name,
                    duration_minutes=duration_minutes,
                )
            )
        if items:
            days.append(ItineraryDayUI(day=day.day, items=items))
    if not days:
        return None
    return ItineraryUI(title=title, days=days)


def _budget_ui(plan: TourismPlan | None, *, language: str) -> BudgetUI | None:
    if plan is None:
        return None
    if (
        plan.known_cost_xaf is None
        and plan.total_estimated_cost_xaf is None
        and plan.budget_xaf is None
    ):
        return None

    fr = language != "en"
    items: list[BudgetItemUI] = []

    if plan.budget_xaf is not None:
        items.append(
            BudgetItemUI(
                label="Budget déclaré" if fr else "Declared budget",
                amount=plan.budget_xaf,
                status="KNOWN",
            )
        )

    known_places = plan.known_cost_xaf
    if known_places is not None:
        items.append(
            BudgetItemUI(
                label="Lieux / activités (coûts connus)" if fr else "Places / activities (known)",
                amount=known_places,
                status="KNOWN",
            )
        )
    else:
        items.append(
            BudgetItemUI(
                label="Lieux / activités" if fr else "Places / activities",
                amount=None,
                status="UNKNOWN",
            )
        )

    items.append(
        BudgetItemUI(
            label="Hébergement" if fr else "Lodging",
            amount=None,
            status="UNKNOWN",
        )
    )
    items.append(
        BudgetItemUI(
            label="Transport" if fr else "Transport",
            amount=None,
            status="UNKNOWN",
        )
    )

    return BudgetUI(
        currency=plan.currency or "XAF",
        items=items,
        total_known=known_places,
    )


def _booking_ui(response_type: str, *, language: str) -> BookingUI | None:
    if response_type != "BOOKING":
        return None
    msg = (
        "Réservation en ligne non disponible — démonstration uniquement."
        if language != "en"
        else "Online booking unavailable — demo only."
    )
    return BookingUI(available=False, demo=True, message=msg)


def _vision_ui(vision_summary: str | None, places: list[PlaceUI]) -> VisionUI | None:
    if not vision_summary and not places:
        return None
    matched = places[0].id if len(places) == 1 else None
    return VisionUI(
        description=vision_summary,
        matched_place_id=matched,
        confidence=None,
    )


def _sources_ui(
    final: FinalResponse | None,
    knowledge: KnowledgeResult | None,
) -> list[SourceUI]:
    out: list[SourceUI] = []
    seen: set[str] = set()

    def add(title: str, url: str | None, stype: str) -> None:
        key = f"{title}|{url or ''}"
        if key in seen:
            return
        seen.add(key)
        out.append(SourceUI(title=title, url=url, type=stype))  # type: ignore[arg-type]

    if final:
        for src in final.sources:
            title = src.name or src.source_id
            stype = "WEB" if src.url and src.url.startswith("http") else "KB"
            add(title, src.url, stype)
    if knowledge:
        for src in knowledge.sources:
            title = src.name or src.source_id
            raw_type = (src.source_type or "").upper()
            if raw_type in {"WEB", "KB"}:
                stype = raw_type
            elif raw_type.startswith("WEB"):
                stype = "WEB"
            elif src.url and str(src.url).startswith("http"):
                stype = "WEB"
            else:
                stype = "KB"
            add(title, src.url, stype)
    return out


def _actions_ui(
    places: list[PlaceUI],
    map_ui: MapUI | None,
    itinerary: ItineraryUI | None,
    hotels: list[HotelUI],
    sources: list[SourceUI],
    *,
    language: str,
) -> list[ActionUI]:
    fr = language != "en"
    actions: list[ActionUI] = []
    for p in places[:8]:
        actions.append(
            ActionUI(
                type="VIEW_PLACE",
                label="Découvrir" if fr else "Discover",
                target_id=p.id,
            )
        )
        actions.append(
            ActionUI(
                type="ADD_TO_TRIP",
                label="Ajouter au voyage" if fr else "Add to trip",
                target_id=p.id,
            )
        )
    if map_ui:
        actions.append(
            ActionUI(
                type="VIEW_MAP",
                label="Voir la carte" if fr else "View map",
                target_id=None,
            )
        )
    if itinerary:
        actions.append(
            ActionUI(
                type="PLAN_TRIP",
                label="Voir l’itinéraire" if fr else "View itinerary",
                target_id=None,
            )
        )
    for h in hotels[:4]:
        actions.append(
            ActionUI(
                type="BOOK_HOTEL",
                label="Réserver (démo)" if fr else "Book (demo)",
                target_id=h.id,
            )
        )
    for s in sources:
        if s.url:
            actions.append(
                ActionUI(
                    type="VIEW_SOURCE",
                    label=s.title[:48],
                    target_id=s.url,
                )
            )
            break
    return actions


def _finite(value: float | None) -> bool:
    if value is None:
        return False
    try:
        return abs(float(value)) < 1e9 and value == value  # not NaN
    except (TypeError, ValueError):
        return False
