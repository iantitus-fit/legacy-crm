# Legacy CRM — Sprint 16a Spec: CSV Contact Importer

**Date:** April 29, 2026
**Priority:** HIGH — unlocks data migration for AccuLynx, DripJobs, Salesforce, and any CSV-exporting CRM
**Estimated build time:** 45-75 min (AI-assisted)
**Dependencies:** None — works with existing contacts schema

---

## Why This Sprint

Data migration is the #1 switching barrier for roofing companies considering a CRM change. A Three Stone Roofing contact (8,000+ customers, uses AccuLynx + Salesforce) independently confirmed this. Every prospect will ask "can I bring my existing data?" and the answer needs to be yes.

This sprint builds a generic CSV importer with field mapping UI and a dry-run preview mode. It works with AccuLynx exports, DripJobs exports, Salesforce exports, and any other CSV/Excel source. The dry-run mode lets prospects test the migration path without importing anything, which is a sales tool as much as a feature.

---

## Current Contact Schema (Target)

These are the fields the importer maps into:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | string | YES | Full name — importer should handle "First Last" or separate first/last columns |
| email | string | no | |
| phone | string | no | |
| company | string | no | |
| address | string | no | Street address |
| city | string | no | |
| state | string | no | |
| zip_code | string | no | |
| lead_source | string | no | Auto-set to "CSV Import" if not mapped |
| client_type | string | no | "residential" or "commercial" — auto-detect or let user set default |
| notes | text | no | Catch-all for unmapped columns user wants to preserve |

Fields NOT imported (system-managed): id, pipeline_id, stage_id, created_at, updated_at

---

## Feature Spec

### Backend

#### New endpoint: POST /api/import/contacts/preview

Accepts multipart file upload (CSV or XLSX). Returns a preview payload without writing to DB.

**Request:** multipart/form-data with file field

**Processing:**
1. Parse file (CSV with auto-detected delimiter, or XLSX first sheet)
2. Read first 100 rows to detect columns
3. Auto-suggest field mappings based on column header names (fuzzy match):
   - "name", "full name", "full_name", "contact name", "customer name" → name
   - "first name", "first_name", "fname" → first_name (will be combined with last_name)
   - "last name", "last_name", "lname" → last_name
   - "email", "e-mail", "email address", "primary contact: email" → email
   - "phone", "phone number", "mobile", "cell", "primary contact: phone" → phone
   - "company", "company name", "business name" → company
   - "address", "street", "street address", "address line 1" → address
   - "city" → city
   - "state", "st" → state
   - "zip", "zip code", "zipcode", "postal code", "zip_code" → zip_code
   - "source", "lead source", "lead_source" → lead_source
   - "type", "client type", "client_type", "contact type" → client_type
   - "notes", "note", "comments" → notes
4. Detect potential duplicates against existing contacts (match on email OR phone OR exact name+address)
5. Count stats: total rows, rows with email, rows with phone, rows with name, potential duplicates, empty/malformed rows skipped

**Response (200):**
```json
{
  "file_name": "acculynx_export.csv",
  "total_rows": 8247,
  "importable_rows": 8103,
  "skipped_rows": 144,
  "skip_reasons": {
    "no_name": 89,
    "empty_row": 55
  },
  "potential_duplicates": 23,
  "columns_detected": ["Name", "Phone", "Email", "Address", "City", "State", "Zip", "Lead Source", "Notes"],
  "suggested_mappings": {
    "Name": "name",
    "Phone": "phone",
    "Email": "email",
    "Address": "address",
    "City": "city",
    "State": "state",
    "Zip": "zip_code",
    "Lead Source": "lead_source",
    "Notes": "notes"
  },
  "unmapped_columns": ["Job Type", "Salesperson", "Created Date"],
  "sample_rows": [
    {"Name": "John Smith", "Phone": "(765) 555-1234", "Email": "john@example.com", "Address": "123 Main St", "City": "Kokomo", "State": "IN", "Zip": "46901", "Lead Source": "Angi", "Notes": ""},
    // ... first 25 rows
  ],
  "preview_token": "abc123..."
}
```

The `preview_token` is a short-lived reference (stored in Redis/memory/temp file) to the parsed data so the confirm step doesn't require re-uploading.

**Error cases:**
- File too large (>50MB): 413
- Unsupported format (not CSV/XLSX): 400
- No parseable rows: 400 with message
- No "name" column detectable: 200 but with warning flag

---

#### New endpoint: POST /api/import/contacts/confirm

Accepts the preview_token plus user-confirmed field mappings and options. Writes to DB.

