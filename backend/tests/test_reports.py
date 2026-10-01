"""Sprint 18a — Lead source attribution tests."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.invoice import Invoice
from app.models.job import Job
from app.models.payment import Payment
from app.models.pipeline import Pipeline
from app.services import reports as reports_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _utc(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


@pytest.fixture()
def seeded_lead_data(db_session, seeded_stages, leads_pipeline, sales_pipeline, jobs_pipeline):
    """Build a small dataset across two lead sources + one unattributed.

    Google LSA: 3 leads, 2 estimates (1 approved → $10,000), $5,000 collected.
    Referral:   2 leads, 1 estimate approved → $20,000, $20,000 collected.
    Unattributed: 1 lead, no estimate.
    """
    today = datetime.now(timezone.utc).date()

    def _c(name, source, days_ago, pipeline=None):
        c = Contact(name=name, lead_source=source, phone=f"+1765555{hash(name) % 10000:04d}")
        c.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        if pipeline:
            c.pipeline_id = pipeline.id
        db_session.add(c)
        db_session.flush()
        return c

    # Google LSA
    g1 = _c("LSA One", "Google LSA", 5, leads_pipeline)
    g2 = _c("LSA Two", "Google LSA", 60, sales_pipeline)
    g3 = _c("LSA Three", "Google LSA", 120, sales_pipeline)
    # Referral
    r1 = _c("Ref One", "Referral", 10, sales_pipeline)
    r2 = _c("Ref Two", "Referral", 200, sales_pipeline)
    # Unattributed
    u1 = _c("Mystery", None, 3, leads_pipeline)
    db_session.commit()

    # Jobs linking estimates to contacts
    def _job_for(contact, pipeline):
        j = Job(contact_id=contact.id, pipeline_id=pipeline.id)
        db_session.add(j)
        db_session.flush()
        return j

    j_g2 = _job_for(g2, sales_pipeline)
    j_g3 = _job_for(g3, sales_pipeline)
    j_r2 = _job_for(r2, sales_pipeline)

    # Estimates
    e_g2 = Estimate(
        job_id=j_g2.id, name="LSA 2 est", status="sent",
        subtotal=Decimal("10000"), tax=Decimal("0"), total=Decimal("10000"),
    )
    # Approved Google LSA estimate
    e_g3 = Estimate(
        job_id=j_g3.id, name="LSA 3 est", status="approved",
        subtotal=Decimal("10000"), tax=Decimal("0"), total=Decimal("10000"),
        approved_at=datetime.now(timezone.utc) - timedelta(days=90),
        pipeline_id=jobs_pipeline.id,
    )
    # Approved Referral estimate
    e_r2 = Estimate(
        job_id=j_r2.id, name="Ref 2 est", status="approved",
        subtotal=Decimal("20000"), tax=Decimal("0"), total=Decimal("20000"),
        approved_at=datetime.now(timezone.utc) - timedelta(days=150),
        pipeline_id=jobs_pipeline.id,
    )
    db_session.add_all([e_g2, e_g3, e_r2])
    db_session.commit()

    # Invoices on the approved estimates
    inv_g = Invoice(
        job_id=j_g3.id, estimate_id=e_g3.id, invoice_number="INV-001",
        status="partial", subtotal=Decimal("10000"), tax=Decimal("0"),
        total=Decimal("10000"), amount_paid=Decimal("5000"),
        balance=Decimal("5000"), date_invoiced=today - timedelta(days=80),
    )
    inv_r = Invoice(
        job_id=j_r2.id, estimate_id=e_r2.id, invoice_number="INV-002",
        status="paid", subtotal=Decimal("20000"), tax=Decimal("0"),
        total=Decimal("20000"), amount_paid=Decimal("20000"),
        balance=Decimal("0"), date_invoiced=today - timedelta(days=140),
    )
    db_session.add_all([inv_g, inv_r])
    db_session.commit()

    # Payments
    p_g = Payment(
        invoice_id=inv_g.id, amount=Decimal("5000"),
        date_received=today - timedelta(days=70), method="check",
    )
    p_r = Payment(
        invoice_id=inv_r.id, amount=Decimal("20000"),
        date_received=today - timedelta(days=135), method="check",
    )
    db_session.add_all([p_g, p_r])
    db_session.commit()

    return {
        "contacts": {"g1": g1, "g2": g2, "g3": g3, "r1": r1, "r2": r2, "u1": u1},
        "estimates": {"e_g3": e_g3, "e_r2": e_r2},
        "invoices": {"inv_g": inv_g, "inv_r": inv_r},
    }


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------
def test_resolve_period_all():
    s, e = reports_service.resolve_period("all")
    assert s is None and e is None


def test_resolve_period_30d():
    today = date(2026, 5, 17)
    s, e = reports_service.resolve_period("30d", now=today)
    assert s == date(2026, 4, 17)
    assert e == today


def test_resolve_period_ytd():
    today = date(2026, 5, 17)
    s, e = reports_service.resolve_period("ytd", now=today)
    assert s == date(2026, 1, 1)
    assert e == today


def test_resolve_period_invalid():
    with pytest.raises(ValueError):
        reports_service.resolve_period("bogus")


# ---------------------------------------------------------------------------
# Full report — counts and metrics
# ---------------------------------------------------------------------------
def test_lead_source_report_all(seeded_lead_data, db_session):
    r = reports_service.get_lead_source_report(db_session, period="all")
    assert r["period"] == "all"
    # 3 LSA + 2 Referral + 1 Unattributed
    assert r["total_leads"] == 6

    by_name = {s["source"]: s for s in r["sources"]}
    assert "Google LSA" in by_name
    assert "Referral" in by_name
    assert by_name["Google LSA"]["lead_count"] == 3
    assert by_name["Referral"]["lead_count"] == 2
    # Unattributed surfaced separately
    assert r["unattributed"]["lead_count"] == 1


def test_lead_source_close_rate(seeded_lead_data, db_session):
    r = reports_service.get_lead_source_report(db_session, period="all")
    by_name = {s["source"]: s for s in r["sources"]}
    # Google LSA: 3 leads, 1 approved -> 33.33%
    assert by_name["Google LSA"]["approved_count"] == 1
    assert by_name["Google LSA"]["close_rate"] == pytest.approx(33.33, abs=0.01)
    # Referral: 2 leads, 1 approved -> 50%
    assert by_name["Referral"]["close_rate"] == 50.0


def test_lead_source_avg_job_value(seeded_lead_data, db_session):
    r = reports_service.get_lead_source_report(db_session, period="all")
    by_name = {s["source"]: s for s in r["sources"]}
    assert by_name["Google LSA"]["avg_job_value"] == 10000.0
    assert by_name["Referral"]["avg_job_value"] == 20000.0


def test_lead_source_no_approved(seeded_lead_data, db_session):
    """A source with no approvals should report close_rate=0, avg_job_value=0."""
    # Add a fresh source with one lead, no estimate.
    c = Contact(name="Facebook One", lead_source="Facebook", phone="+17655551234")
    db_session.add(c)
    db_session.commit()
    r = reports_service.get_lead_source_report(db_session, period="all")
    by_name = {s["source"]: s for s in r["sources"]}
    assert by_name["Facebook"]["lead_count"] == 1
    assert by_name["Facebook"]["approved_count"] == 0
    assert by_name["Facebook"]["close_rate"] == 0.0
    assert by_name["Facebook"]["avg_job_value"] == 0.0


def test_lead_source_unattributed(seeded_lead_data, db_session):
    r = reports_service.get_lead_source_report(db_session, period="all")
    assert r["unattributed"]["lead_count"] == 1
    assert "Unattributed" not in {s["source"] for s in r["sources"]}


def test_lead_source_revenue_tracking(seeded_lead_data, db_session):
    r = reports_service.get_lead_source_report(db_session, period="all")
    by_name = {s["source"]: s for s in r["sources"]}
    assert by_name["Google LSA"]["total_invoiced"] == 10000.0
    assert by_name["Google LSA"]["total_collected"] == 5000.0
    assert by_name["Referral"]["total_invoiced"] == 20000.0
    assert by_name["Referral"]["total_collected"] == 20000.0
    assert r["total_revenue"] == 25000.0


def test_lead_source_avg_days_to_close(seeded_lead_data, db_session):
    r = reports_service.get_lead_source_report(db_session, period="all")
    by_name = {s["source"]: s for s in r["sources"]}
    # LSA approved 90 days ago, contact created 120 days ago → 30 days
    assert by_name["Google LSA"]["avg_days_to_close"] == 30.0
    # Referral approved 150 days ago, contact created 200 days ago → 50 days
    assert by_name["Referral"]["avg_days_to_close"] == 50.0


def test_lead_source_pipeline_breakdown(seeded_lead_data, db_session):
    r = reports_service.get_lead_source_report(db_session, period="all")
    by_name = {s["source"]: s for s in r["sources"]}
    # Google LSA: g1 in leads pipeline, g2+g3 in sales pipeline, e_g3 approved in jobs
    assert by_name["Google LSA"]["pipeline_breakdown"]["leads"] == 1
    assert by_name["Google LSA"]["pipeline_breakdown"]["sales"] == 2
    assert by_name["Google LSA"]["pipeline_breakdown"]["jobs"] == 1
    # Referral: r1+r2 in sales pipeline, e_r2 approved in jobs
    assert by_name["Referral"]["pipeline_breakdown"]["sales"] == 2
    assert by_name["Referral"]["pipeline_breakdown"]["jobs"] == 1


# ---------------------------------------------------------------------------
# Period filtering
# ---------------------------------------------------------------------------
def test_lead_source_report_30d_excludes_old(seeded_lead_data, db_session):
    r = reports_service.get_lead_source_report(db_session, period="30d")
    by_name = {s["source"]: s for s in r["sources"]}
    # Last 30d: g1 (5d), r1 (10d), Mystery (3d). g2/g3/r2 are older.
    assert by_name.get("Google LSA", {}).get("lead_count", 0) == 1
    assert by_name.get("Referral", {}).get("lead_count", 0) == 1
    assert r["unattributed"]["lead_count"] == 1


def test_lead_source_report_custom_range(seeded_lead_data, db_session):
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=7)
    end = today
    r = reports_service.get_lead_source_report(
        db_session, period="custom", start_date=start, end_date=end
    )
    by_name = {s["source"]: s for s in r["sources"]}
    # g1 (5d ago) and Mystery (3d ago) are within 7d. r1 is 10d → out.
    assert by_name.get("Google LSA", {}).get("lead_count", 0) == 1
    assert "Referral" not in by_name or by_name["Referral"]["lead_count"] == 0
    assert r["unattributed"]["lead_count"] == 1


def test_lead_source_revenue_filtered_by_period(seeded_lead_data, db_session):
    """An older invoice should not show in a recent-only period."""
    r = reports_service.get_lead_source_report(db_session, period="30d")
    by_name = {s["source"]: s for s in r["sources"]}
    # Both invoices are 80d and 140d old → both excluded from 30d revenue.
    if "Google LSA" in by_name:
        assert by_name["Google LSA"]["total_invoiced"] == 0.0
    if "Referral" in by_name:
        assert by_name["Referral"]["total_invoiced"] == 0.0


# ---------------------------------------------------------------------------
# Summary endpoint shape
# ---------------------------------------------------------------------------
def test_lead_source_summary_shape(seeded_lead_data, db_session):
    s = reports_service.get_lead_source_summary(db_session, period="all")
    assert s["period"] == "all"
    assert s["total_leads"] == 6
    for src in s["sources"]:
        assert set(src.keys()) == {
            "source", "lead_count", "close_rate", "avg_job_value"
        }


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------
def test_endpoint_requires_auth(client):
    r = client.get("/api/reports/lead-sources")
    assert r.status_code == 401


def test_endpoint_lead_source_report(
    client, auth_headers, seeded_lead_data
):
    r = client.get("/api/reports/lead-sources", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total_leads"] == 6
    assert {s["source"] for s in data["sources"]} == {"Google LSA", "Referral"}


def test_endpoint_invalid_period(client, auth_headers):
    r = client.get("/api/reports/lead-sources?period=bogus", headers=auth_headers)
    assert r.status_code == 400


def test_endpoint_custom_requires_dates(client, auth_headers):
    r = client.get("/api/reports/lead-sources?period=custom", headers=auth_headers)
    assert r.status_code == 400


def test_endpoint_start_after_end_rejected(client, auth_headers):
    r = client.get(
        "/api/reports/lead-sources?period=custom"
        "&start_date=2026-05-10&end_date=2026-05-01",
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_endpoint_summary(client, auth_headers, seeded_lead_data):
    r = client.get(
        "/api/reports/lead-sources/summary?period=all",
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total_leads"] == 6
    assert all("source" in s for s in data["sources"])


def test_endpoint_summary_rejects_custom(client, auth_headers):
    r = client.get(
        "/api/reports/lead-sources/summary?period=custom",
        headers=auth_headers,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Briefing + AI context integration
# ---------------------------------------------------------------------------
def test_briefing_summary_helper(seeded_lead_data, db_session):
    summary = reports_service.get_lead_source_briefing_summary(db_session)
    assert "new_leads_last_7_days" in summary
    assert "breakdown_last_7_days" in summary
    # Last 7d: g1 + Mystery → 2 (Referral r1 at 10d ago is out)
    assert summary["new_leads_last_7_days"] == 2
    # Top closer all time: Referral (50%) since it has >=3 lead bar? No, has 2.
    # With ≥3 lead threshold: only Google LSA (3 leads) qualifies.
    assert summary["top_closer_all_time"]["source"] == "Google LSA"


# NOTE: integration of `lead_source_summary` into get_briefing_context is
# verified by test_ai_briefing.test_briefing_empty_data_returns_all_sections,
# which now asserts the key set explicitly. We don't repeat it here because
# any briefing call against seeded Contact data triggers an unrelated pre-
# existing tz-comparison bug in _briefing_overdue_followups/_briefing_stale_leads
# (SQLite returns tz-naive datetimes from DateTime(timezone=True) columns).


def test_ai_prompt_includes_lead_source_context(
    seeded_lead_data, db_session
):
    """The global system prompt must contain lead source metrics."""
    from app.models.ai_conversation import AIConversation
    from app.services.ai_chat import _build_system_prompt

    convo = AIConversation(
        id="test-convo-1", user_id=1, entity_type=None, entity_id=None
    )
    system_prompt = _build_system_prompt(db_session, convo)
    assert "LEAD SOURCE METRICS" in system_prompt
    assert "Google LSA" in system_prompt
    assert "Referral" in system_prompt
