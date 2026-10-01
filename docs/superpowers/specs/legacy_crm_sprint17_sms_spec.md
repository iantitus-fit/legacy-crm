# Sprint 17 — SMS/Text Messaging + Auto-Response

## Claude Code Prompt

```
Read CLAUDE.md and PRD.md. Sprints 1–16d are complete. 654 tests passing. Latest migration: 0026. Production deployed to Azure. Deploy via ./scripts/deploy.sh.

Sprint 17: Build SMS text messaging with Twilio integration — send/receive texts from inside the CRM, auto-response on new lead creation, and a conversation view on the contact detail page. This is a 3 sub-sprint build.
```

---

## Context

Legacy Roofing currently has ZERO automated lead response. All follow-up is manual phone calls. Industry data shows 75% of roofing leads arrive after hours, and speed-to-lead (responding within minutes) is the #1 driver of close rates. AccuLynx's equivalent add-on (Hatch) costs $300-500/month. This sprint builds the same capability natively with Twilio at ~$10-15/month in usage fees.

### Existing Infrastructure
- SMTP email sending already works (briefing sender, estimate emails, payment receipts)
- Contact model has `phone` field populated for 219 imported contacts
- Contact model has `lead_source` field
- Contacts have `pipeline_id` and `stage_id` for pipeline positioning
- Notification pattern exists: fire-and-forget email on CRM events (estimate sent, payment received, etc.)
- AI panel (Sprint 16c) has conversation pattern with `ai_conversations` / `ai_messages` tables — SMS conversation UI can follow a similar pattern
- Latest migration: 0026 (ai_conversations + ai_messages)

### Phone Number Format
AccuLynx data has phone numbers in mixed formats: "(765) 555-0181", "765-555-0181", "7655550181", etc. The Twilio API requires E.164 format (+1XXXXXXXXXX). All phone formatting/normalization must happen in the service layer, not at the database level — keep the stored format human-readable, convert to E.164 only when calling Twilio.

---

## Sub-Sprint 17a: Data Model + Twilio Service Layer

### Migration 0027 — `sms_messages` table + `sms_config` table

```sql
-- sms_messages: stores all inbound and outbound SMS
CREATE TABLE sms_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    direction VARCHAR(10) NOT NULL,        -- 'inbound' or 'outbound'
    body TEXT NOT NULL,
    from_number VARCHAR(20) NOT NULL,       -- E.164 format
    to_number VARCHAR(20) NOT NULL,         -- E.164 format
    twilio_sid VARCHAR(64) NULLABLE,        -- Twilio message SID for tracking
    status VARCHAR(20) NOT NULL DEFAULT 'queued',  -- queued, sent, delivered, failed, received
    status_detail TEXT NULLABLE,            -- error message if failed
    triggered_by VARCHAR(30) NULLABLE,      -- 'manual', 'auto_new_lead', 'auto_estimate_sent', etc.
    sent_by UUID NULLABLE REFERENCES users(id), -- NULL for inbound and system auto-sends
    read_at TIMESTAMP NULLABLE,            -- when an inbound message was read in CRM
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sms_messages_contact_id ON sms_messages(contact_id);
CREATE INDEX idx_sms_messages_created_at ON sms_messages(created_at);
CREATE INDEX idx_sms_messages_direction ON sms_messages(direction);

-- sms_config: company-level SMS settings (single row for now, multi-tenant ready)
CREATE TABLE sms_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    twilio_account_sid VARCHAR(64) NOT NULL,
    twilio_auth_token_encrypted VARCHAR(256) NOT NULL, -- encrypted at rest
    twilio_phone_number VARCHAR(20) NOT NULL,           -- E.164 format, the company's Twilio number
    auto_respond_new_lead BOOLEAN NOT NULL DEFAULT true,
    auto_respond_after_hours BOOLEAN NOT NULL DEFAULT true,
    business_hours_start TIME NOT NULL DEFAULT '08:00',
    business_hours_end TIME NOT NULL DEFAULT '18:00',
    business_timezone VARCHAR(50) NOT NULL DEFAULT 'America/Indiana/Indianapolis',
    new_lead_template TEXT NOT NULL DEFAULT 'Hi {first_name}, this is Legacy Roofing & Exteriors. We received your request and will be in touch shortly. Reply STOP to opt out.',
    after_hours_template TEXT NOT NULL DEFAULT 'Hi {first_name}, thanks for reaching out to Legacy Roofing & Exteriors. We''re closed for the day but will call you first thing in the morning. Reply STOP to opt out.',
    estimate_sent_template TEXT NOT NULL DEFAULT 'Hi {first_name}, your estimate from Legacy Roofing is ready! View it here: {estimate_url} Reply STOP to opt out.',
    opt_out_keywords TEXT NOT NULL DEFAULT 'STOP,UNSUBSCRIBE,CANCEL,END,QUIT',
    opt_in_keywords TEXT NOT NULL DEFAULT 'START,YES,UNSTOP',
    help_response TEXT NOT NULL DEFAULT 'Legacy Roofing & Exteriors. Call us at (765) 555-0100 or visit legacy-roofing.example. Reply STOP to opt out.',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**Add to contacts table:**
```sql
ALTER TABLE contacts ADD COLUMN sms_opt_out BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE contacts ADD COLUMN sms_opt_out_at TIMESTAMP NULLABLE;
```

### New Files — Backend

**`backend/app/models/sms.py`**
- `SmsMessage` model — maps to sms_messages table
- `SmsConfig` model — maps to sms_config table
- Register both in `models/__init__.py`

**`backend/app/schemas/sms.py`**
- `SmsMessageCreate` — body, contact_id, triggered_by (optional)
- `SmsMessageResponse` — full message with contact name for display
- `SmsConversationResponse` — list of messages for a contact, sorted by created_at
- `SmsConfigResponse` — config without auth token exposed
- `SmsConfigUpdate` — for updating templates, business hours, toggles
- `SmsSendRequest` — contact_id, body (for manual sends from UI)
- `SmsSendEstimateRequest` — contact_id, estimate_id (for sending estimate link via text)

**`backend/app/services/sms_service.py`** — Core SMS service:

```python
# Key functions:

