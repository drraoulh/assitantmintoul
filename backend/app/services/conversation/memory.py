from asyncio import Lock
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.chat import ConversationSummary, ConversationTurn
from app.services.conversation.base import ConversationStore


def summarize_title(content: str) -> str:
    cleaned = " ".join(content.split()).strip()
    if len(cleaned) <= 60:
        return cleaned or "Nouvelle conversation"
    return f"{cleaned[:60].rstrip()}…"


class InMemoryConversationStore(ConversationStore):
    """Process-local chat history. Lost on restart; easy to replace later."""

    persistent = False

    def __init__(self, max_messages: int = 16) -> None:
        self._threads: dict[str, list[ConversationTurn]] = {}
        self._lock = Lock()
        self._max_messages = max_messages

    async def start(self, conversation_id: str | None) -> str:
        thread_id = conversation_id or str(uuid4())
        async with self._lock:
            self._threads.setdefault(thread_id, [])
        return thread_id

    async def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        async with self._lock:
            turns = self._threads.get(conversation_id, [])
            return [
                {"role": turn.role, "content": turn.content}
                for turn in turns[-self._max_messages :]
            ]

    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        async with self._lock:
            history = self._threads.setdefault(conversation_id, [])
            history.append(
                ConversationTurn(
                    role="user" if role == "user" else "assistant",
                    content=content,
                    created_at=datetime.now(timezone.utc),
                )
            )

    async def get_turns(self, conversation_id: str) -> list[ConversationTurn]:
        async with self._lock:
            return list(self._threads.get(conversation_id, []))

    async def list_conversations(self, limit: int = 30) -> list[ConversationSummary]:
        async with self._lock:
            summaries: list[ConversationSummary] = []
            for thread_id, turns in self._threads.items():
                if not turns:
                    continue
                first_user = next(
                    (turn.content for turn in turns if turn.role == "user"),
                    "",
                )
                summaries.append(
                    ConversationSummary(
                        id=thread_id,
                        title=summarize_title(first_user),
                        message_count=len(turns),
                        updated_at=turns[-1].created_at,
                    )
                )
        summaries.sort(
            key=lambda item: item.updated_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return summaries[:limit]

    async def delete(self, conversation_id: str) -> bool:
        async with self._lock:
            return self._threads.pop(conversation_id, None) is not None
