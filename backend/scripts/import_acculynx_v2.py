"""AccuLynx data re-import (v2) — replaces the v1 import with fuller data.

Phases:
  0. Cleanup the previous import (by import_id).
  1. Import contacts from Contacts CSV.
  2. Enrich contacts from Jobs CSV (lead source, pipeline placement).
  3. Create Job + Estimate stubs for Approved/Completed/Invoiced/Closed jobs.
  4. Create Invoices + Payments from the Invoice CSV.
  5. Default any remaining unmatched contacts to Leads/Cold Leads.

Usage:
    DATABASE_URL="<prod_url>" python backend/scripts/import_acculynx_v2.py \\
        --previous-import-id 10a4db4aa71a4337b6bc5f232231fc2a \\
        [--dry-run]

Flags:
    --dry-run               Print summary without committing. Rolls back at the end.
    --previous-import-id    UUID of the previous ContactImport to clean up. If
                            omitted, Phase 0 is skipped.
    --contacts PATH         Override default contacts CSV path.
    --jobs PATH             Override default jobs CSV path.
    --invoices PATH         Override default invoices CSV path.
    --ar-age PATH           Override default AR age CSV path.
    --import-user EMAIL     User attributed for the new ContactImport batch.
                            Default: admin@legacy-roofing.example.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

# Path bootstrap: this script runs standalone with DATABASE_URL set, so we
# need backend/ on sys.path before importing app.* modules.
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal  # noqa: E402
from app.models.contact import Contact  # noqa: E402
from app.models.contact_import import ContactImport  # noqa: E402
from app.models.estimate import Estimate  # noqa: E402
from app.models.invoice import Invoice  # noqa: E402
from app.models.job import Job  # noqa: E402
from app.models.payment import Payment  # noqa: E402
from app.models.pipeline import Pipeline  # noqa: E402
from app.models.pipeline_stage import PipelineStage  # noqa: E402
from app.models.user import User  # noqa: E402


DEFAULT_CONTACTS_CSV = os.path.join(
    HERE, "..", "..", "data", "sample", "contacts_report.csv"
)
DEFAULT_JOBS_CSV = os.path.join(
    HERE, "..", "..", "data", "sample", "jobs_report.csv"
)
DEFAULT_INVOICES_CSV = os.path.join(
    HERE, "..", "..", "data", "sample", "invoice_report.csv"
)
DEFAULT_AR_AGE_CSV = os.path.join(
    HERE, "..", "..", "data", "sample", "ar_age_report.csv"
)
DEFAULT_IMPORT_USER_EMAIL = "admin@legacy-roofing.example"


# ---------------------------- parsing helpers ----------------------------


def parse_address(
    raw: Optional[str],
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Parse '214 Larkspur Drive, Kokomo, IN 46901 US' -> (street, city, ST, zip).

    Drops the trailing ' US' marker. Returns (None, None, None, None) for
    empty/None input. For unparseable input, returns the whole string as
    the street with None for the other fields.
    """
    if not raw:
        return None, None, None, None
    s = raw.strip()
    if not s:
        return None, None, None, None
    if s.upper().endswith(" US"):
        s = s[:-3].rstrip()
    elif s.upper().endswith(", US"):
        s = s[:-4].rstrip()

    parts = [p.strip() for p in s.split(",")]
    if len(parts) >= 3:
        street = ", ".join(parts[:-2]) or None
        city = parts[-2] or None
        m = re.match(r"^([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)$", parts[-1])
        if m:
            return street, city, m.group(1).upper(), m.group(2)
        return street, city, None, None
    return s or None, None, None, None


def parse_date(raw: Optional[str]) -> Optional[datetime]:
    """Parse AccuLynx date strings into timezone-aware UTC datetimes.

    Handles 'M/D/YY', 'M/D/YYYY', and either with 'h:MM AM/PM' suffix.
    Returns None for empty/None/unparseable input.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    for fmt in (
        "%m/%d/%y %I:%M %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%y",
        "%m/%d/%Y",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def digits_only(s: Optional[str]) -> str:
    """Strip every non-digit character. '(765) 555-0119' -> '7655550119'."""
    if not s:
        return ""
    return re.sub(r"\D", "", s)


def normalize_name(s: Optional[str]) -> str:
    """Lowercase, strip, and collapse internal whitespace.

    AccuLynx exports occasionally contain double spaces between first and
    last name (e.g., 'Teresa  Murphy') — collapse them so name-matching works.
    """
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def normalize_email(s: Optional[str]) -> str:
    return (s or "").strip().lower()


LEAD_SOURCE_CONSOLIDATION = {
    "Realtor": "Referral",
    "Property Manager": "Referral",
}


def consolidate_lead_source(raw: Optional[str]) -> Optional[str]:
    """Map AccuLynx lead source values onto the CRM's canonical set.

    'Realtor' and 'Property Manager' both consolidate to 'Referral'.
    Empty/None returns None. Unknown values pass through unchanged.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    return LEAD_SOURCE_CONSOLIDATION.get(s, s)


