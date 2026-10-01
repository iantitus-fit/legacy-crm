# Sprint 14: Line Item UX + Navigation Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish three UX pain points in the estimate/change order flow: add-item choice between blank or from-materials, one-click line item duplication, and consistent back-button navigation across detail pages.

**Architecture:** Two new backend endpoints (`POST .../duplicate` for estimate line items and CO items), three new frontend components (`MaterialPickerModal`, `AddItemSplitButton`, `BackButton`), and edits to four existing detail pages. No data model changes, no migrations, no calculation engine changes.

**Tech Stack:** FastAPI + SQLAlchemy 2.x (backend), React 18 + Vite + Tailwind + lucide-react + react-router-dom (frontend), pytest (tests).

**Spec:** `docs/superpowers/specs/2026-04-11-sprint14-line-item-ux-design.md`

---

## File Structure

**Backend — modify:**
- `backend/app/routers/estimates.py` — add `duplicate_line_item` endpoint after existing `delete_line_item`.
- `backend/app/routers/change_orders.py` — add `duplicate_co_item` endpoint after existing `delete_co_item`.
- `backend/tests/test_estimates.py` — new tests for duplicate line item.
- `backend/tests/test_change_orders.py` — new tests for duplicate CO item.

**Frontend — modify:**
- `frontend/src/api/estimates.js` — add `duplicateLineItem()`.
- `frontend/src/api/changeOrders.js` — add `duplicateChangeOrderItem()`.
- `frontend/src/pages/EstimateDetailPage.jsx` — wire split button, duplicate icon, BackButton.
- `frontend/src/pages/JobDetailPage.jsx` — BackButton.
- `frontend/src/pages/InvoiceDetailPage.jsx` — BackButton.
- `frontend/src/pages/ContactDetailPage.jsx` — BackButton.

**Frontend — create:**
- `frontend/src/components/BackButton.jsx` — shared back-navigation component.
- `frontend/src/components/MaterialPickerModal.jsx` — searchable material picker.
- `frontend/src/components/AddItemSplitButton.jsx` — dropdown button for "Blank" / "From Materials".

---

## Task 1: Backend — duplicate estimate line item endpoint

