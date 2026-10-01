---
type: object
cluster: money
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
entity: backend/app/models/change_order.py
---
# change-order

**Type:** object · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/models/change_order.py:17

## One sentence
A numbered add-on to an estimate (#1, #2...) with its own items, portal link, and signature.

## Why this shape
Roofs reveal rotten decking after tear-off. Scope grows mid-job, and the homeowner has to sign
for the extra money separately from the original proposal.

## Shape
- `co_number` = max for the estimate + 1 (backend/app/routers/change_orders.py:127).
- Items: `change_order_items`, same shape as estimate line items.
- Totals: `recalculate_change_order` (backend/app/routers/change_orders.py:70) with the parent estimate's tax rule (:82): tax-included work gets no separate tax, an explicit 0% stays 0%, NULL falls back to 7%.
- Status: sent (backend/app/routers/change_orders.py:445), then viewed / approved / rejected / changes_requested from the portal (backend/app/routers/change_order_portal.py:190-330), each answer allowed once (see portal-link).

## Connected to
- owned-by: estimate (`estimate_id`)
- feeds: `grand_total` on the estimate (approved COs only), invoice creation (approved CO items copied with `source_type = change_order`)
- looks-like-but-is-not: a revised estimate. The original estimate's items never change.

## If you change this
- **Hits:** estimate `grand_total`, the next final invoice for the estimate, CO PDF, CO portal.
- **Does not hit:** an invoice that already exists. A CO approved after the final invoice is not added to it; bill it on its own or rebuild the invoice.

## Surfaces
Estimate detail page (CO list and badges), CO portal, owner notification email.

## See
backend/app/routers/change_orders.py
