"""One approval path for estimates.

The customer portal and the salesperson's internal approve used to set
different fields: the portal recorded a signature but no approved_at and
moved only the parent job, so a customer-signed estimate never reached the
Jobs board (which reads the estimate's pipeline). Both entry points now call
approve_estimate(), so an approved estimate looks the same however it got
there. The caller commits.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.estimate import Estimate
from app.models.estimate_status_history import EstimateStatusHistory
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage

logger = logging.getLogger("legacy_crm")

# Statuses in which the customer can still answer an estimate or change order
# through the portal. Anything else (approved, rejected, changes requested,
# or a job already underway) is closed until the salesperson resends it.
OPEN_FOR_RESPONSE = frozenset({"draft", "sent", "viewed"})

JOBS_PIPELINE_SLUG = "jobs"
PENDING_SCHEDULE_STAGE = "Pending Schedule"


def approve_estimate(
    db: Session,
    estimate: Estimate,
    *,
    approved_by: str,
    ip_address: Optional[str] = None,
) -> None:
    """Mark an estimate approved and place it (and its job row) in Jobs / Pending Schedule."""
    estimate.status = "approved"
    estimate.approved_at = datetime.now(timezone.utc)
    estimate.approved_by = approved_by
    db.add(
        EstimateStatusHistory(
            estimate_id=estimate.id,
            status="approved",
            changed_by_name=approved_by,
            ip_address=ip_address,
        )
    )

    jobs_pipeline = (
        db.query(Pipeline).filter(Pipeline.slug == JOBS_PIPELINE_SLUG).first()
    )
    if jobs_pipeline is None:
        logger.warning("Jobs pipeline (slug='jobs') not found; approved estimate not placed on a board")
        return
    pending_stage = (
        db.query(PipelineStage)
        .filter(
            PipelineStage.pipeline_id == jobs_pipeline.id,
            PipelineStage.name == PENDING_SCHEDULE_STAGE,
        )
        .first()
    )
    if pending_stage is None:
        logger.warning("'Pending Schedule' stage not found in Jobs pipeline; approved estimate not placed on a board")
        return

    estimate.pipeline_id = jobs_pipeline.id
    estimate.stage_id = pending_stage.id
    if estimate.job_id:
        job = db.query(Job).filter(Job.id == estimate.job_id).first()
        if job is not None:
            job.pipeline_id = jobs_pipeline.id
            job.stage_id = pending_stage.id
