from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_action import AIAction
from app.models.user import User
from app.schemas.ai_action import (
    AIActionListResponse,
    AIActionResponse,
    AIStatsResponse,
    GenerateRequest,
    VALID_EVENT_TYPES,
)
from app.services.ai_events import dispatch
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/generate", response_model=AIActionResponse)
def generate(
    body: GenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported event_type '{body.event_type}'",
        )

    record = dispatch(
        db=db,
        event_type=body.event_type,
        contact_id=body.contact_id,
        estimate_id=body.estimate_id,
        user_id=current_user.id,
        extra=body.extra,
    )
    if record is None:
        raise HTTPException(
            status_code=503,
            detail="AI is disabled (AI_ENABLED=false)",
        )
    return record


@router.post("/actions/{action_id}/use", response_model=AIActionResponse)
def mark_used(
    action_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(AIAction).filter(AIAction.id == action_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="AI action not found")
    record.status = "used"
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return record


@router.post("/actions/{action_id}/dismiss", response_model=AIActionResponse)
def mark_dismissed(
    action_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.query(AIAction).filter(AIAction.id == action_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="AI action not found")
    record.status = "dismissed"
    db.commit()
    db.refresh(record)
    return record


@router.get("/actions", response_model=AIActionListResponse)
def list_actions(
    contact_id: Optional[int] = Query(None),
    estimate_id: Optional[int] = Query(None),
    event_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AIAction)
    if contact_id is not None:
        query = query.filter(AIAction.contact_id == contact_id)
    if estimate_id is not None:
        query = query.filter(AIAction.estimate_id == estimate_id)
    if event_type:
        query = query.filter(AIAction.event_type == event_type)
    if status:
        query = query.filter(AIAction.status == status)

    total = query.count()
    rows = (
        query.order_by(AIAction.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return AIActionListResponse(
        items=rows, total=total, page=page, per_page=per_page
    )


@router.get("/stats", response_model=AIStatsResponse)
def stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = db.query(func.count(AIAction.id)).scalar() or 0
    by_status = dict(
        db.query(AIAction.status, func.count(AIAction.id))
        .group_by(AIAction.status)
        .all()
    )
    by_event = dict(
        db.query(AIAction.event_type, func.count(AIAction.id))
        .group_by(AIAction.event_type)
        .all()
    )
    by_provider = dict(
        db.query(AIAction.provider, func.count(AIAction.id))
        .group_by(AIAction.provider)
        .all()
    )
    total_tokens = (
        db.query(func.coalesce(func.sum(AIAction.tokens_used), 0)).scalar() or 0
    )

    return AIStatsResponse(
        total_actions=int(total),
        completed=int(by_status.get("completed", 0)),
        failed=int(by_status.get("failed", 0)),
        used=int(by_status.get("used", 0)),
        dismissed=int(by_status.get("dismissed", 0)),
        pending=int(by_status.get("pending", 0)),
        total_tokens=int(total_tokens),
        by_event_type={k: int(v) for k, v in by_event.items()},
        by_provider={k: int(v) for k, v in by_provider.items()},
    )
