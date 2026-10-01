# Legacy CRM — Data Model Restructure Spec
## "Client Profile + Estimate-is-Job"

**Date:** April 11, 2026
**Source:** Marcus Hale voice memo walkthrough + follow-up clarifications
**Scope:** This is a data model and navigation restructure, not a feature sprint. The goal is to align the CRM's entity hierarchy with how contractors actually think about their workflow.

---

## The Problem

The current data model uses a three-level hierarchy: **Contact → Job → Estimate**. A "Job" must exist before an estimate can be created, and the Job entity serves double duty as both a client container and a work unit. This creates confusion:

- You have to create a "Job" before you know if the client is buying anything
- Job type (roofing, gutters, painting) lives on the Job, but a single client may need estimates for multiple trades
- When an estimate is approved, there's no clear transition — the Job already exists, so "becoming a job" has no meaning in the system
- Lead Pipeline, Sales Pipeline, and Jobs Pipeline all navigate to the same Job detail page, even though they represent different stages of the relationship

## Marcus's Mental Model (The Fix)

1. **Client Profile** = the person/company. Holds contact info, lead source, commercial/residential classification. This is the central entity.
2. **Estimate** = a scoped proposal. Lives under the client. Has its own job type, location, line items. Multiple estimates per client.
3. **Job** = an approved estimate. Not a separate entity — the estimate record gains a status change and unlocks additional sections (crew, schedule, job costing, ordering).

**The Job table goes away as a standalone entity.** Its fields either move to Contact (lead source, commercial/residential) or to Estimate (job type, work type, crew, schedule). An estimate with status "approved" IS a job.

---

## Current vs. Proposed Entity Relationships

### Current
```
Contact
  └── Job (container — holds lead_source, job_type, work_type, pipeline_id, stage_id)
        ├── Estimate (line items, sections, notes, PDF, portal)
        │     └── Change Order
        ├── Invoice
        ├── Task
        ├── Note
        └── Document
```

### Proposed
```
Contact (= Client Profile)
  │   lead_source, client_type (commercial/residential), pipeline stage for lead/sales tracking
  │
  ├── Estimate (= Proposal, and when approved = Job)
  │     │   job_type, work_type, location/address, crew, schedule
  │     │   status: draft → sent → viewed → approved (= job) → in_progress → complete → closed
  │     │
  │     ├── Line Items (unchanged)
  │     ├── Sections (unchanged)
  │     ├── Estimate Notes (unchanged)
  │     ├── Change Order (attached to approved estimates / jobs)
  │     ├── Invoice (attached to approved estimates / jobs)
  │     └── Job Costing (future — attached to approved estimates / jobs)
  │
  ├── Task (linked to contact, or to specific estimate/job)
  ├── Note (contact-level notes)
  ├── Document (contact-level documents)
  └── Appointment (linked to contact, optionally to estimate)
```

---

## Schema Changes

### Migration: Contacts table (add fields)

```sql
ALTER TABLE contacts ADD COLUMN lead_source VARCHAR(50);
ALTER TABLE contacts ADD COLUMN client_type VARCHAR(20); -- 'residential', 'commercial'
ALTER TABLE contacts ADD COLUMN pipeline_id INTEGER REFERENCES pipelines(id);
ALTER TABLE contacts ADD COLUMN stage_id INTEGER REFERENCES pipeline_stages(id);
```

**Data migration:** Copy `lead_source` from each contact's most recent job. Copy `pipeline_id` and `stage_id` from each contact's most recent job. Default `client_type` to 'residential'.

### Migration: Estimates table (add fields from jobs)

```sql
ALTER TABLE estimates ADD COLUMN job_type VARCHAR(50); -- 'Roofing', 'Gutters', 'Siding', 'Painting', etc.
ALTER TABLE estimates ADD COLUMN work_type VARCHAR(20); -- 'retail', 'insurance'
ALTER TABLE estimates ADD COLUMN location_address TEXT; -- estimate-specific address (may differ from contact address)
ALTER TABLE estimates ADD COLUMN crew_id INTEGER REFERENCES crews(id);
ALTER TABLE estimates ADD COLUMN scheduled_start DATE;
ALTER TABLE estimates ADD COLUMN scheduled_end DATE;
ALTER TABLE estimates ADD COLUMN assigned_to INTEGER REFERENCES users(id);
ALTER TABLE estimates ADD COLUMN approved_at TIMESTAMP;
ALTER TABLE estimates ADD COLUMN approved_by VARCHAR(100); -- 'customer_portal', 'internal', customer name
```

