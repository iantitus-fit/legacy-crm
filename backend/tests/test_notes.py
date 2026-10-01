"""Tests for the notes API (Sprint 8)."""


# ── Helpers ──────────────────────────────────────────────────────────


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post("/api/contacts", json={"name": name}, headers=auth_headers)
    return resp.json()


def _create_job(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
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
            "contact_id": contact["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
        },
        headers=auth_headers,
    )
    return resp.json()


def _create_second_user(client, auth_headers):
    client.post(
        "/api/auth/register",
        json={
            "email": "second@legacy.com",
            "full_name": "Second User",
            "password": "testpassword123",
        },
        headers=auth_headers,
    )
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "second@legacy.com", "password": "testpassword123"},
    )
    return login_resp.json()["access_token"]


def _create_note(client, auth_headers, entity_type, entity_id, note_type="company", content="Test note"):
    resp = client.post(
        "/api/notes",
        json={
            "entity_type": entity_type,
            "entity_id": entity_id,
            "note_type": note_type,
            "content": content,
        },
        headers=auth_headers,
    )
    return resp


# ── CRUD Tests ───────────────────────────────────────────────────────


def test_create_note_for_job(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = _create_note(client, auth_headers, "job", job["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["entity_type"] == "job"
    assert data["entity_id"] == job["id"]
    assert data["note_type"] == "company"
    assert data["content"] == "Test note"
    assert data["created_by_name"] is not None


def test_create_note_for_contact(client, auth_headers):
    contact = _create_contact(client, auth_headers)
    resp = _create_note(client, auth_headers, "contact", contact["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["entity_type"] == "contact"
    assert data["entity_id"] == contact["id"]


def test_create_crew_note(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = _create_note(client, auth_headers, "job", job["id"], note_type="crew", content="Crew note")
    assert resp.status_code == 201
    assert resp.json()["note_type"] == "crew"


def test_create_client_note(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = _create_note(client, auth_headers, "job", job["id"], note_type="client", content="Client note")
    assert resp.status_code == 201
    assert resp.json()["note_type"] == "client"


def test_list_notes_by_entity(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    _create_note(client, auth_headers, "job", job["id"], content="Note 1")
    _create_note(client, auth_headers, "job", job["id"], content="Note 2")

    resp = client.get(
        f"/api/notes?entity_type=job&entity_id={job['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_notes_filter_by_note_type(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    _create_note(client, auth_headers, "job", job["id"], note_type="crew", content="Crew note")
    _create_note(client, auth_headers, "job", job["id"], note_type="client", content="Client note")
    _create_note(client, auth_headers, "job", job["id"], note_type="company", content="Company note")

    resp = client.get(
        f"/api/notes?entity_type=job&entity_id={job['id']}&note_type=crew",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["note_type"] == "crew"


def test_list_notes_newest_first(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    _create_note(client, auth_headers, "job", job["id"], content="First note")
    _create_note(client, auth_headers, "job", job["id"], content="Second note")

    resp = client.get(
        f"/api/notes?entity_type=job&entity_id={job['id']}",
        headers=auth_headers,
    )
    items = resp.json()["items"]
    assert items[0]["content"] == "Second note"
    assert items[1]["content"] == "First note"


def test_update_note(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    note = _create_note(client, auth_headers, "job", job["id"]).json()

    resp = client.put(
        f"/api/notes/{note['id']}",
        json={"content": "Updated content"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "Updated content"


def test_delete_note(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    note = _create_note(client, auth_headers, "job", job["id"]).json()

    resp = client.delete(f"/api/notes/{note['id']}", headers=auth_headers)
    assert resp.status_code == 204

    # Verify gone
    resp = client.get(
        f"/api/notes?entity_type=job&entity_id={job['id']}",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 0


# ── Validation Tests ─────────────────────────────────────────────────


def test_create_note_invalid_entity_type(client, auth_headers):
    resp = client.post(
        "/api/notes",
        json={
            "entity_type": "invoice",
            "entity_id": 1,
            "note_type": "company",
            "content": "Should fail",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_note_invalid_note_type(client, auth_headers):
    contact = _create_contact(client, auth_headers)
    resp = client.post(
        "/api/notes",
        json={
            "entity_type": "contact",
            "entity_id": contact["id"],
            "note_type": "invalid",
            "content": "Should fail",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_note_nonexistent_entity(client, auth_headers):
    resp = client.post(
        "/api/notes",
        json={
            "entity_type": "job",
            "entity_id": 99999,
            "note_type": "company",
            "content": "Should fail",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_update_nonexistent_note(client, auth_headers):
    resp = client.put(
        "/api/notes/99999",
        json={"content": "nope"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_delete_nonexistent_note(client, auth_headers):
    resp = client.delete("/api/notes/99999", headers=auth_headers)
    assert resp.status_code == 404


# ── Authorization Tests ──────────────────────────────────────────────


def test_update_note_only_author(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    note = _create_note(client, auth_headers, "job", job["id"]).json()

    # Create second user
    second_token = _create_second_user(client, auth_headers)
    second_headers = {"Authorization": f"Bearer {second_token}"}

    resp = client.put(
        f"/api/notes/{note['id']}",
        json={"content": "Hacked!"},
        headers=second_headers,
    )
    assert resp.status_code == 403


def test_delete_note_only_author_or_admin(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)

    # Create second user and their note
    second_token = _create_second_user(client, auth_headers)
    second_headers = {"Authorization": f"Bearer {second_token}"}
    note = _create_note(client, second_headers, "job", job["id"]).json()

    # Admin can delete other user's note
    resp = client.delete(f"/api/notes/{note['id']}", headers=auth_headers)
    assert resp.status_code == 204


def test_delete_note_non_author_non_admin_forbidden(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    note = _create_note(client, auth_headers, "job", job["id"]).json()

    # Second user (staff) can't delete admin's note
    second_token = _create_second_user(client, auth_headers)
    second_headers = {"Authorization": f"Bearer {second_token}"}

    resp = client.delete(f"/api/notes/{note['id']}", headers=second_headers)
    assert resp.status_code == 403


# ── Response Shape Tests ─────────────────────────────────────────────


def test_note_response_has_created_by_name(client, auth_headers):
    contact = _create_contact(client, auth_headers)
    resp = _create_note(client, auth_headers, "contact", contact["id"])
    data = resp.json()
    assert "created_by_name" in data
    assert data["created_by_name"] == "Admin User"
    assert "created_at" in data
    assert "updated_at" in data


def test_notes_segregated_by_type(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    _create_note(client, auth_headers, "job", job["id"], note_type="crew", content="Crew 1")
    _create_note(client, auth_headers, "job", job["id"], note_type="crew", content="Crew 2")
    _create_note(client, auth_headers, "job", job["id"], note_type="client", content="Client 1")
    _create_note(client, auth_headers, "job", job["id"], note_type="company", content="Company 1")

    # Crew notes
    resp = client.get(
        f"/api/notes?entity_type=job&entity_id={job['id']}&note_type=crew",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 2

    # Client notes
    resp = client.get(
        f"/api/notes?entity_type=job&entity_id={job['id']}&note_type=client",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 1

    # Company notes
    resp = client.get(
        f"/api/notes?entity_type=job&entity_id={job['id']}&note_type=company",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 1

    # All notes for this job
    resp = client.get(
        f"/api/notes?entity_type=job&entity_id={job['id']}",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 4


# ── Estimate Notes ──────────────────────────────────────────────────


def _create_estimate(client, auth_headers, job_id):
    resp = client.post(
        "/api/estimates",
        json={"job_id": job_id, "name": "Test Estimate"},
        headers=auth_headers,
    )
    return resp.json()


def test_create_note_for_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = _create_note(client, auth_headers, "estimate", est["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["entity_type"] == "estimate"
    assert data["entity_id"] == est["id"]
    assert data["note_type"] == "company"


def test_estimate_notes_three_tiers(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    for tier in ["crew", "client", "company"]:
        resp = _create_note(client, auth_headers, "estimate", est["id"], note_type=tier, content=f"{tier} note")
        assert resp.status_code == 201
        assert resp.json()["note_type"] == tier

    resp = client.get(
        f"/api/notes?entity_type=estimate&entity_id={est['id']}",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 3


def test_filter_notes_by_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est1 = _create_estimate(client, auth_headers, job["id"])
    est2 = _create_estimate(client, auth_headers, job["id"])
    _create_note(client, auth_headers, "estimate", est1["id"], content="Est1 note")
    _create_note(client, auth_headers, "estimate", est2["id"], content="Est2 note")

    resp = client.get(
        f"/api/notes?entity_type=estimate&entity_id={est1['id']}",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["content"] == "Est1 note"


def test_create_note_nonexistent_estimate(client, auth_headers):
    resp = _create_note(client, auth_headers, "estimate", 99999)
    assert resp.status_code == 400
