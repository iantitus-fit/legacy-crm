def test_create_contact(client, auth_headers):
    response = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={
            "name": "John Smith",
            "email": "john@example.com",
            "phone": "765-555-1234",
            "city": "Kokomo",
            "state": "IN",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "John Smith"
    assert data["email"] == "john@example.com"
    assert data["phone"] == "765-555-1234"
    assert data["id"] is not None


def test_create_contact_defaults_state_to_in(client, auth_headers):
    response = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "Jane Doe"},
    )
    assert response.status_code == 201
    assert response.json()["state"] == "IN"


def test_list_contacts_empty(client, auth_headers):
    response = client.get("/api/contacts", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["per_page"] == 25


def test_list_contacts_with_data(client, auth_headers):
    for i in range(3):
        client.post(
            "/api/contacts",
            headers=auth_headers,
            json={"name": f"Contact {i}"},
        )
    response = client.get("/api/contacts", headers=auth_headers)
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_list_contacts_search(client, auth_headers):
    client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "John Smith", "city": "Kokomo"},
    )
    client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "Jane Doe", "city": "Indianapolis"},
    )

    # Search by name
    response = client.get(
        "/api/contacts", headers=auth_headers, params={"search": "john"}
    )
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "John Smith"

    # Search by city
    response = client.get(
        "/api/contacts", headers=auth_headers, params={"search": "kokomo"}
    )
    assert response.json()["total"] == 1


def test_list_contacts_pagination(client, auth_headers):
    for i in range(5):
        client.post(
            "/api/contacts",
            headers=auth_headers,
            json={"name": f"Contact {i:02d}"},
        )

    response = client.get(
        "/api/contacts",
        headers=auth_headers,
        params={"page": 1, "per_page": 2},
    )
    data = response.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["per_page"] == 2

    response = client.get(
        "/api/contacts",
        headers=auth_headers,
        params={"page": 3, "per_page": 2},
    )
    data = response.json()
    assert len(data["items"]) == 1


def test_get_contact(client, auth_headers):
    create_resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "John Smith", "email": "john@example.com"},
    )
    contact_id = create_resp.json()["id"]

    response = client.get(
        f"/api/contacts/{contact_id}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["name"] == "John Smith"


def test_get_contact_not_found(client, auth_headers):
    response = client.get("/api/contacts/999", headers=auth_headers)
    assert response.status_code == 404


def test_update_contact_partial(client, auth_headers):
    create_resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "John Smith", "phone": "765-555-1234"},
    )
    contact_id = create_resp.json()["id"]

    response = client.put(
        f"/api/contacts/{contact_id}",
        headers=auth_headers,
        json={"phone": "765-555-9999"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "765-555-9999"
    assert data["name"] == "John Smith"  # unchanged


def test_delete_contact(client, auth_headers):
    create_resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "John Smith"},
    )
    contact_id = create_resp.json()["id"]

    response = client.delete(
        f"/api/contacts/{contact_id}", headers=auth_headers
    )
    assert response.status_code == 204

    # Verify it's gone
    response = client.get(
        f"/api/contacts/{contact_id}", headers=auth_headers
    )
    assert response.status_code == 404


def test_delete_contact_not_found(client, auth_headers):
    response = client.delete("/api/contacts/999", headers=auth_headers)
    assert response.status_code == 404


def test_contacts_require_auth(client):
    response = client.get("/api/contacts")
    assert response.status_code == 401

    response = client.post("/api/contacts", json={"name": "Test"})
    assert response.status_code == 401


def test_contact_company_field(client, auth_headers):
    resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={"name": "Acme Inc Contact", "company": "Acme Inc"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["company"] == "Acme Inc"
    contact_id = data["id"]

    resp = client.put(
        f"/api/contacts/{contact_id}",
        headers=auth_headers,
        json={"company": "Acme Ltd"},
    )
    assert resp.status_code == 200
    assert resp.json()["company"] == "Acme Ltd"


def test_contact_client_profile_fields(client, auth_headers, seeded_stages):
    """Sprint 15a: contacts accept and return lead_source, client_type, pipeline/stage."""
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    lead_pipeline = next(p for p in pipelines if p["slug"] == "leads")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={lead_pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]

    resp = client.post(
        "/api/contacts",
        headers=auth_headers,
        json={
            "name": "Big Corp Contact",
            "client_type": "commercial",
            "lead_source": "Referral",
            "pipeline_id": lead_pipeline["id"],
            "stage_id": stages[0]["id"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["client_type"] == "commercial"
    assert data["lead_source"] == "Referral"
    assert data["pipeline_id"] == lead_pipeline["id"]
    assert data["stage_id"] == stages[0]["id"]
    contact_id = data["id"]

    resp = client.put(
        f"/api/contacts/{contact_id}",
        headers=auth_headers,
        json={"client_type": "residential", "stage_id": stages[1]["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["client_type"] == "residential"
    assert resp.json()["stage_id"] == stages[1]["id"]
    assert resp.json()["lead_source"] == "Referral"  # unchanged

    resp = client.get(f"/api/contacts/{contact_id}", headers=auth_headers)
    assert resp.json()["pipeline_id"] == lead_pipeline["id"]
