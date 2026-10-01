"""Sprint 20b — Work Orders (standard + secret).

Most visibility checks assert on build_work_order_context() rather than
parsing PDF bytes — pypdf isn't a dependency, and asserting on the
template input is both faster (no WeasyPrint) and less brittle than
grepping rendered PDF text.
"""
import io
from unittest.mock import patch

import pytest

from app.models.estimate import Estimate
from app.models.note import Note
from app.services.work_order_pdf import (
    build_work_order_context,
    render_work_order_pdf,
)


# --- Helpers ---


def _create_contact(client, auth_headers, **overrides):
    body = {"name": "Joe Homeowner", "phone": "555-0100", "email": "joe@example.com", **overrides}
    return client.post("/api/contacts", json=body, headers=auth_headers).json()


def _create_job(client, auth_headers, contact_id):
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    return client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact_id,
            "stage_id": stages[0]["id"],
            "work_type": "retail",
            "property_address": "123 Main St, Kokomo, IN",
        },
        headers=auth_headers,
    ).json()


def _create_estimate(client, auth_headers, job_id, with_items=True):
    payload = {"job_id": job_id, "name": "Roof Replacement"}
    if with_items:
        payload["line_items"] = [
            {"description": "Shingles", "qty": "30", "unit_price": "150.00"},
            {"description": "Underlayment", "qty": "10", "unit_price": "75.00"},
        ]
    return client.post("/api/estimates", json=payload, headers=auth_headers).json()


def _upload_photo(client, auth_headers, *, estimate_id, show_in_work_order, filename):
    # Minimal PNG header so content-type sniffing works
    png_magic = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    return client.post(
        "/api/documents",
        data={
            "estimate_id": str(estimate_id),
            "folder": "Photos",
            "show_in_work_order": str(show_in_work_order).lower(),
        },
        files=[("files", (filename, io.BytesIO(png_magic), "image/png"))],
        headers=auth_headers,
    ).json()


def _add_note(db_session, estimate_id, note_type, content, user_id=1):
    note = Note(
        entity_type="estimate",
        entity_id=estimate_id,
        note_type=note_type,
        content=content,
        created_by_user_id=user_id,
    )
    db_session.add(note)
    db_session.commit()


@pytest.fixture
def setup_estimate(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])
    est = _create_estimate(client, auth_headers, job["id"])
    return {"contact": contact, "job": job, "estimate": est}


# --- Context builder (fast, no WeasyPrint) ---


def test_context_includes_customer_when_not_secret(client, auth_headers, db_session, setup_estimate):
    est_id = setup_estimate["estimate"]["id"]
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    ctx = build_work_order_context(db_session, estimate, secret=False)
    assert ctx["customer"] is not None
    assert ctx["customer"]["name"] == "Joe Homeowner"
    assert ctx["customer"]["phone"] == "555-0100"
    assert ctx["customer"]["email"] == "joe@example.com"


def test_context_redacts_customer_when_secret(client, auth_headers, db_session, setup_estimate):
    est_id = setup_estimate["estimate"]["id"]
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    ctx = build_work_order_context(db_session, estimate, secret=True)
    assert ctx["customer"] is None
    assert ctx["secret"] is True


def test_context_keeps_job_address_when_secret(client, auth_headers, db_session, setup_estimate):
    """Job address is needed by the crew even in secret mode."""
    est_id = setup_estimate["estimate"]["id"]
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    ctx = build_work_order_context(db_session, estimate, secret=True)
    assert ctx["job_address"] == "123 Main St, Kokomo, IN"


def test_context_excludes_pricing(client, auth_headers, db_session, setup_estimate):
    est_id = setup_estimate["estimate"]["id"]
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    ctx = build_work_order_context(db_session, estimate, secret=False)
    # Every section + unsectioned line item must omit unit_price / line_total
    for section in ctx["sections"]:
        for item in section["line_items"]:
            assert "unit_price" not in item
            assert "line_total" not in item
    for item in ctx["unsectioned_items"]:
        assert "unit_price" not in item
        assert "line_total" not in item


# --- WO number stamping ---


