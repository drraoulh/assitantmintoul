from functools import lru_cache

from app.core.config import get_settings
from app.services.firebase.base import FirebaseKnowledgeStore, PlaceholderFirebaseStore
from app.services.firebase.firestore import FirestoreKnowledgeStore


def create_firebase_store() -> FirebaseKnowledgeStore:
    settings = get_settings()
    if not settings.firebase_enabled:
        return PlaceholderFirebaseStore()
    if not settings.firebase_project_id.strip():
        raise ValueError(
            "FIREBASE_ENABLED=true requires FIREBASE_PROJECT_ID to be set."
        )
    return FirestoreKnowledgeStore(
        project_id=settings.firebase_project_id,
        credentials_file=settings.firebase_credentials_file,
    )


@lru_cache
def get_firebase_store() -> FirebaseKnowledgeStore:
    return create_firebase_store()
