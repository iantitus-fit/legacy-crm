from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.employee import (
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeResponse,
    EmployeeUpdate,
)
from app.utils.auth import hash_password
from app.utils.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/api/employees", tags=["employees"])

VALID_ROLES = {"admin", "staff", "crew"}


def _user_to_response(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "phone": user.phone,
        "color": user.color,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(User)
    count_query = db.query(User)

    if search:
        like = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(like)) | (User.email.ilike(like))
        )
        count_query = count_query.filter(
            (User.full_name.ilike(like)) | (User.email.ilike(like))
        )

    if role:
        query = query.filter(User.role == role)
        count_query = count_query.filter(User.role == role)

    if is_active is not None:
        query = query.filter(User.is_active == is_active)
        count_query = count_query.filter(User.is_active == is_active)

    total = count_query.count()
    items = (
        query.order_by(User.full_name.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return EmployeeListResponse(
        items=[_user_to_response(u) for u in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")
    return _user_to_response(user)


@router.post("", response_model=EmployeeResponse, status_code=201)
def create_employee(
    data: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if data.role and data.role not in VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Role must be one of: {', '.join(VALID_ROLES)}",
        )

    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role or "staff",
        phone=data.phone,
        color=data.color,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_to_response(user)


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    update_data = data.model_dump(exclude_unset=True)

    if "role" in update_data and update_data["role"] not in VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Role must be one of: {', '.join(VALID_ROLES)}",
        )

    if "email" in update_data and update_data["email"] != user.email:
        existing = db.query(User).filter(User.email == update_data["email"]).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return _user_to_response(user)


@router.delete("/{employee_id}", status_code=204)
def delete_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == employee_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Employee not found")

    user.is_active = False
    db.commit()
