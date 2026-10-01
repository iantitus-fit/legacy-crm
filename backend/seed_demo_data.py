"""
Seed script for Legacy CRM demo data.

Populates the database with realistic roofing contractor data
for Legacy Exteriors in Kokomo, Indiana.

Usage:
    # From inside the backend container:
    docker compose exec backend python seed_demo_data.py

    # Or locally (with DATABASE_URL set):
    cd backend && python seed_demo_data.py
"""

import os
import sys
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import text

from app.database import SessionLocal
from app.models.user import User
from app.models.contact import Contact
from app.models.crew import Crew
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage
from app.models.job import Job
from app.models.appointment import Appointment
from app.models.estimate import Estimate
from app.models.estimate_line_item import EstimateLineItem
from app.models.task import Task
from app.models.document import Document
from app.utils.auth import hash_password


EMPLOYEE_DEFS = [
    {"email": "logan@legacy-roofing.example", "full_name": "Logan Reed", "role": "staff", "phone": "(765) 555-0103", "color": "#22C55E", "key": "logan"},
    {"email": "bri@legacy-roofing.example", "full_name": "Bri Martinez", "role": "staff", "phone": "(765) 555-0104", "color": "#F59E0B", "key": "bri"},
    {"email": "henry@legacy-roofing.example", "full_name": "Henry Clark", "role": "crew", "phone": "(765) 555-0105", "color": "#3B82F6", "key": "henry"},
    {"email": "jake@legacy-roofing.example", "full_name": "Jake Moss", "role": "crew", "phone": "(765) 555-0106", "color": "#F97316", "key": "jake"},
    {"email": "sarah@legacy-roofing.example", "full_name": "Sarah Collins", "role": "staff", "phone": "(765) 555-0107", "color": "#EC4899", "key": "sarah"},
]

CREW_DEFS = [
    {"name": "Team Henry", "color": "#3B82F6", "members": ["henry", "bri"]},
    {"name": "Team Logan", "color": "#22C55E", "members": ["logan", "jake"]},
    {"name": "Team Sarah", "color": "#EC4899", "members": ["sarah"]},
]


def seed_employees_and_crews(db):
    """Create employees and crews if they don't already exist.

    Returns a dict of key -> User for use by callers.
    Safe to run multiple times — skips existing records.
    """
    employees = {}
    created_count = 0

    for emp in EMPLOYEE_DEFS:
        user = db.query(User).filter(User.email == emp["email"]).first()
        if not user:
            user = User(
                email=emp["email"],
                full_name=emp["full_name"],
                password_hash=hash_password(os.environ.get("DEMO_USER_PASSWORD", "demo-only-change-me")),
                role=emp["role"],
                phone=emp["phone"],
                color=emp["color"],
            )
            db.add(user)
            db.flush()
            created_count += 1
        employees[emp["key"]] = user

    if created_count:
        print(f"  Created {created_count} employees")
    else:
        print("  Employees already exist. Skipping.")

    crew_created = 0
    crews = {}
    for cdef in CREW_DEFS:
        crew = db.query(Crew).filter(Crew.name == cdef["name"]).first()
        if not crew:
            crew = Crew(name=cdef["name"], color=cdef["color"])
            crew.members = [employees[k] for k in cdef["members"]]
            db.add(crew)
            db.flush()
            crew_created += 1
        crews[cdef["name"]] = crew

    if crew_created:
        print(f"  Created {crew_created} crews")
    else:
        print("  Crews already exist. Skipping.")

    db.commit()
    return employees, crews


