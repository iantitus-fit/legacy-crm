# Legacy CRM — Sprint 16b Spec: AI Architecture (Provider Abstraction + Event Triggers)

**Date:** April 29, 2026
**Priority:** HIGH — core differentiator, positions CRM above every competitor at this price point
**Estimated build time:** 60-90 min (AI-assisted)
**Dependencies:** None — builds alongside existing features without modifying them

---

## Why This Sprint

Every major CRM (Salesforce, HubSpot, AccuLynx) is adding AI features priced at $50-220/user/month on top of base licensing. These features are generic: lead scoring, email generation, forecasting. A 15-person roofing company will never use 90% of them.

This sprint builds the AI layer for Legacy CRM — specific, useful automations configured for how roofing contractors actually work. The architecture is trigger-based (CRM events fire LLM calls) with a provider abstraction layer (swap between Claude API and Ollama local models via environment variable). This means:

- **Zero cost during development/testing** — Ollama runs locally, no API tokens
- **Pennies per use in production** — Claude API at CRM volumes is $2-5/month, not $200/user/month
- **No vendor lock-in** — swap models by changing one env var
- **Enterprise function at SMB price** — cherry-picked AI features that matter for roofing, nothing that doesn't

---

## Architecture Overview

```
CRM Event (e.g., lead_created, estimate_approved)
    ↓
Event Dispatcher (checks if AI action is configured for this event)
    ↓
AI Service (provider abstraction layer)
    ↓
┌─────────────────────────────────────┐
│  LLM_PROVIDER=claude  →  Claude API │
│  LLM_PROVIDER=ollama  →  Ollama    │
│  LLM_PROVIDER=none    →  Skip      │
└─────────────────────────────────────┘
    ↓
Output Handler (write draft email, create task, update field, send notification)
```

---

## Part 1: Provider Abstraction Layer

### New file: app/services/ai_provider.py

A single interface that wraps LLM calls. All AI features call this service — never the provider directly.

**Environment variables:**
```
LLM_PROVIDER=ollama           # "claude", "ollama", or "none"
LLM_MODEL=qwen3:8b            # Model identifier (provider-specific)
CLAUDE_API_KEY=sk-ant-...     # Only needed when LLM_PROVIDER=claude
OLLAMA_BASE_URL=http://localhost:11434  # Only needed when LLM_PROVIDER=ollama
AI_ENABLED=true               # Global kill switch
```

**Interface:**
```python
class AIProvider:
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        response_format: str = "text"  # "text" or "json"
    ) -> AIResponse:
        ...

class AIResponse:
    content: str          # The generated text
    provider: str         # "claude", "ollama", or "none"
    model: str            # Model identifier used
    tokens_used: int      # For cost tracking
    duration_ms: int      # For performance monitoring
    success: bool         # Did the call succeed
    error: str | None     # Error message if failed
```

**Provider implementations:**

**ClaudeProvider:**
- Uses `anthropic` Python SDK
- Model: configurable, defaults to `claude-sonnet-4-20250514`
- Handles rate limiting with exponential backoff
- Logs token usage for cost tracking

**OllamaProvider:**
- Uses HTTP requests to Ollama's OpenAI-compatible API at `{OLLAMA_BASE_URL}/v1/chat/completions`
- Model: configurable, defaults to `qwen3:8b`
- No auth required (local)
- Falls back gracefully if Ollama isn't running (logs warning, returns empty response)

**NoneProvider:**
- Returns empty response immediately
- For production environments where AI is disabled or testing without any LLM
- Logs that AI was requested but skipped

**Graceful degradation is critical.** If the LLM call fails for any reason (provider down, timeout, bad response), the CRM continues to function normally. AI features are enhancements, never blockers. Every AI call is wrapped in try/except and logged.

---

## Part 2: Event Trigger System

### New file: app/services/ai_events.py

A lightweight event system that fires AI actions when CRM events occur.

**Event types (start with these 6):**

| Event | Fires When | AI Action |
|-------|-----------|-----------|
| `lead_created` | New contact added with pipeline_id = Leads | Draft a welcome/follow-up text or email |
| `follow_up_overdue` | Contact in Leads/Sales pipeline with no activity for 48+ hours | Draft a follow-up message |
| `estimate_approved` | Customer approves estimate via portal | Generate job summary for crew briefing |
| `job_completed` | Estimate moved to "Complete" stage | Draft a review request email (3-day delay) |
| `estimate_created` | New estimate created with line items | Generate scope-of-work description |
| `pre_visit_summary` | User clicks "AI Summary" on a contact | Summarize all notes, estimates, and communication history |

