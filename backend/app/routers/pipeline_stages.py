from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job import Job
from app.models.lead import Lead
from app.models.pipeline_stage import PipelineStage
from app.models.user import User
from app.schemas.pipeline_stage import (
    PipelineStageCreate,
    PipelineStageListResponse,
    PipelineStageResponse,
    PipelineStageUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/pipeline-stages", tags=["pipeline-stages"])


@router.get("", response_model=PipelineStageListResponse)
def list_pipeline_stages(
    pipeline_id: Optional[int] = Query(None, description="Filter by pipeline"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(PipelineStage)
    if pipeline_id is not None:
        query = query.filter(PipelineStage.pipeline_id == pipeline_id)
    stages = query.order_by(PipelineStage.sort_order).all()
    return PipelineStageListResponse(items=stages)


@router.get("/{stage_id}", response_model=PipelineStageResponse)
def get_pipeline_stage(
    stage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = db.query(PipelineStage).filter(PipelineStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")
    return stage


@router.post("", response_model=PipelineStageResponse, status_code=201)
def create_pipeline_stage(
    stage_data: PipelineStageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check uniqueness within the pipeline
    existing = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == stage_data.pipeline_id,
            PipelineStage.name == stage_data.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400, detail="A stage with this name already exists in this pipeline"
        )

    stage = PipelineStage(**stage_data.model_dump())
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return stage


@router.put("/{stage_id}", response_model=PipelineStageResponse)
def update_pipeline_stage(
    stage_id: int,
    stage_data: PipelineStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = db.query(PipelineStage).filter(PipelineStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")

    update_data = stage_data.model_dump(exclude_unset=True)

    if "name" in update_data:
        existing = (
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id == stage.pipeline_id,
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


@router.delete("/{stage_id}", status_code=204)
def delete_pipeline_stage(
    stage_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stage = db.query(PipelineStage).filter(PipelineStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Pipeline stage not found")

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
