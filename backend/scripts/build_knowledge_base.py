"""Rebuild FAISS (or NumPy) vectors from curated JSON tourist sites."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.rag.ingest import chunk_site, load_tourist_sites
from app.services.rag.rag_service import build_embedder, resolve_vector_dir
from app.services.rag.vector_store import FaissVectorStore, HashingEmbeddingService


def main() -> None:
    settings = get_settings()
    sites = load_tourist_sites(settings.tourist_sites_path)
    chunks: list[dict] = []
    for site in sites:
        chunks.extend(chunk_site(site))
    if not chunks:
        raise SystemExit("No tourism chunks found. Check data/tourist_sites.")

    embedder = build_embedder(settings.embedding_model)
    model_name = getattr(embedder, "model_name", None)
    if isinstance(embedder, HashingEmbeddingService):
        model_name = "hashing"
        print("Using hashing embeddings (install sentence-transformers for MiniLM).")
    else:
        print(f"Using embedding model: {settings.embedding_model}")

    vectors = embedder.embed([chunk["text"] for chunk in chunks])
    directory = resolve_vector_dir(settings.vector_store_path)
    store = FaissVectorStore(directory)
    store.build(vectors, chunks, embedding_model=model_name)
    store.save()
    print(f"Indexed {len(chunks)} chunks from {len(sites)} sites -> {directory}")


if __name__ == "__main__":
    main()
