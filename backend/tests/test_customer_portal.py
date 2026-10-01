from uuid import uuid4

from app.models.estimate_status_history import EstimateStatusHistory
from app.models.estimate_token import EstimateToken


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts", json={"name": name}, headers=auth_headers
    )
    return resp.json()


def _create_job(client, auth_headers, seeded_stages, **overrides):
    contact = _create_contact(client, auth_headers)
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    data = {
        "pipeline_id": pipeline["id"],
        "contact_id": contact["id"],
        "stage_id": stages[0]["id"],
        "work_type": "retail",
        **overrides,
    }
    resp = client.post("/api/jobs", json=data, headers=auth_headers)
    return resp.json()


def _create_estimate(client, auth_headers, job_id, **overrides):
    data = {"job_id": job_id, "name": "Test Estimate", **overrides}
    resp = client.post("/api/estimates", json=data, headers=auth_headers)
    return resp.json()


def _create_token_for_estimate(db_session, estimate_id, status="sent"):
    """Create a portal token and optionally set estimate status."""
    from app.models.estimate import Estimate

    token_value = uuid4().hex
    db_session.add(EstimateToken(
        estimate_id=estimate_id,
        token=token_value,
    ))
    estimate = db_session.query(Estimate).filter(Estimate.id == estimate_id).first()
    estimate.status = status
    db_session.commit()
    return token_value


# --- Basic status defaults ---


