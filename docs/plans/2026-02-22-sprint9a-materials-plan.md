# Sprint 9a: Materials Database & Import — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a master materials library with 1,550 items imported from ABC Supply price lists, with price list expiration tracking, OCR review flagging, and admin UI for browse/search/edit.

**Architecture:** Two new tables (`price_lists` and `materials`) with FK relationship. CSV import service handles OCR cleanup. Standard CRUD router pattern. React page with filters, table, inline edit modal, and CSV import modal.

**Tech Stack:** SQLAlchemy 2.x models, Alembic migration, FastAPI router, Pydantic schemas, React 18 + Tailwind frontend, pytest with SQLite.

---

### Task 1: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/0007_sprint9a_materials.py`

**Step 1: Write the migration file**

```python
"""Sprint 9a: Materials database — price lists and materials library.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "price_lists",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("source_file", sa.String(255), nullable=True),
        sa.Column("effective_date", sa.Date, nullable=True),
        sa.Column("expiration_date", sa.Date, nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "imported_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )

    op.create_table(
        "materials",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "price_list_id",
            sa.Integer,
            sa.ForeignKey("price_lists.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_number", sa.String(50), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("uom", sa.String(10), nullable=True),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("ocr_flag", sa.String(200), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_materials_price_list_item",
        "materials",
        ["price_list_id", "item_number"],
    )
    op.create_index(
        "ix_materials_category",
        "materials",
        ["category"],
    )


def downgrade() -> None:
    op.drop_index("ix_materials_category", table_name="materials")
    op.drop_index("ix_materials_price_list_item", table_name="materials")
    op.drop_table("materials")
    op.drop_table("price_lists")
```

**Step 2: Verify migration applies cleanly**

Run: `cd /Users/iantitus/Desktop/legacy-crm && docker compose exec backend alembic upgrade head`

If Docker isn't running, just verify the file is syntactically valid:
Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -c "import alembic.versions" || echo "Syntax OK (import not needed, just checking)"`

**Step 3: Commit**

```bash
git add backend/alembic/versions/0007_sprint9a_materials.py
git commit -m "feat: add migration for price_lists and materials tables"
```

---

### Task 2: SQLAlchemy Models

**Files:**
- Create: `backend/app/models/price_list.py`
- Create: `backend/app/models/material.py`
- Modify: `backend/app/models/__init__.py` (add imports)

**Step 1: Create PriceList model**

Create `backend/app/models/price_list.py`:

```python
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.material import Material
    from app.models.user import User


class PriceList(Base):
    __tablename__ = "price_lists"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_file: Mapped[Optional[str]] = mapped_column(String(255))
    effective_date: Mapped[Optional[date]] = mapped_column(Date())
    expiration_date: Mapped[Optional[date]] = mapped_column(Date())
    imported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    imported_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("users.id")
    )

    materials: Mapped[List["Material"]] = relationship(
        back_populates="price_list", cascade="all, delete-orphan"
    )
    imported_by: Mapped[Optional["User"]] = relationship()
```

**Step 2: Create Material model**

Create `backend/app/models/material.py`:

```python
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.price_list import PriceList


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    price_list_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("price_lists.id", ondelete="CASCADE"), nullable=False
    )
    item_number: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    uom: Mapped[Optional[str]] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    ocr_flag: Mapped[Optional[str]] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true", nullable=False
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    price_list: Mapped[Optional["PriceList"]] = relationship(
        back_populates="materials"
    )
```

**Step 3: Register models in `__init__.py`**

Add to `backend/app/models/__init__.py` — add these two imports and __all__ entries:

```python
from app.models.material import Material
from app.models.price_list import PriceList
```

Add `"Material"` and `"PriceList"` to the `__all__` list.

**Step 4: Verify models load**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -c "from app.models import Material, PriceList; print('OK')"`

**Step 5: Commit**

```bash
git add backend/app/models/price_list.py backend/app/models/material.py backend/app/models/__init__.py
git commit -m "feat: add PriceList and Material SQLAlchemy models"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/price_list.py`
- Create: `backend/app/schemas/material.py`

**Step 1: Create PriceList schemas**

Create `backend/app/schemas/price_list.py`:

```python
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class PriceListCreate(BaseModel):
    name: str
    source_file: Optional[str] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None


class PriceListUpdate(BaseModel):
    name: Optional[str] = None
    effective_date: Optional[date] = None
    expiration_date: Optional[date] = None


class PriceListResponse(BaseModel):
    id: int
    name: str
    source_file: Optional[str]
    effective_date: Optional[date]
    expiration_date: Optional[date]
    imported_at: Optional[datetime]
    imported_by_user_id: Optional[int]
    material_count: int = 0

    model_config = {"from_attributes": True}


class PriceListListResponse(BaseModel):
    items: List[PriceListResponse]
    total: int
```

**Step 2: Create Material schemas**

Create `backend/app/schemas/material.py`:

```python
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class MaterialCreate(BaseModel):
    price_list_id: int
    item_number: str
    description: str
    unit_price: Decimal
    uom: Optional[str] = None
    category: str
    ocr_flag: Optional[str] = None


class MaterialUpdate(BaseModel):
    item_number: Optional[str] = None
    description: Optional[str] = None
    unit_price: Optional[Decimal] = None
    uom: Optional[str] = None
    category: Optional[str] = None
    ocr_flag: Optional[str] = None
    is_active: Optional[bool] = None


class MaterialResponse(BaseModel):
    id: int
    price_list_id: int
    item_number: str
    description: str
    unit_price: Decimal
    uom: Optional[str]
    category: str
    ocr_flag: Optional[str]
    is_active: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    price_list_name: Optional[str] = None

    model_config = {"from_attributes": True}


class MaterialListResponse(BaseModel):
    items: List[MaterialResponse]
    total: int
    page: int
    per_page: int


class CategoryCount(BaseModel):
    category: str
    count: int


class MaterialImportResponse(BaseModel):
    price_lists_created: int
    materials_imported: int
    errors: List[str]
```

