from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.services.rag.base import RAGService
from app.services.rag.embedding_service import EmbeddingService
from app.services.rag.types import RetrievedChunk, SourceRef
from app.services.rag.vector_store import (
    FaissVectorStore,
    HashingEmbeddingService,
    SentenceTransformerEmbeddingService,
)


class TourismRAGService(RAGService):
    def __init__(
        self,
        store: FaissVectorStore,
        embedder: EmbeddingService,
        top_k: int,
        min_score: float,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._top_k = top_k
        self._min_score = min_score

    async def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        if self._store.size == 0:
            return []
        limit = top_k or self._top_k
        vector = self._embedder.embed([query])
        hits = self._store.search(vector, limit)
        chunks: list[RetrievedChunk] = []
        folded_query = _fold_text(query)
        for score, meta in hits:
            if score < self._min_score:
                continue
            chunk = RetrievedChunk(
                site_id=str(meta.get("site_id", "")),
                site_name=str(meta.get("site_name", "")),
                region=str(meta.get("region", "")),
                city=str(meta.get("city", "")),
                text=str(meta.get("text", "")),
                score=score,
                sources=[
                    SourceRef(
                        title=str(item.get("title", "")),
                        organization=item.get("organization"),
                        url=item.get("url"),
                        publication_date=item.get("publication_date"),
                        verification_status=str(item.get("verification_status", "official")),
                    )
                    for item in meta.get("sources", [])
                ],
            )
            if not _is_relevant(folded_query, chunk, score):
                continue
            chunks.append(chunk)
        return chunks


def _fold_text(value: str) -> str:
    return (
        value.casefold()
        .replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("ô", "o")
    )


def _is_relevant(folded_query: str, chunk: RetrievedChunk, score: float) -> bool:
    tokens = (
        _fold_text(chunk.city),
        _fold_text(chunk.region),
        _fold_text(chunk.site_name),
    )
    if any(token and token in folded_query for token in tokens):
        return True
    return score >= 0.42


def resolve_vector_dir(configured: str) -> Path:
    path = Path(configured)
    if path.is_absolute():
        return path
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data").exists():
            return (parent / "data" / "indexes").resolve()
    return (Path.cwd() / configured).resolve()


def build_embedder(model_name: str | None = None) -> EmbeddingService:
    settings = get_settings()
    name = model_name or settings.embedding_model
    if name in {"hashing", "test-hash"}:
        return HashingEmbeddingService()
    try:
        return SentenceTransformerEmbeddingService(name)
    except Exception:
        return HashingEmbeddingService()


@lru_cache
def get_rag_service() -> RAGService:
    settings = get_settings()
    store = FaissVectorStore(resolve_vector_dir(settings.vector_store_path))
    loaded = store.load()
    model_name = getattr(store, "embedding_model", None) or settings.embedding_model
    embedder = build_embedder(model_name)
    if not loaded:
        return TourismRAGService(store, embedder, settings.rag_top_k, settings.rag_min_score)
    return TourismRAGService(
        store=store,
        embedder=embedder,
        top_k=settings.rag_top_k,
        min_score=settings.rag_min_score,
    )
