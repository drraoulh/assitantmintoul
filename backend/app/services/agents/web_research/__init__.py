"""Web Research Agent — specialized evidence gatherer used when KB is thin."""

from app.services.agents.web_research.agent import WebResearchAgent, run_web_research
from app.services.agents.web_research.models import WebEvidence, WebResearchResult

__all__ = [
    "WebEvidence",
    "WebResearchAgent",
    "WebResearchResult",
    "run_web_research",
]
