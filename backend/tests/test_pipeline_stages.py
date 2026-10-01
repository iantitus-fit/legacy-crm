"""Tests for pipeline stages CRUD and seeding."""
from app.models.job import Job
from app.models.pipeline import Pipeline


def test_seed_creates_default_stages(client, auth_headers, seeded_stages):
    """Default pipelines and stages are seeded on app startup."""
    response = client.get("/api/pipeline-stages", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    # 5 (Leads) + 5 (Sales) + 6 (Jobs) = 16 stages
    assert len(data["items"]) == 16


def test_seed_creates_three_pipelines(client, auth_headers, seeded_stages):
    """Three pipelines are seeded: Leads, Sales, Jobs."""
    response = client.get("/api/pipelines", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    slugs = [p["slug"] for p in data["items"]]
    assert slugs == ["leads", "sales", "jobs"]


def test_list_stages_returns_sorted(client, auth_headers, seeded_stages):
    """Stages are returned sorted by sort_order."""
    response = client.get("/api/pipeline-stages", headers=auth_headers)
    data = response.json()
    sort_orders = [s["sort_order"] for s in data["items"]]
    assert sort_orders == sorted(sort_orders)


def test_list_stages_filter_by_pipeline(client, auth_headers, seeded_stages, leads_pipeline):
    """Can filter stages by pipeline_id."""
    response = client.get(
        f"/api/pipeline-stages?pipeline_id={leads_pipeline.id}",
        headers=auth_headers,
    )
    data = response.json()
    assert len(data["items"]) == 5
    names = [s["name"] for s in data["items"]]
    assert "Cold Leads" in names


def test_get_single_stage(client, auth_headers, seeded_stages, leads_pipeline):
    """Can fetch a single stage by ID."""
    list_resp = client.get(
        f"/api/pipeline-stages?pipeline_id={leads_pipeline.id}",
        headers=auth_headers,
    )
    stage_id = list_resp.json()["items"][0]["id"]

    response = client.get(
        f"/api/pipeline-stages/{stage_id}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Cold Leads"
    assert response.json()["pipeline_id"] == leads_pipeline.id


def test_get_nonexistent_stage(client, auth_headers):
    response = client.get("/api/pipeline-stages/9999", headers=auth_headers)
    assert response.status_code == 404


def test_create_stage(client, auth_headers, seeded_stages, leads_pipeline):
    """Can create a custom pipeline stage."""
    response = client.post(
        "/api/pipeline-stages",
        json={
            "pipeline_id": leads_pipeline.id,
            "name": "Under Review",
            "sort_order": 7,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Under Review"
    assert data["sort_order"] == 7
    assert data["pipeline_id"] == leads_pipeline.id
    assert data["is_closed_won"] is False
    assert data["is_closed_lost"] is False


def test_create_stage_duplicate_name_same_pipeline_fails(
    client, auth_headers, seeded_stages, leads_pipeline
):
    """Cannot create a stage with a name that already exists in the same pipeline."""
    response = client.post(
        "/api/pipeline-stages",
        json={
            "pipeline_id": leads_pipeline.id,
            "name": "Cold Leads",
            "sort_order": 10,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_create_stage_duplicate_name_different_pipeline_ok(
    client, auth_headers, seeded_stages, leads_pipeline, sales_pipeline
):
    """Can create a stage with the same name in a different pipeline."""
    # "Cold Leads" exists in Leads pipeline; create it in Sales pipeline
    response = client.post(
        "/api/pipeline-stages",
        json={
            "pipeline_id": sales_pipeline.id,
            "name": "Cold Leads",
            "sort_order": 10,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201


def test_update_stage(client, auth_headers, seeded_stages, leads_pipeline):
    """Can update a stage's name and sort_order."""
    list_resp = client.get(
        f"/api/pipeline-stages?pipeline_id={leads_pipeline.id}",
        headers=auth_headers,
    )
    stage = list_resp.json()["items"][0]

    response = client.put(
        f"/api/pipeline-stages/{stage['id']}",
        json={"name": "Fresh Lead"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Fresh Lead"
    assert response.json()["sort_order"] == stage["sort_order"]


def test_update_stage_duplicate_name_fails(client, auth_headers, seeded_stages, leads_pipeline):
    """Cannot rename a stage to a name that already exists in the same pipeline."""
    list_resp = client.get(
        f"/api/pipeline-stages?pipeline_id={leads_pipeline.id}",
        headers=auth_headers,
    )
    stages = list_resp.json()["items"]

    response = client.put(
        f"/api/pipeline-stages/{stages[0]['id']}",
        json={"name": stages[1]["name"]},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_delete_stage(client, auth_headers, seeded_stages, leads_pipeline):
    """Can delete a stage with no associated records."""
    create_resp = client.post(
        "/api/pipeline-stages",
        json={
            "pipeline_id": leads_pipeline.id,
            "name": "Temp Stage",
            "sort_order": 99,
        },
        headers=auth_headers,
    )
    stage_id = create_resp.json()["id"]

    response = client.delete(
        f"/api/pipeline-stages/{stage_id}", headers=auth_headers
    )
    assert response.status_code == 204

    get_resp = client.get(
        f"/api/pipeline-stages/{stage_id}", headers=auth_headers
    )
    assert get_resp.status_code == 404


def test_delete_stage_with_jobs_fails(
    client, auth_headers, db_session, seeded_stages, leads_pipeline
):
    """Cannot delete a stage that has jobs."""
    list_resp = client.get(
        f"/api/pipeline-stages?pipeline_id={leads_pipeline.id}",
        headers=auth_headers,
    )
    stage_id = list_resp.json()["items"][0]["id"]

    job = Job(pipeline_id=leads_pipeline.id, stage_id=stage_id, work_type="retail")
    db_session.add(job)
    db_session.commit()

    response = client.delete(
        f"/api/pipeline-stages/{stage_id}", headers=auth_headers
    )
    assert response.status_code == 400
    assert "associated record" in response.json()["detail"]


def test_stages_require_auth(client):
    """Pipeline stage endpoints require authentication."""
    response = client.get("/api/pipeline-stages")
    assert response.status_code == 401
