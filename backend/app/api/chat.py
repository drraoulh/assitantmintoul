from fastapi import APIRouter, Depends

from app.api.deps import get_ai_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai.base import AIService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    ai_service: AIService = Depends(get_ai_service),
) -> ChatResponse:
    return await ai_service.generate_response(
        message=payload.message,
        conversation_id=payload.conversation_id,
        brief=payload.mode == "voice",
    )
