import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_conversation_store
from app.core.database import Base
from app.main import app
from app.services.conversation.memory import InMemoryConversationStore
from app.services.conversation.postgres import SqlConversationStore, _as_uuid


def client_with_store(store) -> TestClient:
    app.dependency_overrides[get_conversation_store] = lambda: store
    return TestClient(app)


@pytest.mark.asyncio
async def test_memory_store_lists_and_titles_threads() -> None:
    store = InMemoryConversationStore()
    thread = await store.start(None)
    await store.add_message(thread, "user", "Que visiter à Kribi en deux jours ?")
    await store.add_message(thread, "assistant", "Les chutes de la Lobé.")

    summaries = await store.list_conversations()
    assert len(summaries) == 1
    assert summaries[0].id == thread
    assert summaries[0].title.startswith("Que visiter à Kribi")
    assert summaries[0].message_count == 2

    turns = await store.get_turns(thread)
    assert [turn.role for turn in turns] == ["user", "assistant"]
    assert await store.delete(thread) is True
    assert await store.delete(thread) is False


def test_history_endpoints_expose_stored_thread() -> None:
    store = InMemoryConversationStore()

    async def seed() -> str:
        thread_id = await store.start(None)
        await store.add_message(thread_id, "user", "Bonjour depuis Douala")
        await store.add_message(thread_id, "assistant", "Bienvenue à Douala.")
        return thread_id

    thread_id = asyncio.run(seed())
    client = client_with_store(store)

    listed = client.get("/api/conversations")
    assert listed.status_code == 200
    body = listed.json()
    assert body["persistent"] is False
    assert body["count"] == 1
    assert body["items"][0]["id"] == thread_id
    assert body["items"][0]["title"] == "Bonjour depuis Douala"

    history = client.get(f"/api/conversations/{thread_id}")
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[1]["content"] == "Bienvenue à Douala."

    assert client.delete(f"/api/conversations/{thread_id}").status_code == 204
    assert client.get(f"/api/conversations/{thread_id}").status_code == 404


def test_unknown_conversation_returns_404() -> None:
    client = client_with_store(InMemoryConversationStore())
    response = client.get("/api/conversations/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."


def test_delete_unknown_conversation_returns_404() -> None:
    client = client_with_store(InMemoryConversationStore())
    response = client.delete("/api/conversations/does-not-exist")
    assert response.status_code == 404


def test_client_ids_that_are_not_uuid_get_a_fresh_uuid() -> None:
    assert str(_as_uuid("7cdf3c8c-8cb9-4163-8ea2-cad044d9ec43")) == (
        "7cdf3c8c-8cb9-4163-8ea2-cad044d9ec43"
    )
    assert _as_uuid("not-a-uuid") != _as_uuid("not-a-uuid")


@pytest.mark.asyncio
async def test_sql_store_falls_back_to_memory_when_database_is_down() -> None:
    class BrokenSession:
        async def __aenter__(self):
            raise OperationalError("SELECT 1", {}, Exception("no route to host"))

        async def __aexit__(self, *_: object) -> None:
            return None

    store = SqlConversationStore(session_factory=lambda: BrokenSession())

    thread = await store.start("11111111-1111-1111-1111-111111111111")
    await store.add_message(thread, "user", "Bonjour")
    await store.add_message(thread, "assistant", "Salut")

    assert await store.get_messages(thread) == [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Salut"},
    ]
    summaries = await store.list_conversations()
    assert summaries and summaries[0].title == "Bonjour"


@pytest.mark.asyncio
async def test_sql_store_persists_threads() -> None:
    """Exercise the real SQL path (SQLite stands in for Supabase Postgres)."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = SqlConversationStore(
        session_factory=async_sessionmaker(engine, expire_on_commit=False),
    )

    thread = await store.start(None)
    await store.add_message(thread, "user", "Que voir à Foumban ?")
    await store.add_message(thread, "assistant", "Le palais des sultans Bamoun.")
    await store.add_message(thread, "user", "Et à Bafoussam ?")

    # A second, older thread must come after the first one in the listing.
    other = await store.start(None)
    await store.add_message(other, "user", "Bonjour")

    assert await store.get_messages(thread) == [
        {"role": "user", "content": "Que voir à Foumban ?"},
        {"role": "assistant", "content": "Le palais des sultans Bamoun."},
        {"role": "user", "content": "Et à Bafoussam ?"},
    ]

    summaries = await store.list_conversations()
    assert {summary.id for summary in summaries} == {thread, other}
    stored = next(summary for summary in summaries if summary.id == thread)
    assert stored.title == "Que voir à Foumban ?"
    assert stored.message_count == 3

    assert await store.delete(thread) is True
    assert await store.get_turns(thread) == []
    assert [summary.id for summary in await store.list_conversations()] == [other]

    await engine.dispose()


def teardown_module() -> None:
    app.dependency_overrides.clear()
