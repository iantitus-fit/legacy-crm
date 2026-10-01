# Legacy CRM — Roofing & Exterior Contractor Business Management System

## Project Overview

A custom CRM built for a two-person roofing and exteriors contractor in Kokomo, Indiana (Legacy Roofing & Exteriors) and a partner painting company. It was built to replace AccuLynx ($585/month) and DripJobs ($250/month), $835/month combined, with one self-hosted system on Azure (~$35-45/month).

The users (owner Dale and operations lead Marcus in this copy; names are stand-ins) are contractors, not developers. The system must be simple, reliable, and match the workflows they already use. They will not troubleshoot technical issues. The developer (Ian) manages the system.

**This is the public portfolio copy.** Customer data, people's names, phone numbers, addresses and supplier pricing are synthetic. See `README.md` and `data/README.md`. The production deployment was torn down in August 2026; no URL is live.

## Where to look first

| Question | Open | Rule |
|---|---|---|
| What does a change to estimates, change orders, invoices or payments hit (the system map) | `map/CLAUDE.md` | catalog, then one card, never the whole objects/ folder; `map/VERIFICATION.md` is the open work list |
| How to run it and load sample data | `README.md` | |
| How a feature was specified before it was built | `docs/` (sprint specs and plans) | |

**Self-maintenance:** if a task changes a file cited by a `map/` card, update that card's citation and Checked date, or mark it stale. If it settles an entry in `map/VERIFICATION.md`, remove the entry.

## Tech Stack

- **Backend:** Python 3.12 (3.13 also works), FastAPI, SQLAlchemy 2.x, Alembic (migrations)
- **Database:** PostgreSQL 16
- **Frontend:** React 18 (Vite), Tailwind CSS
- **Auth:** JWT (python-jose + passlib)
- **PDF Generation:** WeasyPrint + Jinja2 templates
- **Rich Text:** react-quill-new (line item descriptions, section descriptions)
- **Email:** smtplib (Gmail App Passwords via SMTP)
- **Containerization:** Docker, Docker Compose
- **Production:** Azure App Service (B1 Linux), Azure PostgreSQL Flexible Server (B1ms), Azure Container Registry Basic — all Central US
- **Deploy:** `./scripts/deploy.sh` (git push + Docker build + ACR push + app restart)

## Current State

**952 tests at the time of the public copy (run `pytest` for the current count).** Migrations in `backend/alembic/versions/`. Production ran on Azure until August 2026. 1,550 materials imported from supplier price lists via OCR.

### Data Model (Post-Restructure)

The data model was restructured in April 2026. The key change: **Contact = Client Profile, Estimate = Proposal (and when approved = Job).** The `jobs` table is no longer where job-phase data lives, but it is still load-bearing: every estimate requires a `job_id` and every invoice has a NOT NULL `job_id`. All new job-phase fields go on estimates; job rows remain the parent record (see `map/objects/record/job.md` where the map exists).

**Contact** holds client-level data: name, email, phone, address, company, lead_source, client_type, pipeline_id, stage_id. Lead and Sales pipelines show contacts on their boards.

**Estimate** holds both proposal data AND job-phase data: line items, sections, display settings, tax configuration, AND job_type, work_type, crew_id, scheduled_start/end, assigned_to, approved_at/by, pipeline_id, stage_id. The Jobs pipeline shows approved estimates on its board.

### Core Tables