### Event dispatcher

```python
class AIEventDispatcher:
    async def dispatch(self, event_type: str, context: dict) -> AIActionResult | None:
        """
        Check if an AI action is configured for this event.
        If yes, build the prompt with CRM context and call the provider.
        If no, return None.
        """
```

**Context dict** contains all relevant CRM data for that event. For example, `lead_created` includes:
```python
{
    "event": "lead_created",
    "contact": {
        "name": "John Smith",
        "phone": "(765) 555-0101",
        "email": "john@email.com",
        "address": "1420 E Sycamore St, Kokomo, IN",
        "lead_source": "Angi",
        "notes": "Interested in full roof replacement"
    },
    "company": {
        "name": "Legacy Roofing & Exteriors",
        "phone": "(765) 555-0101",
        "services": ["roofing", "siding", "gutters", "painting"]
    }
}
```

### Prompt templates

**New file: app/services/ai_prompts.py**

Each event type has a prompt template. Templates are separated from code so they can be iterated on without changing logic.

```python
PROMPTS = {
    "lead_created": {
        "system": """You are a helpful assistant for {company_name}, a roofing and exteriors company in Kokomo, Indiana. 
You draft short, friendly follow-up messages to new leads. 
Keep the tone professional but warm — like a local business owner talking to a neighbor.
Never use emojis. Never use exclamation points more than once.
Always mention the specific service they're interested in if known.
Always include the company phone number.
Messages should be 2-4 sentences maximum.""",
        
        "user": """Draft a follow-up message for this new lead:

Name: {contact_name}
Lead Source: {lead_source}
Notes: {contact_notes}
Service Interest: {service_interest}

Company phone: {company_phone}"""
    },
    
    "follow_up_overdue": {
        "system": """You are a helpful assistant for {company_name}. 
Draft a gentle follow-up message for a lead who hasn't been contacted in a while.
Keep it short (2-3 sentences), friendly, no pressure.
Reference their original interest if known.
Include the company phone number.""",
        
        "user": """This lead hasn't been contacted in {days_since_activity} days:

Name: {contact_name}
Original Interest: {contact_notes}
Lead Source: {lead_source}
Last Activity: {last_activity_date}

Draft a follow-up message."""
    },

    "estimate_created": {
        "system": """You are a helpful assistant for a roofing and exteriors company.
Generate a professional scope-of-work description based on the estimate line items.
Write in clear, non-technical language that a homeowner would understand.
Be specific about what's included. 
3-5 sentences maximum.""",

        "user": """Generate a scope-of-work description for this estimate:

Customer: {contact_name}
Address: {contact_address}
Line Items:
{line_items_formatted}

Total: {estimate_total}"""
    },

    "estimate_approved": {
        "system": """You are a helpful assistant for a roofing company.
Generate a brief internal job summary for the crew.
Include: what work is being done, the address, any special notes, and the total value.
Keep it factual and direct — this is for the crew, not the customer.
5-8 sentences maximum.""",

        "user": """An estimate was just approved. Generate a crew briefing:

Customer: {contact_name}
Phone: {contact_phone}
Address: {contact_address}
Approved Estimate: {estimate_name}
Line Items:
{line_items_formatted}
Total: {estimate_total}
Customer Notes: {customer_notes}
Internal Notes: {internal_notes}"""
    },

    "job_completed": {
        "system": """You are a helpful assistant for {company_name}.
Draft a short, warm review request email to send 3 days after job completion.
Thank them for their business. Mention the specific work done.
Include a direct link to leave a Google review.
Keep it personal — not corporate. 3-4 sentences maximum.
Never use emojis.""",

        "user": """Draft a review request email:

Customer: {contact_name}
Work Completed: {work_description}
Completion Date: {completion_date}
Google Review Link: {google_review_link}"""
    },

    "pre_visit_summary": {
        "system": """You are a helpful assistant for a roofing company.
Summarize all available information about this customer into a brief pre-visit briefing.
Include: who they are, what they need, any past work or estimates, key notes, and anything the person visiting should know.
Write it as if you're briefing a colleague before they knock on the door.
Keep it to 1 short paragraph.""",

        "user": """Summarize this customer for a pre-visit briefing:

Name: {contact_name}
Phone: {contact_phone}
Email: {contact_email}
Address: {full_address}
Lead Source: {lead_source}
Client Type: {client_type}

Estimates:
{estimates_summary}

Notes:
{all_notes}

Activity History:
{activity_summary}"""
    }
}
```

