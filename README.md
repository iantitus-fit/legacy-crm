# Legacy CRM

A CRM I built for a two-person roofing and exteriors company in Kokomo, Indiana, to replace two
subscriptions, AccuLynx and DripJobs, that cost the owner $835 a month and did not share data with
each other. It was deployed on Azure with the business's real data from April to August 2026, then
taken down to stop the hosting bill while the owner decides. A backup can bring it back. He has not
run his business on it yet, and the case study is honest about why.

The case study, with the business side of the story, is at
[iantitus.com/work/legacy-crm](https://iantitus.com/work/legacy-crm).

## How I built it

I am not a traditional programmer. I have no computer science degree and I do not write complex
logic from a blank file. I built this with Claude Code as my pair programmer, over about twenty
sprints and roughly ten hours of build time.

My part was the part that decides whether software works for a business. I sat with the owner and
learned how he prices a roof. I wrote a spec for every sprint (they are in `docs/`). I set the rules
the code had to follow (`CLAUDE.md`). I made the calls on the data model, read what came back, ran
the tests, and sent work back when it was wrong.

I did not type every line. I directed all of it, from the first spec to the Azure deployment, and
you can check that without taking my word for it.

## Check it yourself

Pick whichever fits how you work.

**Point your AI agent at it.** Open the repo in Claude Code, Cursor, or similar and tell it to start
at `map/CLAUDE.md`. That is a system map of the money path (estimate, change order, invoice,
payment). Each card says what a piece of the system is, where it lives in the code, and what else
moves if you change it. A cold agent can answer "what breaks if I touch invoices" in two files
instead of reading the whole codebase.

**Run the tests.** There are 952 automated tests. They take about 7 minutes. You need Python 3.12
or 3.13.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

The suite uses an in-memory database, so it needs no setup beyond the install. The PDF tests need
WeasyPrint's system libraries (on a Mac: `brew install pango`).

**Run the app with sample data.** You need Docker.

```bash
docker compose up -d
docker compose exec -e ADMIN_PASSWORD=pick-a-password backend python scripts/load_sample_data.py
```

Then open http://localhost:5173 and sign in as `dale@legacy-roofing.example` with the password you
picked. The loader runs the same importer that loaded the business's real AccuLynx data, pointed at
synthetic exports, so the pipelines, estimates, invoices and the 1,550-item materials library all
have something in them.

No Docker? This works too, using a throwaway SQLite file:

```bash
cd backend
DATABASE_URL=sqlite:///./demo.db ADMIN_PASSWORD=pick-a-password python scripts/load_sample_data.py
```

## What is real and what is not

The code is the code that was deployed, with one difference: anything that identified a
person or the business's accounts was replaced.

- **Real:** every model, route, calculation, test, migration, and sprint spec.
- **Synthetic:** customer names, phone numbers, addresses, emails, invoice amounts, and supplier
  prices. The owner and his operations lead appear as Dale and Marcus. See `data/README.md` for how
  the sample data was generated.
- **Removed:** the real AccuLynx exports, database backups, deployment URLs, and credentials. The
  git history starts fresh for the same reason.

## What it does

- Three pipelines on drag-and-drop boards: Leads, Sales, Jobs
- Estimates with sections, rich-text line items, and per-estimate tax handling (roofing adds tax,
  painting includes it)
- A pricing engine for roofs: measurements in, then waste, rounding up to whole units, and margin
- A materials library of 1,550 items OCR'd from scanned supplier price lists, with uncertain rows
  flagged for review
- Branded PDFs and a no-login customer portal where homeowners view, sign, reject, or ask for changes
- Change orders with their own portal and signature
- Deposit and final invoices, payment recording, automatic paid and partial status, emailed receipts
- Crew and employee management, calendars, notes, document uploads
- SMS through Twilio with automated follow-up sequences, lead source reporting, and a daily
  morning briefing email

## What the map found, and what I did about it

Building the system map meant checking every claim against the code, and that turned up nine
problems the tests had not caught. Two of them touched money. A homeowner who signed through the
portal never landed on the Jobs board the way an internal approval did, and a final invoice billed
the whole job even when a deposit invoice had already gone out.

All nine are fixed. The backend fixes come with 20 new tests, and 16 of them fail if you run them
against the code as it was before. `map/VERIFICATION.md` keeps the record: what was wrong, what
changed, and which part of the map describes it now.

## Layout

| Path | What is there |
|---|---|
| `backend/` | FastAPI app, SQLAlchemy models, Alembic migrations, tests |
| `frontend/` | React app (Vite, Tailwind) |
| `map/` | System map of the money path. Start at `map/CLAUDE.md` |
| `docs/` | Sprint specs and implementation plans, written before each build |
| `data/` | Synthetic sample exports and supplier price lists |
| `scripts/` | Sample data generator and deployment scripts |
| `CLAUDE.md` | The rules every AI coding session in this repo had to follow |

## Stack

Python 3.12 or 3.13, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, React 18, Vite, Tailwind CSS,
WeasyPrint for PDFs, Twilio for SMS, Docker. Production ran on Azure App Service with Azure
Database for PostgreSQL.