def normalize_phone(phone: str) -> str | None:
    """Convert any phone format to E.164 (+1XXXXXXXXXX). Return None if unparseable."""
    # Strip all non-digits, handle leading 1 vs no leading 1
    # Return None for clearly invalid numbers (too short, too long)

async def send_sms(db, contact_id: UUID, body: str, triggered_by: str = "manual", sent_by: UUID = None) -> SmsMessage:
    """Send an SMS to a contact. Handles:
    1. Look up contact, get phone number
    2. Check sms_opt_out — refuse to send if opted out
    3. Normalize phone to E.164
    4. Load sms_config for Twilio credentials + from number
    5. Call Twilio API (client.messages.create)
    6. Create sms_messages record with twilio_sid and status
    7. Return the message record
    Raise ValueError if contact has no phone or is opted out.
    """

async def receive_sms(db, from_number: str, to_number: str, body: str, twilio_sid: str) -> SmsMessage:
    """Process inbound SMS. Handles:
    1. Look up contact by phone number (normalize and match)
    2. If no contact found, create a new contact with phone only (name = "Unknown - {phone}")
    3. Check for opt-out keywords (STOP, etc.) — set contact.sms_opt_out = True, send Twilio opt-out confirmation
    4. Check for opt-in keywords (START, etc.) — set contact.sms_opt_out = False
    5. Check for HELP keyword — send help_response
    6. Create sms_messages record with direction='inbound', status='received'
    7. Return the message record
    """

async def auto_respond_new_lead(db, contact_id: UUID):
    """Called when a new contact is created in the Leads pipeline.
    1. Load sms_config — check auto_respond_new_lead toggle
    2. Check if contact has a phone number
    3. Determine if within business hours or after hours
    4. Select appropriate template (new_lead_template or after_hours_template)
    5. Render template with personalization tokens: {first_name}, {company_name}, {rep_name}
    6. Call send_sms with triggered_by='auto_new_lead'
    """

async def send_estimate_link(db, contact_id: UUID, estimate_id: UUID, sent_by: UUID = None):
    """Send estimate portal link via SMS.
    1. Load estimate, build portal URL
    2. Load sms_config, render estimate_sent_template with {first_name}, {estimate_url}
    3. Call send_sms with triggered_by='auto_estimate_sent'
    """

def render_template(template: str, contact, **kwargs) -> str:
    """Replace personalization tokens in a template string."""
    # Supported tokens: {first_name}, {last_name}, {full_name}, {company_name},
    #                   {rep_name}, {estimate_url}, {invoice_url}
    # Missing values render as empty string, not {token}

def is_business_hours(config: SmsConfig) -> bool:
    """Check if current time is within business hours in the configured timezone."""

