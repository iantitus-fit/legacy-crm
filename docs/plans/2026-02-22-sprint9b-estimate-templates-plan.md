# Sprint 9b: Estimate Templates & Calculation Engine — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add estimate templates with a calculation engine that auto-generates estimate line items from roof measurements, including template CRUD, material picker, and apply-template flow.

**Architecture:** Two new tables (`estimate_templates` and `estimate_template_items`) with FK to materials. A pure-function calculation engine computes quantities from measurements. Template CRUD router follows existing materials pattern. Frontend adds Templates list page, Template builder page with material picker, and Apply Template modal on EstimateDetailPage.

**Tech Stack:** SQLAlchemy 2.x models, Alembic migration, FastAPI router, Pydantic schemas, React 18 + Tailwind frontend, pytest with SQLite.

---

### Task 1: Alembic Migration

**Files:**
- Create: `backend/alembic/versions/0008_sprint9b_estimate_templates.py`

**Step 1: Write the migration file**

```python
"""Sprint 9b: Estimate templates and template items.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "estimate_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), unique=True, nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "default_margin_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="46.00",
        ),
        sa.Column(
            "default_waste_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="10.00",
        ),
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

    op.create_table(
        "estimate_template_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer,
            sa.ForeignKey("estimate_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "material_id",
            sa.Integer,
            sa.ForeignKey("materials.id"),
            nullable=True,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("uom", sa.String(20), nullable=True),
        sa.Column(
            "margin_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="46.00",
        ),
        sa.Column(
            "waste_pct",
            sa.Numeric(5, 2),
            nullable=False,
            server_default="10.00",
        ),
        sa.Column("measurement_type", sa.String(50), nullable=True),
        sa.Column(
            "conversion_factor",
            sa.Numeric(10, 4),
            nullable=False,
            server_default="1.0000",
        ),
        sa.Column("default_qty", sa.Numeric(12, 2), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_template_items_template_id",
        "estimate_template_items",
        ["template_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_template_items_template_id", table_name="estimate_template_items")
    op.drop_table("estimate_template_items")
    op.drop_table("estimate_templates")
```

**Step 2: Verify migration file is syntactically valid**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -c "exec(open('alembic/versions/0008_sprint9b_estimate_templates.py').read()); print('OK')"`

**Step 3: Commit**

```bash
git add backend/alembic/versions/0008_sprint9b_estimate_templates.py
git commit -m "feat: add migration for estimate_templates and estimate_template_items"
```

---

### Task 2: SQLAlchemy Models

**Files:**
- Create: `backend/app/models/estimate_template.py`
- Create: `backend/app/models/estimate_template_item.py`
- Modify: `backend/app/models/__init__.py`

**Step 1: Create EstimateTemplate model**

Create `backend/app/models/estimate_template.py`:

```python
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

if TYPE_CHECKING:
    from app.models.estimate_template_item import EstimateTemplateItem


class EstimateTemplate(Base):
    __tablename__ = "estimate_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500))
    default_margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="46.00"
    )
    default_waste_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="10.00"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean(), default=True, server_default="true", nullable=False
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    items: Mapped[List["EstimateTemplateItem"]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )
```

**Step 2: Create EstimateTemplateItem model**

Create `backend/app/models/estimate_template_item.py`:

```python
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.estimate_template import EstimateTemplate
    from app.models.material import Material


class EstimateTemplateItem(Base):
    __tablename__ = "estimate_template_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        Integer(), ForeignKey("estimate_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    material_id: Mapped[Optional[int]] = mapped_column(
        Integer(), ForeignKey("materials.id"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    uom: Mapped[Optional[str]] = mapped_column(String(20))
    margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="46.00"
    )
    waste_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="10.00"
    )
    measurement_type: Mapped[Optional[str]] = mapped_column(String(50))
    conversion_factor: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default="1.0000"
    )
    default_qty: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    sort_order: Mapped[int] = mapped_column(
        Integer(), nullable=False, server_default="0"
    )

    template: Mapped[Optional["EstimateTemplate"]] = relationship(
        back_populates="items"
    )
    material: Mapped[Optional["Material"]] = relationship()
```

**Step 3: Register models in `__init__.py`**

Add to `backend/app/models/__init__.py`:

```python
from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
```

Add `"EstimateTemplate"` and `"EstimateTemplateItem"` to the `__all__` list.

**Step 4: Verify models load**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -c "from app.models import EstimateTemplate, EstimateTemplateItem; print('OK')"`

**Step 5: Commit**

```bash
git add backend/app/models/estimate_template.py backend/app/models/estimate_template_item.py backend/app/models/__init__.py
git commit -m "feat: add EstimateTemplate and EstimateTemplateItem models"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/estimate_template.py`

**Step 1: Create all template schemas**

Create `backend/app/schemas/estimate_template.py`:

```python
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from pydantic import BaseModel


# --- Template Items ---


class TemplateItemCreate(BaseModel):
    material_id: Optional[int] = None
    description: str
    category: str
    unit_cost: Decimal
    uom: Optional[str] = None
    margin_pct: Optional[Decimal] = None
    waste_pct: Optional[Decimal] = None
    measurement_type: Optional[str] = None
    conversion_factor: Decimal = Decimal("1.0000")
    default_qty: Optional[Decimal] = None
    sort_order: Optional[int] = None


class TemplateItemUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    unit_cost: Optional[Decimal] = None
    uom: Optional[str] = None
    margin_pct: Optional[Decimal] = None
    waste_pct: Optional[Decimal] = None
    measurement_type: Optional[str] = None
    conversion_factor: Optional[Decimal] = None
    default_qty: Optional[Decimal] = None
    sort_order: Optional[int] = None


class TemplateItemResponse(BaseModel):
    id: int
    template_id: int
    material_id: Optional[int] = None
    description: str
    category: str
    unit_cost: Decimal
    uom: Optional[str] = None
    margin_pct: Decimal
    waste_pct: Decimal
    measurement_type: Optional[str] = None
    conversion_factor: Decimal
    default_qty: Optional[Decimal] = None
    sort_order: int

    model_config = {"from_attributes": True}


# --- Templates ---


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    default_margin_pct: Decimal = Decimal("46.00")
    default_waste_pct: Decimal = Decimal("10.00")


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    default_margin_pct: Optional[Decimal] = None
    default_waste_pct: Optional[Decimal] = None


class TemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    default_margin_pct: Decimal
    default_waste_pct: Decimal
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    items: List[TemplateItemResponse] = []
    item_count: int = 0

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    items: List[TemplateResponse]
    total: int


class TemplateItemReorder(BaseModel):
    item_ids: List[int]


# --- Measurements & Preview ---


class MeasurementsInput(BaseModel):
    total_area: Optional[Decimal] = None
    ridge: Optional[Decimal] = None
    hip: Optional[Decimal] = None
    valley: Optional[Decimal] = None
    eave: Optional[Decimal] = None
    rake: Optional[Decimal] = None


class PreviewLineItem(BaseModel):
    description: str
    category: str
    qty: int
    unit_price: Decimal
    line_total: Decimal
    measurement_type: Optional[str] = None
    measurement_value: Optional[Decimal] = None
    raw_qty: Decimal
    waste_applied: Decimal
    uom: Optional[str] = None


class PreviewResponse(BaseModel):
    items: List[PreviewLineItem]
    subtotal: Decimal
    item_count: int


class ApplyTemplateRequest(BaseModel):
    template_id: int
    measurements: MeasurementsInput
```

**Step 2: Commit**

```bash
git add backend/app/schemas/estimate_template.py
git commit -m "feat: add Pydantic schemas for estimate templates"
```

---

### Task 4: Calculation Engine Service + Tests

**Files:**
- Create: `backend/app/services/template_calculator.py`
- Create: `backend/tests/test_template_calculator.py`

**Step 1: Write failing tests**

Create `backend/tests/test_template_calculator.py`:

