"""Sprint 18a — Reports router."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.reports import (
    LeadSourceReportResponse,
    LeadSourceSummaryResponse,
)
from app.services import reports as reports_service
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])

_VALID_PERIODS = {"all", "30d", "90d", "ytd", "custom"}


@router.get("/lead-sources", response_model=LeadSourceReportResponse)
def lead_source_report(
    period: str = Query("all"),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Must be one of {sorted(_VALID_PERIODS)}.",
        )
    if period == "custom" and (start_date is None or end_date is None):
        raise HTTPException(
            status_code=400,
            detail="period=custom requires start_date and end_date.",
        )
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be on or before end_date.",
        )
    return reports_service.get_lead_source_report(
        db, period=period, start_date=start_date, end_date=end_date
    )


@router.get("/lead-sources/summary", response_model=LeadSourceSummaryResponse)
def lead_source_summary(
    period: str = Query("30d"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid period. Must be one of {sorted(_VALID_PERIODS)}.",
        )
    if period == "custom":
        raise HTTPException(
            status_code=400,
            detail="summary endpoint does not support period=custom; "
            "use the full /lead-sources endpoint with date params.",
        )
    return reports_service.get_lead_source_summary(db, period=period)
