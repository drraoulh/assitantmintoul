"""AGENT 2 — Knowledge & Retrieval (Phase 2.2).

Turns IntentResult + user query into verified PlaceEvidence /
KnowledgeEvidence. Does **not** draft the final answer or invent facts.
"""

from app.services.agents.knowledge.agent import (
    KnowledgeAgent,
    retrieve_knowledge,
    retrieve_knowledge_sync,
)
from app.services.agents.knowledge.models import (
    KnowledgeEvidence,
    KnowledgeResult,
    PlaceEvidence,
    SourceEvidence,
)

__all__ = [
    "KnowledgeAgent",
    "KnowledgeEvidence",
    "KnowledgeResult",
    "PlaceEvidence",
    "SourceEvidence",
    "retrieve_knowledge",
    "retrieve_knowledge_sync",
]
