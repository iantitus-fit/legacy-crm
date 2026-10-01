"""Tests for appointments CRUD."""
from datetime import date, timedelta


def _create_contact(client, auth_headers, name="Test Contact"):
    resp = client.post("/api/contacts", json={"name": name}, headers=auth_headers)
    return resp.json()


def _get_current_user(client, auth_headers):
    resp = client.get("/api/auth/me", headers=auth_headers)
    return resp.json()


def _create_appointment(client, auth_headers, **overrides):
    user = _get_current_user(client, auth_headers)
    data = {
        "title": "Test Appointment",
        "assigned_to_user_id": user["id"],
        "appointment_date": str(date.today() + timedelta(days=1)),
        "appointment_type": "other",
        **overrides,
    }
    resp = client.post("/api/appointments", json=data, headers=auth_headers)
    return resp.json()


def test_create_appointment(client, auth_headers, seeded_stages):
    user = _get_current_user(client, auth_headers)
    contact = _create_contact(client, auth_headers, "Dale Legacy")

    resp = client.post(
        "/api/appointments",
        json={
            "title": "Roof Inspection",
            "assigned_to_user_id": user["id"],
            "appointment_date": str(date.today() + timedelta(days=1)),
            "contact_id": contact["id"],
            "appointment_time": "09:00:00",
            "duration_minutes": 60,
            "location": "123 Main St",
            "appointment_type": "inspection",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Roof Inspection"
    assert data["contact_name"] == "Dale Legacy"
    assert data["assigned_to_name"] == "Admin User"
    assert data["created_by_name"] == "Admin User"
    assert data["duration_minutes"] == 60
    assert data["appointment_type"] == "inspection"
    assert data["location"] == "123 Main St"


def test_create_appointment_minimal(client, auth_headers, seeded_stages):
    user = _get_current_user(client, auth_headers)
    resp = client.post(
        "/api/appointments",
        json={
            "title": "Quick meeting",
            "assigned_to_user_id": user["id"],
            "appointment_date": str(date.today()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Quick meeting"
    assert data["duration_minutes"] == 60  # default
    assert data["appointment_type"] == "other"  # default


def test_create_appointment_invalid_contact(client, auth_headers, seeded_stages):
    user = _get_current_user(client, auth_headers)
    resp = client.post(
        "/api/appointments",
        json={
            "title": "Bad contact",
            "assigned_to_user_id": user["id"],
            "appointment_date": str(date.today()),
            "contact_id": 9999,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Contact not found" in resp.json()["detail"]


def test_create_appointment_invalid_user(client, auth_headers, seeded_stages):
    resp = client.post(
        "/api/appointments",
        json={
            "title": "Bad user",
            "assigned_to_user_id": 9999,
            "appointment_date": str(date.today()),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Assigned user not found" in resp.json()["detail"]


def test_list_appointments(client, auth_headers, seeded_stages):
    _create_appointment(client, auth_headers, title="Appt 1")
    _create_appointment(client, auth_headers, title="Appt 2")

    resp = client.get("/api/appointments", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_appointments_filter_by_user(client, auth_headers, seeded_stages):
    user = _get_current_user(client, auth_headers)
    _create_appointment(client, auth_headers, title="Appt 1")

    resp = client.get(
        f"/api/appointments?assigned_to_user_id={user['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = client.get(
        "/api/appointments?assigned_to_user_id=9999",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 0


def test_list_appointments_filter_by_type(client, auth_headers, seeded_stages):
    _create_appointment(client, auth_headers, title="A", appointment_type="quote")
    _create_appointment(client, auth_headers, title="B", appointment_type="inspection")

    resp = client.get(
        "/api/appointments?appointment_type=quote",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["appointment_type"] == "quote"


def test_list_appointments_filter_by_date_range(client, auth_headers, seeded_stages):
    tomorrow = date.today() + timedelta(days=1)
    next_week = date.today() + timedelta(days=7)

    _create_appointment(
        client, auth_headers, title="Soon",
        appointment_date=str(tomorrow),
    )
    _create_appointment(
        client, auth_headers, title="Later",
        appointment_date=str(next_week),
    )

    resp = client.get(
        f"/api/appointments?start_date={tomorrow}&end_date={tomorrow}",
        headers=auth_headers,
    )
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Soon"


def test_get_appointment(client, auth_headers, seeded_stages):
    appt = _create_appointment(client, auth_headers, title="Detail Test")

    resp = client.get(f"/api/appointments/{appt['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["title"] == "Detail Test"
    assert resp.json()["assigned_to_name"] is not None


def test_get_appointment_not_found(client, auth_headers, seeded_stages):
    resp = client.get("/api/appointments/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_update_appointment(client, auth_headers, seeded_stages):
    appt = _create_appointment(client, auth_headers, title="Old Title")

    resp = client.put(
        f"/api/appointments/{appt['id']}",
        json={"title": "New Title", "duration_minutes": 90},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "New Title"
    assert data["duration_minutes"] == 90


def test_update_appointment_not_found(client, auth_headers, seeded_stages):
    resp = client.put(
        "/api/appointments/9999",
        json={"title": "No"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_delete_appointment(client, auth_headers, seeded_stages):
    appt = _create_appointment(client, auth_headers, title="Delete Me")

    resp = client.delete(f"/api/appointments/{appt['id']}", headers=auth_headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/appointments/{appt['id']}", headers=auth_headers)
    assert resp.status_code == 404


def test_delete_appointment_not_found(client, auth_headers, seeded_stages):
    resp = client.delete("/api/appointments/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_appointments_require_auth(client):
    resp = client.get("/api/appointments")
    assert resp.status_code == 401