INVOICE_STATUS_MAP = {
    "paid": "paid",
    "unpaid": "sent",
    "draft": "draft",
}


def map_invoice_status(raw: Optional[str]) -> str:
    """Map AccuLynx invoice status to CRM invoice status.

    Unknown/empty inputs default to 'draft' (safest — no payment notion
    attached, won't show in Open Invoices widget).
    """
    if not raw:
        return "draft"
    return INVOICE_STATUS_MAP.get(raw.strip().lower(), "draft")


# Milestone -> (pipeline slug, stage name, creates_estimate?)
# NOTE: 'Estimate Pending Schedule' is a PROD-only stage that Dale added via
# the UI — it is NOT in the seed file. If you're testing locally, seed it
# manually first or the script's stage-lookup will fail loudly.
MILESTONE_MAP: Dict[str, Tuple[str, str, bool]] = {
    "Assigned Lead": ("leads", "Warm Leads", False),
    "Prospect": ("sales", "Estimate Pending Schedule", False),
    "Approved": ("jobs", "In Progress", True),
    "Completed": ("jobs", "Complete", True),
    "Invoiced": ("jobs", "Complete", True),
    "Closed": ("jobs", "Closed", True),
}
DEFAULT_MILESTONE_STAGE: Tuple[str, str, bool] = ("leads", "Cold Leads", False)


def resolve_milestone_stage(milestone: Optional[str]) -> Tuple[str, str, bool]:
    """Map an AccuLynx milestone to (pipeline_slug, stage_name, creates_estimate).

    The third value indicates whether jobs with this milestone should
    produce a Job + Estimate record (Phase 3 behavior).
    """
    if not milestone:
        return DEFAULT_MILESTONE_STAGE
    return MILESTONE_MAP.get(milestone.strip(), DEFAULT_MILESTONE_STAGE)


