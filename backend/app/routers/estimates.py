from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from sqlalchemy import or_

from app.database import get_db
from app.models.change_order import ChangeOrder
from app.models.change_order_item import ChangeOrderItem
from app.models.change_order_signature import ChangeOrderSignature
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.estimate_status_history import EstimateStatusHistory
from app.models.invoice import Invoice
from app.models.estimate_line_item import EstimateLineItem
from app.models.estimate_section import EstimateSection
from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.schemas.estimate import (
    EstimateCreate,
    EstimateLineItemCreate,
    EstimateLineItemResponse,
    EstimateLineItemUpdate,
    EstimateListResponse,
    EstimateResponse,
    EstimateSectionCreate,
    EstimateSectionResponse,
    EstimateSectionUpdate,
    EstimateUpdate,
    LineItemReorder,
    SectionReorder,
)
from app.schemas.estimate_template import ApplyTemplateRequest
from app.services.estimate_calculator import (
    calculate_line_total,
    recalculate_estimate,
)
from app.services.estimate_approval import approve_estimate
from app.services.template_calculator import calculate_template_preview
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/estimates", tags=["estimates"])


def _estimate_to_response(estimate: Estimate, db: Optional[Session] = None) -> dict:
    """Build an EstimateResponse dict with computed fields."""
    line_items = sorted(
        estimate.line_items, key=lambda li: li.sort_order or 0
    )
    job_address = None
    contact_id = None
    contact_name = None
    contact_email = None
    contact_phone = None
    contact_company = None
    contact_address = None
    if estimate.job:
        job_address = estimate.job.property_address
        if estimate.job.contact:
            contact = estimate.job.contact
            contact_id = contact.id
            contact_name = contact.name
            contact_email = contact.email
            contact_phone = contact.phone
            contact_company = contact.company
            contact_address = contact.address

    created_by_user_name = None
    if estimate.created_by_user_id and getattr(estimate, "created_by", None):
        created_by_user_name = estimate.created_by.full_name

    # Sprint 15a — crew and assignee display fields
    crew_name = None
    crew_color = None
    if estimate.crew_id and getattr(estimate, "crew", None):
        crew_name = estimate.crew.name
        crew_color = estimate.crew.color
    assigned_to_name = None
    if estimate.assigned_to_user_id and getattr(estimate, "assigned_to", None):
        assigned_to_name = estimate.assigned_to.full_name

    # Build sections with sorted items and computed subtotals
    sections = []
    for section in sorted(estimate.sections, key=lambda s: s.sort_order or 0):
        section_items = sorted(
            [li for li in estimate.line_items if li.section_id == section.id],
            key=lambda li: li.sort_order or 0,
        )
        section_subtotal = sum(
            (li.line_total or Decimal("0")) for li in section_items
        )
        sections.append({
            "id": section.id,
            "estimate_id": section.estimate_id,
            "name": section.name,
            "description": section.description,
            "sort_order": section.sort_order,
            "created_at": section.created_at,
            "line_items": section_items,
            "subtotal": section_subtotal,
        })

    # Build change orders
    change_orders_list = []
    for co in sorted(getattr(estimate, "change_orders", None) or [], key=lambda c: c.co_number):
        accepted_at = None
        if co.status == "approved" and db:
            sig = (
                db.query(ChangeOrderSignature.signed_at)
                .filter(ChangeOrderSignature.change_order_id == co.id)
                .order_by(ChangeOrderSignature.signed_at.desc())
                .first()
            )
            if sig:
                accepted_at = sig[0]
        change_orders_list.append({
            "id": co.id,
            "estimate_id": co.estimate_id,
            "co_number": co.co_number,
            "name": co.name,
            "status": co.status,
            "subtotal": co.subtotal,
            "tax": co.tax,
            "total": co.total,
            "created_at": co.created_at,
            "accepted_at": accepted_at,
            "items": sorted(co.items, key=lambda i: i.sort_order or 0),
        })

    approved_co_total = sum(
        (Decimal(str(co.total or 0)) for co in (getattr(estimate, "change_orders", None) or []) if co.status == "approved"),
        Decimal("0"),
    )

    return {
        "id": estimate.id,
        "job_id": estimate.job_id,
        "name": estimate.name,
        "tax_rate": estimate.tax_rate,
        "subtotal": estimate.subtotal,
        "tax": estimate.tax,
        "total": estimate.total,
        "show_quantities": estimate.show_quantities,
        "show_unit_prices": estimate.show_unit_prices,
        "show_line_totals": estimate.show_line_totals,
        "show_subtotal": estimate.show_subtotal,
        "tax_included": estimate.tax_included,
        "deposit_percent": estimate.deposit_percent,
        "expiration_date": estimate.expiration_date,
        "created_by_user_id": estimate.created_by_user_id,
        "created_by_user_name": created_by_user_name,
        # Sprint 15a — job-phase fields
        "job_type": estimate.job_type,
        "work_type": estimate.work_type,
        "location_address": estimate.location_address,
        "crew_id": estimate.crew_id,
        "crew_name": crew_name,
        "crew_color": crew_color,
        "scheduled_start": estimate.scheduled_start,
        "scheduled_end": estimate.scheduled_end,
        "assigned_to_user_id": estimate.assigned_to_user_id,
        "assigned_to_name": assigned_to_name,
        "approved_at": estimate.approved_at,
        "approved_by": estimate.approved_by,
        "pipeline_id": estimate.pipeline_id,
        "stage_id": estimate.stage_id,
        "created_at": estimate.created_at,
        "line_items": line_items,
        "sections": sections,
        "change_orders": change_orders_list,
        "grand_total": (Decimal(str(estimate.total or 0))) + approved_co_total,
        "job_address": job_address,
        "contact_id": contact_id,
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "contact_company": contact_company,
        "contact_address": contact_address,
        "status": estimate.status,
        # Invoice.estimate_id has no unique constraint, and prod estimates
        # commonly have deposit + final invoices both referencing the same
        # estimate. Using .scalar() raises MultipleResultsFound when that
        # happens; pick the earliest invoice deterministically instead.
        "invoice_id": (
            (
                db.query(Invoice.id)
                .filter(Invoice.estimate_id == estimate.id)
                .order_by(Invoice.id.asc())
                .first()
                or (None,)
            )[0]
            if db
            else None
        ),
        "scope_of_work": estimate.scope_of_work,
    }


