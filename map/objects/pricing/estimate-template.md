---
type: object
cluster: pricing
status: live
verified: 2026-10-01 · public copy of 7fbda4a + money-path fixes
entity: backend/app/models/estimate_template.py
---
# estimate-template

**Type:** object · **Mark:** live · **Checked:** 2026-10-01 · **Where:** backend/app/services/template_calculator.py:9

## One sentence
A reusable bill of materials that turns roof measurements into priced line items.

## Why this shape
A roofer prices from measurements (total area, ridge, hip, valley, eave, rake). The engine has to
order ordinary-looking math correctly: waste is applied before rounding up, and you cannot buy
0.3 of a bundle.

## Shape
`calculate_item` (backend/app/services/template_calculator.py:9), in order:
1. raw qty = measurement x `conversion_factor`, or `default_qty` when the item has no measurement (:28)
2. apply `waste_pct` (:50)
3. round **up** to whole units (:55-56)
4. sell price = `unit_cost` x (1 + `margin_pct`) (:58)
5. line total (:63)

Items: `estimate_template_items` (backend/app/models/estimate_template_item.py), each with `unit_cost`, `margin_pct`,
`waste_pct`, `measurement_type`, `conversion_factor`, optional `material_id`.
Applied to an estimate by `POST /api/estimates/{id}/apply-template` (backend/app/routers/estimates.py:548), which appends line items and recalculates.

## Connected to
- reads: nothing live at apply time. `unit_cost` is a snapshot of the material price taken when the item was added (frontend/src/pages/TemplateBuilderPage.jsx:539).
- writes: estimate line items (as plain qty / unit_price rows; no link back to the template)
- looks-like-but-is-not: material. `material_id` is kept for reference only.

## If you change this
- **Hits:** apply-template output, template preview, every estimate built afterward.
- **Does not hit:** estimates already built (their line items are copies), or material prices. Re-importing a price list never reprices a template.

## Surfaces
Templates UI and preview (backend/app/routers/estimate_templates.py), apply-template, tests in backend/tests/test_template_calculator.py and test_apply_template.py.

## See
backend/app/services/template_calculator.py
