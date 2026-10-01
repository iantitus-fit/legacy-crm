from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.contact import Contact
from app.models.job import Job
from app.models.lead import Lead
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.schemas.lead import (
    LeadConvertRequest,
    LeadConvertResponse,
    LeadCreate,
    LeadListResponse,
    LeadResponse,
    LeadUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/leads", tags=["leads"])


def _lead_to_response(lead: Lead) -> dict:
    """Build a LeadResponse dict with nested contact info."""
    return {
        "id": lead.id,
        "contact_id": lead.contact_id,
        "stage_id": lead.stage_id,
        "source": lead.source,
        "description": lead.description,
        "assigned_to_user_id": lead.assigned_to_user_id,
        "created_at": lead.created_at,
        "contact_name": lead.contact.name if lead.contact else None,
        "contact_phone": lead.contact.phone if lead.contact else None,
        "contact_email": lead.contact.email if lead.contact else None,
    }


@router.get("", response_model=LeadListResponse)
def list_leads(
    search: Optional[str] = Query(None, description="Search by contact name or source"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Lead).options(joinedload(Lead.contact))

    if search:
        search_filter = f"%{search}%"
        query = query.join(Lead.contact, isouter=True).filter(
            or_(
                Contact.name.ilike(search_filter),
                Lead.source.ilike(search_filter),
            )
        )

    total = query.count()
    leads = (
        query.order_by(Lead.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return LeadListResponse(
        items=[_lead_to_response(lead) for lead in leads],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = (
        db.query(Lead)
        .options(joinedload(Lead.contact))
        .filter(Lead.id == lead_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _lead_to_response(lead)


@router.post("", response_model=LeadResponse, status_code=201)
def create_lead(
    lead_data: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact_id = lead_data.contact_id

    if contact_id is not None:
        # Link to existing contact
        contact = db.query(Contact).filter(Contact.id == contact_id).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact not found")
    elif lead_data.contact_name:
        # Create a new contact from inline info
        contact = Contact(
            name=lead_data.contact_name,
            phone=lead_data.contact_phone,
            email=lead_data.contact_email,
        )
        db.add(contact)
        db.flush()
        contact_id = contact.id
    else:
        raise HTTPException(
            status_code=400,
            detail="Either contact_id or contact_name is required",
        )

    # Default stage to first stage of the Leads pipeline
    first_stage = None
    leads_pipeline = db.query(Pipeline).filter(Pipeline.slug == "leads").first()
    if leads_pipeline:
        first_stage = (
            db.query(PipelineStage)
            .filter(PipelineStage.pipeline_id == leads_pipeline.id)
            .order_by(PipelineStage.sort_order)
            .first()
        )

    lead = Lead(
        contact_id=contact_id,
        stage_id=first_stage.id if first_stage else None,
        source=lead_data.source,
        description=lead_data.description,
        assigned_to_user_id=lead_data.assigned_to_user_id,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)

    # Reload with relationships
    lead = (
        db.query(Lead)
        .options(joinedload(Lead.contact))
        .filter(Lead.id == lead.id)
        .first()
    )
    return _lead_to_response(lead)


@router.put("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    lead_data: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    update_data = lead_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lead, field, value)

    db.commit()
    db.refresh(lead)

    lead = (
        db.query(Lead)
        .options(joinedload(Lead.contact))
        .filter(Lead.id == lead.id)
        .first()
    )
    return _lead_to_response(lead)


@router.delete("/{lead_id}", status_code=204)
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()


@router.post("/{lead_id}/convert", response_model=LeadConvertResponse)
def convert_lead(
    lead_id: int,
    convert_data: LeadConvertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Convert a lead into a job. Deletes the lead after conversion."""
    lead = (
        db.query(Lead)
        .options(joinedload(Lead.contact))
        .filter(Lead.id == lead_id)
        .first()
    )
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    if not lead.contact_id:
        raise HTTPException(status_code=400, detail="Lead has no associated contact")

    contact = lead.contact

    # Default to Sales pipeline first stage
    stage_id = convert_data.stage_id
    sales_pipeline = db.query(Pipeline).filter(Pipeline.slug == "sales").first()
    pipeline_id = sales_pipeline.id if sales_pipeline else None

    if not stage_id and sales_pipeline:
        first_stage = (
            db.query(PipelineStage)
            .filter(PipelineStage.pipeline_id == sales_pipeline.id)
            .order_by(PipelineStage.sort_order)
            .first()
        )
        if first_stage:
            stage_id = first_stage.id

    # Build notes from lead source + description
    notes_parts = []
    if lead.source:
        notes_parts.append(f"Lead source: {lead.source}")
    if lead.description:
        notes_parts.append(lead.description)
    notes = "\n".join(notes_parts) or None

    # Determine property address
    property_address = convert_data.property_address
    if not property_address and contact.address:
        parts = [contact.address]
        if contact.city:
            parts.append(contact.city)
        if contact.state:
            parts.append(contact.state)
        if contact.zip:
            parts.append(contact.zip)
        property_address = ", ".join(parts)

    # Create job in Sales pipeline
    job = Job(
        pipeline_id=pipeline_id,
        contact_id=contact.id,
        stage_id=stage_id,
        job_type=convert_data.job_type,
        work_type=convert_data.work_type,
        property_address=property_address,
        notes=notes,
        assigned_to_user_id=lead.assigned_to_user_id,
        lead_source=lead.source,
    )
    db.add(job)

    # Delete the lead
    db.delete(lead)
    db.commit()
    db.refresh(job)

    return LeadConvertResponse(job_id=job.id, contact_id=contact.id)