def _load_estimate(db: Session, estimate_id: int) -> Estimate:
    """Load an estimate with all relationships."""
    estimate = (
        db.query(Estimate)
        .options(
            joinedload(Estimate.line_items),
            joinedload(Estimate.sections),
            joinedload(Estimate.job).joinedload(Job.contact),
            joinedload(Estimate.change_orders).joinedload(ChangeOrder.items),
            joinedload(Estimate.created_by),
            joinedload(Estimate.crew),
            joinedload(Estimate.assigned_to),
        )
        .filter(Estimate.id == estimate_id)
        .first()
    )
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")
    return estimate


# --- Estimate CRUD ---


@router.get("", response_model=EstimateListResponse)
def list_estimates(
    job_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(
        None,
        description=(
            "Filter by status. Accepts a single status like 'approved' or "
            "comma-separated list 'approved,in_progress,complete,closed' "
            "for the Jobs List view."
        ),
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Estimate).options(
        joinedload(Estimate.line_items),
        joinedload(Estimate.sections),
        joinedload(Estimate.job).joinedload(Job.contact),
        joinedload(Estimate.change_orders).joinedload(ChangeOrder.items),
        joinedload(Estimate.crew),
        joinedload(Estimate.assigned_to),
    )

    if job_id is not None:
        query = query.filter(Estimate.job_id == job_id)

    if status:
        statuses = [s.strip() for s in status.split(",") if s.strip()]
        if len(statuses) == 1:
            query = query.filter(Estimate.status == statuses[0])
        elif len(statuses) > 1:
            query = query.filter(Estimate.status.in_(statuses))

    if search:
        pattern = f"%{search}%"
        query = query.join(Job, Estimate.job_id == Job.id, isouter=True).join(
            Contact, Job.contact_id == Contact.id, isouter=True
        )
        query = query.filter(
            or_(
                Estimate.name.ilike(pattern),
                Job.property_address.ilike(pattern),
                Contact.name.ilike(pattern),
            )
        )

    # Use the filtered query for count (before offset/limit)
    total = query.count()

    items = (
        query.order_by(Estimate.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return EstimateListResponse(
        items=[_estimate_to_response(e, db) for e in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{estimate_id}", response_model=EstimateResponse)
def get_estimate(
    estimate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = _load_estimate(db, estimate_id)
    return _estimate_to_response(estimate, db)


@router.post("", response_model=EstimateResponse, status_code=201)
def create_estimate(
    data: EstimateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == data.job_id).first()
    if not job:
        raise HTTPException(status_code=400, detail="Job not found")

    estimate = Estimate(
        job_id=data.job_id,
        name=data.name or "",
        tax_rate=data.tax_rate,
        show_quantities=data.show_quantities,
        show_unit_prices=data.show_unit_prices,
        show_line_totals=data.show_line_totals,
        show_subtotal=data.show_subtotal,
        tax_included=data.tax_included,
        deposit_percent=data.deposit_percent,
        expiration_date=data.expiration_date,
        created_by_user_id=current_user.id,
        # Sprint 15a — job-phase fields. Default job_type / work_type /
        # location_address from the parent job so newly created estimates
        # inherit the job's scope until the frontend starts passing them
        # explicitly.
        job_type=data.job_type or job.job_type,
        work_type=data.work_type or job.work_type,
        location_address=data.location_address or job.property_address,
        crew_id=data.crew_id,
        scheduled_start=data.scheduled_start,
        scheduled_end=data.scheduled_end,
        assigned_to_user_id=data.assigned_to_user_id or job.assigned_to_user_id,
        pipeline_id=data.pipeline_id,
        stage_id=data.stage_id,
        subtotal=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("0"),
    )
    db.add(estimate)
    db.flush()

    if data.line_items:
        for idx, li in enumerate(data.line_items):
            line_item = EstimateLineItem(
                estimate_id=estimate.id,
                description=li.description,
                qty=li.qty,
                unit_price=li.unit_price,
                line_total=calculate_line_total(li.qty, li.unit_price),
                body=li.body,
                notes=li.notes,
                sort_order=li.sort_order if li.sort_order is not None else idx,
            )
            db.add(line_item)

    db.commit()
    recalculate_estimate(db, estimate.id)

    estimate = _load_estimate(db, estimate.id)
    return _estimate_to_response(estimate, db)


VALID_ESTIMATE_STATUSES = {
    "draft",
    "sent",
    "viewed",
    "approved",
    "in_progress",
    "complete",
    "closed",
    "rejected",
    "changes_requested",
}


@router.put("/{estimate_id}", response_model=EstimateResponse)
def update_estimate(
    estimate_id: int,
    data: EstimateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    update_data = data.model_dump(exclude_unset=True)

    # Sprint 15d — status transitions
    if "status" in update_data:
        new_status = update_data["status"]
        if new_status not in VALID_ESTIMATE_STATUSES:
            raise HTTPException(
                status_code=400, detail=f"Invalid estimate status '{new_status}'"
            )
        # Going from a non-approved state to 'approved' must use the
        # approve-internal endpoint so approved_at / approved_by /
        # pipeline assignment get recorded correctly. Block the shortcut.
        if new_status == "approved" and estimate.status not in {
            "approved",
            "in_progress",
            "complete",
            "closed",
        }:
            raise HTTPException(
                status_code=400,
                detail="Use POST /estimates/{id}/approve-internal to approve an estimate",
            )
        # Job-phase transitions (approved → in_progress → complete → closed)
        # are only valid from an already-approved/job-phase state.
        if new_status in {"in_progress", "complete", "closed"} and estimate.status not in {
            "approved",
            "in_progress",
            "complete",
            "closed",
        }:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot transition from '{estimate.status}' to '{new_status}'. "
                    "Approve the estimate first."
                ),
            )

    previous_status = estimate.status

    for field, value in update_data.items():
        setattr(estimate, field, value)

    db.commit()

    if "tax_rate" in update_data or "tax_included" in update_data:
        recalculate_estimate(db, estimate_id)

    estimate = _load_estimate(db, estimate_id)

    # Sprint 16b — fire job_completed when transitioning into "complete"
    if (
        update_data.get("status") == "complete"
        and previous_status != "complete"
    ):
        contact_id = None
        try:
            if estimate.job and estimate.job.contact:
                contact_id = estimate.job.contact_id
        except Exception:
            contact_id = None
        from app.services.ai_events import safe_dispatch

        safe_dispatch(
            db=db,
            event_type="job_completed",
            contact_id=contact_id,
            estimate_id=estimate.id,
            user_id=current_user.id,
        )

    return _estimate_to_response(estimate, db)


@router.delete("/{estimate_id}", status_code=204)
def delete_estimate(
    estimate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    db.query(EstimateLineItem).filter(
        EstimateLineItem.estimate_id == estimate_id
    ).delete()
    db.query(EstimateSection).filter(
        EstimateSection.estimate_id == estimate_id
    ).delete()
    db.delete(estimate)
    db.commit()


@router.post("/{estimate_id}/duplicate", response_model=EstimateResponse, status_code=201)
def duplicate_estimate(
    estimate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = _load_estimate(db, estimate_id)

    new_estimate = Estimate(
        job_id=source.job_id,
        name=f"{source.name} (Copy)",
        tax_rate=source.tax_rate,
        show_quantities=source.show_quantities,
        show_unit_prices=source.show_unit_prices,
        show_line_totals=source.show_line_totals,
        show_subtotal=source.show_subtotal,
        tax_included=source.tax_included,
        deposit_percent=source.deposit_percent,
        subtotal=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("0"),
    )
    db.add(new_estimate)
    db.flush()

    # Copy sections and build old->new id mapping
    section_id_map = {}
    for section in sorted(source.sections, key=lambda s: s.sort_order or 0):
        new_section = EstimateSection(
            estimate_id=new_estimate.id,
            name=section.name,
            description=section.description,
            sort_order=section.sort_order,
        )
        db.add(new_section)
        db.flush()
        section_id_map[section.id] = new_section.id

    for item in sorted(source.line_items, key=lambda li: li.sort_order or 0):
        new_item = EstimateLineItem(
            estimate_id=new_estimate.id,
            description=item.description,
            qty=item.qty,
            unit_price=item.unit_price,
            line_total=item.line_total,
            body=item.body,
            notes=item.notes,
            sort_order=item.sort_order,
            section_id=section_id_map.get(item.section_id) if item.section_id else None,
        )
        db.add(new_item)

    db.commit()
    recalculate_estimate(db, new_estimate.id)

    new_estimate = _load_estimate(db, new_estimate.id)
    return _estimate_to_response(new_estimate, db)


@router.post("/{estimate_id}/apply-template", response_model=EstimateResponse)
def apply_template(
    estimate_id: int,
    data: ApplyTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    template = (
        db.query(EstimateTemplate)
        .options(joinedload(EstimateTemplate.items))
        .filter(EstimateTemplate.id == data.template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Build measurements dict
    measurements = {}
    for field in ["total_area", "ridge", "hip", "valley", "eave", "rake"]:
        val = getattr(data.measurements, field)
        if val is not None:
            measurements[field] = val

    # Calculate from template items
    items_data = [
        {
            "description": item.description,
            "category": item.category,
            "unit_cost": item.unit_cost,
            "uom": item.uom,
            "margin_pct": item.margin_pct,
            "waste_pct": item.waste_pct,
            "measurement_type": item.measurement_type,
            "conversion_factor": item.conversion_factor,
            "default_qty": item.default_qty,
        }
        for item in sorted(template.items, key=lambda i: i.sort_order or 0)
    ]
    preview = calculate_template_preview(items_data, measurements)

    # Determine starting sort_order
    max_order = (
        db.query(EstimateLineItem.sort_order)
        .filter(EstimateLineItem.estimate_id == estimate_id)
        .order_by(EstimateLineItem.sort_order.desc())
        .first()
    )
    start_order = (max_order[0] or 0) + 1 if max_order else 0

    # Create line items from preview
    for idx, calc_item in enumerate(preview["items"]):
        line_item = EstimateLineItem(
            estimate_id=estimate_id,
            description=calc_item["description"],
            qty=Decimal(str(calc_item["qty"])),
            unit_price=calc_item["unit_price"],
            line_total=calc_item["line_total"],
            sort_order=start_order + idx,
        )
        db.add(line_item)

    db.commit()
    recalculate_estimate(db, estimate_id)

    estimate = _load_estimate(db, estimate_id)
    return _estimate_to_response(estimate, db)


# --- Section CRUD ---


@router.post(
    "/{estimate_id}/sections",
    response_model=EstimateSectionResponse,
    status_code=201,
)
def create_section(
    estimate_id: int,
    data: EstimateSectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    max_order = (
        db.query(EstimateSection.sort_order)
        .filter(EstimateSection.estimate_id == estimate_id)
        .order_by(EstimateSection.sort_order.desc())
        .first()
    )
    sort_order = (max_order[0] or 0) + 1 if max_order else 0

    section = EstimateSection(
        estimate_id=estimate_id,
        name=data.name,
        description=data.description,
        sort_order=sort_order,
    )
    db.add(section)
    db.commit()
    db.refresh(section)

    return {
        "id": section.id,
        "estimate_id": section.estimate_id,
        "name": section.name,
        "description": section.description,
        "sort_order": section.sort_order,
        "created_at": section.created_at,
        "line_items": [],
        "subtotal": Decimal("0"),
    }


@router.get(
    "/{estimate_id}/sections",
    response_model=List[EstimateSectionResponse],
)
def list_sections(
    estimate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    sections = (
        db.query(EstimateSection)
        .options(joinedload(EstimateSection.line_items))
        .filter(EstimateSection.estimate_id == estimate_id)
        .order_by(EstimateSection.sort_order)
        .all()
    )

    result = []
    for section in sections:
        items = sorted(section.line_items, key=lambda li: li.sort_order or 0)
        subtotal = sum((li.line_total or Decimal("0")) for li in items)
        result.append({
            "id": section.id,
            "estimate_id": section.estimate_id,
            "name": section.name,
            "description": section.description,
            "sort_order": section.sort_order,
            "created_at": section.created_at,
            "line_items": items,
            "subtotal": subtotal,
        })
    return result


@router.put(
    "/{estimate_id}/sections/reorder",
    response_model=List[EstimateSectionResponse],
)
def reorder_sections(
    estimate_id: int,
    data: SectionReorder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    existing_ids = {
        row[0]
        for row in db.query(EstimateSection.id)
        .filter(EstimateSection.estimate_id == estimate_id)
        .all()
    }

    if set(data.section_ids) != existing_ids:
        raise HTTPException(
            status_code=400,
            detail="section_ids must contain exactly all section IDs for this estimate",
        )

    for idx, section_id in enumerate(data.section_ids):
        db.query(EstimateSection).filter(
            EstimateSection.id == section_id
        ).update({"sort_order": idx})

    db.commit()
    return list_sections(estimate_id, db=db, current_user=current_user)


@router.put(
    "/{estimate_id}/sections/{section_id}",
    response_model=EstimateSectionResponse,
)
def update_section(
    estimate_id: int,
    section_id: int,
    data: EstimateSectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    section = (
        db.query(EstimateSection)
        .filter(
            EstimateSection.id == section_id,
            EstimateSection.estimate_id == estimate_id,
        )
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(section, field, value)

    db.commit()
    db.refresh(section)

    items = (
        db.query(EstimateLineItem)
        .filter(EstimateLineItem.section_id == section_id)
        .order_by(EstimateLineItem.sort_order)
        .all()
    )
    subtotal = sum((li.line_total or Decimal("0")) for li in items)

    return {
        "id": section.id,
        "estimate_id": section.estimate_id,
        "name": section.name,
        "description": section.description,
        "sort_order": section.sort_order,
        "created_at": section.created_at,
        "line_items": items,
        "subtotal": subtotal,
    }


@router.delete("/{estimate_id}/sections/{section_id}", status_code=204)
def delete_section(
    estimate_id: int,
    section_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    section = (
        db.query(EstimateSection)
        .filter(
            EstimateSection.id == section_id,
            EstimateSection.estimate_id == estimate_id,
        )
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    # Move items to unsectioned
    db.query(EstimateLineItem).filter(
        EstimateLineItem.section_id == section_id
    ).update({"section_id": None})

    db.delete(section)
    db.commit()


# --- Line Item CRUD ---


@router.put(
    "/{estimate_id}/line-items/reorder",
    response_model=EstimateResponse,
)
def reorder_line_items(
    estimate_id: int,
    data: LineItemReorder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    existing_ids = {
        row[0]
        for row in db.query(EstimateLineItem.id)
        .filter(EstimateLineItem.estimate_id == estimate_id)
        .all()
    }

    if set(data.item_ids) != existing_ids:
        raise HTTPException(
            status_code=400,
            detail="item_ids must contain exactly all line item IDs for this estimate",
        )

    for idx, item_id in enumerate(data.item_ids):
        db.query(EstimateLineItem).filter(
            EstimateLineItem.id == item_id
        ).update({"sort_order": idx})

    db.commit()

    estimate = _load_estimate(db, estimate_id)
    return _estimate_to_response(estimate, db)


@router.post(
    "/{estimate_id}/line-items",
    response_model=EstimateLineItemResponse,
    status_code=201,
)
def add_line_item(
    estimate_id: int,
    data: EstimateLineItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    # Validate section_id belongs to this estimate
    if data.section_id is not None:
        section = (
            db.query(EstimateSection)
            .filter(
                EstimateSection.id == data.section_id,
                EstimateSection.estimate_id == estimate_id,
            )
            .first()
        )
        if not section:
            raise HTTPException(
                status_code=400,
                detail="Section not found for this estimate",
            )

    if data.sort_order is None:
        max_order = (
            db.query(EstimateLineItem.sort_order)
            .filter(EstimateLineItem.estimate_id == estimate_id)
            .order_by(EstimateLineItem.sort_order.desc())
            .first()
        )
        sort_order = (max_order[0] or 0) + 1 if max_order else 0
    else:
        sort_order = data.sort_order

    line_item = EstimateLineItem(
        estimate_id=estimate_id,
        description=data.description,
        qty=data.qty,
        unit_price=data.unit_price,
        line_total=calculate_line_total(data.qty, data.unit_price),
        body=data.body,
        notes=data.notes,
        sort_order=sort_order,
        section_id=data.section_id,
    )
    db.add(line_item)
    db.commit()

    recalculate_estimate(db, estimate_id)
    db.refresh(line_item)
    return line_item


@router.put(
    "/{estimate_id}/line-items/{item_id}",
    response_model=EstimateLineItemResponse,
)
def update_line_item(
    estimate_id: int,
    item_id: int,
    data: EstimateLineItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    line_item = (
        db.query(EstimateLineItem)
        .filter(
            EstimateLineItem.id == item_id,
            EstimateLineItem.estimate_id == estimate_id,
        )
        .first()
    )
    if not line_item:
        raise HTTPException(status_code=404, detail="Line item not found")

    update_data = data.model_dump(exclude_unset=True)

    # Validate section_id if being changed
    if "section_id" in update_data and update_data["section_id"] is not None:
        section = (
            db.query(EstimateSection)
            .filter(
                EstimateSection.id == update_data["section_id"],
                EstimateSection.estimate_id == estimate_id,
            )
            .first()
        )
        if not section:
            raise HTTPException(
                status_code=400,
                detail="Section not found for this estimate",
            )

    for field, value in update_data.items():
        setattr(line_item, field, value)

    db.commit()
    recalculate_estimate(db, estimate_id)
    db.refresh(line_item)
    return line_item


@router.delete("/{estimate_id}/line-items/{item_id}", status_code=204)
def delete_line_item(
    estimate_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    line_item = (
        db.query(EstimateLineItem)
        .filter(
            EstimateLineItem.id == item_id,
            EstimateLineItem.estimate_id == estimate_id,
        )
        .first()
    )
    if not line_item:
        raise HTTPException(status_code=404, detail="Line item not found")

    db.delete(line_item)
    db.commit()
    recalculate_estimate(db, estimate_id)


@router.post(
    "/{estimate_id}/line-items/{item_id}/duplicate",
    response_model=EstimateLineItemResponse,
    status_code=201,
)
def duplicate_line_item(
    estimate_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = (
        db.query(EstimateLineItem)
        .filter(
            EstimateLineItem.id == item_id,
            EstimateLineItem.estimate_id == estimate_id,
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Line item not found")

    max_order = (
        db.query(EstimateLineItem.sort_order)
        .filter(EstimateLineItem.estimate_id == estimate_id)
        .order_by(EstimateLineItem.sort_order.desc())
        .first()
    )
    new_sort_order = (max_order[0] or 0) + 1 if max_order else 0

    duplicate = EstimateLineItem(
        estimate_id=estimate_id,
        description=source.description,
        qty=source.qty,
        unit_price=source.unit_price,
        line_total=calculate_line_total(source.qty, source.unit_price),
        body=source.body,
        notes=source.notes,
        section_id=source.section_id,
        sort_order=new_sort_order,
    )
    db.add(duplicate)
    db.commit()

    recalculate_estimate(db, estimate_id)
    db.refresh(duplicate)
    return duplicate


# --- Sprint 15a: Internal approve ---


class InternalApproveRequest(BaseModel):
    signer_name: Optional[str] = None


@router.post(
    "/{estimate_id}/approve-internal",
    response_model=EstimateResponse,
)
def approve_estimate_internal(
    estimate_id: int,
    data: InternalApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Salesperson-driven approval without customer portal signature.

    Accepts estimates in status 'draft', 'sent', or 'viewed'. Sets status
    to 'approved', records approved_at / approved_by, logs to status
    history, and auto-moves the estimate (and legacy parent job) to the
    Jobs pipeline 'Pending Schedule' stage so the new jobs board picks
    it up.
    """
    estimate = _load_estimate(db, estimate_id)

    if estimate.status == "approved":
        raise HTTPException(status_code=400, detail="Estimate is already approved")
    if estimate.status not in ("draft", "sent", "viewed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot internally approve an estimate in status '{estimate.status}'",
        )

    approve_estimate(
        db,
        estimate,
        approved_by=(data.signer_name or "internal").strip() or "internal",
    )

    db.commit()
    estimate = _load_estimate(db, estimate_id)
    return _estimate_to_response(estimate, db)
