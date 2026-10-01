"""HTML email renderer for the Legacy Roofing daily briefing.

Ported from docs/reference/hyperagent/render_email.py with minor adaptations:
- Weather card returns empty when weather is None (v1 skips weather)
- Footer 'Open in CRM' link reads PORTAL_BASE_URL from env
- render_subject guards against weather being None

Hybrid layout: branded header + casual scannable body cards. Inline styles
throughout for email-client compatibility (Gmail, Outlook, Apple Mail).
"""
import os
from datetime import date, datetime
from typing import Dict, List, Optional

# Brand
NAVY      = "#1a2332"
RED       = "#c8423d"
AMBER     = "#d18a3a"
GREEN     = "#3d7d52"
BG        = "#fafaf7"
CARD      = "#ffffff"
TEXT      = "#2a2f36"
MUTED     = "#6a737d"
BORDER    = "#e6e3da"
SUBTLE_BG = "#f4f1ea"


# ---------- formatters ----------

def _money(amount):
    if amount is None:
        return ""
    return f"${amount:,.0f}"


def _money_short(amount):
    if amount is None:
        return ""
    if amount >= 1000:
        return f"${amount/1000:.1f}k".replace(".0k", "k")
    return f"${amount:,.0f}"


def _date_human(iso_str):
    d = date.fromisoformat(iso_str[:10])
    return d.strftime("%A, %B %-d")


def _time_ago(iso_dt):
    if iso_dt is None:
        return ""
    dt = datetime.fromisoformat(iso_dt)
    return dt.strftime("%-I:%M %p")


def _pill(label, color, light=False):
    bg, fg = (f"{color}1a", color) if light else (color, "#ffffff")
    return (f'<span style="display:inline-block;background:{bg};color:{fg};'
            f'font-size:11px;font-weight:700;letter-spacing:0.06em;'
            f'padding:2px 8px;border-radius:999px;text-transform:uppercase;'
            f'vertical-align:middle;">{label}</span>')


def _red_pill(label):   return _pill(label, RED)
def _amber_pill(label): return _pill(label, AMBER)
def _green_pill(label): return _pill(label, GREEN)
def _muted_pill(label): return _pill(label, MUTED, light=True)


# ---------- building blocks ----------

def _section(eyebrow: str, body: str, count: int = None) -> str:
    count_html = ""
    if count is not None:
        count_html = (f'<span style="color:{MUTED};font-weight:500;'
                      f'margin-left:8px;letter-spacing:0;">· {count}</span>')
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:0 0 14px 0;">
  <tr><td style="background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:20px 22px;">
    <div style="font-size:11px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:{RED};margin:0 0 14px 0;">{eyebrow}{count_html}</div>
    {body}
  </td></tr>
</table>
"""


def _row(left_html: str, right_html: str = "") -> str:
    if right_html:
        return f"""
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:0 0 10px 0;border-collapse:collapse;">
  <tr>
    <td style="font-size:14px;color:{TEXT};line-height:1.5;vertical-align:top;">{left_html}</td>
    <td style="font-size:13px;color:{MUTED};text-align:right;white-space:nowrap;padding-left:16px;vertical-align:top;">{right_html}</td>
  </tr>
</table>
"""
    return f'<div style="font-size:14px;color:{TEXT};line-height:1.5;margin:0 0 10px 0;">{left_html}</div>'


def _empty(text: str) -> str:
    return (f'<div style="font-size:13px;color:{MUTED};font-style:italic;'
            f'padding:4px 0;">{text}</div>')


def _name(s: str) -> str:
    return f'<strong style="color:{NAVY};">{s}</strong>'


def _muted(s: str) -> str:
    return f'<span style="color:{MUTED};">{s}</span>'


def _spacer(h=8):
    return f'<div style="height:{h}px;line-height:{h}px;font-size:0;">&nbsp;</div>'


# ---------- shared cards ----------

def _weather_strip(w: Optional[Dict]) -> str:
    """Render the Kokomo weather + 3-day forecast card.

    Returns empty string if weather is None (v1 ships without weather).
    """
    if not w:
        return ""
    today = w.get("today", {})
    forecast = w.get("forecast", [])
    has_severe = w.get("has_severe_alert")

    alert_html = ""
    if has_severe:
        alerts = w.get("alerts", [])
        a = alerts[0] if alerts else {}
        alert_html = f"""