```python
import math
from decimal import Decimal

import pytest

from app.services.template_calculator import (
    calculate_item,
    calculate_template_preview,
)


class TestCalculateItem:
    """Test the single-item calculation function."""

    def test_measurement_based_shingles(self):
        """32.5 sq area * 3 bundles/sq = 97.5, +10% waste = 107.25, ceil = 108.
        Sell price: 117.96 * 1.46 = 172.2216 -> 172.22.
        Line total: 108 * 172.22 = 18599.76."""
        result = calculate_item(
            unit_cost=Decimal("117.96"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="total_area",
            conversion_factor=Decimal("3.0000"),
            default_qty=None,
            measurements={"total_area": Decimal("32.5")},
        )
        assert result["qty"] == 108
        assert result["unit_price"] == Decimal("172.22")
        assert result["line_total"] == Decimal("18599.76")
        assert result["raw_qty"] == Decimal("97.5000")
        assert result["waste_applied"] == Decimal("107.2500")
        assert result["measurement_value"] == Decimal("32.5")

    def test_fixed_qty_labor(self):
        """No measurement_type, default_qty=1. Waste 0%. Margin 46%.
        Qty: ceil(1 * 1.0) = 1. Sell price: 500 * 1.46 = 730.00.
        Line total: 730.00."""
        result = calculate_item(
            unit_cost=Decimal("500.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=Decimal("1.00"),
            measurements={},
        )
        assert result["qty"] == 1
        assert result["unit_price"] == Decimal("730.00")
        assert result["line_total"] == Decimal("730.00")

    def test_ridge_cap_conversion(self):
        """45 LF ridge / 33 LF per bundle = 1.3636..., +10% = 1.5, ceil = 2.
        Sell price: 68.50 * 1.46 = 100.01.
        Line total: 2 * 100.01 = 200.02."""
        result = calculate_item(
            unit_cost=Decimal("68.50"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="ridge",
            conversion_factor=Decimal("0.0303"),  # 1/33
            default_qty=None,
            measurements={"ridge": Decimal("45.0")},
        )
        # 45 * 0.0303 = 1.3635, * 1.10 = 1.49985, ceil = 2
        assert result["qty"] == 2
        assert result["unit_price"] == Decimal("100.01")
        assert result["line_total"] == Decimal("200.02")

    def test_zero_waste(self):
        """Items with 0% waste: qty = ceil(raw_qty)."""
        result = calculate_item(
            unit_cost=Decimal("45.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type="total_area",
            conversion_factor=Decimal("1.0000"),
            default_qty=None,
            measurements={"total_area": Decimal("32.5")},
        )
        # 32.5 * 1.0 = 32.5, * 1.0 = 32.5, ceil = 33
        assert result["qty"] == 33

    def test_missing_measurement_returns_zero_qty(self):
        """If measurement_type is set but that measurement is missing, qty = 0."""
        result = calculate_item(
            unit_cost=Decimal("50.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="valley",
            conversion_factor=Decimal("1.0000"),
            default_qty=None,
            measurements={"total_area": Decimal("32.5")},
        )
        assert result["qty"] == 0
        assert result["line_total"] == Decimal("0.00")

    def test_no_measurement_type_no_default_qty(self):
        """No measurement_type and no default_qty: qty = 0."""
        result = calculate_item(
            unit_cost=Decimal("50.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=None,
            measurements={},
        )
        assert result["qty"] == 0
        assert result["line_total"] == Decimal("0.00")

    def test_zero_margin(self):
        """0% margin: sell price = cost price."""
        result = calculate_item(
            unit_cost=Decimal("100.00"),
            margin_pct=Decimal("0.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=Decimal("5.00"),
            measurements={},
        )
        assert result["unit_price"] == Decimal("100.00")
        assert result["qty"] == 5
        assert result["line_total"] == Decimal("500.00")

    def test_high_conversion_factor(self):
        """Nails: 180 LF eave * 0.5 box/LF = 90, +5% waste = 94.5, ceil = 95."""
        result = calculate_item(
            unit_cost=Decimal("9.50"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("5.00"),
            measurement_type="eave",
            conversion_factor=Decimal("0.5000"),
            default_qty=None,
            measurements={"eave": Decimal("180.0")},
        )
        assert result["qty"] == 95
        assert result["unit_price"] == Decimal("13.87")


class TestCalculateTemplatePreview:
    """Test the full template preview calculation."""

    def test_basic_preview(self):
        """Two items: one measurement-based, one fixed-qty."""
        items = [
            {
                "description": "Shingles",
                "category": "Roofing",
                "unit_cost": Decimal("100.00"),
                "uom": "BD",
                "margin_pct": Decimal("46.00"),
                "waste_pct": Decimal("10.00"),
                "measurement_type": "total_area",
                "conversion_factor": Decimal("3.0000"),
                "default_qty": None,
            },
            {
                "description": "Labor",
                "category": "Labor",
                "unit_cost": Decimal("500.00"),
                "uom": None,
                "margin_pct": Decimal("46.00"),
                "waste_pct": Decimal("0.00"),
                "measurement_type": None,
                "conversion_factor": Decimal("1.0000"),
                "default_qty": Decimal("1.00"),
            },
        ]
        measurements = {"total_area": Decimal("10.0")}
        result = calculate_template_preview(items, measurements)

        assert result["item_count"] == 2
        assert len(result["items"]) == 2

        # Shingles: 10 * 3 = 30, +10% = 33, ceil = 33
        # Price: 100 * 1.46 = 146.00
        # Total: 33 * 146.00 = 4818.00
        shingles = result["items"][0]
        assert shingles["qty"] == 33
        assert shingles["unit_price"] == Decimal("146.00")
        assert shingles["line_total"] == Decimal("4818.00")

        # Labor: default_qty 1, no waste = 1
        # Price: 500 * 1.46 = 730.00
        labor = result["items"][1]
        assert labor["qty"] == 1
        assert labor["line_total"] == Decimal("730.00")

        assert result["subtotal"] == Decimal("5548.00")

    def test_empty_items(self):
        result = calculate_template_preview([], {"total_area": Decimal("10.0")})
        assert result["item_count"] == 0
        assert result["subtotal"] == Decimal("0.00")
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_template_calculator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.template_calculator'`

**Step 3: Write the calculation engine**

Create `backend/app/services/template_calculator.py`:

```python
import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def calculate_item(
    unit_cost: Decimal,
    margin_pct: Decimal,
    waste_pct: Decimal,
    measurement_type: Optional[str],
    conversion_factor: Decimal,
    default_qty: Optional[Decimal],
    measurements: Dict[str, Decimal],
) -> Dict:
    """Calculate a single template item's quantity, sell price, and line total.

    Returns dict with: qty, unit_price, line_total, raw_qty, waste_applied,
    measurement_value.
    """
    unit_cost = Decimal(str(unit_cost))
    margin_pct = Decimal(str(margin_pct))
    waste_pct = Decimal(str(waste_pct))
    conversion_factor = Decimal(str(conversion_factor))

    # Step 1: Determine raw quantity
    measurement_value = None
    if measurement_type and measurement_type in measurements:
        measurement_value = Decimal(str(measurements[measurement_type]))
        raw_qty = (measurement_value * conversion_factor).quantize(
            FOUR_PLACES, rounding=ROUND_HALF_UP
        )
    elif measurement_type is None and default_qty is not None:
        raw_qty = Decimal(str(default_qty))
    else:
        # Missing measurement or no default — zero qty
        return {
            "qty": 0,
            "unit_price": (
                unit_cost * (Decimal("1") + margin_pct / Decimal("100"))
            ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            "line_total": Decimal("0.00"),
            "raw_qty": Decimal("0.0000"),
            "waste_applied": Decimal("0.0000"),
            "measurement_value": measurement_value,
        }

    # Step 2: Apply waste factor
    waste_applied = (
        raw_qty * (Decimal("1") + waste_pct / Decimal("100"))
    ).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)

    # Step 3: Round up to whole units
    qty = math.ceil(float(waste_applied))

    # Step 4: Calculate sell price (unit_cost + margin)
    sell_price = (
        unit_cost * (Decimal("1") + margin_pct / Decimal("100"))
    ).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Step 5: Line total
    line_total = (Decimal(str(qty)) * sell_price).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    return {
        "qty": qty,
        "unit_price": sell_price,
        "line_total": line_total,
        "raw_qty": raw_qty,
        "waste_applied": waste_applied,
        "measurement_value": measurement_value,
    }


def calculate_template_preview(
    items: List[Dict],
    measurements: Dict[str, Decimal],
) -> Dict:
    """Calculate a full template preview from items and measurements.

    Each item dict should have: description, category, unit_cost, uom,
    margin_pct, waste_pct, measurement_type, conversion_factor, default_qty.

    Returns dict with: items (list of calculated line items), subtotal, item_count.
    """
    result_items = []
    subtotal = Decimal("0.00")

    for item in items:
        calc = calculate_item(
            unit_cost=item["unit_cost"],
            margin_pct=item["margin_pct"],
            waste_pct=item["waste_pct"],
            measurement_type=item.get("measurement_type"),
            conversion_factor=item["conversion_factor"],
            default_qty=item.get("default_qty"),
            measurements=measurements,
        )
        result_items.append(
            {
                "description": item["description"],
                "category": item["category"],
                "qty": calc["qty"],
                "unit_price": calc["unit_price"],
                "line_total": calc["line_total"],
                "measurement_type": item.get("measurement_type"),
                "measurement_value": calc["measurement_value"],
                "raw_qty": calc["raw_qty"],
                "waste_applied": calc["waste_applied"],
                "uom": item.get("uom"),
            }
        )
        subtotal += calc["line_total"]

    return {
        "items": result_items,
        "subtotal": subtotal.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
        "item_count": len(result_items),
    }
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_template_calculator.py -v`
Expected: All 10 tests PASS

**Step 5: Commit**

```bash
git add backend/app/services/template_calculator.py backend/tests/test_template_calculator.py
git commit -m "feat: add estimate template calculation engine with tests"
```

---

### Task 5: Template CRUD Router + Tests

**Files:**
- Create: `backend/app/routers/estimate_templates.py`
- Create: `backend/tests/test_estimate_templates.py`
- Modify: `backend/app/main.py` (register router)

