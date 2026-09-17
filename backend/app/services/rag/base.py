from abc import ABC, abstractmethod

from app.services.rag.chunk import KnowledgeChunk


class RAGService(ABC):
    """Retrieve tourist knowledge for grounded answers.

    MVP: lexical TF-IDF over curated files under data/.
    Planned upgrade: open-source embeddings + FAISS or pgvector.
    """

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """Return relevant document texts for a user query."""

    async def retrieve_chunks(self, query: str, top_k: int = 5) -> list[KnowledgeChunk]:
        """Optional richer retrieval. Default wraps `retrieve` texts."""
        texts = await self.retrieve(query, top_k=top_k)
        return [
            KnowledgeChunk(
                id=f"passage:{index}",
                title=f"Passage {index}",
                text=text,
                source="unknown",
            )
            for index, text in enumerate(texts, start=1)
        ]


class PlaceholderRAGService(RAGService):
    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        return []
