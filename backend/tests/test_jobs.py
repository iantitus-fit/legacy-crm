"""Tests for jobs CRUD and pipeline board."""
from decimal import Decimal

from app.models.task import Task


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts", json={"name": name}, headers=auth_headers
    )
    return resp.json()


def _get_pipeline_and_stages(client, auth_headers, slug="jobs"):
    """Get a pipeline and its stages for test setup."""
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == slug)
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    return pipeline, stages


def _create_job(client, auth_headers, **overrides):
    """Create a job; fetches pipeline if not provided."""
    if "pipeline_id" not in overrides:
        pipeline, stages = _get_pipeline_and_stages(client, auth_headers)
        overrides.setdefault("pipeline_id", pipeline["id"])
        if "stage_id" not in overrides and stages:
            overrides.setdefault("stage_id", stages[0]["id"])
    data = {"work_type": "retail", **overrides}
    resp = client.post("/api/jobs", json=data, headers=auth_headers)
    return resp.json()


def test_create_job(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")

    response = client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact["id"],
            "stage_id": stages[0]["id"],
            "job_type": "roof",
            "work_type": "insurance",
            "property_address": "123 Main St, Kokomo, IN",
            "contract_value": "15000.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["contact_name"] == "Test Customer"
    assert data["stage_name"] == "Pending Schedule"
    assert data["pipeline_name"] == "Jobs"
    assert data["work_type"] == "insurance"
    assert data["job_type"] == "roof"
    assert Decimal(data["contract_value"]) == Decimal("15000.00")


def test_create_job_requires_pipeline_id(client, auth_headers, seeded_stages):
    response = client.post(
        "/api/jobs",
        json={"work_type": "retail"},
        headers=auth_headers,
    )
    assert response.status_code == 422  # validation error: pipeline_id required


def test_create_job_with_invalid_contact(client, auth_headers, seeded_stages):
    pipeline, _ = _get_pipeline_and_stages(client, auth_headers)
    response = client.post(
        "/api/jobs",
        json={"pipeline_id": pipeline["id"], "contact_id": 9999, "work_type": "retail"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Contact not found" in response.json()["detail"]


def test_create_job_defaults_to_first_stage(client, auth_headers, seeded_stages):
    """Job without stage_id gets the first stage of the pipeline."""
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "leads")
    response = client.post(
        "/api/jobs",
        json={"pipeline_id": pipeline["id"], "work_type": "retail"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["stage_name"] == "Cold Leads"


def test_create_job_validates_stage_belongs_to_pipeline(client, auth_headers, seeded_stages):
    """Cannot assign a stage from a different pipeline."""
    jobs_pipeline, _ = _get_pipeline_and_stages(client, auth_headers, "jobs")
    _, leads_stages = _get_pipeline_and_stages(client, auth_headers, "leads")
    response = client.post(
        "/api/jobs",
        json={
            "pipeline_id": jobs_pipeline["id"],
            "stage_id": leads_stages[0]["id"],
            "work_type": "retail",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "does not belong" in response.json()["detail"]


def test_list_jobs_empty(client, auth_headers):
    response = client.get("/api/jobs", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_jobs_with_data(client, auth_headers, seeded_stages):
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers)
    contact = _create_contact(client, auth_headers)
    _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"], contact_id=contact["id"], stage_id=stages[0]["id"],
    )
    _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"], contact_id=contact["id"], stage_id=stages[1]["id"],
    )

    response = client.get("/api/jobs", headers=auth_headers)
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_jobs_filter_by_pipeline(client, auth_headers, seeded_stages):
    jobs_pipeline, _ = _get_pipeline_and_stages(client, auth_headers, "jobs")
    leads_pipeline, _ = _get_pipeline_and_stages(client, auth_headers, "leads")
    _create_job(client, auth_headers, pipeline_id=jobs_pipeline["id"])
    _create_job(client, auth_headers, pipeline_id=leads_pipeline["id"])

    response = client.get(
        f"/api/jobs?pipeline_id={jobs_pipeline['id']}", headers=auth_headers
    )
    assert response.json()["total"] == 1


def test_list_jobs_filter_by_stage(client, auth_headers, seeded_stages):
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers)
    _create_job(client, auth_headers, pipeline_id=pipeline["id"], stage_id=stages[0]["id"])
    _create_job(client, auth_headers, pipeline_id=pipeline["id"], stage_id=stages[1]["id"])

    response = client.get(
        f"/api/jobs?stage_id={stages[0]['id']}", headers=auth_headers
    )
    assert response.json()["total"] == 1


def test_list_jobs_filter_by_work_type(client, auth_headers, seeded_stages):
    _create_job(client, auth_headers, work_type="insurance")
    _create_job(client, auth_headers, work_type="retail")

    response = client.get("/api/jobs?work_type=insurance", headers=auth_headers)
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["work_type"] == "insurance"


def test_list_jobs_filter_by_contact(client, auth_headers, seeded_stages):
    c1 = _create_contact(client, auth_headers, name="Alice")
    c2 = _create_contact(client, auth_headers, name="Bob")
    _create_job(client, auth_headers, contact_id=c1["id"])
    _create_job(client, auth_headers, contact_id=c2["id"])

    response = client.get(
        f"/api/jobs?contact_id={c1['id']}", headers=auth_headers
    )
    assert response.json()["total"] == 1


def test_list_jobs_search(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers, name="Smith Family")
    _create_job(client, auth_headers, contact_id=contact["id"])
    _create_job(client, auth_headers, property_address="456 Oak Ave")

    response = client.get("/api/jobs?search=Smith", headers=auth_headers)
    assert response.json()["total"] == 1

    response = client.get("/api/jobs?search=Oak", headers=auth_headers)
    assert response.json()["total"] == 1


def test_get_job_includes_computed_fields(client, auth_headers, seeded_stages):
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    contact = _create_contact(client, auth_headers, name="Dale Legacy")
    job = _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"],
        contact_id=contact["id"],
        stage_id=stages[0]["id"],
    )

    response = client.get(f"/api/jobs/{job['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["contact_name"] == "Dale Legacy"
    assert data["stage_name"] == "Pending Schedule"
    assert data["pipeline_name"] == "Jobs"


def test_get_job_not_found(client, auth_headers):
    response = client.get("/api/jobs/9999", headers=auth_headers)
    assert response.status_code == 404


def test_update_job_partial(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, property_address="Old Address")

    response = client.put(
        f"/api/jobs/{job['id']}",
        json={"property_address": "New Address", "contract_value": "25000.00"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["property_address"] == "New Address"
    assert Decimal(data["contract_value"]) == Decimal("25000.00")
    assert data["work_type"] == "retail"  # unchanged


def test_update_job_stage_via_patch(client, auth_headers, seeded_stages):
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    job = _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"], stage_id=stages[0]["id"],
    )

    response = client.patch(
        f"/api/jobs/{job['id']}/stage",
        json={"stage_id": stages[2]["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["stage_id"] == stages[2]["id"]
    assert response.json()["stage_name"] == "In Progress"


def test_patch_stage_validates_same_pipeline(client, auth_headers, seeded_stages):
    """Cannot drag a job to a stage in a different pipeline."""
    jobs_pipeline, jobs_stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    _, leads_stages = _get_pipeline_and_stages(client, auth_headers, "leads")
    job = _create_job(
        client, auth_headers,
        pipeline_id=jobs_pipeline["id"], stage_id=jobs_stages[0]["id"],
    )

    response = client.patch(
        f"/api/jobs/{job['id']}/stage",
        json={"stage_id": leads_stages[0]["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "does not belong" in response.json()["detail"]


def test_move_job_between_pipelines(client, auth_headers, seeded_stages):
    leads_pipeline, leads_stages = _get_pipeline_and_stages(client, auth_headers, "leads")
    sales_pipeline, sales_stages = _get_pipeline_and_stages(client, auth_headers, "sales")

    job = _create_job(
        client, auth_headers,
        pipeline_id=leads_pipeline["id"], stage_id=leads_stages[0]["id"],
    )

    response = client.put(
        f"/api/jobs/{job['id']}/pipeline",
        json={"pipeline_id": sales_pipeline["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_id"] == sales_pipeline["id"]
    assert data["pipeline_name"] == "Sales"
    # Should default to first stage of Sales
    assert data["stage_id"] == sales_stages[0]["id"]


def test_move_job_to_specific_stage(client, auth_headers, seeded_stages):
    leads_pipeline, leads_stages = _get_pipeline_and_stages(client, auth_headers, "leads")
    sales_pipeline, sales_stages = _get_pipeline_and_stages(client, auth_headers, "sales")

    job = _create_job(
        client, auth_headers,
        pipeline_id=leads_pipeline["id"], stage_id=leads_stages[0]["id"],
    )

    response = client.put(
        f"/api/jobs/{job['id']}/pipeline",
        json={"pipeline_id": sales_pipeline["id"], "stage_id": sales_stages[2]["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["stage_id"] == sales_stages[2]["id"]


def test_delete_job(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers)

    response = client.delete(f"/api/jobs/{job['id']}", headers=auth_headers)
    assert response.status_code == 204

    get_resp = client.get(f"/api/jobs/{job['id']}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_job_with_tasks_fails(client, auth_headers, db_session, seeded_stages):
    job = _create_job(client, auth_headers)

    task = Task(job_id=job["id"], title="Test task")
    db_session.add(task)
    db_session.commit()

    response = client.delete(f"/api/jobs/{job['id']}", headers=auth_headers)
    assert response.status_code == 400
    assert "associated record" in response.json()["detail"]


def test_pipeline_board(client, auth_headers, seeded_stages):
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    contact = _create_contact(client, auth_headers)
    _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"],
        contact_id=contact["id"],
        stage_id=stages[0]["id"],
        contract_value="10000.00",
    )

    response = client.get(
        f"/api/pipelines/{pipeline['id']}/board", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_name"] == "Jobs"
    assert len(data["stages"]) == 6

    first_stage = data["stages"][0]
    assert first_stage["job_count"] == 1
    assert Decimal(first_stage["total_value"]) == Decimal("10000.00")
    assert len(first_stage["jobs"]) == 1
    assert first_stage["jobs"][0]["contact_name"] == "Test Customer"
    assert first_stage["color"] is not None


def test_pipeline_board_totals(client, auth_headers, seeded_stages):
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"], stage_id=stages[0]["id"],
        contract_value="5000.00",
    )
    _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"], stage_id=stages[0]["id"],
        contract_value="7000.00",
    )

    response = client.get(
        f"/api/pipelines/{pipeline['id']}/board", headers=auth_headers
    )
    data = response.json()
    assert data["total_deals"] == 2
    assert Decimal(data["total_value"]) == Decimal("12000.00")
    first_stage = data["stages"][0]
    assert first_stage["job_count"] == 2
    assert Decimal(first_stage["total_value"]) == Decimal("12000.00")


def test_legacy_pipeline_board(client, auth_headers, seeded_stages):
    """Legacy /api/pipeline/board still works (returns Jobs pipeline)."""
    response = client.get("/api/pipeline/board", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_name"] == "Jobs"
    assert len(data["stages"]) == 6


def _create_crew(db_session, name="Schedule Crew", color="#3B82F6"):
    from app.models.crew import Crew
    crew = Crew(name=name, color=color)
    db_session.add(crew)
    db_session.commit()
    db_session.refresh(crew)
    return crew


def test_schedule_job(client, auth_headers, db_session, seeded_stages):
    """PATCH /api/jobs/{id}/schedule sets dates and auto-moves to Scheduled stage."""
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    crew = _create_crew(db_session)
    job = _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"], stage_id=stages[0]["id"],
    )

    from datetime import date, timedelta
    sched_date = date.today() + timedelta(days=2)
    end_date = date.today() + timedelta(days=4)

    response = client.patch(
        f"/api/jobs/{job['id']}/schedule",
        json={
            "scheduled_date": str(sched_date),
            "scheduled_end_date": str(end_date),
            "crew_id": crew.id,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scheduled_date"] == str(sched_date)
    assert data["scheduled_end_date"] == str(end_date)
    assert data["crew_id"] == crew.id
    assert data["crew_name"] == "Schedule Crew"
    assert data["crew_color"] == "#3B82F6"
    assert data["stage_name"] == "Scheduled"  # auto-moved


def test_schedule_job_without_crew(client, auth_headers, db_session, seeded_stages):
    """Schedule without crew_id should work."""
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    job = _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"], stage_id=stages[0]["id"],
    )

    from datetime import date, timedelta
    sched_date = date.today() + timedelta(days=1)

    response = client.patch(
        f"/api/jobs/{job['id']}/schedule",
        json={"scheduled_date": str(sched_date)},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scheduled_date"] == str(sched_date)
    assert data["crew_id"] is None
    assert data["crew_name"] is None


def test_schedule_job_invalid_crew(client, auth_headers, seeded_stages):
    """Invalid crew_id should return 400."""
    job = _create_job(client, auth_headers)

    from datetime import date, timedelta
    response = client.patch(
        f"/api/jobs/{job['id']}/schedule",
        json={
            "scheduled_date": str(date.today()),
            "crew_id": 9999,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Crew not found" in response.json()["detail"]


def test_schedule_fields_in_job_response(client, auth_headers, db_session, seeded_stages):
    """Schedule fields should appear in GET /api/jobs/{id} response."""
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    crew = _create_crew(db_session, "Response Crew", "#FF0000")
    job = _create_job(
        client, auth_headers,
        pipeline_id=pipeline["id"], stage_id=stages[0]["id"],
    )

    from datetime import date
    client.patch(
        f"/api/jobs/{job['id']}/schedule",
        json={"scheduled_date": str(date.today()), "crew_id": crew.id},
        headers=auth_headers,
    )

    response = client.get(f"/api/jobs/{job['id']}", headers=auth_headers)
    data = response.json()
    assert data["scheduled_date"] == str(date.today())
    assert data["crew_id"] == crew.id
    assert data["crew_name"] == "Response Crew"
    assert data["crew_color"] == "#FF0000"


def test_jobs_require_auth(client):
    response = client.get("/api/jobs")
    assert response.status_code == 401
