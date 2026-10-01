# Legacy CRM — Sprint 15.5a: Estimate Tax Toggle

**Scope:** Per-estimate toggle controlling whether tax is calculated on top of line item prices or included in them.
**Source:** Marcus's round 2 feedback — "painting includes tax in price, roofing taxes separately"
**Estimated build time:** 15–25 min in Claude Code

---

## Context

The system currently has `tax_rate` DECIMAL(5,3) DEFAULT 7.000 on the estimates table (added Sprint 10a). Tax is always calculated as `subtotal × tax_rate` and added to get the total. There's no way to say "tax is already included in my prices" — which is how Marcus's painting estimates work. Painting quotes a bundled price; roofing breaks tax out separately.

---

## What's Changing

### New Column

**Migration 0023:** Add `tax_included` BOOLEAN DEFAULT false to `estimates` table.

- `false` (default) = Tax Exclusive — tax calculated on top of subtotal. This is the roofing default.
- `true` = Tax Inclusive — line item prices already include tax. Tax line shows "Included" or $0.00. Total = subtotal.

No migration needed on `invoices` — invoices already have their own `tax_rate` and `tax` fields. When an invoice is created from an estimate, the invoice creation logic should set `tax = 0` and `tax_rate = 0` if the source estimate has `tax_included = true`.

No migration needed on `change_orders` — change orders don't have their own tax fields. They inherit the parent estimate's tax behavior. The grand total calculation on the estimate response already handles this.

### Backend Changes

**MODIFIED: `backend/app/models/estimate.py`**
- Add `tax_included = Column(Boolean, default=False, server_default="false")`

**MODIFIED: `backend/app/schemas/estimate.py`**
- Add `tax_included: bool` to EstimateCreate, EstimateUpdate, EstimateResponse
- Default: `false`

**MODIFIED: `backend/app/routers/estimates.py`**
- Estimate total calculation logic:
  - If `tax_included` is `false`: `tax = subtotal * (tax_rate / 100)`, `total = subtotal + tax` (current behavior, unchanged)
  - If `tax_included` is `true`: `tax = 0`, `total = subtotal`
- Estimate duplicate: copy `tax_included` from source estimate
- Estimate response: include `tax_included` in response

