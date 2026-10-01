from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
from app.models.user import User
from app.schemas.estimate_template import (
    PreviewRequest,
    PreviewResponse,
    TemplateCreate,
    TemplateItemCreate,
    TemplateItemReorder,
    TemplateItemResponse,
    TemplateItemUpdate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.services.template_calculator import calculate_template_preview
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/estimate-templates", tags=["estimate-templates"])


def _template_to_response(tmpl: EstimateTemplate) -> dict:
    """Convert an EstimateTemplate ORM object to a response dict."""
    items_sorted = sorted(tmpl.items, key=lambda i: i.sort_order)
    items = [
        {
            "id": item.id,
            "template_id": item.template_id,
            "material_id": item.material_id,
            "description": item.description,
            "category": item.category,
            "unit_cost": item.unit_cost,
            "uom": item.uom,
            "margin_pct": item.margin_pct,
            "waste_pct": item.waste_pct,
            "measurement_type": item.measurement_type,
            "conversion_factor": item.conversion_factor,
            "default_qty": item.default_qty,
            "sort_order": item.sort_order,
        }
        for item in items_sorted
    ]
    return {
        "id": tmpl.id,
        "name": tmpl.name,
        "description": tmpl.description,
        "default_margin_pct": tmpl.default_margin_pct,
        "default_waste_pct": tmpl.default_waste_pct,
        "is_active": tmpl.is_active,
        "created_at": tmpl.created_at,
        "updated_at": tmpl.updated_at,
        "items": items,
        "item_count": len(items),
    }


def _item_to_response(item: EstimateTemplateItem) -> dict:
    """Convert an EstimateTemplateItem ORM object to a response dict."""
    return {
        "id": item.id,
        "template_id": item.template_id,
        "material_id": item.material_id,
        "description": item.description,
        "category": item.category,
        "unit_cost": item.unit_cost,
        "uom": item.uom,
        "margin_pct": item.margin_pct,
        "waste_pct": item.waste_pct,
        "measurement_type": item.measurement_type,
        "conversion_factor": item.conversion_factor,
        "default_qty": item.default_qty,
        "sort_order": item.sort_order,
    }


def _get_template_or_404(
    db: Session, template_id: int
) -> EstimateTemplate:
    """Fetch a template with items eagerly loaded, or raise 404."""
    tmpl = (
        db.query(EstimateTemplate)
        .options(joinedload(EstimateTemplate.items))
        .filter(
            EstimateTemplate.id == template_id,
            EstimateTemplate.is_active == True,
        )
        .first()
    )
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tmpl


# ---- Template CRUD ----


@router.get("", response_model=TemplateListResponse)
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    templates = (
        db.query(EstimateTemplate)
        .options(joinedload(EstimateTemplate.items))
        .filter(EstimateTemplate.is_active == True)
        .order_by(EstimateTemplate.name)
        .all()
    )
    return TemplateListResponse(
        items=[_template_to_response(t) for t in templates],
        total=len(templates),
    )


@router.post("", response_model=TemplateResponse, status_code=201)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check for duplicate name
    existing = (
        db.query(EstimateTemplate)
        .filter(EstimateTemplate.name == data.name, EstimateTemplate.is_active == True)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="A template with this name already exists")

    tmpl = EstimateTemplate(**data.model_dump())
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)

    # Re-fetch with items eagerly loaded
    tmpl = _get_template_or_404(db, tmpl.id)
    return _template_to_response(tmpl)


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = _get_template_or_404(db, template_id)
    return _template_to_response(tmpl)


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = _get_template_or_404(db, template_id)

    update_data = data.model_dump(exclude_unset=True)

    # Check duplicate name if name is being changed
    if "name" in update_data and update_data["name"] != tmpl.name:
        existing = (
            db.query(EstimateTemplate)
            .filter(
                EstimateTemplate.name == update_data["name"],
                EstimateTemplate.is_active == True,
                EstimateTemplate.id != template_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="A template with this name already exists")

    for field, value in update_data.items():
        setattr(tmpl, field, value)

    db.commit()
    db.refresh(tmpl)
    tmpl = _get_template_or_404(db, tmpl.id)
    return _template_to_response(tmpl)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = _get_template_or_404(db, template_id)
    tmpl.is_active = False
    db.commit()


# ---- Duplicate ----


@router.post("/{template_id}/duplicate", response_model=TemplateResponse, status_code=201)
def duplicate_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = _get_template_or_404(db, template_id)

    new_tmpl = EstimateTemplate(
        name=f"{source.name} (Copy)",
        description=source.description,
        default_margin_pct=source.default_margin_pct,
        default_waste_pct=source.default_waste_pct,
    )
    db.add(new_tmpl)
    db.flush()  # Get the new ID

    for item in sorted(source.items, key=lambda i: i.sort_order):
        new_item = EstimateTemplateItem(
            template_id=new_tmpl.id,
            material_id=item.material_id,
            description=item.description,
            category=item.category,
            unit_cost=item.unit_cost,
            uom=item.uom,
            margin_pct=item.margin_pct,
            waste_pct=item.waste_pct,
            measurement_type=item.measurement_type,
            conversion_factor=item.conversion_factor,
            default_qty=item.default_qty,
            sort_order=item.sort_order,
        )
        db.add(new_item)

    db.commit()
    db.refresh(new_tmpl)
    new_tmpl = _get_template_or_404(db, new_tmpl.id)
    return _template_to_response(new_tmpl)


# ---- Items ----


@router.put("/{template_id}/items/reorder", response_model=TemplateResponse)
def reorder_items(
    template_id: int,
    data: TemplateItemReorder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = _get_template_or_404(db, template_id)

    # Map items by ID for quick lookup
    item_map = {item.id: item for item in tmpl.items}

    for idx, item_id in enumerate(data.item_ids):
        if item_id in item_map:
            item_map[item_id].sort_order = idx

    db.commit()
    db.refresh(tmpl)
    tmpl = _get_template_or_404(db, tmpl.id)
    return _template_to_response(tmpl)


@router.post("/{template_id}/items", response_model=TemplateItemResponse, status_code=201)
def add_item(
    template_id: int,
    data: TemplateItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = _get_template_or_404(db, template_id)

    item_data = data.model_dump()

    # Inherit defaults from template if not specified
    if item_data.get("margin_pct") is None:
        item_data["margin_pct"] = tmpl.default_margin_pct
    if item_data.get("waste_pct") is None:
        item_data["waste_pct"] = tmpl.default_waste_pct

    # Auto-assign sort_order if not specified
    if item_data.get("sort_order") is None:
        max_order = max((i.sort_order for i in tmpl.items), default=-1)
        item_data["sort_order"] = max_order + 1

    item = EstimateTemplateItem(template_id=template_id, **item_data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_to_response(item)


@router.put(
    "/{template_id}/items/{item_id}", response_model=TemplateItemResponse
)
def update_item(
    template_id: int,
    item_id: int,
    data: TemplateItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify template exists
    _get_template_or_404(db, template_id)

    item = (
        db.query(EstimateTemplateItem)
        .filter(
            EstimateTemplateItem.id == item_id,
            EstimateTemplateItem.template_id == template_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return _item_to_response(item)


@router.delete("/{template_id}/items/{item_id}", status_code=204)
def delete_item(
    template_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify template exists
    _get_template_or_404(db, template_id)

    item = (
        db.query(EstimateTemplateItem)
        .filter(
            EstimateTemplateItem.id == item_id,
            EstimateTemplateItem.template_id == template_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(item)
    db.commit()


# ---- Preview ----


@router.post("/{template_id}/preview", response_model=PreviewResponse)
def preview_template(
    template_id: int,
    data: PreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tmpl = _get_template_or_404(db, template_id)

    # Convert MeasurementsInput to a dict of non-None Decimal values
    measurements = {}
    m = data.measurements
    if m.total_area is not None:
        measurements["total_area"] = Decimal(str(m.total_area))
    if m.ridge is not None:
        measurements["ridge"] = Decimal(str(m.ridge))
    if m.hip is not None:
        measurements["hip"] = Decimal(str(m.hip))
    if m.valley is not None:
        measurements["valley"] = Decimal(str(m.valley))
    if m.eave is not None:
        measurements["eave"] = Decimal(str(m.eave))
    if m.rake is not None:
        measurements["rake"] = Decimal(str(m.rake))

    # Convert template items to dicts for the calculator
    item_dicts = [
        {
            "description": item.description,
            "category": item.category,
            "unit_cost": item.unit_cost,
            "uom": item.uom,
            "margin_pct": item.margin_pct,
            "waste_pct": item.waste_pct,
            "measurement_type": item.measurement_type,
            "conversion_factor": item.conversion_factor,
            "default_qty": item.default_qty,
        }
        for item in sorted(tmpl.items, key=lambda i: i.sort_order)
    ]

    result = calculate_template_preview(item_dicts, measurements)
    return result
