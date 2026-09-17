from abc import ABC, abstractmethod

from app.schemas.chat import ConversationSummary, ConversationTurn


class ConversationStore(ABC):
    """Conversation history port.

    Two implementations ship: in-memory (default, lost on restart) and
    SQL/Supabase (`DATABASE_ENABLED=true`). Routes and LLM adapters only
    depend on this interface.
    """

    #: True when threads survive a restart (used by the history endpoints).
    persistent: bool = False

    @abstractmethod
    async def start(self, conversation_id: str | None) -> str:
        """Return an existing id or create a new one."""

    @abstractmethod
    async def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        """Return prior turns as {role, content} dicts (no system prompt)."""

    @abstractmethod
    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        """Append one turn to the thread."""

    @abstractmethod
    async def get_turns(self, conversation_id: str) -> list[ConversationTurn]:
        """Return the readable thread, oldest first, for the history screen."""

    @abstractmethod
    async def list_conversations(self, limit: int = 30) -> list[ConversationSummary]:
        """Return recent threads, most recently updated first."""

    @abstractmethod
    async def delete(self, conversation_id: str) -> bool:
        """Drop a thread. Returns False when it does not exist."""
