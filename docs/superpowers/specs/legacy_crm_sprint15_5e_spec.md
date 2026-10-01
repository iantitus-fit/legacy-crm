# Legacy CRM — Sprint 15.5e: Line Item Description Editor Enhancements

**Scope:** Add font size options and text highlight to the existing React-Quill editor in the line item edit modal.
**Source:** Marcus's feedback — "Line item description editor: option to increase font size and highlight text"
**Reference:** DripJobs call transcript — "we can bold it... different highlight... different size fonts"
**Estimated build time:** 10–15 min in Claude Code

---

## Context

Sprint 10a added React-Quill (`react-quill-new`) to the `LineItemEditModal` for line item descriptions. The current toolbar supports: bold, italic, underline, bullet list, numbered list. The `body` field stores HTML in the database.

Marcus wants two additions: font size options (so he can make section headers or key terms larger) and text highlighting (background color, so he can call attention to important details in the scope of work).

This is a toolbar configuration change — no new backend fields, no new endpoints, no migration.

---

## What's Changing

### Frontend Changes

**MODIFIED: `frontend/src/pages/EstimateDetailPage.jsx`** (or wherever the React-Quill toolbar config lives — may be in LineItemEditModal or a shared config)

**Current toolbar config** (approximate):
```javascript
modules = {
  toolbar: [
    ['bold', 'italic', 'underline'],
    [{ list: 'ordered' }, { list: 'bullet' }],
  ]
}
```

**Updated toolbar config:**
```javascript
modules = {
  toolbar: [
    [{ size: ['small', false, 'large', 'huge'] }],
    ['bold', 'italic', 'underline'],
    [{ list: 'ordered' }, { list: 'bullet' }],
    [{ background: [] }],
    ['clean'],
  ]
}
```

What each addition does:
- **`{ size: [...] }`** — Dropdown with font size options: Small, Normal (default), Large, Huge. React-Quill renders these as CSS classes: `ql-size-small`, `ql-size-large`, `ql-size-huge`. Normal has no class.
- **`{ background: [] }`** — Background color picker (highlight). Empty array = default color palette. React-Quill renders as inline `style="background-color: ..."`.
- **`'clean'`** — "Remove formatting" button (eraser icon). Good to have now that there are more formatting options — lets users clear formatting without manually toggling each option.

**Quill CSS for size classes:**

React-Quill's default CSS may not include size definitions for the rendered content (only for the editor). Add CSS for the size classes so they render correctly both inside the editor and in the description preview below line items:

```css
.ql-size-small { font-size: 0.75em; }
.ql-size-large { font-size: 1.5em; }
.ql-size-huge { font-size: 2em; }
```

This CSS needs to exist in:
1. The estimate detail page (or global styles) — so the description preview below line items renders sizes correctly
2. The React-Quill editor itself — usually handled by importing `react-quill-new/dist/quill.snow.css`, but verify the size classes are included

**Theme awareness:**
- The background highlight colors from Quill's default palette include yellow, green, blue, pink, etc. These work fine in both light and dark themes because they're applied as background colors on the text itself.
- The Quill toolbar dropdown and color picker should work with the existing dark-themed Quill setup from Sprint 10a. If the toolbar dropdowns are hard to read in dark mode, add targeted CSS overrides.

### PDF Template Changes

**MODIFIED: `backend/app/templates/estimate_pdf.html`**

The PDF template renders line item descriptions using `{{ item.body|safe }}`. The HTML contains Quill's CSS classes for sizes. WeasyPrint needs to know what those classes mean.

Add to the `<style>` block in the PDF template:
```css
/* React-Quill font size classes */
.ql-size-small { font-size: 0.75em; }
.ql-size-large { font-size: 1.5em; }
.ql-size-huge { font-size: 2em; }
```

Background colors render via inline styles (e.g., `style="background-color: yellow"`), which WeasyPrint handles natively — no additional CSS needed for highlights.

### Customer Portal Changes

**MODIFIED: Customer portal estimate preview template** (the HTML preview endpoint)

Same CSS addition — add the Quill size classes so font sizes render correctly in the customer-facing estimate view. Check whether the preview shares the same template as the PDF or uses a separate one, and add the size CSS to whichever template serves the portal preview.

### Change Order PDF Template

**MODIFIED: `backend/app/templates/change_order_pdf.html`**

Same CSS addition for size classes. CO items use the same `body` field with the same editor.

### Section Description Rendering

Estimate sections also use React-Quill for their descriptions (Sprint 10b). The section description editor should get the same toolbar updates. Check whether sections share the same Quill config as line items — if so, one change covers both. If they have a separate config, update both.

