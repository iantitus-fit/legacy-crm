import os
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.contact import Contact
from app.models.document import Document
from app.models.estimate import Estimate
from app.models.job import Job
from app.models.user import User
from app.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    FolderListResponse,
    FolderSummary,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Image types include HEIC/HEIF/WEBP so iPhone job-site photos upload directly.
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/heic",
    "image/heif",
    "image/webp",
    "image/gif",
    "text/xml",
    "application/xml",
}

# 20MB matches the prior production limit; spec asked for 10MB but raising the
# floor would regress an already-shipped behavior. Spec's risk note explicitly
# permits going up to 25MB.
MAX_FILE_SIZE = 20 * 1024 * 1024


def _get_upload_dir() -> Path:
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _serialize(doc: Document, db: Session) -> DocumentResponse:
    uploader_name: Optional[str] = None
    if doc.uploaded_by:
        user = db.query(User).filter(User.id == doc.uploaded_by).first()
        if user:
            uploader_name = user.full_name
    data = DocumentResponse.model_validate(doc).model_dump()
    data["uploader_name"] = uploader_name
    return DocumentResponse(**data)


def _scope_query(
    query,
    *,
    job_id: Optional[int],
    contact_id: Optional[int],
    estimate_id: Optional[int],
):
    """Apply polymorphic entity filter to a Document query.

    Precedence: estimate_id → contact_id (with legacy job dual-lookup) →
    job_id. Returns the original query unchanged when no entity is given.
    """
    if estimate_id is not None:
        return query.filter(Document.estimate_id == estimate_id)
    if contact_id is not None:
        return query.outerjoin(Job, Document.job_id == Job.id).filter(
            or_(
                Document.contact_id == contact_id,
                Job.contact_id == contact_id,
            )
        )
    if job_id is not None:
        return query.filter(Document.job_id == job_id)
    return query


@router.get("", response_model=DocumentListResponse)
def list_documents(
    job_id: Optional[int] = Query(None),
    contact_id: Optional[int] = Query(None),
    estimate_id: Optional[int] = Query(None),
    folder: Optional[str] = Query(None),
    is_photo: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _scope_query(
        db.query(Document),
        job_id=job_id,
        contact_id=contact_id,
        estimate_id=estimate_id,
    )

    if folder is not None:
        query = query.filter(Document.folder == folder)
    if is_photo is not None:
        query = query.filter(Document.is_photo == is_photo)

    docs = query.order_by(Document.created_at.desc()).all()
    items = [_serialize(d, db) for d in docs]
    return DocumentListResponse(items=items, total=len(items))


@router.get("/folders", response_model=FolderListResponse)
def list_folders(
    job_id: Optional[int] = Query(None),
    contact_id: Optional[int] = Query(None),
    estimate_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if job_id is None and contact_id is None and estimate_id is None:
        raise HTTPException(
            status_code=400,
            detail="One of job_id, contact_id, or estimate_id is required",
        )

    base = _scope_query(
        db.query(
            Document.folder.label("folder"),
            func.count(Document.id).label("file_count"),
            func.sum(case((Document.is_photo == True, 1), else_=0)).label(  # noqa: E712
                "photo_count"
            ),
        ),
        job_id=job_id,
        contact_id=contact_id,
        estimate_id=estimate_id,
    )

    rows = base.group_by(Document.folder).order_by(Document.folder.asc()).all()
    items = [
        FolderSummary(
            name=row.folder or "General",
            file_count=int(row.file_count or 0),
            photo_count=int(row.photo_count or 0),
        )
        for row in rows
    ]
    total_files = sum(item.file_count for item in items)
    return FolderListResponse(items=items, total_files=total_files)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return _serialize(doc, db)


@router.post("", response_model=List[DocumentResponse], status_code=201)
def upload_documents(
    job_id: Optional[int] = Form(None),
    contact_id: Optional[int] = Form(None),
    estimate_id: Optional[int] = Form(None),
    folder: str = Form("General"),
    description: Optional[str] = Form(None),
    show_in_work_order: bool = Form(False),
    show_in_estimate: bool = Form(False),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Exactly one entity per upload. Existing dual-linked rows still
    # work — we just no longer create new ones.
    targets = [t for t in (contact_id, job_id, estimate_id) if t is not None]
    if not targets:
        raise HTTPException(
            status_code=400,
            detail="One of job_id, contact_id, or estimate_id is required",
        )
    if len(targets) > 1:
        raise HTTPException(
            status_code=400,
            detail="A file can attach to only one of job, contact, or estimate",
        )

    if contact_id is not None:
        if not db.query(Contact).filter(Contact.id == contact_id).first():
            raise HTTPException(status_code=400, detail="Contact not found")
    if job_id is not None:
        if not db.query(Job).filter(Job.id == job_id).first():
            raise HTTPException(status_code=400, detail="Job not found")
    if estimate_id is not None:
        if not db.query(Estimate).filter(Estimate.id == estimate_id).first():
            raise HTTPException(status_code=400, detail="Estimate not found")

    upload_dir = _get_upload_dir()
    documents: List[Document] = []

    for file in files:
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{file.content_type}' not allowed. "
                f"Allowed: PDF, PNG, JPG, HEIC, WEBP, GIF, XML",
            )

        content = file.file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' exceeds {MAX_FILE_SIZE // (1024 * 1024)} MB limit",
            )

        ext = Path(file.filename).suffix if file.filename else ""
        stored_filename = f"{uuid.uuid4()}{ext}"
        file_path = upload_dir / stored_filename

        with open(file_path, "wb") as f:
            f.write(content)

        is_photo = (file.content_type or "").startswith("image/")

        doc = Document(
            job_id=job_id,
            contact_id=contact_id,
            estimate_id=estimate_id,
            filename=stored_filename,
            original_filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            file_size=len(content),
            folder=folder or "General",
            description=description,
            is_photo=is_photo,
            show_in_work_order=show_in_work_order,
            show_in_estimate=show_in_estimate,
            uploaded_by=current_user.id,
        )
        db.add(doc)
        documents.append(doc)

    db.commit()
    for doc in documents:
        db.refresh(doc)

    return [_serialize(d, db) for d in documents]


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(doc, field, value)

    db.commit()
    db.refresh(doc)
    return _serialize(doc, db)


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(settings.upload_dir) / doc.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=str(file_path),
        media_type=doc.content_type,
        filename=doc.original_filename,
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(settings.upload_dir) / doc.filename
    if file_path.exists():
        os.remove(file_path)

    db.delete(doc)
    db.commit()
