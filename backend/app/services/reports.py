"""Sprint 18a — Lead source attribution reporting.

Aggregates lead source metrics by joining contacts through jobs/estimates/
invoices/payments. Lead source lives on the contact; all downstream entities
trace back via job.contact_id.

Period filtering:
  - Lead counts and pipeline metrics are filtered by contact.created_at.
  - Revenue metrics (invoiced, collected) are filtered by the relevant date
    on the financial record (invoice.date_invoiced, payment.date_received),
    independent of when the lead came in. This prevents a Q1 lead with a Q2
    invoice from inflating Q1 numbers when the period is set to Q1.
  - Period "all" applies no date filter.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.payment import Payment
from app.models.pipeline import Pipeline


UNATTRIBUTED_LABEL = "Unattributed"


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------
def resolve_period(
    period: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    now: Optional[date] = None,
) -> Tuple[Optional[date], Optional[date]]:
    """Convert a period code into a (start, end) date range.

    Returns (None, None) for the "all" period — caller skips date filtering.
    """
    today = now or datetime.now(timezone.utc).date()
    if period == "all":
        return None, None
    if period == "30d":
        return today - timedelta(days=30), today
    if period == "90d":
        return today - timedelta(days=90), today
    if period == "ytd":
        return date(today.year, 1, 1), today
    if period == "custom":
        return start_date, end_date
    raise ValueError(f"Unknown period: {period!r}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _bucket_key(lead_source: Optional[str]) -> str:
    if not lead_source or not lead_source.strip():
        return UNATTRIBUTED_LABEL
    return lead_source.strip()


def _within(value: Optional[date], start: Optional[date], end: Optional[date]) -> bool:
    if value is None:
        return False
    if start is not None and value < start:
        return False
    if end is not None and value > end:
        return False
    return True


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _pipeline_slug_map(db: Session) -> Dict[int, str]:
    return {p.id: p.slug for p in db.query(Pipeline).all()}


# ---------------------------------------------------------------------------
# Main aggregator
# ---------------------------------------------------------------------------
def get_lead_source_report(
    db: Session,
    period: str = "all",
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    *,
    now: Optional[date] = None,
) -> Dict[str, Any]:
    """Assemble the full lead source attribution report."""
    range_start, range_end = resolve_period(period, start_date, end_date, now=now)
    pipeline_slugs = _pipeline_slug_map(db)

    # Contacts filtered by created_at if a range is set.
    contact_q = db.query(Contact).filter(Contact.deleted_at.is_(None))
    contacts_in_range: List[Contact] = []
    contacts_all: List[Contact] = contact_q.all()
    for c in contacts_all:
        created = _as_date(c.created_at)
        if range_start or range_end:
            if _within(created, range_start, range_end):
                contacts_in_range.append(c)
        else:
            contacts_in_range.append(c)

    in_range_ids = {c.id for c in contacts_in_range}

    # Per-source accumulators
    sources: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "lead_count": 0,
            "estimate_count": 0,
            "approved_count": 0,
            "approved_estimate_ids": [],
            "total_contract_value": 0.0,
            "total_invoiced": 0.0,
            "total_collected": 0.0,
            "days_to_close": [],
            "pipeline_breakdown": defaultdict(int),
        }
    )

    # Map contact_id -> bucket key for downstream lookups.
    contact_bucket: Dict[int, str] = {c.id: _bucket_key(c.lead_source) for c in contacts_all}

    # Lead counts and pipeline_breakdown (leads/sales): based on the filtered
    # set of contacts. Contacts placed in the Leads pipeline count toward
    # "leads"; Sales pipeline counts toward "sales".
    for c in contacts_in_range:
        bucket = _bucket_key(c.lead_source)
        bag = sources[bucket]
        bag["lead_count"] += 1
        if c.pipeline_id and c.pipeline_id in pipeline_slugs:
            slug = pipeline_slugs[c.pipeline_id]
            if slug in ("leads", "sales"):
                bag["pipeline_breakdown"][slug] += 1

    # Estimates: trace through jobs to contacts.
    # estimate_count = estimates whose contact is in the filtered contact set
    # approved_count + total_contract_value = estimates where status='approved'
    # avg_days_to_close = mean(approved_at - contact.created_at) in days
    est_rows = (
        db.query(Estimate, Job, Contact)
        .join(Job, Job.id == Estimate.job_id)
        .join(Contact, Contact.id == Job.contact_id)
        .filter(Contact.deleted_at.is_(None))
        .all()
    )
    for est, job, contact in est_rows:
        if contact.id not in in_range_ids:
            continue
        bucket = contact_bucket[contact.id]
        bag = sources[bucket]
        bag["estimate_count"] += 1
        if est.status == "approved":
            bag["approved_count"] += 1
            bag["approved_estimate_ids"].append(est.id)
            bag["total_contract_value"] += _to_float(est.total)
            if est.approved_at and contact.created_at:
                approved_d = _as_date(est.approved_at)
                created_d = _as_date(contact.created_at)
                if approved_d and created_d:
                    delta = (approved_d - created_d).days
                    if delta >= 0:
                        bag["days_to_close"].append(delta)
            # Jobs pipeline breakdown: count approved estimates whose
            # estimate.pipeline_id points at the jobs pipeline.
            if est.pipeline_id and pipeline_slugs.get(est.pipeline_id) == "jobs":
                bag["pipeline_breakdown"]["jobs"] += 1

    # Invoices: trace via jobs to contacts. Revenue metrics use the
    # invoice's own date if a date range was specified.
    inv_rows = (
        db.query(Invoice, Job, Contact)
        .join(Job, Job.id == Invoice.job_id)
        .join(Contact, Contact.id == Job.contact_id)
        .filter(Contact.deleted_at.is_(None))
        .filter(Invoice.status != "void")
        .all()
    )
    invoice_to_bucket: Dict[int, str] = {}
    for inv, job, contact in inv_rows:
        bucket = contact_bucket[contact.id]
        invoice_to_bucket[inv.id] = bucket
        if range_start or range_end:
            inv_date = _as_date(inv.date_invoiced) or _as_date(inv.created_at)
            if not _within(inv_date, range_start, range_end):
                continue
        # Use total when present; balance is informational only.
        sources[bucket]["total_invoiced"] += _to_float(inv.total)

    # Payments: filter by date_received.
    pay_rows = (
        db.query(Payment)
        .filter(Payment.invoice_id.in_(list(invoice_to_bucket.keys())))
        .all()
        if invoice_to_bucket
        else []
    )
    for pay in pay_rows:
        bucket = invoice_to_bucket.get(pay.invoice_id)
        if bucket is None:
            continue
        if range_start or range_end:
            if not _within(_as_date(pay.date_received), range_start, range_end):
                continue
        sources[bucket]["total_collected"] += _to_float(pay.amount)

    # Materialize the response shape.
    total_leads = sum(bag["lead_count"] for bucket, bag in sources.items())
    total_revenue = sum(bag["total_collected"] for bag in sources.values())

    rendered: List[Dict[str, Any]] = []
    unattributed_payload: Optional[Dict[str, Any]] = None

    for bucket_name, bag in sources.items():
        lead_count = bag["lead_count"]
        approved = bag["approved_count"]
        close_rate = (
            round((approved / lead_count) * 100, 2) if lead_count else 0.0
        )
        avg_value = (
            round(bag["total_contract_value"] / approved, 2) if approved else 0.0
        )
        lead_pct = (
            round((lead_count / total_leads) * 100, 2) if total_leads else 0.0
        )
        avg_days = (
            round(sum(bag["days_to_close"]) / len(bag["days_to_close"]), 1)
            if bag["days_to_close"]
            else None
        )
        payload = {
            "source": bucket_name,
            "lead_count": lead_count,
            "lead_percentage": lead_pct,
            "estimate_count": bag["estimate_count"],
            "approved_count": approved,
            "close_rate": close_rate,
            "total_contract_value": round(bag["total_contract_value"], 2),
            "avg_job_value": avg_value,
            "total_invoiced": round(bag["total_invoiced"], 2),
            "total_collected": round(bag["total_collected"], 2),
            "avg_days_to_close": avg_days,
            "pipeline_breakdown": {
                "leads": bag["pipeline_breakdown"].get("leads", 0),
                "sales": bag["pipeline_breakdown"].get("sales", 0),
                "jobs": bag["pipeline_breakdown"].get("jobs", 0),
            },
        }
        if bucket_name == UNATTRIBUTED_LABEL:
            unattributed_payload = {
                "lead_count": lead_count,
                "note": "Contacts with no lead_source value",
                **{k: v for k, v in payload.items() if k != "source"},
            }
        else:
            rendered.append(payload)

    # Sort by lead_count desc, then by source name for stability.
    rendered.sort(key=lambda r: (-r["lead_count"], r["source"]))

    return {
        "period": period,
        "start_date": range_start.isoformat() if range_start else None,
        "end_date": range_end.isoformat() if range_end else None,
        "total_leads": total_leads,
        "total_revenue": round(total_revenue, 2),
        "sources": rendered,
        "unattributed": unattributed_payload
        or {"lead_count": 0, "note": "Contacts with no lead_source value"},
    }


def get_lead_source_summary(
    db: Session,
    period: str = "30d",
    *,
    now: Optional[date] = None,
) -> Dict[str, Any]:
    """Lightweight summary for dashboard widgets — top sources by volume.

    Reuses the full report engine and projects only the fields the dashboard
    needs.
    """
    full = get_lead_source_report(db, period=period, now=now)
    projected = [
        {
            "source": s["source"],
            "lead_count": s["lead_count"],
            "close_rate": s["close_rate"],
            "avg_job_value": s["avg_job_value"],
        }
        for s in full["sources"]
    ]
    return {
        "period": period,
        "sources": projected,
        "total_leads": full["total_leads"],
    }


# ---------------------------------------------------------------------------
# Briefing helpers — used by ai_chat.get_briefing_context and the renderer
# ---------------------------------------------------------------------------
def get_lead_source_briefing_summary(
    db: Session, *, now: Optional[date] = None
) -> Dict[str, Any]:
    """Last-7-days new lead breakdown + top/lowest performers all-time.

    Used by the morning briefing and the AI panel global context.
    """
    today = now or datetime.now(timezone.utc).date()
    week_ago = today - timedelta(days=7)

    last7 = get_lead_source_report(
        db, period="custom", start_date=week_ago, end_date=today
    )
    new_leads_breakdown = [
        {"source": s["source"], "count": s["lead_count"]}
        for s in last7["sources"]
        if s["lead_count"] > 0
    ]
    if last7["unattributed"]["lead_count"] > 0:
        new_leads_breakdown.append(
            {
                "source": UNATTRIBUTED_LABEL,
                "count": last7["unattributed"]["lead_count"],
            }
        )

    all_time = get_lead_source_report(db, period="all")
    # "Top closer" — highest close_rate among sources with ≥3 leads to avoid
    # noisy single-lead sources dominating.
    eligible = [s for s in all_time["sources"] if s["lead_count"] >= 3]
    top = max(eligible, key=lambda s: s["close_rate"], default=None)
    # Lowest performer: filter the same way; sort ascending by close_rate.
    low = (
        min(eligible, key=lambda s: s["close_rate"], default=None)
        if eligible
        else None
    )
    # Don't show the same source as both top and low. If only one eligible
    # source exists, omit "lowest".
    if top and low and top["source"] == low["source"]:
        low = None

    return {
        "new_leads_last_7_days": sum(s["count"] for s in new_leads_breakdown),
        "breakdown_last_7_days": new_leads_breakdown,
        "top_closer_all_time": (
            {
                "source": top["source"],
                "close_rate": top["close_rate"],
                "lead_count": top["lead_count"],
                "approved_count": top["approved_count"],
            }
            if top
            else None
        ),
        "lowest_performer_all_time": (
            {
                "source": low["source"],
                "close_rate": low["close_rate"],
                "lead_count": low["lead_count"],
                "approved_count": low["approved_count"],
            }
            if low
            else None
        ),
    }
