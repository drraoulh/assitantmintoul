"""Seed Firestore from local data/ files.

Usage:
  set FIREBASE_ENABLED=true
  set FIREBASE_PROJECT_ID=...
  set FIREBASE_CREDENTIALS_FILE=/path/to/serviceAccount.json
  python -m app.services.firebase.cli_seed
"""

from __future__ import annotations

import asyncio
import logging

from app.services.firebase.factory import create_firebase_store
from app.services.firebase.seed import seed_firebase_from_local

logging.basicConfig(level=logging.INFO)


async def _main() -> None:
    store = create_firebase_store()
    summary = await seed_firebase_from_local(store)
    print(f"Seeded Firebase: {summary}")


if __name__ == "__main__":
    asyncio.run(_main())
