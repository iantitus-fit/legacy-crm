from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.crew import Crew
from app.models.user import User
from app.schemas.crew import (
    CrewCreate,
    CrewListResponse,
    CrewMemberResponse,
    CrewResponse,
    CrewUpdate,
)
from app.utils.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/api/crews", tags=["crews"])


def _crew_to_response(crew: Crew) -> dict:
    return {
        "id": crew.id,
        "name": crew.name,
        "color": crew.color,
        "is_active": crew.is_active,
        "members": [
            CrewMemberResponse(
                id=m.id,
                full_name=m.full_name,
                color=m.color,
            )
            for m in crew.members
        ],
        "created_at": crew.created_at,
    }


@router.get("", response_model=CrewListResponse)
def list_crews(
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Crew).options(joinedload(Crew.members))
    count_query = db.query(Crew)

    if is_active is not None:
        query = query.filter(Crew.is_active == is_active)
        count_query = count_query.filter(Crew.is_active == is_active)

    total = count_query.count()
    items = (
        query.order_by(Crew.name.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    # Deduplicate due to joinedload
    seen = set()
    unique_items = []
    for c in items:
        if c.id not in seen:
            seen.add(c.id)
            unique_items.append(c)

    return CrewListResponse(
        items=[_crew_to_response(c) for c in unique_items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{crew_id}", response_model=CrewResponse)
def get_crew(
    crew_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    crew = (
        db.query(Crew)
        .options(joinedload(Crew.members))
        .filter(Crew.id == crew_id)
        .first()
    )
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")
    return _crew_to_response(crew)


@router.post("", response_model=CrewResponse, status_code=201)
def create_crew(
    data: CrewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = db.query(Crew).filter(Crew.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Crew name already exists")

    crew = Crew(name=data.name, color=data.color)

    if data.member_ids:
        members = db.query(User).filter(User.id.in_(data.member_ids)).all()
        crew.members = members

    db.add(crew)
    db.commit()
    db.refresh(crew)

    crew = (
        db.query(Crew)
        .options(joinedload(Crew.members))
        .filter(Crew.id == crew.id)
        .first()
    )
    return _crew_to_response(crew)


@router.put("/{crew_id}", response_model=CrewResponse)
def update_crew(
    crew_id: int,
    data: CrewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    crew = (
        db.query(Crew)
        .options(joinedload(Crew.members))
        .filter(Crew.id == crew_id)
        .first()
    )
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"] != crew.name:
        existing = db.query(Crew).filter(Crew.name == update_data["name"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Crew name already exists")
        crew.name = update_data["name"]

    if "color" in update_data:
        crew.color = update_data["color"]

    if "is_active" in update_data:
        crew.is_active = update_data["is_active"]

    if "member_ids" in update_data:
        if update_data["member_ids"] is not None:
            members = db.query(User).filter(User.id.in_(update_data["member_ids"])).all()
            crew.members = members
        else:
            crew.members = []

    db.commit()
    db.refresh(crew)

    crew = (
        db.query(Crew)
        .options(joinedload(Crew.members))
        .filter(Crew.id == crew.id)
        .first()
    )
    return _crew_to_response(crew)


@router.delete("/{crew_id}", status_code=204)
def delete_crew(
    crew_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    crew = db.query(Crew).filter(Crew.id == crew_id).first()
    if not crew:
        raise HTTPException(status_code=404, detail="Crew not found")

    crew.is_active = False
    db.commit()
