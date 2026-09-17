import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        if _is_empty_message(exc):
            return JSONResponse(
                status_code=400,
                content={"detail": "Message must not be empty."},
            )
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid chat request."},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred."},
        )


def _is_empty_message(exc: RequestValidationError) -> bool:
    for error in exc.errors():
        location = error.get("loc", ())
        if "message" in location:
            return True
    return False
