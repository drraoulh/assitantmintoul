"""Phase 3.1 — structured UI payloads attached to ChatResponse."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChatResponseType = Literal[
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
]


class ImageUI(BaseModel):
    """Web image result — URLs come from the image search provider, never invented."""

    image_url: str
    thumbnail_url: str | None = None
    page_url: str
    title: str = ""
    source_domain: str = ""


class PlaceUI(BaseModel):
    """Verified place card — null when unknown, never invented."""

    id: str
    name: str
    description: str | None = None
    category: str | None = None
    city: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    image_url: str | None = None
    source_url: str | None = None
    estimated_cost_xaf: int | None = None


class MapMarkerUI(BaseModel):
    place_id: str
    latitude: float
    longitude: float
    title: str


class MapCenterUI(BaseModel):
    latitude: float
    longitude: float


class MapUI(BaseModel):
    enabled: bool = True
    center: MapCenterUI
    markers: list[MapMarkerUI] = Field(default_factory=list)


class ItineraryItemUI(BaseModel):
    time: str | None = None
    place_id: str | None = None
    title: str
    duration_minutes: int | None = None


class ItineraryDayUI(BaseModel):
    day: int
    items: list[ItineraryItemUI] = Field(default_factory=list)


class ItineraryUI(BaseModel):
    title: str
    days: list[ItineraryDayUI] = Field(default_factory=list)


class BudgetItemUI(BaseModel):
    label: str
    amount: int | None = None
    status: Literal["KNOWN", "UNKNOWN", "INDICATIVE"] = "UNKNOWN"


class BudgetUI(BaseModel):
    currency: str = "XAF"
    items: list[BudgetItemUI] = Field(default_factory=list)
    total_known: int | None = None


class HotelUI(BaseModel):
    id: str
    name: str
    location: str | None = None
    image_url: str | None = None
    description: str | None = None
    price: int | None = None
    price_status: Literal["KNOWN", "INDICATIVE", "UNKNOWN"] = "UNKNOWN"
    amenities: list[str] = Field(default_factory=list)
    booking_available: bool = False
    demo_booking: bool = True
    source_url: str | None = None


class BookingUI(BaseModel):
    available: bool = False
    demo: bool = True
    message: str | None = None


class VisionUI(BaseModel):
    description: str | None = None
    matched_place_id: str | None = None
    confidence: float | None = None


class SourceUI(BaseModel):
    title: str
    url: str | None = None
    type: Literal["WEB", "KB", "OTHER"] = "OTHER"


class ActionUI(BaseModel):
    type: Literal[
        "VIEW_PLACE",
        "ADD_TO_TRIP",
        "VIEW_MAP",
        "PLAN_TRIP",
        "BOOK_HOTEL",
        "ASK_AI",
        "VIEW_SOURCE",
    ]
    label: str
    target_id: str | None = None