def test_new_estimate_has_draft_status(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    assert estimate["status"] == "draft"


def test_estimate_list_includes_status(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    _create_estimate(client, auth_headers, job["id"])
    resp = client.get("/api/estimates", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) > 0
    assert "status" in items[0]
    assert items[0]["status"] == "draft"


# --- Invalid token ---


def test_invalid_token_returns_404(client, seeded_stages):
    resp = client.get("/api/portal/badtoken123")
    assert resp.status_code == 404


def test_invalid_token_preview_returns_404(client, seeded_stages):
    resp = client.get("/api/portal/badtoken123/preview")
    assert resp.status_code == 404


# --- GET /api/portal/{token} ---


def test_portal_get_estimate(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.get(f"/api/portal/{token}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == estimate["id"]
    assert data["name"] == "Test Estimate"
    assert data["status"] == "viewed"


def test_portal_first_view_sets_viewed(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"], status="sent")

    # First access
    resp = client.get(f"/api/portal/{token}")
    assert resp.json()["status"] == "viewed"

    # Check status history was created
    history = db_session.query(EstimateStatusHistory).filter(
        EstimateStatusHistory.estimate_id == estimate["id"],
        EstimateStatusHistory.status == "viewed",
    ).first()
    assert history is not None


def test_portal_second_view_does_not_change_status(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"], status="sent")

    # First access sets to viewed
    client.get(f"/api/portal/{token}")
    # Second access should stay viewed
    resp = client.get(f"/api/portal/{token}")
    assert resp.json()["status"] == "viewed"

    # Only one viewed entry
    count = db_session.query(EstimateStatusHistory).filter(
        EstimateStatusHistory.estimate_id == estimate["id"],
        EstimateStatusHistory.status == "viewed",
    ).count()
    assert count == 1


# --- POST /api/portal/{token}/request-changes ---


def test_portal_request_changes(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.post(
        f"/api/portal/{token}/request-changes",
        json={"message": "Please lower the price"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify status changed
    from app.models.estimate import Estimate
    est = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    db_session.refresh(est)
    assert est.status == "changes_requested"

    # Verify history
    history = db_session.query(EstimateStatusHistory).filter(
        EstimateStatusHistory.estimate_id == estimate["id"],
        EstimateStatusHistory.status == "changes_requested",
    ).first()
    assert history is not None
    assert history.notes == "Please lower the price"


# --- POST /api/portal/{token}/reject ---


def test_portal_reject(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.post(
        f"/api/portal/{token}/reject",
        json={"name": "John Smith", "reason": "Too expensive"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    history = db_session.query(EstimateStatusHistory).filter(
        EstimateStatusHistory.estimate_id == estimate["id"],
        EstimateStatusHistory.status == "rejected",
    ).first()
    assert history is not None
    assert history.changed_by_name == "John Smith"
    assert history.notes == "Too expensive"


# --- POST /api/portal/{token}/approve ---


def test_portal_approve(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.post(
        f"/api/portal/{token}/approve",
        json={
            "signer_name": "John Smith",
            "signature_data": "data:image/png;base64,iVBORw0KGgo=",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    from app.models.estimate import Estimate
    est = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    db_session.refresh(est)
    assert est.status == "approved"

    # Verify signature saved
    from app.models.estimate_signature import EstimateSignature
    sig = db_session.query(EstimateSignature).filter(
        EstimateSignature.estimate_id == estimate["id"],
    ).first()
    assert sig is not None
    assert sig.signer_name == "John Smith"
    assert sig.terms_accepted is True

    # Verify history
    history = db_session.query(EstimateStatusHistory).filter(
        EstimateStatusHistory.estimate_id == estimate["id"],
        EstimateStatusHistory.status == "approved",
    ).first()
    assert history is not None


def test_portal_approve_requires_signer_name(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.post(
        f"/api/portal/{token}/approve",
        json={
            "signer_name": "",
            "signature_data": "data:image/png;base64,abc",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 422


def test_portal_approve_requires_signature_data(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.post(
        f"/api/portal/{token}/approve",
        json={
            "signer_name": "John",
            "signature_data": "",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 422


def test_portal_approve_requires_terms_accepted(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.post(
        f"/api/portal/{token}/approve",
        json={
            "signer_name": "John",
            "signature_data": "data:image/png;base64,abc",
            "terms_accepted": False,
        },
    )
    assert resp.status_code == 422


# --- Portal does not require auth ---


def test_portal_no_auth_required(client, auth_headers, seeded_stages, db_session):
    """Portal endpoints work without any Authorization header."""
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    # No auth headers
    resp = client.get(f"/api/portal/{token}")
    assert resp.status_code == 200


# --- Status history IP tracking ---


def test_status_history_captures_ip(client, auth_headers, seeded_stages, db_session):
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"], status="sent")

    client.get(f"/api/portal/{token}")

    history = db_session.query(EstimateStatusHistory).filter(
        EstimateStatusHistory.estimate_id == estimate["id"],
        EstimateStatusHistory.status == "viewed",
    ).first()
    assert history is not None
    # TestClient uses testclient, IP may be set
    assert history.ip_address is not None


def test_approve_moves_job_to_pending_schedule(client, auth_headers, seeded_stages, db_session):
    """Approving an estimate auto-moves the parent job to Pending Schedule in Jobs pipeline."""
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.post(
        f"/api/portal/{token}/approve",
        json={
            "signer_name": "John Smith",
            "signature_data": "data:image/png;base64,iVBORw0KGgo=",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 200

    from app.models.job import Job
    from app.models.pipeline import Pipeline
    from app.models.pipeline_stage import PipelineStage

    updated_job = db_session.query(Job).filter(Job.id == job["id"]).first()
    db_session.refresh(updated_job)

    jobs_pipeline = db_session.query(Pipeline).filter(Pipeline.slug == "jobs").first()
    pending_stage = db_session.query(PipelineStage).filter(
        PipelineStage.pipeline_id == jobs_pipeline.id,
        PipelineStage.name == "Pending Schedule",
    ).first()

    assert updated_job.pipeline_id == jobs_pipeline.id
    assert updated_job.stage_id == pending_stage.id


def test_approve_succeeds_when_pending_schedule_missing(client, auth_headers, seeded_stages, db_session):
    """If Pending Schedule stage doesn't exist, approval still succeeds."""
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    # Delete the Pending Schedule stage so the lookup fails
    from app.models.pipeline import Pipeline
    from app.models.pipeline_stage import PipelineStage

    jobs_pipeline = db_session.query(Pipeline).filter(Pipeline.slug == "jobs").first()
    pending_stage = db_session.query(PipelineStage).filter(
        PipelineStage.pipeline_id == jobs_pipeline.id,
        PipelineStage.name == "Pending Schedule",
    ).first()
    if pending_stage:
        db_session.delete(pending_stage)
        db_session.commit()

    resp = client.post(
        f"/api/portal/{token}/approve",
        json={
            "signer_name": "John Smith",
            "signature_data": "data:image/png;base64,iVBORw0KGgo=",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Estimate should still be approved
    from app.models.estimate import Estimate
    est = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    db_session.refresh(est)
    assert est.status == "approved"

    # Signature should still be saved
    from app.models.estimate_signature import EstimateSignature
    sig = db_session.query(EstimateSignature).filter(
        EstimateSignature.estimate_id == estimate["id"],
    ).first()
    assert sig is not None


def test_reject_without_reason(client, auth_headers, seeded_stages, db_session):
    """Reject with no reason should still work (reason is optional)."""
    job = _create_job(client, auth_headers, seeded_stages)
    estimate = _create_estimate(client, auth_headers, job["id"])
    token = _create_token_for_estimate(db_session, estimate["id"])

    resp = client.post(
        f"/api/portal/{token}/reject",
        json={"name": "Jane Doe"},
    )
    assert resp.status_code == 200

    history = db_session.query(EstimateStatusHistory).filter(
        EstimateStatusHistory.estimate_id == estimate["id"],
        EstimateStatusHistory.status == "rejected",
    ).first()
    assert history is not None
    assert history.notes is None
