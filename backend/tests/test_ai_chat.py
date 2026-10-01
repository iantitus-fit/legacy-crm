"""Sprint 16c — Conversational AI panel + morning briefing tests."""
from __future__ import annotations

import pytest

from app.config import settings
from app.models.ai_conversation import AIConversation, AIMessage
from app.services.ai_provider import MockProvider, set_provider


@pytest.fixture(autouse=True)
def _force_none_provider():
    """Tests must never make real LLM calls."""
    original = settings.llm_provider
    settings.llm_provider = "none"
    set_provider(None)
    yield
    settings.llm_provider = original
    set_provider(None)


@pytest.fixture()
def use_mock_provider():
    def _install(canned: str = None, model: str = "mock-1"):
        provider = MockProvider(model=model, canned=canned)
        set_provider(provider)
        return provider

    yield _install
    set_provider(None)


def test_ai_conversation_model_creates(db_session, auth_headers, client):
    """The AIConversation/AIMessage SQLAlchemy models persist and relate."""
    from app.models.user import User
    user = db_session.query(User).first()
    assert user is not None

    convo = AIConversation(
        id="conv-1",
        user_id=user.id,
        entity_type="contact",
        entity_id=42,
        title="Discussion of contact 42",
    )
    db_session.add(convo)
    db_session.commit()
    db_session.refresh(convo)

    msg = AIMessage(
        id="msg-1",
        conversation_id=convo.id,
        role="user",
        content="hello there",
    )
    db_session.add(msg)
    db_session.commit()

    assert convo.id == "conv-1"
    assert convo.user_id == user.id
    assert convo.entity_type == "contact"
    assert convo.entity_id == 42
    assert msg.conversation_id == "conv-1"
    assert msg.role == "user"
    db_session.refresh(convo)
    assert len(convo.messages) == 1
    assert convo.messages[0].content == "hello there"


def test_schemas_importable():
    from app.schemas.ai_chat import (
        ChatRequest,
        ChatResponse,
        ConversationListItem,
        ConversationListResponse,
        MessageResponse,
        MessageListResponse,
        BriefingResponse,
        NarrativeBriefingResponse,
        ChipsResponse,
        Chip,
        VALID_ENTITY_TYPES,
    )
    req = ChatRequest(message="hi")
    assert req.message == "hi"
    assert req.conversation_id is None
    assert req.entity_type is None
    assert "contact" in VALID_ENTITY_TYPES
    assert "estimate" in VALID_ENTITY_TYPES


def test_new_prompt_templates_exist():
    from app.services.ai_prompts import PROMPTS
    assert "morning_briefing" in PROMPTS
    assert "conversation_system" in PROMPTS
    assert "conversation_with_entity" in PROMPTS
    # Existing templates must still be present (no removals)
    for old in (
        "lead_created", "follow_up_overdue", "estimate_approved",
        "job_completed", "estimate_created", "pre_visit_summary",
    ):
        assert old in PROMPTS


def test_morning_briefing_prompt_renders():
    from app.services.ai_prompts import render_prompt
    system, user = render_prompt(
        "morning_briefing",
        {
            "company_name": "Legacy",
            "user_first_name": "Dale",
            "today_date": "2026-05-04",
            "briefing_data_json": '{"overdue_followups": []}',
        },
    )
    assert "Legacy" in system
    assert "Dale" in user
    assert "2026-05-04" in user


def test_start_conversation_global_with_mock(
    db_session, seeded_stages, use_mock_provider
):
    """A global (no-entity) conversation persists user + assistant messages."""
    from app.models.user import User
    from app.services.ai_chat import start_conversation

    use_mock_provider(canned="Sure, here's what to focus on today.")
    user = db_session.query(User).first()

    convo, response_msg = start_conversation(
        db=db_session,
        user_id=user.id,
        initial_message="What needs attention today?",
    )
    assert convo.id
    assert convo.user_id == user.id
    assert convo.entity_type is None
    assert convo.entity_id is None
    assert convo.title  # auto-generated from initial message
    assert response_msg.role == "assistant"
    assert response_msg.content == "Sure, here's what to focus on today."

    db_session.refresh(convo)
    assert len(convo.messages) == 2
    assert convo.messages[0].role == "user"
    assert convo.messages[0].content == "What needs attention today?"
    assert convo.messages[1].role == "assistant"


