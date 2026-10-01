"""Tests for leads CRUD and lead-to-job conversion."""


def _create_contact(client, auth_headers, **overrides):
    data = {"name": "Test Customer", **overrides}
    resp = client.post("/api/contacts", json=data, headers=auth_headers)
    return resp.json()


def _create_lead(client, auth_headers, **overrides):
    data = {"contact_name": "New Lead Person", "source": "Website", **overrides}
    resp = client.post("/api/leads", json=data, headers=auth_headers)
    return resp.json()


def test_create_lead_with_existing_contact(client, auth_headers, seeded_stages):
    contact = _create_contact(client, auth_headers)
    response = client.post(
        "/api/leads",
        json={"contact_id": contact["id"], "source": "Referral", "description": "Needs new roof"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["contact_id"] == contact["id"]
    assert data["contact_name"] == "Test Customer"
    assert data["source"] == "Referral"
    assert data["stage_id"] is not None  # auto-assigned first Leads pipeline stage


def test_create_lead_with_inline_contact(client, auth_headers, seeded_stages):
    response = client.post(
        "/api/leads",
        json={
            "contact_name": "Jane Doe",
            "contact_phone": "765-555-1234",
            "contact_email": "jane@example.com",
            "source": "Google LSA",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["contact_name"] == "Jane Doe"
    assert data["contact_phone"] == "765-555-1234"
    assert data["contact_email"] == "jane@example.com"
    assert data["contact_id"] is not None


def test_create_lead_inline_requires_name(client, auth_headers):
    """Must provide contact_id or contact_name."""
    response = client.post(
        "/api/leads",
        json={"source": "Website"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "contact_id or contact_name" in response.json()["detail"]


def test_list_leads(client, auth_headers, seeded_stages):
    _create_lead(client, auth_headers, contact_name="Alice", source="Website")
    _create_lead(client, auth_headers, contact_name="Bob", source="Referral")

    response = client.get("/api/leads", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_leads_search_by_source(client, auth_headers, seeded_stages):
    _create_lead(client, auth_headers, contact_name="Alice", source="Google LSA")
    _create_lead(client, auth_headers, contact_name="Bob", source="Referral")

    response = client.get("/api/leads?search=Google", headers=auth_headers)
    assert response.json()["total"] == 1


def test_get_lead_includes_contact_info(client, auth_headers, seeded_stages):
    lead = _create_lead(
        client, auth_headers,
        contact_name="Dale",
        contact_phone="765-555-9999",
        contact_email="dale@test.com",
    )

    response = client.get(f"/api/leads/{lead['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["contact_name"] == "Dale"
    assert data["contact_phone"] == "765-555-9999"
    assert data["contact_email"] == "dale@test.com"


def test_update_lead(client, auth_headers, seeded_stages):
    lead = _create_lead(client, auth_headers, source="Website")

    response = client.put(
        f"/api/leads/{lead['id']}",
        json={"source": "Referral"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["source"] == "Referral"


def test_delete_lead(client, auth_headers, seeded_stages):
    lead = _create_lead(client, auth_headers)

    response = client.delete(f"/api/leads/{lead['id']}", headers=auth_headers)
    assert response.status_code == 204

    get_resp = client.get(f"/api/leads/{lead['id']}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_convert_lead_creates_job(client, auth_headers, seeded_stages):
    lead = _create_lead(client, auth_headers, source="Storm", contact_name="Storm Victim")

    response = client.post(
        f"/api/leads/{lead['id']}/convert",
        json={"job_type": "roof", "work_type": "insurance"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] is not None
    assert data["contact_id"] == lead["contact_id"]

    # Verify the job was created in Sales pipeline
    job_resp = client.get(f"/api/jobs/{data['job_id']}", headers=auth_headers)
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["job_type"] == "roof"
    assert job["work_type"] == "insurance"
    assert job["contact_name"] == "Storm Victim"
    assert job["pipeline_name"] == "Sales"
    assert job["lead_source"] == "Storm"


def test_convert_lead_deletes_lead(client, auth_headers, seeded_stages):
    lead = _create_lead(client, auth_headers)

    client.post(
        f"/api/leads/{lead['id']}/convert",
        json={"work_type": "retail"},
        headers=auth_headers,
    )

    # Lead should be gone
    get_resp = client.get(f"/api/leads/{lead['id']}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_convert_lead_preserves_source_in_notes(client, auth_headers, seeded_stages):
    lead = _create_lead(
        client, auth_headers,
        contact_name="Test",
        source="Google LSA",
        description="Saw our ad, needs inspection",
    )

    resp = client.post(
        f"/api/leads/{lead['id']}/convert",
        json={"work_type": "insurance"},
        headers=auth_headers,
    )
    job_resp = client.get(f"/api/jobs/{resp.json()['job_id']}", headers=auth_headers)
    notes = job_resp.json()["notes"]
    assert "Lead source: Google LSA" in notes
    assert "Saw our ad, needs inspection" in notes


def test_convert_lead_uses_sales_pipeline_first_stage(client, auth_headers, seeded_stages):
    """Converted lead gets Sales pipeline first stage (Draft)."""
    lead = _create_lead(client, auth_headers)

    resp = client.post(
        f"/api/leads/{lead['id']}/convert",
        json={"work_type": "retail"},
        headers=auth_headers,
    )
    job_resp = client.get(f"/api/jobs/{resp.json()['job_id']}", headers=auth_headers)
    assert job_resp.json()["stage_name"] == "Draft"
    assert job_resp.json()["pipeline_name"] == "Sales"


def test_convert_lead_uses_contact_address(client, auth_headers, seeded_stages):
    contact = _create_contact(
        client, auth_headers,
        name="Homeowner",
        address="100 Elm St",
        city="Kokomo",
        state="IN",
        zip="46901",
    )
    lead_resp = client.post(
        "/api/leads",
        json={"contact_id": contact["id"], "source": "Door Knock"},
        headers=auth_headers,
    )
    lead = lead_resp.json()

    resp = client.post(
        f"/api/leads/{lead['id']}/convert",
        json={"work_type": "retail"},
        headers=auth_headers,
    )
    job_resp = client.get(f"/api/jobs/{resp.json()['job_id']}", headers=auth_headers)
    assert "100 Elm St" in job_resp.json()["property_address"]
    assert "Kokomo" in job_resp.json()["property_address"]


def test_convert_nonexistent_lead_fails(client, auth_headers):
    response = client.post(
        "/api/leads/9999/convert",
        json={"work_type": "retail"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_leads_require_auth(client):
    response = client.get("/api/leads")
    assert response.status_code == 401
