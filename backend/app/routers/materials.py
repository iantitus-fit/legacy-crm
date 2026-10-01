import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.material import Material
from app.models.price_list import PriceList
from app.models.user import User
from app.schemas.material import (
    CategoryCount,
    MaterialCreate,
    MaterialImportResponse,
    MaterialListResponse,
    MaterialResponse,
    MaterialUpdate,
)
from app.services.material_import import import_materials_csv
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/materials", tags=["materials"])


def _material_to_response(mat: Material) -> dict:
    return {
        "id": mat.id,
        "price_list_id": mat.price_list_id,
        "item_number": mat.item_number,
        "description": mat.description,
        "unit_price": mat.unit_price,
        "uom": mat.uom,
        "category": mat.category,
        "ocr_flag": mat.ocr_flag,
        "is_active": mat.is_active,
        "created_at": mat.created_at,
        "updated_at": mat.updated_at,
        "price_list_name": mat.price_list.name if mat.price_list else None,
    }


@router.get("/categories", response_model=List[CategoryCount])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Material.category, func.count(Material.id))
        .filter(Material.is_active == True)
        .group_by(Material.category)
        .order_by(Material.category)
        .all()
    )
    return [CategoryCount(category=cat, count=cnt) for cat, cnt in rows]


@router.post("/import", response_model=MaterialImportResponse)
def import_materials(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpfile = tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", mode="wb"
    )
    try:
        content = file.file.read()
        tmpfile.write(content)
        tmpfile.close()

        result = import_materials_csv(
            db,
            tmpfile.name,
            source_file=file.filename,
            user_id=current_user.id,
        )
        return MaterialImportResponse(**result)
    finally:
        os.unlink(tmpfile.name)


@router.get("", response_model=MaterialListResponse)
def list_materials(
    search: Optional[str] = Query(None, description="Search item_number or description"),
    category: Optional[str] = Query(None),
    price_list_id: Optional[int] = Query(None),
    flagged: Optional[str] = Query(None, description="Set to 'true' to show only OCR-flagged items"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Material).options(joinedload(Material.price_list))
    query = query.filter(Material.is_active == True)

    if search:
        sf = f"%{search}%"
        query = query.filter(
            or_(
                Material.item_number.ilike(sf),
                Material.description.ilike(sf),
            )
        )

    if category:
        query = query.filter(Material.category == category)

    if price_list_id:
        query = query.filter(Material.price_list_id == price_list_id)

    if flagged and flagged.lower() == "true":
        query = query.filter(Material.ocr_flag.isnot(None))

    total = query.count()
    materials = (
        query.order_by(Material.category, Material.description)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return MaterialListResponse(
        items=[_material_to_response(m) for m in materials],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{material_id}", response_model=MaterialResponse)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mat = (
        db.query(Material)
        .options(joinedload(Material.price_list))
        .filter(Material.id == material_id)
        .first()
    )
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    return _material_to_response(mat)


@router.post("", response_model=MaterialResponse, status_code=201)
def create_material(
    data: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pl = db.query(PriceList).filter(PriceList.id == data.price_list_id).first()
    if not pl:
        raise HTTPException(status_code=400, detail="Price list not found")

    mat = Material(**data.model_dump())
    db.add(mat)
    db.commit()
    db.refresh(mat)

    mat = (
        db.query(Material)
        .options(joinedload(Material.price_list))
        .filter(Material.id == mat.id)
        .first()
    )
    return _material_to_response(mat)


@router.put("/{material_id}", response_model=MaterialResponse)
def update_material(
    material_id: int,
    data: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mat, field, value)

    db.commit()
    db.refresh(mat)

    mat = (
        db.query(Material)
        .options(joinedload(Material.price_list))
        .filter(Material.id == mat.id)
        .first()
    )
    return _material_to_response(mat)


@router.delete("/{material_id}", status_code=204)
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    mat.is_active = False
    db.commit()
