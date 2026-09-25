from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.chat_ui import (
    ActionUI,
    BookingUI,
    BudgetUI,
    ChatResponseType,
    HotelUI,
    ImageUI,
    ItineraryUI,
    MapUI,
    PlaceUI,
    SourceUI,
    VisionUI,
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    # "voice" asks for a short spoken answer (faster generation + faster TTS).
    mode: Literal["text", "voice"] = "text"
    # Preferred UI language (Cameroon bilingual FR/EN). Guides reply language
    # when the user message does not clearly signal another language.
    locale: Literal["fr", "en"] = "fr"

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("message must not be empty")
        return cleaned

    @field_validator("conversation_id")
    @classmethod
    def empty_conversation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ChatSource(BaseModel):
    title: str
    city: str | None = None
    region: str | None = None
    category: str | None = None
    organization: str | None = None
    url: str | None = None
    image_url: str | None = None


class ChatResponse(BaseModel):
    """HTTP chat reply — backwards compatible with Expo (`message` + `sources`).

    Phase 3.1 adds optional structured tourism UI fields for the Next.js client.
    """

    conversation_id: str
    message: str
    role: Literal["assistant"] = "assistant"
    provider: str
    sources: list[ChatSource] = Field(default_factory=list)

    # Alias of `message` for clients that expect `text` (mirrors message).
    text: str | None = None

    response_type: ChatResponseType | str | None = None
    places: list[PlaceUI] = Field(default_factory=list)
    map: MapUI | None = None
    itinerary: ItineraryUI | None = None
    budget: BudgetUI | None = None
    hotels: list[HotelUI] = Field(default_factory=list)
    booking: BookingUI | None = None
    vision: VisionUI | None = None
    ui_sources: list[SourceUI] = Field(default_factory=list)
    actions: list[ActionUI] = Field(default_factory=list)
    structured_build_ms: float | None = None
    # Web phase summary: decision, provider, queries, evidence_count, research_ms.
    web_research: dict[str, Any] | None = None
    # Web images (IMAGE_SEARCH / dish photos) and the resolved chat intent.
    images: list[ImageUI] = Field(default_factory=list)
    routing: dict[str, Any] | None = None
    tools_used: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _mirror_text(self) -> ChatResponse:
        if self.text is None:
            self.text = self.message
        return self


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    message_count: int
    updated_at: datetime | None = None


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]
    count: int
    persistent: bool


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[ConversationTurn]
    count: int
