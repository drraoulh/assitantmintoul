"""Typed payloads for the Gemini chat service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

GeminiToolName = Literal["google_search", "google_maps"]


class GeminiWebSource(BaseModel):
    title: str
    url: str | None = None
    organization: str | None = None


class GeminiMapResult(BaseModel):
    title: str
    url: str | None = None
    place_id: str | None = None
    snippet: str | None = None


class GeminiGenerateRequest(BaseModel):
    user_message: str
    conversation: list[dict[str, str]] = Field(default_factory=list)
    kb_context: str | None = None
    language: str = "fr"
    enabled_tools: list[str] = Field(
        default_factory=lambda: ["google_search", "google_maps"]
    )


class GeminiResult(BaseModel):
    text: str = ""
    model: str = ""
    tools_used: list[str] = Field(default_factory=list)
    web_sources: list[GeminiWebSource] = Field(default_factory=list)
    map_results: list[GeminiMapResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    empty: bool = False
    error: str | None = None
    http_status: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.text.strip()) and not self.error


class GeminiServiceError(Exception):
    """Non-secret Gemini failure (timeout, quota, empty, HTTP)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
