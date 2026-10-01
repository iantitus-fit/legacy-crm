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
        "\u2018GHI789,Test Starter,47.21,BD,Starter Strip,Mastic Siding/Trim,\n"
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
