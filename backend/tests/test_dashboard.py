"""Tests for dashboard stats with multi-pipeline architecture."""
from datetime import date, timedelta


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


def _create_job(client, auth_headers, pipeline_slug="jobs", **overrides):
    pipeline = _get_pipeline(client, auth_headers, pipeline_slug)
    stages = _get_stages(client, auth_headers, pipeline["id"])
    contact = _create_contact(client, auth_headers)
    data = {
        "pipeline_id": pipeline["id"],
        "contact_id": contact["id"],
        "stage_id": stages[0]["id"],
        "work_type": "retail",
        **overrides,
    }
    resp = client.post("/api/jobs", json=data, headers=auth_headers)
    return resp.json()


def _create_task(client, auth_headers, job_id=None, **overrides):
    data = {"title": "Test Task", **overrides}
    if job_id is not None:
        data["job_id"] = job_id
    resp = client.post("/api/tasks", json=data, headers=auth_headers)
    return resp.json()


# --- Dashboard Stats ---


def test_dashboard_stats_basic(client, auth_headers, seeded_stages):
    job = _create_job(
        client, auth_headers, pipeline_slug="jobs", contract_value="5000.00"
    )
    _create_task(client, auth_headers, job["id"])
    _create_contact(client, auth_headers, name="Extra Contact")

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["jobs_in_progress_count"] >= 1
    assert data["contact_count"] >= 2  # job contact + extra
    assert data["open_tasks"] >= 1
    assert float(data["pipeline_value"]) >= 5000
    assert isinstance(data["recent_jobs"], list)
    assert isinstance(data["tasks_due_today"], list)
    assert isinstance(data["tasks_due_this_week"], list)


def test_dashboard_new_leads_count(client, auth_headers, seeded_stages):
    _create_job(client, auth_headers, pipeline_slug="leads")
    _create_job(client, auth_headers, pipeline_slug="leads")

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert data["new_leads_count"] >= 2


def test_dashboard_active_proposals_count(client, auth_headers, seeded_stages):
    _create_job(client, auth_headers, pipeline_slug="sales")

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert data["active_proposals_count"] >= 1


def test_dashboard_recent_jobs_limit(client, auth_headers, seeded_stages):
    for i in range(12):
        _create_job(client, auth_headers)

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert len(data["recent_jobs"]) == 10


def test_dashboard_recent_jobs_include_pipeline(client, auth_headers, seeded_stages):
    _create_job(client, auth_headers, pipeline_slug="sales")

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert len(data["recent_jobs"]) >= 1
    assert data["recent_jobs"][0]["pipeline_name"] == "Sales"


def test_dashboard_tasks_due_today(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers)
    today = date.today().isoformat()
    _create_task(client, auth_headers, job["id"], due_date=today)

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert len(data["tasks_due_today"]) >= 1
    assert any(t["due_date"] == today for t in data["tasks_due_today"])


def test_dashboard_tasks_due_this_week(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers)
    two_days_out = (date.today() + timedelta(days=2)).isoformat()
    _create_task(client, auth_headers, job["id"], due_date=two_days_out)

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert len(data["tasks_due_this_week"]) >= 1
    # Should not be in today's list
    assert not any(
        t["due_date"] == two_days_out for t in data["tasks_due_today"]
    )


