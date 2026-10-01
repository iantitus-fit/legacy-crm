"""Sprint 16b — AI architecture tests.

All tests run with LLM_PROVIDER=none (no real LLM calls). When tests need
deterministic content, they install a MockProvider via the
ai_provider.set_provider() override and reset it afterwards.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.config import settings
from app.models.ai_action import AIAction
from app.services import ai_events, ai_provider
from app.services.ai_prompts import PROMPTS, render_prompt
from app.services.ai_provider import (
    AIResponse,
    ClaudeProvider,
    MockProvider,
    NoneProvider,
    OllamaProvider,
    get_provider,
    set_provider,
)


# ---------- Fixtures ----------


@pytest.fixture(autouse=True)
def _force_none_provider():
    """Tests must never make real LLM calls. Default to NoneProvider unless
    a test explicitly installs a MockProvider via use_mock_provider()."""
    original = settings.llm_provider
    settings.llm_provider = "none"
    set_provider(None)
    yield
    settings.llm_provider = original
    set_provider(None)


@pytest.fixture()
def use_mock_provider():
    """Helper to install a MockProvider for content-checking tests."""
    installed = []

    def _install(canned: str = None, model: str = "mock-1"):
        provider = MockProvider(model=model, canned=canned)
        installed.append(provider)
        set_provider(provider)
        return provider

    yield _install
    set_provider(None)


def _create_contact(client, auth_headers, **overrides):
    payload = {"name": "Lead Person", **overrides}
    resp = client.post("/api/contacts", headers=auth_headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_lead_pipeline_contact(client, auth_headers, leads_pipeline):
    stages = client.get(
        "/api/pipeline-stages",
        headers=auth_headers,
        params={"pipeline_id": leads_pipeline.id},
    ).json()["items"]
    return _create_contact(
        client,
        auth_headers,
        name="Hot Lead",
        pipeline_id=leads_pipeline.id,
        stage_id=stages[0]["id"],
        lead_source="Angi",
    )


def _create_job(client, auth_headers, seeded_stages, contact_id):
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    resp = client.post(
        "/api/jobs",
        headers=auth_headers,
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact_id,
            "stage_id": stages[0]["id"],
            "work_type": "retail",
        },
    )
    return resp.json()


def _create_estimate_with_lines(client, auth_headers, job_id):
    est = client.post(
        "/api/estimates",
        headers=auth_headers,
        json={"job_id": job_id, "name": "Roof replacement"},
    ).json()
    client.post(
        f"/api/estimates/{est['id']}/line-items",
        headers=auth_headers,
        json={
            "description": "Tear-off + new shingles",
            "qty": 1,
            "unit_price": 12000,
        },
    )
    return est


# ---------- Provider abstraction ----------


def test_provider_claude_init():
    p = ClaudeProvider(api_key="sk-test", model="claude-sonnet-4-20250514", timeout=10.0)
    assert p.name == "claude"
    assert p.api_key == "sk-test"
    assert p.model == "claude-sonnet-4-20250514"


def test_provider_ollama_init():
    p = OllamaProvider(
        base_url="http://localhost:11434/", model="qwen3:8b", timeout=5.0
    )
    assert p.name == "ollama"
    assert p.base_url == "http://localhost:11434"
    assert p.model == "qwen3:8b"


def test_provider_none_returns_empty():
    p = NoneProvider()
    resp = p.generate(system_prompt="x", user_prompt="y")
    assert resp.content == ""
    assert resp.success is True
    assert resp.provider == "none"
    assert resp.tokens_used == 0


def test_provider_selection_from_env():
    settings.llm_provider = "none"
    assert isinstance(get_provider(), NoneProvider)
    settings.llm_provider = "ollama"
    assert isinstance(get_provider(), OllamaProvider)
    settings.llm_provider = "claude"
    settings.claude_api_key = "sk-test"
    assert isinstance(get_provider(), ClaudeProvider)
    settings.llm_provider = "claude"
    settings.claude_api_key = None  # missing key falls back to none
    assert isinstance(get_provider(), NoneProvider)
    settings.llm_provider = "mock"
    assert isinstance(get_provider(), MockProvider)


def test_provider_graceful_failure():
    """Ollama provider returns success=False when the HTTP call fails."""
    p = OllamaProvider(
        base_url="http://localhost:1",  # nothing is listening here
        model="qwen3:8b",
        timeout=0.5,
    )
    resp = p.generate(system_prompt="x", user_prompt="y")
    assert resp.success is False
    assert resp.error
    assert resp.content == ""


def test_provider_timeout():
    """Timeouts surface as error responses, not exceptions."""
    import httpx

    p = OllamaProvider(base_url="http://localhost:1", model="x", timeout=0.1)
    with patch.object(httpx, "post", side_effect=httpx.TimeoutException("timed out")):
        resp = p.generate(system_prompt="x", user_prompt="y")
    assert resp.success is False
    assert "timed out" in resp.error.lower()


def test_ai_disabled_skips(client, auth_headers, seeded_stages):
    settings.ai_enabled = False
    try:
        contact = _create_contact(client, auth_headers, name="Lead Bob")
        resp = client.post(
            "/api/ai/generate",
            headers=auth_headers,
            json={
                "event_type": "pre_visit_summary",
                "contact_id": contact["id"],
            },
        )
        assert resp.status_code == 503
    finally:
        settings.ai_enabled = True


# ---------- /api/ai/generate ----------


def test_generate_endpoint_auth(client):
    resp = client.post("/api/ai/generate", json={"event_type": "pre_visit_summary"})
    assert resp.status_code == 401


def test_generate_pre_visit_summary(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="John lives at 123 Main St. Roof inspection.")
    contact = _create_contact(client, auth_headers, name="John Smith")
    resp = client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={
            "event_type": "pre_visit_summary",
            "contact_id": contact["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["provider"] == "mock"
    assert "John lives" in data["output"]


def test_generate_scope_of_work(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="Tear off the existing roof and install new shingles.")
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, seeded_stages, contact["id"])
    estimate = _create_estimate_with_lines(client, auth_headers, job["id"])
    resp = client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={
            "event_type": "estimate_created",
            "estimate_id": estimate["id"],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["output"].startswith("Tear off")


def test_generate_follow_up_draft(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="Hi John, just checking in on your roof.")
    contact = _create_contact(client, auth_headers, name="John Smith")
    resp = client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={
            "event_type": "follow_up_overdue",
            "contact_id": contact["id"],
            "extra": {"days_since_activity": 5, "last_activity_date": "2026-04-23"},
        },
    )
    assert resp.status_code == 200
    assert "John" in resp.json()["output"]


def test_generate_invalid_event_type(client, auth_headers):
    resp = client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={"event_type": "bogus_event"},
    )
    assert resp.status_code == 400


def test_generate_stores_action(
    client, auth_headers, seeded_stages, use_mock_provider, db_session
):
    use_mock_provider(canned="briefing text")
    contact = _create_contact(client, auth_headers)
    resp = client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={"event_type": "pre_visit_summary", "contact_id": contact["id"]},
    )
    action_id = resp.json()["id"]
    record = db_session.query(AIAction).filter(AIAction.id == action_id).first()
    assert record is not None
    assert record.system_prompt
    assert record.user_prompt
    assert record.output == "briefing text"
    assert record.contact_id == contact["id"]


def test_generate_with_none_provider_records_empty(
    client, auth_headers, seeded_stages, db_session
):
    """LLM_PROVIDER=none still records the action with empty output and
    status='completed' so the audit trail captures the request."""
    contact = _create_contact(client, auth_headers)
    resp = client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={"event_type": "pre_visit_summary", "contact_id": contact["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "none"
    assert data["output"] == ""
    assert data["status"] == "completed"


# ---------- Use / dismiss ----------


def test_use_action(client, auth_headers, seeded_stages, use_mock_provider):
    use_mock_provider(canned="text")
    contact = _create_contact(client, auth_headers)
    gen = client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={"event_type": "pre_visit_summary", "contact_id": contact["id"]},
    ).json()
    resp = client.post(
        f"/api/ai/actions/{gen['id']}/use", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "used"
    assert body["used_at"] is not None


def test_dismiss_action(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="text")
    contact = _create_contact(client, auth_headers)
    gen = client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={"event_type": "pre_visit_summary", "contact_id": contact["id"]},
    ).json()
    resp = client.post(
        f"/api/ai/actions/{gen['id']}/dismiss", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "dismissed"


def test_use_action_not_found(client, auth_headers):
    resp = client.post(
        "/api/ai/actions/does-not-exist/use", headers=auth_headers
    )
    assert resp.status_code == 404


# ---------- Listing / stats ----------


def test_list_actions_by_contact(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="x")
    a = _create_contact(client, auth_headers, name="A")
    b = _create_contact(client, auth_headers, name="B")
    for c in (a, b, a):
        client.post(
            "/api/ai/generate",
            headers=auth_headers,
            json={"event_type": "pre_visit_summary", "contact_id": c["id"]},
        )
    resp = client.get(
        "/api/ai/actions",
        headers=auth_headers,
        params={"contact_id": a["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert all(item["contact_id"] == a["id"] for item in data["items"])


def test_list_actions_by_event(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="x")
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, seeded_stages, contact["id"])
    est = _create_estimate_with_lines(client, auth_headers, job["id"])
    client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={"event_type": "pre_visit_summary", "contact_id": contact["id"]},
    )
    client.post(
        "/api/ai/generate",
        headers=auth_headers,
        json={"event_type": "estimate_created", "estimate_id": est["id"]},
    )
    resp = client.get(
        "/api/ai/actions",
        headers=auth_headers,
        params={"event_type": "estimate_created"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["event_type"] == "estimate_created"


def test_stats_endpoint(
    client, auth_headers, seeded_stages, use_mock_provider, db_session
):
    use_mock_provider(canned="some output here")
    contact = _create_contact(client, auth_headers)
    for _ in range(3):
        client.post(
            "/api/ai/generate",
            headers=auth_headers,
            json={"event_type": "pre_visit_summary", "contact_id": contact["id"]},
        )
    resp = client.get("/api/ai/stats", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_actions"] == 3
    assert body["completed"] == 3
    assert body["total_tokens"] >= 3  # MockProvider counts tokens by word
    assert body["by_event_type"].get("pre_visit_summary") == 3
    assert body["by_provider"].get("mock") == 3


def test_stats_unauthorized(client):
    resp = client.get("/api/ai/stats")
    assert resp.status_code == 401


# ---------- Prompts ----------


def test_prompt_template_rendering():
    system, user = render_prompt(
        "lead_created",
        {
            "company_name": "Legacy",
            "company_phone": "(765) 555-0000",
            "contact_name": "John",
            "lead_source": "Angi",
            "contact_notes": "needs new roof",
            "service_interest": "roof",
        },
    )
    assert "Legacy" in system
    assert "(765) 555-0000" in user
    assert "John" in user
    assert "Angi" in user


def test_prompt_template_missing_context_safe():
    """Missing keys should not raise — they render as 'unknown'."""
    system, user = render_prompt("lead_created", {"contact_name": "X"})
    assert "unknown" in system or "unknown" in user


def test_all_prompt_templates_exist():
    expected = {
        "lead_created",
        "follow_up_overdue",
        "estimate_approved",
        "job_completed",
        "estimate_created",
        "pre_visit_summary",
    }
    assert expected.issubset(PROMPTS.keys())


# ---------- Hooks ----------


def test_lead_created_hook(
    client, auth_headers, seeded_stages, leads_pipeline, use_mock_provider, db_session
):
    use_mock_provider(canned="Welcome message from Legacy.")
    contact = _create_lead_pipeline_contact(client, auth_headers, leads_pipeline)
    actions = (
        db_session.query(AIAction)
        .filter(
            AIAction.event_type == "lead_created",
            AIAction.contact_id == contact["id"],
        )
        .all()
    )
    assert len(actions) == 1
    assert actions[0].output == "Welcome message from Legacy."


def test_lead_created_hook_skips_non_leads_pipeline(
    client, auth_headers, seeded_stages, sales_pipeline, db_session
):
    """Contacts placed in Sales/Jobs pipelines do NOT fire lead_created."""
    stages = client.get(
        "/api/pipeline-stages",
        headers=auth_headers,
        params={"pipeline_id": sales_pipeline.id},
    ).json()["items"]
    _create_contact(
        client,
        auth_headers,
        name="Sales Person",
        pipeline_id=sales_pipeline.id,
        stage_id=stages[0]["id"],
    )
    assert (
        db_session.query(AIAction)
        .filter(AIAction.event_type == "lead_created")
        .count()
        == 0
    )


def test_estimate_approved_hook(
    client, auth_headers, seeded_stages, use_mock_provider, db_session
):
    from uuid import uuid4
    from app.models.estimate import Estimate
    from app.models.estimate_token import EstimateToken

    use_mock_provider(canned="Crew briefing: address xyz, total $12k.")
    contact = _create_contact(client, auth_headers, name="Owner")
    job = _create_job(client, auth_headers, seeded_stages, contact["id"])
    est = _create_estimate_with_lines(client, auth_headers, job["id"])

    token = uuid4().hex
    db_session.add(EstimateToken(estimate_id=est["id"], token=token))
    estimate = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    estimate.status = "sent"
    db_session.commit()

    resp = client.post(
        f"/api/portal/{token}/approve",
        json={
            "signer_name": "Customer",
            "signature_data": "data:image/png;base64,xxx",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 200
    actions = (
        db_session.query(AIAction)
        .filter(AIAction.event_type == "estimate_approved")
        .all()
    )
    assert len(actions) == 1
    assert actions[0].estimate_id == est["id"]


def test_job_completed_hook(
    client, auth_headers, seeded_stages, use_mock_provider, db_session
):
    """Status transition to 'complete' fires job_completed."""
    from app.models.estimate import Estimate
    from app.models.estimate_signature import EstimateSignature
    from app.models.estimate_status_history import EstimateStatusHistory

    use_mock_provider(canned="Thanks for choosing Legacy.")
    contact = _create_contact(client, auth_headers, name="Done Customer")
    job = _create_job(client, auth_headers, seeded_stages, contact["id"])
    est = _create_estimate_with_lines(client, auth_headers, job["id"])

    # Move directly to approved via DB so the update_estimate path can
    # transition approved → in_progress → complete without portal token noise.
    estimate = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    estimate.status = "approved"
    db_session.commit()

    client.put(
        f"/api/estimates/{est['id']}",
        headers=auth_headers,
        json={"status": "in_progress"},
    )
    resp = client.put(
        f"/api/estimates/{est['id']}",
        headers=auth_headers,
        json={"status": "complete"},
    )
    assert resp.status_code == 200
    actions = (
        db_session.query(AIAction)
        .filter(
            AIAction.event_type == "job_completed",
            AIAction.estimate_id == est["id"],
        )
        .all()
    )
    assert len(actions) == 1


def test_hooks_swallow_provider_failures(
    client, auth_headers, seeded_stages, leads_pipeline, db_session
):
    """A provider failure must not break the user-facing operation."""

    class FailingProvider(NoneProvider):
        name = "failing"
        model = "x"

        def generate(self, **kwargs):
            return AIResponse(
                content="",
                provider="failing",
                model="x",
                success=False,
                error="boom",
            )

    set_provider(FailingProvider())
    try:
        contact = _create_lead_pipeline_contact(
            client, auth_headers, leads_pipeline
        )
        # Contact create still succeeded
        assert contact["id"]
        # And we recorded the failure
        actions = (
            db_session.query(AIAction)
            .filter(AIAction.event_type == "lead_created")
            .all()
        )
        assert len(actions) == 1
        assert actions[0].status == "failed"
        assert "boom" in (actions[0].error or "")
    finally:
        set_provider(None)
