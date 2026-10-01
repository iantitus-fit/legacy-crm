"""DEPRECATED (Sprint 15 restructure): The Job entity is being replaced by
the Contact → Estimate model. An approved estimate IS a job. This router
is kept for backward compatibility during the transition — do not add new
features here. New code should use the estimate and contact endpoints.

This file will be removed once Sub-sprint E cleanup is verified in
production and the `jobs` table is dropped.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.contact import Contact
from app.models.crew import Crew
from app.models.document import Document
from app.models.estimate import Estimate
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.task import Task
from app.models.user import User
from app.schemas.job import (
    JobCreate,
    JobListResponse,
    JobPipelineMove,
    JobResponse,
    JobScheduleUpdate,
    JobStageUpdate,
    JobUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _on_stage_change_task(
    contact_id: int,
    pipeline_slug: Optional[str],
    from_stage_id: Optional[int],
    to_stage_id: Optional[int],
) -> None:
    """Sprint 19b — pipeline stage change automation hook.

    Order matters: enroll new sequences first, *then* stop existing ones —
    that way moving "Cold Proposal → New Quote" can enroll the new-quote
    sequences before the cold-proposal sequence's stop_on_stage_change kicks
    in for the just-departed stage's enrollments.
    """
    import logging

    from app.database import SessionLocal
    from app.services.automation_service import (
        check_stage_change_stop,
        on_pipeline_stage_change,
    )

    log = logging.getLogger("legacy_crm.automation")
    db = SessionLocal()
    try:
        on_pipeline_stage_change(
            db,
            contact_id,
            pipeline_slug or "",
            from_stage_id,
            to_stage_id,
        )
        check_stage_change_stop(db, contact_id)
    except Exception:  # pragma: no cover
        log.exception("on_stage_change failed for contact %s", contact_id)
    finally:
        db.close()


def _job_to_response(job: Job) -> dict:
    """Build a JobResponse dict with computed fields."""
    return {
        "id": job.id,
        "pipeline_id": job.pipeline_id,
        "contact_id": job.contact_id,
        "stage_id": job.stage_id,
        "assigned_to_user_id": job.assigned_to_user_id,
        "job_type": job.job_type,
        "work_type": job.work_type,
        "property_address": job.property_address,
        "notes": job.notes,
        "contract_value": job.contract_value,
        "lead_source": job.lead_source,
        "display_name": job.display_name,
        "labels": job.labels,
        "last_activity_at": job.last_activity_at,
        "scheduled_date": job.scheduled_date,
        "scheduled_end_date": job.scheduled_end_date,
        "crew_id": job.crew_id,
        "created_at": job.created_at,
        "contact_name": job.contact.name if job.contact else None,
        "stage_name": job.stage.name if job.stage else None,
        "pipeline_name": job.pipeline.name if job.pipeline else None,
        "assigned_to_name": job.assigned_to.full_name if job.assigned_to else None,
        "crew_name": job.crew.name if job.crew else None,
        "crew_color": job.crew.color if job.crew else None,
    }


def _job_query_options():
    return [
        joinedload(Job.contact),
        joinedload(Job.stage),
        joinedload(Job.pipeline),
        joinedload(Job.assigned_to),
        joinedload(Job.crew),
    ]


@router.get("", response_model=JobListResponse)
def list_jobs(
    search: Optional[str] = Query(None, description="Search by contact name or address"),
    pipeline_id: Optional[int] = Query(None),
    stage_id: Optional[int] = Query(None),
    work_type: Optional[str] = Query(None),
    contact_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Job).options(*_job_query_options())

    if search:
        search_filter = f"%{search}%"
        query = query.join(Job.contact, isouter=True).filter(
            or_(
                Contact.name.ilike(search_filter),
                Job.property_address.ilike(search_filter),
            )
        )

    if pipeline_id is not None:
        query = query.filter(Job.pipeline_id == pipeline_id)
    if stage_id is not None:
        query = query.filter(Job.stage_id == stage_id)
    if work_type is not None:
        query = query.filter(Job.work_type == work_type)
    if contact_id is not None:
        query = query.filter(Job.contact_id == contact_id)

    total = query.count()
    jobs = (
        query.order_by(Job.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return JobListResponse(
        items=[_job_to_response(j) for j in jobs],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = (
        db.query(Job)
        .options(*_job_query_options())
        .filter(Job.id == job_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)


@router.post("", response_model=JobResponse, status_code=201)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate pipeline
    pipeline = db.query(Pipeline).filter(Pipeline.id == job_data.pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=400, detail="Pipeline not found")

    if job_data.contact_id is not None:
        contact = db.query(Contact).filter(Contact.id == job_data.contact_id).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact not found")

    # If stage_id provided, validate it belongs to the pipeline
    if job_data.stage_id is not None:
        stage = db.query(PipelineStage).filter(PipelineStage.id == job_data.stage_id).first()
        if not stage:
            raise HTTPException(status_code=400, detail="Pipeline stage not found")
        if stage.pipeline_id != job_data.pipeline_id:
            raise HTTPException(
                status_code=400, detail="Stage does not belong to the specified pipeline"
            )
    else:
        # Default to first stage of the pipeline
        first_stage = (
            db.query(PipelineStage)
            .filter(PipelineStage.pipeline_id == job_data.pipeline_id)
            .order_by(PipelineStage.sort_order)
            .first()
        )
        if first_stage:
            job_data = job_data.model_copy(update={"stage_id": first_stage.id})

    if job_data.crew_id is not None:
        crew = db.query(Crew).filter(Crew.id == job_data.crew_id).first()
        if not crew:
            raise HTTPException(status_code=400, detail="Crew not found")

    job = Job(**job_data.model_dump())
    job.last_activity_at = datetime.now(timezone.utc)
    db.add(job)
    db.commit()
    db.refresh(job)

    job = (
        db.query(Job)
        .options(*_job_query_options())
        .filter(Job.id == job.id)
        .first()
    )
    return _job_to_response(job)


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    job_data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    update_data = job_data.model_dump(exclude_unset=True)

    if "contact_id" in update_data and update_data["contact_id"] is not None:
        contact = db.query(Contact).filter(Contact.id == update_data["contact_id"]).first()
        if not contact:
            raise HTTPException(status_code=400, detail="Contact not found")

    if "stage_id" in update_data and update_data["stage_id"] is not None:
        stage = db.query(PipelineStage).filter(PipelineStage.id == update_data["stage_id"]).first()
        if not stage:
            raise HTTPException(status_code=400, detail="Pipeline stage not found")
        if stage.pipeline_id != job.pipeline_id:
            raise HTTPException(
                status_code=400, detail="Stage does not belong to the job's pipeline"
            )

    if "crew_id" in update_data and update_data["crew_id"] is not None:
        crew = db.query(Crew).filter(Crew.id == update_data["crew_id"]).first()
        if not crew:
            raise HTTPException(status_code=400, detail="Crew not found")

    for field, value in update_data.items():
        setattr(job, field, value)

    job.last_activity_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)

    job = (
        db.query(Job)
        .options(*_job_query_options())
        .filter(Job.id == job.id)
        .first()
    )
    return _job_to_response(job)


@router.patch("/{job_id}/stage", response_model=JobResponse)
def update_job_stage(
    job_id: int,
    stage_data: JobStageUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lightweight stage update for drag-and-drop."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stage = db.query(PipelineStage).filter(PipelineStage.id == stage_data.stage_id).first()
    if not stage:
        raise HTTPException(status_code=400, detail="Pipeline stage not found")
    if stage.pipeline_id != job.pipeline_id:
        raise HTTPException(
            status_code=400, detail="Stage does not belong to the job's pipeline"
        )

    old_stage_id = job.stage_id
    pipeline_slug = stage.pipeline.slug if stage.pipeline else None

    job.stage_id = stage_data.stage_id
    job.last_activity_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)

    # Sprint 19b — fire automation triggers on stage change
    if job.contact_id and pipeline_slug:
        background_tasks.add_task(
            _on_stage_change_task,
            job.contact_id,
            pipeline_slug,
            old_stage_id,
            job.stage_id,
        )

    job = (
        db.query(Job)
        .options(*_job_query_options())
        .filter(Job.id == job.id)
        .first()
    )
    return _job_to_response(job)


@router.patch("/{job_id}/schedule", response_model=JobResponse)
def schedule_job(
    job_id: int,
    schedule_data: JobScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Quick-schedule a job: set dates, optional crew, auto-move to Scheduled stage."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if schedule_data.crew_id is not None:
        crew = db.query(Crew).filter(Crew.id == schedule_data.crew_id).first()
        if not crew:
            raise HTTPException(status_code=400, detail="Crew not found")

    job.scheduled_date = schedule_data.scheduled_date
    job.scheduled_end_date = schedule_data.scheduled_end_date
    if schedule_data.crew_id is not None:
        job.crew_id = schedule_data.crew_id

    # Auto-move to "Scheduled" stage if it exists in this pipeline
    scheduled_stage = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == job.pipeline_id,
            PipelineStage.name == "Scheduled",
        )
        .first()
    )
    if scheduled_stage:
        job.stage_id = scheduled_stage.id

    job.last_activity_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)

    job = (
        db.query(Job)
        .options(*_job_query_options())
        .filter(Job.id == job.id)
        .first()
    )
    return _job_to_response(job)


@router.put("/{job_id}/pipeline", response_model=JobResponse)
def move_job_to_pipeline(
    job_id: int,
    move_data: JobPipelineMove,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Move a job to a different pipeline."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    pipeline = db.query(Pipeline).filter(Pipeline.id == move_data.pipeline_id).first()
    if not pipeline:
        raise HTTPException(status_code=400, detail="Target pipeline not found")

    old_stage_id = job.stage_id

    if move_data.stage_id is not None:
        stage = db.query(PipelineStage).filter(PipelineStage.id == move_data.stage_id).first()
        if not stage:
            raise HTTPException(status_code=400, detail="Target stage not found")
        if stage.pipeline_id != move_data.pipeline_id:
            raise HTTPException(
                status_code=400, detail="Stage does not belong to the target pipeline"
            )
        job.stage_id = move_data.stage_id
    else:
        first_stage = (
            db.query(PipelineStage)
            .filter(PipelineStage.pipeline_id == move_data.pipeline_id)
            .order_by(PipelineStage.sort_order)
            .first()
        )
        job.stage_id = first_stage.id if first_stage else None

    job.pipeline_id = move_data.pipeline_id
    job.last_activity_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)

    # Sprint 19b — fire automation triggers on cross-pipeline move
    if job.contact_id and pipeline.slug:
        background_tasks.add_task(
            _on_stage_change_task,
            job.contact_id,
            pipeline.slug,
            old_stage_id,
            job.stage_id,
        )

    job = (
        db.query(Job)
        .options(*_job_query_options())
        .filter(Job.id == job.id)
        .first()
    )
    return _job_to_response(job)


@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    estimate_count = db.query(Estimate).filter(Estimate.job_id == job_id).count()
    task_count = db.query(Task).filter(Task.job_id == job_id).count()
    doc_count = db.query(Document).filter(Document.job_id == job_id).count()
    total = estimate_count + task_count + doc_count
    if total > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete job with {total} associated record(s). "
            "Remove estimates, tasks, and documents first.",
        )

    db.delete(job)
    db.commit()
