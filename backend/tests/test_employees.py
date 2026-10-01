"""Tests for employee management endpoints."""


def _create_employee(client, auth_headers, **overrides):
    data = {
        "full_name": "Test Employee",
        "email": "test.emp@legacy.com",
        "password": "password123",
        "role": "staff",
        **overrides,
    }
    return client.post("/api/employees", json=data, headers=auth_headers)


# --- CRUD ---


def test_create_employee(client, auth_headers):
    resp = _create_employee(client, auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["full_name"] == "Test Employee"
    assert data["email"] == "test.emp@legacy.com"
    assert data["role"] == "staff"
    assert data["is_active"] is True


def test_create_employee_with_phone_and_color(client, auth_headers):
    resp = _create_employee(
        client,
        auth_headers,
        email="color@legacy.com",
        phone="(765) 555-0001",
        color="#3B82F6",
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["phone"] == "(765) 555-0001"
    assert data["color"] == "#3B82F6"


def test_create_employee_crew_role(client, auth_headers):
    resp = _create_employee(
        client,
        auth_headers,
        email="crew@legacy.com",
        role="crew",
    )
    assert resp.status_code == 201
    assert resp.json()["role"] == "crew"


def test_create_employee_duplicate_email(client, auth_headers):
    _create_employee(client, auth_headers, email="dup@legacy.com")
    resp = _create_employee(client, auth_headers, email="dup@legacy.com")
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"]


def test_list_employees(client, auth_headers):
    _create_employee(client, auth_headers, email="list1@legacy.com")
    _create_employee(client, auth_headers, email="list2@legacy.com")

    resp = client.get("/api/employees", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    # At least 2 employees + the admin user
    assert data["total"] >= 2


def test_list_employees_search(client, auth_headers):
    _create_employee(
        client, auth_headers, full_name="Logan Reed", email="logan@legacy.com"
    )
    _create_employee(
        client, auth_headers, full_name="Bri Martinez", email="bri@legacy.com"
    )

    resp = client.get(
        "/api/employees", params={"search": "Logan"}, headers=auth_headers
    )
    data = resp.json()
    assert any(e["full_name"] == "Logan Reed" for e in data["items"])
    assert not any(e["full_name"] == "Bri Martinez" for e in data["items"])


def test_list_employees_filter_role(client, auth_headers):
    _create_employee(
        client, auth_headers, email="crew1@legacy.com", role="crew"
    )
    _create_employee(
        client, auth_headers, email="staff1@legacy.com", role="staff"
    )

    resp = client.get(
        "/api/employees", params={"role": "crew"}, headers=auth_headers
    )
    data = resp.json()
    assert all(e["role"] == "crew" for e in data["items"])


def test_list_employees_filter_active(client, auth_headers):
    resp = _create_employee(client, auth_headers, email="todeactivate@legacy.com")
    emp_id = resp.json()["id"]
    client.delete(f"/api/employees/{emp_id}", headers=auth_headers)

    resp = client.get(
        "/api/employees", params={"is_active": True}, headers=auth_headers
    )
    data = resp.json()
    assert all(e["is_active"] is True for e in data["items"])


def test_get_employee(client, auth_headers):
    resp = _create_employee(client, auth_headers)
    emp_id = resp.json()["id"]

    resp = client.get(f"/api/employees/{emp_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == emp_id


def test_get_employee_not_found(client, auth_headers):
    resp = client.get("/api/employees/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_employee(client, auth_headers):
    resp = _create_employee(client, auth_headers)
    emp_id = resp.json()["id"]

    resp = client.put(
        f"/api/employees/{emp_id}",
        json={"full_name": "Updated Name", "color": "#EF4444"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Updated Name"
    assert data["color"] == "#EF4444"


def test_update_employee_duplicate_email(client, auth_headers):
    _create_employee(client, auth_headers, email="first@legacy.com")
    resp = _create_employee(client, auth_headers, email="second@legacy.com")
    emp_id = resp.json()["id"]

    resp = client.put(
        f"/api/employees/{emp_id}",
        json={"email": "first@legacy.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_deactivate_employee(client, auth_headers):
    resp = _create_employee(client, auth_headers, email="deactivate@legacy.com")
    emp_id = resp.json()["id"]

    resp = client.delete(f"/api/employees/{emp_id}", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/employees/{emp_id}", headers=auth_headers)
    assert resp.json()["is_active"] is False


# --- Auth enforcement ---


def test_employees_require_auth(client):
    resp = client.get("/api/employees")
    assert resp.status_code == 401


def test_create_employee_requires_admin(client, auth_headers):
    # Create a staff user
    _create_employee(client, auth_headers, email="staff@legacy.com")
    # Login as staff
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "staff@legacy.com", "password": "password123"},
    )
    staff_token = login_resp.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Staff cannot create employees
    resp = _create_employee(client, staff_headers, email="new@legacy.com")
    assert resp.status_code == 403


def test_staff_can_list_employees(client, auth_headers):
    _create_employee(client, auth_headers, email="stafflist@legacy.com")
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "stafflist@legacy.com", "password": "password123"},
    )
    staff_token = login_resp.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    resp = client.get("/api/employees", headers=staff_headers)
    assert resp.status_code == 200
