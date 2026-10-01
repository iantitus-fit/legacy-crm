"""Expiry for public portal links (estimates, change orders, work orders).

Links never expire unless PORTAL_LINK_DAYS is set. When it is, every newly
minted link gets an expires_at that many days out, and every public lookup
refuses an expired link with 410 Gone.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException

from app.config import settings


def link_expiry() -> Optional[datetime]:
    """expires_at for a link minted now, or None when links do not expire."""
    days = settings.portal_link_days
    if not days:
        return None
    return datetime.now(timezone.utc) + timedelta(days=days)


def is_expired(expires_at: Optional[datetime]) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:  # SQLite hands back naive datetimes
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def ensure_not_expired(record) -> None:
    if is_expired(getattr(record, "expires_at", None)):
        raise HTTPException(
            status_code=410,
            detail="This link has expired. Ask us to send a new one.",
        )