**Step 1: Write failing tests**

Create `backend/tests/test_estimate_templates.py`:

```python
from decimal import Decimal

import pytest

from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
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
def sample_material(db_session, price_list):
    mat = Material(
        price_list_id=price_list.id,
        item_number="OC001",
        description="OC Duration Brownwood",
        unit_price=Decimal("117.96"),
        uom="BD",
        category="Shingles",
    )
    db_session.add(mat)
    db_session.commit()
    db_session.refresh(mat)
    return mat


@pytest.fixture()
def template(db_session):
    t = EstimateTemplate(
        name="IKO Cambridge 30-Year",
        description="Standard residential roof",
        default_margin_pct=Decimal("46.00"),
        default_waste_pct=Decimal("10.00"),
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


@pytest.fixture()
def template_with_items(db_session, template, sample_material):
    items = [
        EstimateTemplateItem(
            template_id=template.id,
            material_id=sample_material.id,
            description="OC Duration Brownwood",
            category="Roofing",
            unit_cost=Decimal("117.96"),
            uom="BD",
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="total_area",
            conversion_factor=Decimal("3.0000"),
            sort_order=0,
        ),
        EstimateTemplateItem(
            template_id=template.id,
            description="Roofing Labor",
            category="Labor",
            unit_cost=Decimal("500.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=Decimal("1.00"),
            sort_order=1,
        ),
    ]
    db_session.add_all(items)
    db_session.commit()
    return template


# --- List Templates ---


def test_list_templates(client, auth_headers, template):
    resp = client.get("/api/estimate-templates", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "IKO Cambridge 30-Year"
    assert data["items"][0]["item_count"] == 0


def test_list_templates_excludes_inactive(client, auth_headers, db_session):
    t = EstimateTemplate(name="Inactive", is_active=False)
    db_session.add(t)
    db_session.commit()
    resp = client.get("/api/estimate-templates", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# --- Get Template ---


def test_get_template(client, auth_headers, template_with_items):
    resp = client.get(
        f"/api/estimate-templates/{template_with_items.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "IKO Cambridge 30-Year"
    assert len(data["items"]) == 2
    assert data["items"][0]["description"] == "OC Duration Brownwood"
    assert data["items"][1]["description"] == "Roofing Labor"


def test_get_template_not_found(client, auth_headers):
    resp = client.get("/api/estimate-templates/99999", headers=auth_headers)
    assert resp.status_code == 404


# --- Create Template ---


def test_create_template(client, auth_headers):
    resp = client.post(
        "/api/estimate-templates",
        headers=auth_headers,
        json={
            "name": "OC Duration Storm",
            "description": "High-wind rated",
            "default_margin_pct": "50.00",
            "default_waste_pct": "12.00",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "OC Duration Storm"
    assert data["default_margin_pct"] == "50.00"


def test_create_template_duplicate_name(client, auth_headers, template):
    resp = client.post(
        "/api/estimate-templates",
        headers=auth_headers,
        json={"name": "IKO Cambridge 30-Year"},
    )
    assert resp.status_code == 400


# --- Update Template ---


def test_update_template(client, auth_headers, template):
    resp = client.put(
        f"/api/estimate-templates/{template.id}",
        headers=auth_headers,
        json={"name": "IKO Cambridge Updated", "default_margin_pct": "48.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "IKO Cambridge Updated"
    assert resp.json()["default_margin_pct"] == "48.00"


# --- Delete (soft) Template ---


def test_delete_template(client, auth_headers, template):
    resp = client.delete(
        f"/api/estimate-templates/{template.id}", headers=auth_headers
    )
    assert resp.status_code == 204

    # Should not appear in list
    resp = client.get("/api/estimate-templates", headers=auth_headers)
    assert resp.json()["total"] == 0


# --- Duplicate Template ---


def test_duplicate_template(client, auth_headers, template_with_items):
    resp = client.post(
        f"/api/estimate-templates/{template_with_items.id}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "IKO Cambridge 30-Year (Copy)"
    assert len(data["items"]) == 2
    assert data["id"] != template_with_items.id


# --- Add Item ---


def test_add_item(client, auth_headers, template, sample_material):
    resp = client.post(
        f"/api/estimate-templates/{template.id}/items",
        headers=auth_headers,
        json={
            "material_id": sample_material.id,
            "description": "OC Duration Brownwood",
            "category": "Roofing",
            "unit_cost": "117.96",
            "uom": "BD",
            "measurement_type": "total_area",
            "conversion_factor": "3.0000",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["description"] == "OC Duration Brownwood"
    assert data["margin_pct"] == "46.00"  # inherited from template default


def test_add_manual_item(client, auth_headers, template):
    resp = client.post(
        f"/api/estimate-templates/{template.id}/items",
        headers=auth_headers,
        json={
            "description": "Dumpster Rental",
            "category": "Labor",
            "unit_cost": "350.00",
            "waste_pct": "0.00",
            "default_qty": "1.00",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["material_id"] is None
    assert resp.json()["default_qty"] == "1.00"


# --- Update Item ---


def test_update_item(client, auth_headers, template_with_items, db_session):
    item = (
        db_session.query(EstimateTemplateItem)
        .filter(EstimateTemplateItem.template_id == template_with_items.id)
        .first()
    )
    resp = client.put(
        f"/api/estimate-templates/{template_with_items.id}/items/{item.id}",
        headers=auth_headers,
        json={"waste_pct": "15.00", "margin_pct": "50.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["waste_pct"] == "15.00"
    assert resp.json()["margin_pct"] == "50.00"


# --- Delete Item ---


def test_delete_item(client, auth_headers, template_with_items, db_session):
    item = (
        db_session.query(EstimateTemplateItem)
        .filter(EstimateTemplateItem.template_id == template_with_items.id)
        .first()
    )
    resp = client.delete(
        f"/api/estimate-templates/{template_with_items.id}/items/{item.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204


# --- Reorder Items ---


def test_reorder_items(client, auth_headers, template_with_items, db_session):
    items = (
        db_session.query(EstimateTemplateItem)
        .filter(EstimateTemplateItem.template_id == template_with_items.id)
        .order_by(EstimateTemplateItem.sort_order)
        .all()
    )
    # Reverse the order
    resp = client.put(
        f"/api/estimate-templates/{template_with_items.id}/items/reorder",
        headers=auth_headers,
        json={"item_ids": [items[1].id, items[0].id]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"][0]["description"] == "Roofing Labor"
    assert data["items"][1]["description"] == "OC Duration Brownwood"


# --- Preview ---


def test_preview(client, auth_headers, template_with_items):
    resp = client.post(
        f"/api/estimate-templates/{template_with_items.id}/preview",
        headers=auth_headers,
        json={
            "measurements": {
                "total_area": "32.5",
            }
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["item_count"] == 2
    # Shingles: 32.5 * 3 = 97.5, +10% = 107.25, ceil = 108
    assert data["items"][0]["qty"] == 108
    # Labor: default_qty 1, no waste
    assert data["items"][1]["qty"] == 1
    assert Decimal(data["subtotal"]) > Decimal("0")


# --- Auth required ---


def test_templates_require_auth(client):
    resp = client.get("/api/estimate-templates")
    assert resp.status_code == 401
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_estimate_templates.py -v`
Expected: FAIL — router doesn't exist

**Step 3: Write the router**

Create `backend/app/routers/estimate_templates.py`:

