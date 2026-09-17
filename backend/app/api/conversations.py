from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import get_conversation_store
from app.schemas.chat import (
    ConversationHistoryResponse,
    ConversationListResponse,
)
from app.services.conversation.base import ConversationStore

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    limit: int = Query(default=30, ge=1, le=100),
    store: ConversationStore = Depends(get_conversation_store),
) -> ConversationListResponse:
    items = await store.list_conversations(limit=limit)
    return ConversationListResponse(
        items=items,
        count=len(items),
        persistent=store.persistent,
    )


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation(
    conversation_id: str,
    store: ConversationStore = Depends(get_conversation_store),
) -> ConversationHistoryResponse:
    turns = await store.get_turns(conversation_id)
    if not turns:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return ConversationHistoryResponse(
        conversation_id=conversation_id,
        messages=turns,
        count=len(turns),
    )


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    store: ConversationStore = Depends(get_conversation_store),
) -> Response:
    deleted = await store.delete(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return Response(status_code=204)