def test_start_conversation_entity_scoped_uses_context(
    db_session, seeded_stages, use_mock_provider
):
    """An entity-scoped conversation includes the entity's context in the
    system prompt sent to the provider."""
    from app.models.user import User
    from app.models.contact import Contact
    from app.services.ai_chat import start_conversation
    from app.services.ai_provider import set_provider

    captured = {}

    class CapturingProvider:
        name = "capture"
        model = "x"

        def generate(self, system_prompt, user_prompt, **_):
            from app.services.ai_provider import AIResponse
            captured["system"] = system_prompt
            captured["user"] = user_prompt
            return AIResponse(
                content="response",
                provider="capture",
                model="x",
                success=True,
            )

    set_provider(CapturingProvider())
    try:
        user = db_session.query(User).first()
        contact = Contact(name="Jane Doe", phone="555-1212")
        db_session.add(contact)
        db_session.commit()
        db_session.refresh(contact)

        convo, _ = start_conversation(
            db=db_session,
            user_id=user.id,
            entity_type="contact",
            entity_id=contact.id,
            initial_message="Summarize this customer for me.",
        )
        assert convo.entity_type == "contact"
        assert convo.entity_id == contact.id
        assert "Jane Doe" in captured["system"]
        assert "Summarize this customer" in captured["user"]
    finally:
        set_provider(None)


def test_continue_conversation_includes_history(
    db_session, seeded_stages, use_mock_provider
):
    """continue_conversation feeds prior messages back so the LLM has context."""
    from app.models.user import User
    from app.services.ai_chat import start_conversation, continue_conversation
    from app.services.ai_provider import set_provider

    use_mock_provider(canned="First reply.")
    user = db_session.query(User).first()
    convo, _ = start_conversation(
        db=db_session, user_id=user.id, initial_message="First message."
    )

    captured = {}

    class CapturingProvider:
        name = "capture"
        model = "x"

        def generate(self, system_prompt, user_prompt, **_):
            from app.services.ai_provider import AIResponse
            captured["user"] = user_prompt
            return AIResponse(
                content="Second reply.", provider="capture", model="x"
            )

    set_provider(CapturingProvider())
    try:
        msg = continue_conversation(
            db=db_session,
            conversation_id=convo.id,
            user_message="Follow-up question.",
        )
        assert msg.content == "Second reply."
        assert "First message." in captured["user"]
        assert "First reply." in captured["user"]
        assert "Follow-up question." in captured["user"]

        db_session.refresh(convo)
        assert len(convo.messages) == 4
    finally:
        set_provider(None)


def test_chat_endpoint_auth(client):
    resp = client.post("/api/ai/chat", json={"message": "hi"})
    assert resp.status_code == 401


def test_chat_starts_new_conversation(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="Hello back.")
    resp = client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={"message": "Hello"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["conversation_id"]
    assert body["entity_type"] is None
    assert body["entity_id"] is None
    assert body["message"]["role"] == "assistant"
    assert body["message"]["content"] == "Hello back."


def test_chat_continues_existing_conversation(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="First.")
    first = client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={"message": "Q1"},
    ).json()
    use_mock_provider(canned="Second.")
    resp = client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={
            "conversation_id": first["conversation_id"],
            "message": "Q2",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == first["conversation_id"]
    assert body["message"]["content"] == "Second."


def test_chat_with_invalid_entity_type_400(client, auth_headers):
    resp = client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={"entity_type": "bogus", "entity_id": 1, "message": "hi"},
    )
    assert resp.status_code == 400


def test_chat_with_unknown_conversation_id_404(client, auth_headers):
    resp = client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={"conversation_id": "does-not-exist", "message": "hi"},
    )
    assert resp.status_code == 404


