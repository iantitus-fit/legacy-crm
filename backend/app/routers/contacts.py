from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.change_order import ChangeOrder
from app.models.contact import Contact
from app.models.pipeline import Pipeline
from app.models.document import Document
from app.models.estimate import Estimate
from app.models.estimate_status_history import EstimateStatusHistory
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.note import Note
from app.models.payment import Payment
from app.models.task import Task
from app.models.user import User
from app.routers.tasks import _task_to_response
from app.schemas.activity import ActivityEvent
from app.schemas.contact import (
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactSearchResult,
    ContactUpdate,
)
from app.schemas.document import DocumentListResponse
from app.schemas.task import TaskResponse
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("", response_model=ContactListResponse)
def list_contacts(
    search: Optional[str] = Query(
        None, description="Search by name, email, phone, city"
    ),
    import_id: Optional[str] = Query(
        None, description="Filter to contacts created by a specific import"
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Contact).filter(Contact.deleted_at.is_(None))

    if import_id:
        query = query.filter(Contact.import_id == import_id)

    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            or_(
                Contact.name.ilike(search_filter),
                Contact.email.ilike(search_filter),
                Contact.phone.ilike(search_filter),
                Contact.city.ilike(search_filter),
            )
        )

    total = query.count()
    contacts = (
        query.order_by(Contact.name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return ContactListResponse(
        items=contacts, total=total, page=page, per_page=per_page
    )


@router.get("/search", response_model=List[ContactSearchResult])
def search_contacts(
    q: str = Query("", description="Search query (min 2 chars)"),
    limit: int = Query(8, ge=1, le=15),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(q) < 2:
        return []

    search_filter = f"%{q}%"
    contacts = (
        db.query(Contact)
        .filter(
            Contact.deleted_at.is_(None),
            or_(
                Contact.name.ilike(search_filter),
                Contact.email.ilike(search_filter),
                Contact.phone.ilike(search_filter),
                Contact.company.ilike(search_filter),
                Contact.address.ilike(search_filter),
            ),
        )
        .order_by(Contact.name)
        .limit(limit)
        .all()
    )
    return contacts


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.deleted_at.is_(None))
        .first()
    )
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


@router.get("/{contact_id}/tasks", response_model=List[TaskResponse])
def list_contact_tasks(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Tasks related to a client: directly linked, plus tasks on the
    client's estimates and legacy jobs."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    job_ids = [
        jid for (jid,) in db.query(Job.id).filter(Job.contact_id == contact_id).all()
    ]
    estimate_ids: List[int] = []
    if job_ids:
        estimate_ids = [
            eid
            for (eid,) in db.query(Estimate.id)
            .filter(Estimate.job_id.in_(job_ids))
            .all()
        ]

    conditions = [
        and_(
            Task.related_entity_type == "contact",
            Task.related_entity_id == contact_id,
        )
    ]
    if estimate_ids:
        conditions.append(
            and_(
                Task.related_entity_type == "estimate",
                Task.related_entity_id.in_(estimate_ids),
            )
        )
    if job_ids:
        conditions.append(
            and_(
                Task.related_entity_type == "job",
                Task.related_entity_id.in_(job_ids),
            )
        )
        conditions.append(Task.job_id.in_(job_ids))

    tasks = (
        db.query(Task)
        .options(
            joinedload(Task.job).joinedload(Job.contact),
            joinedload(Task.assigned_to),
        )
        .filter(or_(*conditions))
        .order_by(Task.due_date.asc().nullslast(), Task.created_at.desc())
        .all()
    )

    seen = set()
    unique: List[Task] = []
    for t in tasks:
        if t.id not in seen:
            seen.add(t.id)
            unique.append(t)

    return [_task_to_response(t, db) for t in unique]


@router.get("/{contact_id}/documents", response_model=DocumentListResponse)
def list_contact_documents(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Documents for a client: directly linked plus those linked through
    the contact's legacy jobs (dual lookup from migration 0021)."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    items = (
        db.query(Document)
        .outerjoin(Job, Document.job_id == Job.id)
        .filter(
            or_(
                Document.contact_id == contact_id,
                Job.contact_id == contact_id,
            )
        )
        .order_by(Document.created_at.desc())
        .all()
    )

    seen = set()
    unique: List[Document] = []
    for d in items:
        if d.id not in seen:
            seen.add(d.id)
            unique.append(d)

    return DocumentListResponse(items=unique, total=len(unique))


def _est_label(estimate: Estimate) -> str:
    base = f"EST-{estimate.id:04d}"
    if estimate.name:
        return f"{base} — {estimate.name}"
    return base


@router.get("/{contact_id}/activity", response_model=List[ActivityEvent])
def list_contact_activity(
    contact_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregated event timeline for a client. Read-only — queries
    existing timestamps from estimates, change orders, invoices,
    payments, notes, and tasks. No activity_log table involved."""
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    job_ids = [
        jid for (jid,) in db.query(Job.id).filter(Job.contact_id == contact_id).all()
    ]
    estimates = (
        db.query(Estimate).filter(Estimate.job_id.in_(job_ids)).all()
        if job_ids
        else []
    )
    estimate_ids = [e.id for e in estimates]
    estimate_label = {e.id: _est_label(e) for e in estimates}

    events: List[dict] = []

    # Estimates: created + (if approved) approved event
    for est in estimates:
        if est.created_at:
            events.append(
                {
                    "type": "estimate_created",
                    "description": f"Estimate {estimate_label[est.id]} created",
                    "entity_type": "estimate",
                    "entity_id": est.id,
                    "timestamp": est.created_at,
                    "actor": None,
                }
            )
        if est.approved_at:
            events.append(
                {
                    "type": "estimate_approved",
                    "description": f"Estimate {estimate_label[est.id]} approved",
                    "entity_type": "estimate",
                    "entity_id": est.id,
                    "timestamp": est.approved_at,
                    "actor": est.approved_by,
                }
            )

    # Estimate status history (sent, viewed, rejected, changes_requested)
    if estimate_ids:
        history_rows = (
            db.query(EstimateStatusHistory)
            .filter(EstimateStatusHistory.estimate_id.in_(estimate_ids))
            .all()
        )
        for h in history_rows:
            label = estimate_label.get(h.estimate_id, f"EST-{h.estimate_id:04d}")
            events.append(
                {
                    "type": f"estimate_{h.status}",
                    "description": f"Estimate {label} {h.status.replace('_', ' ')}",
                    "entity_type": "estimate",
                    "entity_id": h.estimate_id,
                    "timestamp": h.changed_at,
                    "actor": h.changed_by_name,
                }
            )

    # Change orders
    if estimate_ids:
        change_orders = (
            db.query(ChangeOrder)
            .filter(ChangeOrder.estimate_id.in_(estimate_ids))
            .all()
        )
        for co in change_orders:
            label = estimate_label.get(co.estimate_id, f"EST-{co.estimate_id:04d}")
            events.append(
                {
                    "type": "change_order_created",
                    "description": f"Change Order #{co.co_number} created on {label}",
                    "entity_type": "change_order",
                    "entity_id": co.id,
                    "timestamp": co.created_at,
                    "actor": None,
                }
            )

    # Invoices + payments
    invoice_ids: List[int] = []
    invoice_number_by_id: dict = {}
    if estimate_ids:
        invoices = (
            db.query(Invoice).filter(Invoice.estimate_id.in_(estimate_ids)).all()
        )
        for inv in invoices:
            invoice_ids.append(inv.id)
            invoice_number_by_id[inv.id] = inv.invoice_number
            events.append(
                {
                    "type": "invoice_created",
                    "description": f"Invoice {inv.invoice_number} created",
                    "entity_type": "invoice",
                    "entity_id": inv.id,
                    "timestamp": inv.created_at,
                    "actor": None,
                }
            )

    if invoice_ids:
        payments = (
            db.query(Payment).filter(Payment.invoice_id.in_(invoice_ids)).all()
        )
        for p in payments:
            inv_num = invoice_number_by_id.get(p.invoice_id, f"#{p.invoice_id}")
            events.append(
                {
                    "type": "payment_received",
                    "description": f"Payment of ${p.amount:,.2f} received on {inv_num}",
                    "entity_type": "invoice",
                    "entity_id": p.invoice_id,
                    "timestamp": p.created_at,
                    "actor": None,
                }
            )

    # Notes — match contact, this contact's estimates, and legacy jobs
    note_filters = [
        and_(Note.entity_type == "contact", Note.entity_id == contact_id)
    ]
    if estimate_ids:
        note_filters.append(
            and_(Note.entity_type == "estimate", Note.entity_id.in_(estimate_ids))
        )
    if job_ids:
        note_filters.append(
            and_(Note.entity_type == "job", Note.entity_id.in_(job_ids))
        )
    for n in db.query(Note).filter(or_(*note_filters)).all():
        events.append(
            {
                "type": "note_added",
                "description": f"Note added ({n.note_type})",
                "entity_type": n.entity_type,
                "entity_id": n.entity_id,
                "timestamp": n.created_at,
                "actor": None,
            }
        )

    # Tasks — same matching logic as the tasks endpoint, abbreviated
    task_filters = [
        and_(
            Task.related_entity_type == "contact",
            Task.related_entity_id == contact_id,
        )
    ]
    if estimate_ids:
        task_filters.append(
            and_(
                Task.related_entity_type == "estimate",
                Task.related_entity_id.in_(estimate_ids),
            )
        )
    if job_ids:
        task_filters.append(
            and_(
                Task.related_entity_type == "job",
                Task.related_entity_id.in_(job_ids),
            )
        )
        task_filters.append(Task.job_id.in_(job_ids))
    seen_task_ids = set()
    for t in db.query(Task).filter(or_(*task_filters)).all():
        if t.id in seen_task_ids:
            continue
        seen_task_ids.add(t.id)
        events.append(
            {
                "type": "task_created",
                "description": f"Task: {t.title}",
                "entity_type": "task",
                "entity_id": t.id,
                "timestamp": t.created_at,
                "actor": None,
            }
        )

    events = [e for e in events if e["timestamp"] is not None]
    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:limit]


def _auto_respond_new_lead_task(contact_id: int) -> None:
    """Background task wrapper — opens its own DB session so the request
    session can close. Errors are logged, never re-raised."""
    import logging

    from app.database import SessionLocal
    from app.services.sms_service import auto_respond_new_lead

    log = logging.getLogger("legacy_crm.sms")
    db = SessionLocal()
    try:
        auto_respond_new_lead(db, contact_id)
    except Exception:  # pragma: no cover
        log.exception("auto_respond_new_lead failed for contact %s", contact_id)
    finally:
        db.close()


def _on_contact_created_task(contact_id: int) -> None:
    """Sprint 19b — enroll a freshly-created contact in any contact_created
    automations. Background-task wrapper with its own DB session."""
    import logging

    from app.database import SessionLocal
    from app.services.automation_service import on_contact_created

    log = logging.getLogger("legacy_crm.automation")
    db = SessionLocal()
    try:
        on_contact_created(db, contact_id)
    except Exception:  # pragma: no cover
        log.exception("on_contact_created failed for contact %s", contact_id)
    finally:
        db.close()


@router.post("", response_model=ContactResponse, status_code=201)
def create_contact(
    contact_data: ContactCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = Contact(**contact_data.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)

    # Sprint 16b — fire lead_created when the new contact lands in Leads
    in_leads_pipeline = False
    if contact.pipeline_id:
        leads_pipeline = (
            db.query(Pipeline.id).filter(Pipeline.slug == "leads").scalar()
        )
        if leads_pipeline and contact.pipeline_id == leads_pipeline:
            in_leads_pipeline = True
            from app.services.ai_events import safe_dispatch

            safe_dispatch(
                db=db,
                event_type="lead_created",
                contact_id=contact.id,
                user_id=current_user.id,
            )

    # Sprint 17a — fire SMS auto-response for new leads (fire-and-forget)
    if in_leads_pipeline:
        background_tasks.add_task(_auto_respond_new_lead_task, contact.id)

    # Sprint 19b — enroll in any contact_created automation sequences
    background_tasks.add_task(_on_contact_created_task, contact.id)

    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    contact_data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    update_data = contact_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=204)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    job_count = db.query(Job).filter(Job.contact_id == contact_id).count()
    if job_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete contact with {job_count} associated job(s). "
            "Remove or reassign jobs first.",
        )

    db.delete(contact)
    db.commit()