<div style="background:{RED};color:#fff;border-radius:6px;padding:14px 16px;margin:0 0 12px 0;">
  <div style="font-size:12px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;margin:0 0 6px 0;">⚠ Severe weather alert</div>
  <div style="font-size:15px;font-weight:600;line-height:1.3;margin:0 0 4px 0;">{a.get('headline','Severe Weather Warning')}</div>
  <div style="font-size:13px;line-height:1.45;opacity:0.92;">{a.get('details','')}</div>
</div>
"""

    fc_cells = ""
    for f in forecast:
        fc_cells += f"""
<td style="text-align:center;padding:0 6px;">
  <div style="font-size:11px;color:{MUTED};text-transform:uppercase;letter-spacing:0.08em;font-weight:700;margin-bottom:3px;">{f.get('label','')}</div>
  <div style="font-size:13px;color:{TEXT};font-weight:600;">{f.get('high_f','-')}° / {f.get('low_f','-')}°</div>
  <div style="font-size:11px;color:{MUTED};margin-top:2px;">{f.get('condition','')}</div>
  <div style="font-size:11px;color:{MUTED};">{f.get('precip_chance',0)}% rain</div>
</td>
"""

    today_line = (f"<strong style='color:{NAVY};font-size:18px;'>{today.get('temp_f','-')}°F</strong>"
                  f" · {today.get('condition','—')} · {today.get('precip_chance',0)}% rain · "
                  f"wind {today.get('wind_mph','-')} mph {today.get('wind_dir','')}")

    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:0 0 14px 0;">
  <tr><td style="background:{CARD};border:1px solid {BORDER};border-radius:8px;padding:18px 22px;">
    {alert_html}
    <div style="font-size:11px;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;color:{RED};margin:0 0 8px 0;">Kokomo · today & 3-day</div>
    <div style="font-size:14px;color:{TEXT};margin:0 0 14px 0;line-height:1.5;">{today_line}</div>
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="border-top:1px solid {BORDER};padding-top:12px;">
      <tr>{fc_cells}</tr>
    </table>
  </td></tr>
</table>
"""


def _ai_recap_card(recap: Dict) -> str:
    items = recap.get("items", [])
    if not items:
        body = _empty("No overnight AI activity.")
        return _section("Overnight AI", body)
    rows = []
    for it in items:
        type_label = it["action_type"].replace("_", " ").title()
        rows.append(_row(
            f"{_muted_pill(type_label)} &nbsp; {it.get('summary','')}",
            _time_ago(it.get('created_at'))
        ))
    return _section("Overnight AI", "\n".join(rows), count=recap["total"])


# ---------- Dale cards ----------

def _signals_card(signals: List, yesterday_iso: str) -> str:
    if not signals:
        return _section("Yesterday's signals", _empty(f"No customer activity on {_date_human(yesterday_iso)}."))
    type_pill_map = {
        "estimate_signed":  _green_pill("Signed"),
        "payment_received": _green_pill("Paid"),
        "estimate_viewed":  _amber_pill("Viewed"),
        "portal_view":      _muted_pill("Portal"),
    }
    rows = []
    for s in signals:
        pill = type_pill_map.get(s.get("type"), _muted_pill(s.get("type","—")))
        amount_html = _money(s.get("amount")) if s.get("amount") else ""
        rows.append(_row(
            f"{pill} &nbsp; {s.get('summary','')}",
            amount_html,
        ))
    return _section("Yesterday's signals", "\n".join(rows), count=len(signals))


def _new_leads_card(leads: List) -> str:
    if not leads:
        return _section("New leads (yesterday)", _empty("No new leads yesterday."))
    rows = []
    for l in leads:
        flag = _red_pill("No follow-up") if l.get("needs_follow_up") else _green_pill("Touched")
        meta = f'{l.get("source","—")} · {l.get("phone","")}'
        body = (f'{flag} &nbsp; {_name(l.get("name","—"))}<br>'
                f'<span style="font-size:13px;color:{MUTED};">{l.get("lead_note","")} '
                f'<span style="color:{BORDER};">|</span> {meta}</span>')
        rows.append(_row(body))
    return _section("New leads (yesterday)", "\n".join(rows), count=len(leads))


