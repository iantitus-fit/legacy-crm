# Legacy CRM — Sprint 20: AccuLynx Parity Sprint

## Why This Sprint

This sprint closes the remaining gaps between Legacy CRM and what Dale/Marcus use daily in AccuLynx + DripJobs. After Sprint 20, a contractor could switch to Legacy CRM without losing any daily-use functionality. None of these features require client input — all specs come from the March 13 call transcript, the AccuLynx audit, and DripJobs screenshots.

**Gaps being closed:**
1. Photo/file uploads on jobs, contacts, and estimates
2. Document storage with folder organization
3. Work orders (standard + secret) generated from estimates
4. Public booking form for lead intake

---

## Sub-Sprint Structure

- **20a** — File upload infrastructure + photo/document management (backend + frontend)
- **20b** — Work orders: standard + secret, PDF generation, email send
- **20c** — Public booking form for lead intake

---

## 20a — File Uploads + Photo/Document Management

### Migration 0029: files table

```sql
CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    -- Polymorphic attachment: a file belongs to ONE of these entities
    contact_id INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    estimate_id INTEGER REFERENCES estimates(id) ON DELETE CASCADE,
    
    filename VARCHAR(500) NOT NULL,           -- original filename
    stored_filename VARCHAR(500) NOT NULL,    -- UUID-based filename on disk/blob
    mime_type VARCHAR(100) NOT NULL,
    file_size INTEGER NOT NULL,               -- bytes
    
    folder VARCHAR(100) DEFAULT 'General',    -- folder name for organization
    -- Default folders from AccuLynx: General, Contracts, Estimates, 
    -- Insurance Documents, Job Paperwork, Roof Report, Photos
    
    description TEXT,                         -- optional caption/notes
    is_photo BOOLEAN NOT NULL DEFAULT false,  -- quick filter for photo gallery view
    
    -- Visibility toggles (from Marcus's call — photo visibility controls)
    show_in_work_order BOOLEAN NOT NULL DEFAULT false,
    show_in_estimate BOOLEAN NOT NULL DEFAULT false,
    -- If both false = company only (internal)
    
    uploaded_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure file belongs to exactly one entity
    CONSTRAINT file_one_entity CHECK (
        (contact_id IS NOT NULL)::int +
        (job_id IS NOT NULL)::int +
        (estimate_id IS NOT NULL)::int = 1
    )
);

CREATE INDEX idx_files_contact ON files(contact_id) WHERE contact_id IS NOT NULL;
CREATE INDEX idx_files_job ON files(job_id) WHERE job_id IS NOT NULL;
CREATE INDEX idx_files_estimate ON files(estimate_id) WHERE estimate_id IS NOT NULL;
```

### File Storage

**Local storage first** (production path: `/app/uploads/`). Files stored as UUID-named files to avoid collisions. Served via a static file endpoint or a dedicated download route that checks auth.

Future upgrade path: Azure Blob Storage. But local filesystem works on the B1 App Service container and avoids adding Azure SDK complexity now. The `stored_filename` field makes migration to blob storage a backend-only change later.

### API Endpoints (`routers/files.py`)

```
# Upload
POST   /api/files/upload                    — multipart form: file + entity_type + entity_id + folder + description + visibility flags
                                              Returns file metadata. Max 10MB per file.

# List/Get
GET    /api/files?entity_type=job&entity_id=5&folder=Photos  — list files for an entity, filterable by folder
GET    /api/files/{id}                       — file metadata
GET    /api/files/{id}/download              — serve the actual file (auth required)
GET    /api/files/folders?entity_type=job&entity_id=5         — list folders with file counts for an entity

# Update/Delete  
PUT    /api/files/{id}                       — update description, folder, visibility toggles
DELETE /api/files/{id}                       — delete file + remove from disk

# Bulk
POST   /api/files/upload-multiple            — upload multiple files at once (same entity)
```

### Frontend

**FilesTab component** (reusable across ContactDetailPage, JobDetailPage, EstimateDetailPage):

- Folder sidebar: list of folders with file counts. Click to filter. "All Files" at top. "+ New Folder" button (just creates a file with that folder name — folders are implicit from file data, not a separate table).
- File grid/list toggle: grid shows thumbnails for images, icons for other file types. List shows filename, size, date, uploader.
- Upload zone: drag-and-drop area + "Upload" button. Supports multiple files. Folder selector dropdown. Description field. Visibility checkboxes (show in work order, show in estimate).
- Photo gallery mode: when viewing the Photos folder, show a lightbox-style gallery with larger previews.
- Each file card: thumbnail/icon, filename, folder tag, size, date, description preview. Actions: download, edit (description/folder/visibility), delete with confirmation.

