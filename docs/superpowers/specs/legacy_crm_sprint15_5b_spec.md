# Legacy CRM — Sprint 15.5b: Change Order Accepted Dates

**Scope:** Display the acceptance date on approved change orders, matching DripJobs' green date badge.
**Source:** Marcus's feedback — "Change order accepted dates visible inline (match DripJobs date badge)"
**Reference:** DripJobs screenshot shows green badge: `Accepted - on 03/12/2026` next to CO header
**Estimated build time:** 10–15 min in Claude Code

---

## Context

Change orders already track approval through the CO portal. When a customer approves and signs, a `ChangeOrderSignature` record is created with a `signed_at` timestamp. The CO status updates to "approved." But the estimate detail page only shows the status badge — it doesn't show *when* the CO was accepted. DripJobs shows this as a green date badge inline with the CO header.

---

## What's Changing

### Backend Changes

**MODIFIED: `backend/app/routers/estimates.py`** (or wherever COs are serialized into the estimate response)
- When building the change order response data, query the `change_order_signatures` table for each approved CO to get `signed_at`
- Add `accepted_at: Optional[datetime]` to the CO response data
- If CO status == "approved" and a signature exists → `accepted_at = signature.signed_at`
- If CO status != "approved" or no signature → `accepted_at = null`

**MODIFIED: `backend/app/schemas/change_order.py`**
- Add `accepted_at: Optional[datetime] = None` to `ChangeOrderResponse`

**Alternative (simpler if relationship exists):** If `ChangeOrder` model already has a `signatures` relationship defined, just access `co.signatures[0].signed_at` in the serializer. Check the model before creating a separate query.

### Frontend Changes

**MODIFIED: `frontend/src/pages/EstimateDetailPage.jsx`**
- In each CO block header (where the CO number, status badge, and name are displayed):
  - When CO status is "approved" and `accepted_at` is present:
    - Show a green badge: **"Accepted - on [date]"**
    - Date format: `MM/DD/YYYY` (matching DripJobs: "on 03/12/2026")
    - Badge styling: green background (#10B981 or theme success color), white text, rounded, small font
    - Position: inline with the CO header, right of the status badge (or replacing it since "approved" and "Accepted - on date" convey the same info with the date version being more informative)
  - When CO status is anything other than "approved": show the existing status badge (no change)

**Visual reference from DripJobs:**
```
Change Order #88916  [Accepted - on 03/12/2026]    $2,000.00
```
- Green badge replaces or sits alongside the existing purple/gray status badge
- Date is the day the customer signed, not when the CO was created

### No PDF Changes Needed

The CO PDF already shows the signature with date when signed. This sprint is about the *admin-facing* estimate detail page showing the acceptance date at a glance — so Marcus can see when each CO was accepted without opening the CO or checking the portal.

### No Migration Needed

The data already exists in `change_order_signatures.signed_at`. This is purely about surfacing it.

---

## Edge Cases

1. **CO approved but no signature record** — Shouldn't happen in current flow (COs can only be approved via portal which creates a signature). But defensively: if `accepted_at` is null and status is "approved", just show the existing status badge without a date.

2. **Multiple signatures** — If a CO was approved, then status was reverted and re-approved, there could be multiple signature records. Use the most recent `signed_at` (ORDER BY signed_at DESC LIMIT 1).

3. **CO approved internally in the future** — If internal CO approval is added later (like estimates got in the restructure), the `accepted_at` field should also be populated by that flow. For now, it only comes from portal signatures.

---

## Tests

**NEW tests:**
1. Approved CO response includes `accepted_at` datetime
2. Non-approved CO response has `accepted_at` as null
3. CO with no signature but approved status → `accepted_at` is null (defensive)

**EXISTING tests:** All should pass. Adding a field to the response schema with a default of None won't break existing CO tests.

---

## Verification Checklist

- [ ] Approved COs show green "Accepted - on MM/DD/YYYY" badge on estimate detail page
- [ ] Non-approved COs show their normal status badge (no date)
- [ ] Date matches the actual signature date, not the CO creation date
- [ ] Badge is theme-aware (works in both light and dark modes)
- [ ] All existing tests pass (446+ or whatever 15.5a lands at)
- [ ] New tests pass (3+)

---

## Claude Code Prompt

```
Read CLAUDE.md and PRD.md. Data model restructure complete. Sprint 15.5a (tax toggle) complete [UPDATE WITH ACTUAL STATUS]. [Current test count] tests passing. Latest migration: [UPDATE]. Production deployed to Azure.

Sprint 15.5b: Show change order accepted dates inline on the estimate detail page.

BACKEND:
1. Add `accepted_at: Optional[datetime] = None` to ChangeOrderResponse schema.
2. When serializing change orders in the estimate response: if CO status == "approved", query change_order_signatures for that CO and set `accepted_at` to the most recent `signed_at` value. If no signature exists or status != "approved", set `accepted_at` to None.
3. Check if ChangeOrder model has a `signatures` relationship — if so, use it directly instead of a separate query.

FRONTEND:
4. EstimateDetailPage — in each CO block header: when status is "approved" and accepted_at is present, show a green badge "Accepted - on MM/DD/YYYY" (format the date as month/day/year). This replaces the generic "approved" status badge for that CO.
5. When status is anything other than "approved", show the existing status badge unchanged.
6. Green badge styling: green background (use theme success/green color), white text, rounded-full, text-xs, px-2 py-0.5. Should work in both light and dark themes.

TESTS:
7. Test: approved CO with signature → response includes accepted_at datetime.
8. Test: non-approved CO → accepted_at is null.
9. Test: approved CO with no signature record → accepted_at is null (defensive).

ANTI-PATTERNS:
- Do NOT add a migration. The data already exists in change_order_signatures.signed_at.
- Do NOT change the CO portal or CO PDF. This is admin-facing display only.
- Do NOT change how COs are approved. Just surface the existing date.

Run pytest after all changes.
```
