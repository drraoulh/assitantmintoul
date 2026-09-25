"""Web Research Agent models — evidence only, never user-facing prose."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WebEvidence(BaseModel):
    title: str
    url: str = ""
    domain: str = ""
    snippet: str = ""
    content: str | None = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_type: str = "web"
    verified: bool = False
    tier: int = Field(default=4, ge=1, le=4)
    published_at: str | None = None
    rank_score: float = Field(default=0.0, ge=0.0, le=1.0)
    low_confidence: bool = False
    provider: str = ""
    # Route answers: "transport" (origin → destination) or "destination" (what to do there).
    phase: str | None = None
    # "direct" / "reverse" / "both" when the pair of towns is named.
    route_match: str | None = None


class WebResearchResult(BaseModel):
    query: str
    search_queries: list[str] = Field(default_factory=list)
    transport_queries: list[str] = Field(default_factory=list)
    destination_queries: list[str] = Field(default_factory=list)
    raw_results_count: int = 0
    answerable: bool = False
    evidence: list[WebEvidence] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    timed_out: bool = False
    cache_hit: bool = False
    request_id: str | None = None
    research_ms: float | None = None
    provider: str = ""
    decision: str = ""

    def observability(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "answerable": self.answerable,
            "evidence_count": len(self.evidence),
            "key_facts_count": len(self.key_facts),
            "confidence": round(self.confidence, 3),
            "timed_out": self.timed_out,
            "cache_hit": self.cache_hit,
            "research_ms": self.research_ms,
            "provider": self.provider,
            "decision": self.decision,
            "search_queries": list(self.search_queries),
            "transport_queries": list(self.transport_queries),
            "destination_queries": list(self.destination_queries),
            "web_results_count": self.raw_results_count,
            "selected_sources": [e.domain or e.url for e in self.evidence],
            "warnings": list(self.warnings)[:5],
        }