**Files:**
- Modify: `backend/app/routers/estimates.py` (after line 803, i.e. after `delete_line_item`)
- Test: `backend/tests/test_estimates.py` (append to end of file)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_estimates.py`:

```python
def test_duplicate_line_item(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    item = _add_line_item(
        client,
        auth_headers,
        est["id"],
        description="Shingles",
        qty="3.00",
        unit_price="100.00",
        body="<p>Architectural shingles</p>",
        notes="Crew note",
    )

    resp = client.post(
        f"/api/estimates/{est['id']}/line-items/{item['id']}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    dup = resp.json()
    assert dup["id"] != item["id"]
    assert dup["description"] == "Shingles"
    assert Decimal(str(dup["qty"])) == Decimal("3.00")
    assert Decimal(str(dup["unit_price"])) == Decimal("100.00")
    assert Decimal(str(dup["line_total"])) == Decimal("300.00")
    assert dup["body"] == "<p>Architectural shingles</p>"
    assert dup["notes"] == "Crew note"
    assert dup["sort_order"] > item["sort_order"]

    # Estimate now has two items and subtotal doubled
    est_resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    ).json()
    assert len(est_resp["line_items"]) == 2
    assert Decimal(str(est_resp["subtotal"])) == Decimal("600.00")


def test_duplicate_line_item_preserves_section(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])

    section_resp = client.post(
        f"/api/estimates/{est['id']}/sections",
        json={"name": "Roofing"},
        headers=auth_headers,
    )
    section_id = section_resp.json()["id"]

    item = _add_line_item(
        client,
        auth_headers,
        est["id"],
        description="Ridge cap",
        qty="2",
        unit_price="50.00",
        section_id=section_id,
    )

    resp = client.post(
        f"/api/estimates/{est['id']}/line-items/{item['id']}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["section_id"] == section_id


def test_duplicate_line_item_not_found(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])

    resp = client.post(
        f"/api/estimates/{est['id']}/line-items/9999/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_duplicate_line_item_wrong_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est_a = _create_estimate(client, auth_headers, job["id"], name="A")
    est_b = _create_estimate(client, auth_headers, job["id"], name="B")
    item = _add_line_item(client, auth_headers, est_a["id"])

    resp = client.post(
        f"/api/estimates/{est_b['id']}/line-items/{item['id']}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run from `backend/`:
```bash
cd backend && pytest tests/test_estimates.py::test_duplicate_line_item -v
```
Expected: FAIL with 404 or 405 (endpoint does not exist).

- [ ] **Step 3: Implement the duplicate endpoint**

In `backend/app/routers/estimates.py`, add this function immediately after the existing `delete_line_item` function (which ends around line 803):

```python
@router.post(
    "/{estimate_id}/line-items/{item_id}/duplicate",
    response_model=EstimateLineItemResponse,
    status_code=201,
)
def duplicate_line_item(
    estimate_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = (
        db.query(EstimateLineItem)
        .filter(
            EstimateLineItem.id == item_id,
            EstimateLineItem.estimate_id == estimate_id,
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Line item not found")

    max_order = (
        db.query(EstimateLineItem.sort_order)
        .filter(EstimateLineItem.estimate_id == estimate_id)
        .order_by(EstimateLineItem.sort_order.desc())
        .first()
    )
    new_sort_order = (max_order[0] or 0) + 1 if max_order else 0

    duplicate = EstimateLineItem(
        estimate_id=estimate_id,
        description=source.description,
        qty=source.qty,
        unit_price=source.unit_price,
        line_total=source.line_total,
        body=source.body,
        notes=source.notes,
        section_id=source.section_id,
        sort_order=new_sort_order,
    )
    db.add(duplicate)
    db.commit()

    recalculate_estimate(db, estimate_id)
    db.refresh(duplicate)
    return duplicate
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_estimates.py::test_duplicate_line_item tests/test_estimates.py::test_duplicate_line_item_preserves_section tests/test_estimates.py::test_duplicate_line_item_not_found tests/test_estimates.py::test_duplicate_line_item_wrong_estimate -v
```
Expected: 4 passed.

- [ ] **Step 5: Run the full estimates test file to confirm no regressions**

```bash
cd backend && pytest tests/test_estimates.py -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/estimates.py backend/tests/test_estimates.py
git commit -m "Sprint 14a: Add duplicate endpoint for estimate line items"
```

---

## Task 2: Backend — duplicate change order item endpoint

**Files:**
- Modify: `backend/app/routers/change_orders.py` (after line 304, i.e. after `delete_co_item`)
- Test: `backend/tests/test_change_orders.py` (append to end of file)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_change_orders.py`:

```python
def test_duplicate_co_item(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "CO"},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    item_resp = client.post(
        f"/api/change-orders/{co_id}/items",
        json={
            "description": "Extra underlayment",
            "qty": "2",
            "unit_price": "75.00",
            "body": "<p>Synthetic</p>",
            "notes": "Bring extra",
        },
        headers=auth_headers,
    )
    item_id = item_resp.json()["id"]
    original_sort_order = item_resp.json()["sort_order"]

    resp = client.post(
        f"/api/change-orders/{co_id}/items/{item_id}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    dup = resp.json()
    assert dup["id"] != item_id
    assert dup["description"] == "Extra underlayment"
    assert Decimal(str(dup["qty"])) == Decimal("2")
    assert Decimal(str(dup["unit_price"])) == Decimal("75.00")
    assert Decimal(str(dup["line_total"])) == Decimal("150.00")
    assert dup["body"] == "<p>Synthetic</p>"
    assert dup["notes"] == "Bring extra"
    assert dup["sort_order"] > original_sort_order

    # CO subtotal doubled
    co = client.get(f"/api/change-orders/{co_id}", headers=auth_headers).json()
    assert Decimal(str(co["subtotal"])) == Decimal("300.00")
    assert len(co["items"]) == 2


def test_duplicate_co_item_not_found(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)
    co_resp = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={},
        headers=auth_headers,
    )
    co_id = co_resp.json()["id"]

    resp = client.post(
        f"/api/change-orders/{co_id}/items/9999/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_duplicate_co_item_wrong_co(client, auth_headers, seeded_stages, db_session):
    estimate = _create_approved_estimate(client, auth_headers, seeded_stages, db_session)

    co_a = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "A"},
        headers=auth_headers,
    ).json()
    co_b = client.post(
        f"/api/estimates/{estimate['id']}/change-orders",
        json={"name": "B"},
        headers=auth_headers,
    ).json()

    item = client.post(
        f"/api/change-orders/{co_a['id']}/items",
        json={"description": "Item", "qty": "1", "unit_price": "10"},
        headers=auth_headers,
    ).json()

    resp = client.post(
        f"/api/change-orders/{co_b['id']}/items/{item['id']}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_change_orders.py::test_duplicate_co_item -v
```
Expected: FAIL with 404 or 405 (endpoint does not exist).

- [ ] **Step 3: Implement the duplicate endpoint**

In `backend/app/routers/change_orders.py`, add this function immediately after the existing `delete_co_item` function (which ends around line 304):

```python
@router.post(
    "/api/change-orders/{co_id}/items/{item_id}/duplicate",
    response_model=ChangeOrderItemResponse,
    status_code=201,
)
def duplicate_co_item(
    co_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = (
        db.query(ChangeOrderItem)
        .filter(
            ChangeOrderItem.id == item_id,
            ChangeOrderItem.change_order_id == co_id,
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Change order item not found")

    max_order = (
        db.query(ChangeOrderItem.sort_order)
        .filter(ChangeOrderItem.change_order_id == co_id)
        .order_by(ChangeOrderItem.sort_order.desc())
        .first()
    )
    new_sort_order = (max_order[0] or 0) + 1 if max_order else 0

    duplicate = ChangeOrderItem(
        change_order_id=co_id,
        description=source.description,
        qty=source.qty,
        unit_price=source.unit_price,
        line_total=source.line_total,
        body=source.body,
        notes=source.notes,
        sort_order=new_sort_order,
    )
    db.add(duplicate)
    db.commit()

    recalculate_change_order(db, co_id)
    db.refresh(duplicate)
    return duplicate
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_change_orders.py::test_duplicate_co_item tests/test_change_orders.py::test_duplicate_co_item_not_found tests/test_change_orders.py::test_duplicate_co_item_wrong_co -v
```
Expected: 3 passed.

- [ ] **Step 5: Run the full change orders test file**

```bash
cd backend && pytest tests/test_change_orders.py -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/change_orders.py backend/tests/test_change_orders.py
git commit -m "Sprint 14a: Add duplicate endpoint for change order items"
```

---

## Task 3: Backend — full regression run

- [ ] **Step 1: Run the entire backend test suite**

```bash
cd backend && pytest -v
```
Expected: 410+ tests pass, no regressions (the pre-existing Saturday timing flake in `test_dashboard_tasks_due_this_week` is the only acceptable failure and only on Saturdays — today is not Saturday). 7 new tests added by Tasks 1–2, so target is 417+ passing.

- [ ] **Step 2: If any non-Saturday test fails, fix the root cause before proceeding**

Read the failure message, locate the cause in the new code, fix, and rerun Step 1 until green. Do NOT proceed to Task 4 until the suite is green.

---

## Task 4: Frontend — API client functions for duplicate

**Files:**
- Modify: `frontend/src/api/estimates.js`
- Modify: `frontend/src/api/changeOrders.js`

- [ ] **Step 1: Add `duplicateLineItem` to `estimates.js`**

Append to `frontend/src/api/estimates.js` (after the existing `deleteLineItem` around line 45):

```javascript
export const duplicateLineItem = async (estimateId, itemId) => {
  const { data } = await api.post(
    `/estimates/${estimateId}/line-items/${itemId}/duplicate`
  )
  return data
}
```

- [ ] **Step 2: Add `duplicateChangeOrderItem` to `changeOrders.js`**

Append to `frontend/src/api/changeOrders.js` (after the existing `deleteChangeOrderItem` around line 37):

```javascript
export const duplicateChangeOrderItem = async (coId, itemId) => {
  const { data } = await api.post(
    `/change-orders/${coId}/items/${itemId}/duplicate`
  )
  return data
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/estimates.js frontend/src/api/changeOrders.js
git commit -m "Sprint 14a: Add duplicate API client functions"
```

---

## Task 5: Frontend — shared BackButton component

**Files:**
- Create: `frontend/src/components/BackButton.jsx`

- [ ] **Step 1: Create the BackButton component**

Create `frontend/src/components/BackButton.jsx`:

```jsx
import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

/**
 * Consistent back-navigation button for detail pages.
 *
 * Always navigates to the supplied `to` path — we do NOT use `navigate(-1)`
 * because detail pages are reached via deep links (email, bookmarks, direct
 * URL) often enough that history-based back is unreliable.
 */
export default function BackButton({ to, label = 'Back' }) {
  return (
    <Link
      to={to}
      className="inline-flex items-center gap-1.5 text-sm text-slate-400 hover:text-amber-500 transition-colors mb-3"
    >
      <ArrowLeft size={16} />
      {label}
    </Link>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/BackButton.jsx
git commit -m "Sprint 14b: Add shared BackButton component"
```

---

## Task 6: Frontend — MaterialPickerModal component

**Files:**
- Create: `frontend/src/components/MaterialPickerModal.jsx`

- [ ] **Step 1: Create the picker modal**

Create `frontend/src/components/MaterialPickerModal.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { X, Search, Loader2 } from 'lucide-react'
import { listMaterials } from '../api/materials'

/**
 * Searchable material picker. When the user selects a material, calls
 * `onSelect(material)` with the full material record. The parent is
 * responsible for closing the picker and opening the edit modal pre-filled.
 */
export default function MaterialPickerModal({ onClose, onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Debounced search
  useEffect(() => {
    const handle = setTimeout(async () => {
      if (!query || query.trim().length < 2) {
        setResults([])
        return
      }
      setLoading(true)
      setError(null)
      try {
        const data = await listMaterials({ search: query.trim(), perPage: 20 })
        setResults(data.items || [])
      } catch (err) {
        setError('Failed to search materials')
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 250)
    return () => clearTimeout(handle)
  }, [query])

  const formatMoney = (value) => {
    const n = Number(value || 0)
    return `$${n.toFixed(2)}`
  }

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-start justify-center z-50 pt-20"
      onClick={onClose}
    >
      <div
        className="bg-navy-800 border border-slate-700 rounded-lg w-full max-w-2xl max-h-[70vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-white">Search Materials</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-4 border-b border-slate-700">
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="text"
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Type at least 2 characters..."
              className="w-full pl-9 pr-3 py-2 bg-navy-900 border border-slate-700 rounded text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex items-center justify-center py-8 text-slate-400">
              <Loader2 className="animate-spin mr-2" size={16} />
              Searching...
            </div>
          )}
          {error && (
            <div className="p-4 text-red-400 text-sm">{error}</div>
          )}
          {!loading && !error && query.trim().length >= 2 && results.length === 0 && (
            <div className="p-4 text-slate-400 text-sm">No materials found.</div>
          )}
          {!loading && results.length > 0 && (
            <ul className="divide-y divide-slate-700">
              {results.map((material) => (
                <li key={material.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(material)}
                    className="w-full text-left px-4 py-3 hover:bg-navy-900 transition-colors"
                  >
                    <div className="flex justify-between items-start gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-white truncate">
                          {material.description || '(no description)'}
                        </div>
                        <div className="text-xs text-slate-400 mt-0.5">
                          {material.item_number && (
                            <span className="mr-2">#{material.item_number}</span>
                          )}
                          {material.uom && <span>per {material.uom}</span>}
                        </div>
                      </div>
                      <div className="font-mono text-sm text-amber-500 whitespace-nowrap">
                        {formatMoney(material.unit_cost)}
                      </div>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/MaterialPickerModal.jsx
git commit -m "Sprint 14a: Add MaterialPickerModal for material search"
```

---

## Task 7: Frontend — AddItemSplitButton component

**Files:**
- Create: `frontend/src/components/AddItemSplitButton.jsx`

- [ ] **Step 1: Create the split button**

Create `frontend/src/components/AddItemSplitButton.jsx`:

```jsx
import { useEffect, useRef, useState } from 'react'
import { Plus, ChevronDown, FileText, Package } from 'lucide-react'

/**
 * Split button for adding a line item. Main click = blank item. Chevron click
 * = dropdown with "Blank Item" and "From Materials" options.
 *
 * Props:
 * - onAddBlank: () => void
 * - onAddFromMaterials: () => void
 * - label: optional main button text (default "Add Item")
 */
export default function AddItemSplitButton({
  onAddBlank,
  onAddFromMaterials,
  label = 'Add Item',
}) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  const handleBlank = () => {
    setOpen(false)
    onAddBlank()
  }

  const handleFromMaterials = () => {
    setOpen(false)
    onAddFromMaterials()
  }

  return (
    <div className="relative inline-flex" ref={menuRef}>
      <button
        type="button"
        onClick={handleBlank}
        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs bg-amber-500 hover:bg-amber-600 text-navy-900 font-semibold rounded-l border-r border-amber-700"
      >
        <Plus size={14} />
        {label}
      </button>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center px-2 py-1.5 bg-amber-500 hover:bg-amber-600 text-navy-900 rounded-r"
        aria-label="More add options"
      >
        <ChevronDown size={14} />
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 w-52 bg-navy-800 border border-slate-700 rounded shadow-lg z-30">
          <button
            type="button"
            onClick={handleBlank}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-navy-900 text-left"
          >
            <FileText size={14} className="text-slate-400" />
            Blank Item
          </button>
          <button
            type="button"
            onClick={handleFromMaterials}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-white hover:bg-navy-900 text-left border-t border-slate-700"
          >
            <Package size={14} className="text-slate-400" />
            From Materials
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AddItemSplitButton.jsx
git commit -m "Sprint 14a: Add AddItemSplitButton component"
```

---

## Task 8: Frontend — wire split button + material picker into estimate items

**Files:**
- Modify: `frontend/src/pages/EstimateDetailPage.jsx`

This task replaces the existing "Add Item" button (around line 1423) for estimate line items (not yet for CO items — that's Task 9) and adds state for the material picker.

- [ ] **Step 1: Add imports**

At the top of `EstimateDetailPage.jsx`, update the `../api/estimates` import (line 38-49) to include `duplicateLineItem`:

```jsx
import {
  getEstimate,
  updateEstimate,
  duplicateEstimate,
  addLineItem,
  updateLineItem,
  deleteLineItem,
  duplicateLineItem,
  reorderLineItems,
  createSection,
  updateSection,
  deleteSection,
} from '../api/estimates'
```

And update the `../api/changeOrders` import (line 50-58) to include `duplicateChangeOrderItem`:

```jsx
import {
  createChangeOrder,
  updateChangeOrder,
  deleteChangeOrder as deleteChangeOrderApi,
  addChangeOrderItem,
  updateChangeOrderItem,
  deleteChangeOrderItem,
  duplicateChangeOrderItem,
  sendChangeOrder,
} from '../api/changeOrders'
```

Add these new component imports at the end of the import block (after the existing imports):

```jsx
import AddItemSplitButton from '../components/AddItemSplitButton'
import MaterialPickerModal from '../components/MaterialPickerModal'
import BackButton from '../components/BackButton'
```

- [ ] **Step 2: Add state for the material picker and pending target**

Inside the `EstimateDetailPage` component, alongside the other `useState` hooks (near the top of the component), add:

```jsx
const [materialPicker, setMaterialPicker] = useState(null)
// materialPicker shape: null | { target: 'estimate', sectionId?: number | null }
//                    or  { target: 'co', coId: number }
```

- [ ] **Step 3: Add handlers that open the picker and apply the chosen material**

Add these handlers inside the `EstimateDetailPage` component, near the existing `handleAddItem` handler:

```jsx
const openMaterialPickerForEstimate = (sectionId = null) => {
  setMaterialPicker({ target: 'estimate', sectionId })
}

const openMaterialPickerForCO = (coId) => {
  setMaterialPicker({ target: 'co', coId })
}

const handleMaterialSelected = async (material) => {
  const picker = materialPicker
  setMaterialPicker(null)
  if (!picker) return
  try {
    if (picker.target === 'estimate') {
      const newItem = await addLineItem(id, {
        description: material.description || 'New item',
        qty: '1',
        unit_price: String(material.unit_cost ?? '0.00'),
        section_id: picker.sectionId ?? null,
      })
      await fetchEstimate()
      showToast('Item added from materials', 'success')
      // Open edit modal so user can adjust qty/price
      setEditingLineItem(newItem)
    } else if (picker.target === 'co') {
      await addChangeOrderItem(picker.coId, {
        description: material.description || 'New item',
        qty: '1',
        unit_price: String(material.unit_cost ?? '0.00'),
      })
      await fetchEstimate()
      showToast('Item added from materials', 'success')
    }
  } catch (err) {
    showToast('Failed to add material', 'error')
  }
}
```

**Note on `setEditingLineItem`:** if the current code uses a different state setter to open `LineItemEditModal` (e.g. `setSelectedLineItem`), use that name instead. Confirm by searching the file for `LineItemEditModal` — the state setter passed to it is the one to call. If no state-setter-based approach exists (e.g. items are edited via an inline component), omit the last line and simply rely on the new row appearing in the list; the user can click pencil to adjust.

- [ ] **Step 4: Replace the main estimate "Add Item" button with the split button**

Find the existing "Add Item" button in `EstimateDetailPage.jsx` (around line 1423, the one that is rendered inside the estimate line-items list, NOT the one inside each section and NOT the one inside change-order cards). Replace this block:

```jsx
<button onClick={() => handleAddItem()}>
  <Plus size={14} />
  Add Item
</button>
```

With:

```jsx
<AddItemSplitButton
  onAddBlank={() => handleAddItem()}
  onAddFromMaterials={() => openMaterialPickerForEstimate(null)}
/>
```

Also replace the per-section "Add Item" buttons (any additional occurrences that call `handleAddItem(section.id)`) with:

```jsx
<AddItemSplitButton
  onAddBlank={() => handleAddItem(section.id)}
  onAddFromMaterials={() => openMaterialPickerForEstimate(section.id)}
/>
```

Leave CO "Add Item" buttons alone — Task 9 handles those.

- [ ] **Step 5: Render the material picker near the bottom of the component's JSX**

Find the spot where other modals are rendered (`LineItemEditModal`, `SectionEditModal`, etc.) near the end of the `return (...)` block. Add:

```jsx
{materialPicker && (
  <MaterialPickerModal
    onClose={() => setMaterialPicker(null)}
    onSelect={handleMaterialSelected}
  />
)}
```

- [ ] **Step 6: Build the frontend to confirm no syntax errors**

```bash
cd frontend && npm run build
```
Expected: build succeeds with no errors.

- [ ] **Step 7: Manual smoke test**

Start the dev server and verify in the browser:

```bash
cd frontend && npm run dev
```

Then in the browser (logged in):
1. Open any estimate detail page.
2. Click the "Add Item" main button → blank item appears (existing behavior).
3. Click the chevron → dropdown appears with "Blank Item" and "From Materials".
4. Click "From Materials" → picker modal opens with a search input.
5. Type 2+ characters → results appear within ~300ms.
6. Click a result → picker closes, item appears at the bottom with description and unit_cost pre-filled.
7. For an estimate with sections, the per-section split button adds the item to that section.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/EstimateDetailPage.jsx
git commit -m "Sprint 14a: Add split button + material picker to estimate items"
```

---

## Task 9: Frontend — split button + material picker for change order items

**Files:**
- Modify: `frontend/src/pages/EstimateDetailPage.jsx`

- [ ] **Step 1: Replace the CO "Add Item" button inside each change-order card**

Find the CO `<button onClick={() => handleAddCOItem(co.id)}>` around line 1587 and replace with:

```jsx
<AddItemSplitButton
  onAddBlank={() => handleAddCOItem(co.id)}
  onAddFromMaterials={() => openMaterialPickerForCO(co.id)}
/>
```

- [ ] **Step 2: Build**

```bash
cd frontend && npm run build
```
Expected: succeeds.

- [ ] **Step 3: Manual smoke test**

1. Open an approved estimate with a change order.
2. On the change order card, click the "Add Item" chevron → dropdown appears.
3. Click "From Materials" → picker opens, selecting a material adds it to the CO.
4. Verify CO subtotal updates.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EstimateDetailPage.jsx
git commit -m "Sprint 14a: Add split button + material picker to change order items"
```

---

## Task 10: Frontend — duplicate line item icon (estimate items)

**Files:**
- Modify: `frontend/src/pages/EstimateDetailPage.jsx`

- [ ] **Step 1: Add the duplicate handler for estimate items**

Near `handleAddItem` / `handleDeleteItem`, add:

```jsx
const handleDuplicateItem = async (itemId) => {
  try {
    await duplicateLineItem(id, itemId)
    await fetchEstimate()
    showToast('Item duplicated', 'success')
  } catch (err) {
    showToast('Failed to duplicate item', 'error')
  }
}
```

- [ ] **Step 2: Add a copy button to `SortableRow`**

Locate the `SortableRow` component (around lines 345-439). In its trailing actions area where the edit (`Pencil`) and delete (`Trash2`) buttons are rendered, add a copy button between them. Confirm `Copy` is already imported from `lucide-react` (it is — line 7 of the file).

The `SortableRow` component receives props — it currently takes handlers for edit and delete. Add `onDuplicate` to its props destructuring:

```jsx
function SortableRow({ item, onEdit, onDelete, onDuplicate, /* other existing props */ }) {
```

In the actions area of the row JSX, add this button next to the edit button:

```jsx
<button
  type="button"
  onClick={(e) => {
    e.stopPropagation()
    onDuplicate(item.id)
  }}
  className="p-1 text-slate-400 hover:text-amber-500"
  title="Duplicate item"
>
  <Copy size={14} />
</button>
```

- [ ] **Step 3: Pass `onDuplicate` when rendering `SortableRow`**

Find every place `SortableRow` is rendered in `EstimateDetailPage.jsx` (for the main list and for each section). Add the prop:

```jsx
<SortableRow
  /* existing props ... */
  onDuplicate={handleDuplicateItem}
/>
```

- [ ] **Step 4: Build and smoke test**

```bash
cd frontend && npm run build
```

Then:
1. Open an estimate with at least one line item.
2. Click the copy icon on a row → a new row appears at the bottom with identical fields.
3. Verify subtotal doubled.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/EstimateDetailPage.jsx
git commit -m "Sprint 14a: Add duplicate icon to estimate line items"
```

---

## Task 11: Frontend — duplicate line item icon (change order items)

**Files:**
- Modify: `frontend/src/pages/EstimateDetailPage.jsx`

- [ ] **Step 1: Add the duplicate handler for CO items**

Near the existing CO item handlers, add:

```jsx
const handleDuplicateCOItem = async (coId, itemId) => {
  try {
    await duplicateChangeOrderItem(coId, itemId)
    await fetchEstimate()
    showToast('Item duplicated', 'success')
  } catch (err) {
    showToast('Failed to duplicate item', 'error')
  }
}
```

- [ ] **Step 2: Add a copy button next to the existing edit/delete buttons on each CO item row**

Find the CO item row rendering (the area around line 1587 onward that lists CO items with edit/delete buttons — search for `handleDeleteCOItem` to locate it). Add a copy button in the actions area of each CO item row:

```jsx
<button
  type="button"
  onClick={() => handleDuplicateCOItem(co.id, item.id)}
  className="p-1 text-slate-400 hover:text-amber-500"
  title="Duplicate item"
>
  <Copy size={14} />
</button>
```

Place this between the edit and delete buttons so the order is: edit, duplicate, delete — matching the estimate line item row.

- [ ] **Step 3: Build and smoke test**

```bash
cd frontend && npm run build
```

Then:
1. Open an approved estimate with a change order that has at least one item.
2. Click the copy icon on a CO item → duplicate appears at the bottom of the CO's items.
3. Verify CO subtotal doubled.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/EstimateDetailPage.jsx
git commit -m "Sprint 14a: Add duplicate icon to change order items"
```

---

## Task 12: Frontend — BackButton on EstimateDetailPage

**Files:**
- Modify: `frontend/src/pages/EstimateDetailPage.jsx`

- [ ] **Step 1: Render BackButton above the page title**

In the main header area of the estimate detail page (around line 1127-1155), add a `<BackButton>` immediately above the page title/breadcrumb. The component should route to the parent job:

```jsx
{estimate?.job_id && (
  <BackButton to={`/jobs/${estimate.job_id}`} label="Back to Job" />
)}
```

Place this inside the main content container but above any breadcrumb or title element. If there is an existing contextual back button (the one at line ~1150 that uses `navigate('/jobs/${estimate.job_id}')`), remove it — the new BackButton replaces it. The breadcrumb can stay.

- [ ] **Step 2: Build and smoke test**

```bash
cd frontend && npm run build
```

Then:
1. Open an estimate — BackButton visible at top left, labeled "Back to Job".
2. Click it → lands on the parent job detail page.
3. Directly enter an estimate URL in the browser → BackButton still visible and still routes to the parent job.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/EstimateDetailPage.jsx
git commit -m "Sprint 14c: Add BackButton to EstimateDetailPage"
```

---

## Task 13: Frontend — BackButton on JobDetailPage

**Files:**
- Modify: `frontend/src/pages/JobDetailPage.jsx`

- [ ] **Step 1: Add the import**

At the top of `JobDetailPage.jsx`, add:

```jsx
import BackButton from '../components/BackButton'
```

- [ ] **Step 2: Render BackButton above the job title**

In the main header area (around lines 171-179 where the existing breadcrumb lives), add above the breadcrumb:

```jsx
<BackButton to="/jobs" label="Back to Jobs" />
```

Leave the existing breadcrumb alone — BackButton complements it.

- [ ] **Step 3: Build and smoke test**

```bash
cd frontend && npm run build
```

Then:
1. Open a job → BackButton visible at top left.
2. Click it → lands on `/jobs`.
3. Open a job via direct URL → BackButton still works.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/JobDetailPage.jsx
git commit -m "Sprint 14c: Add BackButton to JobDetailPage"
```

---

## Task 14: Frontend — BackButton on InvoiceDetailPage

**Files:**
- Modify: `frontend/src/pages/InvoiceDetailPage.jsx`

- [ ] **Step 1: Add the import**

At the top of `InvoiceDetailPage.jsx`, add:

```jsx
import BackButton from '../components/BackButton'
```

- [ ] **Step 2: Replace the existing ad-hoc back button with BackButton**

Find the existing back button in `InvoiceDetailPage.jsx` (around lines 534-538 — the one using `navigate('/invoices')`). Replace the entire ad-hoc button JSX with:

```jsx
<BackButton to="/invoices" label="Back to Invoices" />
```

- [ ] **Step 3: Build and smoke test**

```bash
cd frontend && npm run build
```

Then:
1. Open an invoice → BackButton visible.
2. Click it → lands on `/invoices`.
3. Open an invoice via direct URL → BackButton still works.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/InvoiceDetailPage.jsx
git commit -m "Sprint 14c: Add BackButton to InvoiceDetailPage"
```

---

## Task 15: Frontend — BackButton on ContactDetailPage

**Files:**
- Modify: `frontend/src/pages/ContactDetailPage.jsx`

- [ ] **Step 1: Add the import**

At the top of `ContactDetailPage.jsx`, add:

```jsx
import BackButton from '../components/BackButton'
```

- [ ] **Step 2: Render BackButton above the existing breadcrumb**

In the main header area (around lines 140-150), add above the breadcrumb:

```jsx
<BackButton to="/contacts" label="Back to Contacts" />
```

Leave the existing breadcrumb alone.

- [ ] **Step 3: Build and smoke test**

```bash
cd frontend && npm run build
```

Then:
1. Open a contact → BackButton visible.
2. Click it → lands on `/contacts`.
3. Open a contact via direct URL → BackButton still works.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ContactDetailPage.jsx
git commit -m "Sprint 14c: Add BackButton to ContactDetailPage"
```

---

## Task 16: Final verification

- [ ] **Step 1: Run the full backend test suite one more time**

```bash
cd backend && pytest -v
```
Expected: 417+ tests pass (410 original + 7 new). Only the known Saturday timing flake may fail, and only on Saturdays.

- [ ] **Step 2: Run the frontend build**

```bash
cd frontend && npm run build
```
Expected: clean build.

- [ ] **Step 3: Manual end-to-end verification checklist**

Start dev servers:
```bash
docker-compose up -d
```

Verify each item in the Sprint 14 spec checklist:

1. Create an estimate, add a blank line item — works.
2. Create an estimate, search materials in the picker, add pre-filled item — works.
3. Edit a pre-filled item to change the price, save — totals update correctly.
4. Duplicate an estimate line item — copy appears at bottom with identical fields; subtotal updates.
5. Duplicate a CO item — copy appears at bottom with identical fields; CO subtotal updates.
6. Navigate to estimate detail, click BackButton — goes to parent job.
7. Navigate to job detail, click BackButton — goes to jobs list.
8. Navigate to invoice detail, click BackButton — goes to invoices list.
9. Navigate to contact detail, click BackButton — goes to contacts list.
10. Direct-link to an estimate detail (paste URL), click BackButton — goes to job (not broken).

- [ ] **Step 4: If everything passes, no further commits needed**

The sprint is complete. The plan is done.

---

## Self-Review Notes

- **Spec coverage:**
  - Feature 1 (blank vs materials) → Tasks 6, 7, 8, 9.
  - Feature 2 (duplicate) → Tasks 1, 2, 4, 10, 11.
  - Feature 3 (back button) → Tasks 5, 12, 13, 14, 15.
  - EmployeeDetailPage was dropped because no such page exists (employees are managed inline at `/settings/employees`), as noted in the design doc.
- **Anti-patterns honored:** no data model changes, no migrations, no calculation engine changes, no "Add Multiple Items", no optional items, no customer portal or PDF output changes.
- **TDD discipline:** backend endpoints have red-green-refactor. Frontend is smoke-tested manually per the project's convention (no existing frontend test infrastructure).
- **Types consistency:** API function names are used identically in tasks 4, 8, 9, 10, 11. Component prop names (`onAddBlank`, `onAddFromMaterials`, `onDuplicate`, `onSelect`, `onClose`, `to`, `label`) are consistent across all consumption sites.
