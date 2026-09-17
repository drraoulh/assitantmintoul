from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

from app.services.rag.base import RAGService
from app.services.rag.chunk import KnowledgeChunk
from app.services.rag.loader import load_knowledge_chunks

_TOKEN = re.compile(r"[a-z0-9àâäáåãæçéèêëíìîïñóòôöõœúùûüýÿ]+", re.IGNORECASE)

# Light stemming / alias boosts for bilingual Cameroon tourism queries.
_ALIASES: dict[str, set[str]] = {
    "yaounde": {"yaoundé", "yaounde", "capitale"},
    "yaoundé": {"yaoundé", "yaounde", "capitale"},
    "douala": {"douala", "littoral"},
    "kribi": {"kribi", "lobé", "lobe", "plage", "beach"},
    "limbe": {"limbe", "limbé", "buea"},
    "limbé": {"limbe", "limbé", "buea"},
    "foumban": {"foumban", "bamoun"},
    "maroua": {"maroua", "mandara", "rhumsiki"},
    "visite": {"visiter", "voir", "site", "sites", "attraction", "attractions"},
    "visiter": {"visite", "voir", "site", "sites"},
    "plage": {"plages", "beach", "beaches", "balnéaire"},
    "beach": {"plage", "plages", "beaches"},
    "manger": {"cuisine", "plat", "food", "restaurant", "ndolé", "ndole"},
    "food": {"cuisine", "manger", "plat", "restaurant"},
}


def _normalize(text: str) -> str:
    lowered = text.lower().casefold()
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(_normalize(text))


def expand_tokens(tokens: list[str]) -> set[str]:
    expanded: set[str] = set(tokens)
    for token in tokens:
        expanded.update(_ALIASES.get(token, set()))
        # Also try without accents already handled by normalize; keep raw aliases.
        for key, values in _ALIASES.items():
            if token == _normalize(key) or token in {_normalize(v) for v in values}:
                expanded.update(_normalize(v) for v in values)
                expanded.add(_normalize(key))
    return expanded


class LocalRAGService(RAGService):
    """Lexical TF-IDF retrieval over curated Cameroon tourism files.

    No embedding model download — suitable for a student laptop MVP.
    A later phase can swap in sentence-transformers + FAISS via the same interface.
    """

    def __init__(
        self,
        chunks: list[KnowledgeChunk] | None = None,
        *,
        data_root: str | None = None,
    ) -> None:
        from pathlib import Path

        root = Path(data_root) if data_root else None
        self._chunks = chunks if chunks is not None else load_knowledge_chunks(root)
        self._docs_tokens: list[list[str]] = [
            tokenize(chunk.searchable_text) for chunk in self._chunks
        ]
        self._idf = self._build_idf(self._docs_tokens)
        self._doc_vectors: list[dict[str, float]] = [
            self._tfidf_vector(tokens) for tokens in self._docs_tokens
        ]

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    async def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        scored = await self.retrieve_chunks(query, top_k=top_k)
        return [chunk.text for chunk in scored]

    async def retrieve_chunks(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]:
        if not self._chunks or top_k <= 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        query_terms = expand_tokens(query_tokens)
        query_vector = self._tfidf_vector(list(query_terms))
        if not query_vector:
            return []

        scored: list[tuple[float, KnowledgeChunk]] = []
        for chunk, doc_vector in zip(self._chunks, self._doc_vectors, strict=True):
            score = self._cosine(query_vector, doc_vector)
            if score <= 0:
                continue
            # Small boost when city/name appears explicitly in the query.
            searchable = _normalize(chunk.searchable_text)
            for term in query_terms:
                if len(term) >= 4 and term in searchable:
                    score += 0.03
            scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:top_k]]

    def _build_idf(self, docs: list[list[str]]) -> dict[str, float]:
        doc_count = len(docs) or 1
        df: Counter[str] = Counter()
        for tokens in docs:
            df.update(set(tokens))
        return {
            term: math.log((1 + doc_count) / (1 + freq)) + 1.0
            for term, freq in df.items()
        }

    def _tfidf_vector(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        tf = Counter(tokens)
        length = float(len(tokens))
        vector: dict[str, float] = {}
        for term, count in tf.items():
            idf = self._idf.get(term, math.log(2.0) + 1.0)
            vector[term] = (count / length) * idf
        return vector

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(value * b.get(term, 0.0) for term, value in a.items())
        if dot <= 0:
            return 0.0
        norm_a = math.sqrt(sum(value * value for value in a.values()))
        norm_b = math.sqrt(sum(value * value for value in b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