---

## What This Does NOT Change

- **Backend:** No changes. The `body` field already stores HTML. Font sizes and highlights are just different HTML/CSS that the existing field handles fine.
- **Database:** No migration. Same TEXT column.
- **Line item data model:** No new fields.
- **Existing descriptions:** All existing descriptions are unaffected. They were created with bold/italic/underline/lists and will continue to render correctly. The new toolbar options are additive.

---

## Downstream Impact Check

| System | Impact | Action |
|--------|--------|--------|
| Line item edit modal | Toolbar gains size + highlight + clean | Update toolbar config |
| Description preview (estimate page) | Must render size classes | Add CSS for ql-size-* |
| Estimate PDF | Must render size classes | Add CSS to template |
| Customer portal preview | Must render size classes | Add CSS to template |
| Change order PDF | Must render size classes | Add CSS to template |
| Invoice PDF | Invoice items have body field too | Add CSS to invoice template |
| Section descriptions | Same editor | Verify shared config or update separately |
| Estimate duplicate | Copies body field HTML | No change needed |
| Template apply | Copies body from template items | No change needed |

---

## Tests

No new backend tests needed — this is a frontend toolbar config change and CSS additions to templates. The body field already accepts and stores any HTML content.

**Manual verification:**
1. Open line item edit modal → see size dropdown, highlight button, clean button in toolbar
2. Set text to "Large" size → preview shows larger text
3. Highlight text yellow → preview shows yellow background
4. Download PDF → sizes and highlights render correctly
5. Customer portal → sizes and highlights render correctly
6. Section description editor → same toolbar options available
7. Existing descriptions without new formatting → render unchanged

---

## Verification Checklist

- [ ] Font size dropdown appears in line item editor toolbar (Small, Normal, Large, Huge)
- [ ] Background highlight color picker appears in toolbar
- [ ] "Clean formatting" button appears in toolbar
- [ ] Size changes render in description preview below line items
- [ ] Highlight renders in description preview below line items
- [ ] Estimate PDF renders font sizes correctly
- [ ] Estimate PDF renders highlight colors correctly
- [ ] Customer portal preview renders sizes and highlights
- [ ] Change order PDF renders sizes and highlights
- [ ] Invoice PDF renders sizes and highlights (if body field is used)
- [ ] Section description editor has same toolbar enhancements
- [ ] Dark theme: toolbar dropdowns are readable
- [ ] Light theme: toolbar dropdowns are readable
- [ ] Existing descriptions render unchanged
- [ ] All existing tests pass (455+)

---

## Claude Code Prompt

```
Read CLAUDE.md and PRD.md. Sprints 15.5a-15.5d complete. 455+ tests passing. Latest migration: 0023. Production deployed to Azure.

Sprint 15.5e: Enhance the line item description editor with font size and highlight options.

FRONTEND:
1. Find the React-Quill toolbar configuration for the LineItemEditModal (and section description editor if separate). Currently has: bold, italic, underline, ordered list, bullet list.
2. Add to the toolbar: font size dropdown ({ size: ['small', false, 'large', 'huge'] }), background highlight color picker ({ background: [] }), and clean formatting button ('clean'). Place size dropdown first, then existing formatting, then highlight, then clean.
3. Add CSS for Quill size classes so they render in the description preview below line items: .ql-size-small { font-size: 0.75em; } .ql-size-large { font-size: 1.5em; } .ql-size-huge { font-size: 2em; }
4. Verify the toolbar dropdowns are readable in both light and dark themes. If the Quill dropdowns have contrast issues in dark mode, add targeted CSS overrides.
5. If section descriptions use a separate Quill config, update that toolbar too.

PDF TEMPLATES:
6. Add the same .ql-size-small, .ql-size-large, .ql-size-huge CSS rules to the <style> block in:
   - backend/app/templates/estimate_pdf.html
   - backend/app/templates/change_order_pdf.html
   - backend/app/templates/invoice_pdf.html (if it renders item body fields)
7. Background highlight colors use inline styles (style="background-color: ...") which WeasyPrint handles natively — no extra CSS needed for those.

PORTAL:
8. Check the customer portal estimate preview — if it uses a separate template that renders line item descriptions, add the size CSS there too. If it reuses the PDF template, no additional change needed.

ANTI-PATTERNS:
- Do NOT change the backend or database. The body TEXT field already stores any HTML.
- Do NOT add a full rich text toolbar (no images, no links, no headers/H1-H6, no tables). Keep it focused: size, bold, italic, underline, lists, highlight, clean.
- Do NOT replace React-Quill with a different editor.

Run pytest after all changes to verify no regressions.
```
