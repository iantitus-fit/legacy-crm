# Sprint 14: Line Item UX + Navigation Polish — Design

**Date:** 2026-04-11
**Status:** Approved, ready for implementation plan
**Scope:** UX-only sprint. No data model changes, no new pages, no calculation engine changes.

## Goal

Polish three UX pain points in the estimate/change order workflow:
1. Add Line Item flow — blank vs. from materials database
2. Duplicate line item — one-click copy
3. Consistent back-button navigation across all detail pages

## Current State (from exploration)

**Estimate line items** live on `EstimateDetailPage.jsx` (1944 lines). Adding an item
currently creates defaults (`qty=1`, `price=0`) via `handleAddItem()` → POST
`/estimates/{id}/line-items`. Editing uses `LineItemEditModal` (lines 110–258)
with fields: description, qty, unit_price, body (ReactQuill), notes, section_id.

**Change order items** reuse the same `LineItemEditModal` (sections disabled).
Backend routes live at `POST /api/change-orders/{co_id}/items`.

**Materials database** already has 1,550 rows and a complete API
(`/api/materials?search=...&category=...`) plus `frontend/src/api/materials.js`
with `listMaterials()`. It is NOT currently wired into line item creation.

**Navigation** is inconsistent: JobDetailPage and ContactDetailPage use breadcrumbs,
EstimateDetailPage has a header back button to its parent job, InvoiceDetailPage has
a hard-coded back button with no breadcrumb. There is no shared BackButton component.
There is no `EmployeeDetailPage` (employees are managed inline at `/settings/employees`),
so it is out of scope.

## Feature 1 — Add Line Item: Blank or From Materials

### UX
Replace the single "Add Item" button with a **split button / dropdown**:
- **Blank Item** — current behavior: creates a default item inline.
- **From Materials** — opens a `MaterialPickerModal` with a search typeahead.

The `MaterialPickerModal`:
- Header: search input (debounced 250ms) that queries `listMaterials({ search, perPage: 20 })`.
- Body: list of matching materials showing `item_number`, `description`, `uom`, `unit_cost`.
- Footer: Cancel button. Clicking a result closes the picker and immediately opens
  `LineItemEditModal` pre-filled:
  - `description` ← material.description
  - `unit_price` ← material.unit_cost
  - `qty` ← 1 (user will override)
  - `body`, `notes`, `section_id` ← empty / currently-selected section
- User saves as normal — the edit modal creates the line item via the existing
  `addLineItem()` + `updateLineItem()` flow (or a single create call that accepts
  all fields at once, using the existing POST endpoint which already accepts them).

### Change Order parity
The same split button appears on each change order card, opening the same
`MaterialPickerModal` but routing the pre-filled edit modal to the CO item create
path. Sections are disabled (COs are flat).

### Backend
**No changes.** `GET /api/materials?search=...` already exists and supports
pagination. The line item POST endpoints already accept all the fields we want to
pre-fill.

### Anti-scope
- No "Add Multiple Items" — Marcus explicitly rejected this.
- No optional items.
- No material linkage persisted on the line item (just copies the values at time of add).

## Feature 2 — Duplicate Line Item

### UX
Add a copy icon (`Copy` from lucide-react) to each line item row in the
`SortableRow` component. One click:
- Calls the new duplicate endpoint.
- Appends the duplicate to the end of the parent list (estimate subtotal section
  or CO) via `sort_order = max + 1`.
- No modal — instant save.
- Refreshes the estimate so totals recalculate.

The copy icon sits next to the existing edit and delete icons on each row.
Same pattern for change order item rows.

### Backend

**New endpoint:** `POST /api/estimates/{estimate_id}/line-items/{item_id}/duplicate`
- 201 response with the new line item.
- Copies: `description`, `qty`, `unit_price`, `body`, `notes`, `section_id`.
- Sets `sort_order = max(sort_order of sibling items) + 1`.
- Recalculates estimate totals (reuses existing `_recalc_estimate()` helper).
- 404 if estimate or item not found or mismatched.

**New endpoint:** `POST /api/change-orders/{co_id}/items/{item_id}/duplicate`
- Same semantics, scoped to the change order.
- Recalculates the CO (reuses `recalculate_change_order()`).

### Tests
- Duplicate line item copies all fields and appends at end.
- Duplicate CO item copies all fields and appends at end.
- 404 when item_id doesn't belong to the estimate / change order.
- Totals recalculated correctly after duplicate.

## Feature 3 — Consistent Back Button

### Component
Create `frontend/src/components/BackButton.jsx`:

```jsx
<BackButton to="/jobs" label="Back to Jobs" />
```

Behavior:
- Always renders the fallback target (never `navigate(-1)`). This eliminates the
  "broken back button on direct link" problem the Sprint 12 known-issue documented.
- Rationale: in this CRM, users land on detail pages via deep links (emails,
  bookmarks) often enough that `navigate(-1)` cannot be trusted. Predictable
  parent-link navigation is simpler and always works.
- Styling: left-arrow icon + label, consistent position (top-left, above page title).

### Placement
Add `<BackButton>` to the header of each detail page, replacing whatever
ad-hoc back affordance currently exists:

| Page | BackButton target |
|------|-------------------|
| `EstimateDetailPage` | `/jobs/{estimate.job_id}` (parent job) |
| `JobDetailPage` | `/jobs` (jobs list; referrer-aware pipeline is out of scope) |
| `InvoiceDetailPage` | `/invoices` |
| `ContactDetailPage` | `/contacts` |

`EmployeeDetailPage` does not exist and is dropped from the spec.

Existing breadcrumbs stay where they are — BackButton complements them. For pages
without breadcrumbs (InvoiceDetailPage), BackButton is the sole back affordance.

## Files to Touch

**Backend**
- `backend/app/routers/estimates.py` — add duplicate endpoint
- `backend/app/routers/change_orders.py` — add duplicate endpoint
- `backend/tests/test_estimates.py` (or equivalent) — duplicate tests
- `backend/tests/test_change_orders.py` — duplicate tests

**Frontend**
- `frontend/src/api/estimates.js` — `duplicateLineItem(estimateId, itemId)`
- `frontend/src/api/changeOrders.js` — `duplicateChangeOrderItem(coId, itemId)`
- `frontend/src/components/BackButton.jsx` — new shared component
- `frontend/src/components/MaterialPickerModal.jsx` — new modal
- `frontend/src/components/AddItemSplitButton.jsx` — new split button
- `frontend/src/pages/EstimateDetailPage.jsx` — wire split button, duplicate icon, BackButton
- `frontend/src/pages/JobDetailPage.jsx` — BackButton
- `frontend/src/pages/InvoiceDetailPage.jsx` — BackButton
- `frontend/src/pages/ContactDetailPage.jsx` — BackButton

## Verification Checklist

1. Add a blank line item to an estimate — works.
2. Search materials in the picker, select one, edit modal opens pre-filled.
3. Override pre-filled price, save — correct totals.
4. Duplicate a line item — copy appears at end with identical fields.
5. Duplicate a CO item — copy appears at end with identical fields.
6. Back button on estimate detail → parent job.
7. Back button on invoice detail → invoices list.
8. Direct-link to an estimate → back button still works (goes to job).
9. All 410+ existing tests still pass.
10. New duplicate endpoint tests pass.

## Anti-Patterns (Explicit)

- No calculation engine changes.
- No data model changes / no migrations.
- No "Add Multiple Items".
- No optional items.
- No customer portal changes.
- No PDF output changes.