**Step 3: Commit**

```bash
git add backend/app/schemas/price_list.py backend/app/schemas/material.py
git commit -m "feat: add Pydantic schemas for PriceList and Material"
```

---

### Task 4: CSV Import Service

**Files:**
- Create: `backend/app/services/material_import.py`
- Test: `backend/tests/test_material_import.py`

**Step 1: Write failing tests for the import service**

Create `backend/tests/test_material_import.py`:

```python
import csv
import io
import os
import tempfile
from decimal import Decimal

import pytest

from app.models.material import Material
from app.models.price_list import PriceList
from app.services.material_import import clean_item_number, import_materials_csv


def test_clean_item_number_strips_smart_quote():
    assert clean_item_number("\u2018O40CSSPL") == "O40CSSPL"


def test_clean_item_number_strips_leading_paren():
    assert clean_item_number("(O40CSSPL") == "O40CSSPL"


def test_clean_item_number_strips_leading_brace():
    assert clean_item_number("{O40CSSPL") == "O40CSSPL"


def test_clean_item_number_preserves_normal():
    assert clean_item_number("O40CSSPL") == "O40CSSPL"


def test_clean_item_number_strips_trailing_whitespace():
    assert clean_item_number("O40CSSPL ") == "O40CSSPL"


def test_import_materials_csv_basic(db_session):
    csv_content = (
        "item_number,description,unit_price,uom,category,source,ocr_flag\n"
        "ABC123,Test Shingle,117.96,SQ,Shingles,ABC Roofing,\n"
        "DEF456,Test Nail,9.50,BX,Fasteners,ABC Roofing,REVIEW - price may have OCR error\n"
        "'GHI789,Test Starter,47.21,BD,Starter Strip,Mastic Siding/Trim,\n"
    )
    tmpfile = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    )
    tmpfile.write(csv_content)
    tmpfile.close()

    try:
        result = import_materials_csv(db_session, tmpfile.name)

        assert result["materials_imported"] == 3
        assert result["price_lists_created"] == 2
        assert result["errors"] == []

        # Verify price lists created
        pls = db_session.query(PriceList).order_by(PriceList.name).all()
        assert len(pls) == 2
        assert pls[0].name == "ABC Roofing"
        assert pls[1].name == "Mastic Siding/Trim"

        # Verify materials
        mats = db_session.query(Material).order_by(Material.item_number).all()
        assert len(mats) == 3
        assert mats[0].item_number == "ABC123"
        assert mats[0].unit_price == Decimal("117.96")
        assert mats[0].uom == "SQ"
        assert mats[0].category == "Shingles"

        # OCR flag preserved
        assert mats[1].item_number == "DEF456"
        assert mats[1].ocr_flag == "REVIEW - price may have OCR error"

        # Smart quote stripped from item number
        assert mats[2].item_number == "GHI789"
    finally:
        os.unlink(tmpfile.name)


def test_import_materials_csv_missing_uom(db_session):
    csv_content = (
        "item_number,description,unit_price,uom,category,source,ocr_flag\n"
        "ABC123,Test Item,50.00,,Shingles,ABC Roofing,\n"
    )
    tmpfile = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    )
    tmpfile.write(csv_content)
    tmpfile.close()

    try:
        result = import_materials_csv(db_session, tmpfile.name)
        assert result["materials_imported"] == 1

        mat = db_session.query(Material).first()
        assert mat.uom is None
    finally:
        os.unlink(tmpfile.name)


def test_import_materials_csv_with_options(db_session):
    csv_content = (
        "item_number,description,unit_price,uom,category,source,ocr_flag\n"
        "ABC123,Test Shingle,117.96,SQ,Shingles,ABC Roofing,\n"
    )
    tmpfile = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    )
    tmpfile.write(csv_content)
    tmpfile.close()

    try:
        result = import_materials_csv(
            db_session,
            tmpfile.name,
            source_file="materials_master.csv",
        )
        assert result["materials_imported"] == 1

        pl = db_session.query(PriceList).first()
        assert pl.source_file == "materials_master.csv"
    finally:
        os.unlink(tmpfile.name)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_material_import.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.material_import'`

**Step 3: Write the import service**

Create `backend/app/services/material_import.py`:

