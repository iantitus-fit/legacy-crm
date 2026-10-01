# Verification log

Deviations the inventory surfaced while building the map. Cards describe what exists; this file
describes what deviates. One entry each: what, where, type, expected vs actual. Checked 2026-10-01.

## Open

None.

## Resolved 2026-10-01

All nine entries from the first inventory were fixed the same day. The backend fixes (V-01 to V-05,
V-08, V-09) are pinned by 20 tests in `backend/tests/test_money_path_fixes.py`. Run against the code
as it was when the map was first built, 16 of them fail; the other 4 guard behavior that was already
right and must stay that way. V-06 is a frontend change and V-07 a documentation change, checked by
reading. The behavior each fix now guarantees is described on the card named.

| Entry | What was wrong | Fix | Card |
|---|---|---|---|
| V-01 | Portal-signed estimates never reached the Jobs board | Both approval doors call `approve_estimate` | processes/approve.md |
| V-02 | Portal approval set no `approved_at`; any status could be approved again | Same function; answers allowed only from draft / sent / viewed, else 409 (estimates and change orders) | objects/portal/portal-link.md |
| V-03 | Final invoice billed the full job even after a deposit invoice | Credit line per deposit, after tax; voiding a deposit removes its credit; no new deposit once a final exists | objects/money/invoice.md |
| V-04 | Change-order tax ignored `tax_included` and turned 0% into 7% | Same tax rule as the parent estimate | objects/money/change-order.md |
| V-05 | Invoice `PUT` accepted any status string | Only draft, sent, void; partial and paid come from payments | objects/money/invoice.md |
| V-06 | Client profile grouped estimates by statuses nothing writes | Active = everything not rejected or closed | objects/record/estimate.md |
| V-07 | Root CLAUDE.md called the jobs table deprecated | Rewritten: required parent, new job-phase fields go on estimates | objects/record/job.md |
| V-08 | `expires_at` on all token tables, never written or read | Optional `PORTAL_LINK_DAYS`; expired links return 410 | objects/portal/portal-link.md |
| V-09 | Next invoice number came from the last row, which imports could hijack | Highest INV number + 1 | objects/money/invoice.md |

Also fixed while in the invoice PDF: a stray backslash printed before every item price.
