"""Tests for calendar endpoints."""
from datetime import date, timedelta

from app.models.crew import Crew
from app.models.estimate import Estimate
from app.models.job import Job
from app.models.appointment import Appointment
from app.models.pipeline_stage import PipelineStage


def _create_contact(client, auth_headers, name="Calendar Contact"):
    resp = client.post("/api/contacts", json={"name": name}, headers=auth_headers)
    return resp.json()


def _get_pipeline_and_stages(client, auth_headers, slug="jobs"):
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == slug)
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    return pipeline, stages


def _get_current_user(client, auth_headers):
    return client.get("/api/auth/me", headers=auth_headers).json()


def _create_crew(db_session, name="Test Crew", color="#3B82F6"):
    crew = Crew(name=name, color=color)
    db_session.add(crew)
    db_session.commit()
    db_session.refresh(crew)
    return crew


def _create_scheduled_estimate(
    client, auth_headers, db_session, sched_date, crew_id=None, status="approved"
):
    """Sprint 15d: Create an approved estimate with scheduled_start set.

    The calendar now reads from approved estimates (a "job" in the new
    model). Creates a contact + backing job + estimate, then directly
    writes status/scheduled_start/crew_id on the estimate in the DB so
    the test doesn't depend on the internal-approve flow.
    """
    contact = _create_contact(client, auth_headers)
    pipeline, stages = _get_pipeline_and_stages(client, auth_headers, "jobs")
    job_resp = client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact["id"],
            "stage_id": stages[0]["id"],
            "work_type": "retail",
            "property_address": "123 Test St",
        },
        headers=auth_headers,
    )
    job_id = job_resp.json()["id"]

    est_resp = client.post(
        "/api/estimates",
        json={"job_id": job_id, "name": "Scheduled Work"},
        headers=auth_headers,
    )
    est = est_resp.json()

    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = status
    est_obj.scheduled_start = sched_date
    if crew_id is not None:
        est_obj.crew_id = crew_id
    db_session.commit()
    db_session.refresh(est_obj)
    return est_obj


def _create_appointment(client, auth_headers, appt_date, **overrides):
    user = _get_current_user(client, auth_headers)
    data = {
        "title": "Test Appointment",
        "assigned_to_user_id": user["id"],
        "appointment_date": str(appt_date),
        **overrides,
    }
    return client.post("/api/appointments", json=data, headers=auth_headers).json()


# ---- Calendar Jobs Tests ----

def test_calendar_jobs_date_range(client, auth_headers, db_session, seeded_stages):
    today = date.today()
    crew = _create_crew(db_session)

    _create_scheduled_estimate(client, auth_headers, db_session, today, crew.id)
    _create_scheduled_estimate(
        client, auth_headers, db_session, today + timedelta(days=10), crew.id
    )

    resp = client.get(
        f"/api/calendar/jobs?start_date={today}&end_date={today + timedelta(days=5)}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["crew_name"] == "Test Crew"
    assert items[0]["crew_color"] == "#3B82F6"


def test_calendar_jobs_crew_filter(client, auth_headers, db_session, seeded_stages):
    today = date.today()
    crew1 = _create_crew(db_session, "Crew A", "#FF0000")
    crew2 = _create_crew(db_session, "Crew B", "#00FF00")

    _create_scheduled_estimate(client, auth_headers, db_session, today, crew1.id)
    _create_scheduled_estimate(client, auth_headers, db_session, today, crew2.id)

    resp = client.get(
        f"/api/calendar/jobs?start_date={today}&end_date={today}&crew_id={crew1.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["crew_name"] == "Crew A"


def test_calendar_jobs_only_job_phase_estimates(
    client, auth_headers, db_session, seeded_stages
):
    """Sprint 15d: only estimates in job-phase status appear on the calendar."""
    today = date.today()
    crew = _create_crew(db_session, "Active Crew")

    # Draft estimate with scheduled_start → should NOT appear
    _create_scheduled_estimate(
        client, auth_headers, db_session, today, crew.id, status="draft"
    )
    # Approved estimate → should appear
    _create_scheduled_estimate(
        client, auth_headers, db_session, today, crew.id, status="approved"
    )

    resp = client.get(
        f"/api/calendar/jobs?start_date={today}&end_date={today}",
        headers=auth_headers,
    )
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["stage_name"].lower() == "approved"


# ---- Calendar Appointments Tests ----

def test_calendar_appointments_date_range(client, auth_headers, seeded_stages):
    today = date.today()
    _create_appointment(client, auth_headers, today, title="Today Appt")
    _create_appointment(client, auth_headers, today + timedelta(days=10), title="Future Appt")

    resp = client.get(
        f"/api/calendar/appointments?start_date={today}&end_date={today + timedelta(days=5)}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Today Appt"


def test_calendar_appointments_employee_filter(client, auth_headers, seeded_stages):
    user = _get_current_user(client, auth_headers)
    today = date.today()
    _create_appointment(client, auth_headers, today, title="Mine")

    resp = client.get(
        f"/api/calendar/appointments?start_date={today}&end_date={today}&assigned_to_user_id={user['id']}",
        headers=auth_headers,
    )
    assert resp.json()["items"][0]["title"] == "Mine"

    resp = client.get(
        f"/api/calendar/appointments?start_date={today}&end_date={today}&assigned_to_user_id=9999",
        headers=auth_headers,
    )
    assert len(resp.json()["items"]) == 0


# ---- Upcoming Tests ----

def test_calendar_upcoming_merged_sorted(client, auth_headers, db_session, seeded_stages):
    today = date.today()
    crew = _create_crew(db_session, "Upcoming Crew")
    _create_scheduled_estimate(
        client, auth_headers, db_session, today + timedelta(days=3), crew.id
    )
    _create_appointment(client, auth_headers, today + timedelta(days=1), title="Earlier Appt")

    resp = client.get("/api/calendar/upcoming?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    # Appointment is sooner, should be first
    assert items[0]["item_type"] == "appointment"
    assert items[1]["item_type"] == "job"
    # Job link now routes to the estimate detail page
    assert items[1]["link"].startswith("/estimates/")


def test_calendar_upcoming_limit(client, auth_headers, db_session, seeded_stages):
    today = date.today()
    for i in range(5):
        _create_appointment(client, auth_headers, today + timedelta(days=i), title=f"Appt {i}")

    resp = client.get("/api/calendar/upcoming?limit=3", headers=auth_headers)
    assert len(resp.json()["items"]) == 3


def test_calendar_requires_auth(client):
    resp = client.get("/api/calendar/jobs")
    assert resp.status_code == 401

    resp = client.get("/api/calendar/appointments")
    assert resp.status_code == 401

    resp = client.get("/api/calendar/upcoming")
    assert resp.status_code == 401