def get_twilio_client(config: SmsConfig):
    """Return authenticated Twilio REST client. Decrypt auth token."""
```

**`backend/app/services/phone_utils.py`** — Phone number utilities:
```python
def normalize_to_e164(phone: str) -> str | None:
    """Normalize US phone to +1XXXXXXXXXX. Returns None if invalid."""

def format_for_display(e164: str) -> str:
    """Convert +17655550181 to (765) 555-0181 for display."""

def match_phone(stored: str, incoming: str) -> bool:
    """Compare two phone numbers ignoring formatting differences."""
```

### Modified Files — Backend

**`backend/app/routers/contacts.py`** — In the contact creation endpoint (`POST /api/contacts`):
- After creating the contact, check if the contact was placed in the Leads pipeline
- If yes, call `auto_respond_new_lead(db, contact.id)` as a background task (fire-and-forget, don't block the response)
- Import and use FastAPI's `BackgroundTasks`

**`backend/app/models/__init__.py`** — Register SmsMessage, SmsConfig

### Environment Variables (new)
```
TWILIO_ACCOUNT_SID=        # from Twilio console
TWILIO_AUTH_TOKEN=          # from Twilio console  
TWILIO_PHONE_NUMBER=        # E.164 format, e.g. +17655551234
SMS_ENABLED=false           # master kill switch — false disables all SMS sending
```

**Design decision:** For v1, store Twilio credentials in environment variables (same pattern as SMTP). The `sms_config` table stores templates, business hours, and toggles. The encrypted auth token column in sms_config is for future use when config is managed via UI — for now, the service reads from env vars first, falls back to sms_config row.

### Tests — Sub-Sprint 17a

**`backend/tests/test_sms_service.py`** — 25+ tests:
- `test_normalize_phone_formats` — "(765) 555-0181", "765-555-0181", "7655550181", "+17655550181", "1-765-555-0181" all normalize to "+17655550181"
- `test_normalize_phone_invalid` — too short, too long, letters return None
- `test_send_sms_creates_record` — mock Twilio client, verify sms_messages row created
- `test_send_sms_opt_out_refused` — contact with sms_opt_out=True → ValueError
- `test_send_sms_no_phone_refused` — contact with no phone → ValueError
- `test_receive_sms_matches_contact` — inbound from known number matches correct contact
- `test_receive_sms_unknown_creates_contact` — inbound from unknown number creates stub contact
- `test_receive_sms_opt_out` — inbound "STOP" sets contact.sms_opt_out = True
- `test_receive_sms_opt_in` — inbound "START" clears opt_out flag
- `test_receive_sms_help` — inbound "HELP" triggers help_response
- `test_auto_respond_new_lead_during_business_hours` — sends new_lead_template
- `test_auto_respond_new_lead_after_hours` — sends after_hours_template
- `test_auto_respond_disabled` — config toggle off → no SMS sent
- `test_render_template_tokens` — all tokens replaced correctly
- `test_render_template_missing_token` — missing value → empty string
- `test_is_business_hours` — boundary cases (8:00am = yes, 5:59pm = yes, 6:00pm = no)
- `test_send_estimate_link` — estimate portal URL included in message body
- `test_phone_match` — various format combinations all match correctly

**Mocking pattern:** All tests must mock the Twilio client. Use `unittest.mock.patch` on the Twilio `Client.messages.create` method. Never make real Twilio API calls in tests. Create a fixture that returns a mock client with predictable SID responses.

### Anti-Patterns — 17a
- Do NOT store phone numbers in E.164 in the database — keep them human-readable as imported
- Do NOT encrypt the auth token in the sms_config table yet — column exists for future use, service reads from env vars
- Do NOT add SMS sending to estimate or invoice send flows yet — that's 17b
- Do NOT build the inbound webhook endpoint yet — that's 17b
- Do NOT build any frontend — that's 17c

---

## Sub-Sprint 17b: API Endpoints + Webhook + Event Integration

### New Files — Backend

**`backend/app/routers/sms.py`** — SMS router:

```python
# Endpoints:

POST /api/sms/send
# Body: { "contact_id": UUID, "body": str }
# Auth: JWT required
# Calls sms_service.send_sms with triggered_by='manual', sent_by=current_user
# Returns: SmsMessageResponse
# Errors: 400 if no phone, 400 if opted out, 404 if contact not found

