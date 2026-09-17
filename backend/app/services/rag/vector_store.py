from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path

import numpy as np

from app.services.rag.embedding_service import EmbeddingService

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover - optional on some Windows setups
    faiss = None


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-12, None)
    return (matrix / norms).astype(np.float32)


class HashingEmbeddingService(EmbeddingService):
    """Deterministic multilingual-ish embeddings for tests and offline fallback."""

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> np.ndarray:
        rows = [self._embed_one(text) for text in texts]
        return _l2_normalize(np.vstack(rows))

    def _embed_one(self, text: str) -> np.ndarray:
        folded = "".join(
            char
            for char in unicodedata.normalize("NFKD", text.lower())
            if not unicodedata.combining(char)
        )
        vector = np.zeros(self.dimension, dtype=np.float32)
        padded = f" {folded} "
        for index in range(len(padded) - 2):
            gram = padded[index : index + 3]
            digest = hashlib.md5(gram.encode("utf-8")).hexdigest()
            bucket = int(digest, 16) % self.dimension
            vector[bucket] += 1.0
        return vector


class SentenceTransformerEmbeddingService(EmbeddingService):
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self.dimension = int(self._model.get_sentence_embedding_dimension())
        self.model_name = model_name

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)


class FaissVectorStore:
    """Persisted vector index. Uses FAISS when installed, else NumPy cosine search."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self._vectors: np.ndarray | None = None
        self._metadata: list[dict] = []
        self._index = None

    @property
    def size(self) -> int:
        return 0 if self._vectors is None else int(self._vectors.shape[0])

    def build(self, vectors: np.ndarray, metadata: list[dict], embedding_model: str | None = None) -> None:
        self._vectors = _l2_normalize(np.asarray(vectors, dtype=np.float32))
        self._metadata = metadata
        self.embedding_model = embedding_model
        self._index = self._make_faiss(self._vectors)

    def save(self) -> None:
        if self._vectors is None:
            raise ValueError("No vectors to save.")
        self.directory.mkdir(parents=True, exist_ok=True)
        np.save(self.directory / "embeddings.npy", self._vectors)
        (self.directory / "metadata.json").write_text(
            json.dumps(self._metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest = {
            "dimension": int(self._vectors.shape[1]),
            "count": int(self._vectors.shape[0]),
            "embedding_model": getattr(self, "embedding_model", None),
        }
        (self.directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        if self._index is not None and faiss is not None:
            faiss.write_index(self._index, str(self.directory / "index.faiss"))

    def load(self) -> bool:
        embeddings_path = self.directory / "embeddings.npy"
        metadata_path = self.directory / "metadata.json"
        if not embeddings_path.exists() or not metadata_path.exists():
            return False
        self._vectors = np.load(embeddings_path).astype(np.float32)
        self._metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        manifest_path = self.directory / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.embedding_model = manifest.get("embedding_model")
        faiss_path = self.directory / "index.faiss"
        if faiss is not None and faiss_path.exists():
            self._index = faiss.read_index(str(faiss_path))
        else:
            self._index = self._make_faiss(self._vectors)
        return True

    def search(self, query_vector: np.ndarray, top_k: int) -> list[tuple[float, dict]]:
        if self._vectors is None or self.size == 0:
            return []
        k = min(top_k, self.size)
        query = _l2_normalize(np.asarray(query_vector, dtype=np.float32).reshape(1, -1))
        if self._index is not None and faiss is not None:
            scores, indexes = self._index.search(query, k)
            pairs = []
            for score, idx in zip(scores[0], indexes[0], strict=True):
                if idx < 0:
                    continue
                pairs.append((float(score), self._metadata[int(idx)]))
            return pairs
        hits = self._vectors @ query[0]
        top = np.argsort(hits)[::-1][:k]
        return [(float(hits[idx]), self._metadata[int(idx)]) for idx in top]

    def _make_faiss(self, vectors: np.ndarray):
        if faiss is None or vectors.size == 0:
            return None
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        return index
