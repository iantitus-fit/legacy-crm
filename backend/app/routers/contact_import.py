from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contact_import import ContactImport
from app.models.user import User
from app.schemas.contact_import import (
    ImportConfirmRequest,
    ImportConfirmResponse,
    ImportHistoryItem,
    ImportHistoryResponse,
    ImportPreviewResponse,
    ImportUndoResponse,
)
from app.services import contact_importer
from app.services.contact_importer import ImportError as ImporterError
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post(
    "/contacts/preview",
    response_model=ImportPreviewResponse,
)
async def preview_contact_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw = await file.read()
    try:
        columns, rows = contact_importer.parse_file(file.filename or "", raw)
        payload = contact_importer.build_preview(
            file_name=file.filename or "upload",
            columns=columns,
            rows=rows,
            db=db,
        )
    except ImporterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return {
        "file_name": payload["file_name"],
        "total_rows": payload["total_rows"],
        "importable_rows": payload["importable_rows"],
        "skipped_rows": payload["skipped_rows"],
        "skip_reasons": payload["skip_reasons"],
        "potential_duplicates": payload["potential_duplicates"],
        "columns_detected": payload["columns_detected"],
        "suggested_mappings": payload["suggested_mappings"],
        "unmapped_columns": payload["unmapped_columns"],
        "sample_rows": payload["sample_rows"],
        "warnings": payload["warnings"],
        "preview_token": payload["preview_token"],
    }


@router.post(
    "/contacts/confirm",
    response_model=ImportConfirmResponse,
)
def confirm_contact_import(
    body: ImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        record = contact_importer.confirm_import(
            db=db,
            user_id=current_user.id,
            preview_token=body.preview_token,
            field_mappings=body.field_mappings or {},
            options=body.options.model_dump(),
        )
    except ImporterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return ImportConfirmResponse(
        imported=record.imported_count,
        skipped_duplicates=getattr(record, "_skipped_duplicates", 0),
        skipped_invalid=record.skipped_count,
        total_processed=record.total_rows,
        import_id=record.id,
        duration_seconds=record.duration_seconds or 0.0,
    )


@router.get("/history", response_model=ImportHistoryResponse)
def list_import_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = db.query(ContactImport).order_by(ContactImport.created_at.desc())
    total = base.count()
    rows = base.offset((page - 1) * per_page).limit(per_page).all()

    user_ids = {r.user_id for r in rows if r.user_id is not None}
    user_names: dict = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_names = {u.id: u.full_name for u in users}

    items = [
        ImportHistoryItem(
            import_id=r.id,
            user_id=r.user_id,
            user_name=user_names.get(r.user_id) if r.user_id else None,
            file_name=r.file_name,
            total_rows=r.total_rows,
            imported_count=r.imported_count,
            skipped_count=r.skipped_count,
            duplicate_count=r.duplicate_count,
            duration_seconds=r.duration_seconds,
            created_at=r.created_at,
            undone_at=r.undone_at,
        )
        for r in rows
    ]
    return ImportHistoryResponse(items=items, total=total)


@router.post(
    "/contacts/{import_id}/undo",
    response_model=ImportUndoResponse,
)
def undo_contact_import(
    import_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        affected = contact_importer.undo_import(db, import_id)
    except ImporterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))

    return ImportUndoResponse(import_id=import_id, soft_deleted=affected)
