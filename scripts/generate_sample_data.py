"""Generate synthetic AccuLynx-style exports for Legacy CRM.

The production system was migrated off AccuLynx using four CSV exports
(Contacts, Jobs, Invoices, A/R Age). Those exports held a real business's
customers, so they never ship. This script writes stand-ins with the same
column layout, the same messiness the importer had to handle (mixed phone
formats, placeholder emails, ZIP+4, "1088: First  Last" job names), and a
pipeline shape modeled on the real one. Every person, phone number, street
and dollar figure below is invented:

  * names are random pairings from common-name lists
  * phone numbers use the 555-01XX block, reserved for fiction
  * streets are made-up names; towns are real places near the business
  * emails use the reserved example.com / example.net / example.org domains

Deterministic: the same seed always produces the same files.

Usage:
    python scripts/generate_sample_data.py            # writes data/sample/
    python scripts/generate_sample_data.py --seed 7   # different but stable set

Then load it through the real importer (see README, "Run it yourself"):
    cd backend && python scripts/import_acculynx_v2.py \
        --contacts ../data/sample/contacts_report.csv \
        --jobs ../data/sample/jobs_report.csv \
        --invoices ../data/sample/invoice_report.csv \
        --ar-age ../data/sample/ar_age_report.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import uuid
from datetime import date, timedelta

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "sample")

FIRST = """James Mary Robert Linda Michael Barbara William Susan David Karen Richard Nancy Joseph
Lisa Thomas Betty Charles Sandra Daniel Ashley Matthew Kimberly Anthony Donna Mark Carol Steven
Michelle Paul Emily Andrew Amanda Joshua Melissa Kevin Deborah Brian Stephanie Gary Rebecca Eric
Laura Ryan Sharon Jacob Cynthia Nicholas Kathleen Tyler Amy Brandon Angela Travis Heather Dustin
Brittany Cody Megan Wade Tonya Dale Shelby Corey Kayla Brent Jodie Clint Tasha""".split()
LAST = """Abbott Ainsley Barlow Beckett Brannigan Calloway Carver Chandler Colby Corwin Dalton Delaney
Easton Ellery Fairchild Fenwick Garrity Gilmore Halvorsen Hargrove Holloway Ingram Jessup
Keller Kinsley Lachlan Langford Marlowe Merrick Nolan Oakley Orton Pemberton Prewitt Quinlan
Radford Rainey Sayer Sheffield Stoddard Talbot Thackeray Upton Vance Wainwright Whitcomb
Yardley Ziegler Bramwell Crandall Dorsey Ebbert Fulton Granger Hadley Kimball Lockhart Mayfield
Norwood Pruett Rowntree Selby Tindall Vickers Winslow""".split()
STREET = """Larkspur Thornapple Wrenfield Harrowgate Quillmont Bramblewood Fernhollow Copperleaf
Ashgrove Kestrel Millbrook Stonecrest Willowmere Foxglove Heathridge Sablewood Juniper Ridge
Bellhaven Cobblestone Tamarack Linden Hollow Ravenwood Briarcliff Meadowlark Silverbirch""".split()
SUFFIX = ["Drive", "Lane", "Court", "Street", "Way", "Road", "Trail", "Circle"]
TOWNS = [  # real towns around the service area, weighted toward the home base
    ("Kokomo", "46901"), ("Kokomo", "46902"), ("Kokomo", "46901"), ("Kokomo", "46902"),
    ("Greentown", "46936"), ("Russiaville", "46979"), ("Galveston", "46932"),
    ("Tipton", "46072"), ("Peru", "46970"), ("Marion", "46952"), ("Logansport", "46947"),
]
AREA_CODES = ["765", "765", "765", "317", "574", "260"]
EMAIL_DOMAINS = ["example.com", "example.net", "example.org"]
PLACEHOLDER_EMAILS = ["na@example.com", "getlater@example.com"]  # importer must not dedup on these

# Lead-source mix modeled on the real export: one paid channel dominates.
LEAD_SOURCES = (["Google LSA"] * 40 + ["Self Generated"] * 10 + ["Other"] * 8 + ["Referral"] * 7
                + ["Facebook"] * 2 + ["Word of Mouth"] * 2 + ["Yard Sign", "Realtor", "Property Manager"])
SALESPEOPLE = ["Dale Brennan"] * 2 + ["Reid Callahan"]
# Pipeline shape: mostly early-stage, a working tail of approved and invoiced jobs.
MILESTONES = (["Prospect"] * 40 + ["Assigned Lead"] * 14 + ["Approved"] * 8 + ["Completed"] * 3
              + ["Invoiced"] * 5 + ["Closed"] * 2)
TODAY = date(2026, 5, 15)


def d(dt: date) -> str:
    return f"{dt.month}/{dt.day}/{dt.strftime('%y')}"


def dt_ampm(dt: date) -> str:
    return f"{d(dt)} 12:00 AM"


class Phones:
    """Hands out unique numbers from the fictional 555-0100..0199 block."""

    def __init__(self, rng: random.Random):
        self.pool = [(ac, n) for ac in sorted(set(AREA_CODES)) for n in range(100, 200)]
        rng.shuffle(self.pool)
        weights = {ac: AREA_CODES.count(ac) for ac in set(AREA_CODES)}
        self.pool.sort(key=lambda p: -weights[p[0]] * rng.random())

    def next(self, rng: random.Random) -> str:
        ac, n = self.pool.pop()
        digits = f"{ac}5550{n:03d}"[:10]
        if rng.random() < 0.15:  # AccuLynx stored some numbers unformatted
            return digits
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def make_contacts(rng: random.Random, n: int):
    phones = Phones(rng)
    used = set()
    contacts = []
    for i in range(n):
        while True:
            first, last = rng.choice(FIRST), rng.choice(LAST)
            if (first, last) not in used:
                used.add((first, last))
                break
        town, zip_code = rng.choice(TOWNS)
        if rng.random() < 0.08:
            zip_code = f"{zip_code}-{rng.randint(1000, 9999)}"
        street = f"{rng.randint(100, 9899)} {rng.choice(STREET)} {rng.choice(SUFFIX)}"
        address = f"{street}, {town}, IN {zip_code} US"
        roll = rng.random()
        if roll < 0.06:
            email = ""
        elif roll < 0.09:
            email = rng.choice(PLACEHOLDER_EMAILS)
        else:
            email = f"{first.lower()}.{last.lower()}@{rng.choice(EMAIL_DOMAINS)}"
        created = TODAY - timedelta(days=rng.randint(0, 130))
        contacts.append({
            "first": first, "last": last, "address": address if rng.random() > 0.01 else "",
            "phone": phones.next(rng), "email": email, "created": created,
            "uid": uuid.UUID(int=rng.getrandbits(128)),
        })
    return contacts


def make_jobs(rng: random.Random, contacts):
    jobs = []
    picks = rng.sample(contacts, len(MILESTONES))
    for k, (milestone, c) in enumerate(zip(rng.sample(MILESTONES, len(MILESTONES)), picks)):
        number = 1001 + k * 2 + rng.randint(0, 1)
        lead_date = c["created"] + timedelta(days=rng.randint(0, 3))
        row = {
            "number": number, "contact": c, "milestone": milestone,
            "lead_source": rng.choice(LEAD_SOURCES), "salesperson": rng.choice(SALESPEOPLE),
            "lead_date": lead_date, "prospect_date": None, "approved": None,
            "completed": None, "invoiced": None, "closed": None, "total": 0.0,
            "uid": uuid.UUID(int=rng.getrandbits(128)),
        }
        if milestone != "Assigned Lead":
            row["prospect_date"] = lead_date + timedelta(days=rng.randint(1, 6))
        stage = ["Approved", "Completed", "Invoiced", "Closed"]
        if milestone in stage:
            row["total"] = round(rng.choice([
                rng.uniform(180, 600),      # small repairs
                rng.uniform(1100, 4800),    # gutters, partial work
                rng.uniform(7500, 26000),   # full replacements
                rng.uniform(7500, 26000),
            ]), 2)
            row["approved"] = row["prospect_date"] + timedelta(days=rng.randint(3, 20))
            idx = stage.index(milestone)
            if idx >= 1:
                row["completed"] = row["approved"] + timedelta(days=rng.randint(5, 25))
            if idx >= 2:
                row["invoiced"] = row["completed"]
            if idx >= 3:
                row["closed"] = row["invoiced"] + timedelta(days=rng.randint(5, 30))
        jobs.append(row)
    return jobs


def make_invoices(rng: random.Random, jobs):
    invoices = []
    for j in jobs:
        if j["milestone"] not in ("Approved", "Completed", "Invoiced", "Closed"):
            continue
        total = j["total"]
        # Deposit invoice on most approved work, then a final invoice once complete.
        parts = []
        if total > 1000 and rng.random() < 0.8:
            deposit = round(total * rng.choice([0.3, 0.4, 0.5]), 2)
            parts.append(("deposit", deposit, j["approved"]))
            if j["completed"]:
                parts.append(("final", round(total - deposit, 2), j["completed"]))
        else:
            parts.append(("full", total, j["completed"] or j["approved"]))
        for seq, (kind, amount, inv_date) in enumerate(parts, start=1):
            if j["milestone"] == "Closed" or (kind == "deposit" and j["milestone"] != "Approved"):
                status, balance = "Paid", 0.0
            elif j["milestone"] == "Approved" and rng.random() < 0.25:
                status, balance = "Draft", amount
            else:
                paid = rng.random() < 0.35
                status, balance = ("Paid", 0.0) if paid else ("Unpaid", amount)
            invoices.append({
                "number": f"{j['number']}-{seq}", "job": j, "amount": amount,
                "balance": balance, "status": status, "date": inv_date,
                "age": (TODAY - inv_date).days if status != "Draft" else "",
            })
    return invoices


def write(name, header, rows):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"wrote {len(rows):4d} rows  data/sample/{name}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=20260515)
    ap.add_argument("--contacts", type=int, default=220)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    os.makedirs(OUT_DIR, exist_ok=True)

    contacts = make_contacts(rng, args.contacts)
    jobs = make_jobs(rng, contacts)
    invoices = make_invoices(rng, jobs)
    ltv = {}
    for inv in invoices:
        c = inv["job"]["contact"]
        if inv["status"] == "Paid":
            ltv[id(c)] = ltv.get(id(c), 0.0) + inv["amount"]

    base = "https://my.acculynx.example"
    write("contacts_report.csv",
          ["Contact: First Name", "Contact: Last Name", "Contact: Types", "Contact: LTV",
           "Contact: Mailing Address", "Contact: Phone", "Contact: Email", "Contact: Created Date",
           "Contact: First Name Url", "Contact: Last Name Url"],
          [[c["first"], c["last"], "Customer", f"{ltv.get(id(c), 0.0):.2f}", c["address"],
            c["phone"], c["email"], d(c["created"]),
            f"{base}/contacts/{c['uid']}", f"{base}/contacts/{c['uid']}"] for c in contacts])

    def name(c):  # AccuLynx job names carry a double space now and then
        return f"{c['first']}{'  ' if rng.random() < 0.2 else ' '}{c['last']}"

    write("jobs_report.csv",
          ["Current Milestone", "Job Name", "Contact Name", "Contact Email", "Phone Number",
           "Location Address", "Lead Source", "Contract Total", "Primary Salesperson",
           "Lead Date", "Prospect Date", "Approved Date", "Completed Date", "Invoiced Date",
           "Closed Date", "Job Name Url"],
          [[j["milestone"], f"{j['number']}: {name(j['contact'])}",
            f"{j['contact']['first']} {j['contact']['last']}", j["contact"]["email"],
            j["contact"]["phone"], j["contact"]["address"], j["lead_source"], f"{j['total']:.2f}",
            j["salesperson"], d(j["lead_date"]),
            *[d(x) if x else "" for x in (j["prospect_date"], j["approved"], j["completed"],
                                          j["invoiced"], j["closed"])],
            f"{base}/jobs/{j['uid']}"] for j in jobs])

    write("invoice_report.csv",
          ["Invoice Number", "Invoice Total", "Invoice Balance Due", "Invoice Date",
           "A/R Age (Invoice Age)", "Invoice Status", "Last Recorded Date", "Primary Salesperson",
           "A/R Owner", "Approved Job Value", "Balance Due", "Current Milestone", "Phone Number",
           "Location Address", "Invoice Created Date", "Invoice Number Url"],
          [[i["number"], f"{i['amount']:.2f}", f"{i['balance']:.2f}",
            dt_ampm(i["date"]) if i["status"] != "Draft" else "", i["age"], i["status"], "",
            i["job"]["salesperson"], i["job"]["salesperson"], f"{i['job']['total']:.2f}",
            f"{sum(x['balance'] for x in invoices if x['job'] is i['job']):.2f}",
            i["job"]["milestone"], i["job"]["contact"]["phone"], i["job"]["contact"]["address"],
            dt_ampm(i["date"]), f"{base}/jobs/{i['job']['uid']}/worksheet/invoices"]
           for i in invoices])

    unpaid = [i for i in invoices if i["status"] == "Unpaid"]
    write("ar_age_report.csv",
          ["Job Name", "A/R Age", "Invoice Number", "Invoice Total", "Invoice Balance Due",
           "Invoice Date", "Primary Salesperson", "A/R Owner", "Approve Job Value", "Balance Due",
           "Current Milestone", "Phone Number", "Location Address", "Job Name Url",
           "Invoice Number Url"],
          [[f"{i['job']['number']}: {name(i['job']['contact'])}", i["age"], i["number"],
            f"{i['amount']:.2f}", f"{i['balance']:.2f}", dt_ampm(i["date"]),
            i["job"]["salesperson"], i["job"]["salesperson"], f"{i['job']['total']:.2f}",
            f"{i['balance']:.2f}", i["job"]["milestone"], i["job"]["contact"]["phone"],
            i["job"]["contact"]["address"], f"{base}/jobs/{i['job']['uid']}",
            f"{base}/jobs/{i['job']['uid']}/worksheet/invoices"] for i in unpaid])


if __name__ == "__main__":
    main()
