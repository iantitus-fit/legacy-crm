"""Tests for GET /api/contacts/{contact_id}/tasks (Sprint 15.6a)."""


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts", json={"name": name}, headers=auth_headers
    )
    return resp.json()


def _create_job(client, auth_headers, contact_id):
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    resp = client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact_id,
            "stage_id": stages[0]["id"],
            "work_type": "retail",
        },
        headers=auth_headers,
    )
    return resp.json()


def _create_estimate(client, auth_headers, job_id):
    resp = client.post(
        "/api/estimates",
        json={"job_id": job_id, "name": "Test Estimate"},
        headers=auth_headers,
    )
    return resp.json()


def test_contact_tasks_returns_tasks_linked_directly_to_contact(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    client.post(
        "/api/tasks",
        json={
            "title": "Call client",
            "related_entity_type": "contact",
            "related_entity_id": contact["id"],
        },
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/contacts/{contact['id']}/tasks", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Call client"


def test_contact_tasks_returns_tasks_linked_to_contact_estimates(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])
    estimate = _create_estimate(client, auth_headers, job["id"])

    client.post(
        "/api/tasks",
        json={
            "title": "Send proposal",
            "related_entity_type": "estimate",
            "related_entity_id": estimate["id"],
        },
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/contacts/{contact['id']}/tasks", headers=auth_headers
    )
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert "Send proposal" in titles


def test_contact_tasks_returns_tasks_linked_to_legacy_jobs(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])

    # Task linked via related_entity (new style)
    client.post(
        "/api/tasks",
        json={
            "title": "Order shingles",
            "related_entity_type": "job",
            "related_entity_id": job["id"],
        },
        headers=auth_headers,
    )
    # Task linked via legacy job_id field
    client.post(
        "/api/tasks",
        json={"job_id": job["id"], "title": "Schedule crew"},
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/contacts/{contact['id']}/tasks", headers=auth_headers
    )
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert "Order shingles" in titles
    assert "Schedule crew" in titles


def test_contact_tasks_excludes_other_contacts_tasks(
    client, auth_headers, seeded_stages
):
    contact_a = _create_contact(client, auth_headers, "Client A")
    contact_b = _create_contact(client, auth_headers, "Client B")

    client.post(
        "/api/tasks",
        json={
            "title": "For A",
            "related_entity_type": "contact",
            "related_entity_id": contact_a["id"],
        },
        headers=auth_headers,
    )
    client.post(
        "/api/tasks",
        json={
            "title": "For B",
            "related_entity_type": "contact",
            "related_entity_id": contact_b["id"],
        },
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/contacts/{contact_a['id']}/tasks", headers=auth_headers
    )
    titles = [t["title"] for t in resp.json()]
    assert titles == ["For A"]


def test_contact_tasks_returns_empty_for_contact_with_no_tasks(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    resp = client.get(
        f"/api/contacts/{contact['id']}/tasks", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_contact_tasks_requires_auth(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
    resp = client.get(f"/api/contacts/{contact['id']}/tasks")
    assert resp.status_code == 401


def test_contact_tasks_404_for_unknown_contact(client, auth_headers):
    resp = client.get("/api/contacts/9999/tasks", headers=auth_headers)
    assert resp.status_code == 404


def test_contact_tasks_dedupes_when_task_matches_multiple_conditions(
    client, auth_headers, seeded_stages
):
    """A task with both job_id and related_entity (job, same job_id) must
    appear once, not twice."""
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])

    client.post(
        "/api/tasks",
        json={
            "job_id": job["id"],
            "title": "Dual link",
            "related_entity_type": "job",
            "related_entity_id": job["id"],
        },
        headers=auth_headers,
    )

    resp = client.get(
        f"/api/contacts/{contact['id']}/tasks", headers=auth_headers
    )
    data = resp.json()
    assert len([t for t in data if t["title"] == "Dual link"]) == 1