def test_chat_with_none_provider_returns_empty_content(
    client, auth_headers, seeded_stages
):
    """LLM_PROVIDER=none: chat still creates the conversation and persists
    the user message; assistant message has empty content."""
    resp = client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={"message": "hi"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]["content"] == ""


def test_list_conversations_empty(client, auth_headers):
    resp = client.get("/api/ai/conversations", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "total": 0}


def test_list_conversations_returns_user_conversations(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="ack")
    for prompt in ["First", "Second", "Third"]:
        client.post(
            "/api/ai/chat",
            headers=auth_headers,
            json={"message": prompt},
        )
    resp = client.get("/api/ai/conversations", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    titles = [c["title"] for c in body["items"]]
    assert any("First" in (t or "") for t in titles)
    assert all(c["message_count"] == 2 for c in body["items"])
    assert "Third" in (body["items"][0]["title"] or "")


def test_list_conversations_filtered_by_entity(
    client, auth_headers, seeded_stages, use_mock_provider, db_session
):
    """Listing with entity_type=contact&entity_id=N returns only those convs."""
    from app.models.contact import Contact

    use_mock_provider(canned="ok")
    contact = Contact(name="Filter Target")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={"message": "global one"},
    )
    client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={
            "entity_type": "contact",
            "entity_id": contact.id,
            "message": "scoped one",
        },
    )
    resp = client.get(
        "/api/ai/conversations",
        headers=auth_headers,
        params={"entity_type": "contact", "entity_id": contact.id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["entity_type"] == "contact"
    assert body["items"][0]["entity_id"] == contact.id


def test_get_messages_returns_paginated_history(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="r")
    first = client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={"message": "Q1"},
    ).json()
    client.post(
        "/api/ai/chat",
        headers=auth_headers,
        json={
            "conversation_id": first["conversation_id"],
            "message": "Q2",
        },
    )
    resp = client.get(
        f"/api/ai/conversations/{first['conversation_id']}/messages",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 4  # Q1 + r + Q2 + r
    assert [m["role"] for m in body["items"]] == [
        "user", "assistant", "user", "assistant",
    ]
    assert body["items"][0]["content"] == "Q1"


def test_get_messages_404_for_unknown_conversation(client, auth_headers):
    resp = client.get(
        "/api/ai/conversations/does-not-exist/messages", headers=auth_headers
    )
    assert resp.status_code == 404


def test_get_messages_404_for_other_users_conversation(
    client, auth_headers, seeded_stages, use_mock_provider, db_session
):
    """Listing messages for another user's conversation returns 404."""
    use_mock_provider(canned="r")
    convo = client.post(
        "/api/ai/chat", headers=auth_headers, json={"message": "mine"}
    ).json()

    # Register a second user and authenticate as them
    other_resp = client.post(
        "/api/auth/register",
        headers=auth_headers,
        json={
            "email": "other@legacy.com",
            "full_name": "Other User",
            "password": "pw12345678",
            "role": "staff",
        },
    )
    assert other_resp.status_code in (200, 201), other_resp.text
    login = client.post(
        "/api/auth/login",
        json={"email": "other@legacy.com", "password": "pw12345678"},
    )
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.get(
        f"/api/ai/conversations/{convo['conversation_id']}/messages",
        headers=other_headers,
    )
    assert resp.status_code == 404


def test_delete_conversation(
    client, auth_headers, seeded_stages, use_mock_provider, db_session
):
    use_mock_provider(canned="r")
    convo = client.post(
        "/api/ai/chat", headers=auth_headers, json={"message": "bye"}
    ).json()
    resp = client.delete(
        f"/api/ai/conversations/{convo['conversation_id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 204
    from app.models.ai_conversation import AIConversation, AIMessage
    assert (
        db_session.query(AIConversation)
        .filter(AIConversation.id == convo["conversation_id"])
        .first()
        is None
    )
    # Messages cascaded
    assert (
        db_session.query(AIMessage)
        .filter(AIMessage.conversation_id == convo["conversation_id"])
        .count()
        == 0
    )


def test_chips_global(client, auth_headers):
    resp = client.get("/api/ai/chips", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    labels = [c["label"] for c in items]
    assert "What needs attention today?" in labels
    assert "Overdue follow-ups" in labels
    assert "Unpaid invoices" in labels


def test_chips_for_contact(client, auth_headers, seeded_stages):
    resp = client.get(
        "/api/ai/chips",
        headers=auth_headers,
        params={"entity_type": "contact"},
    )
    assert resp.status_code == 200
    labels = [c["label"] for c in resp.json()["items"]]
    assert "Summarize this customer" in labels
    assert "Draft follow-up email" in labels


def test_chips_for_estimate(client, auth_headers, seeded_stages):
    resp = client.get(
        "/api/ai/chips",
        headers=auth_headers,
        params={"entity_type": "estimate"},
    )
    assert resp.status_code == 200
    labels = [c["label"] for c in resp.json()["items"]]
    assert "Explain this estimate" in labels


def test_chips_unknown_entity_returns_global(client, auth_headers):
    """Unknown entity_type falls back to global chip set, not 400."""
    resp = client.get(
        "/api/ai/chips",
        headers=auth_headers,
        params={"entity_type": "bogus"},
    )
    assert resp.status_code == 200
    labels = [c["label"] for c in resp.json()["items"]]
    assert "What needs attention today?" in labels


# ---------------------------------------------------------------------------
# Sprint 19d — automation context in the global system prompt
# ---------------------------------------------------------------------------
def test_build_automations_context_empty_db(db_session):
    from app.services.ai_chat import _build_automations_context

    out = _build_automations_context(db_session)
    assert "no automation sequences configured yet" in out


def test_build_automations_context_with_seeded_sequences(db_session):
    from app.models.automation import AutomationSequence
    from app.services.ai_chat import _build_automations_context

    db_session.add(
        AutomationSequence(
            name="Welcome Series",
            trigger_type="contact_created",
            trigger_config={},
            is_active=True,
        )
    )
    db_session.add(
        AutomationSequence(
            name="Paused One",
            trigger_type="estimate_sent",
            trigger_config={},
            is_active=False,
        )
    )
    db_session.commit()

    out = _build_automations_context(db_session)
    assert "Total sequences: 2" in out
    assert "1 active" in out
    assert "1 paused" in out
    assert "Welcome Series" in out
    assert "Paused One" in out


def test_global_system_prompt_includes_automations_block(db_session):
    """Use the existing CapturingProvider pattern to verify the system
    prompt contains the new automation context section."""
    from app.models.automation import AutomationSequence
    from app.models.user import User
    from app.services.ai_chat import start_conversation
    from app.services.ai_provider import set_provider

    db_session.add(
        AutomationSequence(
            name="Sample Drip",
            trigger_type="contact_created",
            trigger_config={},
            is_active=True,
        )
    )
    user = User(
        email="prompt@test.com",
        full_name="Prompter",
        password_hash="x",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    captured = {}

    class CapturingProvider:
        name = "capture"
        model = "x"

        def generate(self, system_prompt, user_prompt, **_):
            from app.services.ai_provider import AIResponse

            captured["system"] = system_prompt
            return AIResponse(
                content="ok", provider="capture", model="x", success=True,
            )

    set_provider(CapturingProvider())
    try:
        start_conversation(
            db=db_session,
            user_id=user.id,
            initial_message="How many contacts are in drip sequences?",
        )
    finally:
        set_provider(None)

    system_prompt = captured.get("system", "")
    assert "AUTOMATION SEQUENCES" in system_prompt
    assert "Sample Drip" in system_prompt


# ---------------------------------------------------------------------------
# Sprint 19d — get_briefing_context includes automation_summary
# ---------------------------------------------------------------------------
def test_get_briefing_context_includes_automation_summary(db_session):
    from app.models.user import User
    from app.services.ai_chat import get_briefing_context

    user = User(
        email="brief@test.com",
        full_name="Briefer",
        password_hash="x",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    ctx = get_briefing_context(db=db_session, user_id=user.id)
    assert "automation_summary" in ctx
    assert "active_enrollments" in ctx["automation_summary"]
    assert ctx["automation_summary"]["active_enrollments"] == 0
