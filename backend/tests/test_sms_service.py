"""Sprint 17a — SMS service tests.

All Twilio API calls are mocked. No real HTTP requests are made.
"""
from datetime import datetime, time
from unittest.mock import MagicMock, patch

import pytest

from app.models.contact import Contact
from app.models.sms import SmsConfig, SmsMessage
from app.services import sms_service
from app.services.phone_utils import (
    format_for_display,
    match_phone,
    normalize_to_e164,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def sms_env(monkeypatch):
    """Enable SMS and provide fake Twilio credentials."""
    monkeypatch.setenv("SMS_ENABLED", "true")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token-xyz")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+18335550199")
    yield


@pytest.fixture()
def mock_twilio():
    """Patch get_twilio_client to return a stub. Yields the messages.create mock."""
    fake_message = MagicMock(sid="SMtest12345", status="queued")
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_message
    with patch(
        "app.services.sms_service.get_twilio_client", return_value=fake_client
    ) as mocked:
        yield fake_client.messages.create


@pytest.fixture()
def contact_with_phone(db_session):
    c = Contact(name="Alice Carter", phone="(765) 555-0181")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture()
def opted_out_contact(db_session):
    c = Contact(name="Bob Optout", phone="(765) 555-0199", sms_opt_out=True)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw",
    [
        "(765) 555-0181",
        "765-555-0181",
        "7655550181",
        "+17655550181",
        "1-765-555-0181",
        "765.555.0181",
        " 765 555 0181 ",
    ],
)
def test_normalize_phone_formats(raw):
    assert normalize_to_e164(raw) == "+17655550181"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        None,
        "abc",
        "12345",
        "999999999999",
        "065-555-0181",  # area code starts with 0
        "165-555-0181",  # area code starts with 1
        "765-055-0181",  # exchange starts with 0
    ],
)
def test_normalize_phone_invalid(raw):
    assert normalize_to_e164(raw) is None


def test_format_for_display():
    assert format_for_display("+17655550181") == "(765) 555-0181"
    assert format_for_display("7655550181") == "(765) 555-0181"


def test_phone_match():
    assert match_phone("(765) 555-0181", "+17655550181") is True
    assert match_phone("765-555-0181", "7655550181") is True
    assert match_phone("1-765-555-0181", "(765) 555-0181") is True
    assert match_phone("(765) 555-0181", "(317) 555-0181") is False
    assert match_phone(None, "+17655550181") is False
    assert match_phone("not a phone", "+17655550181") is False


# ---------------------------------------------------------------------------
# Send SMS
# ---------------------------------------------------------------------------
def test_send_sms_creates_record(
    db_session, contact_with_phone, sms_env, mock_twilio
):
    msg = sms_service.send_sms(db_session, contact_with_phone.id, "Hello!")

    assert msg.id is not None
    assert msg.direction == "outbound"
    assert msg.body == "Hello!"
    assert msg.to_number == "+17655550181"
    assert msg.from_number == "+18335550199"
    assert msg.twilio_sid == "SMtest12345"
    assert msg.status == "queued"
    assert msg.triggered_by == "manual"
    mock_twilio.assert_called_once_with(
        to="+17655550181", from_="+18335550199", body="Hello!"
    )


def test_send_sms_opt_out_refused(db_session, opted_out_contact, sms_env):
    with pytest.raises(ValueError, match="opted out"):
        sms_service.send_sms(db_session, opted_out_contact.id, "Hi")


def test_send_sms_no_phone_refused(db_session, sms_env):
    contact = Contact(name="No Phone")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    with pytest.raises(ValueError, match="no phone"):
        sms_service.send_sms(db_session, contact.id, "Hi")


def test_send_sms_missing_contact(db_session, sms_env):
    with pytest.raises(ValueError, match="not found"):
        sms_service.send_sms(db_session, 9999, "Hi")


def test_send_sms_disabled_records_failed(
    db_session, contact_with_phone, monkeypatch
):
    monkeypatch.setenv("SMS_ENABLED", "false")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+18335550199")

    msg = sms_service.send_sms(db_session, contact_with_phone.id, "Hello!")
    assert msg.status == "failed"
    assert "SMS_ENABLED" in (msg.status_detail or "")


# ---------------------------------------------------------------------------
# Receive SMS
# ---------------------------------------------------------------------------
def test_receive_sms_matches_contact(db_session, contact_with_phone):
    msg = sms_service.receive_sms(
        db_session,
        from_number="+17655550181",
        to_number="+18335550199",
        body="Hey there",
        twilio_sid="SMinbound01",
    )
    assert msg.contact_id == contact_with_phone.id
    assert msg.direction == "inbound"
    assert msg.body == "Hey there"
    assert msg.status == "received"
    assert msg.twilio_sid == "SMinbound01"


