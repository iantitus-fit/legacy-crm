"""Regression tests for the money-path fixes logged in map/VERIFICATION.md (V-01 to V-09).

Each test names the entry it closes. They run against the same in-memory
SQLite fixtures as the rest of the suite.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.config import settings
from app.models.change_order import ChangeOrder
from app.models.change_order_token import ChangeOrderToken
from app.models.estimate import Estimate
from app.models.estimate_signature import EstimateSignature
from app.models.estimate_token import EstimateToken
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.routers.invoices import _next_invoice_number, _render_invoice_html
from app.utils.portal_links import is_expired, link_expiry

SIGNATURE = {
    "signer_name": "Jane Customer",
    "signature_data": "data:image/png;base64,iVBORw0KGgo=",
    "terms_accepted": True,
}


# ---------------------------------------------------------------- helpers


def _job(client, auth_headers):
    contact = client.post("/api/contacts", json={"name": "Test Customer"}, headers=auth_headers).json()
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    jobs = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(f"/api/pipeline-stages?pipeline_id={jobs['id']}", headers=auth_headers).json()["items"]
    return client.post(
        "/api/jobs",
        json={"pipeline_id": jobs["id"], "contact_id": contact["id"], "stage_id": stages[0]["id"],
              "work_type": "retail", "property_address": "100 Test St"},
        headers=auth_headers,
    ).json()


def _estimate(client, auth_headers, amount="1000.00", **fields):
    job = _job(client, auth_headers)
    est = client.post("/api/estimates", json={"job_id": job["id"], "name": "Reroof", **fields},
                      headers=auth_headers).json()
    client.post(f"/api/estimates/{est['id']}/line-items",
                json={"description": "Work", "qty": "1", "unit_price": amount}, headers=auth_headers)
    return est


def _token(db_session, estimate_id, status="sent", expires_at=None):
    value = uuid4().hex
    db_session.add(EstimateToken(estimate_id=estimate_id, token=value, expires_at=expires_at))
    db_session.query(Estimate).filter(Estimate.id == estimate_id).first().status = status
    db_session.commit()
    return value


def _jobs_pending(db_session):
    jobs = db_session.query(Pipeline).filter(Pipeline.slug == "jobs").first()
    stage = db_session.query(PipelineStage).filter(
        PipelineStage.pipeline_id == jobs.id, PipelineStage.name == "Pending Schedule").first()
    return jobs, stage


def _approve_internal(client, auth_headers, estimate_id):
    resp = client.post(f"/api/estimates/{estimate_id}/approve-internal",
                       json={"signer_name": "Dale"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text


def _co(client, auth_headers, estimate_id, amount="100.00"):
    co = client.post(f"/api/estimates/{estimate_id}/change-orders", json={"name": "Decking"},
                     headers=auth_headers).json()
    client.post(f"/api/change-orders/{co['id']}/items",
                json={"description": "Decking", "qty": "1", "unit_price": amount}, headers=auth_headers)
    return co


# ------------------------------------------------- V-01 / V-02: approval


def test_v01_portal_approval_lands_on_jobs_board(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    token = _token(db_session, est["id"])

    assert client.post(f"/api/portal/{token}/approve", json=SIGNATURE).status_code == 200

    row = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    db_session.refresh(row)
    jobs, pending = _jobs_pending(db_session)
    assert row.status == "approved"
    assert row.pipeline_id == jobs.id and row.stage_id == pending.id
    assert row.approved_at is not None and row.approved_by == "Jane Customer"
    board = client.get(f"/api/pipelines/{jobs.id}/estimates-board", headers=auth_headers).json()
    assert board["total_estimates"] == 1


def test_v02_portal_cannot_approve_twice(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    token = _token(db_session, est["id"])
    assert client.post(f"/api/portal/{token}/approve", json=SIGNATURE).status_code == 200
    assert client.post(f"/api/portal/{token}/approve", json=SIGNATURE).status_code == 409
    signatures = db_session.query(EstimateSignature).filter(EstimateSignature.estimate_id == est["id"]).count()
    assert signatures == 1


def test_v02_portal_cannot_approve_after_rejection(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    token = _token(db_session, est["id"])
    assert client.post(f"/api/portal/{token}/reject", json={"name": "Jane", "reason": "Too high"}).status_code == 200
    assert client.post(f"/api/portal/{token}/approve", json=SIGNATURE).status_code == 409


def test_v02_portal_cannot_reopen_a_job_underway(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    token = _token(db_session, est["id"], status="in_progress")
    assert client.post(f"/api/portal/{token}/reject", json={"name": "Jane", "reason": "x"}).status_code == 409
    assert client.post(f"/api/portal/{token}/request-changes", json={"message": "x"}).status_code == 409
    row = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    db_session.refresh(row)
    assert row.status == "in_progress"


def test_v02_change_order_cannot_be_approved_twice(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    _approve_internal(client, auth_headers, est["id"])
    co = _co(client, auth_headers, est["id"])
    value = uuid4().hex
    db_session.add(ChangeOrderToken(change_order_id=co["id"], token=value))
    db_session.query(ChangeOrder).filter(ChangeOrder.id == co["id"]).first().status = "sent"
    db_session.commit()
    assert client.post(f"/api/portal/co/{value}/approve", json=SIGNATURE).status_code == 200
    assert client.post(f"/api/portal/co/{value}/approve", json=SIGNATURE).status_code == 409


# ------------------------------------------- V-03: deposits on the final


def _deposit(client, auth_headers, estimate_id, percent="50"):
    resp = client.post("/api/invoices/deposit", json={"estimate_id": estimate_id, "deposit_percent": percent},
                       headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _final(client, auth_headers, estimate_id):
    resp = client.post("/api/invoices", json={"estimate_id": estimate_id}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_v03_final_invoice_credits_billed_deposit(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)          # 1,000.00 + 7% tax = 1,070.00
    deposit = _deposit(client, auth_headers, est["id"])
    assert Decimal(deposit["total"]) == Decimal("535.00")
    _approve_internal(client, auth_headers, est["id"])

    final = _final(client, auth_headers, est["id"])

    credits = [i for i in final["items"] if i["source_type"] == "deposit_credit"]
    assert len(credits) == 1 and Decimal(credits[0]["line_total"]) == Decimal("-535.00")
    assert credits[0]["source_invoice_id"] == deposit["id"]
    assert Decimal(final["subtotal"]) == Decimal("1000.00")
    assert Decimal(final["tax"]) == Decimal("70.00")      # tax on the work, not on the credit
    assert Decimal(final["total"]) == Decimal("535.00")
    assert Decimal(final["balance"]) == Decimal("535.00")


def test_v03_paying_the_remainder_marks_final_paid(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    _deposit(client, auth_headers, est["id"])
    _approve_internal(client, auth_headers, est["id"])
    final = _final(client, auth_headers, est["id"])
    resp = client.post(f"/api/invoices/{final['id']}/payments",
                       json={"amount": "535.00", "date_received": "2026-05-01", "method": "check"},
                       headers=auth_headers)
    assert resp.status_code == 201, resp.text
    assert client.get(f"/api/invoices/{final['id']}", headers=auth_headers).json()["status"] == "paid"


def test_v03_voided_deposit_is_not_credited(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    deposit = _deposit(client, auth_headers, est["id"])
    client.put(f"/api/invoices/{deposit['id']}", json={"status": "void"}, headers=auth_headers)
    _approve_internal(client, auth_headers, est["id"])
    final = _final(client, auth_headers, est["id"])
    assert not [i for i in final["items"] if i["source_type"] == "deposit_credit"]
    assert Decimal(final["total"]) == Decimal("1070.00")


def test_v03_voiding_deposit_later_removes_its_credit(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    deposit = _deposit(client, auth_headers, est["id"])
    _approve_internal(client, auth_headers, est["id"])
    final = _final(client, auth_headers, est["id"])
    assert Decimal(final["total"]) == Decimal("535.00")

    client.put(f"/api/invoices/{deposit['id']}", json={"status": "void"}, headers=auth_headers)

    final = client.get(f"/api/invoices/{final['id']}", headers=auth_headers).json()
    assert Decimal(final["total"]) == Decimal("1070.00")
    assert not [i for i in final["items"] if i["source_type"] == "deposit_credit"]


def test_v03_no_new_deposit_once_final_exists(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    _approve_internal(client, auth_headers, est["id"])
    _final(client, auth_headers, est["id"])
    resp = client.post("/api/invoices/deposit", json={"estimate_id": est["id"], "deposit_percent": "25"},
                       headers=auth_headers)
    assert resp.status_code == 400


def test_v03_invoice_pdf_lists_credit_under_totals(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    _deposit(client, auth_headers, est["id"])
    _approve_internal(client, auth_headers, est["id"])
    final = _final(client, auth_headers, est["id"])
    html = _render_invoice_html(final["id"], db_session)
    assert "Less deposit invoice" in html
    assert "\\$" not in html          # stray backslashes used to print before every item price


# ------------------------------------------ V-04: change-order tax rules


def test_v04_tax_included_estimate_gets_untaxed_change_orders(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers, tax_included=True)
    _approve_internal(client, auth_headers, est["id"])
    co = _co(client, auth_headers, est["id"])
    row = db_session.query(ChangeOrder).filter(ChangeOrder.id == co["id"]).first()
    db_session.refresh(row)
    assert row.tax == Decimal("0.00") and row.total == Decimal("100.00")


def test_v04_zero_tax_rate_stays_zero_on_change_orders(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers, tax_rate="0")
    _approve_internal(client, auth_headers, est["id"])
    co = _co(client, auth_headers, est["id"])
    row = db_session.query(ChangeOrder).filter(ChangeOrder.id == co["id"]).first()
    db_session.refresh(row)
    assert row.tax == Decimal("0.00") and row.total == Decimal("100.00")


def test_v04_taxed_estimate_still_taxes_change_orders(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    _approve_internal(client, auth_headers, est["id"])
    co = _co(client, auth_headers, est["id"])
    row = db_session.query(ChangeOrder).filter(ChangeOrder.id == co["id"]).first()
    db_session.refresh(row)
    assert row.tax == Decimal("7.00") and row.total == Decimal("107.00")


# --------------------------------------------- V-05: invoice status set


def test_v05_invoice_status_is_a_closed_set(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    _approve_internal(client, auth_headers, est["id"])
    final = _final(client, auth_headers, est["id"])
    url = f"/api/invoices/{final['id']}"
    assert client.put(url, json={"status": "bogus"}, headers=auth_headers).status_code == 400
    assert client.put(url, json={"status": "paid"}, headers=auth_headers).status_code == 400
    assert client.put(url, json={"status": "void"}, headers=auth_headers).status_code == 200


# --------------------------------------------- V-08: portal link expiry


def test_v08_links_do_not_expire_by_default(monkeypatch):
    monkeypatch.setattr(settings, "portal_link_days", None)
    assert link_expiry() is None
    assert is_expired(None) is False


def test_v08_setting_gives_links_an_expiry(monkeypatch):
    monkeypatch.setattr(settings, "portal_link_days", 30)
    expires = link_expiry()
    assert timedelta(days=29) < expires - datetime.now(timezone.utc) <= timedelta(days=30)


def test_v08_expired_estimate_link_is_refused(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    past = datetime.now(timezone.utc) - timedelta(days=1)
    token = _token(db_session, est["id"], expires_at=past)
    assert client.get(f"/api/portal/{token}").status_code == 410
    assert client.post(f"/api/portal/{token}/approve", json=SIGNATURE).status_code == 410


def test_v08_expired_change_order_link_is_refused(client, auth_headers, seeded_stages, db_session):
    est = _estimate(client, auth_headers)
    _approve_internal(client, auth_headers, est["id"])
    co = _co(client, auth_headers, est["id"])
    value = uuid4().hex
    db_session.add(ChangeOrderToken(change_order_id=co["id"], token=value,
                                    expires_at=datetime.now(timezone.utc) - timedelta(days=1)))
    db_session.commit()
    assert client.get(f"/api/portal/co/{value}").status_code == 410


# --------------------------------------------- V-09: invoice numbering


def test_v09_numbering_ignores_imported_invoice_numbers(client, auth_headers, seeded_stages, db_session):
    job = _job(client, auth_headers)
    db_session.add(Invoice(job_id=job["id"], invoice_number="1004-1", status="paid",
                           subtotal=0, tax=0, total=0, amount_paid=0, balance=0))
    db_session.commit()
    assert _next_invoice_number(db_session) == "INV-0001"

    db_session.add(Invoice(job_id=job["id"], invoice_number="INV-0007", status="draft",
                           subtotal=0, tax=0, total=0, amount_paid=0, balance=0))
    db_session.add(Invoice(job_id=job["id"], invoice_number="1188-2", status="draft",
                           subtotal=0, tax=0, total=0, amount_paid=0, balance=0))
    db_session.commit()
    assert _next_invoice_number(db_session) == "INV-0008"
