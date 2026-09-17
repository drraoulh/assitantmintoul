import json

import httpx
import pytest

from app.core.config import get_settings
from app.core.exceptions import (
    GenerationFailedError,
    HuggingFaceAuthError,
    HuggingFaceUnavailableError,
    OllamaUnavailableError,
)
from app.main import app
from app.services.ai.huggingface import HuggingFaceAIService
from app.services.ai.ollama import OllamaAIService
from app.services.conversation.memory import InMemoryConversationStore
from app.services.rag.base import PlaceholderRAGService
from app.services.rag.local import LocalRAGService
from app.services.search.base import PlaceholderWebSearchService, WebSearchHit
from app.services.search.base import WebSearchService
from tests.conftest import FakeAIService, client_with_ai


class FakeWebSearch(WebSearchService):
    async def search(self, query: str, *, max_results: int = 5) -> list[WebSearchHit]:
        return [
            WebSearchHit(
                title="Kribi",
                snippet="Kribi est une ville côtière du Cameroun connue pour ses plages.",
                url="https://fr.wikipedia.org/wiki/Kribi",
                source="wikipedia-fr",
            )
        ]


def test_successful_chat_request() -> None:
    client = client_with_ai(FakeAIService())
    response = client.post(
        "/api/chat",
        json={"message": "Quels sont les sites touristiques de Yaoundé ?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "test-conversation"
    assert "Cameroun" in body["message"]
    assert body["message"]


def test_empty_message_is_rejected() -> None:
    client = client_with_ai(FakeAIService())
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "Message must not be empty."


def test_ollama_unavailable_returns_503() -> None:
    class UnavailableAI(FakeAIService):
        async def generate_response(
            self,
            message: str,
            conversation_id: str | None = None,
            *,
            brief: bool = False,
        ):
            raise OllamaUnavailableError()

    client = client_with_ai(UnavailableAI())
    response = client.post("/api/chat", json={"message": "Bonjour"})
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]
    assert "Traceback" not in response.text


def test_huggingface_auth_error_returns_401() -> None:
    class AuthAI(FakeAIService):
        async def generate_response(
            self,
            message: str,
            conversation_id: str | None = None,
            *,
            brief: bool = False,
        ):
            raise HuggingFaceAuthError()

    client = client_with_ai(AuthAI())
    response = client.post("/api/chat", json={"message": "Bonjour"})
    assert response.status_code == 401
    assert "Hugging Face" in response.json()["detail"]


def test_ai_service_error_returns_502() -> None:
    class BrokenAI(FakeAIService):
        async def generate_response(
            self,
            message: str,
            conversation_id: str | None = None,
            *,
            brief: bool = False,
        ):
            raise GenerationFailedError()

    client = client_with_ai(BrokenAI())
    response = client.post("/api/chat", json={"message": "Bonjour"})
    assert response.status_code == 502
    assert "detail" in response.json()
    assert "Traceback" not in response.text


@pytest.mark.asyncio
async def test_ollama_connect_error_is_mapped() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost:11434")
    service = OllamaAIService(
        conversation_store=InMemoryConversationStore(),
        rag_service=PlaceholderRAGService(),
        web_search_service=PlaceholderWebSearchService(),
        client=client,
        model="qwen3:4b",
        timeout_seconds=5,
    )

    with pytest.raises(OllamaUnavailableError):
        await service.generate_response("Bonjour")


@pytest.mark.asyncio
async def test_ollama_missing_model_is_mapped() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'qwen3:4b' not found"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost:11434")
    service = OllamaAIService(
        conversation_store=InMemoryConversationStore(),
        rag_service=PlaceholderRAGService(),
        web_search_service=PlaceholderWebSearchService(),
        client=client,
        model="qwen3:4b",
        timeout_seconds=5,
    )

    with pytest.raises(Exception) as exc_info:
        await service.generate_response("Bonjour")

    assert "qwen3:4b" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_prompt_includes_rag_context() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "Voici des idées à Yaoundé."}},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, base_url="http://localhost:11434")
    service = OllamaAIService(
        conversation_store=InMemoryConversationStore(),
        rag_service=LocalRAGService(),
        web_search_service=PlaceholderWebSearchService(),
        client=client,
        model="qwen3:4b",
        timeout_seconds=5,
        rag_top_k=3,
    )

    response = await service.generate_response("Quels sites visiter à Yaoundé ?")
    assert response.message
    payload = json.loads(captured["body"].decode())
    system = payload["messages"][0]["content"]
    assert "Curated knowledge base excerpts" in system
    assert "Yaound" in system


@pytest.mark.asyncio
async def test_huggingface_requires_token() -> None:
    service = HuggingFaceAIService(
        conversation_store=InMemoryConversationStore(),
        rag_service=PlaceholderRAGService(),
        web_search_service=PlaceholderWebSearchService(),
        api_token="",
    )
    with pytest.raises(HuggingFaceAuthError):
        await service.generate_response("Bonjour")


@pytest.mark.asyncio
async def test_huggingface_prompt_includes_rag_and_web() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Kribi offre plages et chutes de la Lobé.",
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://router.huggingface.co/v1",
    )
    service = HuggingFaceAIService(
        conversation_store=InMemoryConversationStore(),
        rag_service=LocalRAGService(),
        web_search_service=FakeWebSearch(),
        client=client,
        api_token="hf_test_token",
        model="Qwen/Qwen2.5-7B-Instruct",
        timeout_seconds=5,
        rag_top_k=3,
        web_search_max_results=2,
    )

    response = await service.generate_response("Que voir à Kribi ?")
    assert "Kribi" in response.message
    assert response.provider == "huggingface"
    payload = json.loads(captured["body"].decode())
    system = payload["messages"][0]["content"]
    assert "Curated knowledge base excerpts" in system
    assert "Live web search results" in system
    assert "wikipedia" in system.lower() or "Kribi" in system


@pytest.mark.asyncio
async def test_voice_mode_asks_for_a_short_spoken_answer() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.read()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "Allez à Kribi."}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://router.huggingface.co/v1",
    )
    service = HuggingFaceAIService(
        conversation_store=InMemoryConversationStore(),
        rag_service=PlaceholderRAGService(),
        web_search_service=PlaceholderWebSearchService(),
        client=client,
        api_token="hf_test_token",
        timeout_seconds=5,
    )

    await service.generate_response("Que voir à Kribi ?", brief=True)
    payload = json.loads(captured["body"].decode())
    assert "Voice mode" in payload["messages"][0]["content"]
    assert payload["max_tokens"] == get_settings().llm_voice_max_tokens
    assert payload["max_tokens"] < get_settings().llm_max_tokens


@pytest.mark.asyncio
async def test_huggingface_unavailable_on_connect_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="https://router.huggingface.co/v1",
    )
    service = HuggingFaceAIService(
        conversation_store=InMemoryConversationStore(),
        rag_service=PlaceholderRAGService(),
        web_search_service=PlaceholderWebSearchService(),
        client=client,
        api_token="hf_test_token",
    )
    with pytest.raises(HuggingFaceUnavailableError):
        await service.generate_response("Bonjour")


def teardown_module() -> None:
    app.dependency_overrides.clear()