**Request body:**
```json
{
  "preview_token": "abc123...",
  "field_mappings": {
    "Name": "name",
    "Phone": "phone",
    "Email": "email",
    "Address": "address",
    "City": "city",
    "State": "state",
    "Zip": "zip_code",
    "Lead Source": "lead_source",
    "Job Type": "notes",
    "Notes": "notes",
    "Salesperson": null,
    "Created Date": null
  },
  "options": {
    "default_client_type": "residential",
    "default_lead_source": "CSV Import",
    "duplicate_handling": "skip",
    "combine_unmapped_to_notes": true,
    "pipeline_id": null,
    "stage_id": null
  }
}
```

**Options explained:**
- `default_client_type`: Applied to all imported contacts unless a client_type column is mapped
- `default_lead_source`: Applied when lead_source column is not mapped or is empty. Defaults to "CSV Import"
- `duplicate_handling`: "skip" (don't import duplicates), "import" (import all, create duplicates), "merge" (update existing with new non-empty fields) — v1 supports "skip" and "import" only, "merge" is v2
- `combine_unmapped_to_notes`: If true, any column mapped to "notes" gets concatenated into a single notes field with labels: "Job Type: Residential\nSalesperson: Josh\nNotes: Called 3x, no answer"
- `pipeline_id` / `stage_id`: Optional — place all imported contacts into a specific pipeline stage (e.g., "Imported Leads" stage)

**Processing:**
1. Retrieve parsed data from preview_token
2. Apply user-confirmed mappings
3. Handle first_name + last_name → name combination if both mapped
4. Phone normalization: strip non-digits, validate length, store as-is for display
5. Email validation: basic format check, skip row's email field (not whole row) if invalid
6. Duplicate check based on duplicate_handling setting
7. Batch insert contacts (SQLAlchemy bulk_save_objects, commit every 500 rows for large imports)
8. Log import event: user, timestamp, file_name, total_imported, total_skipped, total_duplicates

**Response (200):**
```json
{
  "imported": 8080,
  "skipped_duplicates": 23,
  "skipped_invalid": 144,
  "total_processed": 8247,
  "import_id": "uuid...",
  "duration_seconds": 12.4
}
```

---

#### New endpoint: GET /api/import/history

Returns past imports for audit trail. Paginated.

**Response includes:** import_id, user, file_name, timestamp, total_imported, total_skipped, duration

---

#### New endpoint: POST /api/import/contacts/{import_id}/undo

Soft-deletes all contacts created by a specific import. Safety net for mistakes.

**Processing:** Sets a `deleted_at` timestamp on all contacts where `import_id` matches. Does not hard delete.

**Requires:** New `import_id` UUID column on contacts table (nullable). Set during import, null for manually-created contacts.

---

### Database Changes

**Migration 0024: import_contacts**

```
contacts table (add columns):
├── import_id (UUID, nullable, index) — links to the import batch that created this contact
├── import_source_file (string, nullable) — original filename for reference
├── deleted_at (timestamp, nullable) — soft delete support for undo

contact_imports table (new):
├── id (UUID, PK)
├── user_id (FK → users)
├── file_name (string)
├── total_rows (int)
├── imported_count (int)
├── skipped_count (int)
├── duplicate_count (int)
├── field_mappings (JSON) — stored for audit
├── options (JSON) — stored for audit
├── duration_seconds (float)
├── created_at (timestamp)
```

---

### Frontend

#### New page: /settings/import (or /import)

Accessible from Settings sidebar or a prominent "Import Contacts" button on the Client Profiles page.

**Step 1 — Upload**
- Drag-and-drop zone or file picker
- Accepts .csv, .xlsx, .xls
- File size limit displayed: 50MB max
- "Upload & Preview" button
- Loading state while backend parses

**Step 2 — Map Fields**
- Left column: detected CSV column headers with a sample value from row 1
- Right column: dropdown selector for each, populated with Legacy CRM contact fields + "Skip this column" + "Add to Notes"
- Auto-suggested mappings pre-selected (user can change any)
- If first_name and last_name both detected, show note: "These will be combined into a single Name field"
- Warning banner if no "name" column is mapped

**Step 3 — Preview & Options**
- Stats bar: "8,247 rows detected · 8,103 importable · 23 potential duplicates · 144 will be skipped (no name)"
- Sample table showing first 25 rows with the mapped field names as column headers
- Rows with potential duplicates highlighted in amber
- Options panel:
  - Default client type: dropdown (residential / commercial)
  - Default lead source: text input, pre-filled with "CSV Import"
  - Duplicate handling: radio (Skip duplicates / Import all)
  - Place in pipeline: optional dropdown (none / select pipeline + stage)
- "Import [8,103] Contacts" button (purple, primary)
- "Cancel" button

**Step 4 — Results**
- Success banner: "Imported 8,080 contacts in 12 seconds"
- Summary: imported, skipped, duplicates
- "View Imported Contacts" button → Client Profiles page filtered by this import_id
- "Undo Import" button (red, with confirmation modal: "This will remove all 8,080 contacts from this import. Are you sure?")

**Import History** (below the upload area or as a tab)
- Table of past imports: date, user, file, imported count, duration
- Each row has "View Contacts" and "Undo" buttons

---

## AccuLynx-Specific Notes

AccuLynx export comes from Reports → Jobs Report → Download CSV. The columns the user selects determine what's in the file. Common columns from AccuLynx:

- Primary Contact: Name
- Primary Contact: Phone
- Primary Contact: Email
- Address (job address, which is usually the contact address)
- City, State, Zip
- Lead Source
- Salesperson
- Job Status
- Created Date

The fuzzy column matcher should handle "Primary Contact: Name" → name, "Primary Contact: Phone" → phone, etc. The colon-prefixed format is AccuLynx-specific but common enough that the matcher should account for it.

---

## DripJobs-Specific Notes

DripJobs contact export format TBD — will need Marcus's sample export to confirm column names. The generic importer should handle it regardless.

---

## Salesforce-Specific Notes

Salesforce exports from Reports as CSV. Column names are the Salesforce field labels, which are often customized per org. Common defaults:

- Full Name (or First Name + Last Name)
- Email
- Phone, Mobile Phone, Home Phone
- Mailing Street, Mailing City, Mailing State, Mailing Zip
- Lead Source
- Account Name (= company)
- Description (= notes)

The mapper handles all of these through fuzzy matching plus user override.

---

## Test Requirements

| Test | Description |
|------|-------------|
| test_preview_csv_upload | Upload valid CSV, get preview with stats and mappings |
| test_preview_xlsx_upload | Upload valid XLSX, get preview |
| test_preview_auto_mapping | Column headers like "Email", "Phone" auto-map correctly |
| test_preview_acculynx_format | "Primary Contact: Name" maps to name field |
| test_preview_first_last_name | first_name + last_name detected and flagged for combination |
| test_preview_empty_file | Empty file returns 400 |
| test_preview_no_name_column | Returns 200 with warning when no name column detected |
| test_preview_sample_rows | Sample rows limited to 25 |
| test_preview_large_file_stats | File with 1000+ rows returns correct counts |
| test_confirm_imports_contacts | Confirm with valid token creates contacts in DB |
| test_confirm_applies_mappings | Mapped columns land in correct contact fields |
| test_confirm_combines_names | first_name + last_name merged into name |
| test_confirm_default_client_type | Default client_type applied when not mapped |
| test_confirm_default_lead_source | Default lead_source applied when column empty |
| test_confirm_skip_duplicates | Duplicate contacts skipped when option set |
| test_confirm_import_duplicates | Duplicate contacts imported when option set |
| test_confirm_combine_notes | Unmapped columns concatenated into notes field |
| test_confirm_sets_import_id | All imported contacts have matching import_id |
| test_confirm_invalid_token | Expired/invalid token returns 400 |
| test_confirm_phone_normalization | Phone stored as-is but validated |
| test_confirm_email_validation | Invalid emails skipped, row still imported |
| test_import_history | GET history returns past imports |
| test_undo_import | Undo soft-deletes all contacts from import |
| test_undo_only_affects_import | Undo doesn't touch manually-created contacts |
| test_unauthorized_access | All endpoints require auth |

25 tests minimum.

---

## Anti-Patterns

- Do NOT modify existing contact CRUD endpoints — the importer uses its own bulk insert path
- Do NOT build AccuLynx-specific logic — the importer is generic CSV, the fuzzy matcher handles vendor-specific headers
- Do NOT require all fields — name is the only required field, everything else is optional
- Do NOT hard delete on undo — soft delete with deleted_at timestamp
- Do NOT parse entire file into memory for large files — stream/chunk for files > 10,000 rows
- Do NOT skip the preview step — every import must go through upload → preview → confirm

---

## Verification Checklist

1. Upload CSV → see preview with auto-mapped columns
2. Upload XLSX → same behavior
3. Adjust field mappings → changes reflected in preview table
4. Click Import → contacts created in database
5. View imported contacts on Client Profiles page
6. Undo import → contacts soft-deleted
7. Import history shows past imports
8. Duplicate detection works (skip mode)
9. First + Last name columns combine correctly
10. Unmapped columns concatenate into notes when option selected
11. AccuLynx-format headers ("Primary Contact: Name") auto-map
12. 8,000+ row file imports in under 30 seconds
13. All existing tests still pass
14. 25+ new tests pass

---

## Context Line for Claude Code Session

```
Read CLAUDE.md. Sprints 1–15.6 complete. 489 tests passing, 0 errors. Latest migration: 0023. Production deployed to Azure. Deploy via ./scripts/deploy.sh. Build Sprint 16a: CSV Contact Importer with dry-run preview. Spec: legacy_crm_sprint16a_spec.md
```
