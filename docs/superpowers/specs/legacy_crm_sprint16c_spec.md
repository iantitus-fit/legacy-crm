# Sprint 16c — Conversational AI Panel + Morning Briefing

## Claude Code Prompt

```
Read CLAUDE.md. Sprints 1–16b complete. 551 tests passing, 0 errors. Latest migration: 0025. Production deployed to Azure. Deploy via ./scripts/deploy.sh. Ollama installed locally (qwen3:8b). AI architecture live with provider abstraction (LLM_PROVIDER env var).

Sprint 16c: Build a conversational AI panel with persistent chat history and a morning briefing summary endpoint. This upgrades the current one-shot AI modals (AIOutputModal.jsx) to a full conversational interface with follow-up capability, and adds a structured data endpoint that external tools (HyperAgent) can consume.

## CONTEXT

The AI provider abstraction from Sprint 16b is already in place:
- app/services/ai_provider.py — NoneProvider, MockProvider, OllamaProvider, ClaudeProvider
- app/services/ai_prompts.py — 6 prompt templates
- app/services/ai_events.py — context builders + dispatch
- 5 existing AI endpoints: POST /api/ai/generate, POST/GET ai/actions, etc.
- Migration 0025: ai_actions table + estimates.scope_of_work column

The current AI UX is two buttons: "AI Summary" on Contact Detail (pre_visit_summary) and "Generate Scope" on Estimate Detail (scope of work). Both open AIOutputModal.jsx which fires a one-shot generation. No conversation history, no follow-up, no cross-customer view.

## NEW FILES

### Backend

**Migration 0026** — `ai_conversations` and `ai_messages` tables:
```sql
-- ai_conversations
id: UUID PK
user_id: FK → users.id (NOT NULL)
entity_type: VARCHAR(50) NULLABLE — 'contact', 'estimate', or NULL for global/briefing
entity_id: UUID NULLABLE — FK to the relevant entity, NULL for global
title: VARCHAR(255) NULLABLE — auto-generated from first message or chip label
created_at: TIMESTAMP
updated_at: TIMESTAMP