**Add "Files" tab** to:
- ContactDetailPage (between existing tabs)
- JobDetailPage (if not already tabbed, add tab navigation)
- EstimateDetailPage (between existing tabs)

**Default folders** seeded in the UI dropdown:
- General, Contracts, Estimates, Insurance Documents, Job Paperwork, Roof Report, Photos

### Tests (target: 25-30)

- Upload: single file, multiple files, 10MB limit enforcement, mime type detection
- List: filter by entity, filter by folder, is_photo filter
- Download: auth required, 404 on missing
- Update: change folder, toggle visibility
- Delete: file removed from disk + DB
- Constraint: file must belong to exactly one entity
- Folder listing with counts

---

## 20b — Work Orders

### What Marcus described (from March 13 transcript):

> "We can send our work order. It has all the client information. We have an option where it shows send like a secret work order. What that'll do is only send the address and the job details and the PO. It will remove all their contact info. So if we have like a subcontractor we may not trust or something, they don't have the client's info."

### Data Model

No new table needed. A work order is a **rendered view** of an existing estimate — similar to how the PDF export works. It's a PDF generation + email send feature, not a separate entity.

Add to estimates table (migration 0029 or separate 0030):

```sql
ALTER TABLE estimates ADD COLUMN work_order_number VARCHAR(50);
-- Auto-generated on first work order send: "WO-{estimate_number}"
```

### API Endpoints (add to `routers/estimates.py` or new `routers/work_orders.py`)

```
# Generate work order PDF
GET    /api/estimates/{id}/work-order?secret=false     — generate standard work order PDF
GET    /api/estimates/{id}/work-order?secret=true      — generate secret work order PDF (strips contact info)

# Send work order
POST   /api/estimates/{id}/work-order/send             — email work order PDF
       Body: { "recipient_email": "...", "secret": false, "message": "..." }

# View work order (like customer view but for crew)
GET    /api/work-orders/{token}                        — public work order view (token-based, no auth)
```

### Work Order PDF Content

**Standard Work Order:**
- Company header (Legacy Roofing & Exteriors branding)
- Work Order number (WO-{estimate_number})
- Customer name, address, phone, email
- Job address (if different from customer)
- Line items with descriptions (from estimate)
- Scope of work sections
- Photos marked as `show_in_work_order=true` (from 20a)
- Notes marked as crew-visible
- NO pricing (no line item prices, no subtotals, no totals)

**Secret Work Order:**
- Company header
- Work Order number
- Job address ONLY (no customer name, phone, or email)
- Line items with descriptions
- Scope of work sections
- Photos marked as `show_in_work_order=true`
- Crew notes
- NO pricing, NO customer contact info

### Frontend

**Add to EstimateDetailPage** (matches DripJobs UI — the "Work Order" dropdown button):

Work Order dropdown button with options:
- "Send Work Order" → modal: recipient email, optional message, [Send] button
- "View Work Order" → opens PDF in new tab
- "Copy Link" → copies public work order URL
- "Send Secret Work Order" → same modal but secret=true
- "View Secret Work Order" → opens secret PDF in new tab  
- "Copy Secret Link" → copies secret work order URL

### Tests (target: 15-20)

- Standard work order PDF: includes customer info, no pricing
- Secret work order PDF: no customer info, no pricing
- Work order send: email delivered with PDF attachment
- Public work order view: accessible without auth via token
- Photos with show_in_work_order=true appear in work order
- Photos with show_in_work_order=false excluded

---

## 20c — Public Booking Form

### What it does

A public-facing form (no login required) that creates a new contact in the Leads pipeline when submitted. This is how leads come in from the website, Google Ads landing pages, door hangers, etc.

### API Endpoint

```
POST   /api/public/booking                   — no auth required
       Body: {
           "first_name": "required",
           "last_name": "required", 
           "phone": "required",
           "email": "optional",
           "address": "optional",
           "service_type": "optional",       -- "Roofing", "Siding", "Gutters", etc.
           "message": "optional",            -- free text
           "lead_source": "optional"         -- defaults to "Website" if not specified
       }
       
       Response: { "success": true, "message": "Thank you! We'll be in touch shortly." }
```

**On submit, the backend:**
1. Creates a Contact record
2. Creates a Job in the Leads pipeline, stage "New Lead" (or first stage)
3. Sets lead_source from form or defaults to "Website"
4. Fires `on_contact_created` trigger → enrolls in New Lead Nurture automation sequence
5. Fires `auto_respond_new_lead` → immediate SMS (if SMS_ENABLED=true)
6. Sends notification email to company (reuse existing estimate notification pattern)

### Rate Limiting + Spam Protection

- Rate limit: 5 submissions per IP per hour (simple in-memory or DB counter)
- Honeypot field: hidden `website` field that bots fill — if populated, silently reject
- No CAPTCHA for now (adds friction for homeowners on mobile)