def _pipeline_card(pipeline: Dict) -> str:
    aging = pipeline.get("aging", [])
    warm  = pipeline.get("warm", [])
    cold  = pipeline.get("sent_not_viewed", [])
    total = len(aging) + len(warm) + len(cold)

    if total == 0:
        return _section("Estimate pipeline", _empty("No open estimates in pipeline."))

    def _bucket(label, color, items, render_meta):
        if not items:
            return ""
        rows = []
        for e in items:
            meta = render_meta(e)
            body = (f'{_name(e.get("contact_name","—"))} '
                    f'<span style="color:{MUTED};">· {e.get("id","")} · {e.get("scope","")}</span>'
                    f'<br><span style="font-size:13px;color:{MUTED};">{meta}</span>')
            rows.append(_row(body, f"<strong style='color:{NAVY};'>{_money(e.get('amount'))}</strong>"))
        header = (f'<div style="font-size:12px;font-weight:700;color:{color};'
                  f'margin:8px 0 8px 0;letter-spacing:0.05em;">{label}</div>')
        return header + "\n".join(rows)

    aging_html = _bucket("Aging — > 5 days", RED, aging,
                         lambda e: f"sent {e['age_days']}d ago "
                                   f"{'· not yet viewed' if e['status']=='sent' else '· viewed but not signed'}")
    warm_html = _bucket("Warm — viewed, not signed", AMBER, warm,
                        lambda e: f"sent {e['age_days']}d ago · viewed")
    cold_html = _bucket("Sent — not yet viewed", MUTED, cold,
                        lambda e: f"sent {e['age_days']}d ago")

    body = "\n".join(filter(None, [aging_html, warm_html, cold_html]))
    return _section("Estimate pipeline", body, count=total)


def _lead_sources_card(summary: Dict) -> str:
    """Sprint 18a — Lead source breakdown for the last 7 days.

    Shows source distribution of new leads plus the all-time top closer.
    If no new leads in the period, still renders an empty-state row so the
    section never silently disappears.
    """
    if not summary:
        return _section(
            "Lead sources — last 7 days",
            _empty("No new leads this week."),
        )
    breakdown = summary.get("breakdown_last_7_days") or []
    new_total = summary.get("new_leads_last_7_days") or 0

    if new_total == 0 or not breakdown:
        body = _empty("No new leads this week.")
    else:
        rows = []
        for item in breakdown:
            src = item.get("source", "—")
            cnt = item.get("count", 0)
            pct = round((cnt / new_total) * 100) if new_total else 0
            left = (
                f'{_name(src)} '
                f'<span style="color:{MUTED};">· {pct}%</span>'
            )
            right = f"<strong style='color:{NAVY};'>{cnt}</strong>"
            rows.append(_row(left, right))
        body = "\n".join(rows)

    # Top closer / lowest performer footer (all-time).
    top = summary.get("top_closer_all_time")
    low = summary.get("lowest_performer_all_time")
    footer_bits = []
    if top:
        footer_bits.append(
            f'<span style="color:{GREEN};font-weight:600;">Top closer:</span> '
            f'{_name(top["source"])} '
            f'<span style="color:{MUTED};">— '
            f'{top["close_rate"]}% close rate '
            f'({top["approved_count"]} of {top["lead_count"]})</span>'
        )
    if low:
        footer_bits.append(
            f'<span style="color:{RED};font-weight:600;">Lowest:</span> '
            f'{_name(low["source"])} '
            f'<span style="color:{MUTED};">— '
            f'{low["close_rate"]}% '
            f'({low["approved_count"]} of {low["lead_count"]})</span>'
        )
    if footer_bits:
        footer = (
            '<div style="margin-top:8px;padding-top:8px;'
            f'border-top:1px solid {BORDER};font-size:13px;">'
            + "<br>".join(footer_bits)
            + "</div>"
        )
        body = body + footer

    return _section("Lead sources — last 7 days", body, count=new_total)


def _cash_card(cash: Dict) -> str:
    overdue = cash.get("overdue", [])
    unpaid  = cash.get("unpaid", [])
    total = len(overdue) + len(unpaid)
    if total == 0:
        return _section("Cash watch", _empty("All invoices paid. Nice."))

    def _row_inv(inv, is_overdue):
        flag = _red_pill(f"{inv['days_overdue']}d overdue") if is_overdue else _muted_pill("Open")
        meta = f"{inv.get('id','')} · {inv.get('memo','')} · due {inv.get('due_date','')[:10]}"
        body = (f'{flag} &nbsp; {_name(inv.get("contact_name","—"))} '
                f'<br><span style="font-size:13px;color:{MUTED};">{meta}</span>')
        return _row(body, f"<strong style='color:{NAVY};'>{_money(inv.get('amount'))}</strong>")

    rows = [_row_inv(i, True) for i in overdue] + [_row_inv(i, False) for i in unpaid]
    return _section("Cash watch", "\n".join(rows), count=total)


