from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.schemas.job import PipelineBoardResponse
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.get("/board", response_model=PipelineBoardResponse)
def get_pipeline_board(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Legacy endpoint — returns the Jobs pipeline board for backward compatibility."""
    jobs_pipeline = db.query(Pipeline).filter(Pipeline.slug == "jobs").first()
    if not jobs_pipeline:
        return PipelineBoardResponse(
            pipeline_id=0,
            pipeline_name="Jobs",
            total_deals=0,
            total_value=Decimal("0"),
            stages=[],
        )

    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.pipeline_id == jobs_pipeline.id)
        .order_by(PipelineStage.sort_order)
        .all()
    )

    jobs = (
        db.query(Job)
        .options(joinedload(Job.contact), joinedload(Job.assigned_to))
        .filter(Job.pipeline_id == jobs_pipeline.id)
        .all()
    )

    jobs_by_stage = {}
    for job in jobs:
        if job.stage_id not in jobs_by_stage:
            jobs_by_stage[job.stage_id] = []
        jobs_by_stage[job.stage_id].append(job)

    total_deals = 0
    total_value = Decimal("0")
    result = []
    for stage in stages:
        stage_jobs = jobs_by_stage.get(stage.id, [])
        stage_value = sum(
            (j.contract_value or Decimal("0")) for j in stage_jobs
        )
        total_deals += len(stage_jobs)
        total_value += stage_value
        result.append({
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
                    "created_at": j.created_at,
                }
                for j in stage_jobs
            ],
        })

    return PipelineBoardResponse(
        pipeline_id=jobs_pipeline.id,
        pipeline_name=jobs_pipeline.name,
        total_deals=total_deals,
        total_value=total_value,
        stages=result,
    )
