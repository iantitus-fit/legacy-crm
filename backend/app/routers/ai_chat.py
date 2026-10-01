import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.user import User
from app.schemas.ai_chat import (
    BriefingResponse,
    ChatRequest,
    ChatResponse,
    Chip,
    ChipsResponse,
    ConversationListItem,
    ConversationListResponse,
    MessageListResponse,
    MessageResponse,
    NarrativeBriefingResponse,
    VALID_ENTITY_TYPES,
)
from app.services.ai_chat import (
    continue_conversation,
    get_briefing_context,
    start_conversation,
)
from app.services.ai_prompts import render_prompt
from app.services.ai_provider import NoneProvider, get_provider
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai-chat"])


def _msg_to_response(msg: AIMessage) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        metadata=msg.message_metadata,
        created_at=msg.created_at,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.entity_type and body.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported entity_type {body.entity_type!r}",
        )
    if body.conversation_id:
        convo = (
            db.query(AIConversation)
            .filter(AIConversation.id == body.conversation_id)
            .filter(AIConversation.user_id == current_user.id)
            .first()
        )
        if convo is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        msg = continue_conversation(
            db=db,
            conversation_id=convo.id,
            user_message=body.message,
        )
        return ChatResponse(
            conversation_id=convo.id,
            entity_type=convo.entity_type,
            entity_id=convo.entity_id,
            message=_msg_to_response(msg),
        )

    convo, msg = start_conversation(
        db=db,
        user_id=current_user.id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        initial_message=body.message,
    )
    return ChatResponse(
        conversation_id=convo.id,
        entity_type=convo.entity_type,
        entity_id=convo.entity_id,
        message=_msg_to_response(msg),
    )


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(AIConversation)
        .filter(AIConversation.user_id == current_user.id)
    )
    if entity_type is not None:
        query = query.filter(AIConversation.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AIConversation.entity_id == entity_id)

    rows = query.order_by(AIConversation.updated_at.desc()).all()

    items = []
    for c in rows:
        last = (
            db.query(AIMessage)
            .filter(AIMessage.conversation_id == c.id)
            .order_by(AIMessage.created_at.desc())
            .first()
        )
        message_count = (
            db.query(AIMessage)
            .filter(AIMessage.conversation_id == c.id)
            .count()
        )
        preview = None
        if last and last.content:
            preview = last.content.strip()
            if len(preview) > 120:
                preview = preview[:117] + "..."
        items.append(
            ConversationListItem(
                id=c.id,
                entity_type=c.entity_type,
                entity_id=c.entity_id,
                title=c.title,
                last_message_preview=preview,
                message_count=message_count,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return ConversationListResponse(items=items, total=len(items))


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
def get_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convo = (
        db.query(AIConversation)
        .filter(AIConversation.id == conversation_id)
        .filter(AIConversation.user_id == current_user.id)
        .first()
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    base = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.asc())
    )
    total = base.count()
    rows = base.offset((page - 1) * per_page).limit(per_page).all()
    return MessageListResponse(
        items=[_msg_to_response(m) for m in rows],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convo = (
        db.query(AIConversation)
        .filter(AIConversation.id == conversation_id)
        .filter(AIConversation.user_id == current_user.id)
        .first()
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(convo)
    db.commit()
    return None


@router.get("/briefing", response_model=BriefingResponse)
def briefing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_briefing_context(db=db, user_id=current_user.id)


@router.get("/briefing/narrative", response_model=NarrativeBriefingResponse)
def briefing_narrative(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    provider = get_provider()
    if isinstance(provider, NoneProvider):
        raise HTTPException(
            status_code=503,
            detail="LLM provider is not configured (LLM_PROVIDER=none)",
        )
    data = get_briefing_context(db=db, user_id=current_user.id)
    safe_json = json.dumps(data, default=str, indent=2)
    today_date = (
        data["generated_at"].date().isoformat()
        if hasattr(data["generated_at"], "date")
        else str(data["generated_at"])
    )
    first_name = (current_user.full_name or "").split(" ")[0] or "there"
    system, user_prompt = render_prompt(
        "morning_briefing",
        {
            "company_name": "Legacy Roofing & Exteriors",
            "user_first_name": first_name,
            "today_date": today_date,
            "briefing_data_json": safe_json,
        },
    )
    response = provider.generate(
        system_prompt=system, user_prompt=user_prompt, max_tokens=2048
    )
    return NarrativeBriefingResponse(
        narrative=response.content or "",
        data=data,
        provider=response.provider,
        model=response.model,
        tokens_used=response.tokens_used,
        duration_ms=response.duration_ms,
    )


GLOBAL_CHIPS = [
    Chip(label="What needs attention today?",
         prompt="What needs my attention today across all my customers and jobs?"),
    Chip(label="Overdue follow-ups",
         prompt="List my overdue follow-ups and suggest next steps."),
    Chip(label="Unpaid invoices",
         prompt="Summarize my unpaid invoices and which ones to chase first."),
    Chip(label="This week's schedule",
         prompt="What's on my schedule this week?"),
    Chip(label="Draft a follow-up for...",
         prompt="Help me draft a follow-up message. Which customer?"),
]

CONTACT_CHIPS = [
    Chip(label="Summarize this customer",
         prompt="Give me a summary of this customer for a pre-visit briefing."),
    Chip(label="Draft follow-up email",
         prompt="Draft a friendly follow-up email for this customer."),
    Chip(label="What's the history here?",
         prompt="What's the full history with this customer? Any concerns?"),
    Chip(label="Generate scope of work",
         prompt="Draft a scope of work based on this customer's most recent estimate."),
]

ESTIMATE_CHIPS = [
    Chip(label="Explain this estimate",
         prompt="Explain this estimate in plain language as if to the homeowner."),
    Chip(label="Draft approval follow-up",
         prompt="Draft a short follow-up to nudge the customer to approve this estimate."),
    Chip(label="Compare to similar jobs",
         prompt="Is this estimate priced in line with similar jobs we've done?"),
]


@router.get("/chips", response_model=ChipsResponse)
def chips(
    entity_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if entity_type == "contact":
        return ChipsResponse(items=CONTACT_CHIPS)
    if entity_type == "estimate":
        return ChipsResponse(items=ESTIMATE_CHIPS)
    return ChipsResponse(items=GLOBAL_CHIPS)
