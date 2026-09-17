class AppError(Exception):
    """Safe, client-facing application error. Never include a stack trace."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OllamaUnavailableError(AppError):
    def __init__(
        self,
        message: str = "Ollama is not running or cannot be reached at the configured URL.",
    ) -> None:
        super().__init__(message, status_code=503)


class HuggingFaceUnavailableError(AppError):
    def __init__(
        self,
        message: str = (
            "Hugging Face Inference Providers cannot be reached or the model is unavailable."
        ),
    ) -> None:
        super().__init__(message, status_code=503)


class HuggingFaceAuthError(AppError):
    def __init__(
        self,
        message: str = (
            "Hugging Face token missing or invalid. Set HUGGINGFACE_HUB_TOKEN "
            "(or HF_TOKEN) with Inference Providers access."
        ),
    ) -> None:
        super().__init__(message, status_code=401)


class ModelNotInstalledError(AppError):
    def __init__(self, model: str) -> None:
        super().__init__(
            (
                f"The model '{model}' is not installed in Ollama. "
                f"Run: ollama pull {model}"
            ),
            status_code=503,
        )


class GenerationTimeoutError(AppError):
    def __init__(
        self,
        message: str = "The language model took too long to respond. Try again.",
    ) -> None:
        super().__init__(message, status_code=504)


class GenerationFailedError(AppError):
    def __init__(
        self,
        message: str = "The language model failed to generate a response.",
    ) -> None:
        super().__init__(message, status_code=502)


class SpeechUnavailableError(AppError):
    def __init__(
        self,
        message: str = (
            "Speech recognition is not available. "
            "Set SPEECH_PROVIDER=whisper and install faster-whisper."
        ),
    ) -> None:
        super().__init__(message, status_code=503)


class TranscriptionFailedError(AppError):
    def __init__(
        self,
        message: str = "Could not transcribe the audio. Try speaking again.",
    ) -> None:
        super().__init__(message, status_code=502)


class SynthesisFailedError(AppError):
    def __init__(
        self,
        message: str = "Could not synthesize speech. Try again.",
    ) -> None:
        super().__init__(message, status_code=502)


class VisionUnavailableError(AppError):
    def __init__(
        self,
        message: str = (
            "Photo identification is not available. "
            "Set VISION_PROVIDER=gemini and GEMINI_API_KEY."
        ),
    ) -> None:
        super().__init__(message, status_code=503)


class VisionFailedError(AppError):
    def __init__(
        self,
        message: str = "Could not analyze the image. Try another photo.",
    ) -> None:
        super().__init__(message, status_code=502)