**Note on status:** Estimates already have a `status` field (draft, sent, viewed, approved). This spec extends it with job-phase statuses: `in_progress`, `complete`, `closed`. An estimate with status in {approved, in_progress, complete, closed} is considered a "job."

**Data migration:** For each existing job that has estimates, copy `job_type`, `work_type`, `assigned_to`, schedule fields to the estimate. For jobs with no estimates, create a placeholder estimate record to preserve the data.

### Migration: Update foreign keys

The following tables currently reference `job_id` and need to be updated:

- **invoices** — already linked to estimates via `estimate_id`. Verify this is the primary link and `job_id` is redundant, or add `estimate_id` FK if missing.
- **change_orders** — already linked to estimates. Verify and confirm.
- **tasks** — currently have `entity_type` + `entity_id` polymorphic link. Update references from job to estimate where appropriate. Contact-level tasks stay on contact.
- **notes** — similar polymorphic link. Job-level notes migrate to either the contact or the estimate.
- **documents** — currently on jobs. Move to contact-level or estimate-level based on context.
- **appointments** — currently linked to contacts. Add optional `estimate_id` FK for estimate-specific appointments.

### Migration: Pipeline stages remap

**Lead Pipeline** — stages apply to Contacts (not jobs). Contacts have a `pipeline_id` and `stage_id`.
- Cold Leads, Warm Leads, No Answer, Angi Leads, Website Inquiry

**Sales Pipeline** — stages apply to Contacts (tracking where the client is in the sales process).
- Draft, Estimate Sent, Cold Proposals, Warm Proposals, Hot Proposals

**Jobs Pipeline** — stages apply to Estimates (only approved estimates appear here).
- Pending Schedule, Scheduled, In Progress, Complete, Warranty, Closed

This means: Lead and Sales pipelines are **contact-level** pipelines. Jobs pipeline is an **estimate-level** pipeline. The pipeline board needs to know which entity type it's displaying.

**Alternative (simpler):** Keep all pipeline tracking on Contact. The Jobs pipeline shows contacts that have at least one approved estimate. The estimate's own status field (approved → in_progress → complete → closed) tracks job-phase progression. This avoids splitting pipeline logic across two entity types.

**Recommended approach:** Use the simpler alternative. Contact holds `pipeline_id` + `stage_id` for all three pipelines. When a contact is in the Jobs pipeline, the board card shows the specific approved estimate(s). The estimate `status` field handles the job lifecycle internally.

### Jobs table — deprecation

The `jobs` table is not deleted in this migration. Instead:

1. All data is migrated to contacts and estimates
2. All foreign keys pointing to jobs are redirected
3. The jobs table is renamed to `jobs_deprecated` or soft-deleted
4. A future cleanup migration removes it after verification

---

## Navigation & UI Changes

### Sidebar

**Current:**
```
SALES
  Contacts
  Leads Pipeline
  Sales Pipeline
JOBS
  Jobs Pipeline
  Jobs List
  Estimates
```

**Proposed:**
```
CLIENTS
  Client Profiles (was Contacts)
  Leads Pipeline
  Sales Pipeline
JOBS
  Jobs Pipeline
  Jobs List (shows approved estimates)
  Estimates (shows all estimates across all clients)
```

### Pipeline Board Behavior

**Lead Pipeline:** Cards represent contacts. Clicking a card opens the **Client Profile** page.

**Sales Pipeline:** Cards represent contacts. Clicking a card opens the **Client Profile** page. The card should show how many active estimates exist and their total value.

**Jobs Pipeline:** Cards represent contacts that have approved estimates. Clicking a card opens the **Client Profile** page, scrolled to or focused on the Jobs tab. The card should show the specific approved estimate/job name, crew, and schedule.

**Alternative for Jobs Pipeline:** Cards represent individual approved estimates (not contacts). This means a contact with 3 approved estimates shows as 3 separate cards. Clicking opens the **Estimate Detail** page (which now has job sections). This may be more intuitive for scheduling and crew assignment since each card = one scope of work.

**Recommended:** Jobs Pipeline cards = individual approved estimates. This matches Marcus's statement: "Jobs pipeline would load the specific job." Each card is one job (one approved estimate) with its own crew, schedule, and address.

### Client Profile Page (Replaces Job Detail + Contact Detail)

