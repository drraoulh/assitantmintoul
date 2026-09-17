from abc import ABC, abstractmethod


class RAGService(ABC):
    """Retrieve tourist knowledge for later grounded answers.

    Planned stack: open-source embeddings + FAISS or pgvector.
    """

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """Return relevant document chunks for a user query."""


class PlaceholderRAGService(RAGService):
    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        return []