def _cold_leads_card(cold: List) -> str:
    if not cold:
        return _section("Cold-lead reactivation", _empty("No cold leads — pipeline is warm."))
    rows = []
    for c in cold:
        flag = _muted_pill(f"{c['days_since_touch']}d cold")
        meta = f"{c.get('source','—')} · {c.get('phone','')}"
        body = (f'{flag} &nbsp; {_name(c.get("name","—"))} '
                f'<br><span style="font-size:13px;color:{MUTED};">{c.get("lead_note","")} '
                f'<span style="color:{BORDER};">|</span> {meta}</span>')
        rows.append(_row(body))
    return _section("Cold-lead reactivation watchlist", "\n".join(rows), count=len(cold))


# ---------- Marcus cards ----------

def _jobs_today_card(jobs: List) -> str:
    if not jobs:
        return _section("Today's jobs", _empty("No jobs on the calendar today."))
    rows = []
    for j in jobs:
        if j.get("needs_crew"):
            flag = _red_pill("No crew assigned")
            crew_meta = "Crew assignment needed"
        else:
            flag = _green_pill(j.get("crew_name","Crew"))
            crew_meta = f"Lead: {j.get('crew_lead','—')}"
        body = (f'{flag} &nbsp; <strong style="color:{NAVY};">{j.get("start_time","—")}</strong> · '
                f'{j.get("title","—")}'
                f'<br><span style="font-size:13px;color:{MUTED};">{j.get("address","")} · {crew_meta}</span>')
        rows.append(_row(body))
    return _section("Today's jobs", "\n".join(rows), count=len(jobs))


def _jobs_no_crew_card(jobs: List) -> str:
    if not jobs:
        return _section("Jobs missing crew (this week)",
                        _empty("All scheduled jobs have crews. 👍"))
    rows = []
    for j in jobs:
        body = (f'{_red_pill("No crew")} &nbsp; <strong style="color:{NAVY};">{j.get("day_label","—")}</strong> '
                f'<span style="color:{MUTED};">· {j.get("start_time","")}</span> · {j.get("title","—")}'
                f'<br><span style="font-size:13px;color:{MUTED};">{j.get("address","")}</span>')
        rows.append(_row(body))
    return _section("Jobs missing crew (this week)", "\n".join(rows), count=len(jobs))


def _marcus_tasks_card(tasks: Dict) -> str:
    overdue = tasks.get("overdue", [])
    today_t = tasks.get("due_today", [])
    if not overdue and not today_t:
        return _section("Tasks today", _empty("Inbox zero. 🎯"))

    def _row_t(t, is_overdue):
        flag = _red_pill(f"{t['days_overdue']}d overdue") if is_overdue else _amber_pill("Due today")
        body = (f'{flag} &nbsp; {t.get("title","")}'
                f'<br><span style="font-size:13px;color:{MUTED};">{t.get("contact_name","")}</span>')
        return _row(body)

    rows = [_row_t(t, True) for t in overdue] + [_row_t(t, False) for t in today_t]
    return _section("Tasks today", "\n".join(rows), count=len(overdue)+len(today_t))


def _marcus_new_leads_card(leads: List) -> str:
    if not leads:
        return _section("Leads to route", _empty("No new leads to route."))
    rows = []
    for l in leads:
        meta = f"{l.get('source','—')} · {l.get('phone','')}"
        body = (f'{_muted_pill("Lead")} &nbsp; {_name(l.get("name","—"))}'
                f'<br><span style="font-size:13px;color:{MUTED};">{l.get("lead_note","")} '
                f'<span style="color:{BORDER};">|</span> {meta}</span>')
        rows.append(_row(body))
    return _section("Leads to route", "\n".join(rows), count=len(leads))


def _marcus_signed_card(signed: List) -> str:
    if not signed:
        return _section("Signed yesterday → ready to schedule",
                        _empty("No new signed estimates yesterday."))
    rows = []
    for e in signed:
        body = (f'{_green_pill("Schedule it")} &nbsp; {_name(e.get("contact_name","—"))} '
                f'<span style="color:{MUTED};">· {e.get("scope","")}</span>'
                f'<br><span style="font-size:13px;color:{MUTED};">{e.get("address","")}</span>')
        rows.append(_row(body, f"<strong style='color:{NAVY};'>{_money(e.get('amount'))}</strong>"))
    return _section("Signed yesterday → ready to schedule", "\n".join(rows), count=len(signed))