```python
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
from app.models.user import User
from app.schemas.estimate_template import (
    MeasurementsInput,
    PreviewResponse,
    TemplateCreate,
    TemplateItemCreate,
    TemplateItemReorder,
    TemplateItemResponse,
    TemplateItemUpdate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.services.template_calculator import calculate_template_preview
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/estimate-templates", tags=["estimate-templates"])


def _template_to_response(template: EstimateTemplate) -> dict:
    sorted_items = sorted(template.items, key=lambda i: i.sort_order or 0)
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "default_margin_pct": template.default_margin_pct,
        "default_waste_pct": template.default_waste_pct,
        "is_active": template.is_active,
        "created_at": template.created_at,
        "updated_at": template.updated_at,
        "items": sorted_items,
        "item_count": len(sorted_items),
    }


def _load_template(db: Session, template_id: int) -> EstimateTemplate:
    template = (
        db.query(EstimateTemplate)
        .options(joinedload(EstimateTemplate.items))
        .filter(EstimateTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


# --- Template CRUD ---


@router.get("", response_model=TemplateListResponse)
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    templates = (
        db.query(EstimateTemplate)
        .options(joinedload(EstimateTemplate.items))
        .filter(EstimateTemplate.is_active == True)
        .order_by(EstimateTemplate.name)
        .all()
    )
    return TemplateListResponse(
        items=[_template_to_response(t) for t in templates],
        total=len(templates),
    )


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = _load_template(db, template_id)
    return _template_to_response(template)


@router.post("", response_model=TemplateResponse, status_code=201)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (
        db.query(EstimateTemplate)
        .filter(EstimateTemplate.name == data.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Template name already exists")

    template = EstimateTemplate(**data.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    template = _load_template(db, template.id)
    return _template_to_response(template)


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: int,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(EstimateTemplate).filter(
        EstimateTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    template = _load_template(db, template_id)
    return _template_to_response(template)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(EstimateTemplate).filter(
        EstimateTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.is_active = False
    db.commit()


@router.post("/{template_id}/duplicate", response_model=TemplateResponse, status_code=201)
def duplicate_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    source = _load_template(db, template_id)

    new_template = EstimateTemplate(
        name=f"{source.name} (Copy)",
        description=source.description,
        default_margin_pct=source.default_margin_pct,
        default_waste_pct=source.default_waste_pct,
    )
    db.add(new_template)
    db.flush()

    for item in sorted(source.items, key=lambda i: i.sort_order or 0):
        new_item = EstimateTemplateItem(
            template_id=new_template.id,
            material_id=item.material_id,
            description=item.description,
            category=item.category,
            unit_cost=item.unit_cost,
            uom=item.uom,
            margin_pct=item.margin_pct,
            waste_pct=item.waste_pct,
            measurement_type=item.measurement_type,
            conversion_factor=item.conversion_factor,
            default_qty=item.default_qty,
            sort_order=item.sort_order,
        )
        db.add(new_item)

    db.commit()
    new_template = _load_template(db, new_template.id)
    return _template_to_response(new_template)


# --- Template Item CRUD ---


@router.post(
    "/{template_id}/items",
    response_model=TemplateItemResponse,
    status_code=201,
)
def add_item(
    template_id: int,
    data: TemplateItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(EstimateTemplate).filter(
        EstimateTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Default margin/waste from template if not specified
    margin = data.margin_pct if data.margin_pct is not None else template.default_margin_pct
    waste = data.waste_pct if data.waste_pct is not None else template.default_waste_pct

    # Auto sort_order if not specified
    if data.sort_order is None:
        max_order = (
            db.query(EstimateTemplateItem.sort_order)
            .filter(EstimateTemplateItem.template_id == template_id)
            .order_by(EstimateTemplateItem.sort_order.desc())
            .first()
        )
        sort_order = (max_order[0] or 0) + 1 if max_order else 0
    else:
        sort_order = data.sort_order

    item = EstimateTemplateItem(
        template_id=template_id,
        material_id=data.material_id,
        description=data.description,
        category=data.category,
        unit_cost=data.unit_cost,
        uom=data.uom,
        margin_pct=margin,
        waste_pct=waste,
        measurement_type=data.measurement_type,
        conversion_factor=data.conversion_factor,
        default_qty=data.default_qty,
        sort_order=sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put(
    "/{template_id}/items/{item_id}",
    response_model=TemplateItemResponse,
)
def update_item(
    template_id: int,
    item_id: int,
    data: TemplateItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(EstimateTemplateItem)
        .filter(
            EstimateTemplateItem.id == item_id,
            EstimateTemplateItem.template_id == template_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Template item not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{template_id}/items/{item_id}", status_code=204)
def delete_item(
    template_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = (
        db.query(EstimateTemplateItem)
        .filter(
            EstimateTemplateItem.id == item_id,
            EstimateTemplateItem.template_id == template_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Template item not found")

    db.delete(item)
    db.commit()


@router.put(
    "/{template_id}/items/reorder",
    response_model=TemplateResponse,
)
def reorder_items(
    template_id: int,
    data: TemplateItemReorder,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = db.query(EstimateTemplate).filter(
        EstimateTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    existing_ids = {
        row[0]
        for row in db.query(EstimateTemplateItem.id)
        .filter(EstimateTemplateItem.template_id == template_id)
        .all()
    }

    if set(data.item_ids) != existing_ids:
        raise HTTPException(
            status_code=400,
            detail="item_ids must contain exactly all item IDs for this template",
        )

    for idx, item_id in enumerate(data.item_ids):
        db.query(EstimateTemplateItem).filter(
            EstimateTemplateItem.id == item_id
        ).update({"sort_order": idx})

    db.commit()
    template = _load_template(db, template_id)
    return _template_to_response(template)


# --- Preview ---


@router.post("/{template_id}/preview", response_model=PreviewResponse)
def preview_template(
    template_id: int,
    data: MeasurementsInput,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    template = _load_template(db, template_id)

    measurements = {}
    for field in ["total_area", "ridge", "hip", "valley", "eave", "rake"]:
        val = getattr(data, field)
        if val is not None:
            measurements[field] = val

    items_data = [
        {
            "description": item.description,
            "category": item.category,
            "unit_cost": item.unit_cost,
            "uom": item.uom,
            "margin_pct": item.margin_pct,
            "waste_pct": item.waste_pct,
            "measurement_type": item.measurement_type,
            "conversion_factor": item.conversion_factor,
            "default_qty": item.default_qty,
        }
        for item in sorted(template.items, key=lambda i: i.sort_order or 0)
    ]

    return calculate_template_preview(items_data, measurements)
```

**Step 4: Register router in `backend/app/main.py`**

Add import after line 19 (the estimates import):
```python
from app.routers.estimate_templates import router as estimate_templates_router
```

Add router registration after line 76 (the estimates_router line):
```python
app.include_router(estimate_templates_router)
```

**Step 5: Run tests to verify they pass**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_estimate_templates.py -v`
Expected: All tests PASS

**Step 6: Run full test suite**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest -v --tb=short`
Expected: All 280+ existing tests plus ~18 new tests pass

**Step 7: Commit**

```bash
git add backend/app/routers/estimate_templates.py backend/tests/test_estimate_templates.py backend/app/main.py
git commit -m "feat: add estimate templates CRUD router with preview and tests"
```

---

### Task 6: Apply Template Endpoint + Tests

**Files:**
- Modify: `backend/app/routers/estimates.py` (add apply-template endpoint)
- Create: `backend/tests/test_apply_template.py`

**Step 1: Write failing tests**

Create `backend/tests/test_apply_template.py`:

```python
from decimal import Decimal

import pytest

from app.models.estimate import Estimate
from app.models.estimate_line_item import EstimateLineItem
from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
from app.models.contact import Contact
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.pipeline_stage import PipelineStage


@pytest.fixture()
def job_with_estimate(db_session, seeded_stages):
    contact = Contact(name="Test Customer", phone="555-1234")
    db_session.add(contact)
    db_session.flush()

    stage = db_session.query(PipelineStage).first()
    pipeline = db_session.query(Pipeline).first()
    job = Job(
        contact_id=contact.id,
        stage_id=stage.id,
        pipeline_id=pipeline.id,
        property_address="123 Main St",
    )
    db_session.add(job)
    db_session.flush()

    estimate = Estimate(
        job_id=job.id,
        name="Test Estimate",
        subtotal=Decimal("0"),
        tax=Decimal("0"),
        total=Decimal("0"),
    )
    db_session.add(estimate)
    db_session.commit()
    db_session.refresh(estimate)
    return estimate


@pytest.fixture()
def template_for_apply(db_session):
    t = EstimateTemplate(
        name="Test Template",
        default_margin_pct=Decimal("46.00"),
        default_waste_pct=Decimal("10.00"),
    )
    db_session.add(t)
    db_session.flush()

    items = [
        EstimateTemplateItem(
            template_id=t.id,
            description="Shingles",
            category="Roofing",
            unit_cost=Decimal("100.00"),
            uom="BD",
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("10.00"),
            measurement_type="total_area",
            conversion_factor=Decimal("3.0000"),
            sort_order=0,
        ),
        EstimateTemplateItem(
            template_id=t.id,
            description="Labor",
            category="Labor",
            unit_cost=Decimal("500.00"),
            margin_pct=Decimal("46.00"),
            waste_pct=Decimal("0.00"),
            measurement_type=None,
            conversion_factor=Decimal("1.0000"),
            default_qty=Decimal("1.00"),
            sort_order=1,
        ),
    ]
    db_session.add_all(items)
    db_session.commit()
    db_session.refresh(t)
    return t


def test_apply_template(
    client, auth_headers, job_with_estimate, template_for_apply
):
    resp = client.post(
        f"/api/estimates/{job_with_estimate.id}/apply-template",
        headers=auth_headers,
        json={
            "template_id": template_for_apply.id,
            "measurements": {"total_area": "10.0"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    # Should have 2 line items
    assert len(data["line_items"]) == 2

    # Shingles: 10 * 3 = 30, +10% = 33, ceil = 33
    # Sell price: 100 * 1.46 = 146.00
    # Total: 33 * 146.00 = 4818.00
    shingles = data["line_items"][0]
    assert shingles["description"] == "Shingles"
    assert int(Decimal(shingles["qty"])) == 33
    assert Decimal(shingles["unit_price"]) == Decimal("146.00")

    # Labor: qty 1, 500 * 1.46 = 730.00
    labor = data["line_items"][1]
    assert shingles["description"] == "Shingles"
    assert int(Decimal(labor["qty"])) == 1

    # Totals should be recalculated
    assert Decimal(data["subtotal"]) > Decimal("0")
    assert Decimal(data["total"]) > Decimal("0")


def test_apply_template_to_existing_items(
    client, auth_headers, job_with_estimate, template_for_apply, db_session
):
    """Applying a template appends to existing line items."""
    # Add an existing line item
    existing = EstimateLineItem(
        estimate_id=job_with_estimate.id,
        description="Existing Item",
        qty=Decimal("1"),
        unit_price=Decimal("100.00"),
        line_total=Decimal("100.00"),
        sort_order=0,
    )
    db_session.add(existing)
    db_session.commit()

    resp = client.post(
        f"/api/estimates/{job_with_estimate.id}/apply-template",
        headers=auth_headers,
        json={
            "template_id": template_for_apply.id,
            "measurements": {"total_area": "10.0"},
        },
    )
    assert resp.status_code == 200
    # 1 existing + 2 from template = 3
    assert len(resp.json()["line_items"]) == 3


def test_apply_template_not_found(client, auth_headers, job_with_estimate):
    resp = client.post(
        f"/api/estimates/{job_with_estimate.id}/apply-template",
        headers=auth_headers,
        json={
            "template_id": 99999,
            "measurements": {"total_area": "10.0"},
        },
    )
    assert resp.status_code == 404


def test_apply_template_estimate_not_found(
    client, auth_headers, template_for_apply
):
    resp = client.post(
        "/api/estimates/99999/apply-template",
        headers=auth_headers,
        json={
            "template_id": template_for_apply.id,
            "measurements": {"total_area": "10.0"},
        },
    )
    assert resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_apply_template.py -v`
