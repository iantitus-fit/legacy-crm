"""Tests for the multi-pipeline system."""
from decimal import Decimal


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts", json={"name": name}, headers=auth_headers
    )
    return resp.json()


def _get_pipeline(client, auth_headers, slug):
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    return next(p for p in pipelines if p["slug"] == slug)


def _get_stages(client, auth_headers, pipeline_id):
    return client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline_id}",
        headers=auth_headers,
    ).json()["items"]


# --- Pipeline list/detail ---


def test_list_pipelines(client, auth_headers, seeded_stages):
    response = client.get("/api/pipelines", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["items"][0]["slug"] == "leads"
    assert data["items"][1]["slug"] == "sales"
    assert data["items"][2]["slug"] == "jobs"


def test_list_pipelines_ordered_by_display_order(client, auth_headers, seeded_stages):
    response = client.get("/api/pipelines", headers=auth_headers)
    data = response.json()
    orders = [p["display_order"] for p in data["items"]]
    assert orders == sorted(orders)


def test_get_pipeline_with_stages(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    response = client.get(
        f"/api/pipelines/{pipeline['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Leads"
    assert len(data["stages"]) == 5
    assert data["stages"][0]["name"] == "Cold Leads"


def test_get_pipeline_not_found(client, auth_headers):
    response = client.get("/api/pipelines/9999", headers=auth_headers)
    assert response.status_code == 404


# --- Pipeline board ---


def test_pipeline_board_empty(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "sales")
    response = client.get(
        f"/api/pipelines/{pipeline['id']}/board", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_name"] == "Sales"
    assert data["total_deals"] == 0
    assert Decimal(data["total_value"]) == Decimal("0")
    assert len(data["stages"]) == 5


def test_pipeline_board_with_jobs(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "sales")
    stages = _get_stages(client, auth_headers, pipeline["id"])
    contact = _create_contact(client, auth_headers)

    client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
            "contract_value": "8000.00",
        },
        headers=auth_headers,
    )

    response = client.get(
        f"/api/pipelines/{pipeline['id']}/board", headers=auth_headers
    )
    data = response.json()
    assert data["total_deals"] == 1
    assert Decimal(data["total_value"]) == Decimal("8000.00")
    assert data["stages"][0]["job_count"] == 1


def test_pipeline_board_filter_by_salesperson(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    stages = _get_stages(client, auth_headers, pipeline["id"])

    # Create a job assigned to admin
    me_resp = client.get("/api/auth/me", headers=auth_headers)
    admin_id = me_resp.json()["id"]

    client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
            "assigned_to_user_id": admin_id,
        },
        headers=auth_headers,
    )
    # Create a job without assignment
    client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
        },
        headers=auth_headers,
    )

    # Filter by admin
    response = client.get(
        f"/api/pipelines/{pipeline['id']}/board?salesperson={admin_id}",
        headers=auth_headers,
    )
    assert response.json()["total_deals"] == 1


def test_pipeline_board_filter_by_lead_source(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    stages = _get_stages(client, auth_headers, pipeline["id"])

    client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
            "lead_source": "Google",
        },
        headers=auth_headers,
    )
    client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
            "lead_source": "Angi",
        },
        headers=auth_headers,
    )

    response = client.get(
        f"/api/pipelines/{pipeline['id']}/board?lead_source=Google",
        headers=auth_headers,
    )
    assert response.json()["total_deals"] == 1


# --- Stage management via pipelines router ---