-- ai_messages
id: UUID PK
conversation_id: FK → ai_conversations.id (NOT NULL, CASCADE DELETE)
role: VARCHAR(20) NOT NULL — 'user', 'assistant', 'system'
content: TEXT NOT NULL
metadata: JSONB NULLABLE — for token counts, model used, generation time, etc.
created_at: TIMESTAMP
```

**app/models/ai_conversation.py** — SQLAlchemy models for both tables.

**app/services/ai_chat.py** — Conversational AI service:
- `start_conversation(user_id, entity_type=None, entity_id=None, initial_message=None)` → creates conversation, assembles context, sends to provider, persists both messages, returns assistant response
- `continue_conversation(conversation_id, user_message)` → loads conversation history (last 20 messages), assembles entity context if scoped, sends full history to provider, persists both messages, returns assistant response
- `get_briefing_context(user_id)` → queries across ALL entities for the current user's company and returns structured JSON (NOT a generated LLM response — this is raw data for the morning briefing). Sections:
  - `overdue_followups` — contacts with no note/activity in 3+ days that have open estimates
  - `unsigned_estimates` — estimates with status 'sent' grouped by: viewed_not_signed (warm), not_viewed (cold), aging_over_5_days (red flag)
  - `overdue_invoices` — invoices past due date, sorted by days overdue desc
  - `unpaid_invoices` — invoices not yet due but still open
  - `upcoming_appointments` — calendar events in next 7 days
  - `tasks_due` — tasks due today or overdue, sorted by due_date
  - `recent_customer_actions` — portal views, signature approvals, payments from last 24 hours (query customer_portal_views if exists, else estimate status changes + payment records)
  - `overnight_ai_actions` — ai_actions created since last 7am ET
  - `stale_leads` — contacts in leads pipeline with no activity in 14+ days, sorted by estimate value desc
  - `summary_counts` — total counts for each section for the KPI strip
- All date/time boundaries computed in America/Indiana/Indianapolis timezone
- Returns plain Python dict, no LLM involved — this is a data assembly endpoint

**app/routers/ai_chat.py** — New router with these endpoints:
- `POST /api/ai/chat` — body: `{conversation_id?: UUID, entity_type?: str, entity_id?: UUID, message: str}`. If conversation_id provided, continues existing conversation. If not, starts new one with optional entity scoping. Returns `{conversation_id, message: {id, role, content, created_at}, entity_type, entity_id}`.
- `GET /api/ai/conversations` — list conversations for current user, optional `?entity_type=&entity_id=` filter. Returns most recent first with last message preview and message count.
- `GET /api/ai/conversations/{id}/messages` — full message history for a conversation, paginated (default 50, max 100).
- `DELETE /api/ai/conversations/{id}` — soft delete or hard delete conversation.
- `GET /api/ai/briefing` — returns the structured briefing data for the current user. No LLM call. This is the endpoint HyperAgent will consume. Requires auth token.
- `GET /api/ai/briefing/narrative` — same data but passed through the LLM provider to generate a natural-language morning briefing summary. This is what the in-CRM panel uses when the user clicks "Morning Briefing".
- `GET /api/ai/chips` — returns available quick-action chips based on context. Global chips always available: "What needs attention today?", "Overdue follow-ups", "Unpaid invoices", "This week's schedule", "Draft a follow-up for...". Per-contact chips when entity_type=contact: "Summarize this customer", "Draft follow-up email", "What's the history here?", "Generate scope of work". Per-estimate chips when entity_type=estimate: "Explain this estimate", "Draft approval follow-up", "Compare to similar jobs".

**app/services/ai_prompts.py** — ADD new prompt templates (do NOT remove existing ones):
- `morning_briefing` — system prompt for generating narrative briefing from structured data
- `conversation_system` — system prompt for ongoing conversations, includes CRM context instructions
- `conversation_with_entity` — system prompt variant that includes specific entity context

### Frontend

**src/components/AIPanel.jsx** — Sliding drawer component:
- Triggered by a persistent button in the app header (brain/sparkle icon + "AI" label)
- Also triggered by a "Chat" button on Contact Detail and Estimate Detail pages (replaces current "AI Summary" button)
- Two modes:
  1. **Global mode** (from header): shows conversation list + morning briefing button at top. Clicking morning briefing starts a briefing conversation. Quick-action chips for global context.
  2. **Entity mode** (from contact/estimate detail): shows conversations scoped to that entity + quick-action chips for that entity type. If no conversations exist, shows chips to start one.
- Chat interface:
  - Scrollable message list with user/assistant message bubbles
  - Assistant messages render markdown (use react-markdown or similar — check what's already in package.json)
  - Loading state: typing indicator dots while waiting for response
  - Input field with send button at bottom
  - Quick-action chips displayed above the input when starting a new conversation or when the conversation is empty
  - Clicking a chip sends it as the user message
- Conversation list:
  - Shows title, last message preview (truncated), timestamp, message count
  - Click to open conversation
  - New conversation button
- Drawer slides in from the right, takes ~400px width on desktop, full-width on mobile
- Close button (X) in header
- Drawer state persists during navigation (doesn't close when changing pages)

**Modify src/components/Layout.jsx** (or wherever the app header lives):
- Add the AI panel trigger button to the header bar, right side

**Modify src/pages/ContactDetailPage.jsx**:
- Replace "AI Summary" button with "Chat" button that opens AIPanel in entity mode (entity_type='contact', entity_id=contact.id)
- Remove AIOutputModal import/usage for this page

**Modify src/pages/EstimateDetailPage.jsx**:
- Replace "Generate Scope" button with "Chat" button that opens AIPanel in entity mode (entity_type='estimate', entity_id=estimate.id)  
- Keep the scope_of_work display and clear button — the chat can still generate scope, but it does so through conversation
- Remove AIOutputModal import/usage for this page

**Do NOT delete AIOutputModal.jsx** — it may still be used elsewhere. Just remove the imports from the two pages above.

## MODIFIED FILES

- `backend/app/main.py` — register ai_chat router
- `backend/app/models/__init__.py` — import new models
- `backend/app/services/ai_prompts.py` — add new templates (keep existing)
- `frontend/src/components/Layout.jsx` — add AI panel button to header
- `frontend/src/pages/ContactDetailPage.jsx` — swap AI Summary button for Chat button
- `frontend/src/pages/EstimateDetailPage.jsx` — swap Generate Scope button for Chat button
- `frontend/src/App.jsx` — no new routes needed (panel is a drawer, not a page)

## REFERENCE FILES (read but don't modify)

- `backend/app/services/ai_provider.py` — use get_provider() for all LLM calls
- `backend/app/services/ai_events.py` — reuse context builders (build_contact_context, build_estimate_context, etc.)
- `backend/app/routers/ai.py` — existing AI endpoints, don't duplicate
- `backend/app/models/ai_action.py` — existing AI action model

## ANTI-PATTERNS

- Do NOT bypass the provider abstraction. All LLM calls go through get_provider().generate().
- Do NOT make the briefing endpoint depend on LLM being configured. GET /api/ai/briefing returns structured data regardless of LLM_PROVIDER setting. Only GET /api/ai/briefing/narrative requires LLM.
- Do NOT auto-fire AI calls on page load. All AI interactions are user-initiated (click button, send message, click chip).
- Do NOT store full entity snapshots in ai_messages. Store the message text only. Context is assembled fresh on each call from live DB data.
- Do NOT create separate conversation tables per entity type. One ai_conversations table with entity_type/entity_id columns handles all scoping.
- Do NOT break the existing AI endpoints. The /api/ai/generate, /api/ai/actions, etc. must continue working.

## VERIFICATION CHECKLIST

1. Migration 0026 applies cleanly on top of 0025
2. All existing 551 tests still pass
3. New tests cover:
   - Create conversation (global and entity-scoped)
   - Send message and get response (with MockProvider)
   - Continue conversation with history
   - List conversations filtered by entity
   - Get messages for a conversation
   - Delete conversation
   - Briefing endpoint returns structured data with correct sections
   - Briefing endpoint works with LLM_PROVIDER=none (returns data, not 503)
   - Narrative briefing endpoint returns 503 when LLM_PROVIDER=none
   - Chips endpoint returns correct chips for global vs contact vs estimate context
4. Frontend builds clean with no warnings
5. AI panel opens from header button (global mode)
6. AI panel opens from Contact Detail (entity mode, scoped to contact)
7. AI panel opens from Estimate Detail (entity mode, scoped to estimate)
8. Quick-action chips display and send correctly
9. Conversation persists — close panel, reopen, history is there
10. Morning briefing chip triggers briefing generation
11. Panel stays open during page navigation
12. Responsive on mobile (full-width drawer)
```

## Notes for Ian

- **Test with Ollama locally first.** Set LLM_PROVIDER=ollama and run conversations against qwen3:8b. The conversational context will be heavier than one-shot generations — watch for response times over 30 seconds and consider truncating conversation history if needed.
- **The /api/ai/briefing endpoint is what HyperAgent will call.** Once this ships, you wire HyperAgent's fetch_data.py to hit this endpoint with a Bearer token instead of returning mock data. One endpoint swap and the morning briefing is live with real CRM data.
- **Deploy to production with same LLM_PROVIDER=none.** The panel will be visible, chips will render, but sending a message will return the "Configure LLM_PROVIDER" message. The briefing DATA endpoint works regardless — it's just SQL queries, no LLM needed.
- **This is a big sprint.** If Claude Code struggles with the full scope, split it: 16c-1 (backend: migration + models + services + endpoints + tests) and 16c-2 (frontend: AIPanel + header integration + page modifications). Backend first, verify tests pass, then frontend.