def test_dashboard_overdue_count(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    _create_task(client, auth_headers, job["id"], due_date=yesterday)

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert data["overdue_task_count"] >= 1


def test_dashboard_completed_tasks_excluded(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    task = _create_task(
        client, auth_headers, job["id"], due_date=yesterday
    )
    # Complete the task
    client.patch(f"/api/tasks/{task['id']}/complete", headers=auth_headers)

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    # The completed task should not count as open or overdue
    assert data["overdue_task_count"] == 0
    assert data["open_tasks"] == 0


def test_dashboard_pipeline_value_excludes_closed(client, auth_headers, seeded_stages):
    """Pipeline value should exclude jobs in 'Closed' stage."""
    jobs_pipeline = _get_pipeline(client, auth_headers, "jobs")
    stages = _get_stages(client, auth_headers, jobs_pipeline["id"])
    closed_stage = next(s for s in stages if s["name"] == "Closed")

    # Create a job in Closed stage
    contact = _create_contact(client, auth_headers)
    client.post(
        "/api/jobs",
        json={
            "pipeline_id": jobs_pipeline["id"],
            "contact_id": contact["id"],
            "stage_id": closed_stage["id"],
            "work_type": "retail",
            "contract_value": "10000.00",
        },
        headers=auth_headers,
    )

    # Create a normal active job in Jobs pipeline
    _create_job(
        client, auth_headers, pipeline_slug="jobs", contract_value="5000.00"
    )

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    pipeline_val = float(data["pipeline_value"])
    assert pipeline_val >= 5000
    assert pipeline_val < 15000  # should not include closed job


def test_dashboard_requires_auth(client):
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 401


# --- New Sprint 6 fields ---


def test_dashboard_my_tasks_today(client, auth_headers, seeded_stages):
    """my_tasks_today returns only tasks assigned to current user due today."""
    job = _create_job(client, auth_headers)
    today = date.today().isoformat()

    # Create task assigned to current user (admin) due today
    _create_task(client, auth_headers, job["id"], due_date=today, title="My task")

    # Create another employee and a task assigned to them
    emp_resp = client.post(
        "/api/employees",
        json={
            "full_name": "Other Person",
            "email": "other@legacy.com",
            "password": "password123",
        },
        headers=auth_headers,
    )
    emp_id = emp_resp.json()["id"]
    _create_task(
        client, auth_headers, job["id"],
        due_date=today, title="Their task",
        assigned_to_user_id=emp_id,
    )

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert len(data["my_tasks_today"]) >= 1
    assert all(t["title"] != "Their task" for t in data["my_tasks_today"])
    assert any(t["title"] == "My task" for t in data["my_tasks_today"])


def test_dashboard_employee_task_counts(client, auth_headers, seeded_stages):
    """Admin sees per-employee open task counts."""
    job = _create_job(client, auth_headers)

    # Create tasks for admin
    _create_task(client, auth_headers, job["id"], title="Admin task 1")
    _create_task(client, auth_headers, job["id"], title="Admin task 2")

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert isinstance(data["employee_task_counts"], list)
    assert len(data["employee_task_counts"]) >= 1
    admin_entry = next(
        (e for e in data["employee_task_counts"] if e["full_name"] == "Admin User"),
        None,
    )
    assert admin_entry is not None
    assert admin_entry["open_count"] >= 2


def test_dashboard_has_new_fields(client, auth_headers, seeded_stages):
    """Dashboard response includes new Sprint 6 fields."""
    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert "my_tasks_today" in data
    assert "employee_task_counts" in data


def test_dashboard_task_buckets(client, auth_headers, seeded_stages):
    """Sprint 14.5: dashboard returns past_due / today / future task buckets."""
    from datetime import date, timedelta

    job = _create_job(client, auth_headers)
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()
    next_week = (today + timedelta(days=7)).isoformat()

    _create_task(client, auth_headers, job["id"], title="Past1", due_date=yesterday)
    _create_task(client, auth_headers, job["id"], title="Past2", due_date=yesterday)
    _create_task(client, auth_headers, job["id"], title="Today1", due_date=today.isoformat())
    _create_task(client, auth_headers, job["id"], title="Future1", due_date=tomorrow)
    _create_task(client, auth_headers, job["id"], title="Future2", due_date=next_week)

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()

    assert "tasks_past_due" in data
    assert "tasks_today" in data
    assert "tasks_future" in data

    past_titles = [t["title"] for t in data["tasks_past_due"]]
    today_titles = [t["title"] for t in data["tasks_today"]]
    future_titles = [t["title"] for t in data["tasks_future"]]

    assert "Past1" in past_titles
    assert "Past2" in past_titles
    assert "Today1" in today_titles
    assert "Future1" in future_titles
    assert "Future2" in future_titles

    # past_due items should be flagged as overdue
    assert all(t["is_overdue"] for t in data["tasks_past_due"])
    # Buckets are limited to 5
    assert len(data["tasks_past_due"]) <= 5
    assert len(data["tasks_today"]) <= 5
    assert len(data["tasks_future"]) <= 5


def test_dashboard_open_invoices(client, auth_headers, seeded_stages, db_session):
    """Sprint 14.5: dashboard returns open_invoices where balance > 0."""
    from decimal import Decimal
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers)

    # Create an estimate on the job
    est_resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "For Invoicing"},
        headers=auth_headers,
    )
    est = est_resp.json()

    # Add a line item so the estimate has a total
    client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Work", "qty": "1", "unit_price": "1000.00"},
        headers=auth_headers,
    )

    # Approve estimate directly in DB (invoices require approved status)
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "approved"
    db_session.commit()

    # Create an invoice from the estimate
    inv_resp = client.post(
        "/api/invoices",
        json={"estimate_id": est["id"]},
        headers=auth_headers,
    )
    assert inv_resp.status_code == 201
    inv = inv_resp.json()
    assert Decimal(str(inv["balance"])) > 0

    resp = client.get("/api/dashboard/stats", headers=auth_headers)
    data = resp.json()
    assert "open_invoices" in data
    assert len(data["open_invoices"]) >= 1
    returned = next(
        (i for i in data["open_invoices"] if i["id"] == inv["id"]), None
    )
    assert returned is not None
    assert returned["invoice_number"] == inv["invoice_number"]
    assert Decimal(str(returned["balance"])) == Decimal(str(inv["balance"]))
    assert Decimal(str(returned["total"])) == Decimal(str(inv["total"]))
    assert returned["contact_name"] is not None
    assert len(data["open_invoices"]) <= 5