Expected: FAIL — endpoint doesn't exist

**Step 3: Add the apply-template endpoint to estimates router**

In `backend/app/routers/estimates.py`, add these imports at the top:

```python
from app.models.estimate_template import EstimateTemplate
from app.models.estimate_template_item import EstimateTemplateItem
from app.schemas.estimate_template import ApplyTemplateRequest
from app.services.template_calculator import calculate_template_preview
from sqlalchemy.orm import joinedload as jl
```

Add this route **after** the `duplicate_estimate` endpoint but **before** the `reorder_line_items` endpoint (literal path `/apply-template` before parameterized `/{estimate_id}/line-items/...`):

```python
@router.post("/{estimate_id}/apply-template", response_model=EstimateResponse)
def apply_template(
    estimate_id: int,
    data: ApplyTemplateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    estimate = db.query(Estimate).filter(Estimate.id == estimate_id).first()
    if not estimate:
        raise HTTPException(status_code=404, detail="Estimate not found")

    template = (
        db.query(EstimateTemplate)
        .options(jl(EstimateTemplate.items))
        .filter(EstimateTemplate.id == data.template_id)
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Build measurements dict
    measurements = {}
    for field in ["total_area", "ridge", "hip", "valley", "eave", "rake"]:
        val = getattr(data.measurements, field)
        if val is not None:
            measurements[field] = val

    # Calculate from template items
    items_data = [
        {
            "description": item.description,
            "category": item.category,
            "unit_cost": item.unit_cost,
            "uom": item.uom,
            "margin_pct": item.margin_pct,
            "waste_pct": item.waste_pct,
            "measurement_type": item.measurement_type,
            "conversion_factor": item.conversion_factor,
            "default_qty": item.default_qty,
        }
        for item in sorted(template.items, key=lambda i: i.sort_order or 0)
    ]
    preview = calculate_template_preview(items_data, measurements)

    # Determine starting sort_order
    max_order = (
        db.query(EstimateLineItem.sort_order)
        .filter(EstimateLineItem.estimate_id == estimate_id)
        .order_by(EstimateLineItem.sort_order.desc())
        .first()
    )
    start_order = (max_order[0] or 0) + 1 if max_order else 0

    # Create line items from preview
    for idx, calc_item in enumerate(preview["items"]):
        line_item = EstimateLineItem(
            estimate_id=estimate_id,
            description=calc_item["description"],
            qty=Decimal(str(calc_item["qty"])),
            unit_price=calc_item["unit_price"],
            line_total=calc_item["line_total"],
            sort_order=start_order + idx,
        )
        db.add(line_item)

    db.commit()
    recalculate_estimate(db, estimate_id)

    estimate = _load_estimate(db, estimate_id)
    return _estimate_to_response(estimate)
```

**Step 4: Run tests to verify they pass**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest tests/test_apply_template.py -v`
Expected: All 4 tests PASS

**Step 5: Run full test suite**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest -v --tb=short`
Expected: All tests pass

**Step 6: Commit**

```bash
git add backend/app/routers/estimates.py backend/tests/test_apply_template.py
git commit -m "feat: add apply-template endpoint to estimates router with tests"
```

---

### Task 7: Frontend API Client

**Files:**
- Create: `frontend/src/api/estimateTemplates.js`

**Step 1: Create the API client**

Create `frontend/src/api/estimateTemplates.js`:

```javascript
import api from './client'

export const listTemplates = async () => {
  const { data } = await api.get('/estimate-templates')
  return data
}

export const getTemplate = async (id) => {
  const { data } = await api.get(`/estimate-templates/${id}`)
  return data
}

export const createTemplate = async (templateData) => {
  const { data } = await api.post('/estimate-templates', templateData)
  return data
}

export const updateTemplate = async (id, templateData) => {
  const { data } = await api.put(`/estimate-templates/${id}`, templateData)
  return data
}

export const deleteTemplate = async (id) => {
  await api.delete(`/estimate-templates/${id}`)
}

export const duplicateTemplate = async (id) => {
  const { data } = await api.post(`/estimate-templates/${id}/duplicate`)
  return data
}

export const addTemplateItem = async (templateId, itemData) => {
  const { data } = await api.post(`/estimate-templates/${templateId}/items`, itemData)
  return data
}

export const updateTemplateItem = async (templateId, itemId, itemData) => {
  const { data } = await api.put(`/estimate-templates/${templateId}/items/${itemId}`, itemData)
  return data
}

export const deleteTemplateItem = async (templateId, itemId) => {
  await api.delete(`/estimate-templates/${templateId}/items/${itemId}`)
}

export const reorderTemplateItems = async (templateId, itemIds) => {
  const { data } = await api.put(`/estimate-templates/${templateId}/items/reorder`, { item_ids: itemIds })
  return data
}

export const previewTemplate = async (templateId, measurements) => {
  const { data } = await api.post(`/estimate-templates/${templateId}/preview`, { ...measurements })
  return data
}

export const applyTemplate = async (estimateId, templateId, measurements) => {
  const { data } = await api.post(`/estimates/${estimateId}/apply-template`, {
    template_id: templateId,
    measurements,
  })
  return data
}
```

**Step 2: Commit**

```bash
git add frontend/src/api/estimateTemplates.js
git commit -m "feat: add frontend API client for estimate templates"
```

---

### Task 8: Frontend Templates List Page

**Files:**
- Create: `frontend/src/pages/TemplatesPage.jsx`
- Modify: `frontend/src/App.jsx` (add route)
- Modify: `frontend/src/components/Sidebar.jsx` (add nav item)

**Step 1: Create TemplatesPage**

Create `frontend/src/pages/TemplatesPage.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Plus, Copy, Trash2, Pencil } from 'lucide-react'
import { listTemplates, createTemplate, duplicateTemplate, deleteTemplate } from '../api/estimateTemplates'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'

export default function TemplatesPage() {
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleteId, setDeleteId] = useState(null)
  const navigate = useNavigate()
  const { addToast } = useToast()

  const fetchTemplates = async () => {
    try {
      const data = await listTemplates()
      setTemplates(data.items)
    } catch {
      addToast('Failed to load templates', 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTemplates()
  }, [])

  const handleCreate = async () => {
    try {
      const t = await createTemplate({ name: 'New Template' })
      navigate(`/templates/${t.id}`)
    } catch (err) {
      addToast(err.response?.data?.detail || 'Failed to create template', 'error')
    }
  }

  const handleDuplicate = async (id) => {
    try {
      const t = await duplicateTemplate(id)
      addToast('Template duplicated')
      navigate(`/templates/${t.id}`)
    } catch {
      addToast('Failed to duplicate', 'error')
    }
  }

  const handleDelete = async () => {
    if (!deleteId) return
    try {
      await deleteTemplate(deleteId)
      setDeleteId(null)
      fetchTemplates()
      addToast('Template deactivated')
    } catch {
      addToast('Failed to delete', 'error')
    }
  }

  if (loading) return <LoadingSpinner centered />

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Estimate Templates</h1>
          <p className="text-sm text-gray-500 mt-1">
            {templates.length} template{templates.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={handleCreate}
          className="flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-navy-900 font-semibold rounded-lg px-4 py-2.5 text-sm transition-colors"
        >
          <Plus size={16} />
          New Template
        </button>
      </div>

      {templates.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No templates yet"
          description="Create a template to speed up estimate generation"
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((t) => (
            <div
              key={t.id}
              className="bg-navy-800 rounded-xl border border-navy-700 p-5 hover:border-navy-600 transition-colors group"
            >
              <div className="flex items-start justify-between mb-3">
                <div
                  className="cursor-pointer flex-1 min-w-0"
                  onClick={() => navigate(`/templates/${t.id}`)}
                >
                  <h3 className="text-base font-semibold text-gray-100 truncate group-hover:text-amber-500 transition-colors">
                    {t.name}
                  </h3>
                  {t.description && (
                    <p className="text-xs text-gray-500 mt-1 truncate">{t.description}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 ml-2 shrink-0">
                  <button
                    onClick={() => navigate(`/templates/${t.id}`)}
                    className="p-1.5 text-gray-500 hover:text-amber-400 transition-colors"
                    title="Edit"
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    onClick={() => handleDuplicate(t.id)}
                    className="p-1.5 text-gray-500 hover:text-blue-400 transition-colors"
                    title="Duplicate"
                  >
                    <Copy size={14} />
                  </button>
                  <button
                    onClick={() => setDeleteId(t.id)}
                    className="p-1.5 text-gray-500 hover:text-red-400 transition-colors"
                    title="Deactivate"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>{t.item_count} item{t.item_count !== 1 ? 's' : ''}</span>
                <span className="font-mono">{parseFloat(t.default_margin_pct)}% margin</span>
                <span className="font-mono">{parseFloat(t.default_waste_pct)}% waste</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        isOpen={deleteId !== null}
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        title="Deactivate Template"
        message="This template will be hidden from the list. Are you sure?"
        confirmLabel="Deactivate"
        variant="danger"
      />
    </div>
  )
}
```

