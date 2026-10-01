"""Admin endpoints for previewing and triggering the morning briefing."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.briefing_sender import VALID_RECIPIENTS, send_morning_briefing
from app.utils.dependencies import require_admin

router = APIRouter(prefix="/api/admin/briefing", tags=["briefing-admin"])


class SendRequest(BaseModel):
    recipient: Literal["dale", "marcus", "all"] = "all"
    dry_run: bool = False


@router.post("/send")
def send(
    body: SendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Send (or preview) the morning briefing."""
    return send_morning_briefing(db=db, recipient=body.recipient, dry_run=body.dry_run)


@router.get("/preview", response_class=HTMLResponse)
def preview(
    recipient: str = Query(default="dale"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Render the briefing HTML for the given recipient and return it directly.

    Open this in a browser to see exactly what the email will look like.
    """
    if recipient not in VALID_RECIPIENTS or recipient == "all":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="recipient must be 'dale' or 'marcus'",
        )
    result = send_morning_briefing(db=db, recipient=recipient, dry_run=True)
    previews = result.get("previews", [])
    if not previews:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="briefing renderer produced no output",
        )
    return HTMLResponse(content=previews[0]["html"], status_code=200)
