import httpx
import pytest

from app.api.deps import get_ai_service
from app.core.exceptions import GenerationFailedError, OllamaUnavailableError
from app.main import app
from app.services.ai.ollama import OllamaAIService
from app.services.conversation.memory import InMemoryConversationStore
from tests.conftest import FakeAIService, client_with_ai


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
        ):
            raise OllamaUnavailableError()

    client = client_with_ai(UnavailableAI())
    response = client.post("/api/chat", json={"message": "Bonjour"})
    assert response.status_code == 503
    assert "Ollama" in response.json()["detail"]
    assert "Traceback" not in response.text


def test_ai_service_error_returns_502() -> None:
    class BrokenAI(FakeAIService):
        async def generate_response(
            self,
            message: str,
            conversation_id: str | None = None,
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
        client=client,
        model="qwen3:4b",
        timeout_seconds=5,
    )

    with pytest.raises(Exception) as exc_info:
        await service.generate_response("Bonjour")

    assert "qwen3:4b" in str(exc_info.value)


def teardown_module() -> None:
    app.dependency_overrides.clear()