def test_add_stage_to_pipeline(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    response = client.post(
        f"/api/pipelines/{pipeline['id']}/stages",
        json={
            "pipeline_id": pipeline["id"],
            "name": "Follow Up",
            "sort_order": 6,
            "color": "#FF5733",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Follow Up"
    assert data["color"] == "#FF5733"
    assert data["pipeline_id"] == pipeline["id"]


def test_add_duplicate_stage_name_same_pipeline_fails(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    response = client.post(
        f"/api/pipelines/{pipeline['id']}/stages",
        json={
            "pipeline_id": pipeline["id"],
            "name": "Cold Leads",
            "sort_order": 10,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_update_stage_via_pipeline(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    stages = _get_stages(client, auth_headers, pipeline["id"])

    response = client.put(
        f"/api/pipelines/{pipeline['id']}/stages/{stages[0]['id']}",
        json={"name": "Ice Cold", "color": "#0000FF"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Ice Cold"
    assert response.json()["color"] == "#0000FF"


def test_delete_stage_via_pipeline(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    # Add a new stage then delete it
    create_resp = client.post(
        f"/api/pipelines/{pipeline['id']}/stages",
        json={
            "pipeline_id": pipeline["id"],
            "name": "Temp",
            "sort_order": 99,
        },
        headers=auth_headers,
    )
    stage_id = create_resp.json()["id"]

    response = client.delete(
        f"/api/pipelines/{pipeline['id']}/stages/{stage_id}",
        headers=auth_headers,
    )
    assert response.status_code == 204


def test_delete_stage_with_jobs_fails(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    stages = _get_stages(client, auth_headers, pipeline["id"])

    # Create a job in this stage
    client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
        },
        headers=auth_headers,
    )

    response = client.delete(
        f"/api/pipelines/{pipeline['id']}/stages/{stages[0]['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_reorder_stages(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    stages = _get_stages(client, auth_headers, pipeline["id"])

    # Reverse the order
    reorder_payload = [
        {"id": s["id"], "sort_order": len(stages) - i}
        for i, s in enumerate(stages)
    ]

    response = client.put(
        f"/api/pipelines/{pipeline['id']}/stages/reorder",
        json={"stages": reorder_payload},
        headers=auth_headers,
    )
    assert response.status_code == 200
    result = response.json()
    # Verify the first stage is now what was last
    assert result[0]["id"] == stages[-1]["id"]


# --- Pipelines require auth ---


def test_pipelines_require_auth(client):
    response = client.get("/api/pipelines")
    assert response.status_code == 401


# --- Sprint 15c: contact-centric and estimate-centric boards ---


def test_contacts_board_empty(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "leads")
    resp = client.get(
        f"/api/pipelines/{pipeline['id']}/contacts-board", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline_id"] == pipeline["id"]
    assert data["total_contacts"] == 0
    assert len(data["stages"]) > 0
    assert all(s["contact_count"] == 0 for s in data["stages"])


def test_contacts_board_with_contact(client, auth_headers, seeded_stages):
    """Contact assigned to a Lead pipeline stage shows up on the board."""
    pipeline = _get_pipeline(client, auth_headers, "leads")
    stages = _get_stages(client, auth_headers, pipeline["id"])
    stage = stages[0]

    resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={
            "name": "Jane Commercial",
            "company": "Jane Inc",
            "client_type": "commercial",
            "lead_source": "Website",
            "pipeline_id": pipeline["id"],
            "stage_id": stage["id"],
        },
    )
    contact = resp.json()

    board = client.get(
        f"/api/pipelines/{pipeline['id']}/contacts-board", headers=auth_headers
    ).json()
    assert board["total_contacts"] == 1
    target_stage = next(s for s in board["stages"] if s["id"] == stage["id"])
    assert target_stage["contact_count"] == 1
    card = target_stage["contacts"][0]
    assert card["id"] == contact["id"]
    assert card["name"] == "Jane Commercial"
    assert card["company"] == "Jane Inc"
    assert card["client_type"] == "commercial"
    assert card["lead_source"] == "Website"
    assert card["estimate_count"] == 0


def test_estimates_board_empty(client, auth_headers, seeded_stages):
    pipeline = _get_pipeline(client, auth_headers, "jobs")
    resp = client.get(
        f"/api/pipelines/{pipeline['id']}/estimates-board", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_estimates"] == 0
    assert len(data["stages"]) > 0


def test_estimates_board_with_approved_estimate(
    client, auth_headers, seeded_stages, db_session
):
    """An internally-approved estimate appears on the estimates board."""
    from app.models.estimate import Estimate

    # Create a sales-pipeline job and an estimate on it
    contact = _create_contact(client, auth_headers)
    sales_pipeline = _get_pipeline(client, auth_headers, "sales")
    sales_stages = _get_stages(client, auth_headers, sales_pipeline["id"])
    job = client.post(
        "/api/jobs",
        headers=auth_headers,
        json={
            "pipeline_id": sales_pipeline["id"],
            "contact_id": contact["id"],
            "stage_id": sales_stages[0]["id"],
            "work_type": "retail",
        },
    ).json()
    est = client.post(
        "/api/estimates",
        headers=auth_headers,
        json={"job_id": job["id"], "name": "Roof Replacement"},
    ).json()
    client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Shingles", "qty": "10", "unit_price": "100.00"},
        headers=auth_headers,
    )

    # Mark it 'sent' (internal-approve requires draft/sent/viewed)
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "sent"
    db_session.commit()

    # Internally approve — this sets estimate.pipeline_id/stage_id to Jobs/Pending Schedule
    approve_resp = client.post(
        f"/api/estimates/{est['id']}/approve-internal",
        json={"signer_name": "Test User"},
        headers=auth_headers,
    )
    assert approve_resp.status_code == 200

    jobs_pipeline = _get_pipeline(client, auth_headers, "jobs")
    board = client.get(
        f"/api/pipelines/{jobs_pipeline['id']}/estimates-board",
        headers=auth_headers,
    ).json()
    assert board["total_estimates"] == 1
    pending = next(s for s in board["stages"] if s["name"] == "Pending Schedule")
    assert pending["estimate_count"] == 1
    card = pending["estimates"][0]
    assert card["id"] == est["id"]
    assert card["name"] == "Roof Replacement"
    assert card["status"] == "approved"
    assert card["contact_name"] == contact["name"]


def test_estimates_board_excludes_unapproved(
    client, auth_headers, seeded_stages, db_session
):
    """Estimates that aren't in a job-phase status are excluded."""
    pipeline = _get_pipeline(client, auth_headers, "jobs")
    stages = _get_stages(client, auth_headers, pipeline["id"])

    contact = _create_contact(client, auth_headers)
    sales_pipeline = _get_pipeline(client, auth_headers, "sales")
    sales_stages = _get_stages(client, auth_headers, sales_pipeline["id"])
    job = client.post(
        "/api/jobs",
        headers=auth_headers,
        json={
            "pipeline_id": sales_pipeline["id"],
            "contact_id": contact["id"],
            "stage_id": sales_stages[0]["id"],
            "work_type": "retail",
        },
    ).json()
    est = client.post(
        "/api/estimates",
        headers=auth_headers,
        json={"job_id": job["id"], "name": "Draft Only"},
    ).json()

    # Manually put it on the jobs pipeline stage but leave status as 'draft'
    from app.models.estimate import Estimate

    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.pipeline_id = pipeline["id"]
    est_obj.stage_id = stages[0]["id"]
    db_session.commit()

    board = client.get(
        f"/api/pipelines/{pipeline['id']}/estimates-board", headers=auth_headers
    ).json()
    assert board["total_estimates"] == 0
