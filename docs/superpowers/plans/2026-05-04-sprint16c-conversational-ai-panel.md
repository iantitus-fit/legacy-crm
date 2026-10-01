# Sprint 16c — Conversational AI Panel + Morning Briefing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace one-shot AI modals with a persistent conversational panel that scopes to contact/estimate or runs globally, plus add a structured morning-briefing data endpoint that external tools (HyperAgent) can consume.

**Architecture:**
- Backend: two new tables (`ai_conversations`, `ai_messages`), one new service (`ai_chat`) calling the existing `get_provider()` abstraction, one new router (`ai_chat`) extending the `/api/ai/*` namespace. Briefing endpoint queries existing CRM tables and returns plain-dict structured data — no LLM dependency.
- Frontend: a single React drawer (`AIPanel`) hung off a React context provider so panel state persists across navigation. The drawer renders in either global or entity-scoped mode driven by props passed when opening.
- All LLM calls flow through the existing `app.services.ai_provider.get_provider()` abstraction. No new providers, no new env vars.

**Tech Stack:** FastAPI + SQLAlchemy 2.x + Alembic on the backend. React 18 + Vite + Tailwind on the frontend. Adds `react-markdown` + `remark-gfm` to render assistant messages. Tests use the existing pytest TestClient + SQLite + MockProvider pattern from `tests/test_ai_actions.py`.

---

## File Structure

### Backend — create

- `backend/alembic/versions/0026_sprint16c_ai_conversations.py` — migration adding `ai_conversations` and `ai_messages`.
- `backend/app/models/ai_conversation.py` — SQLAlchemy models for both new tables (one file, two classes — they always change together).
- `backend/app/schemas/ai_chat.py` — Pydantic request/response models for chat, conversations, messages, briefing, chips.
- `backend/app/services/ai_chat.py` — `start_conversation()`, `continue_conversation()`, `get_briefing_context()`, plus internal helpers.
- `backend/app/routers/ai_chat.py` — endpoints under `/api/ai/*`: `chat`, `conversations`, `briefing`, `briefing/narrative`, `chips`.
- `backend/tests/test_ai_chat.py` — integration tests for chat + conversations + chips endpoints.
- `backend/tests/test_ai_briefing.py` — integration tests for the briefing data endpoint.

### Backend — modify

- `backend/app/main.py` — register `ai_chat_router`.
- `backend/app/models/__init__.py` — export `AIConversation` and `AIMessage`.
- `backend/app/services/ai_prompts.py` — add three templates: `morning_briefing`, `conversation_system`, `conversation_with_entity`. Do not remove existing keys.

### Frontend — create

- `frontend/src/api/aiChat.js` — Axios calls for chat/conversations/briefing/chips.
- `frontend/src/context/AIPanelContext.jsx` — React context exposing `{open, mode, entityType, entityId, openPanel(...), closePanel()}` so any page can trigger the drawer and the drawer state persists across route changes.
- `frontend/src/components/AIPanel.jsx` — sliding right-side drawer. Modes: `global` and `entity`. Renders conversation list + chat view + chip rail.
- `frontend/src/components/AIPanelButton.jsx` — small reusable button (sparkle icon + "AI" label) used in the header and on entity pages.

### Frontend — modify

- `frontend/package.json` — add `react-markdown` and `remark-gfm`.
- `frontend/src/App.jsx` — wrap routes in `<AIPanelProvider>` and mount `<AIPanel />` once at app level.
- `frontend/src/components/Layout.jsx` — render `<AIPanelButton mode="global" />` in the header bar (right side of the search row).
- `frontend/src/pages/ContactDetailPage.jsx` — replace the "AI Summary" button (line 408–415) with `<AIPanelButton mode="entity" entityType="contact" entityId={Number(id)} label="Chat" />`. Remove the `<AIOutputModal>` block (lines 842–848) and the `showAISummary` state. Keep the `AIOutputModal` import only if still used elsewhere on the page; otherwise drop it.
- `frontend/src/pages/EstimateDetailPage.jsx` — replace the "Generate Scope" button (line 1425–1432) with `<AIPanelButton mode="entity" entityType="estimate" entityId={Number(id)} label="Chat" />`. Remove the `<AIOutputModal>` block (lines 2229–2241) and the `showAIScope` state. Keep scope_of_work display + clear button untouched.

### Files to read but not modify

- `backend/app/services/ai_provider.py` — call `get_provider().generate()`.
- `backend/app/services/ai_events.py` — reuse `_company_context()`, `_contact_basics()`, `_format_line_items()`, `_estimates_summary_for_contact()`, `_all_notes_for_contact()`, `_activity_summary_for_contact()` where helpful.
- `backend/app/routers/ai_actions.py` — pattern reference. Do not modify; existing endpoints must keep working.
- `backend/tests/test_ai_actions.py` — fixture pattern reference (`use_mock_provider`, `_force_none_provider`).
- `backend/tests/conftest.py` — `client`, `auth_headers`, `db_session`, `seeded_stages` fixtures. The conftest is fine as-is.

---

## Conventions to follow

- **UUID primary keys are stored as `String(36)` hex** (matches `AIAction`). This works under SQLite tests where native UUID is awkward.
- **JSON columns use `sqlalchemy.JSON()`** (matches `ContactImport.field_mappings`). Postgres maps it to JSONB; SQLite maps to TEXT-with-JSON-serialization. The spec says "JSONB" — use `JSON()` for cross-DB compatibility, which is the established project pattern.
- **All `DateTime` columns use `DateTime(timezone=True)`** with `server_default=func.now()`.
- **Boolean columns** need both `default=` and `server_default=` (per `MEMORY.md`).
- **Python typing** uses `Optional[X]` not `X | None`, and `List[X]` not `list[X]` (per `MEMORY.md`).
- **All money** uses `Numeric(12,2)` (none in this sprint, but be aware when reading invoice/estimate data).
- **Test isolation**: tests must never make real LLM calls. The autouse `_force_none_provider` fixture in `test_ai_chat.py` and `test_ai_briefing.py` must mirror the one in `test_ai_actions.py`.

---

## Task 1: Migration 0026 — ai_conversations + ai_messages tables

**Files:**
- Create: `backend/alembic/versions/0026_sprint16c_ai_conversations.py`

- [ ] **Step 1: Write the migration file**

```python
"""Sprint 16c: AI conversations + messages

Revision ID: 0026
Revises: 0025
"""
from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ai_conversations_user_id", "ai_conversations", ["user_id"]
    )
    op.create_index(
        "ix_ai_conversations_entity",
        "ai_conversations",
        ["entity_type", "entity_id"],
    )

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(length=36),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ai_messages_conversation_id",
        "ai_messages",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_messages_conversation_id", table_name="ai_messages")
    op.drop_table("ai_messages")
    op.drop_index("ix_ai_conversations_entity", table_name="ai_conversations")
    op.drop_index("ix_ai_conversations_user_id", table_name="ai_conversations")
    op.drop_table("ai_conversations")
```

> Note: column is named `message_metadata` (not `metadata`) because `metadata` is a reserved attribute on SQLAlchemy `Base`. The model maps the Python attribute to this column.

- [ ] **Step 2: Manually verify migration ID chain**

Run: `ls backend/alembic/versions/ | tail -3`
Expected: shows `0024_*`, `0025_*`, `0026_sprint16c_ai_conversations.py` in order.

- [ ] **Step 3: Commit**

```bash
git add backend/alembic/versions/0026_sprint16c_ai_conversations.py
git commit -m "Sprint 16c: migration 0026 — ai_conversations + ai_messages tables"
```

---

## Task 2: SQLAlchemy models for AIConversation + AIMessage

**Files:**
- Create: `backend/app/models/ai_conversation.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_chat.py` with this initial structure:

```python
"""Sprint 16c — Conversational AI panel + morning briefing tests."""
from __future__ import annotations

import pytest

from app.config import settings
from app.models.ai_conversation import AIConversation, AIMessage
from app.services.ai_provider import MockProvider, set_provider


@pytest.fixture(autouse=True)
def _force_none_provider():
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
    """The AIConversation/AIMessage SQLAlchemy models can be created and persisted."""
    # Create a user via the setup endpoint (auth_headers fixture does that)
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
    # The relationship loads the message
    db_session.refresh(convo)
    assert len(convo.messages) == 1
    assert convo.messages[0].content == "hello there"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ai_chat.py::test_ai_conversation_model_creates -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.ai_conversation'`.

- [ ] **Step 3: Create the model file**

Write `backend/app/models/ai_conversation.py`:

```python
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[Optional["User"]] = relationship()
    messages: Mapped[List["AIMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AIMessage.created_at",
    )


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False)
    # Python attribute name is `message_metadata` because `metadata` is a
    # SQLAlchemy reserved attribute on Base.
    message_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "message_metadata", JSON(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    conversation: Mapped["AIConversation"] = relationship(back_populates="messages")
```

- [ ] **Step 4: Register the models in `app/models/__init__.py`**

Add to imports and `__all__`:

```python
from app.models.ai_conversation import AIConversation, AIMessage
```

In `__all__`, add `"AIConversation",` and `"AIMessage",` alphabetically near the other AI entry.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ai_chat.py::test_ai_conversation_model_creates -v`
Expected: PASS.

- [ ] **Step 6: Run the full existing test suite to confirm no regression**

Run: `cd backend && pytest -q`
Expected: 552+ passed (one new test added, existing 551 still pass; pre-existing Saturday-only failure of `test_dashboard_tasks_due_this_week` may show — that is a known issue, ignore it).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/ai_conversation.py backend/app/models/__init__.py backend/tests/test_ai_chat.py
git commit -m "Sprint 16c: AIConversation + AIMessage SQLAlchemy models"
```

---

## Task 3: Pydantic schemas for chat / conversations / briefing / chips

**Files:**
- Create: `backend/app/schemas/ai_chat.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ai_chat.py`:

