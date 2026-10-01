from datetime import date, timedelta


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


def _create_task(client, auth_headers, job_id=None, **overrides):
    data = {"title": "Test Task", **overrides}
    if job_id is not None:
        data["job_id"] = job_id
    resp = client.post("/api/tasks", json=data, headers=auth_headers)
    return resp.json()


# --- CRUD ---


def test_create_task(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.post(
        "/api/tasks",
        json={"job_id": job["id"], "title": "Order materials"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Order materials"
    assert data["status"] == "open"
    assert data["is_overdue"] is False


def test_create_task_with_due_date(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    task = _create_task(
        client, auth_headers, job["id"], due_date=tomorrow
    )
    assert task["due_date"] == tomorrow
    assert task["is_overdue"] is False


def test_create_task_invalid_job(client, auth_headers):
    resp = client.post(
        "/api/tasks",
        json={"job_id": 9999, "title": "Bad"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_get_task(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Test Task"


def test_get_task_not_found(client, auth_headers):
    resp = client.get("/api/tasks/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_list_tasks_by_job(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    _create_task(client, auth_headers, job["id"], title="Task 1")
    _create_task(client, auth_headers, job["id"], title="Task 2")

    resp = client.get(
        "/api/tasks",
        params={"job_id": job["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_list_tasks_by_status(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])
    client.patch(f"/api/tasks/{task['id']}/complete", headers=auth_headers)

    resp = client.get(
        "/api/tasks",
        params={"status": "completed"},
        headers=auth_headers,
    )
    data = resp.json()
    assert all(t["status"] == "completed" for t in data["items"])


def test_list_tasks_global(client, auth_headers, seeded_stages):
    job1 = _create_job(client, auth_headers, seeded_stages)
    job2 = _create_job(client, auth_headers, seeded_stages)
    _create_task(client, auth_headers, job1["id"])
    _create_task(client, auth_headers, job2["id"])

    resp = client.get("/api/tasks", headers=auth_headers)
    assert resp.json()["total"] == 2


def test_update_task(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])

    resp = client.put(
        f"/api/tasks/{task['id']}",
        json={"title": "Updated Title"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


def test_toggle_task_complete(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])
    assert task["status"] == "open"

    resp = client.patch(
        f"/api/tasks/{task['id']}/complete", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


def test_toggle_task_reopen(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])
    client.patch(f"/api/tasks/{task['id']}/complete", headers=auth_headers)

    resp = client.patch(
        f"/api/tasks/{task['id']}/complete", headers=auth_headers
    )
    assert resp.json()["status"] == "open"


def test_delete_task(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])

    resp = client.delete(
        f"/api/tasks/{task['id']}", headers=auth_headers
    )
    assert resp.status_code == 204
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_headers)
    assert resp.status_code == 404


# --- Overdue logic ---


def test_task_is_overdue(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    task = _create_task(
        client, auth_headers, job["id"], due_date=yesterday
    )
    assert task["is_overdue"] is True


def test_task_not_overdue_when_completed(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    task = _create_task(
        client, auth_headers, job["id"], due_date=yesterday
    )
    resp = client.patch(
        f"/api/tasks/{task['id']}/complete", headers=auth_headers
    )
    assert resp.json()["is_overdue"] is False


def test_task_not_overdue_no_due_date(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])
    assert task["is_overdue"] is False


def test_task_not_overdue_future_date(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    task = _create_task(
        client, auth_headers, job["id"], due_date=tomorrow
    )
    assert task["is_overdue"] is False


# --- Validation ---


def test_task_status_validation(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])

    resp = client.put(
        f"/api/tasks/{task['id']}",
        json={"status": "invalid"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# --- Auth ---


def test_tasks_require_auth(client):
    resp = client.get("/api/tasks")
    assert resp.status_code == 401

    resp = client.post("/api/tasks", json={"job_id": 1, "title": "X"})
    assert resp.status_code == 401


# --- Computed fields ---


def test_task_has_job_address(client, auth_headers, seeded_stages):
    job = _create_job(
        client, auth_headers, seeded_stages,
        property_address="456 Oak Ave",
    )
    task = _create_task(client, auth_headers, job["id"])
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_headers)
    assert resp.json()["job_address"] == "456 Oak Ave"


# --- Date filters ---


def test_list_tasks_due_date_from_filter(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    _create_task(client, auth_headers, job["id"], title="Old", due_date=yesterday)
    _create_task(client, auth_headers, job["id"], title="Future", due_date=tomorrow)

    resp = client.get(
        "/api/tasks",
        params={"due_date_from": date.today().isoformat()},
        headers=auth_headers,
    )
    data = resp.json()
    assert all(t["due_date"] >= date.today().isoformat() for t in data["items"])
    assert any(t["title"] == "Future" for t in data["items"])


def test_list_tasks_due_date_to_filter(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    _create_task(client, auth_headers, job["id"], title="Old", due_date=yesterday)
    _create_task(client, auth_headers, job["id"], title="Future", due_date=tomorrow)

    resp = client.get(
        "/api/tasks",
        params={"due_date_to": date.today().isoformat()},
        headers=auth_headers,
    )
    data = resp.json()
    assert all(t["due_date"] <= date.today().isoformat() for t in data["items"])
    assert any(t["title"] == "Old" for t in data["items"])


def test_list_tasks_combined_date_and_status_filter(
    client, auth_headers, seeded_stages
):
    job = _create_job(client, auth_headers, seeded_stages)
    today = date.today().isoformat()
    task1 = _create_task(
        client, auth_headers, job["id"], title="Open Today", due_date=today
    )
    task2 = _create_task(
        client, auth_headers, job["id"], title="Done Today", due_date=today
    )
    client.patch(f"/api/tasks/{task2['id']}/complete", headers=auth_headers)

    resp = client.get(
        "/api/tasks",
        params={
            "status": "open",
            "due_date_from": today,
            "due_date_to": today,
        },
        headers=auth_headers,
    )
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Open Today"


# --- Assignment & entity linking ---


def test_create_task_with_assigned_user(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])
    # Task defaults to current user (admin)
    assert task["assigned_to_user_id"] is not None
    assert task["assigned_to_name"] == "Admin User"


def test_create_task_without_job(client, auth_headers, seeded_stages):
    """Standalone task (no job_id)."""
    task = _create_task(client, auth_headers, title="Standalone task")
    assert task["job_id"] is None
    assert task["title"] == "Standalone task"
    assert task["assigned_to_user_id"] is not None


def test_filter_tasks_by_assigned_user(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)

    # Create employee
    emp_resp = client.post(
        "/api/employees",
        json={
            "full_name": "Filter User",
            "email": "filter@legacy.com",
            "password": "password123",
        },
        headers=auth_headers,
    )
    emp_id = emp_resp.json()["id"]

    _create_task(client, auth_headers, job["id"], title="Mine")
    _create_task(
        client, auth_headers, job["id"],
        title="Theirs", assigned_to_user_id=emp_id,
    )

    resp = client.get(
        "/api/tasks",
        params={"assigned_to_user_id": emp_id},
        headers=auth_headers,
    )
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Theirs"
    assert data["items"][0]["assigned_to_user_id"] == emp_id


def test_task_entity_linking(client, auth_headers, seeded_stages):
    contact_resp = client.post(
        "/api/contacts", json={"name": "Entity Test"}, headers=auth_headers
    )
    contact_id = contact_resp.json()["id"]

    task = _create_task(
        client, auth_headers,
        title="Link test",
        related_entity_type="contact",
        related_entity_id=contact_id,
    )
    assert task["related_entity_type"] == "contact"
    assert task["related_entity_id"] == contact_id
    assert task["related_entity_label"] == "Entity Test"


def test_task_entity_linking_job(client, auth_headers, seeded_stages):
    job = _create_job(
        client, auth_headers, seeded_stages,
        property_address="123 Main St",
    )
    task = _create_task(
        client, auth_headers, job["id"],
        title="Job link test",
        related_entity_type="job",
        related_entity_id=job["id"],
    )
    assert task["related_entity_label"] == "123 Main St"


def test_task_response_has_new_fields(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    task = _create_task(client, auth_headers, job["id"])
    resp = client.get(f"/api/tasks/{task['id']}", headers=auth_headers)
    data = resp.json()
    assert "assigned_to_user_id" in data
    assert "assigned_to_name" in data
    assert "related_entity_type" in data
    assert "related_entity_id" in data
    assert "related_entity_label" in data
