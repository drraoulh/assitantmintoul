from uuid import uuid4

from app.schemas.chat import ChatResponse
from app.services.ai.base import AIService


class PlaceholderAIService(AIService):
    """Phase 1 stand-in so Mobile → FastAPI → Mobile works without a model."""

    async def generate_response(
        self,
        message: str,
        conversation_id: str | None = None,
        *,
        brief: bool = False,
    ) -> ChatResponse:
        thread_id = conversation_id or str(uuid4())
        reply = (
            "Bienvenue. Je suis Smartmboa Tour, le guide touristique intelligent du Cameroun.\n\n"
            "Le moteur d'IA n'est pas encore connecté (phase 1 — fondation). "
            f"J'ai bien reçu votre message : « {message.strip()} ».\n\n"
            "Lors des prochaines étapes, je pourrai proposer des sites, "
            "des itinéraires et des informations culturelles à partir de "
            "modèles open source (Ollama / Hugging Face) et de données locales."
        )
        return ChatResponse(
            conversation_id=thread_id,
            role="assistant",
            message=reply,
            provider="placeholder",
        )
