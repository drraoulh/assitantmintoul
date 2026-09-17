from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and .env files."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Cameroon AI Tour Guide"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "*"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/cameroon_tour_guide"
    )
    database_enabled: bool = False

    llm_provider: str = Field(
        default="ollama",
        validation_alias=AliasChoices("LLM_PROVIDER", "AI_PROVIDER"),
    )
    llm_model: str = Field(
        default="qwen3:4b",
        validation_alias=AliasChoices("LLM_MODEL", "OLLAMA_MODEL"),
    )
    ollama_base_url: str = "http://localhost:11434"
    ollama_timeout_seconds: float = 120

    hf_model_id: str = "Qwen/Qwen2.5-7B-Instruct"
    hf_embedding_model_id: str = (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    hf_vision_model_id: str = "openai/clip-vit-base-patch32"
    hf_whisper_model_id: str = "openai/whisper-small"
    hf_tts_model_id: str = "piper"
    huggingface_hub_token: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