**Step 2: Add route to App.jsx**

In `frontend/src/App.jsx`, add the import:
```javascript
import TemplatesPage from './pages/TemplatesPage'
import TemplateBuilderPage from './pages/TemplateBuilderPage'
```

Add routes after the materials route (line 53):
```jsx
<Route path="/templates" element={<TemplatesPage />} />
<Route path="/templates/:id" element={<TemplateBuilderPage />} />
```

Note: TemplateBuilderPage will be created in Task 9. For now, just add the import and route — the build won't pass until Task 9 is done. If you prefer, add only the TemplatesPage route now and add the builder route in Task 9.

**Step 3: Add nav item to Sidebar**

In `frontend/src/components/Sidebar.jsx`, add `FileText` to the lucide-react imports.

Add to the JOBS navSection items array (after the Materials entry):
```javascript
{ to: '/templates', label: 'Templates', icon: FileText },
```

**Step 4: Commit** (Do NOT commit yet if TemplateBuilderPage import is missing — either stub the file or skip the builder import/route until Task 9)

Create a minimal stub for TemplateBuilderPage if needed:

`frontend/src/pages/TemplateBuilderPage.jsx`:
```jsx
export default function TemplateBuilderPage() {
  return <div className="text-gray-400">Loading template builder...</div>
}
```

**Step 5: Verify frontend builds**

Run: `cd /Users/iantitus/Desktop/legacy-crm/frontend && npm run build`
Expected: Build succeeds

**Step 6: Commit**

```bash
git add frontend/src/pages/TemplatesPage.jsx frontend/src/pages/TemplateBuilderPage.jsx frontend/src/App.jsx frontend/src/components/Sidebar.jsx
git commit -m "feat: add Templates list page with create, duplicate, and deactivate"
```

---

### Task 9: Template Builder Page

**Files:**
- Replace: `frontend/src/pages/TemplateBuilderPage.jsx`

**Step 1: Create the full Template Builder Page**

Replace `frontend/src/pages/TemplateBuilderPage.jsx` with the full implementation:

