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
        locale: str = "fr",
    ) -> ChatResponse:
        thread_id = conversation_id or str(uuid4())
        if locale == "en":
            reply = (
                "Welcome. I am Smartmboa Tour, Cameroon's intelligent tourist guide.\n\n"
                "The AI engine is not connected yet (phase 1 — foundation). "
                f"I received your message: “{message.strip()}”.\n\n"
                "In later steps I will suggest sites, itineraries and cultural "
                "information from open-source models (Ollama / Hugging Face) and local data."
            )
        else:
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
