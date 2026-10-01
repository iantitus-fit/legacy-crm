from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.job import Job
from app.models.lead import Lead
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.schemas.board import (
    ContactBoardResponse,
    EstimateBoardResponse,
)
from app.schemas.job import PipelineBoardResponse
from app.schemas.pipeline import (
    PipelineDetailResponse,
    PipelineListResponse,
    PipelineResponse,
)
from app.schemas.pipeline_stage import (
    PipelineStageCreate,
    PipelineStageResponse,
    PipelineStageUpdate,
    StageReorderRequest,
)
from app.utils.dependencies import get_current_user

# Sprint 15a — estimate statuses that count as "jobs" (approved and beyond)
JOB_STATUSES = ("approved", "in_progress", "complete", "closed")
ACTIVE_ESTIMATE_STATUSES = (
    "draft",
    "sent",
    "viewed",
    "approved",
    "in_progress",
    "complete",
)

router = APIRouter(prefix="/api/pipelines", tags=["pipelines"])


@router.get("", response_model=PipelineListResponse)
def list_pipelines(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pipelines = db.query(Pipeline).order_by(Pipeline.display_order).all()
    return PipelineListResponse(items=pipelines)


@router.get("/{pipeline_id}", response_model=PipelineDetailResponse)
def get_pipeline(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pipeline = (
        db.query(Pipeline)
        .options(joinedload(Pipeline.stages))
        .filter(Pipeline.id == pipeline_id)
        .first()
    )
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@router.get("/{pipeline_id}/board", response_model=PipelineBoardResponse)
def get_pipeline_board(
    pipeline_id: int,
    salesperson: Optional[int] = Query(None, description="Filter by assigned user ID"),
    lead_source: Optional[str] = Query(None, description="Filter by lead source"),
    label: Optional[str] = Query(None, description="Filter by label"),
    created_after: Optional[date] = Query(None),
    created_before: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline_id)
        .order_by(PipelineStage.sort_order)
        .all()
    )

    # Build job query with filters
    job_query = (
        db.query(Job)
        .options(joinedload(Job.contact), joinedload(Job.assigned_to), joinedload(Job.crew))
        .filter(Job.pipeline_id == pipeline_id)
    )

    if salesperson is not None:
        job_query = job_query.filter(Job.assigned_to_user_id == salesperson)
    if lead_source is not None:
        job_query = job_query.filter(Job.lead_source == lead_source)
    if created_after is not None:
        job_query = job_query.filter(Job.created_at >= created_after)
    if created_before is not None:
        job_query = job_query.filter(Job.created_at <= created_before)

    jobs = job_query.all()

    # Filter by label in Python (JSON array containment varies by DB)
    if label is not None:
        jobs = [j for j in jobs if j.labels and label in j.labels]

    # Group jobs by stage_id
    jobs_by_stage = {}
    for job in jobs:
        if job.stage_id not in jobs_by_stage:
            jobs_by_stage[job.stage_id] = []
        jobs_by_stage[job.stage_id].append(job)

    total_deals = 0
    total_value = Decimal("0")

    result_stages = []
    for stage in stages:
        stage_jobs = jobs_by_stage.get(stage.id, [])
        stage_value = sum(
            (j.contract_value or Decimal("0")) for j in stage_jobs
        )
        total_deals += len(stage_jobs)
        total_value += stage_value

        result_stages.append({
            "id": stage.id,
            "name": stage.name,
            "sort_order": stage.sort_order,
            "color": stage.color,
            "is_closed_won": stage.is_closed_won,
            "is_closed_lost": stage.is_closed_lost,
            "job_count": len(stage_jobs),
            "total_value": stage_value,
            "jobs": [
                {
                    "id": j.id,
                    "contact_id": j.contact_id,
                    "contact_name": j.contact.name if j.contact else None,
                    "property_address": j.property_address,
                    "work_type": j.work_type,
                    "job_type": j.job_type,
                    "contract_value": j.contract_value,
                    "lead_source": j.lead_source,
                    "display_name": j.display_name,
                    "labels": j.labels,
                    "assigned_to_user_id": j.assigned_to_user_id,
                    "assigned_to_name": j.assigned_to.full_name if j.assigned_to else None,
                    "last_activity_at": j.last_activity_at,
                    "stage_id": j.stage_id,
                    "crew_id": j.crew_id,
                    "crew_name": j.crew.name if j.crew else None,
                    "crew_color": j.crew.color if j.crew else None,
                    "scheduled_date": j.scheduled_date,
                    "created_at": j.created_at,
                }
                for j in stage_jobs
            ],
        })

    return PipelineBoardResponse(
        pipeline_id=pipeline.id,
        pipeline_name=pipeline.name,
        total_deals=total_deals,
        total_value=total_value,
        stages=result_stages,
    )


# --- Sprint 15c: Contact-centric board for Lead/Sales pipelines ---


@router.get(
    "/{pipeline_id}/contacts-board",
    response_model=ContactBoardResponse,
)
def get_contacts_board(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Contact-centric pipeline board used by the Leads and Sales pipelines.

    Each card is one Contact filtered by Contact.pipeline_id == pipeline_id
    and grouped by Contact.stage_id. Each card carries an estimate_count
    and active_estimate_value aggregate so the board can show how much
    pipeline value sits with this client.
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline_id)
        .order_by(PipelineStage.sort_order)
        .all()
    )

    contacts = (
        db.query(Contact)
        .filter(Contact.pipeline_id == pipeline_id)
        .all()
    )

    # Aggregate estimate counts and values per contact. We do this in
    # Python because the relationship is contact -> job -> estimate, and
    # jobs are still the transitional join. Joining Job on contact_id
    # keeps a consistent view during the restructure.
    contact_ids = [c.id for c in contacts]
    est_agg = {}
    if contact_ids:
        rows = (
            db.query(
                Job.contact_id,
                func.count(Estimate.id),
                func.coalesce(func.sum(Estimate.total), 0),
            )
            .join(Estimate, Estimate.job_id == Job.id)
            .filter(
                Job.contact_id.in_(contact_ids),
                Estimate.status.in_(ACTIVE_ESTIMATE_STATUSES),
            )
            .group_by(Job.contact_id)
            .all()
        )
        for contact_id, count, value in rows:
            est_agg[contact_id] = (count or 0, Decimal(str(value or 0)))

    contacts_by_stage = {}
    for c in contacts:
        contacts_by_stage.setdefault(c.stage_id, []).append(c)

    total_contacts = 0
    total_value = Decimal("0")
    result_stages = []
    for stage in stages:
        stage_contacts = contacts_by_stage.get(stage.id, [])
        cards = []
        stage_value = Decimal("0")
        for c in stage_contacts:
            count, value = est_agg.get(c.id, (0, Decimal("0")))
            stage_value += value
            cards.append(
                {
                    "id": c.id,
                    "name": c.name,
                    "company": c.company,
                    "email": c.email,
                    "phone": c.phone,
                    "address": c.address,
                    "client_type": c.client_type,
                    "lead_source": c.lead_source,
                    "stage_id": c.stage_id,
                    "estimate_count": count,
                    "active_estimate_value": value,
                    "last_activity_at": None,
                    "created_at": c.created_at,
                }
            )
        total_contacts += len(cards)
        total_value += stage_value
        result_stages.append(
            {
                "id": stage.id,
                "name": stage.name,
                "sort_order": stage.sort_order,
                "color": stage.color,
                "is_closed_won": stage.is_closed_won,
                "is_closed_lost": stage.is_closed_lost,
                "contact_count": len(cards),
                "total_value": stage_value,
                "contacts": cards,
            }
        )

    return ContactBoardResponse(
        pipeline_id=pipeline.id,
        pipeline_name=pipeline.name,
        total_contacts=total_contacts,
        total_value=total_value,
        stages=result_stages,
    )


