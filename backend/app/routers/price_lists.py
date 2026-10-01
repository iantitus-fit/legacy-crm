from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.material import Material
from app.models.price_list import PriceList
from app.models.user import User
from app.schemas.price_list import (
    PriceListListResponse,
    PriceListResponse,
    PriceListUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/price-lists", tags=["price-lists"])


@router.get("", response_model=PriceListListResponse)
def list_price_lists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pls = db.query(PriceList).order_by(PriceList.name).all()
    items = []
    for pl in pls:
        count = (
            db.query(func.count(Material.id))
            .filter(Material.price_list_id == pl.id, Material.is_active == True)
            .scalar()
        )
        items.append(
            PriceListResponse(
                id=pl.id,
                name=pl.name,
                source_file=pl.source_file,
                effective_date=pl.effective_date,
                expiration_date=pl.expiration_date,
                imported_at=pl.imported_at,
                imported_by_user_id=pl.imported_by_user_id,
                material_count=count,
            )
        )

    return PriceListListResponse(items=items, total=len(items))


@router.put("/{price_list_id}", response_model=PriceListResponse)
def update_price_list(
    price_list_id: int,
    data: PriceListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pl = db.query(PriceList).filter(PriceList.id == price_list_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Price list not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pl, field, value)

    db.commit()
    db.refresh(pl)

    count = (
        db.query(func.count(Material.id))
        .filter(Material.price_list_id == pl.id, Material.is_active == True)
        .scalar()
    )

    return PriceListResponse(
        id=pl.id,
        name=pl.name,
        source_file=pl.source_file,
        effective_date=pl.effective_date,
        expiration_date=pl.expiration_date,
        imported_at=pl.imported_at,
        imported_by_user_id=pl.imported_by_user_id,
        material_count=count,
    )
