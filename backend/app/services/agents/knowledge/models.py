"""Structured evidence models for Agent 2 — Knowledge & Retrieval."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PlaceEvidence(BaseModel):
    """A place verified from structured data (never invented)."""

    place_id: str
    name: str
    city: str | None = None
    region: str | None = None
    description: str | None = None
    cultural_info: str | None = None
    eco_info: str | None = None
    activities: list[str] = Field(default_factory=list)
    category: list[str] = Field(default_factory=list)
    eco_tags: list[str] = Field(default_factory=list)
    cultural_zone: str | None = None
    estimated_cost_xaf: int | None = None
    recommended_duration_hours: float | None = None
    best_period: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    source_ids: list[str] = Field(default_factory=list)
    evidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    is_published: bool = True
    match_reasons: list[str] = Field(default_factory=list)
    location_scope: Literal["IN_CITY", "NEARBY", "IN_REGION", "UNKNOWN"] | None = None
    locality: str | None = None
    division: str | None = None

    @field_validator("activities", "category", "eco_tags", "source_ids", "match_reasons", mode="before")
    @classmethod
    def _listify(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            cleaned = value.strip()
            return [cleaned] if cleaned else []
        if isinstance(value, (list, tuple)):
            out: list[str] = []
            for item in value:
                text = str(item).strip()
                if text and text not in out:
                    out.append(text)
            return out
        return []


class KnowledgeEvidence(BaseModel):
    chunk_id: str
    content: str
    source_id: str | None = None
    title: str | None = None
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    city: str | None = None


class SourceEvidence(BaseModel):
    source_id: str
    name: str | None = None
    url: str | None = None
    source_type: str | None = None


class KnowledgeResult(BaseModel):
    """Agent 2 output — evidences only, no user-facing prose."""

    query: str
    intent: str
    places: list[PlaceEvidence] = Field(default_factory=list)
    knowledge: list[KnowledgeEvidence] = Field(default_factory=list)
    sources: list[SourceEvidence] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    web_needed: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    request_id: str | None = None
    place_retrieval_ms: float | None = None
    knowledge_retrieval_ms: float | None = None
    source_resolution_ms: float | None = None
    total_agent2_ms: float | None = None
    source: Literal["structured", "hybrid", "documents", "empty"] = "empty"
    verified_places_count: int = 0
    knowledge_completeness: Literal["HIGH", "MEDIUM", "LOW", "NONE"] = "NONE"
    geo_facts_count: int = 0

    def observability(self) -> dict[str, object]:
        """Safe metrics — no raw knowledge text / PII."""
        return {
            "request_id": self.request_id,
            "intent": self.intent,
            "confidence": round(self.confidence, 3),
            "places_count": len(self.places),
            "knowledge_count": len(self.knowledge),
            "sources_count": len(self.sources),
            "missing_information": list(self.missing_information),
            "web_needed": self.web_needed,
            "place_retrieval_ms": self.place_retrieval_ms,
            "knowledge_retrieval_ms": self.knowledge_retrieval_ms,
            "source_resolution_ms": self.source_resolution_ms,
            "total_agent2_ms": self.total_agent2_ms,
            "source": self.source,
            "verified_places_count": self.verified_places_count,
            "knowledge_completeness": self.knowledge_completeness,
            "geo_facts_count": self.geo_facts_count,
        }
