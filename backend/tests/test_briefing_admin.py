"""Tests for the briefing_admin router."""

from unittest.mock import patch


def test_preview_requires_admin(client, seeded_stages):
    resp = client.get("/api/admin/briefing/preview?recipient=dale")
    assert resp.status_code == 401  # no auth


def test_preview_returns_html(client, auth_headers, seeded_stages, monkeypatch):
    from app.routers import briefing_admin

    fake_preview = {
        "sent_to": [],
        "skipped": [],
        "dry_run": True,
        "previews": [
            {"recipient": "dale", "to": "dale@test.com",
             "subject": "Legacy briefing · Thu May 15",
             "html": "<html><body>Hi Dale</body></html>"},
        ],
    }
    monkeypatch.setattr(
        briefing_admin, "send_morning_briefing",
        lambda **kwargs: fake_preview,
    )
    resp = client.get(
        "/api/admin/briefing/preview?recipient=dale",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "Hi Dale" in resp.text


def test_preview_rejects_unknown_recipient(client, auth_headers, seeded_stages):
    resp = client.get(
        "/api/admin/briefing/preview?recipient=bob",
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_send_dry_run_returns_preview(client, auth_headers, seeded_stages, monkeypatch):
    from app.routers import briefing_admin

    fake_result = {
        "sent_to": [],
        "skipped": [],
        "dry_run": True,
        "previews": [
            {"recipient": "dale", "to": "dale@test.com",
             "subject": "S", "html": "<html>X</html>"},
        ],
    }
    monkeypatch.setattr(
        briefing_admin, "send_morning_briefing",
        lambda **kwargs: fake_result,
    )
    resp = client.post(
        "/api/admin/briefing/send",
        headers=auth_headers,
        json={"recipient": "dale", "dry_run": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sent_to"] == []
    assert body["previews"][0]["recipient"] == "dale"


def test_send_real_passes_dry_run_false(client, auth_headers, seeded_stages, monkeypatch):
    from app.routers import briefing_admin

    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return {"sent_to": ["k@x"], "skipped": [], "previews": [], "dry_run": False}

    monkeypatch.setattr(briefing_admin, "send_morning_briefing", fake_send)
    resp = client.post(
        "/api/admin/briefing/send",
        headers=auth_headers,
        json={"recipient": "dale", "dry_run": False},
    )
    assert resp.status_code == 200
    assert captured.get("dry_run") is False
    assert captured.get("recipient") == "dale"


def test_send_requires_admin(client, seeded_stages):
    resp = client.post(
        "/api/admin/briefing/send",
        json={"recipient": "dale", "dry_run": True},
    )
    assert resp.status_code == 401
