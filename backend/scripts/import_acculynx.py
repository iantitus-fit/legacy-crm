"""One-time importer for AccuLynx CSV exports into Legacy CRM.

Reads two CSV files and loads them into the existing data model:
  - Contacts Report ... csv  (217 contacts)
  - Jobs Report ... csv       (70 jobs)

Behavior:
  * Idempotent. Re-running does not create duplicates — contacts are
    matched against existing ones by (email when unique) OR
    (name + address) OR (name + phone). Existing contacts are skipped.
  * Address strings like "214 Larkspur Drive, Kokomo, IN 46901 US" are
    parsed into address / city / state / zip. "US" is dropped.
  * Dates in the AccuLynx M/D/YY format are parsed as 21st-century dates.
  * Lead source is copied from the jobs CSV onto the matched contact.
  * Current Milestone is mapped to (pipeline, stage):
        Assigned Lead -> Leads / Warm Leads
        Prospect      -> Sales / Draft
        Approved      -> Jobs  / Pending Schedule
        Invoiced      -> Jobs  / In Progress
        Closed        -> Jobs  / Closed
  * Contacts that don't appear in the jobs CSV default to Leads / Cold Leads.
  * For Approved/Invoiced/Closed milestones a Job stub and a basic
    Estimate (status=approved) are created so the record shows on the
    Jobs pipeline board. The estimate's `total` is the Contract Total.
  * A `contact_imports` batch row is created and every contact imported
    by this script is tagged with its UUID via `Contact.import_id` —
    consistent with the existing UI import flow and undo-able from there.

Usage:
    docker compose exec backend python -m scripts.import_acculynx [--dry-run]

Flags:
    --dry-run          Don't write — only print the summary.
    --contacts PATH    Override path to the contacts CSV.
    --jobs PATH        Override path to the jobs CSV.
    --import-user EMAIL Email of the user attributed for the import
                       (default: admin@legacy-roofing.example). Falls back to any
                       admin user if not found.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

# When run as `python -m scripts.import_acculynx` from inside the backend
# container, the backend's /app dir is on sys.path so `import app...` works.
# When run as a standalone file, the cwd matters; try to be flexible.
try:
    from app.database import SessionLocal
    from app.models.contact import Contact
    from app.models.contact_import import ContactImport
    from app.models.estimate import Estimate
    from app.models.job import Job
    from app.models.pipeline import Pipeline
    from app.models.pipeline_stage import PipelineStage
    from app.models.user import User
except ModuleNotFoundError:  # pragma: no cover
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
    from app.database import SessionLocal
    from app.models.contact import Contact
    from app.models.contact_import import ContactImport
    from app.models.estimate import Estimate
    from app.models.job import Job
    from app.models.pipeline import Pipeline
    from app.models.pipeline_stage import PipelineStage
    from app.models.user import User


DEFAULT_CONTACTS_CSV = "/app/data/sample/contacts_report.csv"
DEFAULT_JOBS_CSV = "/app/data/sample/jobs_report.csv"
DEFAULT_IMPORT_USER_EMAIL = "admin@legacy-roofing.example"

# Milestone -> (pipeline slug, stage name). The script falls back to the
# first stage of the target pipeline if the named stage isn't found,
# matching the spec's "do not create new stages" rule.
MILESTONE_TO_PIPELINE_STAGE = {
    "Assigned Lead": ("leads", "Warm Leads"),
    "Prospect": ("sales", "Draft"),
    "Approved": ("jobs", "Pending Schedule"),
    "Invoiced": ("jobs", "In Progress"),
    "Closed": ("jobs", "Closed"),
}
DEFAULT_PIPELINE_STAGE = ("leads", "Cold Leads")
JOB_PIPELINE_MILESTONES = {"Approved", "Invoiced", "Closed"}

# Address parsing
ADDR_LAST_SEG_RE = re.compile(
    r"^\s*([A-Za-z .'-]+?)\s+([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)\s*$"
)
# Fallback: last segment is "ST ZIP" (no city), with city carried in the
# segment before. The standard AccuLynx format puts a comma between
# street, city, and "ST ZIP US" so a clean parser handles 99% of rows.

# AccuLynx-style placeholder emails seen in the data. We do not use these
# for dedup because the same address is shared by many real contacts.
PLACEHOLDER_EMAILS = {"na@example.com", "getlater@example.com", "getkater@example.com"}


# ---------------------------- helpers ---------------------------------


def parse_address(raw: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Parse '214 Larkspur Drive, Kokomo, IN 46901 US' -> (street, city, ST, zip).

    Returns (None, None, None, None) for empty / unparseable input.
    Drops the trailing 'US' marker.
    """
    if not raw:
        return None, None, None, None
    s = raw.strip()
    if s.upper().endswith(" US"):
        s = s[:-3].rstrip()
    elif s.upper().endswith(", US"):
        s = s[:-4].rstrip()

    parts = [p.strip() for p in s.split(",")]
    # Standard shape: ["214 Larkspur Drive", "Kokomo", "IN 46901"]
    if len(parts) >= 3:
        street = ", ".join(parts[:-2]) or None
        city = parts[-2] or None
        m = re.match(r"^([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)$", parts[-1])
        if m:
            return street, city, m.group(1).upper(), m.group(2)
        # Last segment doesn't match ST ZIP — give back what we have
        return street, city, None, None
    # Fall back: stuff entire string into street
    return s or None, None, None, None


