from abc import ABC, abstractmethod

from app.schemas.chat import ChatResponse


class AIService(ABC):
    """Replaceable language-model backend.

    Routes depend on this interface only. Swap the implementation
    (placeholder, Ollama, Hugging Face) via AI_PROVIDER without
    changing API endpoints.
    """

    @abstractmethod
    async def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> ChatResponse:
        """Return an assistant reply for the given user message."""
