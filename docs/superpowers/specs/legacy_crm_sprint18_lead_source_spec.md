# Sprint 18 — Lead Source Tracking + Attribution Reporting

## Claude Code Prompt

```
Read CLAUDE.md and PRD.md. Sprints 1–17 are complete. 727 tests passing. Latest migration: 0027. Production deployed to Azure. Deploy via ./scripts/deploy.sh.

Sprint 18: Build lead source attribution reporting — a Lead Sources report page, lead source widgets on the dashboard, morning briefing integration, and AI panel queries. The lead_source field already exists on contacts and is populated from AccuLynx import data (Google LSA 53%, Self Generated 14%, Other 11%, Referral 10%, etc.). This sprint adds the reporting and visualization layer. This is a 2 sub-sprint build.
```

---

## Context

Dale is spending real money on Google LSA. 53% of his leads come from there. But he has no way to answer: "What's my close rate on Google LSA leads?" or "Which lead source produces the highest average job value?" or "Am I wasting money on Facebook ads?"

The data already exists in the CRM — lead_source is populated on contacts, and those contacts flow through estimates, invoices, and payments. Sprint 18 connects the dots with reporting.

### What Already Exists
- `contacts.lead_source` field — populated on 70 contacts from AccuLynx import
- Lead source values in use: Google LSA, Self Generated, Other, Referral, Word of Mouth, Facebook, Yard Sign, Realtor, Property Manager
- Contacts flow through the full lifecycle: contact → estimate → approval → invoice → payment
- Contacts have `pipeline_id` and `stage_id` for funnel position
- Contacts have `created_at` for time-based analysis
- Estimates have `status` (draft, sent, viewed, approved, rejected), `total`, `created_at`, `approved_at`
- Invoices have `total`, `amount_paid`, `balance`, `status`, `created_at`
- Morning briefing data endpoint (`GET /api/ai/briefing`) already assembles cross-entity data
- AI panel with conversational queries already deployed

### What Does NOT Exist Yet
- No reporting page or dashboard widgets for lead source data
- No API endpoint that aggregates lead source metrics
- Briefing doesn't mention lead sources
- AI panel has no lead source context in its prompts

---

## Sub-Sprint 18a: Backend — Attribution API + Briefing Integration

### New Files

**`backend/app/routers/reports.py`** — Reports router:

```python
GET /api/reports/lead-sources
# Auth: JWT required
# Query params:
#   ?period=all|30d|90d|ytd|custom
#   ?start_date=YYYY-MM-DD (for custom period)
#   ?end_date=YYYY-MM-DD (for custom period)
# Returns: LeadSourceReportResponse

# Response shape:
{
    "period": "all",
    "start_date": null,
    "end_date": null,
    "total_leads": 70,
    "total_revenue": 18151.00,
    "sources": [
        {
            "source": "Google LSA",
            "lead_count": 37,
            "lead_percentage": 52.9,
            "estimate_count": 5,
            "approved_count": 1,
            "close_rate": 2.7,               # approved / lead_count * 100
            "total_contract_value": 17276.00,
            "avg_job_value": 17276.00,        # total / approved_count (or 0 if none approved)
            "total_invoiced": 0.00,
            "total_collected": 0.00,
            "avg_days_to_close": null,        # avg(approved_at - created_at) or null
            "pipeline_breakdown": {
                "leads": 6,
                "sales": 29,
                "jobs": 2
            }
        },
        // ... more sources
    ],
    "unattributed": {
        "lead_count": 0,
        "note": "Contacts with no lead_source value"
    }
}

GET /api/reports/lead-sources/summary
# Auth: JWT required
# Lightweight version for dashboard widgets — returns just the top-level numbers
# Returns: { sources: [{source, lead_count, close_rate, avg_job_value}], period: "30d" }
```

**`backend/app/schemas/reports.py`** — Report schemas:
- `LeadSourceMetrics` — per-source metrics
- `LeadSourceReportResponse` — full report with all sources
- `LeadSourceSummaryResponse` — lightweight for dashboard