### Frontend — Embeddable Form

Two delivery modes:

**1. Standalone page** at `/book` (public route, no auth):
- Clean, branded form with Legacy Roofing header
- Mobile-optimized (homeowners will hit this from their phone after seeing a door hanger or ad)
- Fields: First Name, Last Name, Phone, Email (optional), Address (optional), Service Needed (dropdown: Roofing, Siding, Gutters, Painting, Other), Message (optional)
- Submit → "Thank you" confirmation with "We'll be in touch within 24 hours"

**2. Embeddable widget** (future — not this sprint):
- iframe-able version for embedding on contractor websites
- Defer until Legacy website rewrite or white-label demand

### Lead Source Tracking via URL Parameters

The booking form should read `?source=` from the URL and set lead_source accordingly:
- `/book?source=google_lsa` → lead_source = "Google LSA"
- `/book?source=facebook` → lead_source = "Facebook"  
- `/book?source=door_hanger` → lead_source = "Door Hanger"
- `/book?source=referral` → lead_source = "Referral"
- No parameter → lead_source = "Website"

This lets Dale put different URLs on different marketing channels and automatically track attribution.

### Tests (target: 15-20)

- Form submission creates contact + job in leads pipeline
- Lead source from URL parameter
- Lead source defaults to "Website"
- Rate limiting blocks after 5 submissions per IP
- Honeypot field rejects bot submissions
- on_contact_created trigger fires (automation enrollment)
- auto_respond_new_lead fires
- Company notification sent
- Validation: first_name, last_name, phone required
- Public endpoint: no auth required

---

## Acceptance Criteria

### 20a — Files
- [ ] Migration 0029 creates files table with entity constraint
- [ ] File upload (single + multiple) with 10MB limit
- [ ] Folder organization with default folders
- [ ] Photo gallery view
- [ ] Visibility toggles (show_in_work_order, show_in_estimate)
- [ ] FilesTab on Contact, Job, and Estimate detail pages
- [ ] Download requires auth
- [ ] Delete removes from disk + DB

### 20b — Work Orders
- [ ] Standard work order PDF with customer info, no pricing
- [ ] Secret work order PDF without customer info or pricing
- [ ] Work order email send with PDF attachment
- [ ] Public work order view via token (no auth)
- [ ] Photos with show_in_work_order=true included in PDF
- [ ] Work Order dropdown on EstimateDetailPage (matches DripJobs UI)

### 20c — Booking Form
- [ ] Public booking form at /book (no auth)
- [ ] Creates contact + job in Leads pipeline on submit
- [ ] Lead source from ?source= URL parameter
- [ ] Triggers automation enrollment + SMS auto-response
- [ ] Company notification on submission
- [ ] Rate limiting (5/hour/IP) + honeypot spam protection
- [ ] Mobile-optimized, branded

---

## Claude Code Context Line

```
Read CLAUDE.md and PRD.md. Sprints 1–19 are complete. 861 tests passing. Latest migration: 0028. Deploy via ./scripts/deploy.sh (uses buildx for amd64). SMS built but SMS_ENABLED=false on production. Automation engine deployed with 5 seed sequences.

Sprint 20: AccuLynx Parity — Photos/Documents, Work Orders, Booking Form. Spec at docs/superpowers/specs/legacy_crm_sprint20_parity_spec.md. Start with 20a (file upload infrastructure + photo/document management). Follow the sub-sprint pattern: 20a → 20b → 20c. Commit, push, and confirm tests after each sub-sprint.
```

---

## Estimated Build Time

- 20a: ~25 min (file upload + folder UI — moderate complexity, new infrastructure)
- 20b: ~20 min (work order PDF generation follows existing PDF patterns from Sprint 11)
- 20c: ~15 min (booking form — simple public endpoint + single-page form)

**Total estimate: ~60 minutes Claude Code time**

---

## Risk Notes

1. **File storage on Azure B1.** The App Service container has ephemeral local storage — files saved to the container filesystem will be lost on restart/redeploy. Mitigation: mount an Azure Files share or Azure Blob Storage. For now, files survive within a container lifecycle. This needs to be solved before production photo usage, but it's a deployment config change, not a code change. Flag it during deploy.

2. **10MB file limit** is conservative for job site photos from modern phones (often 5-8MB each). Should be sufficient for most cases. Raise to 25MB if contractors hit the limit.

3. **Booking form spam** without CAPTCHA is a risk if the URL gets scraped. The honeypot + rate limit should handle casual bots. If spam becomes a problem, add reCAPTCHA v3 (invisible) in a follow-up.

4. **Work order PDFs** reuse the WeasyPrint infrastructure from Sprint 11 estimate PDFs. Same dependency, same patterns. Low risk.