def test_receive_sms_matches_contact_with_messy_stored_format(db_session):
    contact = Contact(name="Messy Phone", phone="765.555.0144")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    msg = sms_service.receive_sms(
        db_session,
        from_number="+17655550144",
        to_number="+18335550199",
        body="Test",
    )
    assert msg.contact_id == contact.id


def test_receive_sms_unknown_creates_contact(db_session):
    msg = sms_service.receive_sms(
        db_session,
        from_number="+13175550199",
        to_number="+18335550199",
        body="Hi from a stranger",
    )
    contact = db_session.query(Contact).filter(Contact.id == msg.contact_id).first()
    assert contact is not None
    assert "Unknown" in contact.name
    assert "(317) 555-0199" in contact.name
    assert contact.phone == "(317) 555-0199"


def test_receive_sms_opt_out(db_session, contact_with_phone):
    sms_service.receive_sms(
        db_session,
        from_number="+17655550181",
        to_number="+18335550199",
        body="STOP",
    )
    db_session.refresh(contact_with_phone)
    assert contact_with_phone.sms_opt_out is True
    assert contact_with_phone.sms_opt_out_at is not None


def test_receive_sms_opt_out_case_insensitive(db_session, contact_with_phone):
    sms_service.receive_sms(
        db_session,
        from_number="+17655550181",
        to_number="+18335550199",
        body="  Stop  ",
    )
    db_session.refresh(contact_with_phone)
    assert contact_with_phone.sms_opt_out is True


def test_receive_sms_opt_in(db_session, opted_out_contact):
    sms_service.receive_sms(
        db_session,
        from_number="+17655550199",
        to_number="+18335550199",
        body="START",
    )
    db_session.refresh(opted_out_contact)
    assert opted_out_contact.sms_opt_out is False
    assert opted_out_contact.sms_opt_out_at is None


def test_receive_sms_help_triggers_response(
    db_session, contact_with_phone, sms_env, mock_twilio
):
    sms_service.receive_sms(
        db_session,
        from_number="+17655550181",
        to_number="+18335550199",
        body="HELP",
    )
    # One outbound message — the help_response — and one inbound HELP.
    outbound = (
        db_session.query(SmsMessage)
        .filter(SmsMessage.contact_id == contact_with_phone.id)
        .filter(SmsMessage.direction == "outbound")
        .all()
    )
    assert len(outbound) == 1
    assert "Legacy Roofing" in outbound[0].body
    assert outbound[0].triggered_by == "auto_help_response"


# ---------------------------------------------------------------------------
# Auto-respond new lead
# ---------------------------------------------------------------------------
def _set_business_hours(config, start=time(8, 0), end=time(18, 0)):
    config.business_hours_start = start
    config.business_hours_end = end


def test_auto_respond_new_lead_during_business_hours(
    db_session, contact_with_phone, sms_env, mock_twilio
):
    config = sms_service.ensure_sms_config(db_session)
    # Force business hours to bracket "now" so the test isn't time-of-day dependent.
    _set_business_hours(config, time(0, 0), time(23, 59, 59))
    db_session.commit()

    msg = sms_service.auto_respond_new_lead(db_session, contact_with_phone.id)
    assert msg is not None
    assert msg.triggered_by == "auto_new_lead"
    assert "Alice" in msg.body  # {first_name} rendered


def test_auto_respond_new_lead_after_hours(
    db_session, contact_with_phone, sms_env, mock_twilio
):
    config = sms_service.ensure_sms_config(db_session)
    # Force "now" to be outside business hours.
    _set_business_hours(config, time(0, 0), time(0, 1))
    db_session.commit()

    msg = sms_service.auto_respond_new_lead(db_session, contact_with_phone.id)
    assert msg is not None
    assert msg.triggered_by == "auto_new_lead_after_hours"
    assert "closed for the day" in msg.body


def test_auto_respond_disabled_toggle(
    db_session, contact_with_phone, sms_env, mock_twilio
):
    config = sms_service.ensure_sms_config(db_session)
    config.auto_respond_new_lead = False
    db_session.commit()

    assert sms_service.auto_respond_new_lead(db_session, contact_with_phone.id) is None
    mock_twilio.assert_not_called()


def test_auto_respond_after_hours_toggle_off_skips_send(
    db_session, contact_with_phone, sms_env, mock_twilio
):
    config = sms_service.ensure_sms_config(db_session)
    _set_business_hours(config, time(0, 0), time(0, 1))
    config.auto_respond_after_hours = False
    db_session.commit()

    assert sms_service.auto_respond_new_lead(db_session, contact_with_phone.id) is None
    mock_twilio.assert_not_called()


def test_auto_respond_kill_switch(db_session, contact_with_phone, monkeypatch):
    monkeypatch.setenv("SMS_ENABLED", "false")
    assert sms_service.auto_respond_new_lead(db_session, contact_with_phone.id) is None


