from app.core.config import get_settings
from app.services.ai.base import AIService
from app.services.ai.huggingface import HuggingFaceAIService
from app.services.ai.ollama import OllamaAIService
from app.services.ai.placeholder import PlaceholderAIService
from app.services.conversation import get_conversation_store


def create_ai_service() -> AIService:
    """Build the AI backend selected by LLM_PROVIDER / AI_PROVIDER."""
    provider = get_settings().llm_provider.strip().lower()
    store = get_conversation_store()

    if provider == "placeholder":
        return PlaceholderAIService()
    if provider == "ollama":
        return OllamaAIService(conversation_store=store)
    if provider in {"huggingface", "hf"}:
        return HuggingFaceAIService(conversation_store=store)
    if provider == "gemini":
        # Same agent pipeline; completions go to Gemini's OpenAI-compatible endpoint.
        return HuggingFaceAIService(conversation_store=store, provider="gemini")

    raise ValueError(
        f"Unknown LLM_PROVIDER '{provider}'. "
        "Use huggingface, gemini, ollama, or placeholder."
    )