```jsx
import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2, Search, X } from 'lucide-react'
import {
  getTemplate,
  updateTemplate,
  addTemplateItem,
  updateTemplateItem,
  deleteTemplateItem,
} from '../api/estimateTemplates'
import { listMaterials } from '../api/materials'
import { useToast } from '../context/ToastContext'
import LoadingSpinner from '../components/LoadingSpinner'
import ConfirmDialog from '../components/ConfirmDialog'

const MEASUREMENT_TYPES = [
  { value: '', label: 'None (fixed qty)' },
  { value: 'total_area', label: 'Total Area (sq)' },
  { value: 'ridge', label: 'Ridge (LF)' },
  { value: 'hip', label: 'Hip (LF)' },
  { value: 'valley', label: 'Valley (LF)' },
  { value: 'eave', label: 'Eave (LF)' },
  { value: 'rake', label: 'Rake (LF)' },
]

const inputClass = 'bg-navy-900 border border-navy-700 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-amber-500 w-full'
const smallInputClass = 'bg-navy-900 border border-navy-700 rounded px-2 py-1.5 text-sm text-gray-200 font-mono text-right focus:outline-none focus:border-amber-500 w-full'

function MaterialPickerModal({ open, onClose, onSelect, onAddManual }) {
  const [materials, setMaterials] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    listMaterials({ search, perPage: 20 })
      .then((data) => setMaterials(data.items))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [open, search])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6 w-full max-w-2xl max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100">Add Item from Materials</h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={20} /></button>
        </div>

        <div className="relative mb-4">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search materials by name or item #..."
            className="w-full bg-navy-900 border border-navy-700 rounded-lg pl-9 pr-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500"
            autoFocus
          />
        </div>

        <div className="flex-1 overflow-y-auto min-h-0">
          {loading ? (
            <div className="flex justify-center py-8"><LoadingSpinner /></div>
          ) : materials.length === 0 ? (
            <p className="text-center text-gray-500 py-8 text-sm">No materials found</p>
          ) : (
            <div className="space-y-1">
              {materials.map((mat) => (
                <button
                  key={mat.id}
                  onClick={() => onSelect(mat)}
                  className="w-full flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-navy-700/50 transition-colors text-left"
                >
                  <div className="min-w-0">
                    <p className="text-sm text-gray-200 truncate">{mat.description}</p>
                    <p className="text-xs text-gray-500">{mat.item_number} &middot; {mat.category}</p>
                  </div>
                  <div className="text-right shrink-0 ml-4">
                    <p className="text-sm font-mono text-gray-200">
                      ${parseFloat(mat.unit_price).toFixed(2)}
                    </p>
                    <p className="text-xs text-gray-500">{mat.uom || '—'}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="pt-4 border-t border-navy-700 mt-4">
          <button
            onClick={onAddManual}
            className="w-full text-center text-sm text-amber-500 hover:text-amber-400 py-2 transition-colors"
          >
            + Add Manual Item (Labor, Custom, etc.)
          </button>
        </div>
      </div>
    </div>
  )
}

function ItemRow({ item, templateId, onUpdate, onDelete }) {
  const [values, setValues] = useState({})
  const { addToast } = useToast()

  useEffect(() => {
    setValues({
      description: item.description,
      category: item.category,
      unit_cost: item.unit_cost,
      uom: item.uom || '',
      margin_pct: item.margin_pct,
      waste_pct: item.waste_pct,
      measurement_type: item.measurement_type || '',
      conversion_factor: item.conversion_factor,
      default_qty: item.default_qty || '',
    })
  }, [item])

  const handleBlur = async (field) => {
    const newVal = values[field]
    const oldVal = field === 'measurement_type'
      ? (item[field] || '')
      : item[field]

    if (String(newVal) === String(oldVal ?? '')) return

    const payload = { [field]: newVal === '' && field === 'measurement_type' ? null : newVal }
    try {
      await updateTemplateItem(templateId, item.id, payload)
      onUpdate()
    } catch {
      addToast('Failed to update item', 'error')
    }
  }

  return (
    <tr className="border-b border-navy-700/50 hover:bg-navy-700/20 transition-colors group">
      <td className="px-2 py-2">
        <input
          className={inputClass}
          value={values.category || ''}
          onChange={(e) => setValues((v) => ({ ...v, category: e.target.value }))}
          onBlur={() => handleBlur('category')}
          style={{ minWidth: '80px' }}
        />
      </td>
      <td className="px-2 py-2">
        <input
          className={inputClass}
          value={values.description || ''}
          onChange={(e) => setValues((v) => ({ ...v, description: e.target.value }))}
          onBlur={() => handleBlur('description')}
          style={{ minWidth: '120px' }}
        />
      </td>
      <td className="px-2 py-2 w-24">
        <input
          type="number"
          step="0.01"
          className={smallInputClass}
          value={values.unit_cost || ''}
          onChange={(e) => setValues((v) => ({ ...v, unit_cost: e.target.value }))}
          onBlur={() => handleBlur('unit_cost')}
        />
      </td>
      <td className="px-2 py-2 w-16">
        <input
          className={inputClass + ' text-center'}
          value={values.uom || ''}
          onChange={(e) => setValues((v) => ({ ...v, uom: e.target.value }))}
          onBlur={() => handleBlur('uom')}
          style={{ minWidth: '40px' }}
        />
      </td>
      <td className="px-2 py-2 w-20">
        <input
          type="number"
          step="0.01"
          className={smallInputClass}
          value={values.margin_pct || ''}
          onChange={(e) => setValues((v) => ({ ...v, margin_pct: e.target.value }))}
          onBlur={() => handleBlur('margin_pct')}
        />
      </td>
      <td className="px-2 py-2 w-20">
        <input
          type="number"
          step="0.01"
          className={smallInputClass}
          value={values.waste_pct || ''}
          onChange={(e) => setValues((v) => ({ ...v, waste_pct: e.target.value }))}
          onBlur={() => handleBlur('waste_pct')}
        />
      </td>
      <td className="px-2 py-2 w-32">
        <select
          className={inputClass}
          value={values.measurement_type || ''}
          onChange={(e) => {
            setValues((v) => ({ ...v, measurement_type: e.target.value }))
            // Immediately save measurement_type changes
            const payload = { measurement_type: e.target.value || null }
            updateTemplateItem(templateId, item.id, payload).then(onUpdate).catch(() => {})
          }}
        >
          {MEASUREMENT_TYPES.map((mt) => (
            <option key={mt.value} value={mt.value}>{mt.label}</option>
          ))}
        </select>
      </td>
      <td className="px-2 py-2 w-20">
        <input
          type="number"
          step="0.0001"
          className={smallInputClass}
          value={values.conversion_factor || ''}
          onChange={(e) => setValues((v) => ({ ...v, conversion_factor: e.target.value }))}
          onBlur={() => handleBlur('conversion_factor')}
        />
      </td>
      <td className="px-2 py-2 w-20">
        <input
          type="number"
          step="0.01"
          className={smallInputClass}
          value={values.default_qty || ''}
          onChange={(e) => setValues((v) => ({ ...v, default_qty: e.target.value }))}
          onBlur={() => handleBlur('default_qty')}
          placeholder={values.measurement_type ? '—' : '0'}
          disabled={!!values.measurement_type}
        />
      </td>
      <td className="px-2 py-2 w-8">
        <button
          onClick={() => onDelete(item.id)}
          className="opacity-0 group-hover:opacity-100 text-gray-600 hover:text-red-400 transition-all p-1"
        >
          <Trash2 size={14} />
        </button>
      </td>
    </tr>
  )
}

export default function TemplateBuilderPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [template, setTemplate] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editingName, setEditingName] = useState(false)
  const [nameValue, setNameValue] = useState('')
  const [editingDesc, setEditingDesc] = useState(false)
  const [descValue, setDescValue] = useState('')
  const [showPicker, setShowPicker] = useState(false)
  const [deleteItemId, setDeleteItemId] = useState(null)

  const fetchTemplate = useCallback(async () => {
    try {
      const data = await getTemplate(id)
      setTemplate(data)
      setNameValue(data.name)
      setDescValue(data.description || '')
    } catch {
      addToast('Failed to load template', 'error')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchTemplate()
  }, [fetchTemplate])

  const handleNameSave = async () => {
    setEditingName(false)
    if (nameValue.trim() && nameValue.trim() !== template.name) {
      try {
        await updateTemplate(id, { name: nameValue.trim() })
        fetchTemplate()
      } catch (err) {
        addToast(err.response?.data?.detail || 'Failed to update name', 'error')
      }
    }
  }

  const handleDescSave = async () => {
    setEditingDesc(false)
    if (descValue !== (template.description || '')) {
      try {
        await updateTemplate(id, { description: descValue || null })
        fetchTemplate()
      } catch {
        addToast('Failed to update description', 'error')
      }
    }
  }

  const handleDefaultChange = async (field, value) => {
    try {
      await updateTemplate(id, { [field]: value })
      fetchTemplate()
    } catch {
      addToast('Failed to update default', 'error')
    }
  }

  const handleMaterialSelect = async (material) => {
    setShowPicker(false)
    try {
      await addTemplateItem(id, {
        material_id: material.id,
        description: material.description,
        category: material.category,
        unit_cost: material.unit_price,
        uom: material.uom,
      })
      fetchTemplate()
    } catch {
      addToast('Failed to add item', 'error')
    }
  }

  const handleAddManual = async () => {
    setShowPicker(false)
    try {
      await addTemplateItem(id, {
        description: 'New Item',
        category: 'Labor',
        unit_cost: '0.00',
        waste_pct: '0.00',
      })
      fetchTemplate()
    } catch {
      addToast('Failed to add item', 'error')
    }
  }

  const handleDeleteItem = async () => {
    if (!deleteItemId) return
    try {
      await deleteTemplateItem(id, deleteItemId)
      setDeleteItemId(null)
      fetchTemplate()
    } catch {
      addToast('Failed to delete item', 'error')
    }
  }

  if (loading) return <LoadingSpinner centered />
  if (!template) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-400">Template not found</p>
        <button onClick={() => navigate('/templates')} className="text-amber-500 hover:text-amber-400 mt-2 text-sm">
          Back to templates
        </button>
      </div>
    )
  }

  const items = template.items || []

  return (
    <div>
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
        <Link to="/templates" className="hover:text-gray-300 transition-colors">Templates</Link>
        <span>/</span>
        <span className="text-gray-300">{template.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/templates')}
            className="p-2 text-gray-400 hover:text-gray-200 hover:bg-navy-800 rounded-lg transition-colors"
          >
            <ArrowLeft size={20} />
          </button>
          <div>
            {editingName ? (
              <input
                type="text"
                value={nameValue}
                onChange={(e) => setNameValue(e.target.value)}
                onBlur={handleNameSave}
                onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') { setNameValue(template.name); setEditingName(false) } }}
                className="text-2xl font-bold bg-navy-800 border border-navy-600 rounded-lg px-3 py-1 text-gray-100 focus:outline-none focus:ring-2 focus:ring-amber-500/50"
                autoFocus
              />
            ) : (
              <h1
                onClick={() => setEditingName(true)}
                className="text-2xl font-bold text-gray-100 cursor-text hover:text-amber-500 transition-colors"
              >
                {template.name}
              </h1>
            )}
            {editingDesc ? (
              <input
                type="text"
                value={descValue}
                onChange={(e) => setDescValue(e.target.value)}
                onBlur={handleDescSave}
                onKeyDown={(e) => { if (e.key === 'Enter') e.target.blur(); if (e.key === 'Escape') { setDescValue(template.description || ''); setEditingDesc(false) } }}
                className="mt-1 text-sm bg-navy-800 border border-navy-600 rounded px-2 py-1 text-gray-400 focus:outline-none focus:ring-1 focus:ring-amber-500/50 w-64"
                placeholder="Add description..."
                autoFocus
              />
            ) : (
              <p
                onClick={() => setEditingDesc(true)}
                className="text-sm text-gray-500 mt-0.5 cursor-text hover:text-gray-300 transition-colors"
              >
                {template.description || 'Click to add description...'}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Defaults Bar */}
      <div className="flex items-center gap-6 mb-6 bg-navy-800 rounded-xl border border-navy-700 px-5 py-3">
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">Default Margin %</label>
          <input
            type="number"
            step="0.01"
            className="bg-navy-900 border border-navy-700 rounded px-2 py-1 text-sm font-mono text-gray-200 w-20 text-right focus:outline-none focus:border-amber-500"
            defaultValue={parseFloat(template.default_margin_pct)}
            onBlur={(e) => handleDefaultChange('default_margin_pct', e.target.value)}
          />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">Default Waste %</label>
          <input
            type="number"
            step="0.01"
            className="bg-navy-900 border border-navy-700 rounded px-2 py-1 text-sm font-mono text-gray-200 w-20 text-right focus:outline-none focus:border-amber-500"
            defaultValue={parseFloat(template.default_waste_pct)}
            onBlur={(e) => handleDefaultChange('default_waste_pct', e.target.value)}
          />
        </div>
        <div className="text-xs text-gray-500 ml-auto">
          {items.length} item{items.length !== 1 ? 's' : ''}
        </div>
      </div>

      {/* Items Table */}
      <div className="bg-navy-800 rounded-xl overflow-x-auto border border-navy-700 mb-4">
        <table className="w-full">
          <thead>
            <tr className="border-b border-navy-700">
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">Category</th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">Description</th>
              <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">Cost</th>
              <th className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">UOM</th>
              <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">Margin%</th>
              <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">Waste%</th>
              <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">Measurement</th>
              <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">Conv.</th>
              <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wider px-2 py-2.5">Def Qty</th>
              <th className="w-8 px-2 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={10} className="text-center text-gray-500 text-sm py-8">
                  No items yet — click "Add Item" to get started
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <ItemRow
                  key={item.id}
                  item={item}
                  templateId={id}
                  onUpdate={fetchTemplate}
                  onDelete={setDeleteItemId}
                />
              ))
            )}
          </tbody>
        </table>

        <button
          onClick={() => setShowPicker(true)}
          className="flex items-center gap-2 w-full px-3 py-2.5 text-sm text-gray-500 hover:text-amber-500 hover:bg-navy-700/30 transition-colors border-t border-navy-700"
        >
          <Plus size={14} />
          Add Item
        </button>
      </div>

      <MaterialPickerModal
        open={showPicker}
        onClose={() => setShowPicker(false)}
        onSelect={handleMaterialSelect}
        onAddManual={handleAddManual}
      />

      <ConfirmDialog
        isOpen={deleteItemId !== null}
        onConfirm={handleDeleteItem}
        onCancel={() => setDeleteItemId(null)}
        title="Delete Item"
        message="Remove this item from the template?"
        confirmLabel="Delete"
        variant="danger"
      />
    </div>
  )
}
```