**MODIFIED: `backend/app/routers/invoices.py`**
- When creating invoice from estimate (`POST /api/invoices` or however it's currently triggered):
  - If source estimate has `tax_included = true`: set invoice `tax = 0`, `tax_rate = 0`
  - If source estimate has `tax_included = false`: current behavior (copy tax_rate, calculate tax)

**MODIFIED: Deposit invoice endpoint** (`POST /api/invoices/deposit`)
- Same logic: inherit `tax_included` behavior from source estimate

**Auto-default behavior (nice-to-have, low risk):**
- When `work_type` is set on an estimate (from restructure — estimate now has `work_type` field):
  - If `work_type` == `"painting"` and `tax_included` hasn't been manually set → default `tax_included = true`
  - If `work_type` == `"roofing"` and `tax_included` hasn't been manually set → default `tax_included = false`
  - User can always override manually
- **Implementation note:** This auto-default should happen on the frontend only (set the toggle when work_type changes), not enforced on the backend. The backend just stores whatever value is sent. This avoids complexity around "has the user manually set this."

### Frontend Changes

**MODIFIED: `frontend/src/pages/EstimateDetailPage.jsx`**

**Settings area** (where the existing display toggles live — show_quantities, show_unit_prices, etc.):
- Add a toggle switch labeled **"Tax Included in Prices"**
- When toggled ON: the tax_rate input field grays out (still visible for reference but non-functional), and the Totals section updates immediately
- When toggled OFF: tax_rate input is active, tax calculated normally
- Auto-saves on toggle (same pattern as other display settings)

**Totals section:**
- When `tax_included = false` (current behavior):
  ```
  Subtotal    $6,250.00
  Tax (7%)      $437.50
  Total       $6,687.50
  ```
- When `tax_included = true`:
  ```
  Subtotal    $6,250.00
  Tax         Included
  Total       $6,250.00
  ```

**Line items table Tax column:**
- When `tax_included = true`: show "—" instead of "$0.00" in each row's Tax cell. Subtle visual signal that tax isn't being calculated per-item.
- When `tax_included = false`: current behavior (show calculated tax per item, or $0.00)

**Work type auto-default (frontend only):**
- When user sets `work_type` on the estimate's Job Info panel:
  - If work_type changes to "painting" → set `tax_included = true` (with auto-save)
  - If work_type changes to "roofing" → set `tax_included = false` (with auto-save)
  - Only trigger on work_type *change*, not on initial page load (don't override a manually-set value on every render)

### PDF Changes

**MODIFIED: Estimate PDF template (WeasyPrint/Jinja2)**
- When `tax_included = true`: Totals section shows "Tax: Included" instead of a dollar amount
- When `tax_included = false`: current behavior

**MODIFIED: Invoice PDF template**
- When invoice was created from a tax-included estimate (tax = 0, tax_rate = 0): hide the Tax row entirely from the totals section, or show "Tax: N/A"
- When tax applies normally: current behavior

### Customer Portal Changes

**MODIFIED: Customer-facing estimate portal**
- Respect `tax_included` setting in the totals display
- When `tax_included = true`: show "Tax: Included" in totals
- When `tax_included = false`: show calculated tax amount

**Change order portal:** No changes needed — CO portal shows CO items and CO total only. Tax is calculated at the estimate level, not the CO level.

---

## What This Does NOT Change

- **Tax rate storage:** `tax_rate` column stays. Even when tax is included, the rate is stored for reference/reporting.
- **Line item prices:** No changes to how line items store their amounts. The toggle only affects whether tax is calculated on top.
- **Change order model:** No new fields on change_orders. COs inherit parent estimate behavior.
- **Per-line-item taxability:** Not in scope. This is an estimate-level toggle. If Marcus later needs some line items taxed and others not (e.g., materials taxed, labor not), that's a future enhancement.
- **Existing estimates:** Migration defaults `tax_included = false`, so all existing estimates continue to behave as they do now.

---

## Downstream Impact Check

| System | Impact | Action |
|--------|--------|--------|
| Estimate totals | Tax calculation changes | Update calculation logic |
| Estimate PDF | Totals section display | Update Jinja2 template |
| Customer portal | Totals display | Update portal component |
| Invoice creation | Inherit tax behavior | Update invoice creation logic |
| Invoice PDF | Tax row display | Update Jinja2 template |
| Deposit invoices | Inherit tax behavior | Update deposit creation logic |
| Change orders | No own tax fields | No change needed |
| CO portal | Shows CO total only | No change needed |
| Dashboard stats | Uses estimate total | No change — total is already correct |
| Pipeline board | Uses estimate total | No change — total is already correct |
| Payment tracking | Uses invoice balance | No change — invoice total drives this |

---

## Tests

**NEW tests:**
1. Create estimate with `tax_included = false` → verify tax calculated normally
2. Create estimate with `tax_included = true` → verify tax = 0, total = subtotal
3. Update `tax_included` from false to true → verify totals recalculate
4. Duplicate estimate with `tax_included = true` → verify copy preserves setting
5. Create invoice from tax-included estimate → verify invoice tax = 0
6. Create deposit invoice from tax-included estimate → verify deposit tax = 0
7. Estimate response includes `tax_included` field

**EXISTING tests:** Should all pass unchanged. The default is `false`, which preserves current behavior for every existing test that creates estimates without specifying `tax_included`.

---

## Verification Checklist

- [ ] Migration 0023 runs cleanly (both SQLite for tests and Postgres for production)
- [ ] Existing estimates default to `tax_included = false` — no behavior change
- [ ] Toggle in estimate settings area saves and persists on reload
- [ ] Totals section shows "Included" when toggle is on
- [ ] Line items Tax column shows "—" when toggle is on
- [ ] PDF renders "Tax: Included" when toggle is on
- [ ] Customer portal shows correct totals for both modes
- [ ] Invoice created from tax-included estimate has tax = 0
- [ ] Deposit invoice from tax-included estimate has tax = 0
- [ ] Work type auto-default fires on work_type change (not on page load)
- [ ] All existing tests pass (446+)
- [ ] New tests pass (7+)

---

## Claude Code Prompt

```
Read CLAUDE.md and PRD.md. Data model restructure complete: Job entity deprecated. Contact = Client Profile. Estimate = Proposal, and when approved = Job. Sprint 15 theming complete. 446 tests passing. Latest migration: 0022. Production deployed to Azure.

Sprint 15.5a: Add tax toggle to estimates.

BACKEND:
1. Migration 0023: Add `tax_included` BOOLEAN DEFAULT false to `estimates` table.
2. Update Estimate model with `tax_included` column.
3. Update EstimateCreate, EstimateUpdate, EstimateResponse schemas to include `tax_included` (default false).
4. Update estimate total calculation: when `tax_included` is true, set tax = 0 and total = subtotal. When false, current behavior (tax = subtotal * tax_rate / 100).
5. Update estimate duplicate to copy `tax_included`.
6. Update invoice creation from estimate: if source estimate has `tax_included = true`, set invoice tax = 0 and tax_rate = 0.
7. Update deposit invoice creation: same logic as #6.

FRONTEND:
8. EstimateDetailPage — add "Tax Included in Prices" toggle switch in the settings/display area (alongside existing show_quantities, show_unit_prices toggles). Auto-save on toggle.
9. When `tax_included` is true: gray out (but don't hide) the tax_rate input field.
10. Totals section: when `tax_included` is true, show "Tax: Included" instead of the dollar amount. Total = subtotal.
11. Line items table: when `tax_included` is true, show "—" in the Tax column cells instead of "$0.00".
12. Work type auto-default (frontend only): when work_type changes to "painting", set tax_included = true. When work_type changes to "roofing", set tax_included = false. Only on work_type *change*, not on initial load.

PDF:
13. Estimate PDF template: when tax_included is true, show "Tax: Included" in totals section.
14. Invoice PDF template: when tax = 0 and tax_rate = 0 (from tax-included estimate), hide the Tax row or show "Tax: N/A".

PORTAL:
15. Customer-facing estimate portal: respect tax_included in totals display. Show "Tax: Included" when true.

TESTS:
16. Test estimate with tax_included = false → tax calculated normally.
17. Test estimate with tax_included = true → tax = 0, total = subtotal.
18. Test update tax_included toggle → totals recalculate.
19. Test duplicate estimate preserves tax_included.
20. Test invoice from tax-included estimate → invoice tax = 0.
21. Test deposit invoice from tax-included estimate → deposit tax = 0.
22. Test estimate response includes tax_included field.

ANTI-PATTERNS:
- Do NOT remove the tax_rate column or field. It stays for reference even when tax is included.
- Do NOT add tax fields to change_orders. COs inherit parent estimate behavior.
- Do NOT enforce work_type → tax_included mapping on the backend. The auto-default is frontend-only.
- Do NOT change existing test behavior. Default is false = current behavior.

Run pytest after all changes. All 446+ existing tests must pass plus 7+ new tests.
```
