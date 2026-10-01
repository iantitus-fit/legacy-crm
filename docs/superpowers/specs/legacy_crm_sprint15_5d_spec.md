# Legacy CRM — Sprint 15.5d: Quick Client Search

**Scope:** Global search bar in the app header that searches clients by name, phone, email, company, or address with typeahead results and direct navigation to client profiles.
**Source:** Marcus's feedback — "Quick client search: type name → auto-populates contact info with edit button to modify contact details, job address, etc."
**Reference:** DripJobs has "Search leads, contacts, tags..." in the top header bar
**Estimated build time:** 20–30 min in Claude Code

---

## Context

The CRM already has a contacts list page with search and pagination (`GET /api/contacts?search=...`). But that requires navigating to the contacts page first. Marcus wants to search from anywhere — type a name in the header, see matching clients instantly, click through to their profile. DripJobs has this as a persistent search bar in the top nav.

After the restructure, Contact = Client Profile. The client profile page already shows all contact details with inline editing. So "auto-populate + edit button" in Marcus's request = navigate to client profile, where everything is already editable.

---

## What's Changing

### Backend Changes

**NEW endpoint: `GET /api/contacts/search`**

A lightweight search endpoint optimized for typeahead. Separate from the full paginated contacts list.

```
GET /api/contacts/search?q=kevin&limit=8

Response: [
  {
    "id": 1,
    "name": "Gary Lindqvist",
    "company": "Bluewater Pool Service",
    "email": "office@bluewater-pools.example",
    "phone": "(317) 555-0142",
    "address": "4410 Fernhollow Rd, Laurel, IN 47024",
    "client_type": "residential",
    "lead_source": "referral"
  },
  ...
]
```

- Searches across: `name`, `email`, `phone`, `company`, `address` fields (case-insensitive ILIKE)
- `q` parameter required, minimum 2 characters (return empty array if < 2 chars)
- `limit` parameter optional, default 8, max 15
- Returns flat array (no pagination wrapper — this is a typeahead, not a list page)
- Ordered by name alphabetically
- Uses OR matching: `WHERE name ILIKE %q% OR email ILIKE %q% OR phone ILIKE %q% OR company ILIKE %q% OR address ILIKE %q%`

**MODIFIED: `backend/app/routers/contacts.py`**
- Add the new search endpoint. Keep it separate from the existing paginated list endpoint — different response shape, different use case.

**MODIFIED: `backend/app/schemas/contact.py`**
- Add `ContactSearchResult` schema with just the fields needed for the dropdown (id, name, company, email, phone, address, client_type, lead_source). This is a subset of the full ContactResponse.

### Frontend Changes

**NEW component: `frontend/src/components/GlobalSearch.jsx`**

A search bar component that lives in the app header/top bar area.

**Layout:**
- Search icon + input field in the top bar (to the right of the sidebar toggle on mobile, or in the main content header area)
- Placeholder text: "Search clients..."
- Full width on mobile, ~300px on desktop
- If the app currently has no top bar/header component, add a minimal one: just the search bar and optionally the user avatar/name on the right

**Behavior:**
- On focus: input expands slightly (subtle visual cue)
- On typing (debounced, 300ms): calls `GET /api/contacts/search?q={input}&limit=8`
- Results appear in a dropdown below the search bar
- Each result row shows:
  ```
  [Avatar] Gary Lindqvist                    (317) 555-0142
           Bluewater Pool Service · Laurel, IN
  ```
  - Avatar: initials circle (same pattern used on pipeline cards and client profile)
  - Name: bold, primary text
  - Phone: right-aligned, secondary text
  - Second line: company + city/state extracted from address, muted text
- Click a result → navigate to `/contacts/{id}` (client profile page), close dropdown, clear search
- Keyboard nav: up/down arrows to highlight results, Enter to navigate to highlighted result, Escape to close dropdown
- Empty state (no results): "No clients found"
- Loading state: small spinner in the input or below it
- Click outside dropdown → close it
- On navigate away (route change) → close dropdown and clear input

**Styling:**
- Use theme-aware CSS variables (works in both light and dark themes)
- Dropdown: card with shadow, same background as other dropdowns/modals in the app
- Results: hover highlight on each row
- Match the overall visual language of the existing UI (no new design system elements)

**Mobile considerations:**
- On mobile (< 768px): search bar could be an icon that expands to full-width input on tap
- Or: always visible as a compact bar below the sidebar toggle
- Dropdown results should be full-width on mobile
- Tap a result → navigate + close (same as desktop)

**NEW file: `frontend/src/api/contacts.js`** (or modify existing)
- Add `searchContacts(query)` function that calls `GET /api/contacts/search?q=${query}&limit=8`
- Uses the authenticated API client (same as other API calls)

### Where It Goes in the Layout

