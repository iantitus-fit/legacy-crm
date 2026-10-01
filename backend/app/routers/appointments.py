from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentListResponse,
    AppointmentResponse,
    AppointmentUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/appointments", tags=["appointments"])

VALID_TYPES = {"quote", "follow_up", "inspection", "meeting", "other"}


def _appt_to_response(appt: Appointment) -> dict:
    return {
        "id": appt.id,
        "title": appt.title,
        "contact_id": appt.contact_id,
        "assigned_to_user_id": appt.assigned_to_user_id,
        "appointment_date": appt.appointment_date,
        "appointment_time": appt.appointment_time,
        "duration_minutes": appt.duration_minutes,
        "location": appt.location,
        "notes": appt.notes,
        "appointment_type": appt.appointment_type,
        "created_by_user_id": appt.created_by_user_id,
        "created_at": appt.created_at,
        "updated_at": appt.updated_at,
        "contact_name": appt.contact.name if appt.contact else None,
        "assigned_to_name": appt.assigned_to.full_name if appt.assigned_to else None,
        "assigned_to_color": appt.assigned_to.color if appt.assigned_to else None,
        "created_by_name": appt.created_by.full_name if appt.created_by else None,
    }


def _appt_query_options():
    return [
        joinedload(Appointment.contact),
        joinedload(Appointment.assigned_to),
        joinedload(Appointment.created_by),
    ]


@router.get("", response_model=AppointmentListResponse)
def list_appointments(
    assigned_to_user_id: Optional[int] = Query(None),
    appointment_type: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Appointment).options(*_appt_query_options())
    count_query = db.query(Appointment)

    if assigned_to_user_id is not None:
        query = query.filter(Appointment.assigned_to_user_id == assigned_to_user_id)
        count_query = count_query.filter(Appointment.assigned_to_user_id == assigned_to_user_id)
    if appointment_type is not None:
        query = query.filter(Appointment.appointment_type == appointment_type)
        count_query = count_query.filter(Appointment.appointment_type == appointment_type)
    if start_date is not None:
        query = query.filter(Appointment.appointment_date >= start_date)
        count_query = count_query.filter(Appointment.appointment_date >= start_date)
    if end_date is not None:
        query = query.filter(Appointment.appointment_date <= end_date)
        count_query = count_query.filter(Appointment.appointment_date <= end_date)

    total = count_query.count()
    items = (
        query.order_by(Appointment.appointment_date.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return AppointmentListResponse(
        items=[_appt_to_response(a) for a in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{appt_id}", response_model=AppointmentResponse)
def get_appointment(
    appt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = (
        db.query(Appointment)
        .options(*_appt_query_options())
        .filter(Appointment.id == appt_id)
        .first()
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return _appt_to_response(appt)


@router.post("", response_model=AppointmentResponse, status_code=201)
def create_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.contact_id is not None:
        contact = db.query(Contact).filter(Contact.id == data.contact_id).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact not found")

    user = db.query(User).filter(User.id == data.assigned_to_user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Assigned user not found")

    appt = Appointment(
        **data.model_dump(),
        created_by_user_id=current_user.id,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    appt = (
        db.query(Appointment)
        .options(*_appt_query_options())
        .filter(Appointment.id == appt.id)
        .first()
    )
    return _appt_to_response(appt)


@router.put("/{appt_id}", response_model=AppointmentResponse)
def update_appointment(
    appt_id: int,
    data: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    update_data = data.model_dump(exclude_unset=True)

    if "contact_id" in update_data and update_data["contact_id"] is not None:
        contact = db.query(Contact).filter(Contact.id == update_data["contact_id"]).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact not found")

    if "assigned_to_user_id" in update_data and update_data["assigned_to_user_id"] is not None:
        user = db.query(User).filter(User.id == update_data["assigned_to_user_id"]).first()
        if not user:
            raise HTTPException(status_code=400, detail="Assigned user not found")

    for field, value in update_data.items():
        setattr(appt, field, value)

    db.commit()
    db.refresh(appt)

    appt = (
        db.query(Appointment)
        .options(*_appt_query_options())
        .filter(Appointment.id == appt.id)
        .first()
    )
    return _appt_to_response(appt)


@router.delete("/{appt_id}", status_code=204)
def delete_appointment(
    appt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    db.delete(appt)
    db.commit()