def parse_date(raw: str) -> Optional[datetime]:
    """Parse '2/14/26' -> datetime(2026, 2, 14, tzinfo=UTC).

    Returns None for empty input.
    """
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def digits_only(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\D", "", s)


def normalize_name(s: Optional[str]) -> str:
    # Collapse runs of whitespace; AccuLynx exports occasionally contain
    # double spaces (e.g. 'Teresa  Murphy') that otherwise miss the
    # contact-by-name match.
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def normalize_email(s: Optional[str]) -> str:
    return (s or "").strip().lower()


# ----------------------------- core -----------------------------------


def load_reference_data(db) -> Dict[str, dict]:
    """Pre-fetch pipelines/stages/users into lookup dicts."""
    pipelines = {p.slug: p for p in db.query(Pipeline).all()}

    stages_by_pipeline_and_name: Dict[Tuple[str, str], PipelineStage] = {}
    first_stage_by_pipeline: Dict[str, PipelineStage] = {}
    for pipeline_slug, pipeline in pipelines.items():
        stages = sorted(pipeline.stages, key=lambda s: s.sort_order)
        if stages:
            first_stage_by_pipeline[pipeline_slug] = stages[0]
        for stage in stages:
            stages_by_pipeline_and_name[(pipeline_slug, stage.name)] = stage

    users = db.query(User).filter(User.is_active.is_(True)).all()
    users_by_full_name = {u.full_name.lower(): u for u in users if u.full_name}
    users_by_first_name: Dict[str, User] = {}
    for u in users:
        if u.full_name:
            first = u.full_name.split()[0].lower()
            users_by_first_name.setdefault(first, u)

    return {
        "pipelines": pipelines,
        "stages": stages_by_pipeline_and_name,
        "first_stage": first_stage_by_pipeline,
        "users": users,
        "users_by_full_name": users_by_full_name,
        "users_by_first_name": users_by_first_name,
    }


def resolve_stage(refs: Dict, milestone: Optional[str]) -> Tuple[Optional[Pipeline], Optional[PipelineStage]]:
    """Map a milestone -> (Pipeline, PipelineStage) using refs.

    Falls back to DEFAULT_PIPELINE_STAGE when milestone is None or empty.
    Falls back to first stage of the target pipeline if the named stage
    doesn't exist.
    """
    if milestone and milestone in MILESTONE_TO_PIPELINE_STAGE:
        pipeline_slug, stage_name = MILESTONE_TO_PIPELINE_STAGE[milestone]
    else:
        pipeline_slug, stage_name = DEFAULT_PIPELINE_STAGE

    pipeline = refs["pipelines"].get(pipeline_slug)
    stage = refs["stages"].get((pipeline_slug, stage_name))
    if pipeline and not stage:
        stage = refs["first_stage"].get(pipeline_slug)
    return pipeline, stage


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


def build_existing_dedup_index(db) -> Dict[str, set]:
    """Build dedup lookups against existing non-deleted contacts.

    Matches the existing contact_importer pattern: dedup by lowercased
    email, by digits-only phone, and by (lowercased name, lowercased
    address) tuple.
    """
    existing = (
        db.query(Contact.email, Contact.phone, Contact.name, Contact.address)
        .filter(Contact.deleted_at.is_(None))
        .all()
    )
    by_email = set()
    by_phone = set()
    by_name_addr = set()
    for email, phone, name, address in existing:
        if email:
            by_email.add(email.strip().lower())
        if phone:
            d = digits_only(phone)
            if d:
                by_phone.add(d)
        if name:
            by_name_addr.add((normalize_name(name), (address or "").strip().lower()))
    return {"emails": by_email, "phones": by_phone, "name_addr": by_name_addr}


def is_duplicate(
    existing: Dict[str, set],
    csv_email_counts: Counter,
    email: str,
    phone_digits: str,
    name_addr: Tuple[str, str],
) -> bool:
    """Return True if this candidate matches an existing contact.

    Email-based match is suppressed when the email appears multiple
    times in the CSV (placeholder) or is in the placeholder list, since
    those collide across genuinely-different contacts.
    """
    if email and email not in PLACEHOLDER_EMAILS and csv_email_counts.get(email, 0) <= 1:
        if email in existing["emails"]:
            return True
    if name_addr[0] and name_addr in existing["name_addr"]:
        return True
    if phone_digits and phone_digits in existing["phones"]:
        return True
    return False


def import_contacts(
    db,
    refs: Dict,
    rows: List[dict],
    csv_path: str,
    import_id: str,
    dry_run: bool,
) -> Tuple[Dict[str, int], Dict[str, Contact]]:
    """Insert contacts. Returns (counts, name_lc -> Contact).

    The returned name_lc dict only contains newly-created contacts so
    the jobs phase can enrich them safely.
    """
    counts: Dict[str, object] = {
        "imported": 0,
        "skipped_dup": 0,
        "skipped_no_name": 0,
        "duplicate_names": [],
    }
    by_name_lc: Dict[str, Contact] = {}

    existing = build_existing_dedup_index(db)
    csv_email_counts = Counter(
        normalize_email(r["Contact: Email"]) for r in rows if r["Contact: Email"]
    )

    for row in rows:
        first = (row.get("Contact: First Name") or "").strip()
        last = (row.get("Contact: Last Name") or "").strip()
        full_name = (first + " " + last).strip()
        if not full_name:
            counts["skipped_no_name"] += 1
            continue

        email = normalize_email(row.get("Contact: Email"))
        phone_raw = (row.get("Contact: Phone") or "").strip()
        phone_d = digits_only(phone_raw)
        street, city, state, zip_code = parse_address(row.get("Contact: Mailing Address"))
        client_type = (row.get("Contact: Types") or "").strip() or None
        created_at = parse_date(row.get("Contact: Created Date"))

        name_lc = normalize_name(full_name)
        name_addr = (name_lc, (street or "").strip().lower())

        if is_duplicate(existing, csv_email_counts, email, phone_d, name_addr):
            counts["skipped_dup"] += 1  # type: ignore[operator]
            counts["duplicate_names"].append(full_name)  # type: ignore[union-attr]
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
            # Default pipeline assignment; jobs phase may override this.
            pipeline_id=None,
            stage_id=None,
            import_id=import_id,
            import_source_file=os.path.basename(csv_path)[:500],
        )
        if created_at is not None:
            contact.created_at = created_at

        db.add(contact)
        counts["imported"] += 1

        # Track for jobs-enrichment phase and update the existing index
        # so duplicate rows within the same CSV are caught too.
        by_name_lc[name_lc] = contact
        if email and email not in PLACEHOLDER_EMAILS:
            existing["emails"].add(email)
        if phone_d:
            existing["phones"].add(phone_d)
        existing["name_addr"].add(name_addr)

    # Flush so that contact.id is available for the jobs phase
    if not dry_run:
        db.flush()

    return counts, by_name_lc


