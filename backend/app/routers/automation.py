"""Sprint 19b — automation API.

CRUD for sequences, steps, and enrollments + a dashboard and execution-log
endpoint. The router pulls service-layer logic from
``app.services.automation_service`` for enrollment, stop, and trigger
operations so business rules stay in one place.

Auth: every endpoint requires an authenticated user. No role gate — the SMS
config admin restriction is about credentials; automations are operational.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.automation import (
    AutomationEnrollment,
    AutomationLog,
    AutomationSequence,
    AutomationStep,
)
from app.models.contact import Contact
from app.models.user import User
from app.schemas.automation import (
    AutomationLogListResponse,
    AutomationLogResponse,
    ContactToggleRequest,
    ContactToggleResponse,
    DashboardActivityItem,
    DashboardResponse,
    EnrollmentListResponse,
    EnrollmentManualCreate,
    EnrollmentResponse,
    EnrollmentStopRequest,
    SequenceCreate,
    SequenceListResponse,
    SequenceResponse,
    SequenceUpdate,
    StepCreate,
    StepReorderRequest,
    StepResponse,
    StepUpdate,
)
from app.services import automation_service
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/automations", tags=["automations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_sequence_or_404(db: Session, sequence_id: int) -> AutomationSequence:
    seq = (
        db.query(AutomationSequence)
        .options(joinedload(AutomationSequence.steps))
        .filter(AutomationSequence.id == sequence_id)
        .first()
    )
    if not seq:
        raise HTTPException(status_code=404, detail="Sequence not found")
    return seq


def _get_step_or_404(db: Session, step_id: int) -> AutomationStep:
    step = (
        db.query(AutomationStep).filter(AutomationStep.id == step_id).first()
    )
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return step


def _get_enrollment_or_404(
    db: Session, enrollment_id: int
) -> AutomationEnrollment:
    enrollment = (
        db.query(AutomationEnrollment)
        .filter(AutomationEnrollment.id == enrollment_id)
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return enrollment


def _sequence_to_response(
    db: Session, seq: AutomationSequence
) -> SequenceResponse:
    active_count = (
        db.query(func.count(AutomationEnrollment.id))
        .filter(
            AutomationEnrollment.sequence_id == seq.id,
            AutomationEnrollment.status == "active",
        )
        .scalar()
        or 0
    )
    total_count = (
        db.query(func.count(AutomationEnrollment.id))
        .filter(AutomationEnrollment.sequence_id == seq.id)
        .scalar()
        or 0
    )
    steps_sorted = sorted(seq.steps, key=lambda s: s.step_order)
    return SequenceResponse(
        id=seq.id,
        name=seq.name,
        description=seq.description,
        trigger_type=seq.trigger_type,
        trigger_config=seq.trigger_config or {},
        is_active=seq.is_active,
        created_at=seq.created_at,
        updated_at=seq.updated_at,
        steps=[StepResponse.model_validate(s) for s in steps_sorted],
        step_count=len(steps_sorted),
        active_enrollment_count=active_count,
        total_enrollment_count=total_count,
    )


def _enrollment_to_response(
    enrollment: AutomationEnrollment,
) -> EnrollmentResponse:
    return EnrollmentResponse(
        id=enrollment.id,
        sequence_id=enrollment.sequence_id,
        contact_id=enrollment.contact_id,
        current_step_order=enrollment.current_step_order,
        status=enrollment.status,
        enrolled_at=enrollment.enrolled_at,
        completed_at=enrollment.completed_at,
        stopped_at=enrollment.stopped_at,
        stopped_reason=enrollment.stopped_reason,
        next_step_at=enrollment.next_step_at,
        sequence_name=(
            enrollment.sequence.name if enrollment.sequence else None
        ),
        contact_name=(
            enrollment.contact.name if enrollment.contact else None
        ),
    )


def _log_to_response(log: AutomationLog) -> AutomationLogResponse:
    enrollment = log.enrollment
    return AutomationLogResponse(
        id=log.id,
        enrollment_id=log.enrollment_id,
        step_id=log.step_id,
        channel=log.channel,
        rendered_body=log.rendered_body,
        rendered_subject=log.rendered_subject,
        status=log.status,
        sent_at=log.sent_at,
        error_message=log.error_message,
        created_at=log.created_at,
        sequence_name=(
            enrollment.sequence.name
            if enrollment and enrollment.sequence
            else None
        ),
        contact_name=(
            enrollment.contact.name
            if enrollment and enrollment.contact
            else None
        ),
    )


# ---------------------------------------------------------------------------
# Sequences
# ---------------------------------------------------------------------------
@router.get("/sequences", response_model=SequenceListResponse)
def list_sequences(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    sequences = (
        db.query(AutomationSequence)
        .options(joinedload(AutomationSequence.steps))
        .order_by(AutomationSequence.id.desc())
        .all()
    )
    items = [_sequence_to_response(db, s) for s in sequences]
    return SequenceListResponse(items=items, total=len(items))


@router.post("/sequences", response_model=SequenceResponse, status_code=201)
def create_sequence(
    data: SequenceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    existing = (
        db.query(AutomationSequence)
        .filter(AutomationSequence.name == data.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="A sequence with this name already exists",
        )

    seq = AutomationSequence(
        name=data.name,
        description=data.description,
        trigger_type=data.trigger_type,
        trigger_config=data.trigger_config or {},
        is_active=data.is_active,
    )
    db.add(seq)
    db.flush()

    if data.steps:
        used_orders = set()
        next_order = 1
        for step_data in data.steps:
            order = step_data.step_order
            if order is None:
                while next_order in used_orders:
                    next_order += 1
                order = next_order
            used_orders.add(order)
            next_order = max(next_order, order + 1)
            step = AutomationStep(
                sequence_id=seq.id,
                step_order=order,
                channel=step_data.channel,
                delay_minutes=step_data.delay_minutes,
                template_body=step_data.template_body,
                template_subject=step_data.template_subject,
                stop_on_reply=step_data.stop_on_reply,
                stop_on_stage_change=step_data.stop_on_stage_change,
                is_active=step_data.is_active,
            )
            db.add(step)

    db.commit()
    seq = _get_sequence_or_404(db, seq.id)
    return _sequence_to_response(db, seq)


@router.get("/sequences/{sequence_id}", response_model=SequenceResponse)
def get_sequence(
    sequence_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    seq = _get_sequence_or_404(db, sequence_id)
    return _sequence_to_response(db, seq)


@router.put("/sequences/{sequence_id}", response_model=SequenceResponse)
def update_sequence(
    sequence_id: int,
    data: SequenceUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    seq = _get_sequence_or_404(db, sequence_id)
    update_data = data.model_dump(exclude_unset=True)

    if (
        "name" in update_data
        and update_data["name"]
        and update_data["name"] != seq.name
    ):
        conflict = (
            db.query(AutomationSequence)
            .filter(
                AutomationSequence.name == update_data["name"],
                AutomationSequence.id != sequence_id,
            )
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=400,
                detail="A sequence with this name already exists",
            )

    for field, value in update_data.items():
        setattr(seq, field, value)
    db.commit()
    db.refresh(seq)
    return _sequence_to_response(db, seq)


@router.put("/sequences/{sequence_id}/toggle", response_model=SequenceResponse)
def toggle_sequence(
    sequence_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    seq = _get_sequence_or_404(db, sequence_id)
    seq.is_active = not seq.is_active
    db.commit()
    db.refresh(seq)
    return _sequence_to_response(db, seq)


@router.delete("/sequences/{sequence_id}", status_code=204)
def delete_sequence(
    sequence_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    seq = _get_sequence_or_404(db, sequence_id)
    active_count = (
        db.query(func.count(AutomationEnrollment.id))
        .filter(
            AutomationEnrollment.sequence_id == sequence_id,
            AutomationEnrollment.status == "active",
        )
        .scalar()
        or 0
    )
    if active_count > 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot delete sequence with {active_count} active "
                "enrollment(s). Stop enrollments first or deactivate the "
                "sequence."
            ),
        )
    seq.is_active = False
    db.commit()


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------
@router.post(
    "/sequences/{sequence_id}/steps",
    response_model=StepResponse,
    status_code=201,
)
def create_step(
    sequence_id: int,
    data: StepCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    seq = _get_sequence_or_404(db, sequence_id)
    if data.channel not in ("sms", "email"):
        raise HTTPException(
            status_code=400, detail="channel must be 'sms' or 'email'"
        )

    step_order = data.step_order
    if step_order is None:
        existing_orders = [s.step_order for s in seq.steps]
        step_order = (max(existing_orders) + 1) if existing_orders else 1

    # Avoid colliding with an existing step_order — shift the new step past the max.
    conflict = (
        db.query(AutomationStep)
        .filter(
            AutomationStep.sequence_id == sequence_id,
            AutomationStep.step_order == step_order,
        )
        .first()
    )
    if conflict:
        existing_orders = [s.step_order for s in seq.steps]
        step_order = (max(existing_orders) + 1) if existing_orders else 1

    step = AutomationStep(
        sequence_id=sequence_id,
        step_order=step_order,
        channel=data.channel,
        delay_minutes=data.delay_minutes,
        template_body=data.template_body,
        template_subject=data.template_subject,
        stop_on_reply=data.stop_on_reply,
        stop_on_stage_change=data.stop_on_stage_change,
        is_active=data.is_active,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return StepResponse.model_validate(step)


@router.put("/steps/{step_id}", response_model=StepResponse)
def update_step(
    step_id: int,
    data: StepUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    step = _get_step_or_404(db, step_id)
    update_data = data.model_dump(exclude_unset=True)
    if "channel" in update_data and update_data["channel"] not in (
        "sms",
        "email",
    ):
        raise HTTPException(
            status_code=400, detail="channel must be 'sms' or 'email'"
        )
    for field, value in update_data.items():
        setattr(step, field, value)
    db.commit()
    db.refresh(step)
    return StepResponse.model_validate(step)


@router.delete("/steps/{step_id}", status_code=204)
def delete_step(
    step_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    step = _get_step_or_404(db, step_id)
    db.delete(step)
    db.commit()


@router.put(
    "/sequences/{sequence_id}/steps/reorder",
    response_model=SequenceResponse,
)
def reorder_steps(
    sequence_id: int,
    data: StepReorderRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    seq = _get_sequence_or_404(db, sequence_id)
    steps_by_id = {s.id: s for s in seq.steps}
    for item in data.items:
        step = steps_by_id.get(item.step_id)
        if not step or step.sequence_id != sequence_id:
            raise HTTPException(
                status_code=400,
                detail=f"Step {item.step_id} does not belong to this sequence",
            )

    # Shift all step_orders into a temporary high range first to dodge the
    # unique (sequence_id, step_order) constraint during the swap.
    high_offset = (
        max((s.step_order for s in seq.steps), default=0)
        + len(data.items)
        + 1000
    )
    for idx, item in enumerate(data.items):
        steps_by_id[item.step_id].step_order = high_offset + idx
    db.flush()
    for item in data.items:
        steps_by_id[item.step_id].step_order = item.step_order
    db.commit()
    seq = _get_sequence_or_404(db, sequence_id)
    return _sequence_to_response(db, seq)


# ---------------------------------------------------------------------------
# Enrollments
# ---------------------------------------------------------------------------
@router.get("/enrollments", response_model=EnrollmentListResponse)
def list_enrollments(
    sequence_id: Optional[int] = Query(None),
    contact_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(AutomationEnrollment).options(
        joinedload(AutomationEnrollment.sequence),
        joinedload(AutomationEnrollment.contact),
    )
    if sequence_id is not None:
        query = query.filter(AutomationEnrollment.sequence_id == sequence_id)
    if contact_id is not None:
        query = query.filter(AutomationEnrollment.contact_id == contact_id)
    if status:
        query = query.filter(AutomationEnrollment.status == status)

    total = query.count()
    rows = (
        query.order_by(AutomationEnrollment.id.desc()).limit(limit).all()
    )
    return EnrollmentListResponse(
        items=[_enrollment_to_response(r) for r in rows],
        total=total,
    )


@router.post(
    "/enroll", response_model=EnrollmentResponse, status_code=201
)
def manual_enroll(
    data: EnrollmentManualCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = automation_service.enroll_contact(
        db, data.contact_id, data.sequence_id
    )
    if result.enrollment is None:
        raise HTTPException(status_code=400, detail=result.reason or "enrollment blocked")
    return _enrollment_to_response(result.enrollment)


@router.put(
    "/enrollments/{enrollment_id}/stop",
    response_model=EnrollmentResponse,
)
def stop_enrollment_endpoint(
    enrollment_id: int,
    data: EnrollmentStopRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    _ = _get_enrollment_or_404(db, enrollment_id)
    updated = automation_service.stop_enrollment(
        db, enrollment_id, "manual", data.reason or "stopped via API"
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    return _enrollment_to_response(updated)


# ---------------------------------------------------------------------------
# Dashboard + logs
# ---------------------------------------------------------------------------
@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    active_sequences = (
        db.query(func.count(AutomationSequence.id))
        .filter(AutomationSequence.is_active.is_(True))
        .scalar()
        or 0
    )
    paused_sequences = (
        db.query(func.count(AutomationSequence.id))
        .filter(AutomationSequence.is_active.is_(False))
        .scalar()
        or 0
    )
    contacts_in_sequences = (
        db.query(func.count(func.distinct(AutomationEnrollment.contact_id)))
        .filter(AutomationEnrollment.status == "active")
        .scalar()
        or 0
    )
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=7)
    messages_sent_7d = (
        db.query(func.count(AutomationLog.id))
        .filter(
            AutomationLog.status == "sent",
            AutomationLog.created_at >= cutoff,
        )
        .scalar()
        or 0
    )
    messages_pending = (
        db.query(func.count(AutomationEnrollment.id))
        .filter(
            AutomationEnrollment.status == "active",
            AutomationEnrollment.next_step_at.isnot(None),
        )
        .scalar()
        or 0
    )

    recent_logs = (
        db.query(AutomationLog)
        .options(
            joinedload(AutomationLog.enrollment).joinedload(
                AutomationEnrollment.sequence
            ),
            joinedload(AutomationLog.enrollment).joinedload(
                AutomationEnrollment.contact
            ),
        )
        .order_by(AutomationLog.id.desc())
        .limit(5)
        .all()
    )
    activity: List[DashboardActivityItem] = []
    for log in recent_logs:
        enrollment = log.enrollment
        activity.append(
            DashboardActivityItem(
                log_id=log.id,
                timestamp=log.created_at,
                contact_id=(enrollment.contact_id if enrollment else None),
                contact_name=(
                    enrollment.contact.name
                    if enrollment and enrollment.contact
                    else None
                ),
                sequence_id=(enrollment.sequence_id if enrollment else None),
                sequence_name=(
                    enrollment.sequence.name
                    if enrollment and enrollment.sequence
                    else None
                ),
                channel=log.channel,
                status=log.status,
            )
        )

    return DashboardResponse(
        active_sequences=active_sequences,
        paused_sequences=paused_sequences,
        contacts_in_sequences=contacts_in_sequences,
        messages_sent_7d=messages_sent_7d,
        messages_pending=messages_pending,
        recent_activity=activity,
    )


@router.get("/logs", response_model=AutomationLogListResponse)
def list_logs(
    sequence_id: Optional[int] = Query(None),
    contact_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(AutomationLog).options(
        joinedload(AutomationLog.enrollment).joinedload(
            AutomationEnrollment.sequence
        ),
        joinedload(AutomationLog.enrollment).joinedload(
            AutomationEnrollment.contact
        ),
    )
    if sequence_id is not None:
        query = query.join(AutomationEnrollment).filter(
            AutomationEnrollment.sequence_id == sequence_id
        )
    if contact_id is not None:
        query = query.join(
            AutomationEnrollment,
            AutomationLog.enrollment_id == AutomationEnrollment.id,
            isouter=False,
        ).filter(AutomationEnrollment.contact_id == contact_id)
    if status:
        query = query.filter(AutomationLog.status == status)

    total = query.count()
    rows = query.order_by(AutomationLog.id.desc()).limit(limit).all()
    return AutomationLogListResponse(
        items=[_log_to_response(r) for r in rows],
        total=total,
    )


# ---------------------------------------------------------------------------
# Contact-scoped endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/contacts/{contact_id}",
    response_model=EnrollmentListResponse,
)
def list_contact_enrollments(
    contact_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    rows = (
        db.query(AutomationEnrollment)
        .options(
            joinedload(AutomationEnrollment.sequence),
            joinedload(AutomationEnrollment.contact),
        )
        .filter(AutomationEnrollment.contact_id == contact_id)
        .order_by(AutomationEnrollment.id.desc())
        .all()
    )
    return EnrollmentListResponse(
        items=[_enrollment_to_response(r) for r in rows],
        total=len(rows),
    )


@router.put(
    "/contacts/{contact_id}/toggle",
    response_model=ContactToggleResponse,
)
def toggle_contact_automations(
    contact_id: int,
    data: ContactToggleRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.automations_enabled = data.automations_enabled
    db.commit()
    db.refresh(contact)
    return ContactToggleResponse(
        contact_id=contact.id,
        automations_enabled=contact.automations_enabled,
    )
