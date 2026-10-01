# Sprint 9b: Estimate Templates & Calculation Engine — Design Document

**Date:** 2026-02-22
**Sprint:** 9b
**Status:** Approved

## Overview

Add estimate templates tied to product types (e.g., "IKO Cambridge 30-Year") with a calculation engine that auto-generates estimate line items from roof measurements. Each template item links to the materials library and carries its own waste %, margin %, measurement type, unit conversion, and default quantity. The Apply Template flow lets users enter measurements, preview calculated results, and generate estimate line items in one step.

Hover XML parsing is deferred to a future sprint — users enter measurements manually via the Apply Template modal.

## Data Model

### `estimate_templates` table

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| name | String(200), unique | e.g. "IKO Cambridge 30-Year" |
| description | String(500), nullable | Product type notes |
| default_margin_pct | Numeric(5,2), default 46.00 | Dale's standard margin |
| default_waste_pct | Numeric(5,2), default 10.00 | Standard waste factor |
| is_active | Boolean, default true | Soft delete |
| created_at | DateTime(tz), server_default=now() | |
| updated_at | DateTime(tz), server_default=now() | |

### `estimate_template_items` table

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | |
| template_id | Integer FK → estimate_templates | CASCADE delete |
| material_id | Integer FK → materials, nullable | Link to materials library (null for manual/labor items) |
| description | String(500) | Copied from material at add-time, or entered manually |
| category | String(100) | Roofing, Fasteners, Flashing, Underlayment, Ventilation, Labor, etc. |
| unit_cost | Numeric(12,2) | Snapshot from material or manual entry |
| uom | String(20), nullable | bundle, box, roll, piece, each, LF, SQ |
| margin_pct | Numeric(5,2) | Per-item override (defaults to template's default_margin_pct) |
| waste_pct | Numeric(5,2) | Per-item override (defaults to template's default_waste_pct) |
| measurement_type | String(50), nullable | One of: total_area, ridge, valley, eave, rake, hip — or null for fixed-qty items |
| conversion_factor | Numeric(10,4), default 1.0000 | Units of material per unit of measurement (e.g., 3.0 = 3 bundles per square) |
| default_qty | Numeric(12,2), nullable | Fallback qty when measurement_type is null (e.g., 1 for "Dumpster Rental") |
| sort_order | Integer | Display ordering within template |

**Indexes:**
- `ix_template_items_template_id` on (template_id)

### Measurement Types

| measurement_type | Unit | Source |
|------------------|------|--------|
| total_area | squares | Hover: total roof area |
| ridge | linear feet | Hover: ridge length |
| hip | linear feet | Hover: hip length |
| valley | linear feet | Hover: valley length |
| eave | linear feet | Hover: eave length |
| rake | linear feet | Hover: rake length |
| null | — | Uses default_qty directly |

## Calculation Engine

### Formula

For each template item, given a measurements dict:

1. **Determine raw quantity:**
   - If `measurement_type` is set and measurement value exists: `raw_qty = measurement_value * conversion_factor`
   - If `measurement_type` is null: `raw_qty = default_qty` (or 0 if not set)

2. **Apply waste factor:** `adjusted_qty = raw_qty * (1 + waste_pct / 100)`

3. **Round up to whole units:** `final_qty = ceil(adjusted_qty)` — you don't buy partial bundles

4. **Calculate sell price:** `sell_price = unit_cost * (1 + margin_pct / 100)`

5. **Line total:** `line_total = final_qty * sell_price`

This matches the CLAUDE.md formula: `(measurement × conversion) × (1 + waste%) × unit_cost × (1 + margin%)`

### Key decisions

- **unit_cost is a snapshot:** When adding a material to a template, unit_cost is copied from the material's current price. Changing the material's price later does NOT change existing templates. Users can manually refresh prices.
- **Sell price is computed, not stored:** The estimate line items store the final `unit_price` (sell price after margin) since that's what the existing `estimate_line_items` table uses.
- **Qty rounds up:** Partial units are always rounded up (ceil) since you can't buy half a bundle.
- **Preview is stateless:** The preview endpoint takes measurements + template and returns calculated items without persisting anything.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/estimate-templates | List active templates |
| GET | /api/estimate-templates/{id} | Template with all items |
| POST | /api/estimate-templates | Create template |
| PUT | /api/estimate-templates/{id} | Update template metadata |
| DELETE | /api/estimate-templates/{id} | Soft delete (is_active=false) |
| POST | /api/estimate-templates/{id}/duplicate | Deep copy template + items |
| POST | /api/estimate-templates/{id}/items | Add item to template |
| PUT | /api/estimate-templates/{id}/items/{item_id} | Update item |
| DELETE | /api/estimate-templates/{id}/items/{item_id} | Delete item |
| PUT | /api/estimate-templates/{id}/items/reorder | Reorder items |
| POST | /api/estimate-templates/{id}/preview | Preview calculation with measurements (no persist) |
| POST | /api/estimates/{id}/apply-template | Apply template → create line items on existing estimate |

### Preview Request/Response

**POST /api/estimate-templates/{id}/preview**

Request:
```json
{
  "measurements": {
    "total_area": 32.5,
    "ridge": 45.0,
    "valley": 22.0,
    "eave": 180.0,
    "rake": 95.0,
    "hip": 30.0
  }
}
```

Response:
```json
{
  "items": [
    {
      "description": "OC Duration Brownwood",
      "category": "Roofing",
      "qty": 108,
      "unit_price": "172.22",
      "line_total": "18599.76",
      "measurement_type": "total_area",
      "measurement_value": 32.5,
      "raw_qty": 97.5,
      "waste_applied": 107.25,
      "uom": "BD"
    }
  ],
  "subtotal": "25430.50",
  "item_count": 12
}
```

### Apply Template Request

**POST /api/estimates/{id}/apply-template**

```json
{
  "template_id": 1,
  "measurements": {
    "total_area": 32.5,
    "ridge": 45.0,
    "eave": 180.0
  }
}
```

Appends calculated line items to the estimate, then recalculates totals.

## Frontend

### Templates List Page (`/templates`)

- Card grid showing each template: name, description, item count, default margin/waste
- "New Template" button → creates template, navigates to builder
- Card actions: edit (go to builder), duplicate, deactivate

### Template Builder Page (`/templates/:id`)

- **Header section:** Editable name, description, default margin %, default waste %
- **Items table:** category | description | unit cost | UOM | margin % | waste % | measurement type | conversion factor | default qty | actions
- **Add Item button:** Opens material picker modal
  - Search materials by name/number, filter by category/price list
  - Select material → auto-fills description, unit_cost, uom, category
  - Or "Add Manual Item" for labor/custom items
- **Inline editing:** All fields editable inline (same pattern as EstimateDetailPage)
- **Duplicate button** in header

### Apply Template Modal (on EstimateDetailPage)

- Triggered from a new "Apply Template" button on EstimateDetailPage
- Step 1: Select template from dropdown
- Step 2: Enter measurements (total area, ridge, hip, valley, eave, rake) — only fields that the template's items actually use are required
- Step 3: Live preview table showing calculated items with qty, sell price, line total
- Step 4: "Apply" button → POST to apply-template endpoint → refresh estimate

### Sidebar Navigation

- Add "Templates" nav item in the JOBS section (after Materials), using `FileText` icon

## Testing Strategy

- **Calculation engine:** Extensive unit tests covering all measurement types, waste/margin math, rounding, edge cases (zero measurements, missing measurement types, null default_qty)
- **Template CRUD:** Standard router tests following the materials test pattern
- **Apply template:** Integration test creating a template, adding items, applying to an estimate, verifying generated line items and totals
- **Frontend:** Build verification (no UI tests for MVP)
