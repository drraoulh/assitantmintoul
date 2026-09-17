from functools import lru_cache

from app.services.conversation.base import ConversationStore
from app.services.conversation.memory import InMemoryConversationStore

__all__ = ["ConversationStore", "InMemoryConversationStore", "get_conversation_store"]


@lru_cache
def get_conversation_store() -> ConversationStore:
    return InMemoryConversationStore()