**Option A (preferred): Add to the existing Layout component**
- The Layout component wraps all authenticated pages (sidebar + main content area)
- Add the search bar to the top of the main content area, as a sticky header bar
- This is where DripJobs puts it — top of the page, always accessible

**Option B: Add to sidebar**
- Search bar at the top of the sidebar, above the nav items
- Works but less prominent on mobile when sidebar is collapsed

Claude Code should check the current Layout component structure and pick the option that fits cleanly. Option A is preferred if there's a natural place for it.

---

## What This Does NOT Include

- **Search across estimates/invoices/tasks** — This searches clients only. A unified search across all entities is a bigger feature for later.
- **Search from pipeline cards** — Pipeline boards have their own filter system. This is separate.
- **Inline editing from search results** — Results navigate to the client profile, where editing already works. No inline editing in the dropdown itself.
- **Recent searches or search history** — Not needed for v1.
- **"Create new client" from search** — If no results found, Marcus should use the existing "+ New Lead" flow. Could add a "Create Client" link in the empty state later, but not in this sprint.

---

## Tests

**NEW backend tests:**
1. `GET /api/contacts/search?q=kevin` → returns matching contacts
2. `GET /api/contacts/search?q=kevin` → response includes id, name, company, email, phone, address
3. `GET /api/contacts/search?q=k` → returns empty array (below 2-char minimum)
4. `GET /api/contacts/search?q=nonexistent` → returns empty array
5. `GET /api/contacts/search?q=317` → matches by phone number
6. `GET /api/contacts/search?q=pool` → matches by company name
7. `GET /api/contacts/search` (no q param) → returns 422 or empty array
8. Unauthenticated request → 401

**No frontend tests** — the search component is UI behavior, tested manually.

---

## Verification Checklist

- [ ] Search bar visible in app header on all authenticated pages
- [ ] Typing 2+ characters triggers search after 300ms debounce
- [ ] Results show name, company, phone, address preview
- [ ] Clicking a result navigates to client profile page
- [ ] Keyboard navigation works (up/down/enter/escape)
- [ ] Empty state shows "No clients found"
- [ ] Search works by name, phone, email, company, address
- [ ] Dropdown closes on click outside, escape, or navigation
- [ ] Works in both light and dark themes
- [ ] Works on mobile viewports (375px+)
- [ ] All existing tests pass (455+)
- [ ] New backend tests pass (8+)

---

## Claude Code Prompt

```
Read CLAUDE.md and PRD.md. Sprint 15.5a (tax toggle) and 15.5b (CO accepted dates) complete. 455 tests passing. Latest migration: 0023. Production deployed to Azure.

Sprint 15.5d: Add global quick client search bar.

BACKEND:
1. Add GET /api/contacts/search endpoint in contacts.py. Parameters: q (required string, min 2 chars), limit (optional int, default 8, max 15). Searches contacts by name, email, phone, company, address using case-insensitive ILIKE with OR matching. Returns flat JSON array (not paginated). Order by name ASC.
2. Add ContactSearchResult schema: id, name, company (optional), email (optional), phone (optional), address (optional), client_type (optional), lead_source (optional).
3. Return empty array if q is less than 2 characters.
4. Endpoint requires authentication (same as other contact endpoints).

FRONTEND:
5. Create GlobalSearch.jsx component: search input with debounced typeahead (300ms delay), dropdown results panel.
6. Each result row shows: initials avatar, name (bold), phone (right-aligned), second line with company and city/state. Click navigates to /contacts/{id}.
7. Keyboard navigation: up/down arrows to highlight, Enter to select, Escape to close.
8. Empty state: "No clients found". Loading state: spinner in input.
9. Add GlobalSearch to the Layout component — place it as a sticky bar at the top of the main content area, or in whatever header area exists. Check the current Layout structure and place it where it fits naturally. DripJobs reference: search bar at the very top of the page.
10. Style with theme-aware CSS variables (must work in both light and dark themes). Dropdown uses card styling consistent with the rest of the app.
11. On mobile (< 768px): search bar should be usable. Can be a search icon that expands, or a compact always-visible bar. Results dropdown full-width.
12. Add searchContacts(query) function to the contacts API client.

TESTS:
13. Test search by name → returns matching contacts.
14. Test response shape includes required fields.
15. Test q less than 2 chars → empty array.
16. Test no matches → empty array.
17. Test search by phone → matches.
18. Test search by company → matches.
19. Test missing q param → 422 or empty array.
20. Test unauthenticated → 401.

ANTI-PATTERNS:
- Do NOT reuse the existing paginated contacts list endpoint. Create a separate lightweight search endpoint.
- Do NOT add search across estimates, invoices, or tasks. Clients only.
- Do NOT add inline editing in the search dropdown. Click navigates to client profile where editing already works.
- Do NOT add a new top-level page. This is a component embedded in the existing Layout.

Run pytest after all changes. All existing tests must pass plus 8+ new tests.
```
