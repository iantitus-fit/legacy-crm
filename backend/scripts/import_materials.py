"""CLI script to import materials from a CSV file.

Usage: cd backend && python -m scripts.import_materials ../data/materials_master.csv
"""
import sys
from pathlib import Path

# Add backend to path so app imports work
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.services.material_import import import_materials_csv


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.import_materials <csv_path>")
        sys.exit(1)

    csv_path = sys.argv[1]
    if not Path(csv_path).exists():
        print(f"File not found: {csv_path}")
        sys.exit(1)

    db = SessionLocal()
    try:
        print(f"Importing from {csv_path}...")
        result = import_materials_csv(
            db,
            csv_path,
            source_file=Path(csv_path).name,
        )
        print(f"Price lists created: {result['price_lists_created']}")
        print(f"Materials imported: {result['materials_imported']}")
        if result["errors"]:
            print(f"Errors ({len(result['errors'])}):")
            for err in result["errors"][:20]:
                print(f"  - {err}")
            if len(result["errors"]) > 20:
                print(f"  ... and {len(result['errors']) - 20} more")
    finally:
        db.close()


if __name__ == "__main__":
    main()
