"""Tests for crew management endpoints."""


def _create_employee(client, auth_headers, **overrides):
    data = {
        "full_name": "Crew Member",
        "email": "member@legacy.com",
        "password": "password123",
        "role": "crew",
        **overrides,
    }
    resp = client.post("/api/employees", json=data, headers=auth_headers)
    return resp.json()


def _create_crew(client, auth_headers, **overrides):
    data = {
        "name": "Test Crew",
        "color": "#3B82F6",
        **overrides,
    }
    return client.post("/api/crews", json=data, headers=auth_headers)


# --- CRUD ---


def test_create_crew(client, auth_headers):
    resp = _create_crew(client, auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Crew"
    assert data["color"] == "#3B82F6"
    assert data["is_active"] is True
    assert data["members"] == []


def test_create_crew_with_members(client, auth_headers):
    emp1 = _create_employee(client, auth_headers, email="m1@legacy.com", full_name="Member One")
    emp2 = _create_employee(client, auth_headers, email="m2@legacy.com", full_name="Member Two")

    resp = _create_crew(
        client,
        auth_headers,
        name="Full Crew",
        member_ids=[emp1["id"], emp2["id"]],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["members"]) == 2
    member_names = {m["full_name"] for m in data["members"]}
    assert "Member One" in member_names
    assert "Member Two" in member_names


def test_create_crew_duplicate_name(client, auth_headers):
    _create_crew(client, auth_headers, name="Dup Crew")
    resp = _create_crew(client, auth_headers, name="Dup Crew")
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"]


def test_list_crews(client, auth_headers):
    _create_crew(client, auth_headers, name="Crew A")
    _create_crew(client, auth_headers, name="Crew B")

    resp = client.get("/api/crews", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2


def test_get_crew(client, auth_headers):
    resp = _create_crew(client, auth_headers)
    crew_id = resp.json()["id"]

    resp = client.get(f"/api/crews/{crew_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Crew"


def test_get_crew_not_found(client, auth_headers):
    resp = client.get("/api/crews/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_crew(client, auth_headers):
    resp = _create_crew(client, auth_headers)
    crew_id = resp.json()["id"]

    resp = client.put(
        f"/api/crews/{crew_id}",
        json={"name": "Renamed Crew", "color": "#EF4444"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Renamed Crew"
    assert data["color"] == "#EF4444"


def test_update_crew_members(client, auth_headers):
    emp1 = _create_employee(client, auth_headers, email="up1@legacy.com")
    emp2 = _create_employee(client, auth_headers, email="up2@legacy.com")

    resp = _create_crew(
        client, auth_headers, name="Update Members Crew",
        member_ids=[emp1["id"]],
    )
    crew_id = resp.json()["id"]
    assert len(resp.json()["members"]) == 1

    # Replace members with emp2 only
    resp = client.put(
        f"/api/crews/{crew_id}",
        json={"member_ids": [emp2["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["members"]) == 1
    assert data["members"][0]["id"] == emp2["id"]


def test_deactivate_crew(client, auth_headers):
    resp = _create_crew(client, auth_headers, name="Deactivate Crew")
    crew_id = resp.json()["id"]

    resp = client.delete(f"/api/crews/{crew_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/crews/{crew_id}", headers=auth_headers)
    assert resp.json()["is_active"] is False


# --- Auth enforcement ---


def test_crews_require_auth(client):
    resp = client.get("/api/crews")
    assert resp.status_code == 401


def test_create_crew_requires_admin(client, auth_headers):
    # Create a staff user
    client.post(
        "/api/employees",
        json={
            "full_name": "Staff Guy",
            "email": "staffcrew@legacy.com",
            "password": "password123",
            "role": "staff",
        },
        headers=auth_headers,
    )
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "staffcrew@legacy.com", "password": "password123"},
    )
    staff_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = _create_crew(client, staff_headers, name="Staff Crew")
    assert resp.status_code == 403


def test_staff_can_list_crews(client, auth_headers):
    _create_crew(client, auth_headers, name="Visible Crew")

    client.post(
        "/api/employees",
        json={
            "full_name": "Staff Lister",
            "email": "stafflist2@legacy.com",
            "password": "password123",
            "role": "staff",
        },
        headers=auth_headers,
    )
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "stafflist2@legacy.com", "password": "password123"},
    )
    staff_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    resp = client.get("/api/crews", headers=staff_headers)
    assert resp.status_code == 200