```python
def test_schemas_importable():
    from app.schemas.ai_chat import (
        ChatRequest,
        ChatResponse,
        ConversationListItem,
        ConversationListResponse,
        MessageResponse,
        MessageListResponse,
        BriefingResponse,
        ChipsResponse,
        Chip,
    )
    # Required-field validation
    req = ChatRequest(message="hi")
    assert req.message == "hi"
    assert req.conversation_id is None
    assert req.entity_type is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ai_chat.py::test_schemas_importable -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.ai_chat'`.

- [ ] **Step 3: Create the schemas**

Write `backend/app/schemas/ai_chat.py`:

```python
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


VALID_ENTITY_TYPES = {"contact", "estimate"}


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    message: str


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    conversation_id: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    message: MessageResponse


class ConversationListItem(BaseModel):
    id: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    title: Optional[str] = None
    last_message_preview: Optional[str] = None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    items: List[ConversationListItem]
    total: int


class MessageListResponse(BaseModel):
    items: List[MessageResponse]
    total: int
    page: int
    per_page: int


class BriefingSection(BaseModel):
    """Generic section list — every briefing section is a list of dicts."""
    pass


class BriefingResponse(BaseModel):
    overdue_followups: List[Dict[str, Any]] = Field(default_factory=list)
    unsigned_estimates: Dict[str, List[Dict[str, Any]]] = Field(
        default_factory=lambda: {
            "viewed_not_signed": [],
            "not_viewed": [],
            "aging_over_5_days": [],
        }
    )
    overdue_invoices: List[Dict[str, Any]] = Field(default_factory=list)
    unpaid_invoices: List[Dict[str, Any]] = Field(default_factory=list)
    upcoming_appointments: List[Dict[str, Any]] = Field(default_factory=list)
    tasks_due: List[Dict[str, Any]] = Field(default_factory=list)
    recent_customer_actions: List[Dict[str, Any]] = Field(default_factory=list)
    overnight_ai_actions: List[Dict[str, Any]] = Field(default_factory=list)
    stale_leads: List[Dict[str, Any]] = Field(default_factory=list)
    summary_counts: Dict[str, int] = Field(default_factory=dict)
    generated_at: datetime


class NarrativeBriefingResponse(BaseModel):
    narrative: str
    data: BriefingResponse
    provider: str
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[int] = None


class Chip(BaseModel):
    label: str
    prompt: str


class ChipsResponse(BaseModel):
    items: List[Chip]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ai_chat.py::test_schemas_importable -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/ai_chat.py backend/tests/test_ai_chat.py
git commit -m "Sprint 16c: Pydantic schemas for chat + conversations + briefing + chips"
```

---

## Task 4: Add new prompt templates to ai_prompts.py

**Files:**
- Modify: `backend/app/services/ai_prompts.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ai_chat.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_chat.py::test_new_prompt_templates_exist tests/test_ai_chat.py::test_morning_briefing_prompt_renders -v`
Expected: FAIL — keys missing.

- [ ] **Step 3: Add the three new templates**

Open `backend/app/services/ai_prompts.py`. After the closing brace of the `pre_visit_summary` entry but before the `}` that closes the `PROMPTS` dict, insert:

```python
    "morning_briefing": {
        "system": (
            "You are an executive assistant briefing the owner of "
            "{company_name}, a roofing and exteriors company.\n"
            "Generate a concise morning briefing in 4-6 short sections.\n"
            "Use plain language. Lead with the most urgent items.\n"
            "Format with bold section headers and bullet lists.\n"
            "Do not invent details — only summarize the JSON data provided.\n"
            "If a section's list is empty, omit that section entirely."
        ),
        "user": (
            "Good morning, {user_first_name}. Today is {today_date}.\n\n"
            "Generate a morning briefing from this CRM data:\n\n"
            "{briefing_data_json}"
        ),
    },
    "conversation_system": {
        "system": (
            "You are a helpful CRM assistant for {company_name}, a roofing "
            "and exteriors company in Kokomo, Indiana.\n"
            "You help the owner triage their day, draft customer messages, "
            "summarize jobs, and answer questions about their pipeline.\n"
            "Keep responses concise and actionable. Use plain language.\n"
            "When drafting customer-facing messages, never use emojis and "
            "no more than one exclamation point.\n"
            "If the user asks about specific data (a customer, an estimate, "
            "an invoice) and you weren't given that data in the context, say "
            "you don't have it rather than inventing details."
        ),
        "user": "{user_message}",
    },
    "conversation_with_entity": {
        "system": (
            "You are a helpful CRM assistant for {company_name}.\n"
            "You are currently scoped to a specific {entity_label}. Use the "
            "context below to answer questions and draft messages.\n"
            "Keep responses concise. Never invent details not present in the "
            "context. When drafting customer messages, never use emojis.\n\n"
            "=== {entity_label} CONTEXT ===\n"
            "{entity_context}\n"
            "=== END CONTEXT ==="
        ),
        "user": "{user_message}",
    },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_chat.py::test_new_prompt_templates_exist tests/test_ai_chat.py::test_morning_briefing_prompt_renders -v`
Expected: PASS.

- [ ] **Step 5: Run the existing AI tests to confirm no regression**

