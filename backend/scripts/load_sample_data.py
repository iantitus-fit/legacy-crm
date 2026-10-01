"""Load the synthetic sample data through the real AccuLynx importer.

Runs the same import path that moved the production business off AccuLynx,
pointed at data/sample/ instead of the client's exports.

    # with Docker (Postgres, the way production ran)
    docker compose up -d
    docker compose exec -e ADMIN_PASSWORD=pick-one backend python scripts/load_sample_data.py

    # without Docker (throwaway SQLite file, fastest way to look around)
    cd backend
    DATABASE_URL=sqlite:///./demo.db ADMIN_PASSWORD=pick-one python scripts/load_sample_data.py

What it does, in order:
  1. If the database is empty, creates the tables and the default pipelines.
  2. Makes sure an admin user exists (ADMIN_EMAIL / ADMIN_PASSWORD from the env).
  3. Adds the Sales stage "Estimate Pending Schedule". The owner created it in
     production through Settings > Pipelines; the importer maps AccuLynx
     "Prospect" jobs into it and refuses to run without it.
  4. Loads the supplier price lists (synthetic prices) if the materials table is empty.
  5. Runs scripts/import_acculynx_v2.py against data/sample/*.csv.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, HERE)

import app.models as models_pkg  # noqa: E402
from sqlalchemy import inspect  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models.material import Material  # noqa: E402
from app.models.pipeline import Pipeline  # noqa: E402
from app.models.pipeline_stage import PipelineStage  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.material_import import import_materials_csv  # noqa: E402
from app.services.pipeline_seed import seed_pipelines  # noqa: E402
from app.utils.auth import hash_password  # noqa: E402

for mod in pkgutil.iter_modules(models_pkg.__path__):
    importlib.import_module(f"app.models.{mod.name}")


def main() -> None:
    if not inspect(engine).has_table("pipelines"):
        Base.metadata.create_all(engine)
        print("created tables")
    db = SessionLocal()
    try:
        seed_pipelines(db)

        email = os.environ.get("ADMIN_EMAIL", "dale@legacy-roofing.example")
        if not db.query(User).filter(User.role == "admin").first():
            password = os.environ.get("ADMIN_PASSWORD")
            if not password:
                sys.exit("No admin user yet. Set ADMIN_PASSWORD (and optionally ADMIN_EMAIL).")
            db.add(User(email=email, full_name="Dale Brennan",
                        password_hash=hash_password(password), role="admin"))
            db.commit()
            print(f"created admin user {email}")

        sales = db.query(Pipeline).filter(Pipeline.slug == "sales").one()
        stage_name = "Estimate Pending Schedule"
        if not db.query(PipelineStage).filter_by(pipeline_id=sales.id, name=stage_name).first():
            last = max((s.sort_order for s in db.query(PipelineStage).filter_by(pipeline_id=sales.id)), default=0)
            db.add(PipelineStage(pipeline_id=sales.id, name=stage_name, sort_order=last + 1, color="#14B8A6"))
            db.commit()
            print(f"added sales stage '{stage_name}'")

        if not db.query(Material).first():
            for candidate in (os.path.join(BACKEND_DIR, "..", "data", "materials_master.csv"),
                              os.path.join(BACKEND_DIR, "materials_master.csv")):
                if os.path.exists(candidate):
                    result = import_materials_csv(db, candidate, source_file="materials_master.csv")
                    print(f"loaded {result['materials_imported']} materials from {os.path.basename(candidate)}")
                    break
    finally:
        db.close()

    import import_acculynx_v2  # noqa: E402

    sys.argv = [sys.argv[0], "--import-user", email, *sys.argv[1:]]
    import_acculynx_v2.main()


if __name__ == "__main__":
    main()