def test_auto_respond_no_phone(db_session, sms_env, mock_twilio):
    contact = Contact(name="No Phone Lead")
    db_session.add(contact)
    db_session.commit()
    db_session.refresh(contact)

    assert sms_service.auto_respond_new_lead(db_session, contact.id) is None
    mock_twilio.assert_not_called()


def test_auto_respond_opted_out(db_session, opted_out_contact, sms_env, mock_twilio):
    assert sms_service.auto_respond_new_lead(db_session, opted_out_contact.id) is None
    mock_twilio.assert_not_called()


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------
def test_render_template_tokens(db_session):
    contact = Contact(name="Alice Carter", company="Acme Roofing")
    result = sms_service.render_template(
        "Hi {first_name} {last_name} from {company_name}, "
        "your rep is {rep_name}. URL: {estimate_url}",
        contact,
        rep_name="Dale",
        estimate_url="https://example.com/e/abc",
    )
    assert result == (
        "Hi Alice Carter from Acme Roofing, your rep is Dale. "
        "URL: https://example.com/e/abc"
    )


def test_render_template_missing_token(db_session):
    contact = Contact(name="Alice")
    result = sms_service.render_template(
        "Hi {first_name}, your URL is {estimate_url}.", contact
    )
    assert result == "Hi Alice, your URL is ."


def test_render_template_no_contact():
    result = sms_service.render_template(
        "Hi {first_name}, contact rep {rep_name}", rep_name="Marcus"
    )
    assert result == "Hi , contact rep Marcus"


# ---------------------------------------------------------------------------
# Business hours
# ---------------------------------------------------------------------------
def test_is_business_hours_boundaries(db_session):
    config = sms_service.ensure_sms_config(db_session)
    config.business_hours_start = time(8, 0)
    config.business_hours_end = time(18, 0)
    config.business_timezone = "America/Indiana/Indianapolis"
    db_session.commit()

    tz_aware = lambda h, m: datetime(2026, 5, 17, h, m).replace(tzinfo=None)

    assert sms_service.is_business_hours(config, tz_aware(8, 0)) is True
    assert sms_service.is_business_hours(config, tz_aware(12, 30)) is True
    assert sms_service.is_business_hours(config, tz_aware(17, 59)) is True
    assert sms_service.is_business_hours(config, tz_aware(18, 0)) is False
    assert sms_service.is_business_hours(config, tz_aware(18, 1)) is False
    assert sms_service.is_business_hours(config, tz_aware(7, 59)) is False
    assert sms_service.is_business_hours(config, tz_aware(2, 0)) is False


# ---------------------------------------------------------------------------
# Estimate link
# ---------------------------------------------------------------------------
def test_send_estimate_link(
    db_session, contact_with_phone, sms_env, mock_twilio, monkeypatch
):
    monkeypatch.setenv("PORTAL_BASE_URL", "https://crm.example.com")

    from app.models.estimate import Estimate
    from app.models.estimate_token import EstimateToken

    estimate = Estimate(
        name="Roof Replacement",
        status="sent",
        subtotal=0,
        tax=0,
        total=0,
    )
    db_session.add(estimate)
    db_session.commit()
    db_session.refresh(estimate)

    token = EstimateToken(estimate_id=estimate.id, token="tok-abc-123")
    db_session.add(token)
    db_session.commit()

    msg = sms_service.send_estimate_link(
        db_session, contact_with_phone.id, estimate.id
    )
    assert msg is not None
    assert msg.triggered_by == "auto_estimate_sent"
    assert "https://crm.example.com/portal/estimate/tok-abc-123" in msg.body
    assert "Alice" in msg.body


def test_send_estimate_link_kill_switch(
    db_session, contact_with_phone, monkeypatch
):
    monkeypatch.setenv("SMS_ENABLED", "false")

    from app.models.estimate import Estimate

    estimate = Estimate(
        name="x",
        status="sent",
        subtotal=0,
        tax=0,
        total=0,
    )
    db_session.add(estimate)
    db_session.commit()
    db_session.refresh(estimate)

    assert (
        sms_service.send_estimate_link(
            db_session, contact_with_phone.id, estimate.id
        )
        is None
    )


# ---------------------------------------------------------------------------
# ensure_sms_config — singleton
# ---------------------------------------------------------------------------
def test_ensure_sms_config_creates_default_row(db_session):
    assert db_session.query(SmsConfig).count() == 0
    config = sms_service.ensure_sms_config(db_session)
    assert config.id is not None
    assert config.auto_respond_new_lead is True
    assert config.auto_respond_after_hours is True
    assert config.business_hours_start == time(8, 0)
    assert config.business_hours_end == time(18, 0)
    assert "STOP" in config.opt_out_keywords


def test_ensure_sms_config_returns_existing_row(db_session):
    first = sms_service.ensure_sms_config(db_session)
    second = sms_service.ensure_sms_config(db_session)
    assert first.id == second.id
    assert db_session.query(SmsConfig).count() == 1