# ---------- summary strip ----------

def _summary_strip(stats: List[tuple]) -> str:
    cells = ""
    for label, value, color in stats:
        cells += f"""
<td style="text-align:center;padding:10px 8px;">
  <div style="font-size:22px;font-weight:700;color:{color};line-height:1;">{value}</div>
  <div style="font-size:10px;color:{MUTED};text-transform:uppercase;letter-spacing:0.1em;font-weight:700;margin-top:6px;">{label}</div>
</td>
"""
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:0 0 14px 0;">
  <tr><td style="background:{SUBTLE_BG};border:1px solid {BORDER};border-radius:8px;padding:8px 6px;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%"><tr>{cells}</tr></table>
  </td></tr>
</table>
"""


# ---------- header / wrapper ----------

def _header(date_iso: str, recipient: str, role: str) -> str:
    date_label = _date_human(date_iso)
    greeting = f"Morning {recipient}"
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:0 0 14px 0;">
  <tr><td style="background:{NAVY};border-radius:8px 8px 0 0;padding:24px 24px 18px 24px;border-bottom:3px solid {RED};">
    <div style="font-family:'Helvetica Neue',Arial,sans-serif;font-size:11px;letter-spacing:0.22em;color:{RED};text-transform:uppercase;font-weight:700;">Legacy Roofing &amp; Exteriors</div>
    <div style="font-family:Georgia,'Times New Roman',serif;font-size:24px;color:#fff;font-weight:600;margin-top:8px;line-height:1.15;">Daily Briefing — {date_label}</div>
    <div style="font-size:13px;color:#b8c2d1;margin-top:6px;">{greeting} · {role}</div>
  </td></tr>
</table>
"""


def _footer(date_iso: str) -> str:
    portal_url = os.environ.get("PORTAL_BASE_URL", "#")
    return f"""
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="margin:14px 0 0 0;">
  <tr><td style="padding:18px 24px;text-align:center;color:{MUTED};font-size:12px;line-height:1.55;">
    Sent at 7:00 AM ET · {_date_human(date_iso)} · Kokomo, IN<br>
    <a href="{portal_url}" style="color:{RED};text-decoration:none;font-weight:600;">Open Legacy CRM →</a>
  </td></tr>
</table>
"""


