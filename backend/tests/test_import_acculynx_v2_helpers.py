"""Unit tests for pure-function helpers in import_acculynx_v2.

Integration testing (end-to-end CSV → DB) is done manually against a prod
DB backup, not in this suite.
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

# The script lives in backend/scripts/, not on the default test path.
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.abspath(os.path.join(HERE, "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import import_acculynx_v2 as importer  # noqa: E402


def test_parse_address_standard():
    assert importer.parse_address("214 Larkspur Drive, Kokomo, IN 46901 US") == (
        "214 Larkspur Drive", "Kokomo", "IN", "46901"
    )


def test_parse_address_no_us_suffix():
    assert importer.parse_address("123 Main St, Indianapolis, IN 46201") == (
        "123 Main St", "Indianapolis", "IN", "46201"
    )


def test_parse_address_zip_plus_four():
    assert importer.parse_address("99 Test Rd, Kokomo, IN 46901-1234 US") == (
        "99 Test Rd", "Kokomo", "IN", "46901-1234"
    )


def test_parse_address_empty():
    assert importer.parse_address("") == (None, None, None, None)


def test_parse_address_none():
    assert importer.parse_address(None) == (None, None, None, None)


def test_parse_address_street_with_comma():
    # Streets with units use commas inside the street segment
    assert importer.parse_address(
        "100 Main St, Apt 5, Kokomo, IN 46901 US"
    ) == ("100 Main St, Apt 5", "Kokomo", "IN", "46901")


def test_parse_address_unparseable_falls_back_to_street():
    assert importer.parse_address("Just a free-form address") == (
        "Just a free-form address", None, None, None
    )


def test_parse_date_short_year():
    result = importer.parse_date("4/8/26")
    assert result == datetime(2026, 4, 8, tzinfo=timezone.utc)


def test_parse_date_short_year_with_time():
    result = importer.parse_date("4/8/26 12:00 AM")
    assert result == datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc)


def test_parse_date_full_year():
    result = importer.parse_date("4/8/2026")
    assert result == datetime(2026, 4, 8, tzinfo=timezone.utc)


def test_parse_date_empty():
    assert importer.parse_date("") is None
    assert importer.parse_date(None) is None
    assert importer.parse_date("   ") is None


def test_parse_date_unparseable():
    assert importer.parse_date("not a date") is None


def test_digits_only_formatted_phone():
    assert importer.digits_only("(765) 555-0119") == "7655550119"


def test_digits_only_unformatted():
    assert importer.digits_only("3175550188") == "3175550188"


def test_digits_only_empty():
    assert importer.digits_only("") == ""
    assert importer.digits_only(None) == ""


def test_normalize_name_collapses_double_space():
    assert importer.normalize_name("Teresa  Murphy") == "teresa murphy"


def test_normalize_name_strips_and_lowercases():
    assert importer.normalize_name("  Nora Whitfield  ") == "nora whitfield"


def test_normalize_name_empty():
    assert importer.normalize_name("") == ""
    assert importer.normalize_name(None) == ""


def test_normalize_email():
    assert importer.normalize_email("  Foo@BAR.com  ") == "foo@bar.com"
    assert importer.normalize_email("") == ""
    assert importer.normalize_email(None) == ""


def test_consolidate_lead_source_passthrough():
    assert importer.consolidate_lead_source("Google LSA") == "Google LSA"
    assert importer.consolidate_lead_source("Self Generated") == "Self Generated"
    assert importer.consolidate_lead_source("Referral") == "Referral"
    assert importer.consolidate_lead_source("Word of Mouth") == "Word of Mouth"
    assert importer.consolidate_lead_source("Facebook") == "Facebook"
    assert importer.consolidate_lead_source("Yard Sign") == "Yard Sign"
    assert importer.consolidate_lead_source("Other") == "Other"


def test_consolidate_lead_source_consolidates_to_referral():
    assert importer.consolidate_lead_source("Realtor") == "Referral"
    assert importer.consolidate_lead_source("Property Manager") == "Referral"


def test_consolidate_lead_source_empty():
    assert importer.consolidate_lead_source("") is None
    assert importer.consolidate_lead_source(None) is None


def test_consolidate_lead_source_unknown_passes_through():
    # Unknown values are kept as-is rather than dropped — they may be
    # valid sources Dale added later that we don't have in our map.
    assert importer.consolidate_lead_source("Some New Source") == "Some New Source"


def test_map_invoice_status_paid():
    assert importer.map_invoice_status("Paid") == "paid"


def test_map_invoice_status_unpaid():
    assert importer.map_invoice_status("Unpaid") == "sent"


def test_map_invoice_status_draft():
    assert importer.map_invoice_status("Draft") == "draft"


def test_map_invoice_status_case_insensitive():
    assert importer.map_invoice_status("paid") == "paid"
    assert importer.map_invoice_status("  PAID  ") == "paid"


def test_map_invoice_status_unknown_defaults_to_draft():
    assert importer.map_invoice_status("Weird") == "draft"
    assert importer.map_invoice_status("") == "draft"
    assert importer.map_invoice_status(None) == "draft"


def test_resolve_milestone_assigned_lead():
    assert importer.resolve_milestone_stage("Assigned Lead") == (
        "leads", "Warm Leads", False
    )


def test_resolve_milestone_prospect():
    # Prospect should land in the prod-only Sales stage, no estimate
    assert importer.resolve_milestone_stage("Prospect") == (
        "sales", "Estimate Pending Schedule", False
    )


def test_resolve_milestone_approved():
    # Approved+ milestones create an Estimate (third tuple element True)
    assert importer.resolve_milestone_stage("Approved") == (
        "jobs", "In Progress", True
    )


def test_resolve_milestone_completed():
    assert importer.resolve_milestone_stage("Completed") == (
        "jobs", "Complete", True
    )


def test_resolve_milestone_invoiced():
    assert importer.resolve_milestone_stage("Invoiced") == (
        "jobs", "Complete", True
    )


def test_resolve_milestone_closed():
    assert importer.resolve_milestone_stage("Closed") == (
        "jobs", "Closed", True
    )


def test_resolve_milestone_unknown_defaults_to_leads_cold():
    assert importer.resolve_milestone_stage("Weird") == (
        "leads", "Cold Leads", False
    )
    assert importer.resolve_milestone_stage("") == (
        "leads", "Cold Leads", False
    )
    assert importer.resolve_milestone_stage(None) == (
        "leads", "Cold Leads", False
    )


def test_parse_ar_age_job_name_standard():
    assert importer.parse_ar_age_job_name("1088: Kelsey Bass") == "Kelsey Bass"


def test_parse_ar_age_job_name_double_space():
    # AR Age has internal double spaces; normalize them
    assert importer.parse_ar_age_job_name("1088: Kelsey  Bass") == "Kelsey Bass"


def test_parse_ar_age_job_name_no_colon():
    # No colon — return the whole thing trimmed
    assert importer.parse_ar_age_job_name("Just A Name") == "Just A Name"


def test_parse_ar_age_job_name_empty():
    assert importer.parse_ar_age_job_name("") is None
    assert importer.parse_ar_age_job_name(None) is None


def test_safe_decimal_normal():
    assert importer.safe_decimal("8615.40") == Decimal("8615.40")


def test_safe_decimal_with_commas():
    # Some AccuLynx exports include thousands separators
    assert importer.safe_decimal("8,615.40") == Decimal("8615.40")


def test_safe_decimal_with_dollar_sign():
    assert importer.safe_decimal("$8,615.40") == Decimal("8615.40")


def test_safe_decimal_empty():
    assert importer.safe_decimal("") == Decimal("0")
    assert importer.safe_decimal(None) == Decimal("0")


def test_safe_decimal_invalid():
    assert importer.safe_decimal("not a number") == Decimal("0")


def test_safe_decimal_zero():
    assert importer.safe_decimal("0") == Decimal("0")
    assert importer.safe_decimal("0.00") == Decimal("0")