def parse_ar_age_job_name(raw: Optional[str]) -> Optional[str]:
    """Extract a contact name from an AR Age 'Job Name' value.

    The AR Age report formats job names as '1088: Kelsey Bass' — we want
    just the name. Falls back to the whole string (whitespace-collapsed)
    if there's no colon.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    if ":" in s:
        s = s.split(":", 1)[1]
    return re.sub(r"\s+", " ", s).strip() or None


def safe_decimal(raw: Optional[str]) -> Decimal:
    """Parse a money-ish string into Decimal. Strips $ and commas.

    Returns Decimal('0') for empty/None/unparseable input — important for
    Contract Total = '' rows (Prospects with no estimate yet).
    """
    if not raw:
        return Decimal("0")
    s = raw.strip().replace("$", "").replace(",", "")
    if not s:
        return Decimal("0")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return Decimal("0")


# ---------------------------- reference loader ----------------------------


def load_reference_data(db) -> Dict:
    """Pre-fetch pipelines/stages/users into lookup dicts.

    Validates that every stage named in MILESTONE_MAP + DEFAULT_MILESTONE_STAGE
    exists in the DB. Raises SystemExit with a clear error if not — better
    to crash than to silently mis-categorize 220 contacts.
    """
    pipelines = {p.slug: p for p in db.query(Pipeline).all()}
    if not pipelines:
        raise SystemExit("No pipelines found in DB — refusing to import")

    stages_by_key: Dict[Tuple[str, str], PipelineStage] = {}
    for p in pipelines.values():
        for s in p.stages:
            stages_by_key[(p.slug, s.name)] = s

    required_stages = set()
    for slug, stage_name, _ in MILESTONE_MAP.values():
        required_stages.add((slug, stage_name))
    required_stages.add((DEFAULT_MILESTONE_STAGE[0], DEFAULT_MILESTONE_STAGE[1]))

    missing = [k for k in required_stages if k not in stages_by_key]
    if missing:
        missing_fmt = ", ".join(f"{slug}/{name}" for slug, name in missing)
        raise SystemExit(
            f"Required pipeline stages are missing in DB: {missing_fmt}. "
            f"Refusing to import — add them via /settings/pipelines first."
        )

    users = db.query(User).filter(User.is_active.is_(True)).all()
    users_by_email = {u.email.lower(): u for u in users if u.email}
    users_by_full_name = {u.full_name.lower(): u for u in users if u.full_name}
    users_by_first_name: Dict[str, User] = {}
    for u in users:
        if u.full_name:
            first = u.full_name.split()[0].lower()
            users_by_first_name.setdefault(first, u)

    return {
        "pipelines": pipelines,
        "stages": stages_by_key,
        "users": users,
        "users_by_email": users_by_email,
        "users_by_full_name": users_by_full_name,
        "users_by_first_name": users_by_first_name,
    }


def find_salesperson(refs: Dict, raw_name: Optional[str]) -> Optional[User]:
    if not raw_name:
        return None
    name = raw_name.strip().lower()
    if not name:
        return None
    if name in refs["users_by_full_name"]:
        return refs["users_by_full_name"][name]
    first = name.split()[0]
    return refs["users_by_first_name"].get(first)


# ---------------------------- phase 0: cleanup ----------------------------


def cleanup_previous_import(db, import_id: str) -> Dict[str, int]:
    """Delete everything created by a previous ContactImport batch.

    Deletes in FK-safe order: payments -> invoices -> estimates -> jobs
    -> contacts -> ContactImport row itself. Returns counts.

    Safety: only deletes records LINKED to contacts tagged with this
    import_id. Does NOT touch user accounts (Marcus, Dale, Ian).
    """
    counts = {
        "payments": 0,
        "invoices": 0,
        "estimates": 0,
        "jobs": 0,
        "contacts": 0,
        "batches": 0,
    }

    contact_ids = [
        c.id for c in db.query(Contact.id).filter(Contact.import_id == import_id).all()
    ]
    if not contact_ids:
        print(f"  Phase 0: no contacts found with import_id={import_id} — skipping")
        # Even with no contacts, clean up the orphaned ContactImport row
        batch = db.query(ContactImport).filter(ContactImport.id == import_id).first()
        if batch is not None:
            db.delete(batch)
            counts["batches"] = 1
        return counts

    # Find all jobs linked to those contacts
    job_ids = [
        j.id for j in db.query(Job.id).filter(Job.contact_id.in_(contact_ids)).all()
    ]

    if job_ids:
        # Payments depend on invoices, invoices depend on jobs
        invoice_ids = [
            i.id for i in db.query(Invoice.id).filter(Invoice.job_id.in_(job_ids)).all()
        ]
        if invoice_ids:
            counts["payments"] = (
                db.query(Payment)
                .filter(Payment.invoice_id.in_(invoice_ids))
                .delete(synchronize_session=False)
            )
            counts["invoices"] = (
                db.query(Invoice)
                .filter(Invoice.id.in_(invoice_ids))
                .delete(synchronize_session=False)
            )

        # NOTE: Estimate has no contact_id column — only job_id — so the
        # job-linked deletion above catches all estimates from a v1 import.
        counts["estimates"] = (
            db.query(Estimate)
            .filter(Estimate.job_id.in_(job_ids))
            .delete(synchronize_session=False)
        )

        counts["jobs"] = (
            db.query(Job)
            .filter(Job.id.in_(job_ids))
            .delete(synchronize_session=False)
        )

    counts["contacts"] = (
        db.query(Contact)
        .filter(Contact.import_id == import_id)
        .delete(synchronize_session=False)
    )

    batch = db.query(ContactImport).filter(ContactImport.id == import_id).first()
    if batch is not None:
        db.delete(batch)
        counts["batches"] = 1

    db.flush()
    print(
        f"  Phase 0: deleted {counts['payments']} payments, "
        f"{counts['invoices']} invoices, {counts['estimates']} estimates, "
        f"{counts['jobs']} jobs, {counts['contacts']} contacts, "
        f"{counts['batches']} import batch"
    )
    return counts


# ---------------------------- phase 1: contacts ----------------------------

# AccuLynx placeholder emails seen in v1 import — many real contacts share
# these, so we exclude them from email-based dedup.
PLACEHOLDER_EMAILS = {"na@example.com", "getlater@example.com", "getkater@example.com"}

# Skip importing these as contacts — they exist as user accounts.
SKIP_CONTACT_NAMES_LC = {"marcus hale", "dale brennan", "ian titus"}
SKIP_CONTACT_EMAILS = {
    "marcus@legacy-roofing.example",
    "marcus@painting-partner.example",
    "dale@legacy-roofing.example",
    "admin@legacy-roofing.example",
}


def build_dedup_index(db) -> Dict[str, set]:
    """Build dedup lookups from existing non-deleted contacts."""
    rows = (
        db.query(Contact.email, Contact.phone, Contact.name, Contact.address)
        .filter(Contact.deleted_at.is_(None))
        .all()
    )
    by_email = set()
    by_phone = set()
    by_name = set()
    for email, phone, name, address in rows:
        if email:
            by_email.add(email.strip().lower())
        if phone:
            d = digits_only(phone)
            if d:
                by_phone.add(d)
        if name:
            by_name.add(normalize_name(name))
    return {"emails": by_email, "phones": by_phone, "names": by_name}


def import_contacts(
    db,
    refs: Dict,
    rows: List[dict],
    csv_path: str,
    import_id: str,
) -> Tuple[Dict, Dict[str, Contact], Dict[str, Contact]]:
    """Phase 1: insert new contacts from the Contacts CSV.

    Returns (counts, by_name_lc, by_phone_digits) where the two dicts cover
    BOTH newly-created contacts AND pre-existing contacts whose name/phone
    matched. The maps are used by Phase 2 (job enrichment by name) and
    Phase 4 (invoice matching by phone).
    """
    counts: Dict[str, object] = {
        "imported": 0,
        "skipped_dup_email": 0,
        "skipped_dup_name": 0,
        "skipped_dup_phone": 0,
        "skipped_no_name": 0,
        "skipped_user_account": 0,
    }
    by_name_lc: Dict[str, Contact] = {}
    by_phone_digits: Dict[str, Contact] = {}

    existing = build_dedup_index(db)
    csv_email_counts = Counter(
        normalize_email(r.get("Contact: Email")) for r in rows if r.get("Contact: Email")
    )

    # Pre-populate name/phone maps with EXISTING contacts so Phase 2/4 can
    # still match against them (e.g., if Ian was already in the DB).
    for c in db.query(Contact).filter(Contact.deleted_at.is_(None)).all():
        n = normalize_name(c.name)
        if n and n not in by_name_lc:
            by_name_lc[n] = c
        if c.phone:
            d = digits_only(c.phone)
            if d and d not in by_phone_digits:
                by_phone_digits[d] = c

    for i, row in enumerate(rows, start=1):
        first = (row.get("Contact: First Name") or "").strip()
        last = (row.get("Contact: Last Name") or "").strip()
        full_name = (first + " " + last).strip()
        if not full_name:
            counts["skipped_no_name"] += 1
            continue

        name_lc = normalize_name(full_name)
        email = normalize_email(row.get("Contact: Email"))
        phone_raw = (row.get("Contact: Phone") or "").strip()
        phone_d = digits_only(phone_raw)

        # User-account skip
        if name_lc in SKIP_CONTACT_NAMES_LC or (email and email in SKIP_CONTACT_EMAILS):
            counts["skipped_user_account"] += 1
            continue

        street, city, state, zip_code = parse_address(row.get("Contact: Mailing Address"))
        client_type = (row.get("Contact: Types") or "").strip() or None
        created_at = parse_date(row.get("Contact: Created Date"))

        # Dedup — case-insensitive email (unless placeholder/repeated), then name
        if email and email not in PLACEHOLDER_EMAILS and csv_email_counts.get(email, 0) <= 1:
            if email in existing["emails"]:
                counts["skipped_dup_email"] += 1
                # Map this row to the existing contact so Phase 2/4 still work
                existing_contact = (
                    db.query(Contact)
                    .filter(Contact.email.ilike(email), Contact.deleted_at.is_(None))
                    .first()
                )
                if existing_contact is not None:
                    if name_lc not in by_name_lc:
                        by_name_lc[name_lc] = existing_contact
                    if phone_d and phone_d not in by_phone_digits:
                        by_phone_digits[phone_d] = existing_contact
                continue

        if name_lc in existing["names"]:
            counts["skipped_dup_name"] += 1
            continue

        contact = Contact(
            name=full_name,
            email=email or None,
            phone=phone_raw or None,
            address=street,
            city=city,
            state=state or "IN",
            zip=zip_code,
            client_type=client_type,
            pipeline_id=None,
            stage_id=None,
            import_id=import_id,
            import_source_file=os.path.basename(csv_path)[:500],
        )
        if created_at is not None:
            contact.created_at = created_at

        db.add(contact)
        counts["imported"] += 1
        print(f"  Contact {i}/{len(rows)}: {full_name}")

        by_name_lc[name_lc] = contact
        if phone_d:
            by_phone_digits[phone_d] = contact

        # Refresh dedup index so a duplicate row in the same CSV doesn't slip through
        if email and email not in PLACEHOLDER_EMAILS:
            existing["emails"].add(email)
        if phone_d:
            existing["phones"].add(phone_d)
        existing["names"].add(name_lc)

    db.flush()
    return counts, by_name_lc, by_phone_digits


# ---------------------------- phase 2: enrich ------------------------------


def enrich_contacts_from_jobs(
    db,
    refs: Dict,
    job_rows: List[dict],
    contacts_by_name: Dict[str, Contact],
) -> Dict:
    """Phase 2: set lead_source, pipeline, stage on contacts from Jobs CSV.

    Lookup by Contact Name (whitespace-normalized, case-insensitive), with
    Contact Email as fallback. Unmatched jobs are reported but not failed.
    """
    counts = {
        "matched": 0,
        "matched_by_email": 0,
        "unmatched": 0,
        "lead_source_set": 0,
        "address_filled": 0,
    }
    pipeline_counter: Counter = Counter()
    lead_sources: Counter = Counter()
    unmatched: List[str] = []

    # Email -> Contact fallback index. We rebuild from the by_name dict so
    # the lookup includes both new and existing contacts.
    by_email: Dict[str, Contact] = {}
    for c in contacts_by_name.values():
        if c.email:
            by_email.setdefault(c.email.strip().lower(), c)

    for row in job_rows:
        raw_name = (row.get("Contact Name") or "").strip()
        name_lc = normalize_name(raw_name)
        email = normalize_email(row.get("Contact Email"))
        milestone = (row.get("Current Milestone") or "").strip()
        lead_source = consolidate_lead_source(row.get("Lead Source"))
        location = (row.get("Location Address") or "").strip() or None

        contact = contacts_by_name.get(name_lc)
        if contact is None and email and email in by_email:
            contact = by_email[email]
            counts["matched_by_email"] += 1
        if contact is None:
            counts["unmatched"] += 1
            unmatched.append(raw_name)
            continue

        counts["matched"] += 1

        if lead_source and not contact.lead_source:
            contact.lead_source = lead_source
            counts["lead_source_set"] += 1
            lead_sources[lead_source] += 1

        if location and not contact.address:
            street, city, state, zip_code = parse_address(location)
            contact.address = street
            if city:
                contact.city = city
            if state:
                contact.state = state
            if zip_code:
                contact.zip = zip_code
            counts["address_filled"] += 1

        slug, stage_name, _ = resolve_milestone_stage(milestone)
        pipeline = refs["pipelines"].get(slug)
        stage = refs["stages"].get((slug, stage_name))
        if pipeline and stage:
            contact.pipeline_id = pipeline.id
            contact.stage_id = stage.id
            pipeline_counter[(slug, stage_name)] += 1

    db.flush()
    counts["pipeline_distribution"] = pipeline_counter  # type: ignore
    counts["lead_sources"] = lead_sources  # type: ignore
    counts["unmatched_names"] = unmatched  # type: ignore
    return counts


# ------------------------- phase 3: jobs + estimates -----------------------


def create_jobs_and_estimates(
    db,
    refs: Dict,
    job_rows: List[dict],
    contacts_by_name: Dict[str, Contact],
    import_user_id: Optional[int],
) -> Tuple[Dict, Dict[int, Estimate]]:
    """Phase 3: for jobs with Contract Total > 0, create Job + approved Estimate.

    Returns (counts, estimates_by_contact_id) so Phase 4 can find an
    existing estimate to attach invoices to.

    Note: a single contact can have multiple jobs in the CSV (e.g., Jodi
    Ruch has 2 Approved rows). We create a separate Job + Estimate for
    each row. The estimates_by_contact_id map keeps only the LAST one,
    which is acceptable because Phase 4's match is fuzzy.
    """
    counts = {
        "jobs_created": 0,
        "estimates_created": 0,
        "skipped_no_contact": 0,
        "skipped_zero_total": 0,
    }
    estimates_by_contact: Dict[int, Estimate] = {}

    for row in job_rows:
        milestone = (row.get("Current Milestone") or "").strip()
        slug, stage_name, creates_estimate = resolve_milestone_stage(milestone)
        if not creates_estimate:
            continue

        contract_total = safe_decimal(row.get("Contract Total"))
        if contract_total <= 0:
            counts["skipped_zero_total"] += 1
            continue

        raw_name = (row.get("Contact Name") or "").strip()
        name_lc = normalize_name(raw_name)
        contact = contacts_by_name.get(name_lc)
        if contact is None:
            counts["skipped_no_contact"] += 1
            continue

        location = (row.get("Location Address") or "").strip() or None
        approved_date = parse_date(row.get("Approved Date"))
        completed_date = parse_date(row.get("Completed Date"))
        lead_date = parse_date(row.get("Lead Date"))
        lead_source = consolidate_lead_source(row.get("Lead Source"))
        salesperson = find_salesperson(refs, row.get("Primary Salesperson"))

        pipeline = refs["pipelines"][slug]
        stage = refs["stages"][(slug, stage_name)]

        job = Job(
            pipeline_id=pipeline.id,
            contact_id=contact.id,
            stage_id=stage.id,
            assigned_to_user_id=salesperson.id if salesperson else None,
            job_type="Roofing",
            work_type="Roofing",
            property_address=location or contact.address,
            contract_value=contract_total,
            lead_source=lead_source,
            display_name=raw_name,
            last_activity_at=completed_date or approved_date or lead_date,
        )
        db.add(job)
        db.flush()
        counts["jobs_created"] += 1

        estimate = Estimate(
            job_id=job.id,
            name=f"Imported from AccuLynx — {raw_name}",
            status="approved",
            subtotal=contract_total,
            tax=Decimal("0"),
            total=contract_total,
            tax_rate=Decimal("0"),
            tax_included=True,
            job_type="Roofing",
            work_type="roofing",
            location_address=location or contact.address,
            assigned_to_user_id=salesperson.id if salesperson else None,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            approved_at=approved_date or completed_date,
            approved_by=row.get("Primary Salesperson") or None,
            created_by_user_id=import_user_id,
        )
        db.add(estimate)
        db.flush()
        counts["estimates_created"] += 1
        estimates_by_contact[contact.id] = estimate

    return counts, estimates_by_contact


# --------------------- phase 4: invoices + payments ------------------------


def _build_ar_age_by_phone(ar_age_rows: List[dict]) -> Dict[str, str]:
    """Map phone digits -> contact name parsed from AR Age 'Job Name'."""
    out: Dict[str, str] = {}
    for row in ar_age_rows:
        phone_d = digits_only(row.get("Phone Number"))
        name = parse_ar_age_job_name(row.get("Job Name"))
        if phone_d and name and phone_d not in out:
            out[phone_d] = name
    return out


def _get_or_create_stub_contact(
    db,
    refs: Dict,
    phone_raw: str,
    phone_d: str,
    fallback_name: Optional[str],
    location: Optional[str],
    import_id: str,
    csv_path: str,
    contacts_by_phone: Dict[str, Contact],
) -> Contact:
    """Create a minimal contact record for an invoice that didn't match.

    Uses fallback_name (from AR Age) if available, else 'Unknown
    (<last 4 digits>)'. Places in Leads/Cold Leads.
    """
    if phone_d in contacts_by_phone:
        return contacts_by_phone[phone_d]

    name = fallback_name or f"Unknown ({phone_d[-4:]})"
    street, city, state, zip_code = parse_address(location)
    cold = refs["pipelines"].get("leads")
    cold_stage = refs["stages"].get(("leads", "Cold Leads"))

    stub = Contact(
        name=name,
        phone=phone_raw or None,
        address=street,
        city=city,
        state=state or "IN",
        zip=zip_code,
        pipeline_id=cold.id if cold else None,
        stage_id=cold_stage.id if cold_stage else None,
        import_id=import_id,
        import_source_file=os.path.basename(csv_path)[:500],
    )
    db.add(stub)
    db.flush()
    contacts_by_phone[phone_d] = stub
    return stub


def _ensure_job_and_estimate_for_invoice(
    db,
    refs: Dict,
    contact: Contact,
    approved_job_value: Decimal,
    location: Optional[str],
    invoice_milestone: Optional[str],
    invoice_created_at: Optional[datetime],
    salesperson_name: Optional[str],
    import_user_id: Optional[int],
    estimates_by_contact: Dict[int, Estimate],
) -> Tuple[Job, Estimate]:
    """Return (job, estimate) for an invoice, creating them if needed.

    If the contact already has an estimate from Phase 3, reuse it (and its
    Job). Otherwise create a Job + Estimate stub using the invoice's
    Approved Job Value as the total and the invoice's milestone for
    pipeline placement.
    """
    existing = estimates_by_contact.get(contact.id)
    if existing is not None and existing.job_id is not None:
        job = db.query(Job).filter(Job.id == existing.job_id).first()
        if job is not None:
            return job, existing

    slug, stage_name, _ = resolve_milestone_stage(invoice_milestone)
    pipeline = refs["pipelines"][slug]
    stage = refs["stages"][(slug, stage_name)]

    job = Job(
        pipeline_id=pipeline.id,
        contact_id=contact.id,
        stage_id=stage.id,
        job_type="Roofing",
        work_type="Roofing",
        property_address=location or contact.address,
        contract_value=approved_job_value if approved_job_value > 0 else None,
        display_name=contact.name,
        last_activity_at=invoice_created_at,
    )
    db.add(job)
    db.flush()

    estimate = Estimate(
        job_id=job.id,
        name=f"Imported from AccuLynx invoice — {contact.name}",
        status="approved",
        subtotal=approved_job_value,
        tax=Decimal("0"),
        total=approved_job_value,
        tax_rate=Decimal("0"),
        tax_included=True,
        job_type="Roofing",
        work_type="roofing",
        location_address=location or contact.address,
        pipeline_id=pipeline.id,
        stage_id=stage.id,
        approved_at=invoice_created_at,
        approved_by=salesperson_name or None,
        created_by_user_id=import_user_id,
    )
    db.add(estimate)
    db.flush()
    estimates_by_contact[contact.id] = estimate
    return job, estimate


def create_invoices_and_payments(
    db,
    refs: Dict,
    invoice_rows: List[dict],
    ar_age_rows: List[dict],
    contacts_by_phone: Dict[str, Contact],
    estimates_by_contact: Dict[int, Estimate],
    import_id: str,
    csv_path: str,
    import_user_id: Optional[int],
) -> Dict:
    """Phase 4: create invoice + payment records.

    Match strategy: phone digits exactly. Unmatched invoices spawn stub
    contacts using AR Age's job-name parsing for the name when available.
    """
    counts = {
        "invoices_created": 0,
        "payments_created": 0,
        "stub_contacts_created": 0,
        "estimates_created_for_invoice": 0,
        "matched_to_existing_estimate": 0,
        "skipped_no_phone": 0,
        "skipped_duplicate_invoice_number": 0,
    }

    ar_age_by_phone = _build_ar_age_by_phone(ar_age_rows)
    existing_invoice_numbers = {
        n for (n,) in db.query(Invoice.invoice_number).all()
    }

    for row in invoice_rows:
        invoice_number = (row.get("Invoice Number") or "").strip()
        if not invoice_number:
            continue
        if invoice_number in existing_invoice_numbers:
            counts["skipped_duplicate_invoice_number"] += 1
            continue

        phone_raw = (row.get("Phone Number") or "").strip()
        phone_d = digits_only(phone_raw)
        if not phone_d:
            counts["skipped_no_phone"] += 1
            continue

        invoice_total = safe_decimal(row.get("Invoice Total"))
        invoice_balance = safe_decimal(row.get("Invoice Balance Due"))
        approved_job_value = safe_decimal(row.get("Approved Job Value"))
        invoice_status_raw = row.get("Invoice Status")
        invoice_status = map_invoice_status(invoice_status_raw)
        invoice_date = parse_date(row.get("Invoice Date"))
        invoice_created_at = parse_date(row.get("Invoice Created Date"))
        last_recorded_date = parse_date(row.get("Last Recorded Date"))
        invoice_milestone = (row.get("Current Milestone") or "").strip()
        location = (row.get("Location Address") or "").strip() or None
        salesperson_name = (row.get("Primary Salesperson") or "").strip() or None

        contact = contacts_by_phone.get(phone_d)
        if contact is None:
            contact = _get_or_create_stub_contact(
                db, refs, phone_raw, phone_d,
                ar_age_by_phone.get(phone_d),
                location, import_id, csv_path, contacts_by_phone,
            )
            counts["stub_contacts_created"] += 1

        existing_est = estimates_by_contact.get(contact.id)
        job, estimate = _ensure_job_and_estimate_for_invoice(
            db, refs, contact,
            approved_job_value if approved_job_value > 0 else invoice_total,
            location, invoice_milestone, invoice_created_at,
            salesperson_name, import_user_id, estimates_by_contact,
        )
        if existing_est is not None and existing_est.id == estimate.id:
            counts["matched_to_existing_estimate"] += 1
        else:
            counts["estimates_created_for_invoice"] += 1

        # Date fields: Invoice.due_date and date_invoiced are Date types
        date_invoiced = invoice_created_at.date() if invoice_created_at else None
        due_date = invoice_date.date() if invoice_date else None

        amount_paid = invoice_total - invoice_balance
        if amount_paid < 0:
            amount_paid = Decimal("0")
        if amount_paid > 0 and amount_paid < invoice_total:
            invoice_status = "partial"

        invoice = Invoice(
            job_id=job.id,
            estimate_id=estimate.id,
            invoice_number=invoice_number,
            status=invoice_status,
            date_invoiced=date_invoiced,
            due_date=due_date,
            subtotal=invoice_total,
            tax=Decimal("0"),
            tax_rate=Decimal("0"),
            total=invoice_total,
            amount_paid=amount_paid,
            balance=invoice_balance,
            is_deposit=False,
            notes=f"Imported from AccuLynx ({invoice_status_raw or 'unknown status'})",
            created_by=import_user_id,
        )
        db.add(invoice)
        db.flush()
        counts["invoices_created"] += 1
        existing_invoice_numbers.add(invoice_number)
        print(
            f"  Invoice {invoice_number}: {contact.name} "
            f"${invoice_total} ({invoice_status})"
        )

        # Payment: any positive paid amount creates a Payment row
        if amount_paid > 0:
            pay_date = (
                last_recorded_date or invoice_date or invoice_created_at
            )
            payment = Payment(
                invoice_id=invoice.id,
                date_received=(pay_date.date() if pay_date else date.today()),
                amount=amount_paid,
                method="other",
                reference=None,
                notes="Imported from AccuLynx",
                is_deposit=False,
                created_by=import_user_id,
            )
            db.add(payment)
            counts["payments_created"] += 1

    db.flush()
    return counts


# -------------------- phase 5: default unmatched contacts ------------------


def assign_default_pipeline(
    db,
    refs: Dict,
    contacts_by_name: Dict[str, Contact],
    import_id: str,
) -> int:
    """Phase 5: place any imported contact still without a pipeline into
    Leads/Cold Leads.

    Only touches contacts tagged with THIS run's import_id so we don't
    move existing un-piped contacts.
    """
    cold = refs["pipelines"].get("leads")
    cold_stage = refs["stages"].get(("leads", "Cold Leads"))
    if not (cold and cold_stage):
        return 0

    set_count = 0
    for contact in contacts_by_name.values():
        if contact.import_id != import_id:
            continue
        if contact.pipeline_id is None and contact.stage_id is None:
            contact.pipeline_id = cold.id
            contact.stage_id = cold_stage.id
            set_count += 1
    db.flush()
    return set_count


# ---------------------------- summary + main -------------------------------


def print_summary(
    dry_run: bool,
    import_id: str,
    cleanup_counts: Dict,
    contacts_counts: Dict,
    jobs_counts: Dict,
    estimates_counts: Dict,
    invoices_counts: Dict,
    default_count: int,
) -> None:
    mode = "DRY-RUN (rolled back)" if dry_run else "COMMITTED"
    print()
    print(f"=== AccuLynx v2 import — {mode} ===")
    print(f"New batch:  {import_id}")
    print()
    print("--- Phase 0: cleanup ---")
    for k, v in cleanup_counts.items():
        print(f"  {k:<10}: {v}")
    print()
    print("--- Phase 1: contacts ---")
    for k in (
        "imported", "skipped_dup_email", "skipped_dup_name",
        "skipped_no_name", "skipped_user_account",
    ):
        print(f"  {k:<22}: {contacts_counts.get(k, 0)}")
    print()
    print("--- Phase 2: job enrichment ---")
    for k in ("matched", "matched_by_email", "unmatched",
              "lead_source_set", "address_filled"):
        print(f"  {k:<22}: {jobs_counts.get(k, 0)}")
    print()
    print("  Pipeline placement (contacts):")
    for (slug, name), n in jobs_counts.get(
        "pipeline_distribution", Counter()
    ).most_common():
        print(f"    {slug:>8} / {name:<28} : {n}")
    print()
    print("  Lead sources:")
    for src, n in jobs_counts.get("lead_sources", Counter()).most_common():
        print(f"    {src:<28} : {n}")
    print()
    print("--- Phase 3: jobs + estimates ---")
    for k in ("jobs_created", "estimates_created",
              "skipped_no_contact", "skipped_zero_total"):
        print(f"  {k:<22}: {estimates_counts.get(k, 0)}")
    print()
    print("--- Phase 4: invoices + payments ---")
    for k in ("invoices_created", "payments_created",
              "stub_contacts_created", "estimates_created_for_invoice",
              "matched_to_existing_estimate", "skipped_no_phone",
              "skipped_duplicate_invoice_number"):
        print(f"  {k:<32}: {invoices_counts.get(k, 0)}")
    print()
    print(f"--- Phase 5: defaulted to Leads/Cold: {default_count}")
    print()
    unmatched = jobs_counts.get("unmatched_names", [])
    if unmatched:
        print("Unmatched job contact names:")
        for n in unmatched:
            print(f"  - {n}")
        print()


def get_import_user(db, email: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    return (
        db.query(User)
        .filter(User.role == "admin", User.is_active.is_(True))
        .first()
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--previous-import-id", default=None)
    parser.add_argument("--contacts", default=DEFAULT_CONTACTS_CSV)
    parser.add_argument("--jobs", default=DEFAULT_JOBS_CSV)
    parser.add_argument("--invoices", default=DEFAULT_INVOICES_CSV)
    parser.add_argument("--ar-age", default=DEFAULT_AR_AGE_CSV)
    parser.add_argument("--import-user", default=DEFAULT_IMPORT_USER_EMAIL)
    args = parser.parse_args()

    for path, label in [
        (args.contacts, "contacts"), (args.jobs, "jobs"),
        (args.invoices, "invoices"), (args.ar_age, "ar-age"),
    ]:
        if not os.path.exists(path):
            sys.exit(f"{label} CSV not found: {path}")

    with open(args.contacts, newline="", encoding="utf-8-sig") as f:
        contact_rows = list(csv.DictReader(f))
    with open(args.jobs, newline="", encoding="utf-8-sig") as f:
        job_rows = list(csv.DictReader(f))
    with open(args.invoices, newline="", encoding="utf-8-sig") as f:
        invoice_rows = list(csv.DictReader(f))
    with open(args.ar_age, newline="", encoding="utf-8-sig") as f:
        ar_age_rows = list(csv.DictReader(f))

    db = SessionLocal()
    try:
        refs = load_reference_data(db)
        import_user = get_import_user(db, args.import_user)
        if import_user is None:
            sys.exit("No admin user available to attribute this import")

        # Phase 0: cleanup previous import
        if args.previous_import_id:
            cleanup_counts = cleanup_previous_import(db, args.previous_import_id)
        else:
            cleanup_counts = {
                "payments": 0, "invoices": 0, "estimates": 0,
                "jobs": 0, "contacts": 0, "batches": 0,
            }

        new_import_id = uuid.uuid4().hex
        batch = ContactImport(
            id=new_import_id,
            user_id=import_user.id,
            file_name=os.path.basename(args.contacts),
            total_rows=len(contact_rows),
        )
        db.add(batch)
        db.flush()

        # Phase 1
        contacts_counts, contacts_by_name, contacts_by_phone = import_contacts(
            db, refs, contact_rows, args.contacts, new_import_id,
        )

        # Phase 2
        jobs_counts = enrich_contacts_from_jobs(
            db, refs, job_rows, contacts_by_name,
        )

        # Phase 3
        estimates_counts, estimates_by_contact = create_jobs_and_estimates(
            db, refs, job_rows, contacts_by_name, import_user.id,
        )

        # Phase 4
        invoices_counts = create_invoices_and_payments(
            db, refs, invoice_rows, ar_age_rows,
            contacts_by_phone, estimates_by_contact,
            new_import_id, args.invoices, import_user.id,
        )

        # Phase 5
        default_count = assign_default_pipeline(
            db, refs, contacts_by_name, new_import_id,
        )

        batch.imported_count = contacts_counts.get("imported", 0)
        batch.skipped_count = (
            contacts_counts.get("skipped_no_name", 0)
            + contacts_counts.get("skipped_user_account", 0)
        )
        batch.duplicate_count = (
            contacts_counts.get("skipped_dup_email", 0)
            + contacts_counts.get("skipped_dup_name", 0)
            + contacts_counts.get("skipped_dup_phone", 0)
        )

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print_summary(
            args.dry_run, new_import_id,
            cleanup_counts, contacts_counts, jobs_counts,
            estimates_counts, invoices_counts, default_count,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