def _wrap_email(body_html: str, recipient: str, role: str, date_iso: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Legacy Roofing — Daily Briefing</title>
</head>
<body style="margin:0;padding:0;background:{BG};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:{TEXT};-webkit-font-smoothing:antialiased;">
<table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:{BG};">
  <tr><td align="center" style="padding:24px 12px;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="640" style="max-width:640px;width:100%;">
      <tr><td>
        {_header(date_iso, recipient, role)}
        {body_html}
        {_footer(date_iso)}
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>
"""


# ---------- Sprint 19d — automations card ----------

def _automations_card(automations: Dict) -> str:
    """Render the morning briefing's Automations section.

    Returns an empty string when nothing automation-related happened so the
    section disappears on quiet days.
    """
    active = int(automations.get("active_enrollments") or 0)
    sent = int(automations.get("messages_sent_yesterday") or 0)
    pending = int(automations.get("messages_pending_today") or 0)
    replies = int(automations.get("reply_stops_yesterday") or 0)
    paused = list(automations.get("paused_sequences") or [])

    if active == 0 and sent == 0 and pending == 0 and not paused:
        return ""

    rows = []
    rows.append(_row(
        f"<strong>{active}</strong> contact{'s' if active != 1 else ''} in active sequences"
    ))
    rows.append(_row(
        f"<strong>{sent}</strong> message{'s' if sent != 1 else ''} sent yesterday"
    ))
    rows.append(_row(
        f"<strong>{pending}</strong> message{'s' if pending != 1 else ''} scheduled today"
    ))
    if replies > 0:
        rows.append(_row(
            f'<span style="color:{GREEN};">'
            f"<strong>{replies}</strong> contact{'s' if replies != 1 else ''} "
            f"replied (sequence{'s' if replies != 1 else ''} stopped)</span>"
        ))
    if paused:
        rows.append(_row(
            f'<span style="color:{MUTED};">'
            f"{len(paused)} sequence{'s' if len(paused) != 1 else ''} paused: "
            f"{', '.join(paused[:3])}{'…' if len(paused) > 3 else ''}</span>"
        ))

    return _section("Automations", "".join(rows), count=active)


# ---------- public entrypoints ----------

def render_dale_email(view: Dict) -> str:
    pipeline = view["estimate_pipeline"]
    cash = view["cash_watch"]
    summary_stats = [
        ("Yesterday signals", len(view["yesterday_signals"]), NAVY),
        ("New leads", len(view["new_leads"]), NAVY),
        ("Aging estimates", len(pipeline["aging"]), RED if pipeline["aging"] else NAVY),
        ("Overdue $", _money_short(sum(i["amount"] for i in cash["overdue"])) or "$0",
         RED if cash["overdue"] else NAVY),
        ("Cold leads", len(view["cold_leads"]), NAVY),
    ]
    body = "\n".join([
        _weather_strip(view["weather"]),
        _summary_strip(summary_stats),
        _ai_recap_card(view["ai_recap"]),
        _signals_card(view["yesterday_signals"], view["yesterday"]),
        _new_leads_card(view["new_leads"]),
        _pipeline_card(view["estimate_pipeline"]),
        _lead_sources_card(view.get("lead_sources") or {}),
        _automations_card(view.get("automations") or {}),
        _cash_card(view["cash_watch"]),
        _cold_leads_card(view["cold_leads"]),
    ])
    return _wrap_email(body, "Dale", view["role"], view["briefing_date"])


def render_marcus_email(view: Dict) -> str:
    today_jobs = view["jobs_today"]
    no_crew = view["jobs_no_crew"]
    tasks = view["tasks"]
    needs_crew_today = sum(1 for j in today_jobs if j.get("needs_crew"))
    summary_stats = [
        ("Jobs today", len(today_jobs), NAVY),
        ("Missing crew", len(no_crew) + needs_crew_today,
         RED if (len(no_crew) + needs_crew_today) else NAVY),
        ("Overdue tasks", len(tasks["overdue"]),
         RED if tasks["overdue"] else NAVY),
        ("New leads", len(view["new_leads"]), NAVY),
        ("Signed yesterday", len(view["signed_yesterday"]), GREEN if view["signed_yesterday"] else NAVY),
    ]
    body = "\n".join([
        _weather_strip(view["weather"]),
        _summary_strip(summary_stats),
        _ai_recap_card(view["ai_recap"]),
        _jobs_today_card(view["jobs_today"]),
        _jobs_no_crew_card(view["jobs_no_crew"]),
        _marcus_tasks_card(view["tasks"]),
        _marcus_new_leads_card(view["new_leads"]),
        _marcus_signed_card(view["signed_yesterday"]),
        _automations_card(view.get("automations") or {}),
    ])
    return _wrap_email(body, "Marcus", view["role"], view["briefing_date"])


def render_email(view: Dict) -> str:
    if view["recipient"] == "Dale":
        return render_dale_email(view)
    if view["recipient"] == "Marcus":
        return render_marcus_email(view)
    raise ValueError(f"Unknown recipient: {view['recipient']}")


# ---------- subject line ----------

def render_subject(view: Dict) -> str:
    d = date.fromisoformat(view["briefing_date"]).strftime("%a %b %-d")
    parts = [f"Legacy briefing · {d}"]
    if view["recipient"] == "Dale":
        n_overdue = len(view["cash_watch"]["overdue"])
        n_signed = sum(1 for s in view["yesterday_signals"] if s.get("type") == "estimate_signed")
        n_aging = len(view["estimate_pipeline"]["aging"])
        bits = []
        if n_overdue: bits.append(f"{n_overdue} overdue")
        if n_signed:  bits.append(f"{n_signed} signed yesterday")
        if n_aging:   bits.append(f"{n_aging} aging est")
        if bits: parts.append(" · ".join(bits))
    else:
        n_no_crew = len(view["jobs_no_crew"]) + sum(1 for j in view["jobs_today"] if j.get("needs_crew"))
        n_overdue_tasks = len(view["tasks"]["overdue"])
        bits = []
        if n_no_crew:       bits.append(f"{n_no_crew} jobs need crew")
        if n_overdue_tasks: bits.append(f"{n_overdue_tasks} task overdue")
        if view["signed_yesterday"]:
            bits.append(f"{len(view['signed_yesterday'])} signed → schedule")
        if bits: parts.append(" · ".join(bits))
    weather = view.get("weather") or {}
    if weather.get("has_severe_alert"):
        parts.insert(0, "⚠ SEVERE WX")
    return " — ".join(parts)