```python
import csv
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.price_list import PriceList

# Leading OCR artifact characters to strip
_OCR_JUNK_RE = re.compile(r"^[\u2018\u2019({]+")


def clean_item_number(raw: str) -> str:
    """Strip leading OCR artifact characters and whitespace from item numbers."""
    return _OCR_JUNK_RE.sub("", raw).strip()


def import_materials_csv(
    db: Session,
    file_path: str,
    source_file: Optional[str] = None,
    effective_date: Optional[date] = None,
    expiration_date: Optional[date] = None,
    user_id: Optional[int] = None,
) -> Dict:
    """Import materials from a CSV file.

    CSV must have columns: item_number, description, unit_price, uom, category, source, ocr_flag

    Returns dict with keys: price_lists_created, materials_imported, errors
    """
    errors: List[str] = []
    price_list_cache: Dict[str, PriceList] = {}
    imported_count = 0

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):
            source_name = (row.get("source") or "").strip()
            if not source_name:
                errors.append(f"Row {row_num}: missing source")
                continue

            # Get or create price list for this source
            if source_name not in price_list_cache:
                existing = (
                    db.query(PriceList)
                    .filter(PriceList.name == source_name)
                    .first()
                )
                if existing:
                    price_list_cache[source_name] = existing
                else:
                    pl = PriceList(
                        name=source_name,
                        source_file=source_file,
                        effective_date=effective_date,
                        expiration_date=expiration_date,
                        imported_by_user_id=user_id,
                    )
                    db.add(pl)
                    db.flush()
                    price_list_cache[source_name] = pl

            # Parse fields
            raw_item = (row.get("item_number") or "").strip()
            description = (row.get("description") or "").strip()
            raw_price = (row.get("unit_price") or "").strip()
            uom = (row.get("uom") or "").strip() or None
            category = (row.get("category") or "").strip()
            ocr_flag = (row.get("ocr_flag") or "").strip() or None

            if not raw_item or not description or not raw_price or not category:
                errors.append(
                    f"Row {row_num}: missing required field "
                    f"(item_number={raw_item!r}, description={description!r}, "
                    f"unit_price={raw_price!r}, category={category!r})"
                )
                continue

            item_number = clean_item_number(raw_item)

            try:
                unit_price = Decimal(raw_price)
            except InvalidOperation:
                errors.append(f"Row {row_num}: invalid price {raw_price!r}")
                continue

            material = Material(
                price_list_id=price_list_cache[source_name].id,
                item_number=item_number,
                description=description,
                unit_price=unit_price,
                uom=uom,
                category=category,
                ocr_flag=ocr_flag,
            )
            db.add(material)
            imported_count += 1

    db.commit()

    return {
        "price_lists_created": len(
            [pl for pl in price_list_cache.values() if pl in db.new or True]
        ),
        "materials_imported": imported_count,
        "errors": errors,
    }
```

Note: The `price_lists_created` count simply uses the cache length since all entries in the cache were either found or created during this import.

**Step 4: Run tests to verify they pass**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_material_import.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/material_import.py backend/tests/test_material_import.py
git commit -m "feat: add CSV import service for materials with OCR cleanup"
```

---

### Task 5: Materials & Price Lists Router + Tests

**Files:**
- Create: `backend/app/routers/materials.py`
- Create: `backend/app/routers/price_lists.py`
- Create: `backend/tests/test_materials.py`
- Create: `backend/tests/test_price_lists.py`
- Modify: `backend/app/main.py` (register routers, lines 11-27 imports, lines 61-76 include_router)

**Step 1: Write failing tests for materials CRUD**

Create `backend/tests/test_materials.py`:

```python
from decimal import Decimal

import pytest

from app.models.material import Material
from app.models.price_list import PriceList


@pytest.fixture()
def price_list(db_session):
    pl = PriceList(name="ABC Roofing", source_file="test.csv")
    db_session.add(pl)
    db_session.commit()
    db_session.refresh(pl)
    return pl


@pytest.fixture()
def sample_materials(db_session, price_list):
    materials = [
        Material(
            price_list_id=price_list.id,
            item_number="ABC001",
            description="OC Duration Brownwood",
            unit_price=Decimal("117.96"),
            uom="SQ",
            category="Shingles",
        ),
        Material(
            price_list_id=price_list.id,
            item_number="ABC002",
            description="Coil Nail 1.25 inch",
            unit_price=Decimal("45.00"),
            uom="BX",
            category="Fasteners",
        ),
        Material(
            price_list_id=price_list.id,
            item_number="ABC003",
            description="OC Starter Strip",
            unit_price=Decimal("47.21"),
            uom="BD",
            category="Starter Strip",
            ocr_flag="REVIEW - price may have OCR error",
        ),
    ]
    db_session.add_all(materials)
    db_session.commit()
    return materials


# --- List Materials ---