def test_work_order_number_stamped_on_first_render(
    client, auth_headers, db_session, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    assert estimate.work_order_number is None
    ctx = build_work_order_context(db_session, estimate, secret=False)
    assert ctx["wo_number"] == f"WO-{est_id}"
    db_session.refresh(estimate)
    assert estimate.work_order_number == f"WO-{est_id}"


def test_work_order_number_reused_on_subsequent_render(
    client, auth_headers, db_session, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    build_work_order_context(db_session, estimate, secret=False)
    first_value = estimate.work_order_number
    # Manually mutate to detect overwrites
    estimate.work_order_number = "WO-CUSTOM"
    db_session.commit()
    build_work_order_context(db_session, estimate, secret=False)
    db_session.refresh(estimate)
    assert estimate.work_order_number == "WO-CUSTOM"


# --- Photos ---


def test_context_includes_show_in_work_order_photos(
    client, auth_headers, db_session, setup_estimate, temp_upload_dir
):
    est_id = setup_estimate["estimate"]["id"]
    _upload_photo(client, auth_headers, estimate_id=est_id, show_in_work_order=True, filename="roof.png")
    _upload_photo(client, auth_headers, estimate_id=est_id, show_in_work_order=False, filename="internal.png")
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    ctx = build_work_order_context(db_session, estimate, secret=False)
    captions = [p["caption"] for p in ctx["photos"]]
    assert "roof.png" in captions
    assert "internal.png" not in captions


def test_context_excludes_non_image_documents(
    client, auth_headers, db_session, setup_estimate, temp_upload_dir
):
    est_id = setup_estimate["estimate"]["id"]
    # PDF with show_in_work_order=True should still be excluded — only photos
    client.post(
        "/api/documents",
        data={
            "estimate_id": str(est_id),
            "folder": "Job Paperwork",
            "show_in_work_order": "true",
        },
        files=[("files", ("contract.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf"))],
        headers=auth_headers,
    )
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    ctx = build_work_order_context(db_session, estimate, secret=False)
    assert ctx["photos"] == []


# --- Notes ---


def test_context_includes_crew_and_company_notes(
    client, auth_headers, db_session, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    _add_note(db_session, est_id, "crew", "Bring 3 bundles extra")
    _add_note(db_session, est_id, "company", "Internal: insurance verified")
    _add_note(db_session, est_id, "client", "Client wants pickup at 9am")
    estimate = db_session.query(Estimate).filter(Estimate.id == est_id).first()
    ctx = build_work_order_context(db_session, estimate, secret=False)
    contents = [n.content for n in ctx["crew_notes"]]
    assert "Bring 3 bundles extra" in contents
    assert "Internal: insurance verified" in contents
    assert "Client wants pickup at 9am" not in contents


# --- HTTP endpoints ---


def test_get_work_order_pdf_returns_pdf(client, auth_headers, setup_estimate):
    est_id = setup_estimate["estimate"]["id"]
    resp = client.get(
        f"/api/estimates/{est_id}/work-order",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_get_work_order_pdf_secret_variant(client, auth_headers, setup_estimate):
    est_id = setup_estimate["estimate"]["id"]
    resp = client.get(
        f"/api/estimates/{est_id}/work-order?secret=true",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_get_work_order_pdf_404_for_unknown_estimate(client, auth_headers):
    resp = client.get("/api/estimates/9999/work-order", headers=auth_headers)
    assert resp.status_code == 404


def test_get_work_order_pdf_requires_auth(client, setup_estimate):
    est_id = setup_estimate["estimate"]["id"]
    resp = client.get(f"/api/estimates/{est_id}/work-order")
    assert resp.status_code == 401


# --- Send ---


def test_send_work_order_calls_email_service(
    client, auth_headers, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    with patch("app.routers.work_orders.send_email") as mock_send:
        mock_send.return_value = True
        resp = client.post(
            f"/api/estimates/{est_id}/work-order/send",
            json={"recipient_email": "crew@example.com"},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent_to"] == "crew@example.com"
    assert body["wo_number"] == f"WO-{est_id}"
    assert body["secret"] is False
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "crew@example.com"
    assert call_kwargs["attachment_bytes"].startswith(b"%PDF")
    assert call_kwargs["attachment_filename"] == f"WO-{est_id}.pdf"


def test_send_work_order_secret_flag_propagates(
    client, auth_headers, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    with patch("app.routers.work_orders.send_email") as mock_send:
        mock_send.return_value = True
        resp = client.post(
            f"/api/estimates/{est_id}/work-order/send",
            json={"recipient_email": "sub@example.com", "secret": True},
            headers=auth_headers,
        )
    assert resp.status_code == 200
    assert resp.json()["secret"] is True
    assert "Secret" in mock_send.call_args.kwargs["subject"]


def test_send_work_order_requires_recipient_email(
    client, auth_headers, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    resp = client.post(
        f"/api/estimates/{est_id}/work-order/send",
        json={"secret": False},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# --- Tokens + public route ---


def test_create_work_order_link_returns_token_and_url(
    client, auth_headers, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    resp = client.post(
        f"/api/estimates/{est_id}/work-order/link",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    assert f"/api/work-orders/{body['token']}" in body["url"]
    assert body["secret"] is False


def test_work_order_link_reused_for_same_secret_setting(
    client, auth_headers, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    a = client.post(
        f"/api/estimates/{est_id}/work-order/link", headers=auth_headers
    ).json()
    b = client.post(
        f"/api/estimates/{est_id}/work-order/link", headers=auth_headers
    ).json()
    assert a["token"] == b["token"]


def test_work_order_link_secret_and_standard_differ(
    client, auth_headers, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    std = client.post(
        f"/api/estimates/{est_id}/work-order/link?secret=false",
        headers=auth_headers,
    ).json()
    sec = client.post(
        f"/api/estimates/{est_id}/work-order/link?secret=true",
        headers=auth_headers,
    ).json()
    assert std["token"] != sec["token"]
    assert std["secret"] is False
    assert sec["secret"] is True


def test_public_token_route_returns_pdf_without_auth(
    client, auth_headers, setup_estimate
):
    est_id = setup_estimate["estimate"]["id"]
    link = client.post(
        f"/api/estimates/{est_id}/work-order/link", headers=auth_headers
    ).json()
    resp = client.get(f"/api/work-orders/{link['token']}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_public_token_route_404_for_invalid_token(client):
    resp = client.get("/api/work-orders/nonexistent-token-1234")
    assert resp.status_code == 404
