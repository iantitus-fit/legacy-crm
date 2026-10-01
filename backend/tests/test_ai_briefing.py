"""Sprint 16c — Morning briefing data endpoint tests."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config import settings
from app.services.ai_provider import MockProvider, set_provider


@pytest.fixture(autouse=True)
def _force_none_provider():
    original = settings.llm_provider
    settings.llm_provider = "none"
    set_provider(None)
    yield
    settings.llm_provider = original
    set_provider(None)


@pytest.fixture()
def use_mock_provider():
    def _install(canned: str = None, model: str = "mock-1"):
        provider = MockProvider(model=model, canned=canned)
        set_provider(provider)
        return provider

    yield _install
    set_provider(None)


def _bootstrap_user(db_session, client):
    """Run setup so a user exists, then return that User row.

    Note: when seeded_stages is also requested, that fixture seeds the
    initial users (Dale, Marcus etc.) so /api/auth/setup may not be needed
    or may 400. Service-layer tests should fetch the existing user
    directly from db_session instead of requiring this helper.
    """
    client.post(
        "/api/auth/setup",
        json={
            "email": "dale@legacy.com",
            "full_name": "Dale Owner",
            "password": "testpassword123",
        },
    )
    from app.models.user import User
    return db_session.query(User).first()


def _ensure_user(db_session, seeded_stages):
    """Get or create a user. Service tests don't need an auth token."""
    from app.models.user import User
    user = db_session.query(User).first()
    if user is None:
        from app.utils.auth import hash_password
        user = User(
            email="briefing@test.com",
            full_name="Briefing Tester",
            password_hash=hash_password("x"),
            role="admin",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


def test_briefing_empty_data_returns_all_sections(
    db_session, seeded_stages
):
    from app.services.ai_chat import get_briefing_context
    user = _ensure_user(db_session, seeded_stages)
    data = get_briefing_context(db=db_session, user_id=user.id)
    expected_keys = {
        "overdue_followups",
        "unsigned_estimates",
        "overdue_invoices",
        "unpaid_invoices",
        "upcoming_appointments",
        "tasks_due",
        "recent_customer_actions",
        "overnight_ai_actions",
        "stale_leads",
        "lead_source_summary",
        "automation_summary",
        "summary_counts",
        "generated_at",
    }
    assert set(data.keys()) == expected_keys
    assert isinstance(data["unsigned_estimates"], dict)
    assert "viewed_not_signed" in data["unsigned_estimates"]
    assert "not_viewed" in data["unsigned_estimates"]
    assert "aging_over_5_days" in data["unsigned_estimates"]
    assert data["summary_counts"]["overdue_followups"] == 0


def test_briefing_overdue_invoices(db_session, seeded_stages):
    """Invoices past due_date show up under overdue_invoices."""
    from app.services.ai_chat import get_briefing_context
    from app.models.contact import Contact
    from app.models.invoice import Invoice
    from app.models.job import Job
    from app.models.pipeline import Pipeline

    user = _ensure_user(db_session, seeded_stages)
    contact = Contact(name="Past-Due Co")
    db_session.add(contact)
    db_session.commit()

    jobs_pipeline = db_session.query(Pipeline).filter(Pipeline.slug == "jobs").first()
    job = Job(contact_id=contact.id, work_type="retail", pipeline_id=jobs_pipeline.id)
    db_session.add(job)
    db_session.commit()

    today = date.today()
    overdue = Invoice(
        job_id=job.id,
        invoice_number="INV-OD01",
        status="partial",
        date_invoiced=today - timedelta(days=20),
        due_date=today - timedelta(days=10),
        subtotal=Decimal("1000"),
        total=Decimal("1000"),
        balance=Decimal("400"),
    )
    not_yet = Invoice(
        job_id=job.id,
        invoice_number="INV-FUT01",
        status="draft",
        date_invoiced=today,
        due_date=today + timedelta(days=10),
        subtotal=Decimal("500"),
        total=Decimal("500"),
        balance=Decimal("500"),
    )
    db_session.add_all([overdue, not_yet])
    db_session.commit()

    data = get_briefing_context(db=db_session, user_id=user.id)
    overdue_nums = [i["invoice_number"] for i in data["overdue_invoices"]]
    assert "INV-OD01" in overdue_nums
    assert "INV-FUT01" not in overdue_nums

    unpaid_nums = [i["invoice_number"] for i in data["unpaid_invoices"]]
    assert "INV-FUT01" in unpaid_nums
    assert "INV-OD01" not in unpaid_nums


def test_briefing_tasks_due_today_or_overdue(db_session, seeded_stages):
    from app.models.task import Task
    from app.services.ai_chat import get_briefing_context

    user = _ensure_user(db_session, seeded_stages)
    today = date.today()
    db_session.add_all([
        Task(title="Today task", status="open", due_date=today,
             assigned_to_user_id=user.id),
        Task(title="Overdue task", status="open",
             due_date=today - timedelta(days=2),
             assigned_to_user_id=user.id),
        Task(title="Future task", status="open",
             due_date=today + timedelta(days=2),
             assigned_to_user_id=user.id),
        Task(title="Done task", status="done", due_date=today,
             assigned_to_user_id=user.id),
    ])
    db_session.commit()

    data = get_briefing_context(db=db_session, user_id=user.id)
    titles = [t["title"] for t in data["tasks_due"]]
    assert "Today task" in titles
    assert "Overdue task" in titles
    assert "Future task" not in titles
    assert "Done task" not in titles


def test_briefing_summary_counts_match_section_lengths(
    db_session, seeded_stages
):
    """summary_counts must match the lengths of each list section."""
    from app.models.task import Task
    from app.services.ai_chat import get_briefing_context

    user = _ensure_user(db_session, seeded_stages)
    db_session.add_all([
        Task(title=f"T{i}", status="open", due_date=date.today(),
             assigned_to_user_id=user.id)
        for i in range(3)
    ])
    db_session.commit()

    data = get_briefing_context(db=db_session, user_id=user.id)
    assert data["summary_counts"]["tasks_due"] == 3
    assert data["summary_counts"]["overdue_followups"] == len(
        data["overdue_followups"]
    )


def test_briefing_endpoint_auth(client):
    resp = client.get("/api/ai/briefing")
    assert resp.status_code == 401


def test_briefing_endpoint_returns_data_even_with_none_provider(
    client, auth_headers, seeded_stages
):
    """Spec: /api/ai/briefing must work regardless of LLM_PROVIDER setting."""
    resp = client.get("/api/ai/briefing", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "summary_counts" in body
    assert "overdue_followups" in body
    assert "unsigned_estimates" in body
    assert isinstance(body["unsigned_estimates"], dict)


def test_narrative_briefing_endpoint_503_with_none_provider(
    client, auth_headers, seeded_stages
):
    """Narrative requires an LLM. With provider=none, return 503."""
    resp = client.get("/api/ai/briefing/narrative", headers=auth_headers)
    assert resp.status_code == 503


def test_narrative_briefing_endpoint_with_mock(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="Good morning. Three things to do today.")
    resp = client.get("/api/ai/briefing/narrative", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["narrative"].startswith("Good morning")
    assert "data" in body
    assert "summary_counts" in body["data"]
    assert body["provider"] == "mock"


def test_briefing_invoices_include_contact_name(client, auth_headers, seeded_stages, db_session):
    """Overdue and unpaid invoices in the briefing must carry contact_name
    so downstream consumers (email renderer) can display it without re-querying."""
    from app.models.contact import Contact
    from app.models.job import Job
    from app.models.invoice import Invoice
    from app.models.pipeline import Pipeline
    from datetime import date, timedelta
    from decimal import Decimal

    contact = Contact(name="Test Customer", email="t@x.com")
    db_session.add(contact)
    db_session.flush()

    jobs_pipeline = db_session.query(Pipeline).filter(Pipeline.slug == "jobs").first()
    job = Job(
        pipeline_id=jobs_pipeline.id, contact_id=contact.id,
        job_type="Roofing", work_type="Roofing",
    )
    db_session.add(job)
    db_session.flush()

    inv = Invoice(
        job_id=job.id,
        invoice_number="INV-TEST-1",
        status="sent",
        due_date=date.today() - timedelta(days=5),
        subtotal=Decimal("100"), tax=Decimal("0"), total=Decimal("100"),
        amount_paid=Decimal("0"), balance=Decimal("100"),
    )
    db_session.add(inv)
    db_session.commit()

    resp = client.get("/api/ai/briefing", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    overdue = data["overdue_invoices"]
    assert any(i["invoice_number"] == "INV-TEST-1" for i in overdue)
    row = next(i for i in overdue if i["invoice_number"] == "INV-TEST-1")
    assert row["contact_name"] == "Test Customer"
    assert row["contact_id"] == contact.id