- **users** — id, email, full_name, password_hash, role (admin/staff), phone, color, is_active, theme_preference, created_at
- **contacts** — id, name, email, phone, address, city, state, zip, company, lead_source, client_type, pipeline_id, stage_id, created_at
- **pipelines** — id, name, slug (leads/sales/jobs), sort_order
- **pipeline_stages** — id, pipeline_id (FK), name, slug, color, sort_order
- **estimates** — id, job_id (FK, legacy), contact_id, name, status (draft/sent/viewed/approved/rejected/changes_requested), subtotal, tax, tax_rate, tax_included, total, show_quantities, show_unit_prices, show_line_totals, show_subtotal, deposit_percent, expiration_date, job_type, work_type, crew_id, location_address, scheduled_start, scheduled_end, assigned_to, approved_at, approved_by, pipeline_id, stage_id, created_by, created_at
- **estimate_line_items** — id, estimate_id (FK), section_id (FK nullable), description, qty, unit_price, line_total, body (HTML rich text), notes, sort_order
- **estimate_sections** — id, estimate_id (FK), name, description (HTML), sort_order
- **estimate_templates** — id, name, description, items (with calculation engine: waste%, margin%, measurement_type, conversion_factor)
- **estimate_tokens** — id, estimate_id (FK), token (unique), created_by, created_at, expires_at
- **estimate_signatures** — id, estimate_id (FK), signer_name, signature_data (base64), signed_at, ip_address, terms_accepted
- **estimate_status_history** — id, estimate_id (FK), status, changed_at, changed_by_name, ip_address, notes
- **change_orders** — id, estimate_id (FK), co_number, name, status, subtotal, tax, total, created_at, created_by
- **change_order_items** — id, change_order_id (FK), description, qty, unit_price, line_total, body, notes, sort_order
- **change_order_tokens** — same pattern as estimate_tokens
- **change_order_signatures** — same pattern as estimate_signatures
- **invoices** — id, estimate_id (FK), invoice_number (unique, INV-XXXX), status, is_deposit, date_invoiced, due_date, subtotal, tax, tax_rate, total, amount_paid, balance, notes, created_by
- **invoice_items** — id, invoice_id (FK), description, qty, unit_price, line_total, body, sort_order, source_type (estimate/change_order), source_co_number
- **payments** — id, invoice_id (FK), amount, payment_date, method, reference_number, notes, is_deposit, created_by
- **materials** — id, description, category, subcategory, unit_type, unit_cost, supplier, sku, flagged, notes
- **tasks** — id, job_id (FK), title, status, due_date, assigned_to, created_at
- **documents** — id, job_id (FK nullable), contact_id (FK nullable), filename, filepath, file_type, file_size, created_at
- **notes** — id, entity_type (job/contact/estimate), entity_id, note_type (company/crew/client), content, created_by, created_at
- **crews** — id, name, color, created_at + crew_members junction table
- **appointments** — id, title, contact_id (FK), assigned_to (FK), date, start_time, duration_minutes, type, location, notes
- **jobs** — (DEPRECATED) id, contact_id, stage_id, job_type, work_type, property_address, contract_value, etc.
- **leads** — id, contact_id, stage_id, source, description, assigned_to

### Latest Migration

Migration `0023` — adds `tax_included` BOOLEAN to estimates. All migrations are in `backend/alembic/versions/`.

## Features Shipped

### Full Estimate-to-Payment Lifecycle
- Estimates with line items, sections, rich text descriptions (font size, highlight, bold/italic/lists), display settings, three-tier notes (company/crew/client)
- Estimate templates with materials picker and calculation engine (waste/margin/measurement-based quantities)
- Per-estimate tax toggle: tax exclusive (roofing, calculated on top) or tax inclusive (painting, included in price). Auto-defaults based on work_type.
- Branded PDF export (WeasyPrint + Jinja2) with logo, sections, scope of work, line items, totals, signature block
- Customer portal — public-facing estimate view via unique token link, no login required
- Digital signatures — HTML5 canvas capture, terms acceptance, payment schedule acknowledgment
- Estimate status tracking: draft → sent → viewed → approved → rejected → changes_requested
- Status history audit trail with timestamp, IP, notes
- Company email notifications on all customer actions
- Signed PDFs — customer signature embedded after approval
- Auto-pipeline move on approval (estimate moves to Jobs pipeline)

