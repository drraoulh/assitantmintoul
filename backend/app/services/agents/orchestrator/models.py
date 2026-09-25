"""Structured outputs for Phase 2.5 Agent Orchestrator."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.services.agents.intent.models import IntentResult
from app.services.agents.knowledge.models import KnowledgeResult
from app.services.agents.planner.models import TourismPlan
from app.services.agents.response.models import FinalResponse


class OrchestrationTimings(BaseModel):
    """Per-step latency. ``None`` means the step was not executed."""

    intent_ms: float | None = None
    knowledge_ms: float | None = None
    planner_ms: float | None = None
    response_ms: float | None = None
    vision_ms: float | None = None
    web_ms: float | None = None
    total_ms: float | None = None


class OrchestrationContext(BaseModel):
    """Agents 1–3 output before Agent 4 presentation (Phase 2.6 streaming)."""

    intent: IntentResult
    knowledge: KnowledgeResult
    plan: TourismPlan | None = None
    timings: OrchestrationTimings = Field(default_factory=OrchestrationTimings)
    agents_called: list[str] = Field(default_factory=list)
    request_id: str | None = None
    mode: str = "text"
    vision_summary: str | None = None
    web_hit_count: int = 0
    web_research: dict[str, Any] | None = None
    images: list[dict[str, Any]] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)


class OrchestrationResult(BaseModel):
    """Full orchestration outcome — coordinator output only."""

    intent: IntentResult
    knowledge: KnowledgeResult | None = None
    plan: TourismPlan | None = None
    final_response: FinalResponse
    timings: OrchestrationTimings = Field(default_factory=OrchestrationTimings)
    agents_called: list[str] = Field(default_factory=list)
    request_id: str | None = None
    mode: str = "text"
    vision_summary: str | None = None
    web_hit_count: int = 0
    web_research: dict[str, Any] | None = None
    images: list[dict[str, Any]] = Field(default_factory=list)
    fallback_used: bool = False
    tools_used: list[str] = Field(default_factory=list)

    def observability(self) -> dict[str, Any]:
        """Safe metrics payload — no raw user text / secrets."""
        return {
            "request_id": self.request_id,
            "intent": self.intent.intent if self.intent else None,
            "response_type": (
                self.final_response.response_type if self.final_response else None
            ),
            "mode": self.mode,
            "agents_called": list(self.agents_called),
            "total_ms": self.timings.total_ms,
            "intent_ms": self.timings.intent_ms,
            "knowledge_ms": self.timings.knowledge_ms,
            "planner_ms": self.timings.planner_ms,
            "response_ms": self.timings.response_ms,
            "vision_ms": self.timings.vision_ms,
            "web_ms": self.timings.web_ms,
            "web_hit_count": self.web_hit_count,
            "web_research": self.web_research,
            "fallback_used": self.fallback_used,
            "tools_used": list(self.tools_used),
            "knowledge_source": self.knowledge.source if self.knowledge else None,
            "plan_feasibility": self.plan.feasibility if self.plan else None,
        }