**Step 2: Verify frontend builds**

Run: `cd /Users/iantitus/Desktop/legacy-crm/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/pages/TemplateBuilderPage.jsx
git commit -m "feat: add Template Builder page with material picker and inline editing"
```

---

### Task 10: Apply Template Modal on EstimateDetailPage

**Files:**
- Modify: `frontend/src/pages/EstimateDetailPage.jsx`

**Step 1: Add ApplyTemplateModal and integrate into EstimateDetailPage**

In `frontend/src/pages/EstimateDetailPage.jsx`, add these imports at the top:

```javascript
import { FileText, X, Search } from 'lucide-react'
import { listTemplates, previewTemplate, applyTemplate } from '../api/estimateTemplates'
```

Add the `ApplyTemplateModal` component definition **before** the `EstimateDetailPage` export:

```jsx
const formatCurrency = (value) => {
  if (!value && value !== 0) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(value)
}

function ApplyTemplateModal({ open, onClose, estimateId, onApplied }) {
  const [templates, setTemplates] = useState([])
  const [selectedId, setSelectedId] = useState('')
  const [measurements, setMeasurements] = useState({
    total_area: '',
    ridge: '',
    hip: '',
    valley: '',
    eave: '',
    rake: '',
  })
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const { addToast } = useToast()

  useEffect(() => {
    if (!open) return
    listTemplates().then((d) => setTemplates(d.items)).catch(() => {})
    setSelectedId('')
    setMeasurements({ total_area: '', ridge: '', hip: '', valley: '', eave: '', rake: '' })
    setPreview(null)
  }, [open])

  const handlePreview = async () => {
    if (!selectedId) return
    setLoading(true)
    try {
      const m = {}
      for (const [k, v] of Object.entries(measurements)) {
        if (v !== '' && v !== null) m[k] = v
      }
      const data = await previewTemplate(selectedId, { measurements: m })
      setPreview(data)
    } catch {
      addToast('Failed to generate preview', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleApply = async () => {
    if (!selectedId) return
    setApplying(true)
    try {
      const m = {}
      for (const [k, v] of Object.entries(measurements)) {
        if (v !== '' && v !== null) m[k] = v
      }
      await applyTemplate(estimateId, selectedId, m)
      addToast('Template applied successfully')
      onApplied()
      onClose()
    } catch {
      addToast('Failed to apply template', 'error')
    } finally {
      setApplying(false)
    }
  }

  if (!open) return null

  const measurementFields = [
    { key: 'total_area', label: 'Total Area', unit: 'squares' },
    { key: 'ridge', label: 'Ridge Length', unit: 'LF' },
    { key: 'hip', label: 'Hip Length', unit: 'LF' },
    { key: 'valley', label: 'Valley Length', unit: 'LF' },
    { key: 'eave', label: 'Eave Length', unit: 'LF' },
    { key: 'rake', label: 'Rake Length', unit: 'LF' },
  ]

  // Determine which measurement types the selected template uses
  const selectedTemplate = templates.find((t) => t.id === Number(selectedId))
  const usedTypes = new Set(
    (selectedTemplate?.items || [])
      .map((i) => i.measurement_type)
      .filter(Boolean)
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-navy-800 rounded-xl border border-navy-700 p-6 w-full max-w-3xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
            <FileText size={20} className="text-amber-500" />
            Apply Template
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={20} /></button>
        </div>

        {/* Step 1: Select Template */}
        <div className="mb-4">
          <label className="block text-xs text-gray-500 mb-1">Template</label>
          <select
            value={selectedId}
            onChange={(e) => { setSelectedId(e.target.value); setPreview(null) }}
            className="w-full bg-navy-900 border border-navy-700 rounded-lg px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-amber-500"
          >
            <option value="">Select a template...</option>
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.name} ({t.item_count} items)</option>
            ))}
          </select>
        </div>

        {/* Step 2: Measurements */}
        {selectedId && (
          <div className="mb-4">
            <label className="block text-xs text-gray-500 mb-2">Roof Measurements</label>
            <div className="grid grid-cols-3 gap-3">
              {measurementFields.map(({ key, label, unit }) => (
                <div key={key}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className="text-xs text-gray-400">{label}</span>
                    {usedTypes.has(key) && (
                      <span className="text-[10px] text-amber-500 font-medium">REQUIRED</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <input
                      type="number"
                      step="0.1"
                      value={measurements[key]}
                      onChange={(e) => setMeasurements((m) => ({ ...m, [key]: e.target.value }))}
                      className="flex-1 bg-navy-900 border border-navy-700 rounded px-2 py-1.5 text-sm text-gray-200 font-mono text-right focus:outline-none focus:border-amber-500"
                      placeholder="0"
                    />
                    <span className="text-xs text-gray-500 w-10">{unit}</span>
                  </div>
                </div>
              ))}
            </div>
            <button
              onClick={handlePreview}
              disabled={loading}
              className="mt-3 px-4 py-2 bg-navy-700 hover:bg-navy-600 text-gray-200 text-sm rounded-lg transition-colors disabled:opacity-50"
            >
              {loading ? 'Calculating...' : 'Preview'}
            </button>
          </div>
        )}

        {/* Step 3: Preview */}
        {preview && (
          <div className="flex-1 overflow-y-auto min-h-0 mb-4">
            <div className="bg-navy-900 rounded-lg border border-navy-700 overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-navy-700">
                    <th className="text-left text-xs font-medium text-gray-500 uppercase px-3 py-2">Description</th>
                    <th className="text-left text-xs font-medium text-gray-500 uppercase px-3 py-2">Category</th>
                    <th className="text-right text-xs font-medium text-gray-500 uppercase px-3 py-2">Qty</th>
                    <th className="text-right text-xs font-medium text-gray-500 uppercase px-3 py-2">Unit Price</th>
                    <th className="text-right text-xs font-medium text-gray-500 uppercase px-3 py-2">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-700/50">
                  {preview.items.map((item, idx) => (
                    <tr key={idx}>
                      <td className="px-3 py-2 text-sm text-gray-200">{item.description}</td>
                      <td className="px-3 py-2 text-sm text-gray-400">{item.category}</td>
                      <td className="px-3 py-2 text-sm font-mono text-gray-300 text-right">
                        {item.qty} {item.uom || ''}
                      </td>
                      <td className="px-3 py-2 text-sm font-mono text-gray-300 text-right">
                        {formatCurrency(item.unit_price)}
                      </td>
                      <td className="px-3 py-2 text-sm font-mono text-gray-100 text-right">
                        {formatCurrency(item.line_total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="flex justify-between items-center px-3 py-2.5 border-t border-navy-700 bg-navy-800/50">
                <span className="text-sm text-gray-400">{preview.item_count} items</span>
                <span className="text-base font-mono font-bold text-amber-500">
                  {formatCurrency(preview.subtotal)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Apply */}
        {preview && (
          <button
            onClick={handleApply}
            disabled={applying}
            className="w-full bg-amber-500 hover:bg-amber-600 disabled:opacity-50 text-navy-900 font-semibold rounded-lg py-2.5 transition-colors"
          >
            {applying ? 'Applying...' : `Apply ${preview.item_count} Items to Estimate`}
          </button>
        )}
      </div>
    </div>
  )
}
```

Then add the ApplyTemplateModal state and button to the `EstimateDetailPage` component:

Add state near top of `EstimateDetailPage`:
```javascript
const [showApplyTemplate, setShowApplyTemplate] = useState(false)
```

Add the "Apply Template" button in the header area, next to the Duplicate button:
```jsx
<button
  onClick={() => setShowApplyTemplate(true)}
  className="flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-gray-200 hover:bg-navy-800 rounded-lg transition-colors"
>
  <FileText size={16} />
  Apply Template
</button>
```

Add the modal at the bottom, before the closing `</div>`:
```jsx
<ApplyTemplateModal
  open={showApplyTemplate}
  onClose={() => setShowApplyTemplate(false)}
  estimateId={id}
  onApplied={fetchEstimate}
/>
```

**Step 2: Verify frontend builds**

Run: `cd /Users/iantitus/Desktop/legacy-crm/frontend && npm run build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add frontend/src/pages/EstimateDetailPage.jsx
git commit -m "feat: add Apply Template modal to EstimateDetailPage with live preview"
```

---

### Task 11: Final Integration Test & Full Suite

**Step 1: Run the full backend test suite**

Run: `cd /Users/iantitus/Desktop/legacy-crm/backend && python -m pytest -v --tb=short`
Expected: All tests pass (280 original + ~32 new = ~312+)

**Step 2: Verify frontend builds clean**

Run: `cd /Users/iantitus/Desktop/legacy-crm/frontend && npm run build`
Expected: Build succeeds

**Step 3: If any fixes were needed, commit them**

```bash
git add -A && git commit -m "fix: resolve any Sprint 9b integration issues"
```
