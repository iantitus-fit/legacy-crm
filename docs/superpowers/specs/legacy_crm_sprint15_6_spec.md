# Legacy CRM — Sprint 15.6: Client Profile Tabs

**Sprint:** 15.6 (4 sub-sprints)
**Objective:** Add Tasks, Documents, and Activity tabs to the Client Profile page, plus an Archived/Rejected collapsible section on the existing Estimates tab.
**Dependencies:** None — all features use existing data models and API patterns.
**Migration:** None required.

---

## Context Line for Claude Code

```
Read CLAUDE.md. Sprints 1–15.5 complete. 465 tests passing, 0 errors. Latest migration: 0023. Production deployed to Azure. Deploy via ./scripts/deploy.sh. This sprint adds Tasks, Documents, and Activity tabs to the Client Profile page at /contacts/:id.
```

---

## Sub-sprint 15.6a: Tasks Tab on Client Profile

### Current Behavior
Client Profile page has tabs: Info, Notes, Estimates, Jobs, Invoices. No Tasks tab. Tasks related to this client are only visible from the global Tasks page.

### Desired Behavior
New "Tasks" tab on Client Profile showing all tasks related to this client — both tasks linked directly to the contact AND tasks linked to any of this contact's estimates.

### Backend

**New endpoint:** `GET /api/contacts/{contact_id}/tasks`

Query logic:
1. Find all tasks where `entity_type = 'contact' AND entity_id = {contact_id}`
2. Find all estimate IDs belonging to this contact: `SELECT id FROM estimates WHERE contact_id = {contact_id}`
3. Find all tasks where `entity_type = 'estimate' AND entity_id IN (those estimate IDs)`
4. Also include tasks where `entity_type = 'job' AND entity_id IN (SELECT id FROM jobs WHERE contact_id = {contact_id})` — catches legacy job-linked tasks during transition
5. Union all results, order by `due_date ASC NULLS LAST, created_at DESC`
6. Return with assignee name and entity display info (entity_type, entity_id, plus a display_name for the linked entity)

Response shape — reuse existing `TaskResponse` schema, add `entity_display_name` field if not already present:
```json
{
  "id": 1,
  "title": "Follow up with Bob",
  "description": "...",
  "due_date": "2026-04-28",
  "completed": false,
  "assigned_to": 3,
  "assignee_name": "Logan",
  "entity_type": "estimate",
  "entity_id": 5,
  "entity_display_name": "EST-0005 — Roof Replacement",
  "created_at": "..."
}
```

### Frontend