# --- Sprint 15c: new-model dashboard counts ---


def test_dashboard_v2_counts_from_contacts_and_estimates(
    client, auth_headers, seeded_stages, db_session
):
    """Dashboard v2 counts come from contacts and approved estimates."""
    from app.models.estimate import Estimate

    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    leads_pipeline = next(p for p in pipelines if p["slug"] == "leads")
    sales_pipeline = next(p for p in pipelines if p["slug"] == "sales")
    jobs_pipeline = next(p for p in pipelines if p["slug"] == "jobs")

    leads_stages = client.get(
        f"/api/pipeline-stages?pipeline_id={leads_pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    sales_stages = client.get(
        f"/api/pipeline-stages?pipeline_id={sales_pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]

    # Two leads-pipeline contacts
    for name in ["Lead A", "Lead B"]:
        client.post(
            "/api/contacts",
            headers=auth_headers,
            json={
                "name": name,
                "pipeline_id": leads_pipeline["id"],
                "stage_id": leads_stages[0]["id"],
            },
        )

    # One sales-pipeline contact
    client.post(
        "/api/contacts",
        headers=auth_headers,
        json={
            "name": "Sales C",
            "pipeline_id": sales_pipeline["id"],
            "stage_id": sales_stages[0]["id"],
        },
    )

    # One approved estimate in the Jobs pipeline
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers)  # contact's pipeline defaults to jobs
    est = client.post(
        "/api/estimates",
        headers=auth_headers,
        json={"job_id": job["id"], "name": "Work"},
    ).json()
    client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Labor", "qty": "1", "unit_price": "500"},
        headers=auth_headers,
    )
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "sent"
    db_session.commit()
    client.post(
        f"/api/estimates/{est['id']}/approve-internal",
        json={},
        headers=auth_headers,
    )

    stats = client.get("/api/dashboard/stats", headers=auth_headers).json()
    assert stats["new_leads_count_v2"] == 2
    assert stats["active_proposals_count_v2"] == 1
    assert stats["jobs_in_progress_count_v2"] == 1
    from decimal import Decimal
    assert Decimal(str(stats["pipeline_value_v2"])) > 0
