from datetime import date, timedelta
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import func, nullslast
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.task import Task
from app.models.user import User
from app.schemas.calendar import UpcomingItem
from app.schemas.dashboard import (
    DashboardStatsResponse,
    EmployeeTaskCount,
    OpenInvoiceResponse,
    RecentJobResponse,
    TaskDueResponse,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _end_of_week(today: date) -> date:
    """Return the date of the coming Sunday (end of week)."""
    days_until_sunday = 6 - today.weekday()  # Monday=0, Sunday=6
    if days_until_sunday == 0:
        days_until_sunday = 7
    return today + timedelta(days=days_until_sunday)


@router.get("/stats", response_model=DashboardStatsResponse)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    end_of_week = _end_of_week(today)

    # Look up pipeline IDs by slug
    leads_pipeline = db.query(Pipeline).filter(Pipeline.slug == "leads").first()
    sales_pipeline = db.query(Pipeline).filter(Pipeline.slug == "sales").first()
    jobs_pipeline = db.query(Pipeline).filter(Pipeline.slug == "jobs").first()

    # New leads count: jobs in Leads pipeline
    new_leads_count = 0
    if leads_pipeline:
        new_leads_count = (
            db.query(func.count(Job.id))
            .filter(Job.pipeline_id == leads_pipeline.id)
            .scalar()
        ) or 0

    # Active proposals: jobs in Sales pipeline
    active_proposals_count = 0
    if sales_pipeline:
        active_proposals_count = (
            db.query(func.count(Job.id))
            .filter(Job.pipeline_id == sales_pipeline.id)
            .scalar()
        ) or 0

    # Jobs in progress: jobs in Jobs pipeline excluding Complete/Warranty/Closed
    jobs_in_progress_count = 0
    if jobs_pipeline:
        closed_stage_names = ["Complete", "Warranty", "Closed"]
        closed_stage_ids = [
            s.id for s in
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id == jobs_pipeline.id,
                PipelineStage.name.in_(closed_stage_names),
            )
            .all()
        ]
        q = db.query(func.count(Job.id)).filter(
            Job.pipeline_id == jobs_pipeline.id
        )
        if closed_stage_ids:
            q = q.filter(~Job.stage_id.in_(closed_stage_ids))
        jobs_in_progress_count = q.scalar() or 0

    # Contact count
    contact_count = db.query(func.count(Contact.id)).scalar() or 0

    # Sprint 15c — new-model counts. Lead/Sales counts come from
    # Contact.pipeline_id; Jobs count comes from approved Estimate rows
    # (because an approved estimate IS a job in the new model).
    new_leads_count_v2 = 0
    if leads_pipeline:
        new_leads_count_v2 = (
            db.query(func.count(Contact.id))
            .filter(Contact.pipeline_id == leads_pipeline.id)
            .scalar()
        ) or 0

    active_proposals_count_v2 = 0
    if sales_pipeline:
        active_proposals_count_v2 = (
            db.query(func.count(Contact.id))
            .filter(Contact.pipeline_id == sales_pipeline.id)
            .scalar()
        ) or 0

    jobs_in_progress_count_v2 = 0
    if jobs_pipeline:
        closed_stage_ids_v2 = [
            s.id for s in
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id == jobs_pipeline.id,
                PipelineStage.name.in_(["Complete", "Warranty", "Closed"]),
            )
            .all()
        ]
        q = (
            db.query(func.count(Estimate.id))
            .filter(
                Estimate.pipeline_id == jobs_pipeline.id,
                Estimate.status.in_(["approved", "in_progress", "complete"]),
            )
        )
        if closed_stage_ids_v2:
            q = q.filter(~Estimate.stage_id.in_(closed_stage_ids_v2))
        jobs_in_progress_count_v2 = q.scalar() or 0

    # New pipeline value: sum of Estimate.total for estimates in Sales
    # or Jobs pipelines (active and approved, excluding fully-closed).
    pipeline_value_v2 = Decimal("0")
    value_pipeline_ids_v2 = [
        p.id for p in (sales_pipeline, jobs_pipeline) if p is not None
    ]
    if value_pipeline_ids_v2:
        closed_stage_ids_all_v2 = [
            s.id for s in
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id.in_(value_pipeline_ids_v2),
                PipelineStage.name == "Closed",
            )
            .all()
        ]
        vq = (
            db.query(func.coalesce(func.sum(Estimate.total), 0))
            .filter(
                Estimate.pipeline_id.in_(value_pipeline_ids_v2),
                Estimate.status.in_(
                    ["draft", "sent", "viewed", "approved", "in_progress", "complete"]
                ),
            )
        )
        if closed_stage_ids_all_v2:
            vq = vq.filter(~Estimate.stage_id.in_(closed_stage_ids_all_v2))
        pipeline_value_v2 = Decimal(str(vq.scalar() or 0))

    # Open tasks
    open_tasks = (
        db.query(func.count(Task.id))
        .filter(Task.status == "open")
        .scalar()
    ) or 0

    # Pipeline value: sum across Sales + Jobs pipelines (excluding Closed stage)
    pipeline_value = Decimal("0")
    value_pipeline_ids = []
    if sales_pipeline:
        value_pipeline_ids.append(sales_pipeline.id)
    if jobs_pipeline:
        value_pipeline_ids.append(jobs_pipeline.id)

    if value_pipeline_ids:
        # Exclude "Closed" stages
        closed_stage_ids_all = [
            s.id for s in
            db.query(PipelineStage)
            .filter(
                PipelineStage.pipeline_id.in_(value_pipeline_ids),
                PipelineStage.name == "Closed",
            )
            .all()
        ]
        vq = db.query(func.sum(Job.contract_value)).filter(
            Job.pipeline_id.in_(value_pipeline_ids)
        )
        if closed_stage_ids_all:
            vq = vq.filter(~Job.stage_id.in_(closed_stage_ids_all))
        pipeline_value = vq.scalar() or Decimal("0")

    # Overdue task count
    overdue_task_count = (
        db.query(func.count(Task.id))
        .filter(
            Task.status == "open",
            Task.due_date.isnot(None),
            Task.due_date < today,
        )
        .scalar()
    ) or 0

    # Recent jobs (last 10)
    recent_job_rows = (
        db.query(Job, Contact.name, PipelineStage.name, Pipeline.name)
        .join(Contact, Job.contact_id == Contact.id, isouter=True)
        .join(PipelineStage, Job.stage_id == PipelineStage.id, isouter=True)
        .join(Pipeline, Job.pipeline_id == Pipeline.id, isouter=True)
        .order_by(Job.created_at.desc())
        .limit(10)
        .all()
    )
    recent_jobs: List[RecentJobResponse] = [
        RecentJobResponse(
            id=job.id,
            contact_id=job.contact_id,
            contact_name=contact_name,
            property_address=job.property_address,
            stage_name=stage_name,
            pipeline_name=pipeline_name,
            work_type=job.work_type,
            contract_value=job.contract_value,
            created_at=job.created_at,
        )
        for job, contact_name, stage_name, pipeline_name in recent_job_rows
    ]

    # Tasks due today
    tasks_today_rows = (
        db.query(Task, Job.property_address)
        .join(Job, Task.job_id == Job.id, isouter=True)
        .filter(
            Task.status == "open",
            Task.due_date == today,
        )
        .all()
    )
    tasks_due_today: List[TaskDueResponse] = [
        TaskDueResponse(
            id=task.id,
            title=task.title,
            due_date=task.due_date,
            job_id=task.job_id,
            job_address=job_address,
            is_overdue=False,
            assigned_to_user_id=task.assigned_to_user_id,
            assigned_to_name=None,
        )
        for task, job_address in tasks_today_rows
    ]

    # Tasks due this week (today through end of week Sunday)
    tasks_week_rows = (
        db.query(Task, Job.property_address)
        .join(Job, Task.job_id == Job.id, isouter=True)
        .filter(
            Task.status == "open",
            Task.due_date.isnot(None),
            Task.due_date >= today,
            Task.due_date <= end_of_week,
        )
        .order_by(Task.due_date.asc())
        .all()
    )
    tasks_due_this_week: List[TaskDueResponse] = [
        TaskDueResponse(
            id=task.id,
            title=task.title,
            due_date=task.due_date,
            job_id=task.job_id,
            job_address=job_address,
            is_overdue=False,
            assigned_to_user_id=task.assigned_to_user_id,
            assigned_to_name=None,
        )
        for task, job_address in tasks_week_rows
    ]

    # Sprint 14.5: task buckets for dashboard columns (past due / today / future)
    def _task_rows_to_response(rows, is_overdue: bool = False):
        return [
            TaskDueResponse(
                id=task.id,
                title=task.title,
                due_date=task.due_date,
                job_id=task.job_id,
                job_address=job_address,
                is_overdue=is_overdue,
                assigned_to_user_id=task.assigned_to_user_id,
                assigned_to_name=None,
            )
            for task, job_address in rows
        ]

    past_due_rows = (
        db.query(Task, Job.property_address)
        .join(Job, Task.job_id == Job.id, isouter=True)
        .filter(
            Task.status == "open",
            Task.due_date.isnot(None),
            Task.due_date < today,
        )
        .order_by(Task.due_date.asc())
        .limit(5)
        .all()
    )
    tasks_past_due = _task_rows_to_response(past_due_rows, is_overdue=True)

    today_bucket_rows = (
        db.query(Task, Job.property_address)
        .join(Job, Task.job_id == Job.id, isouter=True)
        .filter(
            Task.status == "open",
            Task.due_date == today,
        )
        .order_by(Task.due_date.asc())
        .limit(5)
        .all()
    )
    tasks_today_bucket = _task_rows_to_response(today_bucket_rows)

    future_rows = (
        db.query(Task, Job.property_address)
        .join(Job, Task.job_id == Job.id, isouter=True)
        .filter(
            Task.status == "open",
            Task.due_date.isnot(None),
            Task.due_date > today,
        )
        .order_by(Task.due_date.asc())
        .limit(5)
        .all()
    )
    tasks_future = _task_rows_to_response(future_rows)

    # Sprint 14.5: open invoices (balance > 0, not void), max 5
    open_invoice_rows = (
        db.query(Invoice, Contact.name)
        .join(Job, Invoice.job_id == Job.id, isouter=True)
        .join(Contact, Job.contact_id == Contact.id, isouter=True)
        .filter(
            Invoice.balance > 0,
            Invoice.status != "void",
        )
        .order_by(nullslast(Invoice.due_date.asc()), Invoice.created_at.asc())
        .limit(5)
        .all()
    )
    open_invoices: List[OpenInvoiceResponse] = [
        OpenInvoiceResponse(
            id=inv.id,
            invoice_number=inv.invoice_number,
            contact_name=contact_name,
            total=inv.total,
            balance=inv.balance,
            due_date=inv.due_date,
            status=inv.status,
        )
        for inv, contact_name in open_invoice_rows
    ]

    # My tasks today: filtered to current user
    my_tasks_rows = (
        db.query(Task, Job.property_address)
        .join(Job, Task.job_id == Job.id, isouter=True)
        .filter(
            Task.status == "open",
            Task.due_date == today,
            Task.assigned_to_user_id == current_user.id,
        )
        .all()
    )
    my_tasks_today: List[TaskDueResponse] = [
        TaskDueResponse(
            id=task.id,
            title=task.title,
            due_date=task.due_date,
            job_id=task.job_id,
            job_address=job_address,
            is_overdue=False,
            assigned_to_user_id=task.assigned_to_user_id,
            assigned_to_name=None,
        )
        for task, job_address in my_tasks_rows
    ]

    # Employee task counts (admin only)
    employee_task_counts: List[EmployeeTaskCount] = []
    if current_user.role == "admin":
        open_counts = (
            db.query(
                Task.assigned_to_user_id,
                func.count(Task.id),
            )
            .filter(Task.status == "open", Task.assigned_to_user_id.isnot(None))
            .group_by(Task.assigned_to_user_id)
            .all()
        )
        open_map = {uid: cnt for uid, cnt in open_counts}

        due_today_counts = (
            db.query(
                Task.assigned_to_user_id,
                func.count(Task.id),
            )
            .filter(
                Task.status == "open",
                Task.due_date == today,
                Task.assigned_to_user_id.isnot(None),
            )
            .group_by(Task.assigned_to_user_id)
            .all()
        )
        due_today_map = {uid: cnt for uid, cnt in due_today_counts}

        # Get all active users who have open tasks
        user_ids = set(open_map.keys())
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids), User.is_active == True).all()
            for u in users:
                employee_task_counts.append(
                    EmployeeTaskCount(
                        user_id=u.id,
                        full_name=u.full_name,
                        open_count=open_map.get(u.id, 0),
                        due_today_count=due_today_map.get(u.id, 0),
                    )
                )

    # Sprint 15d — Upcoming this week pulls from approved estimates
    # (a "job" in the new model) plus appointments through end of week.
    upcoming_this_week = []
    from sqlalchemy.orm import joinedload as _joinedload

    upcoming_estimates = (
        db.query(Estimate)
        .options(
            _joinedload(Estimate.crew),
            _joinedload(Estimate.job),
        )
        .filter(
            Estimate.scheduled_start.isnot(None),
            Estimate.scheduled_start >= today,
            Estimate.scheduled_start <= end_of_week,
            Estimate.status.in_(["approved", "in_progress", "complete"]),
        )
        .order_by(Estimate.scheduled_start.asc())
        .limit(5)
        .all()
    )
    for e in upcoming_estimates:
        title = (
            e.name
            or e.location_address
            or (e.job.property_address if e.job else None)
            or f"Estimate #{e.id}"
        )
        upcoming_this_week.append(
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

    upcoming_appts = (
        db.query(Appointment)
        .filter(
            Appointment.appointment_date >= today,
            Appointment.appointment_date <= end_of_week,
        )
        .order_by(Appointment.appointment_date.asc())
        .limit(5)
        .all()
    )
    for a in upcoming_appts:
        assigned = db.query(User).filter(User.id == a.assigned_to_user_id).first()
        upcoming_this_week.append(
            UpcomingItem(
                id=a.id,
                item_type="appointment",
                title=a.title,
                date=a.appointment_date,
                time=a.appointment_time,
                color=assigned.color if assigned else None,
                link="/calendars/appointments",
            )
        )

    upcoming_this_week.sort(
        key=lambda x: (x.date, x.time or __import__("datetime").time(23, 59))
    )
    upcoming_this_week = upcoming_this_week[:5]

    return DashboardStatsResponse(
        new_leads_count=new_leads_count,
        active_proposals_count=active_proposals_count,
        jobs_in_progress_count=jobs_in_progress_count,
        contact_count=contact_count,
        open_tasks=open_tasks,
        pipeline_value=pipeline_value,
        overdue_task_count=overdue_task_count,
        recent_jobs=recent_jobs,
        tasks_due_today=tasks_due_today,
        tasks_due_this_week=tasks_due_this_week,
        tasks_past_due=tasks_past_due,
        tasks_today=tasks_today_bucket,
        tasks_future=tasks_future,
        my_tasks_today=my_tasks_today,
        employee_task_counts=employee_task_counts,
        upcoming_this_week=upcoming_this_week,
        open_invoices=open_invoices,
        new_leads_count_v2=new_leads_count_v2,
        active_proposals_count_v2=active_proposals_count_v2,
        jobs_in_progress_count_v2=jobs_in_progress_count_v2,
        pipeline_value_v2=pipeline_value_v2,
    )