### Change Orders
- Create from approved estimates, auto-numbered (#1, #2, etc.)
- Separate public portal with digital signature and terms acceptance
- CO PDF generation with signature rendering
- Acceptance date badges displayed inline on estimate detail page
- Grand total = estimate total + sum of approved CO totals

### Invoices & Payments
- Auto-generated from estimates + approved change order items
- Sequential numbering (INV-0001, INV-0002)
- Deposit invoices with configurable percentage
- Payment recording: date, amount, method, reference, notes, deposit flag
- Auto-status transitions: draft → partial → paid
- Payment receipt emails
- Void invoice protection

### Client Profiles (Post-Restructure)
- Contact = Client Profile with summary cards (contract value, active estimates, open balance, next scheduled)
- Tabs: Estimates, Invoices, Jobs (approved estimates)
- Lead/Sales pipelines show contacts; Jobs pipeline shows approved estimates
- Create estimate directly from client profile

### Pipeline & Navigation
- Three-pipeline Kanban: Leads, Sales, Jobs — drag-and-drop, colored stages, configurable
- Dashboard with pipeline summary cards, task rows (past due/today/future), open invoices
- Global floating quick-create FAB: new lead, new estimate, new appointment, new task
- Global quick client search bar with debounced typeahead across name, phone, email, company, address

### Supporting Features
- Materials database (1,550 items from ABC Supply, OCR-imported, category filtering)
- Employee/crew management with 12 color options
- Calendar system: appointments + job schedule with crew color coding, multi-day spanning
- Three-tier notes on contacts, jobs, and estimates
- Document upload (PDF, PNG, JPG, XML) with auth-protected download
- Light/dark theming with CSS variable system, user preference saved to DB

## Design Direction

- **Theming:** Light and dark modes, user-selectable via sidebar toggle
- **Light theme:** White cards (#FFFFFF) on purple-50 background (#EDE9FE), black text
- **Dark theme:** Purple-tinted dark backgrounds (#0F0D1A / #1E1B3A), white text
- **Brand colors:** Purple (~#7C3AED primary), Teal (~#14B8A6 secondary)
- **CSS approach:** Tailwind with semantic color names backed by CSS variables (Option B). Theme defined in theme.css with 60+ variables.
- **Pipeline board:** Kanban-style with colored stage columns
- **Calendar:** Month/week view, color-coded by crew assignment
- **Responsive:** Desktop-first, mobile-functional. Marcus tests from iPhone on job sites.

## Rules (Do Not Violate)

1. **Never modify existing migration files.** Create new migration files for schema changes.
2. **Never change the data model without flagging it first.** Explain what and why before making model changes.
3. **All money values use Numeric(12,2).** Never use floats for currency.
4. **All timestamps use DateTime(timezone=True).**
5. **State defaults to "IN" (Indiana)** for new contacts.
6. **Do not introduce new frameworks** without explaining why the current stack can't handle the requirement.
7. **Keep the frontend in a single React app.** No micro-frontends, no SSR frameworks.
8. **Write tests for business logic** — especially estimate calculations, tax logic, and payment status transitions. UI tests are optional.
9. **API routes follow RESTful conventions.** Use plural nouns: /contacts, /jobs, /estimates, etc.
10. **Use Pydantic models for all API request/response validation.** No raw dicts.
11. **Verify your work.** After implementing a feature, run pytest. All existing tests must pass plus any new tests for the feature.
12. **Contact = Client Profile.** The `contacts` table is the client entity. Do not create new "client" tables.
13. **Estimate = Proposal AND Job.** When approved, an estimate IS the job. Job-phase fields (crew, schedule, work_type) live on the estimate. Do not add job-phase fields to the `jobs` table. Job rows are still required as the parent of estimates and invoices (created by lead conversion and the AccuLynx importer); do not drop or null them.
14. **Theme-aware styling.** All new frontend components must use semantic theme classes (bg-surface, text-th-text, etc.) — never hardcode colors.

## Deployment

### Production Deploy
```bash
ACR_NAME=<registry> WEB_APP_NAME=<web-app> RESOURCE_GROUP=<resource-group> ./scripts/deploy.sh
```
This runs: git push → Docker build with Dockerfile.prod → ACR login → push to registry → app restart.

### Azure CLI
`az login` must run in a standard terminal, not inside Claude Code (can't handle interactive prompts).

### Local Development
```bash
cd legacy-crm
docker compose up --build
```
Access at http://localhost:5173. Backend at http://localhost:8000.

### Database Backup
```bash
WEB_APP_NAME=<your-web-app> RESOURCE_GROUP=<your-resource-group> ./scripts/dump_prod_db.sh
```
Pulls DATABASE_URL from Azure env vars at runtime.

## Environment Variables

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/legacycrm
JWT_SECRET=<change-in-production>
CORS_ORIGINS=http://localhost:5173
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_FROM_EMAIL=<configured>
SMTP_PASSWORD=<gmail-app-password>
PORTAL_BASE_URL=<production-url-or-ngrok-url>
PORTAL_LINK_DAYS=<optional; unset = portal links never expire>
```

## Known Issues

- `test_dashboard_tasks_due_this_week` — timing-sensitive test that fails on Saturdays due to end-of-week boundary calculation. Not a real bug.
- Test fixture isolation — some test files (appointments, change_orders, change_order_portal, auth_routes, apply_template, calendar) have SQLite table creation/teardown issues in conftest.py. The tests pass when run individually but fail in full suite due to table leaking between tests. Fix is pending for conftest.py db_session fixture.
- Company info (name, address, phone) is hardcoded in PDF templates and email templates. Needs a company settings table for configurability.
- Portal link expiry is opt-in: set PORTAL_LINK_DAYS to give new links an expiry (expired links return 410).