**Route:** `/clients/:id` (or keep `/contacts/:id` and rename the display)

**Header:**
- Client name
- Company (if set)
- Phone (clickable), Email (clickable), Address (clickable)
- Client type badge: Residential / Commercial
- Lead source badge
- Pipeline stage indicator

**Summary cards:**
- Contract value (sum of approved estimates)
- Schedule status
- Active estimates count
- Open invoice balance

**Tabs:**
- **Details** — contact info, client type, lead source, address, notes
- **Estimates** — list of all estimates for this client (with status badges: draft, sent, approved, etc.)
  - Includes an "Archived / Rejected" section at the bottom (collapsed by default)
  - "+ Create Estimate" button
- **Jobs** — list of approved estimates (shortcut/filtered view of Estimates tab showing only status ∈ {approved, in_progress, complete, closed})
  - Each job card shows: estimate name, job type, crew, schedule, contract value
  - Click → opens Estimate Detail page with job sections visible
- **Invoices** — all invoices across all estimates for this client
- **Tasks** — contact-level tasks
- **Documents** — contact-level documents
- **Activity** — timeline of all actions across all estimates

### Estimate Detail Page (Enhanced for Job Phase)

The estimate detail page already exists and is well-built. When an estimate's status is "approved" or beyond, additional sections become visible:

**Always visible (all estimate statuses):**
- Estimate header (name, number, contact, dates, etc.)
- Line items with sections
- Estimate notes (company/crew/client)
- Change orders (if any)
- Actions: Send, Preview, Download PDF

**Visible only when status ≥ approved (job sections):**
- **Job Info panel:** Crew assignment, scheduled dates, job type, work type
- **Invoices tab:** Create invoice, list invoices, payment tracking
- **Job Costing tab:** (future sprint — placeholder)
- **Schedule section:** Assign crew, set dates, link to calendar

**"Internal Approve" button:**
- Visible on estimates in "sent" or "viewed" status
- Allows the salesperson to mark an estimate as approved without customer portal signature
- Sets `approved_by = 'internal'` and `approved_at = now()`
- Moves contact to Jobs pipeline (if using contact-level pipeline tracking)

**Deposit invoice from estimate:**
- Marcus mentioned wanting to send deposit invoices before formal approval
- Add "Create Deposit Invoice" button visible on estimates in sent/viewed status
- Creates an invoice linked to the estimate with a configurable deposit percentage
- Does NOT change estimate status — the estimate remains in its current state

### Create Estimate Flow

**From Client Profile:**
- "+ Create Estimate" button on Estimates tab
- Pre-fills contact info
- User selects job type (roofing, gutters, siding, painting, etc.)
- User enters estimate location (defaults to contact address, editable)

**From Sales Pipeline:**
- "+ New Estimate" button
- Opens contact picker first (search existing or create new)
- Then follows same flow as above

**From FAB (floating action button):**
- "New Estimate" option
- Opens contact picker → then estimate creation

### Jobs List Page

Currently shows jobs. Refactored to show approved estimates.
- Each row = one approved estimate
- Columns: Estimate name/number, Client name, Job type, Crew, Scheduled dates, Status, Contract value
- Filterable by status, crew, job type
- Searchable by client name or estimate name

---

## What Does NOT Change

- **Estimate calculation engine** — untouched
- **Customer portal** — still works the same, linked to estimates
- **PDF generation** — still works the same
- **Email delivery** — still works the same
- **Change orders** — still linked to estimates (no change needed)
- **Materials database** — untouched
- **Calendar system** — will need to reference estimates instead of jobs for scheduled items
- **Crew/employee management** — untouched, crews now assigned to estimates
- **Three-tier notes on estimates** — untouched
- **Estimate templates** — untouched

---

## Implementation Approach

This is a large restructure. Recommended sub-sprint breakdown:

### Sub-sprint A: Schema Migration + Backend
- New migration: add fields to contacts and estimates
- Data migration: copy from jobs to contacts/estimates
- New/modified API endpoints for contacts (client profiles)
- Update estimate endpoints to handle job-phase fields
- Pipeline board endpoints: contacts for lead/sales, estimates for jobs
- Internal approve endpoint
- Deposit invoice endpoint
- **Do NOT touch frontend yet** — backend must be solid first
- **Target: all existing tests updated and passing**