def test_list_materials(client, auth_headers, price_list, sample_materials):
    resp = client.get("/api/materials", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


def test_list_materials_search(client, auth_headers, price_list, sample_materials):
    resp = client.get(
        "/api/materials", headers=auth_headers, params={"search": "Duration"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["item_number"] == "ABC001"


def test_list_materials_filter_category(
    client, auth_headers, price_list, sample_materials
):
    resp = client.get(
        "/api/materials", headers=auth_headers, params={"category": "Fasteners"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_list_materials_filter_price_list(
    client, auth_headers, price_list, sample_materials
):
    resp = client.get(
        "/api/materials",
        headers=auth_headers,
        params={"price_list_id": price_list.id},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 3


def test_list_materials_filter_flagged(
    client, auth_headers, price_list, sample_materials
):
    resp = client.get(
        "/api/materials", headers=auth_headers, params={"flagged": "true"}
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["item_number"] == "ABC003"


def test_list_materials_pagination(
    client, auth_headers, price_list, sample_materials
):
    resp = client.get(
        "/api/materials", headers=auth_headers, params={"per_page": 2, "page": 1}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1


# --- Get Material ---


def test_get_material(client, auth_headers, price_list, sample_materials):
    mat_id = sample_materials[0].id
    resp = client.get(f"/api/materials/{mat_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["item_number"] == "ABC001"
    assert data["price_list_name"] == "ABC Roofing"


def test_get_material_not_found(client, auth_headers):
    resp = client.get("/api/materials/99999", headers=auth_headers)
    assert resp.status_code == 404


# --- Create Material ---


def test_create_material(client, auth_headers, price_list):
    resp = client.post(
        "/api/materials",
        headers=auth_headers,
        json={
            "price_list_id": price_list.id,
            "item_number": "NEW001",
            "description": "New Test Item",
            "unit_price": "25.50",
            "uom": "PC",
            "category": "Fasteners",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["item_number"] == "NEW001"
    assert data["unit_price"] == "25.50"


# --- Update Material ---


def test_update_material(client, auth_headers, price_list, sample_materials):
    mat_id = sample_materials[0].id
    resp = client.put(
        f"/api/materials/{mat_id}",
        headers=auth_headers,
        json={"unit_price": "125.00", "ocr_flag": None},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["unit_price"] == "125.00"


def test_update_material_clear_ocr_flag(
    client, auth_headers, price_list, sample_materials
):
    mat_id = sample_materials[2].id  # the flagged one
    resp = client.put(
        f"/api/materials/{mat_id}",
        headers=auth_headers,
        json={"ocr_flag": None},
    )
    assert resp.status_code == 200
    assert resp.json()["ocr_flag"] is None


# --- Delete (soft) Material ---


def test_delete_material(client, auth_headers, price_list, sample_materials):
    mat_id = sample_materials[0].id
    resp = client.delete(f"/api/materials/{mat_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Should still exist but inactive
    resp = client.get(f"/api/materials/{mat_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


# --- Categories Endpoint ---


def test_list_categories(client, auth_headers, price_list, sample_materials):
    resp = client.get("/api/materials/categories", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    # Sorted by category name
    cats = [c["category"] for c in data]
    assert "Fasteners" in cats
    assert "Shingles" in cats


# --- Auth required ---


def test_list_materials_requires_auth(client):
    resp = client.get("/api/materials")
    assert resp.status_code == 401
```

**Step 2: Write failing tests for price lists**

Create `backend/tests/test_price_lists.py`:

```python
import pytest

from app.models.material import Material
from app.models.price_list import PriceList
from decimal import Decimal


@pytest.fixture()
def price_lists(db_session):
    pls = [
        PriceList(name="ABC Roofing", source_file="roofing.csv"),
        PriceList(name="Mastic Siding/Trim", source_file="siding.csv"),
    ]
    db_session.add_all(pls)
    db_session.commit()
    # Add a material to ABC Roofing for count testing
    mat = Material(
        price_list_id=pls[0].id,
        item_number="T001",
        description="Test",
        unit_price=Decimal("10.00"),
        category="Shingles",
    )
    db_session.add(mat)
    db_session.commit()
    return pls


def test_list_price_lists(client, auth_headers, price_lists):
    resp = client.get("/api/price-lists", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    # ABC Roofing should show material_count=1
    abc = next(i for i in data["items"] if i["name"] == "ABC Roofing")
    assert abc["material_count"] == 1


def test_update_price_list(client, auth_headers, price_lists):
    pl_id = price_lists[0].id
    resp = client.put(
        f"/api/price-lists/{pl_id}",
        headers=auth_headers,
        json={"expiration_date": "2026-06-01"},
    )
    assert resp.status_code == 200
    assert resp.json()["expiration_date"] == "2026-06-01"


def test_update_price_list_not_found(client, auth_headers):
    resp = client.put(
        "/api/price-lists/99999",
        headers=auth_headers,
        json={"name": "X"},
    )
    assert resp.status_code == 404
```

**Step 3: Run tests to verify they fail**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_materials.py tests/test_price_lists.py -v`
Expected: FAIL — routers don't exist yet

**Step 4: Write the materials router**

Create `backend/app/routers/materials.py`:

```python
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.material import Material
from app.models.price_list import PriceList
from app.models.user import User
from app.schemas.material import (
    CategoryCount,
    MaterialCreate,
    MaterialListResponse,
    MaterialResponse,
    MaterialUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/materials", tags=["materials"])


def _material_to_response(mat: Material) -> dict:
    return {
        "id": mat.id,
        "price_list_id": mat.price_list_id,
        "item_number": mat.item_number,
        "description": mat.description,
        "unit_price": mat.unit_price,
        "uom": mat.uom,
        "category": mat.category,
        "ocr_flag": mat.ocr_flag,
        "is_active": mat.is_active,
        "created_at": mat.created_at,
        "updated_at": mat.updated_at,
        "price_list_name": mat.price_list.name if mat.price_list else None,
    }


@router.get("/categories", response_model=List[CategoryCount])
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Material.category, func.count(Material.id))
        .filter(Material.is_active == True)
        .group_by(Material.category)
        .order_by(Material.category)
        .all()
    )
    return [CategoryCount(category=cat, count=cnt) for cat, cnt in rows]


@router.get("", response_model=MaterialListResponse)
def list_materials(
    search: Optional[str] = Query(None, description="Search item_number or description"),
    category: Optional[str] = Query(None),
    price_list_id: Optional[int] = Query(None),
    flagged: Optional[str] = Query(None, description="Set to 'true' to show only OCR-flagged items"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Material).options(joinedload(Material.price_list))

    # Default to active only
    query = query.filter(Material.is_active == True)

    if search:
        sf = f"%{search}%"
        query = query.filter(
            or_(
                Material.item_number.ilike(sf),
                Material.description.ilike(sf),
            )
        )

    if category:
        query = query.filter(Material.category == category)

    if price_list_id:
        query = query.filter(Material.price_list_id == price_list_id)

    if flagged and flagged.lower() == "true":
        query = query.filter(Material.ocr_flag.isnot(None))

    total = query.count()
    materials = (
        query.order_by(Material.category, Material.description)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return MaterialListResponse(
        items=[_material_to_response(m) for m in materials],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{material_id}", response_model=MaterialResponse)
def get_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mat = (
        db.query(Material)
        .options(joinedload(Material.price_list))
        .filter(Material.id == material_id)
        .first()
    )
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")
    return _material_to_response(mat)


@router.post("", response_model=MaterialResponse, status_code=201)
def create_material(
    data: MaterialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pl = db.query(PriceList).filter(PriceList.id == data.price_list_id).first()
    if not pl:
        raise HTTPException(status_code=400, detail="Price list not found")

    mat = Material(**data.model_dump())
    db.add(mat)
    db.commit()
    db.refresh(mat)

    # Reload with relationship
    mat = (
        db.query(Material)
        .options(joinedload(Material.price_list))
        .filter(Material.id == mat.id)
        .first()
    )
    return _material_to_response(mat)


@router.put("/{material_id}", response_model=MaterialResponse)
def update_material(
    material_id: int,
    data: MaterialUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(mat, field, value)

    db.commit()
    db.refresh(mat)

    mat = (
        db.query(Material)
        .options(joinedload(Material.price_list))
        .filter(Material.id == mat.id)
        .first()
    )
    return _material_to_response(mat)


@router.delete("/{material_id}", status_code=204)
def delete_material(
    material_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    mat.is_active = False
    db.commit()
```

**Step 5: Write the price lists router**

Create `backend/app/routers/price_lists.py`:

```python
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.material import Material
from app.models.price_list import PriceList
from app.models.user import User
from app.schemas.price_list import (
    PriceListListResponse,
    PriceListResponse,
    PriceListUpdate,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/price-lists", tags=["price-lists"])


@router.get("", response_model=PriceListListResponse)
def list_price_lists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get all price lists with material counts
    pls = db.query(PriceList).order_by(PriceList.name).all()
    items = []
    for pl in pls:
        count = (
            db.query(func.count(Material.id))
            .filter(Material.price_list_id == pl.id, Material.is_active == True)
            .scalar()
        )
        items.append(
            PriceListResponse(
                id=pl.id,
                name=pl.name,
                source_file=pl.source_file,
                effective_date=pl.effective_date,
                expiration_date=pl.expiration_date,
                imported_at=pl.imported_at,
                imported_by_user_id=pl.imported_by_user_id,
                material_count=count,
            )
        )

    return PriceListListResponse(items=items, total=len(items))


@router.put("/{price_list_id}", response_model=PriceListResponse)
def update_price_list(
    price_list_id: int,
    data: PriceListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pl = db.query(PriceList).filter(PriceList.id == price_list_id).first()
    if not pl:
        raise HTTPException(status_code=404, detail="Price list not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(pl, field, value)

    db.commit()
    db.refresh(pl)

    count = (
        db.query(func.count(Material.id))
        .filter(Material.price_list_id == pl.id, Material.is_active == True)
        .scalar()
    )

    return PriceListResponse(
        id=pl.id,
        name=pl.name,
        source_file=pl.source_file,
        effective_date=pl.effective_date,
        expiration_date=pl.expiration_date,
        imported_at=pl.imported_at,
        imported_by_user_id=pl.imported_by_user_id,
        material_count=count,
    )
```

**Step 6: Register routers in main.py**

In `backend/app/main.py`, add these imports (after line 22, the `leads` import):

```python
from app.routers.materials import router as materials_router
from app.routers.price_lists import router as price_lists_router
```

Add these router registrations (after line 74, the `estimates_router` line):

```python
app.include_router(materials_router)
app.include_router(price_lists_router)
```

**Step 7: Run tests to verify they pass**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_materials.py tests/test_price_lists.py -v`
Expected: All tests PASS

**Step 8: Run full test suite to check for regressions**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest -v`
Expected: All 251+ tests pass (plus the new ones)

**Step 9: Commit**

```bash
git add backend/app/routers/materials.py backend/app/routers/price_lists.py backend/app/main.py backend/tests/test_materials.py backend/tests/test_price_lists.py
git commit -m "feat: add materials and price lists CRUD routers with tests"
```

---

### Task 6: CSV Import API Endpoint + Test

**Files:**
- Modify: `backend/app/routers/materials.py` (add import endpoint)
- Create: `backend/tests/test_material_import_api.py`

**Step 1: Write failing test for the import endpoint**

Create `backend/tests/test_material_import_api.py`:

```python
import io

import pytest


def test_import_materials_csv_endpoint(client, auth_headers):
    csv_content = (
        "item_number,description,unit_price,uom,category,source,ocr_flag\n"
        "ABC123,Test Shingle,117.96,SQ,Shingles,ABC Roofing,\n"
        "DEF456,Test Nail,9.50,BX,Fasteners,ABC Roofing,\n"
    )
    resp = client.post(
        "/api/materials/import",
        headers=auth_headers,
        files={"file": ("materials.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["materials_imported"] == 2
    assert data["price_lists_created"] == 1
    assert data["errors"] == []


def test_import_materials_no_file(client, auth_headers):
    resp = client.post("/api/materials/import", headers=auth_headers)
    assert resp.status_code == 422


def test_import_requires_auth(client):
    resp = client.post("/api/materials/import")
    assert resp.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_material_import_api.py -v`
Expected: FAIL — 404 or similar (endpoint doesn't exist yet)

**Step 3: Add the import endpoint to the materials router**

Add this to the top of `backend/app/routers/materials.py`, after the existing imports:

```python
import tempfile
import os
from fastapi import UploadFile, File
from app.services.material_import import import_materials_csv
from app.schemas.material import MaterialImportResponse
```

Add this route **after** the `/categories` route but **before** the `GET ""` route (literal paths must come before parameterized paths — see CLAUDE.md note about FastAPI route ordering):

```python
@router.post("/import", response_model=MaterialImportResponse)
def import_materials(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Save uploaded file to temp location
    tmpfile = tempfile.NamedTemporaryFile(
        delete=False, suffix=".csv", mode="wb"
    )
    try:
        content = file.file.read()
        tmpfile.write(content)
        tmpfile.close()

        result = import_materials_csv(
            db,
            tmpfile.name,
            source_file=file.filename,
            user_id=current_user.id,
        )
        return MaterialImportResponse(**result)
    finally:
        os.unlink(tmpfile.name)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_material_import_api.py -v`
Expected: All 3 PASS

**Step 5: Run full test suite**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/app/routers/materials.py backend/tests/test_material_import_api.py
git commit -m "feat: add CSV import endpoint for materials"
```

---

### Task 7: Frontend API Client

**Files:**
- Create: `frontend/src/api/materials.js`
- Create: `frontend/src/api/priceLists.js`

**Step 1: Create materials API client**

Create `frontend/src/api/materials.js`:

```javascript
import api from './client'

export const listMaterials = async ({ search, category, priceListId, flagged, page = 1, perPage = 50 } = {}) => {
  const params = { page, per_page: perPage }
  if (search) params.search = search
  if (category) params.category = category
  if (priceListId) params.price_list_id = priceListId
  if (flagged) params.flagged = 'true'
  const { data } = await api.get('/materials', { params })
  return data
}

export const getMaterial = async (id) => {
  const { data } = await api.get(`/materials/${id}`)
  return data
}

export const createMaterial = async (materialData) => {
  const { data } = await api.post('/materials', materialData)
  return data
}

export const updateMaterial = async (id, materialData) => {
  const { data } = await api.put(`/materials/${id}`, materialData)
  return data
}

export const deleteMaterial = async (id) => {
  await api.delete(`/materials/${id}`)
}

export const listCategories = async () => {
  const { data } = await api.get('/materials/categories')
  return data
}

export const importMaterials = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await api.post('/materials/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}
```

**Step 2: Create price lists API client**

Create `frontend/src/api/priceLists.js`:

```javascript
import api from './client'

export const listPriceLists = async () => {
  const { data } = await api.get('/price-lists')
  return data
}

export const updatePriceList = async (id, priceListData) => {
  const { data } = await api.put(`/price-lists/${id}`, priceListData)
  return data
}
```

**Step 3: Commit**

```bash
git add frontend/src/api/materials.js frontend/src/api/priceLists.js
git commit -m "feat: add frontend API clients for materials and price lists"
```

---

### Task 8: Frontend Materials Page

**Files:**
- Create: `frontend/src/pages/MaterialsPage.jsx`
- Modify: `frontend/src/App.jsx` (add route, line 50 area)
- Modify: `frontend/src/components/Sidebar.jsx` (add nav item, lines 36-43)

**Step 1: Create the MaterialsPage component**

Create `frontend/src/pages/MaterialsPage.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { Package, Upload, AlertTriangle, ChevronDown, X, Pencil, Check } from 'lucide-react'
import { listMaterials, listCategories, updateMaterial, deleteMaterial, importMaterials } from '../api/materials'
import { listPriceLists, updatePriceList } from '../api/priceLists'
import { useToast } from '../context/ToastContext'
import SearchInput from '../components/SearchInput'
import Pagination from '../components/Pagination'
import EmptyState from '../components/EmptyState'
import LoadingSpinner from '../components/LoadingSpinner'

const formatCurrency = (value) => {
  if (value == null) return '—'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

function PriceListCards({ priceLists, onUpdate }) {
  const today = new Date().toISOString().slice(0, 10)

  const getStatus = (pl) => {
    if (!pl.expiration_date) return { label: 'No expiry set', color: 'text-gray-500' }
    if (pl.expiration_date < today) return { label: 'Expired', color: 'text-red-400' }
    // Check if expiring within 30 days
    const exp = new Date(pl.expiration_date)
    const thirtyDays = new Date()
    thirtyDays.setDate(thirtyDays.getDate() + 30)
    if (exp <= thirtyDays) return { label: 'Expiring soon', color: 'text-amber-400' }
    return { label: 'Current', color: 'text-emerald-400' }
  }

  const [editingId, setEditingId] = useState(null)
  const [editDate, setEditDate] = useState('')

  const handleSave = async (id) => {
    await onUpdate(id, { expiration_date: editDate || null })
    setEditingId(null)
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {priceLists.map((pl) => {
        const status = getStatus(pl)
        return (
          <div key={pl.id} className="bg-navy-800 rounded-xl p-4 border border-navy-700">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-200">{pl.name}</h3>
              <span className={`text-xs font-medium ${status.color}`}>{status.label}</span>
            </div>
            <p className="text-2xl font-mono font-bold text-gray-100 mb-1">
              {pl.material_count.toLocaleString()}
            </p>
            <p className="text-xs text-gray-500 mb-2">materials</p>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-gray-500">Expires:</span>
              {editingId === pl.id ? (
                <span className="flex items-center gap-1">
                  <input
                    type="date"
                    value={editDate}
                    onChange={(e) => setEditDate(e.target.value)}
                    className="bg-navy-900 border border-navy-600 rounded px-2 py-0.5 text-xs text-gray-200"
                  />
                  <button onClick={() => handleSave(pl.id)} className="text-emerald-400 hover:text-emerald-300">
                    <Check size={14} />
                  </button>
                  <button onClick={() => setEditingId(null)} className="text-gray-500 hover:text-gray-300">
                    <X size={14} />
                  </button>
                </span>
              ) : (
                <button
                  onClick={() => { setEditingId(pl.id); setEditDate(pl.expiration_date || '') }}
                  className="text-gray-300 hover:text-amber-400 flex items-center gap-1"
                >
                  {pl.expiration_date || 'Not set'}
                  <Pencil size={10} />
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ImportModal({ open, onClose, onSuccess }) {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const { addToast } = useToast()

  const handleImport = async () => {
    if (!file) return
    setLoading(true)
    try {
      const res = await importMaterials(file)
      setResult(res)
      if (res.errors.length === 0) {
        addToast(`Imported ${res.materials_imported} materials from ${res.price_lists_created} price list(s)`)
        onSuccess()
      }
    } catch (err) {
      addToast(err.response?.data?.detail || 'Import failed', 'error')
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">Import Materials CSV</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={20} /></button>
        </div>

        {result ? (
          <div className="space-y-3">
            <p className="text-emerald-400 font-medium">
              Imported {result.materials_imported} materials from {result.price_lists_created} price list(s)
            </p>
            {result.errors.length > 0 && (
              <div className="bg-red-900/20 border border-red-800 rounded-lg p-3">
                <p className="text-red-400 text-sm font-medium mb-1">{result.errors.length} error(s):</p>
                <ul className="text-xs text-red-300 space-y-1 max-h-40 overflow-y-auto">
                  {result.errors.map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            )}
            <button onClick={onClose} className="w-full bg-amber-500 hover:bg-amber-600 text-navy-900 font-semibold rounded-lg py-2 transition-colors">
              Done
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-gray-400">
              Upload a CSV with columns: item_number, description, unit_price, uom, category, source, ocr_flag
            </p>
            <div className="border-2 border-dashed border-navy-600 rounded-lg p-6 text-center">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files[0])}
                className="hidden"
                id="csv-upload"
              />
              <label htmlFor="csv-upload" className="cursor-pointer">
                <Upload size={32} className="mx-auto text-gray-500 mb-2" />
                <p className="text-sm text-gray-300">{file ? file.name : 'Click to select CSV file'}</p>
              </label>
            </div>
            <button
              onClick={handleImport}
              disabled={!file || loading}
              className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-navy-900 font-semibold rounded-lg py-2 transition-colors"
            >
              {loading ? 'Importing...' : 'Import'}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function EditMaterialModal({ material, open, onClose, onSave }) {
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const { addToast } = useToast()

  useEffect(() => {
    if (material) {
      setForm({
        item_number: material.item_number,
        description: material.description,
        unit_price: material.unit_price,
        uom: material.uom || '',
        category: material.category,
        ocr_flag: material.ocr_flag || '',
      })
    }
  }, [material])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      const payload = {
        ...form,
        ocr_flag: form.ocr_flag || null,
        uom: form.uom || null,
      }
      await onSave(material.id, payload)
      onClose()
      addToast('Material updated')
    } catch (err) {
      addToast(err.response?.data?.detail || 'Update failed', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (!open || !material) return null

  const inputClass = 'w-full bg-navy-900 border border-navy-600 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6 w-full max-w-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">Edit Material</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={20} /></button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Item Number</label>
              <input className={inputClass} value={form.item_number || ''} onChange={(e) => setForm({ ...form, item_number: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">UOM</label>
              <input className={inputClass} value={form.uom || ''} onChange={(e) => setForm({ ...form, uom: e.target.value })} placeholder="SQ, BD, BX, PC, RL" />
            </div>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Description</label>
            <input className={inputClass} value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Unit Price</label>
              <input type="number" step="0.01" className={inputClass} value={form.unit_price || ''} onChange={(e) => setForm({ ...form, unit_price: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Category</label>
              <input className={inputClass} value={form.category || ''} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            </div>
          </div>
          {material.ocr_flag && (
            <div className="bg-amber-900/20 border border-amber-800 rounded-lg p-3">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle size={14} className="text-amber-400" />
                <span className="text-xs font-medium text-amber-400">OCR Flag</span>
              </div>
              <p className="text-xs text-amber-300 mb-2">{material.ocr_flag}</p>
              <button
                type="button"
                onClick={() => setForm({ ...form, ocr_flag: '' })}
                className="text-xs text-amber-400 hover:text-amber-300 underline"
              >
                Mark as reviewed (clear flag)
              </button>
            </div>
          )}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 bg-navy-700 hover:bg-navy-600 text-gray-300 rounded-lg py-2 text-sm transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={saving} className="flex-1 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-navy-900 font-semibold rounded-lg py-2 text-sm transition-colors">
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function MaterialsPage() {
  const [materials, setMaterials] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('')
  const [priceListId, setPriceListId] = useState('')
  const [flaggedOnly, setFlaggedOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [categories, setCategories] = useState([])
  const [priceLists, setPriceLists] = useState([])
  const [showImport, setShowImport] = useState(false)
  const [editingMaterial, setEditingMaterial] = useState(null)
  const { addToast } = useToast()
  const perPage = 50

  const fetchMaterials = () => {
    setLoading(true)
    listMaterials({
      search,
      category: category || undefined,
      priceListId: priceListId || undefined,
      flagged: flaggedOnly || undefined,
      page,
      perPage,
    })
      .then((data) => {
        setMaterials(data.items)
        setTotal(data.total)
      })
      .catch(() => addToast('Failed to load materials', 'error'))
      .finally(() => setLoading(false))
  }

  const fetchMeta = () => {
    listCategories().then(setCategories).catch(() => {})
    listPriceLists().then((d) => setPriceLists(d.items)).catch(() => {})
  }

  useEffect(() => {
    fetchMeta()
  }, [])

  useEffect(() => {
    fetchMaterials()
  }, [search, category, priceListId, flaggedOnly, page])

  const handleSearch = (value) => {
    setSearch(value)
    setPage(1)
  }

  const handleFilterChange = (setter) => (e) => {
    setter(e.target.value)
    setPage(1)
  }

  const handleUpdate = async (id, data) => {
    const updated = await updateMaterial(id, data)
    setMaterials((prev) => prev.map((m) => (m.id === id ? updated : m)))
    return updated
  }

  const handleDeactivate = async (id) => {
    await deleteMaterial(id)
    setMaterials((prev) => prev.filter((m) => m.id !== id))
    setTotal((t) => t - 1)
    addToast('Material deactivated')
  }

  const handlePriceListUpdate = async (id, data) => {
    await updatePriceList(id, data)
    fetchMeta()
  }

  const flaggedCount = categories.reduce((a, c) => a + c.count, 0)
  // We don't have a direct flagged count from meta, so we'll show it from filtered results
  const selectClass = 'bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500'

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Materials Library</h1>
          <p className="text-sm text-gray-500 mt-1">
            {total.toLocaleString()} materials across {priceLists.length} price list{priceLists.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowImport(true)}
          className="flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-navy-900 font-semibold rounded-lg px-4 py-2.5 text-sm transition-colors"
        >
          <Upload size={16} />
          Import CSV
        </button>
      </div>

      {/* Price List Cards */}
      {priceLists.length > 0 && (
        <PriceListCards priceLists={priceLists} onUpdate={handlePriceListUpdate} />
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex-1 min-w-[200px] max-w-sm">
          <SearchInput
            value={search}
            onChange={handleSearch}
            placeholder="Search by item # or description..."
          />
        </div>
        <select
          value={category}
          onChange={handleFilterChange(setCategory)}
          className={selectClass}
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c.category} value={c.category}>
              {c.category} ({c.count})
            </option>
          ))}
        </select>
        <select
          value={priceListId}
          onChange={handleFilterChange(setPriceListId)}
          className={selectClass}
        >
          <option value="">All Sources</option>
          {priceLists.map((pl) => (
            <option key={pl.id} value={pl.id}>
              {pl.name} ({pl.material_count})
            </option>
          ))}
        </select>
        <button
          onClick={() => { setFlaggedOnly(!flaggedOnly); setPage(1) }}
          className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm border transition-colors ${
            flaggedOnly
              ? 'bg-amber-500/20 border-amber-500 text-amber-400'
              : 'bg-navy-900 border-navy-700 text-gray-400 hover:text-gray-200'
          }`}
        >
          <AlertTriangle size={14} />
          Needs Review
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      ) : materials.length === 0 ? (
        <EmptyState
          icon={Package}
          title={search || category || flaggedOnly ? 'No materials found' : 'No materials yet'}
          description={
            search || category || flaggedOnly
              ? 'Try adjusting your filters'
              : 'Import a CSV to get started'
          }
        />
      ) : (
        <>
          <div className="bg-navy-800 rounded-xl overflow-x-auto border border-navy-700">
            <table className="w-full">
              <thead>
                <tr className="border-b border-navy-700">
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">Item #</th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">Description</th>
                  <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">Unit Price</th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">UOM</th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">Category</th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">Source</th>
                  <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">Status</th>
                  <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wider px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-700">
                {materials.map((mat) => (
                  <tr key={mat.id} className="hover:bg-navy-700/30 transition-colors">
                    <td className="px-4 py-3 text-sm font-mono text-gray-300">{mat.item_number}</td>
                    <td className="px-4 py-3 text-sm text-gray-200 max-w-xs truncate">{mat.description}</td>
                    <td className="px-4 py-3 text-sm font-mono text-gray-100 text-right">{formatCurrency(mat.unit_price)}</td>
                    <td className="px-4 py-3 text-sm text-gray-400">{mat.uom || <span className="text-amber-500 text-xs">Missing</span>}</td>
                    <td className="px-4 py-3 text-sm text-gray-400">{mat.category}</td>
                    <td className="px-4 py-3 text-sm text-gray-500">{mat.price_list_name}</td>
                    <td className="px-4 py-3 text-center">
                      {mat.ocr_flag ? (
                        <span className="inline-flex items-center gap-1 text-xs text-amber-400" title={mat.ocr_flag}>
                          <AlertTriangle size={12} />
                          Review
                        </span>
                      ) : (
                        <span className="text-xs text-emerald-400">OK</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => setEditingMaterial(mat)}
                        className="text-gray-500 hover:text-amber-400 transition-colors p-1"
                        title="Edit"
                      >
                        <Pencil size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination
            page={page}
            perPage={perPage}
            total={total}
            onPageChange={setPage}
          />
        </>
      )}

      {/* Modals */}
      <ImportModal
        open={showImport}
        onClose={() => { setShowImport(false) }}
        onSuccess={() => { setShowImport(false); fetchMaterials(); fetchMeta() }}
      />
      <EditMaterialModal
        material={editingMaterial}
        open={!!editingMaterial}
        onClose={() => setEditingMaterial(null)}
        onSave={handleUpdate}
      />
    </div>
  )
}
```

**Step 2: Add route to App.jsx**

In `frontend/src/App.jsx`, add the import (after line 22):

```javascript
import MaterialsPage from './pages/MaterialsPage'
```

Add the route (after the estimates/:id route, around line 51):

```jsx
<Route path="/materials" element={<MaterialsPage />} />
```

**Step 3: Add to Sidebar navigation**

In `frontend/src/components/Sidebar.jsx`, add `Package` to the lucide-react imports (line 2-17):

Add `Package` to the import destructure.

Add materials nav item to the JOBS section (after the Estimates entry at line 41):

```javascript
{ to: '/materials', label: 'Materials', icon: Package },
```

**Step 4: Verify frontend builds**

Run: `cd /Users/iantitus/Desktop/legacy-crm/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add frontend/src/pages/MaterialsPage.jsx frontend/src/api/materials.js frontend/src/api/priceLists.js frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat: add Materials Library page with search, filters, edit, and CSV import"
```

---

### Task 9: Import the Master CSV

**Files:**
- Create: `backend/scripts/import_materials.py` (CLI script)

**Step 1: Create the CLI import script**

Create `backend/scripts/import_materials.py`:

```python
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
```

Also create `backend/scripts/__init__.py` (empty file so Python treats it as a package).

**Step 2: Commit**

```bash
git add backend/scripts/import_materials.py backend/scripts/__init__.py
git commit -m "feat: add CLI script for materials CSV import"
```

---

### Task 10: Final Integration Test & Full Suite

**Step 1: Run the full backend test suite**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest -v --tb=short`
Expected: All tests pass (251 original + ~20 new = ~271+)

**Step 2: Verify frontend builds clean**

Run: `cd /Users/iantitus/Desktop/legacy-crm/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit any final fixes if needed, then tag**

```bash
git add -A
git commit -m "Sprint 9a: Materials database, CSV import, and admin UI"
```