GET /api/contacts/{contact_id}/sms
# Auth: JWT required
# Returns: list of SmsMessageResponse for this contact, sorted by created_at desc
# Pagination: ?page=1&per_page=50
# Includes: direction, body, status, triggered_by, created_at, sent_by (with user name)

POST /api/sms/send-estimate
# Body: { "contact_id": UUID, "estimate_id": UUID }
# Auth: JWT required
# Sends estimate portal link via SMS
# Returns: SmsMessageResponse

GET /api/sms/config
# Auth: JWT required (admin only)
# Returns: SmsConfigResponse (no auth token)

PUT /api/sms/config
# Auth: JWT required (admin only)
# Body: SmsConfigUpdate (templates, business hours, toggles)
# Returns: updated SmsConfigResponse

POST /api/webhooks/twilio/inbound
# NO AUTH — Twilio cannot send JWT tokens
# Twilio signature validation instead (X-Twilio-Signature header)
# Receives: From, To, Body, MessageSid (form-encoded)
# Calls sms_service.receive_sms
# Returns: TwiML response (empty <Response/> — we handle replies through our own send flow, not TwiML)
# CRITICAL: Validate Twilio signature to prevent spoofed requests

POST /api/webhooks/twilio/status
# NO AUTH — Twilio status callback
# Twilio signature validation
# Receives: MessageSid, MessageStatus (sent, delivered, undelivered, failed)
# Updates sms_messages.status for the matching twilio_sid
# Returns: 200 OK
```

**Twilio signature validation:**
```python
from twilio.request_validator import RequestValidator

def validate_twilio_signature(request, auth_token):
    """Validate that the request actually came from Twilio."""
    validator = RequestValidator(auth_token)
    url = str(request.url)
    signature = request.headers.get('X-Twilio-Signature', '')
    # For POST, pass form params; for GET, params are in URL
    return validator.validate(url, dict(await request.form()), signature)