def import_jobs(
    db,
    refs: Dict,
    job_rows: List[dict],
    new_contacts_by_name: Dict[str, Contact],
    import_id: str,
    dry_run: bool,
) -> Dict[str, int]:
    """Enrich contacts from the jobs CSV and create Job+Estimate stubs.

    Only contacts that were just imported (in `new_contacts_by_name`)
    are enriched. Jobs that point to a pre-existing contact (already in
    the DB before this run) are reported as `skipped_existing_contact`.
    """
    counts = {
        "matched": 0,
        "unmatched": 0,
        "lead_source_set": 0,
        "skipped_existing_contact": 0,
        "jobs_created": 0,
        "estimates_created": 0,
    }
    pipeline_counter: Counter = Counter()
    lead_sources: Counter = Counter()
    unmatched: List[str] = []
    salespersons_unknown: Counter = Counter()

    # Build a quick lookup over ALL contacts (incl. those that existed
    # before this run) so we can report when a job's contact exists but
    # we're choosing not to mutate it.
    all_contacts = {
        normalize_name(c.name): c
        for c in db.query(Contact).filter(Contact.deleted_at.is_(None)).all()
    }

    for row in job_rows:
        raw_name = (row.get("Contact Name") or "").strip()
        name_lc = normalize_name(raw_name)
        milestone = (row.get("Current Milestone") or "").strip()
        lead_source = (row.get("Lead Source") or "").strip() or None
        salesperson_name = (row.get("Primary Salesperson") or "").strip()
        location = (row.get("Location Address") or "").strip() or None
        try:
            contract_total = Decimal(row.get("Contract Total") or "0")
        except Exception:
            contract_total = Decimal("0")

        # Date metadata
        lead_date = parse_date(row.get("Lead Date"))
        approved_date = parse_date(row.get("Approved Date"))
        completed_date = parse_date(row.get("Completed Date"))

        pipeline, stage = resolve_stage(refs, milestone)
        pipeline_counter[(pipeline.slug if pipeline else "?", stage.name if stage else "?")] += 1

        contact = new_contacts_by_name.get(name_lc)
        if contact is None:
            existing_contact = all_contacts.get(name_lc)
            if existing_contact is not None:
                counts["matched"] += 1
                counts["skipped_existing_contact"] += 1
                continue
            counts["unmatched"] += 1
            unmatched.append(raw_name)
            continue

        counts["matched"] += 1

        if lead_source:
            contact.lead_source = lead_source
            counts["lead_source_set"] += 1
            lead_sources[lead_source] += 1

        salesperson = find_salesperson(refs, salesperson_name)
        if salesperson_name and salesperson is None:
            salespersons_unknown[salesperson_name] += 1

        if milestone in JOB_PIPELINE_MILESTONES:
            # Contact stays on its current/Sales board for traceability;
            # the Jobs pipeline shows the Job we're about to create.
            # Place contact in Sales/Hot Proposals as the strongest sales
            # signal we have for them.
            sales_pipeline = refs["pipelines"].get("sales")
            sales_hot = refs["stages"].get(("sales", "Hot Proposals"))
            if sales_pipeline and sales_hot:
                contact.pipeline_id = sales_pipeline.id
                contact.stage_id = sales_hot.id

            if pipeline and stage:
                # Idempotency guard: don't create a Job/Estimate if one
                # already exists for this contact at this pipeline.
                existing_job = (
                    db.query(Job)
                    .filter(Job.contact_id == contact.id, Job.pipeline_id == pipeline.id)
                    .first()
                )
                if existing_job is None:
                    job = Job(
                        pipeline_id=pipeline.id,
                        contact_id=contact.id,
                        stage_id=stage.id,
                        assigned_to_user_id=salesperson.id if salesperson else None,
                        job_type="Roofing",
                        work_type="Roofing",
                        property_address=location or contact.address,
                        contract_value=contract_total if contract_total > 0 else None,
                        lead_source=lead_source,
                        display_name=raw_name,
                        last_activity_at=approved_date or lead_date,
                    )
                    db.add(job)
                    counts["jobs_created"] += 1
                    if not dry_run:
                        db.flush()

                    estimate = Estimate(
                        job_id=job.id,
                        name=f"Imported from AccuLynx — {raw_name}",
                        status="approved",
                        subtotal=contract_total,
                        tax=Decimal("0"),
                        total=contract_total,
                        tax_rate=Decimal("0.0000"),
                        tax_included=True,
                        job_type="Roofing",
                        work_type="Roofing",
                        location_address=location or contact.address,
                        assigned_to_user_id=salesperson.id if salesperson else None,
                        pipeline_id=pipeline.id,
                        stage_id=stage.id,
                        approved_at=approved_date,
                        approved_by=salesperson_name or None,
                        created_by_user_id=salesperson.id if salesperson else None,
                    )
                    db.add(estimate)
                    counts["estimates_created"] += 1
        else:
            # Lead / Prospect: contact pipeline placement reflects the
            # milestone directly.
            if pipeline and stage:
                contact.pipeline_id = pipeline.id
                contact.stage_id = stage.id

    counts["unmatched_names"] = unmatched  # type: ignore
    counts["pipeline_distribution"] = pipeline_counter  # type: ignore
    counts["lead_sources"] = lead_sources  # type: ignore
    counts["salespersons_unknown"] = salespersons_unknown  # type: ignore
    return counts


