from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.job import Job
from app.models.note import Note
from app.models.user import User
from app.schemas.note import (
    NoteCreate,
    NoteListResponse,
    NoteResponse,
    NoteUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/notes", tags=["notes"])

VALID_ENTITY_TYPES = {"job", "contact", "estimate"}
VALID_NOTE_TYPES = {"crew", "client", "company"}


def _note_to_response(note: Note) -> dict:
    """Build a NoteResponse dict with created_by_name."""
    created_by_name = None
    if note.created_by:
        created_by_name = note.created_by.full_name
    return {
        "id": note.id,
        "entity_type": note.entity_type,
        "entity_id": note.entity_id,
        "note_type": note.note_type,
        "content": note.content,
        "created_by_user_id": note.created_by_user_id,
        "created_by_name": created_by_name,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


def _validate_entity_exists(db: Session, entity_type: str, entity_id: int):
    """Check that the referenced entity exists."""
    if entity_type == "job":
        if not db.query(Job).filter(Job.id == entity_id).first():
            raise HTTPException(status_code=400, detail="Job not found")
    elif entity_type == "contact":
        if not db.query(Contact).filter(Contact.id == entity_id).first():
            raise HTTPException(status_code=400, detail="Contact not found")
    elif entity_type == "estimate":
        if not db.query(Estimate).filter(Estimate.id == entity_id).first():
            raise HTTPException(status_code=400, detail="Estimate not found")


@router.get("", response_model=NoteListResponse)
def list_notes(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    note_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Note).options(joinedload(Note.created_by))
    count_query = db.query(Note)

    if entity_type is not None:
        query = query.filter(Note.entity_type == entity_type)
        count_query = count_query.filter(Note.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(Note.entity_id == entity_id)
        count_query = count_query.filter(Note.entity_id == entity_id)
    if note_type is not None:
        query = query.filter(Note.note_type == note_type)
        count_query = count_query.filter(Note.note_type == note_type)

    total = count_query.count()

    items = (
        query.order_by(Note.created_at.desc(), Note.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return NoteListResponse(
        items=[_note_to_response(n) for n in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=NoteResponse, status_code=201)
def create_note(
    data: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"entity_type must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}",
        )
    if data.note_type not in VALID_NOTE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"note_type must be one of: {', '.join(sorted(VALID_NOTE_TYPES))}",
        )

    _validate_entity_exists(db, data.entity_type, data.entity_id)

    note = Note(
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        note_type=data.note_type,
        content=data.content,
        created_by_user_id=current_user.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    note = (
        db.query(Note)
        .options(joinedload(Note.created_by))
        .filter(Note.id == note.id)
        .first()
    )
    return _note_to_response(note)


@router.put("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int,
    data: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if note.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the author can edit this note")

    note.content = data.content
    db.commit()
    db.refresh(note)

    note = (
        db.query(Note)
        .options(joinedload(Note.created_by))
        .filter(Note.id == note.id)
        .first()
    )
    return _note_to_response(note)


@router.delete("/{note_id}", status_code=204)
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    if note.created_by_user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only the author or admin can delete this note")

    db.delete(note)
    db.commit()
