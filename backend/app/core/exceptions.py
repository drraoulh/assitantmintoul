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
