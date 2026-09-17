from functools import lru_cache

from app.core.config import get_settings
from app.services.conversation.base import ConversationStore
from app.services.conversation.memory import InMemoryConversationStore
from app.services.conversation.postgres import SqlConversationStore

__all__ = [
    "ConversationStore",
    "InMemoryConversationStore",
    "SqlConversationStore",
    "get_conversation_store",
]


@lru_cache
def get_conversation_store() -> ConversationStore:
    """Supabase-backed history when DATABASE_ENABLED=true, else in-memory."""
    settings = get_settings()
    context = settings.conversation_context_messages
    if settings.database_enabled:
        return SqlConversationStore(context_messages=context)
    return InMemoryConversationStore(context)