def seed(db):
    # -- Guard: skip if demo data already exists --
    existing = db.query(Contact).filter(Contact.name == "Mike Hargrove").first()
    if existing:
        print("Demo data already seeded. Skipping.")
        return

    # -- Look up pipelines and stages (seeded on app startup) --
    pipelines = {p.slug: p for p in db.query(Pipeline).all()}
    if not pipelines:
        print("ERROR: Pipelines not found. Start the app first so pipelines get seeded.")
        sys.exit(1)

    leads_pipeline = pipelines.get("leads")
    sales_pipeline = pipelines.get("sales")
    jobs_pipeline = pipelines.get("jobs")

    if not all([leads_pipeline, sales_pipeline, jobs_pipeline]):
        print(f"ERROR: Expected 3 pipelines (leads, sales, jobs). Found: {list(pipelines.keys())}")
        sys.exit(1)

    # Build stage lookup: (pipeline_slug, stage_name) -> stage
    all_stages = db.query(PipelineStage).all()
    stages = {}
    for s in all_stages:
        p = pipelines.get(next((slug for slug, p in pipelines.items() if p.id == s.pipeline_id), None))
        if p:
            stages[(p.slug, s.name)] = s

    required = [
        ("leads", "Cold Leads"),
        ("leads", "Warm Leads"),
        ("sales", "Estimate Sent"),
        ("sales", "Warm Proposals"),
        ("jobs", "Scheduled"),
        ("jobs", "In Progress"),
        ("jobs", "Complete"),
    ]
    for key in required:
        if key not in stages:
            print(f"ERROR: Missing stage {key}. Found: {list(stages.keys())}")
            sys.exit(1)

    # =====================================================================
    # EMPLOYEES & CREWS — seeded via seed_employees_and_crews() below
    # =====================================================================
    employees, crews = seed_employees_and_crews(db)
    admin = db.query(User).first()
    admin_id = admin.id if admin else None

    # =====================================================================
    # CONTACTS — 5 realistic Howard County / Kokomo, IN residents
    # =====================================================================
    contacts = [
        Contact(
            name="Mike Hargrove",
            email="mike.hargrove@example.com",
            phone="(765) 555-0142",
            address="2341 W Thornapple St",
            city="Kokomo",
            state="IN",
            zip="46901",
        ),
        Contact(
            name="Sharon Whitaker",
            email="sharon.whitaker@example.com",
            phone="(765) 555-0387",
            address="805 N Wrenfield Way",
            city="Kokomo",
            state="IN",
            zip="46901",
        ),
        Contact(
            name="Doug Pennington",
            email="doug.pennington@example.com",
            phone="(765) 555-0219",
            address="1420 E Harrowgate St",
            city="Kokomo",
            state="IN",
            zip="46902",
        ),
        Contact(
            name="Lisa Carmichael",
            email="lcarmichael@example.com",
            phone="(765) 555-0561",
            address="3100 S Quillmont St",
            city="Greentown",
            state="IN",
            zip="46936",
        ),
        Contact(
            name="Jerry Eastman",
            email="jerry.eastman@example.com",
            phone="(765) 555-0804",
            address="780 E Bramblewood St",
            city="Kokomo",
            state="IN",
            zip="46901",
        ),
    ]
    db.add_all(contacts)
    db.flush()  # assigns IDs

    print(f"  Created {len(contacts)} contacts")

    # =====================================================================
    # JOBS — 5 jobs spread across Leads, Sales, and Jobs pipelines
    # =====================================================================
    today = date.today()

    team_henry = crews.get("Team Henry")
    team_logan = crews.get("Team Logan")

    jobs = [
        # 1. Leads pipeline / Cold Leads — new inquiry, no estimate yet
        Job(
            contact_id=contacts[0].id,
            pipeline_id=leads_pipeline.id,
            stage_id=stages[("leads", "Cold Leads")].id,
            assigned_to_user_id=admin_id,
            job_type="Full Reroof",
            work_type="retail",
            property_address="2341 W Thornapple St, Kokomo, IN 46901",
            notes="Homeowner called about missing shingles after wind storm. Wants full reroof quote. 30-year architectural.",
            lead_source="Google LSA",
            contract_value=None,
        ),
        # 2. Leads pipeline / Warm Leads — insurance claim, scheduling inspection
        Job(
            contact_id=contacts[1].id,
            pipeline_id=leads_pipeline.id,
            stage_id=stages[("leads", "Warm Leads")].id,
            assigned_to_user_id=admin_id,
            job_type="Storm Damage Reroof",
            work_type="insurance",
            property_address="805 N Wrenfield Way, Kokomo, IN 46901",
            notes="Hail damage claim filed with State Farm. Adjuster meeting Thursday. Policy #SF-4821773.",
            lead_source="Storm",
            contract_value=Decimal("18500.00"),
        ),
        # 3. Sales pipeline / Estimate Sent — retail, waiting on approval
        Job(
            contact_id=contacts[2].id,
            pipeline_id=sales_pipeline.id,
            stage_id=stages[("sales", "Estimate Sent")].id,
            assigned_to_user_id=admin_id,
            job_type="Full Reroof",
            work_type="retail",
            property_address="1420 E Harrowgate St, Kokomo, IN 46902",
            notes="Two-story colonial, steep 8/12 pitch on front face. Estimate sent 2/14. Homeowner comparing with one other bid.",
            lead_source="Referral",
            contract_value=Decimal("14200.00"),
        ),
        # 4. Jobs pipeline / Scheduled — insurance, crew assigned, scheduled
        Job(
            contact_id=contacts[3].id,
            pipeline_id=jobs_pipeline.id,
            stage_id=stages[("jobs", "Scheduled")].id,
            assigned_to_user_id=admin_id,
            job_type="Storm Damage Reroof + Gutters",
            work_type="insurance",
            property_address="3100 S Quillmont St, Greentown, IN 46936",
            notes="Insurance approved full replacement. IKO Dynasty Sedona. Team Henry assigned. Gutter replacement added as supplement.",
            lead_source="Storm",
            contract_value=Decimal("22750.00"),
            scheduled_date=today + timedelta(days=2),
            scheduled_end_date=today + timedelta(days=4),
            crew_id=team_henry.id if team_henry else None,
        ),
        # 5. Sales pipeline / Warm Proposals — retail, negotiating
        Job(
            contact_id=contacts[4].id,
            pipeline_id=sales_pipeline.id,
            stage_id=stages[("sales", "Warm Proposals")].id,
            assigned_to_user_id=admin_id,
            job_type="Roof Repair",
            work_type="retail",
            property_address="780 E Bramblewood St, Kokomo, IN 46901",
            notes="Small repair job — 2 sq section over garage. Customer wants to compare pricing.",
            lead_source="Door Knock",
            contract_value=Decimal("3800.00"),
        ),
    ]
    db.add_all(jobs)
    db.flush()

    print(f"  Created {len(jobs)} jobs")

    # =====================================================================
    # ESTIMATES — 2 estimates with realistic roofing line items
    # =====================================================================

    # --- Estimate 1: Pennington reroof (job 3, Sales / Estimate Sent) ---
    est1_items = [
        ("IKO Cambridge AR Shingles — Dual Grey", Decimal("34.00"), Decimal("125.50")),
        ("IKO Hip & Ridge Cap Shingles", Decimal("5.00"), Decimal("68.75")),
        ("IKO Leading Edge Plus Starter Strip", Decimal("8.00"), Decimal("52.00")),
        ("Synthetic Underlayment — Tiger Paw", Decimal("7.00"), Decimal("89.00")),
        ("Ice & Water Shield (eaves + valleys)", Decimal("4.00"), Decimal("112.00")),
        ("Aluminum Drip Edge — 10 ft", Decimal("26.00"), Decimal("8.50")),
        ("Step Flashing — Aluminum", Decimal("30.00"), Decimal("3.25")),
        ("Pipe Boot Flashing", Decimal("3.00"), Decimal("18.50")),
        ("1-1/4\" Coil Roofing Nails — Box", Decimal("4.00"), Decimal("42.00")),
        ("Ridge Vent — 4 ft sections", Decimal("12.00"), Decimal("14.75")),
        ("Tear-Off Existing Roof (per square)", Decimal("34.00"), Decimal("45.00")),
        ("Dumpster Rental — 20 yd", Decimal("1.00"), Decimal("475.00")),
        ("Labor — Roofing Installation (per sq)", Decimal("34.00"), Decimal("175.00")),
    ]

    est1_subtotal = sum(qty * price for desc, qty, price in est1_items)
    est1_tax = (est1_subtotal * Decimal("0.07")).quantize(Decimal("0.01"))
    est1_total = est1_subtotal + est1_tax

    estimate1 = Estimate(
        job_id=jobs[2].id,
        name="Full Reroof — IKO Cambridge Dual Grey",
        tax_rate=Decimal("0.0700"),
        subtotal=est1_subtotal,
        tax=est1_tax,
        total=est1_total,
    )
    db.add(estimate1)
    db.flush()

    for i, (desc, qty, unit_price) in enumerate(est1_items, start=1):
        db.add(EstimateLineItem(
            estimate_id=estimate1.id,
            description=desc,
            qty=qty,
            unit_price=unit_price,
            line_total=(qty * unit_price).quantize(Decimal("0.01")),
            sort_order=i,
        ))

    # --- Estimate 2: Carmichael insurance reroof (job 4, Jobs / Scheduled) ---
    est2_items = [
        ("IKO Dynasty AR Shingles — Sedona", Decimal("38.00"), Decimal("148.00")),
        ("IKO Hip & Ridge Cap Shingles", Decimal("6.00"), Decimal("68.75")),
        ("IKO Leading Edge Plus Starter Strip", Decimal("9.00"), Decimal("52.00")),
        ("Synthetic Underlayment — Tiger Paw", Decimal("8.00"), Decimal("89.00")),
        ("Ice & Water Shield (eaves + valleys)", Decimal("5.00"), Decimal("112.00")),
        ("Aluminum Drip Edge — 10 ft", Decimal("30.00"), Decimal("8.50")),
        ("Step Flashing — Aluminum", Decimal("24.00"), Decimal("3.25")),
        ("Pipe Boot Flashing", Decimal("4.00"), Decimal("18.50")),
        ("1-1/4\" Coil Roofing Nails — Box", Decimal("5.00"), Decimal("42.00")),
        ("Ridge Vent — 4 ft sections", Decimal("14.00"), Decimal("14.75")),
        ("Tear-Off Existing Roof (per square)", Decimal("38.00"), Decimal("45.00")),
        ("Dumpster Rental — 20 yd", Decimal("1.00"), Decimal("475.00")),
        ("Labor — Roofing Installation (per sq)", Decimal("38.00"), Decimal("195.00")),
        ("Seamless Gutter — 5\" Aluminum (LF)", Decimal("185.00"), Decimal("9.50")),
        ("Downspout — 3x4 Aluminum (LF)", Decimal("48.00"), Decimal("7.25")),
    ]

    est2_subtotal = sum(qty * price for desc, qty, price in est2_items)
    est2_tax = (est2_subtotal * Decimal("0.07")).quantize(Decimal("0.01"))
    est2_total = est2_subtotal + est2_tax

    estimate2 = Estimate(
        job_id=jobs[3].id,
        name="Storm Damage Reroof + Gutters — IKO Dynasty Sedona",
        tax_rate=Decimal("0.0700"),
        subtotal=est2_subtotal,
        tax=est2_tax,
        total=est2_total,
    )
    db.add(estimate2)
    db.flush()

    for i, (desc, qty, unit_price) in enumerate(est2_items, start=1):
        db.add(EstimateLineItem(
            estimate_id=estimate2.id,
            description=desc,
            qty=qty,
            unit_price=unit_price,
            line_total=(qty * unit_price).quantize(Decimal("0.01")),
            sort_order=i,
        ))

    print(f"  Created 2 estimates ({len(est1_items)} + {len(est2_items)} line items)")

    # =====================================================================
    # TASKS — 4 tasks with varying due dates, assigned to employees
    # =====================================================================
    tasks = [
        # Overdue — was due 3 days ago, assigned to Sarah
        Task(
            job_id=jobs[1].id,
            title="Upload adjuster photos from Whitaker inspection",
            status="open",
            due_date=today - timedelta(days=3),
            assigned_to_user_id=employees["sarah"].id,
            related_entity_type="contact",
            related_entity_id=contacts[1].id,
        ),
        # Due today, assigned to admin (Dale)
        Task(
            job_id=jobs[2].id,
            title="Follow up with Doug Pennington on estimate approval",
            status="open",
            due_date=today,
            assigned_to_user_id=admin_id,
            related_entity_type="job",
            related_entity_id=jobs[2].id,
        ),
        # Due this week, assigned to Logan
        Task(
            job_id=jobs[3].id,
            title="Order IKO Dynasty Sedona from ABC Supply — 38 sq",
            status="open",
            due_date=today + timedelta(days=3),
            assigned_to_user_id=employees["logan"].id,
        ),
        # Future, assigned to Bri
        Task(
            job_id=jobs[3].id,
            title="Schedule crew for Carmichael reroof — week of 3/2",
            status="open",
            due_date=today + timedelta(days=11),
            assigned_to_user_id=employees["bri"].id,
            related_entity_type="job",
            related_entity_id=jobs[3].id,
        ),
    ]
    db.add_all(tasks)

    print(f"  Created {len(tasks)} tasks")

    # =====================================================================
    # APPOINTMENTS — 4 sample appointments
    # =====================================================================
    appointments = [
        Appointment(
            title="Roof inspection — Hargrove",
            contact_id=contacts[0].id,
            assigned_to_user_id=admin_id,
            appointment_date=today + timedelta(days=1),
            appointment_time=time(9, 0),
            duration_minutes=60,
            location="2341 W Thornapple St, Kokomo, IN 46901",
            appointment_type="inspection",
            created_by_user_id=admin_id,
        ),
        Appointment(
            title="Follow-up call — Whitaker insurance",
            contact_id=contacts[1].id,
            assigned_to_user_id=employees["sarah"].id,
            appointment_date=today + timedelta(days=2),
            appointment_time=time(14, 0),
            duration_minutes=30,
            location=None,
            notes="Discuss adjuster findings, next steps for claim.",
            appointment_type="follow_up",
            created_by_user_id=admin_id,
        ),
        Appointment(
            title="Quote presentation — Pennington",
            contact_id=contacts[2].id,
            assigned_to_user_id=admin_id,
            appointment_date=today + timedelta(days=3),
            appointment_time=time(10, 30),
            duration_minutes=90,
            location="1420 E Harrowgate St, Kokomo, IN 46902",
            appointment_type="quote",
            created_by_user_id=admin_id,
        ),
        Appointment(
            title="Final walkthrough — Eastman repair",
            contact_id=contacts[4].id,
            assigned_to_user_id=employees["logan"].id,
            appointment_date=today + timedelta(days=5),
            appointment_time=time(8, 0),
            duration_minutes=60,
            location="780 E Bramblewood St, Kokomo, IN 46901",
            appointment_type="inspection",
            created_by_user_id=admin_id,
        ),
    ]
    db.add_all(appointments)

    print(f"  Created {len(appointments)} appointments")

    # =====================================================================
    # DOCUMENTS — 2 uploaded document references
    # =====================================================================
    documents = [
        Document(
            job_id=jobs[3].id,
            filename="carmichael_hover_report_a1b2c3.pdf",
            original_filename="Carmichael_3100_Quillmont_Hover_Report.pdf",
            content_type="application/pdf",
            file_size=2_845_000,
        ),
        Document(
            job_id=jobs[1].id,
            filename="whitaker_insurance_scope_d4e5f6.pdf",
            original_filename="Whitaker_805_Wrenfield_StateFarm_Scope.pdf",
            content_type="application/pdf",
            file_size=1_230_000,
        ),
    ]
    db.add_all(documents)

    print(f"  Created {len(documents)} documents")

    # -- Commit everything --
    db.commit()
    print("\nDemo data seeded successfully!")
    print(f"  Estimate 1 total: ${est1_total:,.2f}")
    print(f"  Estimate 2 total: ${est2_total:,.2f}")


if __name__ == "__main__":
    print("Seeding Legacy CRM demo data...\n")
    db = SessionLocal()
    try:
        seed_employees_and_crews(db)
        seed(db)
    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        sys.exit(1)
    finally:
        db.close()