### Sub-sprint B: Frontend — Client Profile Page
- Rename Contact Detail → Client Profile
- Add new tabs (Estimates, Jobs, Invoices, Activity)
- Add summary cards
- Add lead source + client type fields
- "+ Create Estimate" from within client profile
- Wire up pipeline stage display

### Sub-sprint C: Frontend — Pipeline & Navigation Updates
- Update sidebar labels
- Lead Pipeline → shows contacts, opens client profile
- Sales Pipeline → shows contacts, opens client profile
- Jobs Pipeline → shows approved estimates, opens estimate detail
- Jobs List → shows approved estimates
- Update FAB and quick-create flows
- Update dashboard stats

### Sub-sprint D: Frontend — Estimate Detail Job Sections
- Conditional job sections (crew, schedule, invoices) visible when status ≥ approved
- Internal approve button
- Deposit invoice button
- Estimate status extended with job-phase values
- Calendar integration (estimates replace jobs as scheduled entities)

### Sub-sprint E: Test Suite + Cleanup
- Full test suite review and update
- Deprecate jobs table
- Remove dead code referencing old job entity
- Verify all customer-facing flows (portal, PDF, email) still work
- Verify calendar shows approved estimates correctly

---

## Risks and Mitigations

**Risk:** Migration complexity — jobs have many foreign key relationships.
**Mitigation:** Don't delete the jobs table immediately. Migrate data, redirect references, verify everything works, then deprecate in a separate step.

**Risk:** Estimate status field overloaded — it now covers both proposal lifecycle (draft → sent → approved) and job lifecycle (in_progress → complete → closed).
**Mitigation:** This is actually fine. The status values are sequential and non-overlapping. The UI just shows different sections based on which phase the status falls in.

**Risk:** Pipeline board performance — contacts in lead/sales pipelines need to show estimate counts and values, which requires joins.
**Mitigation:** The board already does joins (jobs → estimates for value totals). The join target changes but the pattern is the same.

**Risk:** Breaking customer portals.
**Mitigation:** Customer portals link directly to estimates by estimate ID. Since estimates are not being restructured (only enhanced), portals should continue working unchanged. Verify in sub-sprint E.

---

## Test Impact

Estimated test changes:
- **Job CRUD tests** — rewrite to work with contact + estimate model
- **Pipeline board tests** — update to reflect contact-based lead/sales boards and estimate-based jobs board
- **Estimate tests** — extend to cover new fields (job_type, crew, schedule, status transitions)
- **Invoice tests** — verify estimate linkage works (should be minimal change if already linked by estimate_id)
- **Calendar tests** — update to reference estimates instead of jobs
- **New tests needed:** internal approve flow, deposit invoice flow, client profile tabs, estimate status transitions through job phases

---

## Context Line for Claude Code Session

```
Read CLAUDE.md and PRD.md. Major restructure: the Job entity is being eliminated. Contact becomes "Client Profile" (add lead_source, client_type, pipeline_id, stage_id). Estimates gain job-phase fields (job_type, work_type, crew_id, schedule dates, approved_at). An approved estimate IS a job — no separate entity. Lead/Sales pipelines track contacts. Jobs pipeline tracks approved estimates. See restructure spec for full details. Current state: Sprints 1–14.5 complete, 422+ tests, production deployed to Azure. Latest migration: 0017.
```

---

## Acceptance Criteria (Overall)

- [ ] Contacts table has lead_source, client_type, pipeline_id, stage_id fields
- [ ] Estimates table has job_type, work_type, location_address, crew_id, schedule fields, approved_at, approved_by
- [ ] All existing job data migrated to contacts and estimates
- [ ] Client Profile page shows: contact info, lead source, client type, estimate list, jobs list, invoices
- [ ] Lead Pipeline shows contacts, clicking opens client profile
- [ ] Sales Pipeline shows contacts, clicking opens client profile
- [ ] Jobs Pipeline shows approved estimates, clicking opens estimate detail with job sections
- [ ] Estimate detail shows job sections (crew, schedule, invoices) when status ≥ approved
- [ ] Internal approve button works on sent/viewed estimates
- [ ] Deposit invoice can be created from non-approved estimates
- [ ] Archived/rejected estimates visible in collapsed section on client profile
- [ ] Calendar shows approved estimates (not jobs) as scheduled items
- [ ] All customer portals still work (estimate portal, change order portal)
- [ ] All PDF generation still works
- [ ] All email delivery still works
- [ ] 422+ tests passing (updated for new model)
- [ ] Jobs table deprecated (data preserved, not actively used)
