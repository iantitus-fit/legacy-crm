from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.crew import Crew
from app.models.estimate import Estimate
from app.models.job import Job
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.schemas.calendar import (
    CalendarAppointmentEvent,
    CalendarAppointmentsResponse,
    CalendarJobEvent,
    CalendarJobsResponse,
    UpcomingItem,
    UpcomingResponse,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

# Sprint 15d — estimates replace jobs as the calendar's scheduled entity.
# A "job" on the calendar is an approved-and-beyond estimate with a
# scheduled_start set.
JOB_PHASE_STATUSES = ("approved", "in_progress", "complete", "closed")


@router.get("/jobs", response_model=CalendarJobsResponse)
def get_calendar_jobs(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    crew_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approved estimates with scheduled_start in range.

    Response shape is unchanged (still CalendarJobEvent) but fields are
    populated from Estimate: id = estimate.id, display_name = estimate.name,
    scheduled_date = estimate.scheduled_start, etc. The endpoint path
    stays /api/calendar/jobs for backward compatibility — "job" is just
    an approved estimate in the new model.
    """
    query = (
        db.query(Estimate)
        .options(
            joinedload(Estimate.job).joinedload(Job.contact),
            joinedload(Estimate.crew),
        )
        .filter(
            Estimate.scheduled_start.isnot(None),
            Estimate.status.in_(JOB_PHASE_STATUSES),
        )
    )

    if start_date is not None:
        # Include estimates that end after start_date or start after start_date
        query = query.filter(
            (Estimate.scheduled_end >= start_date)
            | (Estimate.scheduled_start >= start_date)
        )
    if end_date is not None:
        query = query.filter(Estimate.scheduled_start <= end_date)
    if crew_id is not None:
        query = query.filter(Estimate.crew_id == crew_id)

    estimates = query.order_by(Estimate.scheduled_start.asc()).all()

    return CalendarJobsResponse(
        items=[
            CalendarJobEvent(
                id=e.id,
                display_name=e.name or (e.job.display_name if e.job else None),
                contact_name=(
                    e.job.contact.name if e.job and e.job.contact else None
                ),
                property_address=(
                    e.location_address
                    or (e.job.property_address if e.job else None)
                ),
                scheduled_date=e.scheduled_start,
                scheduled_end_date=e.scheduled_end,
                crew_id=e.crew_id,
                crew_name=e.crew.name if e.crew else None,
                crew_color=e.crew.color if e.crew else None,
                stage_name=(e.status or "").replace("_", " ").title(),
                work_type=e.work_type,
                contract_value=e.total,
            )
            for e in estimates
        ]
    )


@router.get("/appointments", response_model=CalendarAppointmentsResponse)
def get_calendar_appointments(
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    assigned_to_user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.contact),
            joinedload(Appointment.assigned_to),
        )
    )

    if start_date is not None:
        query = query.filter(Appointment.appointment_date >= start_date)
    if end_date is not None:
        query = query.filter(Appointment.appointment_date <= end_date)
    if assigned_to_user_id is not None:
        query = query.filter(Appointment.assigned_to_user_id == assigned_to_user_id)

    appts = query.order_by(Appointment.appointment_date.asc()).all()

    return CalendarAppointmentsResponse(
        items=[
            CalendarAppointmentEvent(
                id=a.id,
                title=a.title,
                contact_id=a.contact_id,
                contact_name=a.contact.name if a.contact else None,
                assigned_to_user_id=a.assigned_to_user_id,
                assigned_to_name=a.assigned_to.full_name if a.assigned_to else None,
                assigned_to_color=a.assigned_to.color if a.assigned_to else None,
                appointment_date=a.appointment_date,
                appointment_time=a.appointment_time,
                duration_minutes=a.duration_minutes,
                location=a.location,
                appointment_type=a.appointment_type,
            )
            for a in appts
        ]
    )


@router.get("/upcoming", response_model=UpcomingResponse)
def get_upcoming(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Next N upcoming items (jobs + appointments merged, sorted by date)."""
    today = date.today()
    items = []

    # Sprint 15d — upcoming scheduled estimates (a "job" is an approved estimate)
    estimates = (
        db.query(Estimate)
        .options(
            joinedload(Estimate.job).joinedload(Job.contact),
            joinedload(Estimate.crew),
        )
        .filter(
            Estimate.scheduled_start >= today,
            Estimate.scheduled_start.isnot(None),
            Estimate.status.in_(JOB_PHASE_STATUSES),
        )
        .order_by(Estimate.scheduled_start.asc())
        .limit(limit)
        .all()
    )
    for e in estimates:
        title = (
            e.name
            or e.location_address
            or (e.job.property_address if e.job else None)
            or f"Estimate #{e.id}"
        )
        items.append(
            UpcomingItem(
                id=e.id,
                item_type="job",
                title=title,
                date=e.scheduled_start,
                time=None,
                color=e.crew.color if e.crew else None,
                link=f"/estimates/{e.id}",
            )
        )

    # Upcoming appointments
    appts = (
        db.query(Appointment)
        .options(joinedload(Appointment.assigned_to))
        .filter(Appointment.appointment_date >= today)
        .order_by(Appointment.appointment_date.asc())
        .limit(limit)
        .all()
    )
    for a in appts:
        items.append(
            UpcomingItem(
                id=a.id,
                item_type="appointment",
                title=a.title,
                date=a.appointment_date,
                time=a.appointment_time,
                color=a.assigned_to.color if a.assigned_to else None,
                link=f"/calendars/appointments",
            )
        )

    # Sort merged list by date, then time
    items.sort(key=lambda x: (x.date, x.time or __import__("datetime").time(23, 59)))

    return UpcomingResponse(items=items[:limit])
