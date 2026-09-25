"""Deterministic KnowledgeResult / TourismPlan → ChatResponse UI payloads.

No LLM. Overhead target < 50 ms. Never invents coordinates, prices, or URLs.
"""

from __future__ import annotations

import json
import logging
import time
import unicodedata
from typing import Any

from app.schemas.chat_ui import (
    ActionUI,
    BookingUI,
    BudgetItemUI,
    BudgetUI,
    HotelUI,
    ImageUI,
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
from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult, PlaceEvidence
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.models import FinalResponse

logger = logging.getLogger(__name__)

_HOTEL_HINTS = ("hotel", "hôtel", "heberg", "héberg", "lodge", "resort", "auberge", "inn")
_PLACE_CARD_TYPES = {
    "PLACE_LIST",
    "PLACE_DETAILS",
    "ITINERARY",
    "BUDGET_TRIP",
    "NATURE",
    "HOTEL",
    "BOOKING",
    "VISION",
    "TRAVEL_ROUTE",
}


def build_structured_ui(
    *,
    final: FinalResponse | None = None,
    knowledge: KnowledgeResult | None = None,
    plan: TourismPlan | None = None,
    vision_summary: str | None = None,
    language: str = "fr",
    intent: IntentResult | None = None,
    images: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a dict of ChatResponse structured fields + ``structured_build_ms``.

    Place cards and maps only appear for place-oriented answers; dishes,
    images and general questions never get them.
    """
    t0 = time.perf_counter()

    response_type = (
        (final.response_type if final else None)
        or (knowledge.intent if knowledge else None)
        or "SIMPLE_ANSWER"
    )
    # Normalize intent-ish leftovers to Agent 4 response types when needed.
    response_type = _normalize_response_type(str(response_type), plan)

    places = _places_ui(knowledge)
    hidden_place_names: set[str] = set()
    if response_type not in _PLACE_CARD_TYPES:
        hidden_place_names = {p.name for p in places}
        places = []
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
    if response_type == "TRAVEL_ROUTE" and intent and intent.origin and intent.destination:
        map_ui = _route_map_ui(intent.origin, intent.destination, places) or map_ui
    itinerary = _itinerary_ui(plan, language=language)
    budget = _budget_ui(plan, language=language)
    booking = _booking_ui(response_type, language=language)
    vision = _vision_ui(vision_summary, places)
    ui_sources = _sources_ui(final, knowledge)
    if hidden_place_names:
        ui_sources = [s for s in ui_sources if s.title not in hidden_place_names]
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
        "images": [ImageUI.model_validate(img) for img in images or []],
        "routing": intent.routing() if intent else None,
        "structured_build_ms": elapsed,
    }


def log_chat_observability(
    intent: IntentResult | None,
    knowledge: KnowledgeResult | None,
    ui: dict[str, Any],
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """One line per chat answer: what was searched, selected and displayed."""
    web = ui.get("web_research") or {}
    data = {
        "request_id": request_id or (intent.request_id if intent else None),
        "intent": intent.chat_intent if intent else None,
        "origin": intent.origin if intent else None,
        "destination": intent.destination if intent else None,
        "location": (intent.city or intent.region or intent.location) if intent else None,
        "web_queries": web.get("transport_queries") or web.get("search_queries") or [],
        "destination_queries": web.get("destination_queries") or [],
        "web_results_count": web.get("web_results_count", 0),
        "selected_sources": web.get("selected_sources") or [],
        "smartmboa_results_count": len(knowledge.places) if knowledge else 0,
        "image_search_used": bool(intent and intent.wants_images),
        "images_count": len(ui.get("images") or []),
        "places_displayed": [getattr(p, "name", "") for p in ui.get("places") or []],
        "response_type": ui.get("response_type"),
    }
    logger.info("chat_observability %s", json.dumps(data, ensure_ascii=False, default=str))
    return data


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
        "IMAGE_SEARCH": "IMAGES",
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
        "TRAVEL_ROUTE",
        "IMAGES",
    }
    return value if value in allowed else "TOURISM_INFORMATION"


def _site_catalog():
    try:
        from app.services.tourism.factory import get_site_catalog

        return get_site_catalog()
    except Exception:
        return None


def _image_url_for(place_id: str, catalog=None) -> str | None:
    """Look up a verified catalog image — never invent."""
    try:
        catalog = catalog if catalog is not None else _site_catalog()
        if catalog is None:
            return None
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
    # One catalog per build: an unwarmed catalog reloads its JSON on every lookup.
    catalog = _site_catalog() if knowledge.places else None
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
                image_url=_image_url_for(place.place_id, catalog),
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


def _city_point(city: str) -> tuple[float, float] | None:
    """Median coordinates of the verified catalog places in ``city``."""
    try:
        from app.services.tourism.factory import get_site_catalog

        needle = _fold(city)
        points = [
            (s.latitude, s.longitude)
            for s in get_site_catalog().by_city(city)
            if _fold(s.city) == needle and _finite(s.latitude) and _finite(s.longitude)
        ]
    except Exception:
        return None
    if not points:
        return None
    lats = sorted(p[0] for p in points)
    lons = sorted(p[1] for p in points)
    return lats[len(lats) // 2], lons[len(lons) // 2]


def _route_map_ui(origin: str, destination: str, places: list[PlaceUI]) -> MapUI | None:
    start, end = _city_point(origin), _city_point(destination)
    if start is None or end is None:
        return None
    markers = [
        MapMarkerUI(place_id=f"route:origin:{_fold(origin)}", latitude=start[0], longitude=start[1], title=origin),
        MapMarkerUI(place_id=f"route:destination:{_fold(destination)}", latitude=end[0], longitude=end[1], title=destination),
    ]
    for p in places:
        if p.latitude is not None and p.longitude is not None:
            markers.append(
                MapMarkerUI(place_id=p.id, latitude=p.latitude, longitude=p.longitude, title=p.name)
            )
    return MapUI(
        enabled=True,
        center=MapCenterUI(latitude=(start[0] + end[0]) / 2, longitude=(start[1] + end[1]) / 2),
        markers=markers,
    )


def _fold(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").casefold())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).strip()


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
