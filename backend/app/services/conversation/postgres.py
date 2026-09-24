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
from app.services.conversation.timing import StoreTrace, timed_op, timed_session

logger = logging.getLogger(__name__)

# Process-local history cache for multi-turn voice (same worker).
# Avoids a second NullPool TLS round-trip when the thread was just loaded/written.
_HISTORY_CACHE_MAX = 64


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

    Phase 1.7: voice/chat prepare path uses a single session + SQL LIMIT and
    defers conversation INSERT until the first ``add_message`` (lazy create).
    An in-process history cache removes repeat TLS round-trips on multi-turn
    voice within the same worker.
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
        self.last_trace: StoreTrace | None = None
        # thread_id -> recent messages (oldest-first, up to context window)
        self._history_cache: dict[str, list[dict[str, str]]] = {}

    def _degrade(self, action: str, error: Exception) -> None:
        logger.warning("Database %s failed (%s); using in-memory history", action, error)

    def _cache_get(self, thread_id: str, limit: int) -> list[dict[str, str]] | None:
        cached = self._history_cache.get(thread_id)
        if cached is None:
            return None
        return cached[-limit:] if limit else list(cached)

    def _cache_put(self, thread_id: str, messages: list[dict[str, str]]) -> None:
        window = self._context_messages or len(messages)
        self._history_cache[thread_id] = list(messages[-window:])
        while len(self._history_cache) > _HISTORY_CACHE_MAX:
            self._history_cache.pop(next(iter(self._history_cache)))

    def _cache_append(self, thread_id: str, turns: list[tuple[str, str]]) -> None:
        current = list(self._history_cache.get(thread_id) or [])
        for role, content in turns:
            current.append(
                {
                    "role": "user" if role == "user" else "assistant",
                    "content": content,
                }
            )
        self._cache_put(thread_id, current)

    def _cache_invalidate(self, thread_id: str) -> None:
        self._history_cache.pop(thread_id, None)

    async def start(self, conversation_id: str | None) -> str:
        """Return a thread id without opening a DB connection (lazy create)."""
        trace = StoreTrace()
        self.last_trace = trace
        thread_id = _as_uuid(conversation_id)
        with timed_op(trace, "start_mint_id", created=conversation_id is None):
            pass
        trace.meta["mode"] = "lazy_start"
        return str(thread_id)

    async def get_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, str]]:
        """Return the last ``limit`` turns oldest-first (SQL LIMIT when uncached)."""
        trace = StoreTrace()
        self.last_trace = trace
        thread_id = str(_as_uuid(conversation_id))
        window = self._context_messages if limit is None else max(0, int(limit))
        if window <= 0:
            return []

        cached = self._cache_get(thread_id, window)
        if cached is not None:
            with timed_op(trace, "history_cache_hit", rows=len(cached)):
                pass
            trace.meta["mode"] = "get_messages_cache"
            return cached

        try:
            async with timed_session(self._session_factory, trace) as session:
                with timed_op(trace, "messages_get", limit=window):
                    rows = await session.execute(
                        select(Message.role, Message.content)
                        .where(Message.conversation_id == _as_uuid(thread_id))
                        .order_by(Message.created_at.desc(), Message.id.desc())
                        .limit(window)
                    )
                    fetched = list(rows.all())
                with timed_op(trace, "history_format", rows=len(fetched)):
                    recent = list(reversed(fetched))
                    history = [
                        {
                            "role": "user" if row.role == "user" else "assistant",
                            "content": row.content,
                        }
                        for row in recent
                    ]
            self._cache_put(thread_id, history)
            return history
        except SQLAlchemyError as error:
            self._degrade("get_messages", error)
            return await self._fallback.get_messages(thread_id)

    async def prepare_for_generation(
        self,
        conversation_id: str | None,
        *,
        limit: int | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        """Prepare ``(thread_id, history)`` with minimal Supabase round-trips."""
        trace = StoreTrace()
        self.last_trace = trace
        thread_id = str(_as_uuid(conversation_id))
        window = self._context_messages if limit is None else max(0, int(limit))
        trace.meta["conversation_id_given"] = conversation_id is not None
        trace.meta["limit"] = window

        if conversation_id is None:
            with timed_op(trace, "prepare_skip_db_new_thread"):
                pass
            self._cache_put(thread_id, [])
            trace.meta["mode"] = "prepare_no_db"
            return thread_id, []

        if window <= 0:
            return thread_id, []

        cached = self._cache_get(thread_id, window)
        if cached is not None:
            with timed_op(trace, "history_cache_hit", rows=len(cached)):
                pass
            trace.meta["mode"] = "prepare_cache_hit"
            return thread_id, cached

        try:
            async with timed_session(self._session_factory, trace) as session:
                with timed_op(trace, "messages_get", limit=window):
                    rows = await session.execute(
                        select(Message.role, Message.content)
                        .where(Message.conversation_id == _as_uuid(thread_id))
                        .order_by(Message.created_at.desc(), Message.id.desc())
                        .limit(window)
                    )
                    fetched = list(rows.all())
                with timed_op(trace, "history_format", rows=len(fetched)):
                    recent = list(reversed(fetched))
                    history = [
                        {
                            "role": "user" if row.role == "user" else "assistant",
                            "content": row.content,
                        }
                        for row in recent
                    ]
            self._cache_put(thread_id, history)
            trace.meta["mode"] = "prepare_single_session"
            return thread_id, history
        except SQLAlchemyError as error:
            self._degrade("prepare_for_generation", error)
            fb_id = await self._fallback.start(thread_id)
            return fb_id, await self._fallback.get_messages(fb_id)

    async def prepare_for_generation_legacy(
        self,
        conversation_id: str | None,
        *,
        limit: int | None = None,
    ) -> tuple[str, list[dict[str, str]], StoreTrace]:
        """Phase 1.6-style prepare: two sequential NullPool sessions (BEFORE baseline)."""
        trace = StoreTrace()
        thread_id = _as_uuid(conversation_id)
        window = self._context_messages if limit is None else max(0, int(limit))

        try:
            async with timed_session(self._session_factory, trace) as session:
                with timed_op(trace, "conversation_get"):
                    existing = await session.get(Conversation, thread_id)
                if existing is None:
                    with timed_op(trace, "conversation_create"):
                        session.add(Conversation(id=thread_id))
                    with timed_op(trace, "commit"):
                        await session.commit()
        except SQLAlchemyError as error:
            self._degrade("legacy_start", error)
            fb = await self._fallback.start(str(thread_id))
            return fb, await self._fallback.get_messages(fb), trace

        try:
            async with timed_session(self._session_factory, trace) as session:
                with timed_op(trace, "messages_get_full"):
                    rows = await session.execute(
                        select(Message)
                        .where(Message.conversation_id == thread_id)
                        .order_by(Message.created_at, Message.id)
                    )
                    all_rows = list(rows.scalars())
                with timed_op(trace, "history_format", rows=len(all_rows)):
                    turns = [
                        {
                            "role": "user" if row.role == "user" else "assistant",
                            "content": row.content,
                        }
                        for row in all_rows
                    ]
                    history = turns[-window:] if window else turns
            trace.meta["mode"] = "legacy_two_sessions"
            return str(thread_id), history, trace
        except SQLAlchemyError as error:
            self._degrade("legacy_get_messages", error)
            return str(thread_id), await self._fallback.get_messages(str(thread_id)), trace

    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        await self.add_messages(conversation_id, [(role, content)])

    async def add_messages(
        self,
        conversation_id: str,
        turns: list[tuple[str, str]],
    ) -> None:
        """Persist one or more turns in a single session/commit (Phase 1.7)."""
        if not turns:
            return
        trace = StoreTrace()
        self.last_trace = trace
        thread_id = str(_as_uuid(conversation_id))
        try:
            async with timed_session(self._session_factory, trace) as session:
                with timed_op(trace, "conversation_get"):
                    conversation = await session.get(Conversation, _as_uuid(thread_id))
                if conversation is None:
                    with timed_op(trace, "conversation_create"):
                        conversation = Conversation(id=_as_uuid(thread_id))
                        session.add(conversation)
                with timed_op(trace, "message_insert", count=len(turns)):
                    for role, content in turns:
                        session.add(
                            Message(
                                conversation_id=_as_uuid(thread_id),
                                role=role,
                                content=content,
                            )
                        )
                        if role == "user" and not conversation.title:
                            conversation.title = summarize_title(content)
                conversation.updated_at = datetime.now(timezone.utc)
                with timed_op(trace, "commit"):
                    await session.commit()
            self._cache_append(thread_id, turns)
        except SQLAlchemyError as error:
            self._degrade("add_messages", error)
            self._cache_invalidate(thread_id)
            for role, content in turns:
                await self._fallback.add_message(thread_id, role, content)

    async def get_turns(self, conversation_id: str) -> list[ConversationTurn]:
        """Full thread for the history UI (no LIMIT — intentional)."""
        trace = StoreTrace()
        self.last_trace = trace
        thread_id = _as_uuid(conversation_id)
        try:
            async with timed_session(self._session_factory, trace) as session:
                with timed_op(trace, "messages_get_full"):
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
        self._cache_invalidate(str(thread_id))
        try:
            async with self._session_factory() as session:
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
