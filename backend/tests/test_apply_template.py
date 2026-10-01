from decimal import Decimal

import pytest

from app.models.estimate import Estimate
from app.models.estimate_line_item import EstimateLineItem
from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
from app.models.contact import Contact
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage


@pytest.fixture()
def job_with_estimate(db_session, seeded_stages):
    contact = Contact(name="Test Customer", phone="555-1234")
    db_session.add(contact)
    db_session.flush()

    stage = db_session.query(PipelineStage).first()
    pipeline = db_session.query(Pipeline).first()
    job = Job(
        contact_id=contact.id,
        stage_id=stage.id,
        pipeline_id=pipeline.id,
        property_address="123 Main St",
    )
    db_session.add(job)
    db_session.flush()

    estimate = Estimate(
        job_id=job.id,
        name="Test Estimate",
        subtotal=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("0"),
    )
    db_session.add(estimate)
    db_session.commit()
    db_session.refresh(estimate)
    return estimate


@pytest.fixture()
def template_for_apply(db_session):
    t = EstimateTemplate(
        name="Test Template",
        default_margin_pct=Decimal("46.00"),
        default_waste_pct=Decimal("10.00"),
    )
    db_session.add(t)
    db_session.flush()

    items = [
        EstimateTemplateItem(
            template_id=t.id,
            description="Shingles",
            category="Roofing",
            unit_cost=Decimal("100.00"),
            uom="BD",
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="total_area",
            conversion_factor=Decimal("3.0000"),
            sort_order=0,
        ),
        EstimateTemplateItem(
            template_id=t.id,
            description="Labor",
            category="Labor",
            unit_cost=Decimal("500.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=Decimal("1.00"),
            sort_order=1,
        ),
    ]
    db_session.add_all(items)
    db_session.commit()
    db_session.refresh(t)
    return t


def test_apply_template(
    client, auth_headers, job_with_estimate, template_for_apply
):
    resp = client.post(
        f"/api/estimates/{job_with_estimate.id}/apply-template",
        headers=auth_headers,
        json={
            "template_id": template_for_apply.id,
            "measurements": {"total_area": "10.0"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    # Should have 2 line items
    assert len(data["line_items"]) == 2

    # Shingles: 10 * 3 = 30, +10% = 33, ceil = 33
    # Sell price: 100 * 1.46 = 146.00
    shingles = data["line_items"][0]
    assert shingles["description"] == "Shingles"
    assert int(Decimal(shingles["qty"])) == 33
    assert Decimal(shingles["unit_price"]) == Decimal("146.00")

    # Labor: qty 1, 500 * 1.46 = 730.00
    labor = data["line_items"][1]
    assert labor["description"] == "Labor"
    assert int(Decimal(labor["qty"])) == 1

    # Totals should be recalculated
    assert Decimal(data["subtotal"]) > Decimal("0")
    assert Decimal(data["total"]) > Decimal("0")


def test_apply_template_to_existing_items(
    client, auth_headers, job_with_estimate, template_for_apply, db_session
):
    """Applying a template appends to existing line items."""
    existing = EstimateLineItem(
        estimate_id=job_with_estimate.id,
        description="Existing Item",
        qty=Decimal("1"),
        unit_price=Decimal("100.00"),
        line_total=Decimal("100.00"),
        sort_order=0,
    )
    db_session.add(existing)
    db_session.commit()

    resp = client.post(
        f"/api/estimates/{job_with_estimate.id}/apply-template",
        headers=auth_headers,
        json={
            "template_id": template_for_apply.id,
            "measurements": {"total_area": "10.0"},
        },
    )
    assert resp.status_code == 200
    assert len(resp.json()["line_items"]) == 3


def test_apply_template_not_found(client, auth_headers, job_with_estimate):
    resp = client.post(
        f"/api/estimates/{job_with_estimate.id}/apply-template",
        headers=auth_headers,
        json={
            "template_id": 99999,
            "measurements": {"total_area": "10.0"},
        },
    )
    assert resp.status_code == 404


def test_apply_template_estimate_not_found(
    client, auth_headers, template_for_apply
):
    resp = client.post(
        "/api/estimates/99999/apply-template",
        headers=auth_headers,
        json={
            "template_id": template_for_apply.id,
            "measurements": {"total_area": "10.0"},
        },
    )
    assert resp.status_code == 404