# --- Sprint 15c: Estimate-centric board for the Jobs pipeline ---


@router.get(
    "/{pipeline_id}/estimates-board",
    response_model=EstimateBoardResponse,
)
def get_estimates_board(
    pipeline_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Estimate-centric pipeline board used by the Jobs pipeline.

    Each card is one Estimate filtered by Estimate.pipeline_id == pipeline_id
    (set when the estimate is internally approved or customer-portal
    approved) and in a job-phase status. Grouped by Estimate.stage_id.
    """
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline_id)
        .order_by(PipelineStage.sort_order)
        .all()
    )

    estimates = (
        db.query(Estimate)
        .options(
            joinedload(Estimate.job).joinedload(Job.contact),
            joinedload(Estimate.crew),
            joinedload(Estimate.assigned_to),
        )
        .filter(
            Estimate.pipeline_id == pipeline_id,
            Estimate.status.in_(JOB_STATUSES),
        )
        .all()
    )

    estimates_by_stage = {}
    for e in estimates:
        estimates_by_stage.setdefault(e.stage_id, []).append(e)

    total_estimates = 0
    total_value = Decimal("0")
    result_stages = []
    for stage in stages:
        stage_estimates = estimates_by_stage.get(stage.id, [])
        cards = []
        stage_value = Decimal("0")
        for e in stage_estimates:
            value = Decimal(str(e.total or 0))
            stage_value += value
            contact_id = None
            contact_name = None
            contact_company = None
            if e.job and e.job.contact:
                contact_id = e.job.contact.id
                contact_name = e.job.contact.name
                contact_company = e.job.contact.company
            cards.append(
                {
                    "id": e.id,
                    "name": e.name,
                    "status": e.status,
                    "job_type": e.job_type,
                    "work_type": e.work_type,
                    "location_address": e.location_address,
                    "total": e.total,
                    "contact_id": contact_id,
                    "contact_name": contact_name,
                    "contact_company": contact_company,
                    "crew_id": e.crew_id,
                    "crew_name": e.crew.name if e.crew else None,
                    "crew_color": e.crew.color if e.crew else None,
                    "scheduled_start": e.scheduled_start,
                    "scheduled_end": e.scheduled_end,
                    "assigned_to_user_id": e.assigned_to_user_id,
                    "assigned_to_name": e.assigned_to.full_name if e.assigned_to else None,
                    "approved_at": e.approved_at,
                    "stage_id": e.stage_id,
                    "created_at": e.created_at,
                }
            )
        total_estimates += len(cards)
        total_value += stage_value
        result_stages.append(
            {
                "id": stage.id,
                "name": stage.name,
                "sort_order": stage.sort_order,
                "color": stage.color,
                "is_closed_won": stage.is_closed_won,
                "is_closed_lost": stage.is_closed_lost,
                "estimate_count": len(cards),
                "total_value": stage_value,
                "estimates": cards,
            }
        )

    return EstimateBoardResponse(
        pipeline_id=pipeline.id,
        pipeline_name=pipeline.name,
        total_estimates=total_estimates,
        total_value=total_value,
        stages=result_stages,
    )


# --- Stage management within a pipeline ---


@router.post("/{pipeline_id}/stages", response_model=PipelineStageResponse, status_code=201)
def add_stage_to_pipeline(
    pipeline_id: int,
    stage_data: PipelineStageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    existing = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == pipeline_id,
            PipelineStage.name == stage_data.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="A stage with this name already exists in this pipeline"
        )

    stage = PipelineStage(
        pipeline_id=pipeline_id,
        name=stage_data.name,
        sort_order=stage_data.sort_order,
        color=stage_data.color,
        is_closed_won=stage_data.is_closed_won,
        is_closed_lost=stage_data.is_closed_lost,
    )
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


@router.put("/{pipeline_id}/stages/reorder", response_model=list)
def reorder_stages(
    pipeline_id: int,
    reorder_data: StageReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    for item in reorder_data.stages:
        stage = (
            db.query(PipelineStage)
            .filter(
                PipelineStage.id == item.id,
                PipelineStage.pipeline_id == pipeline_id,
            )
            .first()
        )
        if not stage:
            raise HTTPException(
                status_code=400,
                detail=f"Stage {item.id} not found in this pipeline",
            )
        stage.sort_order = item.sort_order

    db.commit()

    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == pipeline_id)
        .order_by(PipelineStage.sort_order)
        .all()
    )
    return [
        PipelineStageResponse.model_validate(s).model_dump()
        for s in stages
    ]


@router.put("/{pipeline_id}/stages/{stage_id}", response_model=PipelineStageResponse)
def update_pipeline_stage(
    pipeline_id: int,
    stage_id: int,
    stage_data: PipelineStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.id == stage_id, PipelineStage.pipeline_id == pipeline_id)
        .first()
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found in this pipeline")

    update_data = stage_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        existing = (
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id == pipeline_id,
                PipelineStage.name == update_data["name"],
                PipelineStage.id != stage_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="A stage with this name already exists in this pipeline"
            )

    for field, value in update_data.items():
        setattr(stage, field, value)

    db.commit()
    db.refresh(stage)
    return stage


@router.delete("/{pipeline_id}/stages/{stage_id}", status_code=204)
def delete_pipeline_stage(
    pipeline_id: int,
    stage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = (
        db.query(PipelineStage)
        .filter(PipelineStage.id == stage_id, PipelineStage.pipeline_id == pipeline_id)
        .first()
    )
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found in this pipeline")

    job_count = db.query(Job).filter(Job.stage_id == stage_id).count()
    lead_count = db.query(Lead).filter(Lead.stage_id == stage_id).count()
    total = job_count + lead_count
    if total > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete stage with {total} associated record(s). "
            "Move jobs/leads to another stage first.",
        )

    db.delete(stage)
    db.commit()
