from asyncio import Lock
from uuid import uuid4

from app.services.conversation.base import ConversationStore


class InMemoryConversationStore(ConversationStore):
    """Process-local chat history. Lost on restart; easy to replace later."""

    def __init__(self, max_messages: int = 16) -> None:
        self._threads: dict[str, list[dict[str, str]]] = {}
        self._lock = Lock()
        self._max_messages = max_messages

    async def start(self, conversation_id: str | None) -> str:
        thread_id = conversation_id or str(uuid4())
        async with self._lock:
            self._threads.setdefault(thread_id, [])
        return thread_id

    async def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        async with self._lock:
            return list(self._threads.get(conversation_id, []))

    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        async with self._lock:
            history = self._threads.setdefault(conversation_id, [])
            history.append({"role": role, "content": content})
            if len(history) > self._max_messages:
                self._threads[conversation_id] = history[-self._max_messages :]