def apply_default_pipeline(
    db,
    refs: Dict,
    new_contacts_by_name: Dict[str, Contact],
) -> int:
    """Place any newly-imported contact without a pipeline into Leads/Cold."""
    default_pipeline = refs["pipelines"].get(DEFAULT_PIPELINE_STAGE[0])
    default_stage = refs["stages"].get(DEFAULT_PIPELINE_STAGE)
    if not (default_pipeline and default_stage):
        return 0
    set_count = 0
    for contact in new_contacts_by_name.values():
        if contact.pipeline_id is None and contact.stage_id is None:
            contact.pipeline_id = default_pipeline.id
            contact.stage_id = default_stage.id
            set_count += 1
    return set_count


def get_import_user(db, email: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email).first()
    if user:
        return user
    return db.query(User).filter(User.role == "admin", User.is_active.is_(True)).first()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing")
    parser.add_argument("--contacts", default=DEFAULT_CONTACTS_CSV, help="Contacts CSV path")
    parser.add_argument("--jobs", default=DEFAULT_JOBS_CSV, help="Jobs CSV path")
    parser.add_argument(
        "--import-user",
        default=DEFAULT_IMPORT_USER_EMAIL,
        help="Email of user attributed for the import batch",
    )
    args = parser.parse_args()

    if not os.path.exists(args.contacts):
        sys.exit(f"Contacts CSV not found: {args.contacts}")
    if not os.path.exists(args.jobs):
        sys.exit(f"Jobs CSV not found: {args.jobs}")

    with open(args.contacts, newline="") as f:
        contact_rows = list(csv.DictReader(f))
    with open(args.jobs, newline="") as f:
        job_rows = list(csv.DictReader(f))

    db = SessionLocal()
    try:
        refs = load_reference_data(db)
        import_user = get_import_user(db, args.import_user)
        if import_user is None:
            sys.exit("No admin user available to attribute this import")

        import_id = uuid.uuid4().hex
        batch = ContactImport(
            id=import_id,
            user_id=import_user.id,
            file_name=os.path.basename(args.contacts),
            total_rows=len(contact_rows),
        )
        db.add(batch)
        if not args.dry_run:
            db.flush()

        contacts_counts, new_contacts_by_name = import_contacts(
            db, refs, contact_rows, args.contacts, import_id, args.dry_run
        )
        jobs_counts = import_jobs(
            db, refs, job_rows, new_contacts_by_name, import_id, args.dry_run
        )
        defaulted = apply_default_pipeline(db, refs, new_contacts_by_name)

        batch.imported_count = contacts_counts["imported"]
        batch.skipped_count = contacts_counts["skipped_no_name"]
        batch.duplicate_count = contacts_counts["skipped_dup"]

        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print_summary(
            args.dry_run,
            args.contacts,
            args.jobs,
            import_id,
            contacts_counts,
            jobs_counts,
            defaulted,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def print_summary(
    dry_run: bool,
    contacts_path: str,
    jobs_path: str,
    import_id: str,
    contacts_counts: Dict,
    jobs_counts: Dict,
    defaulted: int,
) -> None:
    mode = "DRY-RUN" if dry_run else "COMMITTED"
    print()
    print(f"=== AccuLynx import — {mode} ===")
    print(f"Contacts file: {contacts_path}")
    print(f"Jobs file:     {jobs_path}")
    print(f"Import batch:  {import_id}")
    print()
    print("--- Contacts ---")
    print(f"  Imported (new):           {contacts_counts['imported']}")
    print(f"  Skipped (duplicates):     {contacts_counts['skipped_dup']}")
    print(f"  Skipped (no name):        {contacts_counts['skipped_no_name']}")
    dup_names = contacts_counts.get("duplicate_names") or []
    if dup_names:
        print("  Duplicate names (skipped):")
        for n in dup_names:
            print(f"    - {n}")
    print()
    print("--- Jobs ---")
    print(f"  Matched:                  {jobs_counts['matched']}")
    print(f"  Unmatched:                {jobs_counts['unmatched']}")
    print(f"  Skipped (pre-existing):   {jobs_counts['skipped_existing_contact']}")
    print(f"  Lead source set:          {jobs_counts['lead_source_set']}")
    print(f"  Jobs created:             {jobs_counts['jobs_created']}")
    print(f"  Estimates created:        {jobs_counts['estimates_created']}")
    print()
    print(f"  Defaulted to Leads/Cold:  {defaulted}")
    print()
    print("--- Pipeline placement (from jobs CSV) ---")
    for (pslug, sname), n in jobs_counts.get("pipeline_distribution", Counter()).most_common():
        print(f"  {pslug:>8} / {sname:<20} : {n}")
    print()
    print("--- Lead sources ---")
    for src, n in jobs_counts.get("lead_sources", Counter()).most_common():
        print(f"  {src:<22} : {n}")
    unknown = jobs_counts.get("salespersons_unknown", Counter())
    if unknown:
        print()
        print("--- Salespersons not matched to a user (left unassigned) ---")
        for name, n in unknown.most_common():
            print(f"  {name:<22} : {n}")
    unmatched = jobs_counts.get("unmatched_names", [])
    if unmatched:
        print()
        print("--- Unmatched job contact names ---")
        for n in unmatched:
            print(f"  {n}")
    print()


if __name__ == "__main__":
    main()
