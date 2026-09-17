from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None

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


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    role: Literal["assistant"] = "assistant"
    provider: str