---

## Part 3: AI Action Results Storage

### Database Changes

**Migration 0025: ai_actions**

```
ai_actions table (new):
├── id (UUID, PK)
├── event_type (string, index) — "lead_created", "follow_up_overdue", etc.
├── contact_id (FK → contacts, nullable)
├── estimate_id (FK → estimates, nullable)
├── provider (string) — "claude", "ollama", "none"
├── model (string) — model identifier used
├── system_prompt (text) — stored for audit/debugging
├── user_prompt (text) — stored for audit/debugging
├── output (text) — the generated content
├── tokens_used (int, nullable)
├── duration_ms (int, nullable)
├── status (string) — "completed", "failed", "pending", "dismissed"
├── used_at (timestamp, nullable) — when a user actually used the output (sent email, applied description)
├── created_at (timestamp)
├── created_by (FK → users, nullable)
```

This table serves three purposes:
1. **Audit trail** — every AI generation is logged with full prompt and output
2. **Cost tracking** — token usage per action, per provider
3. **Quality iteration** — review outputs to improve prompts over time

---

## Part 4: API Endpoints

### New router: app/routers/ai_actions.py

**POST /api/ai/generate**
Manual trigger — user clicks a button to generate AI content for a specific purpose.

Request:
```json
{
    "event_type": "pre_visit_summary",
    "contact_id": "uuid...",
    "estimate_id": "uuid..."  // optional, depends on event type
}
```

Response:
```json
{
    "id": "uuid...",
    "event_type": "pre_visit_summary",
    "output": "John Smith at 1420 E Sycamore St is a residential lead from Angi who's interested in a full roof replacement. No estimates created yet. He was imported via CSV on April 29. This is a first visit — introduce the company and inspect the roof before discussing pricing.",
    "provider": "ollama",
    "model": "qwen3:8b",
    "tokens_used": 287,
    "duration_ms": 1420
}
```

**POST /api/ai/actions/{action_id}/use**
Mark an AI-generated output as "used" (user sent the email, applied the description, etc.)

