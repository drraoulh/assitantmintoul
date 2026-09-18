from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    # "voice" asks for a short spoken answer (faster generation + faster TTS).
    mode: Literal["text", "voice"] = "text"

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
    conversation_id: str
    message: str
    role: Literal["assistant"] = "assistant"
    provider: str
    sources: list[ChatSource] = Field(default_factory=list)


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
