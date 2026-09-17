"""Sync Supabase tourism tables into knowledge_chunks and warm the RAG index.

Usage (from backend/):
  .\\.venv\\Scripts\\python.exe -m scripts.sync_knowledge_base
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.kb.supabase_repository import SupabaseKnowledgeRepository
from app.services.rag.factory import refresh_rag_service
from app.services.tourism.factory import warm_tourism_knowledge


async def main() -> None:
    settings = get_settings()
    if not settings.database_enabled:
        raise SystemExit(
            "DATABASE_ENABLED=false. Set it to true and configure DATABASE_URL first."
        )

    print("Syncing knowledge_chunks from places / regions / culture / phrases…")
    repo = SupabaseKnowledgeRepository()
    synced = await repo.sync_knowledge_chunks()
    print(f"Synced {synced} chunks into knowledge_chunks")

    stats = await warm_tourism_knowledge(sync=True)
    refresh_rag_service()
    print(f"Catalog places={stats['places']} rag_chunks={stats['chunks']}")
    print("Done. Restart uvicorn if it was already running without --reload.")


if __name__ == "__main__":
    asyncio.run(main())
