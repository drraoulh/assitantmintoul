from collections.abc import Sequence

from fastapi.testclient import TestClient

from app.api.deps import get_ai_service
from app.main import app
from app.schemas.chat import ChatResponse
from app.services.ai.base import AIService
from app.services.rag.types import RetrievedChunk


class FakeAIService(AIService):
    async def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
        retrieved_context: Sequence[RetrievedChunk] | None = None,
        *,
        brief: bool = False,
        locale: str = "fr",
    ) -> ChatResponse:
        extra = ""
        if retrieved_context:
            extra = " | " + retrieved_context[0].site_name
        return ChatResponse(
            conversation_id=conversation_id or "test-conversation",
            message=f"Bienvenue au Cameroun. Vous avez dit : {message}{extra}",
            provider="fake",
        )


def client_with_ai(service: AIService) -> TestClient:
    app.dependency_overrides[get_ai_service] = lambda: service
    return TestClient(app)