**POST /api/ai/actions/{action_id}/dismiss**
Mark an AI-generated output as "dismissed" (user didn't like it, wrote their own)

**GET /api/ai/actions?contact_id=...&event_type=...**
List AI actions for a contact or by event type. Paginated.

**GET /api/ai/stats**
Dashboard-level stats: total actions generated, total tokens used, total used vs dismissed, breakdown by event type. Useful for tracking AI adoption and cost.

---

## Part 5: Frontend Integration (Minimal for This Sprint)

This sprint focuses on the backend architecture and one visible frontend touchpoint. Full UI integration (inline draft editors, auto-send flows, dashboard AI widget) comes in a follow-up sprint.

### Contact Detail / Client Profile Page

**New button: "AI Summary"** — appears in the contact header area. Click triggers `POST /api/ai/generate` with `event_type: pre_visit_summary`. Output displays in a modal or expandable panel on the contact page. User can copy the text or dismiss it.

This is the simplest, most demo-able AI feature and it exercises the full stack: button click → API → provider abstraction → LLM call → response display.

### Estimate Detail Page

**New button: "Generate Scope of Work"** — appears near the estimate description/notes area. Click triggers `POST /api/ai/generate` with `event_type: estimate_created`. Output displays in a modal. User can "Apply to Estimate" (writes it to the estimate's scope of work field) or dismiss.

---

## Part 6: Background Event Hooks (Wire-Up Points)

These are NOT background workers or cron jobs in this sprint. These are hook points in existing code where AI generation is triggered asynchronously after the primary action completes. The AI call happens fire-and-forget — the user's action (creating a lead, approving an estimate) completes immediately regardless of whether the AI call succeeds.

**Hook points to wire:**

1. **Contact creation** (when pipeline_id = Leads pipeline): after successful contact create, dispatch `lead_created` event
2. **Estimate approval** (portal endpoint): after successful approval, dispatch `estimate_approved` event
3. **Pipeline stage change to "Complete"**: after stage update, dispatch `job_completed` event

The outputs are stored in `ai_actions` table and surfaced on the relevant contact/estimate pages. The user sees "AI drafted a follow-up for this lead" and can review, use, edit, or dismiss it.

`follow_up_overdue` requires a periodic check (daily scan of contacts in Leads/Sales pipelines with no activity in 48+ hours). This can be a management command run via cron or Azure scheduled task. Defer the scheduler setup to next sprint — for now, build the endpoint and logic so it can be triggered manually or via `python manage.py check_overdue_followups`.

---

## Test Requirements

| Test | Description |
|------|-------------|
| test_provider_claude_init | Claude provider initializes with API key |
| test_provider_ollama_init | Ollama provider initializes with base URL |
| test_provider_none_returns_empty | None provider returns empty response immediately |
| test_provider_selection_from_env | Correct provider selected based on LLM_PROVIDER env var |
| test_provider_graceful_failure | Failed LLM call returns error response, doesn't raise |
| test_generate_endpoint_auth | Requires authentication |
| test_generate_pre_visit_summary | Generates summary for a contact (mock provider) |
| test_generate_scope_of_work | Generates scope for an estimate (mock provider) |
| test_generate_follow_up_draft | Generates follow-up for a lead (mock provider) |
| test_generate_stores_action | AI action stored in database with full prompt and output |
| test_use_action | Marking action as "used" updates status and timestamp |
| test_dismiss_action | Marking action as "dismissed" updates status |
| test_list_actions_by_contact | Filter actions by contact_id |
| test_list_actions_by_event | Filter actions by event_type |
| test_stats_endpoint | Returns token usage and action counts |
| test_prompt_template_rendering | Templates render with context variables correctly |
| test_lead_created_hook | Contact creation in Leads pipeline triggers AI generation |
| test_estimate_approved_hook | Estimate approval triggers AI generation |
| test_ai_disabled_skips | AI_ENABLED=false skips all AI actions |
| test_provider_timeout | Provider returns error on timeout, doesn't block |

20 tests minimum. All tests use a mock provider (no real LLM calls in tests).

---

## Anti-Patterns

- Do NOT call LLM providers directly from routers — always go through AIProvider abstraction
- Do NOT block user actions on AI responses — all AI calls are async/fire-and-forget for hooks, or clearly user-initiated for manual triggers
- Do NOT store API keys in code — environment variables only
- Do NOT make AI features required — every feature must degrade gracefully when AI_ENABLED=false or provider is unavailable
- Do NOT send AI-generated content to customers automatically — all output is a draft that requires human review before sending
- Do NOT import anthropic SDK at module level — conditional import based on provider selection to avoid import errors when SDK isn't installed

---

## Environment Setup Notes

**For local development with Ollama:**
```bash
# Install Ollama (Mac)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull qwen3:8b

# Set env vars in .env
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://host.docker.internal:11434
AI_ENABLED=true
```

Note: Inside Docker, `localhost` refers to the container, not the host machine. Use `host.docker.internal` to reach Ollama running on the Mac.

**For production (Azure):**
```bash
LLM_PROVIDER=claude
LLM_MODEL=claude-sonnet-4-20250514
CLAUDE_API_KEY=sk-ant-...
AI_ENABLED=true
```

**For testing (CI/test suite):**
```bash
LLM_PROVIDER=none
AI_ENABLED=true  # Tests run with mock provider
```

---

## Verification Checklist

1. Set LLM_PROVIDER=ollama, pull qwen3:8b, click "AI Summary" on a contact → see generated summary
2. Set LLM_PROVIDER=none → click "AI Summary" → returns empty/placeholder gracefully
3. Set AI_ENABLED=false → AI buttons still visible but return "AI is disabled" message
4. Click "Generate Scope of Work" on an estimate with line items → see generated description
5. Apply scope of work to estimate → text saved to estimate
6. Create a new lead → ai_actions table has a draft follow-up stored
7. Check /api/ai/stats → see action count and token usage
8. All 489+ existing tests still pass
9. 20+ new tests pass
10. Ollama not running → CRM continues to work, AI features show "unavailable" gracefully

---

## Context Line for Claude Code Session

```
Read CLAUDE.md. Sprints 1–16a complete. 522 tests passing, 0 errors. Latest migration: 0024. Production deployed to Azure. Deploy via ./scripts/deploy.sh. Build Sprint 16b: AI Architecture with provider abstraction and event triggers. Spec: legacy_crm_sprint16b_spec.md. IMPORTANT: All tests must use mock AI provider — no real LLM calls in tests. Set LLM_PROVIDER=none in test environment.
```
