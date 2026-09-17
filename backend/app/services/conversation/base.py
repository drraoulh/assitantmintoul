from abc import ABC, abstractmethod


class ConversationStore(ABC):
    """Conversation history port.

    Phase 2 uses an in-memory implementation. A later phase can swap this
    for PostgreSQL without changing the chat route or the LLM adapter.
    """

    @abstractmethod
    async def start(self, conversation_id: str | None) -> str:
        """Return an existing id or create a new one."""

    @abstractmethod
    async def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        """Return prior turns as {role, content} dicts (no system prompt)."""

    @abstractmethod
    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        """Append one turn to the thread."""
