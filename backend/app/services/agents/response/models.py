"""Final response models for Agent 4."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

ResponseType = Literal[
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

ResponseMode = Literal["text", "voice"]


class SourceReference(BaseModel):
    source_id: str
    name: str | None = None
    url: str | None = None


class FinalResponse(BaseModel):
    """User-facing answer — grounded presentation only."""

    text: str
    language: str = "fr"
    response_type: ResponseType | str
    response_mode: ResponseMode = "text"
    sources: list[SourceReference] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    fallback_used: bool = False
    request_id: str | None = None
    prompt_build_ms: float | None = None
    llm_ttft_ms: float | None = None
    llm_generation_ms: float | None = None
    total_agent4_ms: float | None = None
    grounding_ok: bool | None = None
    grounding_validation_ms: float | None = None
    grounding_violations: list[str] = Field(default_factory=list)
    # Violations of the LLM draft that caused it to be replaced by the fallback.
    replaced_violations: list[str] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)

    @field_validator("sources", mode="before")
    @classmethod
    def _sources(cls, value: object) -> list:
        return value or []

    def observability(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "response_type": self.response_type,
            "language": self.language,
            "response_mode": self.response_mode,
            "confidence": round(self.confidence, 3),
            "fallback_used": self.fallback_used,
            "sources_count": len(self.sources),
            "warnings_count": len(self.warnings),
            "text_chars": len(self.text or ""),
            "prompt_build_ms": self.prompt_build_ms,
            "llm_ttft_ms": self.llm_ttft_ms,
            "llm_generation_ms": self.llm_generation_ms,
            "total_agent4_ms": self.total_agent4_ms,
            "grounding_ok": self.grounding_ok,
            "grounding_validation_ms": self.grounding_validation_ms,
            "grounding_violation_count": len(self.grounding_violations),
            "tools_used": list(self.tools_used),
        }