Run: `cd backend && pytest tests/test_ai_actions.py -q`
Expected: all pass (the existing `test_all_prompt_templates_exist` only asserts `expected.issubset(PROMPTS.keys())` so adding keys is safe).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_prompts.py backend/tests/test_ai_chat.py
git commit -m "Sprint 16c: add morning_briefing + conversation prompt templates"
```

---

## Task 5: ai_chat service — start_conversation + continue_conversation

**Files:**
- Create: `backend/app/services/ai_chat.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ai_chat.py`:

```python
def test_start_conversation_global_with_mock(
    db_session, seeded_stages, auth_headers, client, use_mock_provider
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

    # Both messages persisted
    db_session.refresh(convo)
    assert len(convo.messages) == 2
    assert convo.messages[0].role == "user"
    assert convo.messages[0].content == "What needs attention today?"
    assert convo.messages[1].role == "assistant"


def test_start_conversation_entity_scoped_uses_context(
    db_session, seeded_stages, auth_headers, client, use_mock_provider
):
    """An entity-scoped conversation includes the entity's context in the
    system prompt sent to the provider."""
    from app.models.user import User
    from app.models.contact import Contact
    from app.services.ai_chat import start_conversation

    # Capture what gets sent to the provider
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

    from app.services.ai_provider import set_provider
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
        # The system prompt embedded the contact's context
        assert "Jane Doe" in captured["system"]
        assert "Summarize this customer" in captured["user"]
    finally:
        set_provider(None)


def test_continue_conversation_includes_history(
    db_session, seeded_stages, auth_headers, client, use_mock_provider
):
    """continue_conversation feeds prior messages back into the user prompt
    so the LLM has context for follow-ups."""
    from app.models.user import User
    from app.services.ai_chat import start_conversation, continue_conversation

    use_mock_provider(canned="First reply.")
    user = db_session.query(User).first()
    convo, _ = start_conversation(
        db=db_session, user_id=user.id, initial_message="First message."
    )

    # Capture second-call prompt
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

    from app.services.ai_provider import set_provider
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
        # 2 from start + 2 from continue = 4 messages
        assert len(convo.messages) == 4
    finally:
        set_provider(None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_chat.py::test_start_conversation_global_with_mock tests/test_ai_chat.py::test_start_conversation_entity_scoped_uses_context tests/test_ai_chat.py::test_continue_conversation_includes_history -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.ai_chat'`.

- [ ] **Step 3: Create `backend/app/services/ai_chat.py` with start + continue**

```python
"""Conversational AI service.

Exposes start_conversation/continue_conversation for the chat panel and
get_briefing_context for the morning briefing data endpoint.

All LLM calls go through ai_provider.get_provider(). When the provider is
NoneProvider, assistant messages are persisted with empty content so the
conversation history remains consistent — the panel renders an inline
"AI provider not configured" warning rather than blocking.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.services import ai_events
from app.services.ai_prompts import render_prompt
from app.services.ai_provider import AIProvider, get_provider

logger = logging.getLogger("legacy_crm.ai")

MAX_HISTORY_MESSAGES = 20
TITLE_MAX_LEN = 80


# ---------- Public API ----------


def start_conversation(
    *,
    db: Session,
    user_id: int,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    initial_message: str,
    provider: Optional[AIProvider] = None,
) -> Tuple[AIConversation, AIMessage]:
    """Create a new conversation, persist initial user message, generate
    assistant reply, persist assistant message, return both.
    """
    convo = AIConversation(
        id=uuid.uuid4().hex,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        title=_derive_title(initial_message),
    )
    db.add(convo)
    db.flush()  # assign timestamps without ending tx

    user_msg = _persist_message(db, convo.id, "user", initial_message)
    assistant_msg = _generate_and_persist(
        db=db,
        convo=convo,
        user_message_text=initial_message,
        history=[user_msg],
        provider=provider,
    )

    convo.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(convo)
    db.refresh(assistant_msg)
    return convo, assistant_msg


def continue_conversation(
    *,
    db: Session,
    conversation_id: str,
    user_message: str,
    provider: Optional[AIProvider] = None,
) -> AIMessage:
    """Append a user message to an existing conversation and generate an
    assistant reply. Returns the assistant message."""
    convo = (
        db.query(AIConversation)
        .filter(AIConversation.id == conversation_id)
        .first()
    )
    if convo is None:
        raise ValueError(f"Conversation {conversation_id!r} not found")

    history = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == convo.id)
        .order_by(AIMessage.created_at.asc())
        .limit(MAX_HISTORY_MESSAGES)
        .all()
    )

    user_msg = _persist_message(db, convo.id, "user", user_message)
    history.append(user_msg)

    assistant_msg = _generate_and_persist(
        db=db,
        convo=convo,
        user_message_text=user_message,
        history=history,
        provider=provider,
    )
    convo.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


# ---------- Internal helpers ----------


def _derive_title(text: str) -> str:
    cleaned = " ".join((text or "").split())
    return cleaned[:TITLE_MAX_LEN] if cleaned else "New conversation"


def _persist_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> AIMessage:
    msg = AIMessage(
        id=uuid.uuid4().hex,
        conversation_id=conversation_id,
        role=role,
        content=content,
        message_metadata=metadata,
    )
    db.add(msg)
    db.flush()
    return msg


def _build_system_prompt(
    db: Session, convo: AIConversation
) -> str:
    """Pick the right system prompt template + entity context."""
    company_ctx = {
        "company_name": settings.ai_company_name,
        "company_phone": settings.ai_company_phone,
    }
    if convo.entity_type and convo.entity_id:
        entity_label, entity_context = _build_entity_context(
            db, convo.entity_type, convo.entity_id
        )
        ctx = {
            **company_ctx,
            "entity_label": entity_label,
            "entity_context": entity_context,
        }
        system, _ = render_prompt("conversation_with_entity", ctx)
        return system
    system, _ = render_prompt("conversation_system", company_ctx)
    return system


def _build_entity_context(
    db: Session, entity_type: str, entity_id: int
) -> Tuple[str, str]:
    """Return (label, context_text) for the system prompt."""
    if entity_type == "contact":
        contact = db.query(Contact).filter(Contact.id == entity_id).first()
        if contact is None:
            return ("Customer", "(customer not found)")
        lines = [
            f"Name: {contact.name}",
            f"Phone: {contact.phone or ''}",
            f"Email: {contact.email or ''}",
            f"Address: {contact.address or ''}",
            f"Lead Source: {contact.lead_source or ''}",
            f"Client Type: {contact.client_type or ''}",
            "",
            "Estimates:",
            ai_events._estimates_summary_for_contact(db, contact.id),
            "",
            "Recent Notes:",
            ai_events._all_notes_for_contact(db, contact.id),
            "",
            "Recent Activity:",
            ai_events._activity_summary_for_contact(db, contact.id),
        ]
        return ("Customer", "\n".join(lines))
    if entity_type == "estimate":
        estimate = (
            db.query(Estimate).filter(Estimate.id == entity_id).first()
        )
        if estimate is None:
            return ("Estimate", "(estimate not found)")
        contact_line = ""
        if estimate.job and estimate.job.contact:
            contact_line = (
                f"Customer: {estimate.job.contact.name}  |  "
                f"Phone: {estimate.job.contact.phone or ''}"
            )
        lines = [
            f"Estimate: {estimate.name or f'#{estimate.id}'}",
            f"Status: {estimate.status}",
            f"Total: ${estimate.total or 0}",
            contact_line,
            "",
            "Line Items:",
            ai_events._format_line_items(estimate),
        ]
        return ("Estimate", "\n".join(lines))
    return (entity_type.title(), "(unsupported entity type)")


def _build_user_prompt(history: List[AIMessage], current_user_text: str) -> str:
    """Format the full message history for the user prompt.

    The provider abstraction takes a single (system, user) pair, so we
    serialize history into the user prompt with role markers. Recent
    messages (last MAX_HISTORY_MESSAGES) only.
    """
    recent = history[-MAX_HISTORY_MESSAGES:]
    lines = []
    for m in recent:
        prefix = "User" if m.role == "user" else "Assistant"
        lines.append(f"{prefix}: {m.content}")
    # If the current user message isn't already in history, append it.
    if not recent or recent[-1].content != current_user_text:
        lines.append(f"User: {current_user_text}")
    lines.append("Assistant:")
    return "\n\n".join(lines)


def _generate_and_persist(
    *,
    db: Session,
    convo: AIConversation,
    user_message_text: str,
    history: List[AIMessage],
    provider: Optional[AIProvider],
) -> AIMessage:
    system_prompt = _build_system_prompt(db, convo)
    user_prompt = _build_user_prompt(history, user_message_text)
    active = provider or get_provider()
    response = active.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    metadata = {
        "provider": response.provider,
        "model": response.model,
        "tokens_used": response.tokens_used,
        "duration_ms": response.duration_ms,
        "success": response.success,
        "error": response.error,
    }
    return _persist_message(
        db,
        conversation_id=convo.id,
        role="assistant",
        content=response.content or "",
        metadata=metadata,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_chat.py::test_start_conversation_global_with_mock tests/test_ai_chat.py::test_start_conversation_entity_scoped_uses_context tests/test_ai_chat.py::test_continue_conversation_includes_history -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_chat.py backend/tests/test_ai_chat.py
git commit -m "Sprint 16c: ai_chat.start_conversation + continue_conversation"
```

---

## Task 6: ai_chat service — get_briefing_context

**Files:**
- Modify: `backend/app/services/ai_chat.py`

This is a pure data-assembly function. It returns a Python dict with the sections enumerated in the spec, computed from live CRM data. All boundary calculations use America/Indiana/Indianapolis timezone via `zoneinfo` (stdlib).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ai_briefing.py`:

```python
"""Sprint 16c — Morning briefing data endpoint tests."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.config import settings
from app.services.ai_provider import set_provider


@pytest.fixture(autouse=True)
def _force_none_provider():
    original = settings.llm_provider
    settings.llm_provider = "none"
    set_provider(None)
    yield
    settings.llm_provider = original
    set_provider(None)


def _bootstrap_user(db_session, client):
    """Run setup so a user exists, then return that User row."""
    client.post(
        "/api/auth/setup",
        json={
            "email": "dale@legacy.com",
            "full_name": "Dale Owner",
            "password": "testpassword123",
        },
    )
    from app.models.user import User
    return db_session.query(User).first()


def test_briefing_empty_data_returns_all_sections(db_session, client):
    from app.services.ai_chat import get_briefing_context
    user = _bootstrap_user(db_session, client)
    data = get_briefing_context(db=db_session, user_id=user.id)
    expected_keys = {
        "overdue_followups",
        "unsigned_estimates",
        "overdue_invoices",
        "unpaid_invoices",
        "upcoming_appointments",
        "tasks_due",
        "recent_customer_actions",
        "overnight_ai_actions",
        "stale_leads",
        "summary_counts",
        "generated_at",
    }
    assert set(data.keys()) == expected_keys
    assert isinstance(data["unsigned_estimates"], dict)
    assert "viewed_not_signed" in data["unsigned_estimates"]
    assert "not_viewed" in data["unsigned_estimates"]
    assert "aging_over_5_days" in data["unsigned_estimates"]
    assert data["summary_counts"]["overdue_followups"] == 0


def test_briefing_overdue_invoices(
    db_session, seeded_stages, client, auth_headers
):
    """Invoices past due_date show up under overdue_invoices."""
    from app.services.ai_chat import get_briefing_context
    from app.models.contact import Contact
    from app.models.invoice import Invoice
    from app.models.job import Job
    from app.models.user import User

    user = db_session.query(User).first()
    contact = Contact(name="Past-Due Co")
    db_session.add(contact)
    db_session.commit()

    job = Job(contact_id=contact.id, work_type="retail")
    db_session.add(job)
    db_session.commit()

    today = date.today()
    overdue = Invoice(
        job_id=job.id,
        invoice_number="INV-OD01",
        status="partial",
        date_invoiced=today - timedelta(days=20),
        due_date=today - timedelta(days=10),
        subtotal=Decimal("1000"),
        total=Decimal("1000"),
        balance=Decimal("400"),
    )
    not_yet = Invoice(
        job_id=job.id,
        invoice_number="INV-FUT01",
        status="draft",
        date_invoiced=today,
        due_date=today + timedelta(days=10),
        subtotal=Decimal("500"),
        total=Decimal("500"),
        balance=Decimal("500"),
    )
    db_session.add_all([overdue, not_yet])
    db_session.commit()

    data = get_briefing_context(db=db_session, user_id=user.id)
    overdue_nums = [i["invoice_number"] for i in data["overdue_invoices"]]
    assert "INV-OD01" in overdue_nums
    assert "INV-FUT01" not in overdue_nums

    unpaid_nums = [i["invoice_number"] for i in data["unpaid_invoices"]]
    assert "INV-FUT01" in unpaid_nums
    assert "INV-OD01" not in unpaid_nums


def test_briefing_tasks_due_today_or_overdue(db_session, client):
    from datetime import date, timedelta
    from app.models.task import Task
    from app.models.user import User
    from app.services.ai_chat import get_briefing_context

    user = _bootstrap_user(db_session, client)
    today = date.today()
    db_session.add_all([
        Task(title="Today task", status="open", due_date=today,
             assigned_to_user_id=user.id),
        Task(title="Overdue task", status="open",
             due_date=today - timedelta(days=2),
             assigned_to_user_id=user.id),
        Task(title="Future task", status="open",
             due_date=today + timedelta(days=2),
             assigned_to_user_id=user.id),
        Task(title="Done task", status="done", due_date=today,
             assigned_to_user_id=user.id),
    ])
    db_session.commit()

    data = get_briefing_context(db=db_session, user_id=user.id)
    titles = [t["title"] for t in data["tasks_due"]]
    assert "Today task" in titles
    assert "Overdue task" in titles
    assert "Future task" not in titles
    assert "Done task" not in titles


def test_briefing_summary_counts_match_section_lengths(db_session, client):
    """summary_counts must match the lengths of each list section."""
    from datetime import date
    from app.models.task import Task
    from app.services.ai_chat import get_briefing_context

    user = _bootstrap_user(db_session, client)
    db_session.add_all([
        Task(title=f"T{i}", status="open", due_date=date.today(),
             assigned_to_user_id=user.id)
        for i in range(3)
    ])
    db_session.commit()

    data = get_briefing_context(db=db_session, user_id=user.id)
    assert data["summary_counts"]["tasks_due"] == 3
    assert data["summary_counts"]["overdue_followups"] == len(
        data["overdue_followups"]
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_briefing.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_briefing_context' from 'app.services.ai_chat'`.

- [ ] **Step 3: Append `get_briefing_context` to `backend/app/services/ai_chat.py`**

Add these imports near the top of the file (alongside existing imports):

```python
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_

from app.models.ai_action import AIAction
from app.models.appointment import Appointment
from app.models.contact import Contact
from app.models.estimate import Estimate
from app.models.estimate_status_history import EstimateStatusHistory
from app.models.invoice import Invoice
from app.models.note import Note
from app.models.payment import Payment
from app.models.pipeline import Pipeline
from app.models.task import Task
```

Then append at the bottom of the file:

```python
# ---------- Morning briefing ----------

INDIANA_TZ = ZoneInfo("America/Indiana/Indianapolis")
STALE_LEAD_DAYS = 14
OVERDUE_FOLLOWUP_DAYS = 3
AGING_ESTIMATE_DAYS = 5
RECENT_ACTION_HOURS = 24


def get_briefing_context(*, db: Session, user_id: int) -> Dict[str, Any]:
    """Assemble the morning briefing data dict.

    No LLM is involved. This is the structured-data endpoint that powers
    both the in-CRM panel (via /api/ai/briefing/narrative) and external
    consumers like HyperAgent (via /api/ai/briefing).
    """
    now_local = datetime.now(INDIANA_TZ)
    today = now_local.date()
    overdue_invoices = _briefing_overdue_invoices(db, today)
    unpaid_invoices = _briefing_unpaid_invoices(db, today)
    tasks_due = _briefing_tasks_due(db, today, user_id)
    upcoming_appointments = _briefing_upcoming_appointments(db, today, user_id)
    overdue_followups = _briefing_overdue_followups(db, today)
    unsigned = _briefing_unsigned_estimates(db, now_local)
    stale_leads = _briefing_stale_leads(db, today)
    recent_actions = _briefing_recent_customer_actions(db, now_local)
    overnight_ai = _briefing_overnight_ai_actions(db, now_local)

    summary_counts = {
        "overdue_followups": len(overdue_followups),
        "unsigned_estimates": (
            len(unsigned["viewed_not_signed"])
            + len(unsigned["not_viewed"])
            + len(unsigned["aging_over_5_days"])
        ),
        "overdue_invoices": len(overdue_invoices),
        "unpaid_invoices": len(unpaid_invoices),
        "upcoming_appointments": len(upcoming_appointments),
        "tasks_due": len(tasks_due),
        "recent_customer_actions": len(recent_actions),
        "overnight_ai_actions": len(overnight_ai),
        "stale_leads": len(stale_leads),
    }

    return {
        "overdue_followups": overdue_followups,
        "unsigned_estimates": unsigned,
        "overdue_invoices": overdue_invoices,
        "unpaid_invoices": unpaid_invoices,
        "upcoming_appointments": upcoming_appointments,
        "tasks_due": tasks_due,
        "recent_customer_actions": recent_actions,
        "overnight_ai_actions": overnight_ai,
        "stale_leads": stale_leads,
        "summary_counts": summary_counts,
        "generated_at": datetime.now(timezone.utc),
    }


def _briefing_overdue_invoices(db: Session, today: date) -> List[Dict[str, Any]]:
    rows = (
        db.query(Invoice)
        .filter(Invoice.due_date < today)
        .filter(Invoice.balance > 0)
        .filter(Invoice.status != "void")
        .order_by(Invoice.due_date.asc())
        .all()
    )
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "status": inv.status,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "days_overdue": (today - inv.due_date).days if inv.due_date else 0,
            "balance": str(inv.balance),
            "total": str(inv.total),
            "job_id": inv.job_id,
        }
        for inv in rows
    ]


def _briefing_unpaid_invoices(db: Session, today: date) -> List[Dict[str, Any]]:
    rows = (
        db.query(Invoice)
        .filter(Invoice.balance > 0)
        .filter(Invoice.status != "void")
        .filter(or_(Invoice.due_date >= today, Invoice.due_date.is_(None)))
        .order_by(Invoice.due_date.asc().nullslast())
        .all()
    )
    return [
        {
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "status": inv.status,
            "due_date": inv.due_date.isoformat() if inv.due_date else None,
            "balance": str(inv.balance),
            "total": str(inv.total),
            "job_id": inv.job_id,
        }
        for inv in rows
    ]


def _briefing_tasks_due(
    db: Session, today: date, user_id: int
) -> List[Dict[str, Any]]:
    rows = (
        db.query(Task)
        .filter(Task.status != "done")
        .filter(Task.due_date <= today)
        .order_by(Task.due_date.asc())
        .all()
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "days_overdue": (today - t.due_date).days if t.due_date else 0,
            "assigned_to_user_id": t.assigned_to_user_id,
            "related_entity_type": t.related_entity_type,
            "related_entity_id": t.related_entity_id,
        }
        for t in rows
    ]


def _briefing_upcoming_appointments(
    db: Session, today: date, user_id: int
) -> List[Dict[str, Any]]:
    cutoff = today + timedelta(days=7)
    rows = (
        db.query(Appointment)
        .filter(Appointment.appointment_date >= today)
        .filter(Appointment.appointment_date <= cutoff)
        .order_by(Appointment.appointment_date.asc())
        .all()
    )
    return [
        {
            "id": a.id,
            "title": a.title,
            "date": a.appointment_date.isoformat(),
            "time": a.appointment_time.isoformat() if a.appointment_time else None,
            "duration_minutes": a.duration_minutes,
            "type": a.appointment_type,
            "contact_id": a.contact_id,
            "assigned_to_user_id": a.assigned_to_user_id,
        }
        for a in rows
    ]


def _briefing_overdue_followups(
    db: Session, today: date
) -> List[Dict[str, Any]]:
    """Contacts with an open estimate ('sent' or 'viewed') and no recent
    note/activity in OVERDUE_FOLLOWUP_DAYS+ days."""
    from app.models.job import Job

    cutoff_dt = datetime.combine(
        today - timedelta(days=OVERDUE_FOLLOWUP_DAYS),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    pairs = (
        db.query(Contact, Estimate)
        .join(Job, Job.contact_id == Contact.id)
        .join(Estimate, Estimate.job_id == Job.id)
        .filter(Estimate.status.in_(["sent", "viewed"]))
        .all()
    )

    out: List[Dict[str, Any]] = []
    seen_contact_ids = set()
    for contact, estimate in pairs:
        if contact.id in seen_contact_ids:
            continue
        # Most recent note for this contact
        latest_note = (
            db.query(Note.created_at)
            .filter(Note.entity_type == "contact")
            .filter(Note.entity_id == contact.id)
            .order_by(Note.created_at.desc())
            .first()
        )
        last_touch = latest_note[0] if latest_note else estimate.created_at
        if last_touch and last_touch >= cutoff_dt:
            continue
        seen_contact_ids.add(contact.id)
        out.append(
            {
                "contact_id": contact.id,
                "contact_name": contact.name,
                "contact_phone": contact.phone,
                "estimate_id": estimate.id,
                "estimate_total": str(estimate.total or 0),
                "last_activity": (
                    last_touch.isoformat() if last_touch else None
                ),
            }
        )
    return out


def _briefing_unsigned_estimates(
    db: Session, now_local: datetime
) -> Dict[str, List[Dict[str, Any]]]:
    """Group 'sent' estimates by signal: viewed-but-not-signed, not viewed
    yet, or aging > 5 days.

    'viewed' is signaled by a status-history row of status='viewed'.
    """
    sent = (
        db.query(Estimate)
        .filter(Estimate.status.in_(["sent", "viewed"]))
        .all()
    )
    aging_cutoff = now_local - timedelta(days=AGING_ESTIMATE_DAYS)
    out = {
        "viewed_not_signed": [],
        "not_viewed": [],
        "aging_over_5_days": [],
    }
    for est in sent:
        viewed = est.status == "viewed" or (
            db.query(EstimateStatusHistory)
            .filter(EstimateStatusHistory.estimate_id == est.id)
            .filter(EstimateStatusHistory.status == "viewed")
            .first()
            is not None
        )
        row = {
            "id": est.id,
            "name": est.name or f"Estimate #{est.id}",
            "status": est.status,
            "total": str(est.total or 0),
            "created_at": (
                est.created_at.isoformat() if est.created_at else None
            ),
        }
        # Aging takes precedence for the red-flag bucket
        created_at_aware = est.created_at
        if (
            created_at_aware
            and created_at_aware.tzinfo
            and created_at_aware < aging_cutoff
        ):
            out["aging_over_5_days"].append(row)
            continue
        if viewed:
            out["viewed_not_signed"].append(row)
        else:
            out["not_viewed"].append(row)
    return out


def _briefing_stale_leads(db: Session, today: date) -> List[Dict[str, Any]]:
    """Contacts in the Leads pipeline with no activity in 14+ days."""
    leads_pipeline = (
        db.query(Pipeline).filter(Pipeline.slug == "leads").first()
    )
    if leads_pipeline is None:
        return []
    cutoff_dt = datetime.combine(
        today - timedelta(days=STALE_LEAD_DAYS),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
    contacts = (
        db.query(Contact)
        .filter(Contact.pipeline_id == leads_pipeline.id)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for c in contacts:
        latest_note = (
            db.query(Note.created_at)
            .filter(Note.entity_type == "contact")
            .filter(Note.entity_id == c.id)
            .order_by(Note.created_at.desc())
            .first()
        )
        last_touch = latest_note[0] if latest_note else c.created_at
        if last_touch and last_touch >= cutoff_dt:
            continue
        # Largest open estimate value for sort
        from app.models.job import Job
        biggest = (
            db.query(Estimate.total)
            .join(Job, Job.id == Estimate.job_id)
            .filter(Job.contact_id == c.id)
            .order_by(Estimate.total.desc().nullslast())
            .first()
        )
        out.append(
            {
                "contact_id": c.id,
                "contact_name": c.name,
                "contact_phone": c.phone,
                "lead_source": c.lead_source,
                "estimate_value": str(biggest[0]) if biggest and biggest[0] else "0",
                "last_activity": last_touch.isoformat() if last_touch else None,
            }
        )
    out.sort(key=lambda r: Decimal(r["estimate_value"] or "0"), reverse=True)
    return out


def _briefing_recent_customer_actions(
    db: Session, now_local: datetime
) -> List[Dict[str, Any]]:
    cutoff = now_local - timedelta(hours=RECENT_ACTION_HOURS)
    out: List[Dict[str, Any]] = []
    history = (
        db.query(EstimateStatusHistory)
        .filter(EstimateStatusHistory.changed_at >= cutoff)
        .filter(EstimateStatusHistory.status.in_(["viewed", "approved"]))
        .order_by(EstimateStatusHistory.changed_at.desc())
        .all()
    )
    for h in history:
        out.append(
            {
                "type": f"estimate_{h.status}",
                "estimate_id": h.estimate_id,
                "at": h.changed_at.isoformat() if h.changed_at else None,
                "actor": h.changed_by_name,
            }
        )
    payments = (
        db.query(Payment)
        .filter(Payment.created_at >= cutoff)
        .order_by(Payment.created_at.desc())
        .all()
    )
    for p in payments:
        out.append(
            {
                "type": "payment",
                "invoice_id": p.invoice_id,
                "amount": str(p.amount),
                "method": p.method,
                "at": p.created_at.isoformat() if p.created_at else None,
            }
        )
    return out


def _briefing_overnight_ai_actions(
    db: Session, now_local: datetime
) -> List[Dict[str, Any]]:
    """AIAction rows created since the last 7am Indiana time."""
    today = now_local.date()
    seven_am = datetime.combine(today, datetime.min.time(), tzinfo=INDIANA_TZ).replace(
        hour=7
    )
    if now_local < seven_am:
        # Before 7am: window is yesterday 7am → now
        seven_am = seven_am - timedelta(days=1)
    rows = (
        db.query(AIAction)
        .filter(AIAction.created_at >= seven_am)
        .order_by(AIAction.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "event_type": r.event_type,
            "status": r.status,
            "contact_id": r.contact_id,
            "estimate_id": r.estimate_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_briefing.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: 559+ pass (8 new tests added on top of 551).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_chat.py backend/tests/test_ai_briefing.py
git commit -m "Sprint 16c: ai_chat.get_briefing_context with Indiana timezone boundaries"
```

---

## Task 7: Router — POST /api/ai/chat (start + continue)

**Files:**
- Create: `backend/app/routers/ai_chat.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ai_chat.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_chat.py -k chat -v`
Expected: FAIL with 404s (router not registered).

- [ ] **Step 3: Create the router file**

Write `backend/app/routers/ai_chat.py`:

```python
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ai_conversation import AIConversation, AIMessage
from app.models.user import User
from app.schemas.ai_chat import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    VALID_ENTITY_TYPES,
)
from app.services.ai_chat import continue_conversation, start_conversation
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai-chat"])


def _msg_to_response(msg: AIMessage) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        metadata=msg.message_metadata,
        created_at=msg.created_at,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.entity_type and body.entity_type not in VALID_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported entity_type {body.entity_type!r}",
        )
    if body.conversation_id:
        convo = (
            db.query(AIConversation)
            .filter(AIConversation.id == body.conversation_id)
            .filter(AIConversation.user_id == current_user.id)
            .first()
        )
        if convo is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        msg = continue_conversation(
            db=db,
            conversation_id=convo.id,
            user_message=body.message,
        )
        return ChatResponse(
            conversation_id=convo.id,
            entity_type=convo.entity_type,
            entity_id=convo.entity_id,
            message=_msg_to_response(msg),
        )

    convo, msg = start_conversation(
        db=db,
        user_id=current_user.id,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        initial_message=body.message,
    )
    return ChatResponse(
        conversation_id=convo.id,
        entity_type=convo.entity_type,
        entity_id=convo.entity_id,
        message=_msg_to_response(msg),
    )
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

Add the import alongside the existing AI import (line ~14):

```python
from app.routers.ai_actions import router as ai_actions_router
from app.routers.ai_chat import router as ai_chat_router
```

And in the `include_router` block (line ~76), add directly after `app.include_router(ai_actions_router)`:

```python
app.include_router(ai_chat_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_chat.py -k chat -v`
Expected: all chat tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ai_chat.py backend/app/main.py backend/tests/test_ai_chat.py
git commit -m "Sprint 16c: POST /api/ai/chat (start + continue conversations)"
```

---

## Task 8: Router — GET /api/ai/conversations (list with filtering)

**Files:**
- Modify: `backend/app/routers/ai_chat.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ai_chat.py`:

```python
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
    # Titles auto-derive from initial message
    assert any("First" in (t or "") for t in titles)
    assert all(c["message_count"] == 2 for c in body["items"])
    # Sorted by updated_at desc — newest first
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_chat.py -k list_conversations -v`
Expected: FAIL with 404 or 405.

- [ ] **Step 3: Add the list endpoint to `backend/app/routers/ai_chat.py`**

Add the schema imports and these endpoints to the same router file:

```python
# At top of file, expand existing schema import:
from app.schemas.ai_chat import (
    ChatRequest,
    ChatResponse,
    ConversationListItem,
    ConversationListResponse,
    MessageResponse,
    VALID_ENTITY_TYPES,
)

# At bottom of file, after the chat() endpoint:

@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(AIConversation)
        .filter(AIConversation.user_id == current_user.id)
    )
    if entity_type is not None:
        query = query.filter(AIConversation.entity_type == entity_type)
    if entity_id is not None:
        query = query.filter(AIConversation.entity_id == entity_id)

    rows = query.order_by(AIConversation.updated_at.desc()).all()

    items = []
    for c in rows:
        last = (
            db.query(AIMessage)
            .filter(AIMessage.conversation_id == c.id)
            .order_by(AIMessage.created_at.desc())
            .first()
        )
        message_count = (
            db.query(AIMessage)
            .filter(AIMessage.conversation_id == c.id)
            .count()
        )
        preview = None
        if last and last.content:
            preview = last.content.strip()
            if len(preview) > 120:
                preview = preview[:117] + "..."
        items.append(
            ConversationListItem(
                id=c.id,
                entity_type=c.entity_type,
                entity_id=c.entity_id,
                title=c.title,
                last_message_preview=preview,
                message_count=message_count,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
        )
    return ConversationListResponse(items=items, total=len(items))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_chat.py -k list_conversations -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ai_chat.py backend/tests/test_ai_chat.py
git commit -m "Sprint 16c: GET /api/ai/conversations with entity filter"
```

---

## Task 9: Router — GET /api/ai/conversations/{id}/messages + DELETE /api/ai/conversations/{id}

**Files:**
- Modify: `backend/app/routers/ai_chat.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ai_chat.py`:

```python
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


def test_get_messages_403_for_other_users_conversation(
    client, auth_headers, seeded_stages, use_mock_provider, db_session
):
    """Listing messages for another user's conversation returns 404."""
    use_mock_provider(canned="r")
    convo = client.post(
        "/api/ai/chat", headers=auth_headers, json={"message": "mine"}
    ).json()

    # Create a second user and authenticate as them
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
    assert other_resp.status_code in (200, 201)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_chat.py -k "get_messages or delete_conversation" -v`
Expected: FAIL with 404/405.

- [ ] **Step 3: Add the message-list and delete endpoints**

Append to `backend/app/routers/ai_chat.py` (and update the schema import to include `MessageListResponse`):

```python
from app.schemas.ai_chat import (
    ChatRequest,
    ChatResponse,
    ConversationListItem,
    ConversationListResponse,
    MessageListResponse,
    MessageResponse,
    VALID_ENTITY_TYPES,
)

from fastapi import status as http_status

@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=MessageListResponse,
)
def get_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convo = (
        db.query(AIConversation)
        .filter(AIConversation.id == conversation_id)
        .filter(AIConversation.user_id == current_user.id)
        .first()
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    base = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.asc())
    )
    total = base.count()
    rows = base.offset((page - 1) * per_page).limit(per_page).all()
    return MessageListResponse(
        items=[_msg_to_response(m) for m in rows],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    convo = (
        db.query(AIConversation)
        .filter(AIConversation.id == conversation_id)
        .filter(AIConversation.user_id == current_user.id)
        .first()
    )
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(convo)
    db.commit()
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_chat.py -k "get_messages or delete_conversation" -v`
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ai_chat.py backend/tests/test_ai_chat.py
git commit -m "Sprint 16c: GET messages + DELETE conversation endpoints"
```

---

## Task 10: Router — GET /api/ai/briefing + GET /api/ai/briefing/narrative

**Files:**
- Modify: `backend/app/routers/ai_chat.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ai_briefing.py`:

```python
def test_briefing_endpoint_auth(client):
    resp = client.get("/api/ai/briefing")
    assert resp.status_code == 401


def test_briefing_endpoint_returns_data_even_with_none_provider(
    client, auth_headers, seeded_stages
):
    """Spec: /api/ai/briefing must work regardless of LLM_PROVIDER setting."""
    resp = client.get("/api/ai/briefing", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "summary_counts" in body
    assert "overdue_followups" in body
    assert "unsigned_estimates" in body
    assert isinstance(body["unsigned_estimates"], dict)


def test_narrative_briefing_endpoint_503_with_none_provider(
    client, auth_headers, seeded_stages
):
    """Narrative requires an LLM. With provider=none, return 503."""
    resp = client.get("/api/ai/briefing/narrative", headers=auth_headers)
    assert resp.status_code == 503


def test_narrative_briefing_endpoint_with_mock(
    client, auth_headers, seeded_stages, use_mock_provider
):
    use_mock_provider(canned="Good morning. Three things to do today.")
    resp = client.get("/api/ai/briefing/narrative", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["narrative"].startswith("Good morning")
    assert "data" in body
    assert "summary_counts" in body["data"]
    assert body["provider"] == "mock"
```

(And add the `use_mock_provider` fixture at the top of `test_ai_briefing.py` matching the one in `test_ai_chat.py`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_briefing.py -k "endpoint_auth or returns_data or narrative" -v`
Expected: FAIL with 404 (routes not registered).

- [ ] **Step 3: Add the briefing endpoints to `backend/app/routers/ai_chat.py`**

Update the schema import:

```python
from app.schemas.ai_chat import (
    ...,
    BriefingResponse,
    NarrativeBriefingResponse,
)
```

Add at the bottom of the router file:

```python
import json as _json

from app.services.ai_chat import get_briefing_context
from app.services.ai_prompts import render_prompt
from app.services.ai_provider import get_provider, NoneProvider


@router.get("/briefing", response_model=BriefingResponse)
def briefing(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_briefing_context(db=db, user_id=current_user.id)


@router.get("/briefing/narrative", response_model=NarrativeBriefingResponse)
def briefing_narrative(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    provider = get_provider()
    if isinstance(provider, NoneProvider):
        raise HTTPException(
            status_code=503,
            detail="LLM provider is not configured (LLM_PROVIDER=none)",
        )
    data = get_briefing_context(db=db, user_id=current_user.id)
    # Serialize for the prompt; default str() handles datetimes/Decimals.
    safe_json = _json.dumps(data, default=str, indent=2)
    system, user_prompt = render_prompt(
        "morning_briefing",
        {
            "company_name": "Legacy Roofing & Exteriors",
            "user_first_name": (current_user.full_name or "").split(" ")[0]
            or "there",
            "today_date": data["generated_at"].date().isoformat()
            if hasattr(data["generated_at"], "date")
            else str(data["generated_at"]),
            "briefing_data_json": safe_json,
        },
    )
    response = provider.generate(
        system_prompt=system, user_prompt=user_prompt, max_tokens=2048
    )
    return NarrativeBriefingResponse(
        narrative=response.content or "",
        data=data,
        provider=response.provider,
        model=response.model,
        tokens_used=response.tokens_used,
        duration_ms=response.duration_ms,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_briefing.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ai_chat.py backend/tests/test_ai_briefing.py
git commit -m "Sprint 16c: GET /api/ai/briefing + /api/ai/briefing/narrative"
```

---

## Task 11: Router — GET /api/ai/chips

**Files:**
- Modify: `backend/app/routers/ai_chat.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ai_chat.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_ai_chat.py -k chips -v`
Expected: FAIL with 404.

- [ ] **Step 3: Add chips endpoint + chip definitions**

Update the schema import:

```python
from app.schemas.ai_chat import (
    ...,
    Chip,
    ChipsResponse,
)
```

Append:

```python
GLOBAL_CHIPS = [
    Chip(label="What needs attention today?",
         prompt="What needs my attention today across all my customers and jobs?"),
    Chip(label="Overdue follow-ups",
         prompt="List my overdue follow-ups and suggest next steps."),
    Chip(label="Unpaid invoices",
         prompt="Summarize my unpaid invoices and which ones to chase first."),
    Chip(label="This week's schedule",
         prompt="What's on my schedule this week?"),
    Chip(label="Draft a follow-up for...",
         prompt="Help me draft a follow-up message. Which customer?"),
]

CONTACT_CHIPS = [
    Chip(label="Summarize this customer",
         prompt="Give me a summary of this customer for a pre-visit briefing."),
    Chip(label="Draft follow-up email",
         prompt="Draft a friendly follow-up email for this customer."),
    Chip(label="What's the history here?",
         prompt="What's the full history with this customer? Any concerns?"),
    Chip(label="Generate scope of work",
         prompt="Draft a scope of work based on this customer's most recent estimate."),
]

ESTIMATE_CHIPS = [
    Chip(label="Explain this estimate",
         prompt="Explain this estimate in plain language as if to the homeowner."),
    Chip(label="Draft approval follow-up",
         prompt="Draft a short follow-up to nudge the customer to approve this estimate."),
    Chip(label="Compare to similar jobs",
         prompt="Is this estimate priced in line with similar jobs we've done?"),
]


@router.get("/chips", response_model=ChipsResponse)
def chips(
    entity_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if entity_type == "contact":
        return ChipsResponse(items=CONTACT_CHIPS)
    if entity_type == "estimate":
        return ChipsResponse(items=ESTIMATE_CHIPS)
    return ChipsResponse(items=GLOBAL_CHIPS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_ai_chat.py -k chips -v`
Expected: all 4 PASS.

- [ ] **Step 5: Run the full backend test suite**

Run: `cd backend && pytest -q`
Expected: 575+ pass (24+ new tests on top of 551). The pre-existing Saturday-only `test_dashboard_tasks_due_this_week` may fail; ignore it.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ai_chat.py backend/tests/test_ai_chat.py
git commit -m "Sprint 16c: GET /api/ai/chips with global/contact/estimate variants"
```

---

## Task 12: Frontend — install react-markdown + add API client

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/api/aiChat.js`

- [ ] **Step 1: Install dependencies**

```bash
cd frontend && npm install react-markdown remark-gfm
```

Expected: `package.json` and `package-lock.json` updated, no errors.

- [ ] **Step 2: Create the API client**

Write `frontend/src/api/aiChat.js`:

```javascript
import api from './client'

export const sendChat = async ({ conversationId, entityType, entityId, message }) => {
  const { data } = await api.post('/ai/chat', {
    conversation_id: conversationId,
    entity_type: entityType,
    entity_id: entityId,
    message,
  })
  return data
}

export const listConversations = async ({ entityType, entityId } = {}) => {
  const params = {}
  if (entityType) params.entity_type = entityType
  if (entityId !== undefined && entityId !== null) params.entity_id = entityId
  const { data } = await api.get('/ai/conversations', { params })
  return data
}

export const getConversationMessages = async (conversationId, { page = 1, perPage = 50 } = {}) => {
  const { data } = await api.get(`/ai/conversations/${conversationId}/messages`, {
    params: { page, per_page: perPage },
  })
  return data
}

export const deleteConversation = async (conversationId) => {
  await api.delete(`/ai/conversations/${conversationId}`)
}

export const getBriefing = async () => {
  const { data } = await api.get('/ai/briefing')
  return data
}

export const getBriefingNarrative = async () => {
  const { data } = await api.get('/ai/briefing/narrative')
  return data
}

export const getChips = async ({ entityType } = {}) => {
  const params = {}
  if (entityType) params.entity_type = entityType
  const { data } = await api.get('/ai/chips', { params })
  return data
}
```

- [ ] **Step 3: Verify the frontend still builds**

```bash
cd frontend && npm run build
```

Expected: build completes, no errors. (Imports of unused functions don't trigger warnings.)

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api/aiChat.js
git commit -m "Sprint 16c: install react-markdown + add aiChat API client"
```

---

## Task 13: Frontend — AIPanelContext provider

**Files:**
- Create: `frontend/src/context/AIPanelContext.jsx`

The drawer needs to be openable from anywhere, and its open/close + scoping state must persist across navigation. A React context is the simplest fit.

- [ ] **Step 1: Create the context**

Write `frontend/src/context/AIPanelContext.jsx`:

```jsx
import { createContext, useCallback, useContext, useState } from 'react'

const AIPanelContext = createContext(null)

export function AIPanelProvider({ children }) {
  const [open, setOpen] = useState(false)
  // mode: 'global' | 'entity'; entityType: 'contact' | 'estimate' | null
  const [mode, setMode] = useState('global')
  const [entityType, setEntityType] = useState(null)
  const [entityId, setEntityId] = useState(null)
  // Track the currently active conversation so opening the panel from
  // another page can resume it.
  const [activeConversationId, setActiveConversationId] = useState(null)

  const openPanel = useCallback((opts = {}) => {
    setMode(opts.mode || 'global')
    setEntityType(opts.entityType || null)
    setEntityId(opts.entityId ?? null)
    if (opts.conversationId !== undefined) {
      setActiveConversationId(opts.conversationId)
    }
    setOpen(true)
  }, [])

  const closePanel = useCallback(() => setOpen(false), [])

  const value = {
    open,
    mode,
    entityType,
    entityId,
    activeConversationId,
    setActiveConversationId,
    openPanel,
    closePanel,
  }
  return (
    <AIPanelContext.Provider value={value}>{children}</AIPanelContext.Provider>
  )
}

export function useAIPanel() {
  const ctx = useContext(AIPanelContext)
  if (!ctx) throw new Error('useAIPanel must be used inside <AIPanelProvider>')
  return ctx
}
```

- [ ] **Step 2: Wrap routes in the provider in `frontend/src/App.jsx`**

Find the existing provider stack (`ThemeProvider` → `AuthProvider` → `ToastProvider` → `BrowserRouter`). Add `AIPanelProvider` directly inside `ToastProvider`:

```jsx
import { AIPanelProvider } from './context/AIPanelContext'
// ...
<ToastProvider>
  <AIPanelProvider>
    <BrowserRouter>
      ...
    </BrowserRouter>
  </AIPanelProvider>
</ToastProvider>
```

- [ ] **Step 3: Verify the build**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/context/AIPanelContext.jsx frontend/src/App.jsx
git commit -m "Sprint 16c: AIPanelContext provider for global panel state"
```

---

## Task 14: Frontend — AIPanelButton reusable trigger

**Files:**
- Create: `frontend/src/components/AIPanelButton.jsx`

- [ ] **Step 1: Create the button**

Write `frontend/src/components/AIPanelButton.jsx`:

```jsx
import { Sparkles } from 'lucide-react'
import { useAIPanel } from '../context/AIPanelContext'

export default function AIPanelButton({
  mode = 'global',
  entityType = null,
  entityId = null,
  label = 'AI',
  variant = 'default',
}) {
  const { openPanel } = useAIPanel()
  const handleClick = () =>
    openPanel({ mode, entityType, entityId, conversationId: null })

  const baseClasses =
    'flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors'
  const variantClasses =
    variant === 'header'
      ? 'text-th-text-secondary hover:text-th-text bg-surface hover:bg-surface-hover'
      : 'text-brand-purple hover:text-brand-purple-text bg-brand-purple/10 hover:bg-brand-purple/20'

  return (
    <button
      onClick={handleClick}
      className={`${baseClasses} ${variantClasses}`}
      title={mode === 'global' ? 'Open AI assistant' : `AI chat about this ${entityType}`}
    >
      <Sparkles size={15} />
      {label}
    </button>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: builds successfully.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AIPanelButton.jsx
git commit -m "Sprint 16c: AIPanelButton trigger component"
```

---

## Task 15: Frontend — AIPanel drawer (skeleton + open/close)

**Files:**
- Create: `frontend/src/components/AIPanel.jsx`
- Modify: `frontend/src/App.jsx`

The drawer is mounted once at the app level so it persists across navigation. Render it after `<BrowserRouter>` content.

- [ ] **Step 1: Create the panel skeleton**

Write `frontend/src/components/AIPanel.jsx`:

```jsx
import { useEffect, useRef, useState } from 'react'
import { Loader2, Send, Sparkles, Sun, Trash2, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAIPanel } from '../context/AIPanelContext'
import { useToast } from '../context/ToastContext'
import {
  deleteConversation,
  getBriefingNarrative,
  getChips,
  getConversationMessages,
  listConversations,
  sendChat,
} from '../api/aiChat'

export default function AIPanel() {
  const {
    open,
    closePanel,
    mode,
    entityType,
    entityId,
    activeConversationId,
    setActiveConversationId,
  } = useAIPanel()
  const { addToast } = useToast()

  const [view, setView] = useState('list') // 'list' | 'chat'
  const [conversations, setConversations] = useState([])
  const [chips, setChips] = useState([])
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingList, setLoadingList] = useState(false)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [briefingLoading, setBriefingLoading] = useState(false)
  const messagesEndRef = useRef(null)

  // Reload conversation list + chips whenever the panel opens or scope changes.
  useEffect(() => {
    if (!open) return
    setLoadingList(true)
    Promise.all([
      listConversations(
        mode === 'entity' ? { entityType, entityId } : {},
      ),
      getChips(mode === 'entity' ? { entityType } : {}),
    ])
      .then(([convs, chipResp]) => {
        setConversations(convs.items || [])
        setChips(chipResp.items || [])
      })
      .catch(() => addToast('Failed to load conversations', 'error'))
      .finally(() => setLoadingList(false))
  }, [open, mode, entityType, entityId])

  // When activeConversationId changes, load its messages and switch to chat view.
  useEffect(() => {
    if (!open || !activeConversationId) {
      if (open && !activeConversationId) setView('list')
      return
    }
    setView('chat')
    setLoadingMessages(true)
    getConversationMessages(activeConversationId)
      .then((data) => setMessages(data.items || []))
      .catch(() => addToast('Failed to load messages', 'error'))
      .finally(() => setLoadingMessages(false))
  }, [open, activeConversationId])

  // Auto-scroll on new messages.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const startNew = () => {
    setActiveConversationId(null)
    setMessages([])
    setView('chat')
  }

  const send = async (text) => {
    const message = (text ?? input).trim()
    if (!message || sending) return
    setInput('')
    setSending(true)
    // Optimistic user message
    setMessages((prev) => [
      ...prev,
      {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: message,
        created_at: new Date().toISOString(),
      },
    ])
    try {
      const resp = await sendChat({
        conversationId: activeConversationId,
        entityType: mode === 'entity' ? entityType : null,
        entityId: mode === 'entity' ? entityId : null,
        message,
      })
      if (!activeConversationId) setActiveConversationId(resp.conversation_id)
      setMessages((prev) => [...prev, resp.message])
    } catch (err) {
      addToast(err?.response?.data?.detail || 'Send failed', 'error')
    } finally {
      setSending(false)
    }
  }

  const openBriefing = async () => {
    setBriefingLoading(true)
    setActiveConversationId(null)
    setMessages([])
    setView('chat')
    try {
      const data = await getBriefingNarrative()
      setMessages([
        {
          id: 'briefing-1',
          role: 'assistant',
          content: data.narrative || '_(no briefing returned)_',
          created_at: new Date().toISOString(),
        },
      ])
    } catch (err) {
      const detail = err?.response?.data?.detail
      const msg =
        err?.response?.status === 503
          ? `Morning briefing requires an LLM provider. ${detail || ''}`
          : detail || 'Briefing failed'
      setMessages([
        {
          id: 'briefing-err',
          role: 'assistant',
          content: msg,
          created_at: new Date().toISOString(),
        },
      ])
    } finally {
      setBriefingLoading(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await deleteConversation(id)
      setConversations((prev) => prev.filter((c) => c.id !== id))
      if (activeConversationId === id) {
        setActiveConversationId(null)
        setMessages([])
        setView('list')
      }
    } catch {
      addToast('Delete failed', 'error')
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 pointer-events-none">
      <div
        className="absolute inset-0 bg-black/30 pointer-events-auto"
        onClick={closePanel}
      />
      <aside
        className="absolute right-0 top-0 bottom-0 w-full sm:w-[420px] bg-surface border-l border-th-border shadow-2xl flex flex-col pointer-events-auto"
      >
        <header className="flex items-center justify-between px-4 py-3 border-b border-th-border">
          <div className="flex items-center gap-2 text-th-text">
            <Sparkles size={16} className="text-brand-purple" />
            <h3 className="text-base font-semibold">
              {mode === 'entity'
                ? `AI · ${entityType}`
                : 'AI Assistant'}
            </h3>
          </div>
          <div className="flex items-center gap-2">
            {view === 'chat' && (
              <button
                onClick={() => {
                  setActiveConversationId(null)
                  setMessages([])
                  setView('list')
                }}
                className="text-xs text-th-text-muted hover:text-th-text"
              >
                ← Back
              </button>
            )}
            <button
              onClick={closePanel}
              className="text-th-text-muted hover:text-th-text"
              aria-label="Close AI panel"
            >
              <X size={18} />
            </button>
          </div>
        </header>

        {view === 'list' && (
          <div className="flex-1 overflow-y-auto">
            {mode === 'global' && (
              <button
                onClick={openBriefing}
                disabled={briefingLoading}
                className="w-full flex items-center gap-2 px-4 py-3 text-sm text-th-text bg-brand-purple/10 hover:bg-brand-purple/20 transition-colors border-b border-th-border disabled:opacity-50"
              >
                {briefingLoading ? (
                  <Loader2 size={15} className="animate-spin" />
                ) : (
                  <Sun size={15} className="text-brand-purple" />
                )}
                Morning Briefing
              </button>
            )}

            <div className="px-4 py-3 border-b border-th-border">
              <button
                onClick={startNew}
                className="w-full text-sm bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text font-semibold px-3 py-2 rounded-lg"
              >
                Start a new conversation
              </button>
            </div>

            {loadingList && (
              <div className="p-4 text-sm text-th-text-muted">Loading…</div>
            )}
            {!loadingList && conversations.length === 0 && (
              <div className="p-6 text-center text-sm text-th-text-muted">
                No conversations yet. Use a chip below to start one.
              </div>
            )}
            {!loadingList && conversations.map((c) => (
              <div
                key={c.id}
                className="flex items-start justify-between gap-2 px-4 py-3 border-b border-th-border hover:bg-surface-hover cursor-pointer"
                onClick={() => setActiveConversationId(c.id)}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-th-text truncate">
                    {c.title || 'Untitled'}
                  </p>
                  {c.last_message_preview && (
                    <p className="text-xs text-th-text-muted truncate mt-0.5">
                      {c.last_message_preview}
                    </p>
                  )}
                  <p className="text-[10px] text-th-text-muted mt-1">
                    {c.message_count} messages ·{' '}
                    {new Date(c.updated_at).toLocaleString()}
                  </p>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(c.id)
                  }}
                  className="text-th-text-muted hover:text-red-400 p-1"
                  aria-label="Delete conversation"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}

            {chips.length > 0 && (
              <div className="px-4 py-3 border-t border-th-border">
                <p className="text-[11px] uppercase tracking-wide text-th-text-muted mb-2">
                  Quick prompts
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {chips.map((chip) => (
                    <button
                      key={chip.label}
                      onClick={() => {
                        startNew()
                        setTimeout(() => send(chip.prompt), 0)
                      }}
                      className="text-xs px-2.5 py-1 rounded-full bg-surface-hover hover:bg-brand-purple/20 text-th-text-secondary"
                    >
                      {chip.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {view === 'chat' && (
          <>
            <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
              {loadingMessages && (
                <p className="text-sm text-th-text-muted">Loading…</p>
              )}
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={
                    m.role === 'user'
                      ? 'flex justify-end'
                      : 'flex justify-start'
                  }
                >
                  <div
                    className={
                      m.role === 'user'
                        ? 'max-w-[85%] rounded-2xl rounded-br-sm px-3 py-2 text-sm bg-brand-purple/15 text-th-text'
                        : 'max-w-[85%] rounded-2xl rounded-bl-sm px-3 py-2 text-sm bg-surface-hover text-th-text prose prose-sm prose-invert max-w-none'
                    }
                  >
                    {m.role === 'assistant' ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {m.content || '_(empty response — is LLM_PROVIDER configured?)_'}
                      </ReactMarkdown>
                    ) : (
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    )}
                  </div>
                </div>
              ))}
              {sending && (
                <div className="flex justify-start">
                  <div className="bg-surface-hover rounded-2xl rounded-bl-sm px-3 py-2 text-sm text-th-text-muted">
                    <span className="inline-flex gap-1">
                      <span className="animate-bounce">·</span>
                      <span className="animate-bounce [animation-delay:0.15s]">·</span>
                      <span className="animate-bounce [animation-delay:0.3s]">·</span>
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {chips.length > 0 && messages.length === 0 && (
              <div className="px-4 pt-2 pb-1 flex flex-wrap gap-1.5">
                {chips.map((chip) => (
                  <button
                    key={chip.label}
                    onClick={() => send(chip.prompt)}
                    className="text-xs px-2.5 py-1 rounded-full bg-surface-hover hover:bg-brand-purple/20 text-th-text-secondary"
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            )}

            <form
              onSubmit={(e) => {
                e.preventDefault()
                send()
              }}
              className="border-t border-th-border p-3 flex items-center gap-2"
            >
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask anything…"
                disabled={sending}
                className="flex-1 bg-surface-hover text-th-text rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-brand-purple/50"
              />
              <button
                type="submit"
                disabled={!input.trim() || sending}
                className="bg-btn-primary-bg hover:bg-btn-primary-hover text-btn-primary-text rounded-lg p-2 disabled:opacity-50"
              >
                {sending ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Send size={16} />
                )}
              </button>
            </form>
          </>
        )}
      </aside>
    </div>
  )
}
```

- [ ] **Step 2: Mount the panel once at app level**

In `frontend/src/App.jsx`, import and render `<AIPanel />` inside `<AIPanelProvider>` (before or after `<BrowserRouter>` is fine — since it's `position: fixed`):

```jsx
import AIPanel from './components/AIPanel'
// ...
<AIPanelProvider>
  <BrowserRouter>
    <Routes>
      ...
    </Routes>
  </BrowserRouter>
  <AIPanel />
</AIPanelProvider>
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AIPanel.jsx frontend/src/App.jsx
git commit -m "Sprint 16c: AIPanel drawer with conversation list + chat view + briefing"
```

---

## Task 16: Frontend — wire AIPanelButton into Layout header

**Files:**
- Modify: `frontend/src/components/Layout.jsx`

- [ ] **Step 1: Add the button to the header bar**

Open `frontend/src/components/Layout.jsx`. Add the import:

```jsx
import AIPanelButton from './AIPanelButton'
```

In the header `<div className="sticky top-0 z-30 ...">` block (lines 33–44), append `<AIPanelButton mode="global" variant="header" />` after the `<GlobalSearch />` wrapper. The updated block:

```jsx
<div className="sticky top-0 z-30 bg-page-secondary px-4 md:px-6 py-3 flex items-center gap-3">
  <button
    onClick={() => setSidebarOpen(true)}
    className="lg:hidden p-2 text-th-text-secondary hover:text-th-text bg-surface rounded-lg transition-colors"
  >
    <Menu size={20} />
  </button>
  <div className="flex-1 max-w-xl">
    <GlobalSearch />
  </div>
  <AIPanelButton mode="global" variant="header" />
</div>
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build
```

Expected: builds successfully.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Layout.jsx
git commit -m "Sprint 16c: header AI Assistant button"
```

---

## Task 17: Frontend — replace AI Summary on ContactDetailPage

**Files:**
- Modify: `frontend/src/pages/ContactDetailPage.jsx`

- [ ] **Step 1: Replace the AI Summary button**

Open `frontend/src/pages/ContactDetailPage.jsx`. The current button is at lines 408–415 (inside the read-mode action toolbar).

Remove the `<button onClick={() => setShowAISummary(true)} ...>` block (8 lines including children). Replace with:

```jsx
<AIPanelButton
  mode="entity"
  entityType="contact"
  entityId={Number(id)}
  label="Chat"
/>
```

Add at the top of the file imports (after the existing import block):

```jsx
import AIPanelButton from '../components/AIPanelButton'
```

- [ ] **Step 2: Remove the AIOutputModal usage**

Delete the `<AIOutputModal isOpen={showAISummary} ... />` block at lines 842–848.

Remove the `showAISummary` state declaration (search the file: `useState` initialization referencing `showAISummary` and the `setShowAISummary` setter — there's exactly one).

Find and remove the `import AIOutputModal from '../components/AIOutputModal'` line (line 41) only if no other reference to `AIOutputModal` remains in the file. Verify with: `grep -n AIOutputModal frontend/src/pages/ContactDetailPage.jsx` — expect zero matches after the cleanup.

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: build succeeds, no warnings about unused imports.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ContactDetailPage.jsx
git commit -m "Sprint 16c: replace AI Summary modal with chat panel on ContactDetailPage"
```

---

## Task 18: Frontend — replace Generate Scope on EstimateDetailPage

**Files:**
- Modify: `frontend/src/pages/EstimateDetailPage.jsx`

- [ ] **Step 1: Replace the Generate Scope button**

Open `frontend/src/pages/EstimateDetailPage.jsx`. The current button is at lines 1424–1432.

Remove the `<button onClick={() => setShowAIScope(true)} ...>` block (~8 lines). Replace with:

```jsx
<AIPanelButton
  mode="entity"
  entityType="estimate"
  entityId={Number(id)}
  label="Chat"
/>
```

Add the import near the top of the file:

```jsx
import AIPanelButton from '../components/AIPanelButton'
```

- [ ] **Step 2: Remove the AIOutputModal usage**

Delete the `<AIOutputModal isOpen={showAIScope} ... />` block at lines 2229–2241.

Remove the `showAIScope` state declaration (search for `useState` referencing `showAIScope`).

Remove `import AIOutputModal from '../components/AIOutputModal'` (line 79) only if no other reference remains. Verify with: `grep -n AIOutputModal frontend/src/pages/EstimateDetailPage.jsx` — expect zero matches.

> Keep the `scope_of_work` display block and the "Clear" button untouched — the spec is explicit that scope-of-work display stays.

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build
```

Expected: builds clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EstimateDetailPage.jsx
git commit -m "Sprint 16c: replace Generate Scope modal with chat panel on EstimateDetailPage"
```

---

## Task 19: Final verification — full test suite + frontend build + manual smoke checks

**Files:** None (verification only)

- [ ] **Step 1: Run the full backend test suite**

```bash
cd backend && pytest -q
```

Expected: 575+ tests pass. (Pre-existing `test_dashboard_tasks_due_this_week` may fail on Saturdays; ignore per `CLAUDE.md` known issues.)

- [ ] **Step 2: Run the full frontend build**

```bash
cd frontend && npm run build
```

Expected: build succeeds with no errors.

- [ ] **Step 3: Confirm no regressions in modified pages — grep check**

```bash
grep -n "AIOutputModal" /Users/iantitus/Desktop/legacy-crm/frontend/src/pages/ContactDetailPage.jsx /Users/iantitus/Desktop/legacy-crm/frontend/src/pages/EstimateDetailPage.jsx
```

Expected: no output (zero matches in either file). The component file `AIOutputModal.jsx` itself remains untouched per spec.

- [ ] **Step 4: Confirm migration chain is intact**

```bash
ls /Users/iantitus/Desktop/legacy-crm/backend/alembic/versions/ | sort
```

Expected: ends with `0024_*`, `0025_*`, `0026_sprint16c_ai_conversations.py`.

- [ ] **Step 5: Manual smoke test (local Docker)**

```bash
cd /Users/iantitus/Desktop/legacy-crm && docker compose up --build -d
```

In a browser at http://localhost:5173:
1. Log in.
2. Click the AI button in the header → drawer opens in global mode.
3. Click "Start a new conversation", type "test", press send → assistant message appears (will be empty under LLM_PROVIDER=none, with the inline note rendered as italic markdown).
4. Click a quick-action chip → new conversation begins, prompt sends.
5. Navigate to a contact → click "Chat" → drawer opens in entity mode for that contact, only that contact's conversations show.
6. Navigate to an estimate → click "Chat" → drawer opens in entity mode for that estimate.
7. Close the drawer, navigate between pages, reopen the drawer → previous mode + active conversation are preserved.
8. From global mode, click "Morning Briefing" → expect a 503-detail message inline (because LLM_PROVIDER=none locally by default).
9. Set `LLM_PROVIDER=ollama` in `.env`, restart backend, repeat step 8 → expect a generated narrative.

Document any issues in the commit message; do not auto-fix.

- [ ] **Step 6: Commit a marker note (optional)**

If everything passes, no further commit is needed. The work is on `main` ready for `./scripts/deploy.sh`.

---

## Self-Review Notes

- Spec coverage: every section of the spec maps to at least one task — migration (1), models (2), schemas (3), prompts (4), service start/continue (5), service briefing (6), router chat (7), router conversations list (8), router messages + delete (9), router briefing/narrative (10), router chips (11), frontend client (12), context (13), button (14), panel (15), header (16), contact page (17), estimate page (18), verification (19).
- Anti-patterns from spec: each respected — provider abstraction is the single LLM call site (`get_provider()`), `briefing` does not require LLM (no `NoneProvider` short-circuit), no auto-fire on page load (panel opens only on click, briefing endpoint runs only when user clicks the chip), no full snapshots in `ai_messages` (only message text + minimal metadata), single conversations table (entity_type/entity_id columns), existing AI endpoints untouched.
- Verification checklist from spec: items 1–4 are covered by Task 19. Items 5–12 (manual UI checks) are covered by Task 19 Step 5.
- Type consistency: `String(36)` UUIDs everywhere, `JSON()` not JSONB (cross-DB), `message_metadata` Python attribute is mapped to the `message_metadata` column to avoid SQLAlchemy's reserved `metadata` clash, all timestamps `DateTime(timezone=True)`.
- No placeholders detected. Each step has full code or exact commands. Test code is real, not stubbed.
