from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import AsyncSessionLocal
from app.models.conversation import Conversation, Message
from app.schemas.chat import ConversationSummary, ConversationTurn
from app.services.conversation.base import ConversationStore
from app.services.conversation.memory import (
    InMemoryConversationStore,
    summarize_title,
)

logger = logging.getLogger(__name__)


def _as_uuid(value: str | None) -> UUID:
    """Accept any client id; mint a fresh one when it is not a UUID."""
    if not value:
        return uuid4()
    try:
        return UUID(str(value))
    except ValueError:
        return uuid4()


class SqlConversationStore(ConversationStore):
    """Persist threads in Postgres (Supabase).

    Every operation degrades to an in-memory thread when the database is
    unreachable, so a network hiccup never breaks the chat.
    """

    persistent = True

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        *,
        context_messages: int = 16,
    ) -> None:
        self._session_factory = session_factory or AsyncSessionLocal
        self._context_messages = context_messages
        self._fallback = InMemoryConversationStore(context_messages)

    def _degrade(self, action: str, error: Exception) -> None:
        logger.warning("Database %s failed (%s); using in-memory history", action, error)

    async def start(self, conversation_id: str | None) -> str:
        thread_id = _as_uuid(conversation_id)
        try:
            async with self._session_factory() as session:
                existing = await session.get(Conversation, thread_id)
                if existing is None:
                    session.add(Conversation(id=thread_id))
                    await session.commit()
        except SQLAlchemyError as error:
            self._degrade("start", error)
            return await self._fallback.start(str(thread_id))
        return str(thread_id)

    async def get_messages(self, conversation_id: str) -> list[dict[str, str]]:
        turns = await self.get_turns(conversation_id)
        recent = turns[-self._context_messages :] if self._context_messages else turns
        return [{"role": turn.role, "content": turn.content} for turn in recent]

    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        thread_id = _as_uuid(conversation_id)
        try:
            async with self._session_factory() as session:
                conversation = await session.get(Conversation, thread_id)
                if conversation is None:
                    conversation = Conversation(id=thread_id)
                    session.add(conversation)

                session.add(
                    Message(
                        conversation_id=thread_id,
                        role=role,
                        content=content,
                    )
                )
                if role == "user" and not conversation.title:
                    conversation.title = summarize_title(content)
                conversation.updated_at = datetime.now(timezone.utc)
                await session.commit()
        except SQLAlchemyError as error:
            self._degrade("add_message", error)
            await self._fallback.add_message(str(thread_id), role, content)

    async def get_turns(self, conversation_id: str) -> list[ConversationTurn]:
        thread_id = _as_uuid(conversation_id)
        try:
            async with self._session_factory() as session:
                rows = await session.execute(
                    select(Message)
                    .where(Message.conversation_id == thread_id)
                    .order_by(Message.created_at, Message.id)
                )
                return [
                    ConversationTurn(
                        role="user" if row.role == "user" else "assistant",
                        content=row.content,
                        created_at=row.created_at,
                    )
                    for row in rows.scalars()
                ]
        except SQLAlchemyError as error:
            self._degrade("get_turns", error)
            return await self._fallback.get_turns(str(thread_id))

    async def list_conversations(self, limit: int = 30) -> list[ConversationSummary]:
        try:
            async with self._session_factory() as session:
                rows = await session.execute(
                    select(
                        Conversation.id,
                        Conversation.title,
                        Conversation.updated_at,
                        func.count(Message.id).label("message_count"),
                    )
                    .join(Message, Message.conversation_id == Conversation.id)
                    .group_by(Conversation.id, Conversation.title, Conversation.updated_at)
                    .order_by(Conversation.updated_at.desc())
                    .limit(limit)
                )
                return [
                    ConversationSummary(
                        id=str(row.id),
                        title=row.title or "Nouvelle conversation",
                        message_count=int(row.message_count),
                        updated_at=row.updated_at,
                    )
                    for row in rows
                ]
        except SQLAlchemyError as error:
            self._degrade("list_conversations", error)
            return await self._fallback.list_conversations(limit)

    async def delete(self, conversation_id: str) -> bool:
        thread_id = _as_uuid(conversation_id)
        try:
            async with self._session_factory() as session:
                # Explicit message delete: do not rely on FK cascade enforcement.
                await session.execute(
                    sql_delete(Message).where(Message.conversation_id == thread_id)
                )
                result = await session.execute(
                    sql_delete(Conversation).where(Conversation.id == thread_id)
                )
                await session.commit()
                return bool(result.rowcount)
        except SQLAlchemyError as error:
            self._degrade("delete", error)
            return await self._fallback.delete(str(thread_id))
