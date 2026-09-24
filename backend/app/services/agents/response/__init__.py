"""AGENT 4 — Response Generator (Phase 2.4).

Presentation layer only: reformulates IntentResult + KnowledgeResult +
TourismPlan into FinalResponse. Never invents tourism facts.
"""

from app.services.agents.response.agent import ResponseGenerator, generate_response
from app.services.agents.response.models import FinalResponse, SourceReference
from app.services.agents.response.structured_ui import build_structured_ui

__all__ = [
    "FinalResponse",
    "ResponseGenerator",
    "SourceReference",
    "generate_response",
    "build_structured_ui",
]
