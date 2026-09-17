from uuid import uuid4

from app.core.config import get_settings
from app.schemas.chat import ChatResponse
from app.services.ai.base import AIService


class HuggingFaceAIService(AIService):
    """Hugging Face compatible adapter.

    Not implemented in this phase. Later this can load a local Transformers
    model or call a self-hosted inference endpoint.
    """

    async def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
    ) -> ChatResponse:
        settings = get_settings()
        return ChatResponse(
            conversation_id=conversation_id or str(uuid4()),
            role="assistant",
            message=(
                "The Hugging Face provider is reserved in the architecture "
                f"(planned model: {settings.hf_model_id}) but is not wired yet. "
                "Set LLM_PROVIDER=ollama for local Qwen inference."
            ),
            provider="huggingface",
        )