**New `ClientTasksTab.jsx` component:**
- 3 sections (collapsible): **Overdue** (red header, past due_date + not completed), **Upcoming** (due_date >= today or no due_date, not completed), **Completed** (completed = true, most recent first, collapsed by default)
- Each task row shows: checkbox (toggle complete), title, due date (red if overdue), assignee name with color dot, entity link chip (e.g., "EST-0005" or "Lead" — clickable, routes to the entity)
- Entity link chip: if entity_type = 'estimate', link to `/estimates/{entity_id}`. If entity_type = 'contact', no link (you're already there). If entity_type = 'job', link to `/jobs/{entity_id}` (legacy fallback).
- "+ Add Task" button at top — opens existing task create modal, pre-fills entity_type = 'contact' and entity_id = this contact's ID
- Task completion toggle: `PUT /api/tasks/{id}` with `completed: true/false` — existing endpoint
- Count badge on tab header showing incomplete task count

### Reference
Marcus's call transcript: "It'd be nice if he had that where he could pop up, have a popup window, boom, oh, that's what that job is." — the entity link chips solve this by letting users click through to the related estimate or lead from any task.

### Tests (target: 6-8 new tests)
- GET /api/contacts/{id}/tasks returns tasks linked to contact
- GET /api/contacts/{id}/tasks returns tasks linked to contact's estimates
- GET /api/contacts/{id}/tasks returns tasks linked to contact's legacy jobs
- GET /api/contacts/{id}/tasks excludes tasks linked to other contacts
- GET /api/contacts/{id}/tasks requires auth
- GET /api/contacts/{id}/tasks returns empty array for contact with no tasks

---

## Sub-sprint 15.6b: Documents Tab on Client Profile

### Current Behavior
Documents exist in the system with dual-lookup (contact_id or job_id). No Documents tab on Client Profile.

### Desired Behavior
New "Documents" tab showing all documents associated with this client.

### Backend

**New endpoint:** `GET /api/contacts/{contact_id}/documents`

Query logic:
1. Find all documents where `contact_id = {contact_id}`
2. Also find documents where `job_id IN (SELECT id FROM jobs WHERE contact_id = {contact_id})` — dual-lookup from restructure
3. Union, deduplicate by document ID, order by `created_at DESC`

### Frontend

**New `ClientDocumentsTab.jsx` component:**
- File list view: icon (based on file type), filename, upload date, size, uploaded by
- File type icons: PDF icon, image icon, generic document icon
- Click filename → download or open in new tab
- "+ Upload Document" button — opens file upload modal, associates with contact_id
- Empty state: "No documents yet. Upload files related to this client."
- If documents exist for estimates (PDFs of sent proposals, signed documents), those should appear here too since they're associated with the contact's estimates

### Implementation Note
The document storage layer already supports dual-lookup (contact_id and job_id) from Migration 0021. This tab just needs to query both paths and display results.

### Tests (target: 4-5 new tests)
- GET /api/contacts/{id}/documents returns documents linked to contact
- GET /api/contacts/{id}/documents returns documents linked to contact's jobs
- GET /api/contacts/{id}/documents requires auth
- GET /api/contacts/{id}/documents returns empty array for contact with no documents

---

## Sub-sprint 15.6c: Activity Tab on Client Profile

### Current Behavior
Activity tab existed on the old Job Detail page as a placeholder ("Coming soon"). No activity tracking or display anywhere.

### Desired Behavior
New "Activity" tab showing a chronological feed of all events related to this client. This is a read-only timeline — no data model changes needed because it aggregates existing data.

### Implementation — Aggregation Endpoint

**New endpoint:** `GET /api/contacts/{contact_id}/activity`

This endpoint does NOT require an activity_log table. It queries existing tables and assembles a timeline:

1. **Estimates:** `created_at`, `sent_at`, `viewed_at`, `approved_at` from estimates where `contact_id = {contact_id}`
2. **Change Orders:** `created_at`, status changes from change_orders linked to those estimates
3. **Invoices:** `created_at`, `paid_at` from invoices linked to those estimates
4. **Payments:** `created_at` from payments linked to those invoices
5. **Notes:** `created_at` from notes where entity links to this contact or its estimates/jobs
6. **Tasks:** `created_at`, `completed_at` (if completed) from tasks linked to this contact or its estimates
7. **Pipeline stage changes:** If we track `updated_at` on contacts/estimates when stage changes, include those. If not, skip — this can be added later with an actual audit log.

Response shape:
```json
[
  {
    "type": "estimate_created",
    "description": "Estimate EST-0005 created",
    "entity_type": "estimate",
    "entity_id": 5,
    "timestamp": "2026-04-15T14:30:00Z",
    "actor": "Ian Titus"
  },
  {
    "type": "estimate_sent",
    "description": "Estimate EST-0005 sent to client",
    "entity_type": "estimate",
    "entity_id": 5,
    "timestamp": "2026-04-15T15:00:00Z",
    "actor": null
  },
  {
    "type": "payment_received",
    "description": "Payment of $2,500.00 received on INV-0003",
    "entity_type": "invoice",
    "entity_id": 3,
    "timestamp": "2026-04-20T10:15:00Z",
    "actor": null
  }
]
```

Sorted by timestamp descending (newest first). Limit to last 50 events by default, with `?limit=` parameter.

### Frontend

**New `ClientActivityTab.jsx` component:**
- Vertical timeline layout with colored dots per event type
- Event type color coding: green (payments, approvals), blue (estimates, invoices created), purple (notes, tasks), orange (sent/viewed), gray (other)
- Each event shows: colored dot, event description, relative timestamp ("2 hours ago", "Apr 15"), clickable entity link
- Empty state: "No activity recorded for this client yet."

### Design Note
This is NOT an audit log or event sourcing system. It's a query-time aggregation of existing timestamps. If you later want real event sourcing (who changed what field, when), that's Sprint 16+ territory with an actual `activity_log` table. This implementation gives Marcus a useful timeline today with zero schema changes.

### Tests (target: 5-6 new tests)
- GET /api/contacts/{id}/activity returns events from estimates
- GET /api/contacts/{id}/activity returns events from invoices/payments
- GET /api/contacts/{id}/activity returns events sorted by timestamp desc
- GET /api/contacts/{id}/activity respects limit parameter
- GET /api/contacts/{id}/activity requires auth

---

## Sub-sprint 15.6d: Archived/Rejected Estimates Section

### Current Behavior
Estimates tab on Client Profile shows all estimates in a flat list regardless of status.

### Desired Behavior
Estimates tab splits into two sections:
1. **Active Estimates** (default, expanded) — statuses: draft, sent, viewed, approved, completed
2. **Archived / Rejected** (collapsed by default, expandable) — statuses: rejected, archived, expired

### Frontend Only
No backend changes. The existing estimates list endpoint already returns status. This is purely a frontend filter/display change in the Estimates tab component.

- Collapsible section header: "Archived / Rejected (3)" with chevron toggle
- Collapsed by default — click to expand
- Archived/rejected estimates shown with muted styling (reduced opacity or gray text)
- If no archived/rejected estimates exist, don't show the section at all

### Tests
No new backend tests needed — this is a frontend-only display change.

---

## Anti-Patterns

- **Do NOT create an activity_log table.** The Activity tab aggregates existing timestamps. A real audit log is a future sprint.
- **Do NOT change the task data model.** Query tasks by their existing entity_type/entity_id fields. The task model cleanup (relinking from jobs to contacts/estimates) is a separate backlog item.
- **Do NOT change existing tab behavior.** Info, Notes, Estimates, Jobs, Invoices tabs must work exactly as they do now.
- **Do NOT modify customer portals, PDF templates, or the estimate calculation engine.**
- **Do NOT create new migrations.** All data needed for these tabs already exists in the database.

---

## Tab Order on Client Profile (Final)

Info | Notes | Tasks | Estimates | Jobs | Invoices | Documents | Activity

(Tasks moves to after Notes since it's a high-frequency tab. Activity goes last since it's read-only reference.)

---

## Verification Checklist

1. Client Profile shows all 8 tabs
2. Tasks tab shows tasks from contact + contact's estimates + contact's legacy jobs
3. Tasks tab overdue/upcoming/completed sections work
4. Task completion toggle works from the tab
5. "+ Add Task" creates task linked to this contact
6. Entity link chips on tasks are clickable and route correctly
7. Documents tab shows uploaded documents
8. Documents tab file upload works and associates with contact
9. Activity tab shows timeline of events from estimates, invoices, payments, notes
10. Activity events are sorted newest-first
11. Activity entity links are clickable
12. Estimates tab has collapsed "Archived / Rejected" section
13. Section only appears when archived/rejected estimates exist
14. All 465+ existing tests still pass
15. New tests pass (target: 15-19 new tests total across sub-sprints)
16. Theme-aware: all new components use CSS variable classes (not hardcoded colors)
17. Mobile-responsive: tabs wrap or scroll on narrow viewports