### Modified Files

**`backend/app/services/briefing_filters.py`** — Add lead source data to Dale's briefing view:
- Add a `lead_source_summary` section to the briefing data
- Query: count of new leads in the last 7 days grouped by lead_source
- Format: "5 new leads this week — 3 from Google LSA, 1 from Angi, 1 referral"
- Also add: "Top performing source (close rate): Referral at 14.3%"

**`backend/app/services/briefing_renderer.py`** — Render the lead source summary section in the briefing email:
- New card in the briefing HTML between the Estimate Pipeline and Cash Watch sections
- Title: "Lead Sources — Last 7 Days"
- Show: source name, count, percentage of total
- If no new leads in 7 days, show "No new leads this week" (don't hide the section)

**`backend/app/services/ai_prompts.py`** — Add lead source context to AI panel system prompts:
- When the AI panel assembles context for global queries, include lead source summary stats
- Enable queries like: "What's my close rate on Google LSA leads?", "Which lead source has the highest average job value?", "How many leads came from Facebook this month?"
- Add a new prompt template or extend the existing global context builder

**`backend/app/main.py`** — Register reports router

### Query Logic

The attribution query joins across multiple tables. Here's the core logic:

```python
# For each distinct lead_source value:

# lead_count: COUNT of contacts WHERE lead_source = X AND created_at within period
# estimate_count: COUNT of estimates WHERE contact.lead_source = X
# approved_count: COUNT of estimates WHERE contact.lead_source = X AND status = 'approved'
# close_rate: approved_count / lead_count * 100
# total_contract_value: SUM of estimate.total WHERE contact.lead_source = X AND status = 'approved'
# avg_job_value: total_contract_value / approved_count
# total_invoiced: SUM of invoice.total WHERE contact.lead_source = X
# total_collected: SUM of payments WHERE invoice.contact.lead_source = X
# avg_days_to_close: AVG of (estimate.approved_at - contact.created_at) in days

# pipeline_breakdown:
#   leads: COUNT of contacts WHERE lead_source = X AND pipeline = leads pipeline
#   sales: COUNT of contacts WHERE lead_source = X AND pipeline = sales pipeline
#   jobs: COUNT of estimates WHERE contact.lead_source = X AND status = 'approved' AND pipeline = jobs
```

**Important:** The join path is contact → estimate (via contact_id) → invoice (via estimate_id) → payment (via invoice_id). All metrics trace back to the contact's lead_source. Contacts without a lead_source value should be grouped as "Unattributed" — don't drop them.

**Period filtering:** Apply the period filter to `contacts.created_at` for lead counts and pipeline metrics. For revenue metrics (invoiced, collected), filter by the relevant date on the financial record (invoice.created_at, payment.date_received) within the same period. This prevents a lead from Q1 with a Q2 invoice from inflating Q1 revenue numbers if the period is set to Q1. For the "all" period, don't filter by date.

### Tests — Sub-Sprint 18a

**`backend/tests/test_reports.py`** — 20+ tests:
- `test_lead_source_report_all` — returns all sources with correct counts
- `test_lead_source_report_30d` — period filter excludes older contacts
- `test_lead_source_report_custom_range` — start_date/end_date work
- `test_lead_source_close_rate` — approved / lead_count calculated correctly
- `test_lead_source_avg_job_value` — total_value / approved_count
- `test_lead_source_no_approved` — close_rate = 0, avg_job_value = 0 for sources with no approvals
- `test_lead_source_unattributed` — contacts without lead_source counted separately
- `test_lead_source_summary_endpoint` — lightweight endpoint returns correct shape
- `test_lead_source_revenue_tracking` — invoiced and collected amounts correct
- `test_lead_source_avg_days_to_close` — date math correct
- `test_lead_source_pipeline_breakdown` — correct counts per pipeline
- `test_lead_source_report_requires_auth` — 401 without JWT
- `test_briefing_includes_lead_sources` — briefing data includes lead_source_summary
- `test_ai_context_includes_lead_sources` — AI prompt context has lead source data

### Anti-Patterns — 18a
- Do NOT create a new migration — lead_source already exists on contacts, no schema changes needed
- Do NOT modify the lead_source values or normalize them — keep the exact values from AccuLynx
- Do NOT add lead_source to estimates or invoices — the attribution traces back through the contact relationship
- Do NOT build the frontend yet — that's 18b

---

## Sub-Sprint 18b: Frontend — Report Page + Dashboard Widgets

### New Files

**`frontend/src/pages/LeadSourceReportPage.jsx`** — Full attribution report page:

**Layout:**
- Page title: "Lead Source Attribution"
- Period selector: All Time | Last 30 Days | Last 90 Days | Year to Date | Custom Range
- Summary cards row (top): Total Leads, Total Revenue, Top Source (by volume), Best Closer (by close rate)
- Main content: two sections side by side (or stacked on mobile)

**Left section — Source breakdown table:**
| Source | Leads | % | Estimates | Approved | Close Rate | Avg Value | Revenue |
|--------|-------|---|-----------|----------|------------|-----------|---------|
| Google LSA | 40 | 52% | 6 | 2 | 5.0% | $11,400 | $22,800 |
| Self Generated | 10 | 14% | 0 | 0 | 0% | — | $0 |
| ... | | | | | | | |

- Sortable by any column (click header to sort)
- Row click → could expand to show individual contacts for that source (stretch goal, not required for v1)

**Right section — Visualizations:**
- Pie/donut chart: lead distribution by source (volume)
- Bar chart: close rate by source
- Bar chart: average job value by source

**Charts:** Use Recharts (already available in the project from Sprint 16c's AI panel). Keep charts simple — the data tells the story, not the visualization complexity.

**Empty state:** If no lead source data exists, show: "No lead source data available. Lead sources are populated when contacts are imported or created with a source."

**`frontend/src/api/reports.js`** — Reports API module:
```javascript
export async function getLeadSourceReport(period = 'all', startDate, endDate) { ... }
export async function getLeadSourceSummary() { ... }
```

### Modified Files

**`frontend/src/App.jsx`** — Add route `/reports/lead-sources`

**`frontend/src/components/Sidebar.jsx`** — Add "Lead Sources" under a REPORTS section in the sidebar (or under an existing section if REPORTS doesn't exist yet). If this is the first report page, create the REPORTS section.

**`frontend/src/pages/DashboardPage.jsx`** — Add a lead source widget:
- Small card or section on the dashboard: "Lead Sources — Last 30 Days"
- Shows top 3 sources by volume with lead counts
- "View Full Report →" link to the report page
- Uses the /api/reports/lead-sources/summary endpoint

### UI Design Notes

**Keep it clean and scannable.** This is a report Dale glances at, not a data analysis tool. The table should tell the story at a glance: Google LSA brings the most leads but has a low close rate. Referrals close at 3x the rate. That insight should jump off the page.

**Color-code close rates:** Red below 5%, yellow 5-15%, green above 15%. This makes the "where should I spend more" decision visual.

**Mobile:** The table should scroll horizontally on mobile. Charts stack vertically. Period selector works as a dropdown on narrow screens.

### Tests — Sub-Sprint 18b

Frontend smoke tests (manual):
1. Lead Source report page loads at /reports/lead-sources
2. Period selector changes data
3. Table shows all sources with correct numbers
4. Charts render (pie chart for volume, bar charts for rates/values)
5. Table columns are sortable
6. Dashboard widget shows top 3 sources
7. "View Full Report" link works from dashboard
8. Mobile layout (375px) — table scrolls, charts stack
9. Empty state displays when no data exists

---

## What Is NOT In Sprint 18

- Lead source dropdown on the contact create/edit form (already exists from data model restructure)
- Lead source field on the new lead form in the pipeline board (if it doesn't already have it — check and add if missing, but don't build a whole UI for it)
- Marketing spend tracking (how much Dale spends per source) — that's a future sprint
- ROI calculation (revenue / spend) — requires spend tracking first
- Automated lead source detection from inbound channels (Google LSA webhook, Facebook lead forms) — future integration sprint
- Per-salesperson attribution (close rate by rep by source) — Sprint 25 territory

---

## Morning Briefing Integration Detail

The briefing email Dale receives should include a new section. Position it after the Estimate Pipeline section and before Cash Watch:

```
📊 LEAD SOURCES — LAST 7 DAYS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

New leads this week: 5
• Google LSA: 3
• Referral: 1  
• Word of Mouth: 1

Top closer (all time): Referral — 14.3% close rate
Lowest performer: Facebook — 0% close rate (2 leads, 0 closed)
```

If there are no new leads in the past 7 days, show:
```
📊 LEAD SOURCES — LAST 7 DAYS
━━━━━━━━━━━━━━━━━━━━━━━━━━━

No new leads this week.
```

This gives Dale a weekly pulse on where his leads are coming from without him needing to open the CRM.

---

## AI Panel Integration Detail

Add lead source context to the AI panel's global context so it can answer questions like:
- "What's my close rate on Google LSA leads?"
- "Which lead source has the highest average job value?"
- "How many leads came in this month?"
- "Should I increase my Google LSA budget?"
- "Compare Google LSA vs referral performance"

This means the `get_briefing_context` function (or the AI chat context builder) needs to include a `lead_source_metrics` section with the same data the report endpoint returns. The AI doesn't need to query the database itself — it reads the pre-assembled context and answers in natural language.

---

## Verification Checklist

### 18a
- [ ] GET /api/reports/lead-sources returns correct data for all periods
- [ ] GET /api/reports/lead-sources/summary returns lightweight version
- [ ] Close rate calculated correctly (approved / leads * 100)
- [ ] Average job value calculated correctly
- [ ] Avg days to close calculated correctly
- [ ] Unattributed contacts (no lead_source) counted separately
- [ ] Period filtering works: all, 30d, 90d, ytd, custom
- [ ] Briefing data includes lead_source_summary section
- [ ] Briefing email renders lead source section
- [ ] AI panel context includes lead source metrics
- [ ] All 20+ new tests passing
- [ ] All 727 existing tests still passing

### 18b
- [ ] Lead Source report page loads at /reports/lead-sources
- [ ] Period selector filters data correctly
- [ ] Table shows all sources with sortable columns
- [ ] Charts render (pie + bar)
- [ ] Close rates color-coded (red/yellow/green)
- [ ] Dashboard widget shows top 3 sources
- [ ] Sidebar has Lead Sources link under REPORTS
- [ ] Mobile layout works (375px)
- [ ] No regressions

---

## Context Line for Claude Code Sessions

### Sub-sprint 18a:
```
Read CLAUDE.md and PRD.md. Sprints 1–17 complete. 727 tests passing. Latest migration: 0027. Sprint 18a: Build lead source attribution API — GET /api/reports/lead-sources (full report with close rates, avg job value, revenue by source, period filtering) and GET /api/reports/lead-sources/summary (dashboard widget). Add lead source section to morning briefing. Add lead source context to AI panel prompts. No migration needed — lead_source already exists on contacts. Read the full Sprint 18 spec at docs/superpowers/specs/legacy_crm_sprint18_lead_source_spec.md.
```

### Sub-sprint 18b:
```
Read CLAUDE.md and PRD.md. Sprint 18a complete. [X] tests passing. Sprint 18b: Build frontend — LeadSourceReportPage with period selector, sortable table, Recharts visualizations (pie + bar charts), color-coded close rates. Add dashboard widget for top 3 sources. Add Lead Sources to sidebar under REPORTS section. Read the full Sprint 18 spec at docs/superpowers/specs/legacy_crm_sprint18_lead_source_spec.md.
```
