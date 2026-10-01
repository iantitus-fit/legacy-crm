# Legacy CRM — Sprint 15 Spec: Light/Dark Theming

**Date:** April 12, 2026
**Source:** Marcus Hale (confirmed preferences April 11)
**Prerequisite:** Data model restructure (Sub-sprints A–E) complete. 445 tests passing. Latest migration: 0021.

---

## Overview

The CRM currently has a single dark navy/slate theme. Marcus wants two branded themes with a user-level toggle:

1. **Light theme** — white background, black text, purple and teal accents (similar to DripJobs' visual style)
2. **Dark theme** — deep purple/black background, white text, teal accents

Both themes use the same brand palette: purple (~#6B21A8), teal (~#06B6D4), white, black.

---

## Brand Color Palette

These are the source colors. The spec defines semantic tokens below that reference these.

| Name | Hex | Usage |
|------|-----|-------|
| Purple 900 | #4C1D95 | Dark theme sidebar, deep accents |
| Purple 800 | #5B21B6 | Dark theme background tones |
| Purple 700 | #6D28D9 | Primary buttons, active states |
| Purple 600 | #7C3AED | Hover states, lighter accents |
| Purple 500 | #8B5CF6 | Light theme accent text, badges |
| Purple 100 | #EDE9FE | Light theme hover backgrounds, subtle fills |
| Purple 50 | #F5F3FF | Light theme card backgrounds (alternate) |
| Teal 600 | #0D9488 | Secondary accent, success-adjacent |
| Teal 500 | #14B8A6 | Active badges, status indicators |
| Teal 400 | #2DD4BF | Dark theme accent highlights |
| Teal 100 | #CCFBF1 | Light theme teal badges/fills |
| White | #FFFFFF | Light theme backgrounds |
| Gray 50 | #F9FAFB | Light theme page background |
| Gray 100 | #F3F4F6 | Light theme card backgrounds |
| Gray 200 | #E5E7EB | Light theme borders |
| Gray 300 | #D1D5DB | Light theme dividers |
| Gray 500 | #6B7280 | Secondary text (both themes) |
| Gray 700 | #374151 | Light theme primary text |
| Gray 900 | #111827 | Light theme headings |
| Slate 900 | #0F172A | Dark theme deep background |
| Slate 800 | #1E1B3A | Dark theme card/surface (purple-tinted) |
| Slate 700 | #2D2A4A | Dark theme elevated surfaces |

**Note:** The dark theme shifts from the current navy/blue-gray tones to purple-tinted dark tones. This is the "purple dark theme" Marcus requested. The exact hex values above are starting points — Claude Code should tune them during implementation so the contrast ratios meet WCAG AA (4.5:1 for body text, 3:1 for large text/UI elements).

---

## CSS Variable Architecture

The app needs a semantic token layer so components reference tokens, not raw colors. This is the core of the theming system.

### Implementation approach

Use CSS custom properties on `:root` with a `[data-theme="dark"]` override on the `<html>` element. No Tailwind dark: prefix, no class-based toggling on individual components — one attribute swap at the root changes everything.

```css
:root {
  /* Backgrounds */
  --bg-primary: #FFFFFF;
  --bg-secondary: #F9FAFB;
  --bg-surface: #FFFFFF;
  --bg-surface-hover: #F3F4F6;
  --bg-sidebar: #FFFFFF;
  --bg-input: #FFFFFF;
  --bg-modal: #FFFFFF;

  /* Text */
  --text-primary: #111827;
  --text-secondary: #6B7280;
  --text-muted: #9CA3AF;
  --text-inverse: #FFFFFF;

  /* Borders */
  --border-primary: #E5E7EB;
  --border-secondary: #D1D5DB;
  --border-focus: #7C3AED;

  /* Brand */
  --brand-purple: #7C3AED;
  --brand-purple-hover: #6D28D9;
  --brand-purple-light: #EDE9FE;
  --brand-purple-text: #6D28D9;
  --brand-teal: #14B8A6;
  --brand-teal-hover: #0D9488;
  --brand-teal-light: #CCFBF1;
  --brand-teal-text: #0D9488;

  /* Sidebar */
  --sidebar-bg: #FFFFFF;
  --sidebar-text: #374151;
  --sidebar-text-active: #7C3AED;
  --sidebar-hover-bg: #F5F3FF;
  --sidebar-section-label: #9CA3AF;
  --sidebar-border: #E5E7EB;

  /* Pipeline cards */
  --card-bg: #FFFFFF;
  --card-border: #E5E7EB;
  --card-hover-bg: #F9FAFB;

  /* Status badges (consistent across themes) */
  --badge-success-bg: #D1FAE5;
  --badge-success-text: #065F46;
  --badge-warning-bg: #FEF3C7;
  --badge-warning-text: #92400E;
  --badge-danger-bg: #FEE2E2;
  --badge-danger-text: #991B1B;
  --badge-info-bg: #EDE9FE;
  --badge-info-text: #5B21B6;

  /* Buttons */
  --btn-primary-bg: #7C3AED;
  --btn-primary-text: #FFFFFF;
  --btn-primary-hover: #6D28D9;
  --btn-secondary-bg: transparent;
  --btn-secondary-text: #374151;
  --btn-secondary-border: #D1D5DB;
  --btn-secondary-hover-bg: #F3F4F6;
  --btn-danger-bg: #EF4444;
  --btn-danger-text: #FFFFFF;

  /* FAB */
  --fab-bg: #F59E0B;
  --fab-text: #FFFFFF;
  --fab-hover: #D97706;

  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
}

[data-theme="dark"] {
  /* Backgrounds — purple-tinted darks */
  --bg-primary: #0F0D1A;
  --bg-secondary: #1A1730;
  --bg-surface: #1E1B3A;
  --bg-surface-hover: #2D2A4A;
  --bg-sidebar: #13102A;
  --bg-input: #1E1B3A;
  --bg-modal: #1E1B3A;

  /* Text */
  --text-primary: #F3F4F6;
  --text-secondary: #9CA3AF;
  --text-muted: #6B7280;
  --text-inverse: #111827;

  /* Borders */
  --border-primary: #2D2A4A;
  --border-secondary: #3D3A5A;
  --border-focus: #8B5CF6;

  /* Brand */
  --brand-purple: #8B5CF6;
  --brand-purple-hover: #A78BFA;
  --brand-purple-light: #2D2A4A;
  --brand-purple-text: #A78BFA;
  --brand-teal: #2DD4BF;
  --brand-teal-hover: #5EEAD4;
  --brand-teal-light: #1A3A35;
  --brand-teal-text: #2DD4BF;

  /* Sidebar */
  --sidebar-bg: #13102A;
  --sidebar-text: #D1D5DB;
  --sidebar-text-active: #A78BFA;
  --sidebar-hover-bg: #1E1B3A;
  --sidebar-section-label: #6B7280;
  --sidebar-border: #2D2A4A;

  /* Pipeline cards */
  --card-bg: #1E1B3A;
  --card-border: #2D2A4A;
  --card-hover-bg: #2D2A4A;

  /* Status badges — darkened versions */
  --badge-success-bg: #064E3B;
  --badge-success-text: #6EE7B7;
  --badge-warning-bg: #78350F;
  --badge-warning-text: #FCD34D;
  --badge-danger-bg: #7F1D1D;
  --badge-danger-text: #FCA5A5;
  --badge-info-bg: #3B1D8F;
  --badge-info-text: #C4B5FD;

  /* Buttons */
  --btn-primary-bg: #7C3AED;
  --btn-primary-text: #FFFFFF;
  --btn-primary-hover: #8B5CF6;
  --btn-secondary-bg: transparent;
  --btn-secondary-text: #D1D5DB;
  --btn-secondary-border: #3D3A5A;
  --btn-secondary-hover-bg: #2D2A4A;
  --btn-danger-bg: #DC2626;
  --btn-danger-text: #FFFFFF;

  /* FAB */
  --fab-bg: #F59E0B;
  --fab-text: #FFFFFF;
  --fab-hover: #D97706;

  /* Shadows — stronger for dark bg */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.4);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.5);
}
```

### What this means for existing components

Every component that currently uses hardcoded colors (hex values, rgba, Tailwind color classes in inline styles) needs to be migrated to these CSS variables. This is the majority of the work. The approach:

1. Create a `theme.css` file with the variables above
2. Import it at the app root (before component styles)
3. Systematically replace hardcoded colors in every component

**Do NOT attempt to do this with find-and-replace.** Each component needs to be reviewed individually because the same hex value might map to different semantic tokens depending on context (e.g., `#1E293B` might be a background in one place and a text color in another).

---

## Theme Toggle

### Backend

Add `theme_preference` field to the `users` table:

```sql
ALTER TABLE users ADD COLUMN theme_preference VARCHAR(10) DEFAULT 'dark';
```

New or modified endpoints:
- `PUT /api/users/me/preferences` — accepts `{ theme_preference: "light" | "dark" }` 
- `GET /api/auth/me` — already returns user info, include `theme_preference` in the response

### Frontend

- On app load, read `theme_preference` from the auth response and set `document.documentElement.setAttribute('data-theme', preference)`
- Store in React context or a lightweight state so the toggle is reactive
- Toggle UI: a simple switch in the Settings page, or a sun/moon icon in the top nav bar (or both)
- On toggle: PATCH the preference to the backend, update the `data-theme` attribute immediately (don't wait for the server response — optimistic update)
- Before auth loads (flash prevention): check `localStorage` for a cached theme preference and apply it immediately in a `<script>` tag in `index.html` before React mounts. This prevents the white flash on dark theme or dark flash on light theme.

### Settings page location

The CRM already has a Settings section in the sidebar (Pipeline Settings). Add a "Display" or "Appearance" subsection with:
- Theme toggle: Light / Dark (radio buttons or a toggle switch with sun/moon icons)
- That's it for now. Future settings like language, date format, etc. can go here later.

---

## Component Migration Checklist

These are the components/pages that need color migration. Claude Code should go through each one and replace hardcoded colors with the appropriate CSS variable.

### Layout
- [ ] Sidebar/Navigation — background, text, active state, section labels, hover
- [ ] Top bar (if exists) — background, text, icons
- [ ] Main content area — page background
- [ ] Modal overlays — background, backdrop

### Pipeline/Board
- [ ] Pipeline board page — background, column headers, column backgrounds
- [ ] Pipeline cards — background, border, text, hover state
- [ ] Pipeline stage badges — colors (these may stay hardcoded per-stage since users customize them)
- [ ] Drag-and-drop placeholder

### Client Profile
- [ ] Header area — background, text, badges
- [ ] Summary cards — background, border, values, labels
- [ ] Tab bar — active/inactive states, border
- [ ] Info form — input backgrounds, borders, labels

### Estimates
- [ ] Estimate list — row backgrounds, borders, status badges
- [ ] Estimate detail — header, line items table, section headers
- [ ] Line item rows — background, borders, hover
- [ ] Action buttons — already covered by btn variables
- [ ] Job Info panel — background, borders (only visible when approved)
- [ ] Estimate notes — three-tier column headers

### Invoices / Payments
- [ ] Invoice list — row backgrounds
- [ ] Invoice detail — header, line items
- [ ] Payment tracking — status badges

### Calendar
- [ ] Calendar grid — backgrounds, borders, today highlight
- [ ] Event blocks — these use crew colors, which should stay as-is
- [ ] Week/month toggle

### Dashboard
- [ ] Stat cards — backgrounds, borders, values
- [ ] Task rows — backgrounds, overdue highlighting
- [ ] Open invoices table — backgrounds, borders
- [ ] Recent jobs section

### Forms & Inputs (global)
- [ ] Text inputs — background, border, focus ring, text
- [ ] Select dropdowns — background, border, options
- [ ] Textareas — same as text inputs
- [ ] Checkboxes/toggles
- [ ] Date pickers

### Misc
- [ ] Toast notifications — backgrounds, text
- [ ] Confirmation modals — backgrounds, buttons
- [ ] Empty states — text, icons
- [ ] Loading spinners/skeletons
- [ ] Tooltips/popovers
- [ ] FAB — already has variables but verify

---

## Customer-Facing Pages — NO THEME CHANGE

The customer portal (estimate view, change order view, invoice view) should NOT be affected by the theme toggle. These pages have their own styling that matches the branded PDF output. They should remain as-is with their current white/clean styling regardless of what theme the internal user has selected.

**Verify this is the case after the migration.** If the portal pages share any CSS with the internal app, they need to be isolated.

---

## PDF Output — NO CHANGE

PDF generation (WeasyPrint + Jinja2) uses its own inline styles in the template. It does not reference the app's CSS. No changes needed, but verify the output hasn't changed after the migration.

---

## Anti-Patterns

- **Do NOT use Tailwind's `dark:` prefix.** The theming is CSS variable-based with a `data-theme` attribute. Mixing approaches creates maintenance problems.
- **Do NOT change pipeline stage colors.** Users customize these. They should render the same in both themes. If a stage color has poor contrast against the new theme backgrounds, that's a user-configuration issue, not a theming bug.
- **Do NOT change crew colors.** Same reasoning.
- **Do NOT theme the customer portal.** See above.
- **Do NOT create a "system" theme option** (follow OS preference). Just light and dark. Keep it simple.
- **Do NOT restructure component files** during this sprint. The goal is color migration, not refactoring. Change colors in place.

---

## Implementation Order

1. **Migration** — add `theme_preference` to users table
2. **CSS variables file** — create `theme.css` with both theme definitions
3. **Theme provider** — React context + localStorage flash prevention + `data-theme` attribute management
4. **Settings UI** — theme toggle on settings page (or top nav icon)
5. **Backend** — preference endpoint + include in auth response
6. **Component migration** — go through the checklist above, component by component
7. **Verification** — toggle between themes, check every page, verify customer portal and PDF are unaffected

---

## Verification Checklist

- [ ] Light theme renders correctly on all internal pages
- [ ] Dark theme renders correctly on all internal pages
- [ ] No hardcoded colors remain in component files (grep for hex values)
- [ ] Theme preference persists across sessions (saved to DB)
- [ ] Theme applies immediately on toggle (no page reload)
- [ ] No white/dark flash on initial page load
- [ ] Customer portal pages are NOT affected by theme
- [ ] PDF output is NOT affected by theme
- [ ] Pipeline stage colors render correctly in both themes
- [ ] Crew colors on calendar render correctly in both themes
- [ ] Status badges are readable in both themes
- [ ] Form inputs are clearly visible in both themes (borders, focus states)
- [ ] FAB is visible in both themes
- [ ] Toast notifications are readable in both themes
- [ ] All 445+ existing tests still pass
- [ ] Mobile viewport looks correct in both themes

---

## Context Line for Claude Code Session

```
Read CLAUDE.md and PRD.md. Data model restructure complete (Sub-sprints A–E). 445 tests passing. Latest migration: 0021. Sprint 15: Light/dark theming. The full spec is at docs/superpowers/specs/legacy_crm_sprint15_spec.md — read it before starting. Current theme is dark navy/slate. Adding: CSS variable theming system, light theme (white + purple/teal accents), dark theme (purple-tinted dark + teal accents), user preference toggle saved to DB. Customer portal and PDF output must NOT be affected.
```
