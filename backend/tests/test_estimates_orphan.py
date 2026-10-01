"""Repro for production 500 on GET /api/estimates.

Two angles covered here:

1. Estimates with NULL job_id (the AccuLynx-import shape the user
   flagged). The current response builder already handles this, so
   these tests are documentation that the orphan path works.

2. Estimates with MULTIPLE invoices. Invoice.estimate_id has no
   unique constraint and prod has deposit + final invoices on the
   same estimate. The list builder used `.scalar()` to pull invoice_id,
   which raises MultipleResultsFound on >=2 rows — exactly the prod
   500. Fixed by switching to `.first()` with a deterministic order.
"""
from decimal import Decimal

from app.models.estimate import Estimate
from app.models.invoice import Invoice


def test_list_estimates_with_orphan_estimate(
    client, auth_headers, seeded_stages, db_session
):
    """An estimate with NULL job_id must not 500 the list endpoint."""
    # Insert directly so we bypass the EstimateCreate.job_id requirement.
    orphan = Estimate(
        job_id=None,
        name="Imported - no job",
        status="draft",
    )
    db_session.add(orphan)
    db_session.commit()

    resp = client.get("/api/estimates", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1
    matches = [
        item for item in body["items"] if item["name"] == "Imported - no job"
    ]
    assert len(matches) == 1
    item = matches[0]
    assert item["job_id"] is None
    assert item["contact_id"] is None
    assert item["job_address"] is None


def test_list_estimates_with_orphan_estimate_and_empty_name(
    client, auth_headers, seeded_stages, db_session
):
    """Empty name + NULL job_id (closer to actual AccuLynx-import shape)."""
    db_session.add(
        Estimate(
            job_id=None,
            name="",
            status="draft",
        )
    )
    db_session.commit()
    resp = client.get("/api/estimates", headers=auth_headers)
    assert resp.status_code == 200, resp.text


def test_list_estimates_orphan_estimate_via_get_one(
    client, auth_headers, seeded_stages, db_session
):
    """Single-fetch path also exercised on an orphan."""
    orphan = Estimate(job_id=None, name="Imported", status="draft")
    db_session.add(orphan)
    db_session.commit()
    db_session.refresh(orphan)

    resp = client.get(f"/api/estimates/{orphan.id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == orphan.id
    assert resp.json()["job_id"] is None


def _create_job_via_api(client, auth_headers):
    contact = client.post(
        "/api/contacts",
        json={"name": "Multi-invoice client"},
        headers=auth_headers,
    ).json()
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
            "contact_id": contact["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
        },
        headers=auth_headers,
    ).json()


def test_list_estimates_handles_estimate_with_multiple_invoices(
    client, auth_headers, seeded_stages, db_session
):
    """Two invoices pointing at one estimate must not 500 the list endpoint.

    Repro: prod has deposit + final invoices per AccuLynx-imported
    estimate. The list response builder previously used .scalar() to
    pull the linked invoice_id, which raises MultipleResultsFound on
    a second invoice. This test fails before the fix and passes after.
    """
    job = _create_job_via_api(client, auth_headers)
    est = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Multi-invoice estimate"},
        headers=auth_headers,
    ).json()

    # Insert two invoices for the same estimate directly so we bypass the
    # POST flow's auto-numbering (which guarantees uniqueness of
    # invoice_number but not estimate_id).
    db_session.add(
        Invoice(
            job_id=job["id"],
            estimate_id=est["id"],
            invoice_number="INV-DEPOSIT-1",
            status="paid",
            subtotal=Decimal("100"),
            tax=Decimal("0"),
            total=Decimal("100"),
            is_deposit=True,
        )
    )
    db_session.add(
        Invoice(
            job_id=job["id"],
            estimate_id=est["id"],
            invoice_number="INV-FINAL-1",
            status="draft",
            subtotal=Decimal("900"),
            tax=Decimal("0"),
            total=Decimal("900"),
            is_deposit=False,
        )
    )
    db_session.commit()

    resp = client.get("/api/estimates", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    items = [i for i in resp.json()["items"] if i["id"] == est["id"]]
    assert len(items) == 1
    # invoice_id is populated with one of the linked invoices (the
    # deterministic earliest one) and the request doesn't 500.
    assert items[0]["invoice_id"] is not None


def test_get_estimate_handles_multiple_invoices(
    client, auth_headers, seeded_stages, db_session
):
    """Same scenario on the single-estimate GET path."""
    job = _create_job_via_api(client, auth_headers)
    est = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Multi-invoice estimate"},
        headers=auth_headers,
    ).json()
    for n, deposit in [("INV-A", True), ("INV-B", False)]:
        db_session.add(
            Invoice(
                job_id=job["id"],
                estimate_id=est["id"],
                invoice_number=n,
                status="draft",
                subtotal=Decimal("0"),
                tax=Decimal("0"),
                total=Decimal("0"),
                is_deposit=deposit,
            )
        )
    db_session.commit()

    resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["invoice_id"] is not None
