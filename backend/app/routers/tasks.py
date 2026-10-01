from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.job import Job
from app.models.task import Task
from app.models.user import User
from app.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

VALID_STATUSES = {"open", "completed"}
VALID_ENTITY_TYPES = {"contact", "job", "estimate"}


def _resolve_entity_label(db: Session, entity_type: Optional[str], entity_id: Optional[int]) -> Optional[str]:
    """Look up a display label for the related entity."""
    if not entity_type or not entity_id:
        return None
    if entity_type == "contact":
        contact = db.query(Contact).filter(Contact.id == entity_id).first()
        return contact.name if contact else None
    if entity_type == "job":
        job = db.query(Job).filter(Job.id == entity_id).first()
        if job:
            return job.property_address or f"Job #{job.id}"
        return None
    if entity_type == "estimate":
        estimate = db.query(Estimate).filter(Estimate.id == entity_id).first()
        return estimate.name if estimate else None
    return None


def _task_to_response(task: Task, db: Session) -> dict:
    """Build a TaskResponse dict with computed fields."""
    today = date.today()
    is_overdue = (
        task.status == "open"
        and task.due_date is not None
        and task.due_date < today
    )
    job_address = None
    contact_name = None
    if task.job:
        job_address = task.job.property_address
        if task.job.contact:
            contact_name = task.job.contact.name

    assigned_to_name = None
    if task.assigned_to:
        assigned_to_name = task.assigned_to.full_name

    related_entity_label = _resolve_entity_label(
        db, task.related_entity_type, task.related_entity_id
    )

    return {
        "id": task.id,
        "job_id": task.job_id,
        "title": task.title,
        "status": task.status,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "job_address": job_address,
        "contact_name": contact_name,
        "is_overdue": is_overdue,
        "assigned_to_user_id": task.assigned_to_user_id,
        "assigned_to_name": assigned_to_name,
        "related_entity_type": task.related_entity_type,
        "related_entity_id": task.related_entity_id,
        "related_entity_label": related_entity_label,
    }


@router.get("", response_model=TaskListResponse)
def list_tasks(
    job_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    due_date_from: Optional[date] = Query(None),
    due_date_to: Optional[date] = Query(None),
    assigned_to_user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Task).options(
        joinedload(Task.job).joinedload(Job.contact),
        joinedload(Task.assigned_to),
    )

    count_query = db.query(Task)

    if job_id is not None:
        query = query.filter(Task.job_id == job_id)
        count_query = count_query.filter(Task.job_id == job_id)
    if status is not None:
        query = query.filter(Task.status == status)
        count_query = count_query.filter(Task.status == status)
    if due_date_from is not None:
        query = query.filter(Task.due_date >= due_date_from)
        count_query = count_query.filter(Task.due_date >= due_date_from)
    if due_date_to is not None:
        query = query.filter(Task.due_date <= due_date_to)
        count_query = count_query.filter(Task.due_date <= due_date_to)
    if assigned_to_user_id is not None:
        query = query.filter(Task.assigned_to_user_id == assigned_to_user_id)
        count_query = count_query.filter(Task.assigned_to_user_id == assigned_to_user_id)

    total = count_query.count()

    # Sort: open first, then by due_date asc (nulls last), then created_at desc
    items = (
        query.order_by(
            case((Task.status == "open", 0), else_=1),
            Task.due_date.asc().nullslast(),
            Task.created_at.desc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return TaskListResponse(
        items=[_task_to_response(t, db) for t in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = (
        db.query(Task)
        .options(
            joinedload(Task.job).joinedload(Job.contact),
            joinedload(Task.assigned_to),
        )
        .filter(Task.id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_to_response(task, db)


@router.post("", response_model=TaskResponse, status_code=201)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.job_id is not None:
        job = db.query(Job).filter(Job.id == data.job_id).first()
        if not job:
            raise HTTPException(status_code=400, detail="Job not found")

    if data.related_entity_type and data.related_entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"related_entity_type must be one of: {', '.join(VALID_ENTITY_TYPES)}",
        )

    assigned_to = data.assigned_to_user_id if data.assigned_to_user_id is not None else current_user.id

    task = Task(
        job_id=data.job_id,
        title=data.title,
        due_date=data.due_date,
        assigned_to_user_id=assigned_to,
        related_entity_type=data.related_entity_type,
        related_entity_id=data.related_entity_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    task = (
        db.query(Task)
        .options(
            joinedload(Task.job).joinedload(Job.contact),
            joinedload(Task.assigned_to),
        )
        .filter(Task.id == task.id)
        .first()
    )
    return _task_to_response(task, db)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = data.model_dump(exclude_unset=True)

    if "status" in update_data and update_data["status"] not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Status must be one of: {', '.join(VALID_STATUSES)}",
        )

    if "related_entity_type" in update_data:
        if update_data["related_entity_type"] and update_data["related_entity_type"] not in VALID_ENTITY_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"related_entity_type must be one of: {', '.join(VALID_ENTITY_TYPES)}",
            )

    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    task = (
        db.query(Task)
        .options(
            joinedload(Task.job).joinedload(Job.contact),
            joinedload(Task.assigned_to),
        )
        .filter(Task.id == task.id)
        .first()
    )
    return _task_to_response(task, db)


@router.patch("/{task_id}/complete", response_model=TaskResponse)
def toggle_task_complete(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "completed" if task.status == "open" else "open"
    db.commit()
    db.refresh(task)

    task = (
        db.query(Task)
        .options(
            joinedload(Task.job).joinedload(Job.contact),
            joinedload(Task.assigned_to),
        )
        .filter(Task.id == task.id)
        .first()
    )
    return _task_to_response(task, db)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