```

### Modified Files — Backend

**`backend/app/main.py`** — Register sms router and webhook router

**`backend/app/routers/estimates.py`** — In the estimate send endpoint (`POST /api/estimates/{id}/send`):
- After sending the email, also trigger SMS if the contact has a phone number
- Use `BackgroundTasks` to call `sms_service.send_estimate_link` (fire-and-forget)
- Only if SMS_ENABLED=true and contact is not opted out

**`backend/app/routers/contacts.py`** — Add sms_opt_out to contact response schema if not already there

### Seed Data

**`backend/app/services/sms_service.py`** — Add a `ensure_sms_config(db)` function:
- Check if sms_config row exists
- If not, create one with default templates and business hours
- Called on app startup or first SMS operation
- This avoids requiring a migration to seed config data

### Tests — Sub-Sprint 17b

**`backend/tests/test_sms_endpoints.py`** — 20+ tests:
- `test_send_sms_manual` — POST /api/sms/send with valid contact → 200, message created
- `test_send_sms_no_auth` — POST without JWT → 401
- `test_send_sms_invalid_contact` — POST with bad contact_id → 404
- `test_send_sms_opted_out` — POST to opted-out contact → 400
- `test_get_conversation` — GET /api/contacts/{id}/sms returns messages in order
- `test_get_conversation_pagination` — page/per_page params work
- `test_send_estimate_link` — POST /api/sms/send-estimate creates message with URL
- `test_get_config` — GET /api/sms/config returns config without auth token
- `test_update_config` — PUT /api/sms/config updates templates
- `test_inbound_webhook` — POST /api/webhooks/twilio/inbound with valid signature → processes message
- `test_inbound_webhook_invalid_signature` — invalid signature → 403
- `test_inbound_webhook_opt_out` — inbound "STOP" → sets opt_out flag
- `test_status_webhook` — POST /api/webhooks/twilio/status updates message status
- `test_auto_respond_on_lead_creation` — create contact in leads pipeline → auto SMS triggered
- `test_estimate_send_triggers_sms` — send estimate email → SMS also sent if phone exists

**Webhook test pattern:** Mock the Twilio request validator to return True for test requests. The webhook endpoint must work with form-encoded data (not JSON) — Twilio sends `application/x-www-form-urlencoded`.

### Anti-Patterns — 17b
- Do NOT require auth on webhook endpoints — Twilio can't send JWTs. Use Twilio signature validation instead.
- Do NOT respond to inbound SMS with TwiML `<Message>` — we send replies through our own send_sms flow so they're tracked in our database. Return empty `<Response/>`.
- Do NOT block the contact creation response waiting for SMS — use BackgroundTasks
- Do NOT send SMS if SMS_ENABLED env var is false or missing — this is the kill switch for environments without Twilio configured (local dev, test suite)

---

## Sub-Sprint 17c: Frontend — Conversation View + Send UI

### Modified Files — Frontend

**`frontend/src/api/sms.js`** — New API module:
```javascript
export async function sendSms(contactId, body) { ... }
export async function getConversation(contactId, page = 1) { ... }
export async function sendEstimateViaSms(contactId, estimateId) { ... }
export async function getSmsConfig() { ... }
export async function updateSmsConfig(config) { ... }
```

**`frontend/src/pages/ContactDetailPage.jsx`** — Add "Messages" tab to the contact detail page:
- New tab in the existing tab strip (alongside Estimates, Invoices, Notes, etc.)
- Tab shows unread count badge if there are unread inbound messages
- Tab content = conversation view component

**`frontend/src/components/SmsConversationView.jsx`** — New component:
- Chat-bubble style conversation view (like iMessage / WhatsApp)
- Outbound messages: right-aligned, brand purple background, white text
- Inbound messages: left-aligned, light gray background, dark text
- Each bubble shows: message body, timestamp, status indicator (sent/delivered/failed)
- Auto-triggered messages show a small label: "Auto-response" or "Estimate sent"
- Message input at the bottom: text field + send button
- Send button disabled while sending (loading state)
- Auto-scroll to bottom on new messages
- Load more (pagination) when scrolling up
- If contact has no phone number: show empty state "No phone number on file — add one to start texting"
- If contact is opted out: show banner "This contact has opted out of text messages" and disable send

**`frontend/src/pages/EstimateDetailPage.jsx`** — Add "Send via Text" button:
- Next to existing "Send Estimate" (email) button
- Opens confirmation modal: "Send estimate link to {contact_name} at {phone}?"
- Calls sendEstimateViaSms
- Success toast: "Estimate link sent via text"
- Only visible if contact has a phone number

**`frontend/src/pages/SettingsPage.jsx`** (or new `SmsSettingsPage.jsx`):
- Add SMS Settings section/page (accessible from Settings nav)
- Editable fields:
  - Auto-respond to new leads: toggle
  - Auto-respond after hours: toggle  
  - Business hours: start time + end time
  - New lead template: textarea with token reference
  - After hours template: textarea with token reference
  - Estimate sent template: textarea with token reference
- Token reference help text: "Available tokens: {first_name}, {last_name}, {company_name}, {rep_name}, {estimate_url}"
- Save button
- "Test SMS" button: sends a test message to the admin's own phone number

### UI Design Notes

**Conversation bubbles** — Keep it simple and familiar. The DripJobs "Chat" sidebar is a reference but we're building a full tab experience, not a sidebar. Think of how a CRM user checks text history: they're on a client profile, they click Messages, they see the thread, they type a reply. The flow should feel as natural as texting from a phone.

**Status indicators:**
- Queued: gray clock icon
- Sent: single gray checkmark
- Delivered: double blue checkmarks
- Failed: red exclamation with hover tooltip showing error detail
- Received (inbound): no indicator needed

**Mobile responsiveness:** This tab must work on mobile (375px). Marcus tests from his iPhone on job sites. Chat bubbles, input field, and send button must be fully functional at mobile width.

### Tests — Sub-Sprint 17c

Frontend tests are manual smoke tests (no frontend test framework in the project). Verify:
1. Messages tab appears on contact detail page
2. Conversation loads for contacts with SMS history
3. Send message works — message appears in thread immediately
4. Inbound messages appear on left, outbound on right
5. Auto-response messages show label
6. Opted-out contact shows banner and disabled send
7. No-phone contact shows empty state
8. Send via Text button appears on estimate detail
9. SMS Settings page loads and saves
10. Mobile layout (375px) — conversation view functional

---

## Dependencies and Setup

### Python Package
Add to `requirements.txt`:
```
twilio>=9.0.0
```

### Environment Variables for Development
```
SMS_ENABLED=true
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxx    # from Twilio trial account
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxx     # from Twilio trial account
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX      # trial phone number
```

### Environment Variables for Production (Azure)
Same variables, set via Azure App Service configuration. SMS_ENABLED=false until Twilio account is upgraded and A2P 10DLC registration is complete.

### Twilio Console Setup (for development)
1. Create free Twilio account at twilio.com
2. Verify your personal phone number
3. Get a trial phone number (Twilio assigns one automatically)
4. Note Account SID and Auth Token from the console dashboard
5. Configure the Twilio phone number's webhook:
   - Messaging → "A message comes in" → Webhook → POST → `{CRM_BASE_URL}/api/webhooks/twilio/inbound`
   - For local dev: use ngrok URL
   - For production: use Azure URL
6. Configure status callback:
   - Set in code when sending: `status_callback=f"{CRM_BASE_URL}/api/webhooks/twilio/status"`

### Trial Account Limitations
- Outbound SMS prepended with "Sent from a Twilio trial account"
- Can only send to verified phone numbers (add test numbers in Twilio console)
- $15.50 in free credits (hundreds of test messages)
- Full API access — all endpoints work identically to paid

---

## What Is NOT In Sprint 17

- Drip sequences / automated follow-up chains (Sprint 19)
- MMS / image messaging
- Group texting / broadcast
- Call recording or transcription (Sprint 21)
- Per-rep phone numbers (future — one company number for v1)
- Twilio voice calls
- A2P 10DLC registration (done when going live, not a code task)
- SMS reporting/analytics dashboard

---

## Verification Checklist

### 17a
- [ ] Migration 0027 runs cleanly
- [ ] sms_messages and sms_config tables created
- [ ] contacts.sms_opt_out column added
- [ ] Phone normalization handles all AccuLynx formats
- [ ] send_sms creates message record with Twilio SID
- [ ] receive_sms matches contact by phone number
- [ ] STOP/START/HELP keywords handled correctly
- [ ] auto_respond_new_lead sends correct template based on time of day
- [ ] Template rendering handles all tokens + missing values gracefully
- [ ] All 25+ new tests passing
- [ ] All 654 existing tests still passing

### 17b
- [ ] POST /api/sms/send works with valid JWT
- [ ] GET /api/contacts/{id}/sms returns conversation history
- [ ] POST /api/sms/send-estimate sends portal link
- [ ] GET/PUT /api/sms/config work for admin users
- [ ] POST /api/webhooks/twilio/inbound processes messages (with signature validation)
- [ ] POST /api/webhooks/twilio/status updates message status
- [ ] New lead creation triggers auto-response in background
- [ ] Estimate send triggers SMS in background
- [ ] SMS_ENABLED=false prevents all sending
- [ ] All 20+ new tests passing
- [ ] All previous tests still passing

### 17c
- [ ] Messages tab on contact detail shows conversation
- [ ] Chat bubbles: outbound right/purple, inbound left/gray
- [ ] Send message from conversation view works
- [ ] Auto-response messages labeled
- [ ] Opted-out contact shows warning banner
- [ ] No-phone contact shows empty state
- [ ] "Send via Text" button on estimate detail works
- [ ] SMS Settings page functional
- [ ] Mobile layout (375px) works for conversation view
- [ ] No regressions in existing UI

---

## Context Line for Claude Code Sessions

### Sub-sprint 17a:
```
Read CLAUDE.md and PRD.md. Sprints 1–16d are complete. 654 tests passing. Latest migration: 0026. Sprint 17a: Build SMS data model (migration 0027: sms_messages + sms_config tables, contacts.sms_opt_out column) and Twilio service layer (sms_service.py, phone_utils.py). Mock Twilio client in all tests. Read the full Sprint 17 spec at docs/superpowers/specs/legacy_crm_sprint17_sms_spec.md for implementation details.
```

### Sub-sprint 17b:
```
Read CLAUDE.md and PRD.md. Sprint 17a complete. [X] tests passing. Sprint 17b: Build SMS API endpoints (sms router: send, conversation, config CRUD) and Twilio webhook endpoints (inbound + status). Wire auto-respond into contact creation and estimate send flows using BackgroundTasks. Read the full Sprint 17 spec at docs/superpowers/specs/legacy_crm_sprint17_sms_spec.md.
```

### Sub-sprint 17c:
```
Read CLAUDE.md and PRD.md. Sprint 17b complete. [X] tests passing. Sprint 17c: Build frontend — SmsConversationView component (chat bubbles), Messages tab on ContactDetailPage, "Send via Text" on EstimateDetailPage, SMS Settings page. Read the full Sprint 17 spec at docs/superpowers/specs/legacy_crm_sprint17_sms_spec.md.
```
