import io

import pytest
from openpyxl import Workbook

from app.models.contact import Contact


# ---------- Fixtures ----------


def _csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def _xlsx_bytes(rows):
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _post_preview(client, auth_headers, *, name, content, mime="text/csv"):
    return client.post(
        "/api/import/contacts/preview",
        headers=auth_headers,
        files={"file": (name, io.BytesIO(content), mime)},
    )


def _seed_existing_contact(client, auth_headers, **kwargs):
    payload = {"name": "Existing Person"}
    payload.update(kwargs)
    resp = client.post("/api/contacts", headers=auth_headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------- Preview ----------


def test_preview_csv_upload(client, auth_headers):
    csv = (
        "Name,Email,Phone\n"
        "John Smith,john@example.com,(765) 555-1111\n"
        "Jane Doe,jane@example.com,765-555-2222\n"
    )
    resp = _post_preview(
        client, auth_headers, name="contacts.csv", content=_csv_bytes(csv)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_rows"] == 2
    assert data["importable_rows"] == 2
    assert data["skipped_rows"] == 0
    assert data["potential_duplicates"] == 0
    assert "preview_token" in data and len(data["preview_token"]) > 8
    assert data["columns_detected"] == ["Name", "Email", "Phone"]
    assert len(data["sample_rows"]) == 2


def test_preview_xlsx_upload(client, auth_headers):
    raw = _xlsx_bytes(
        [
            ["Name", "Email", "Phone"],
            ["Alice Adams", "alice@example.com", "5551234567"],
            ["Bob Brown", "", "5557654321"],
        ]
    )
    resp = _post_preview(
        client,
        auth_headers,
        name="contacts.xlsx",
        content=raw,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_rows"] == 2
    assert data["importable_rows"] == 2


def test_preview_auto_mapping(client, auth_headers):
    csv = (
        "Email,Phone,Full Name,Zip Code\n"
        "a@b.com,555-0001,Test Person,46901\n"
    )
    data = _post_preview(
        client, auth_headers, name="x.csv", content=_csv_bytes(csv)
    ).json()
    assert data["suggested_mappings"]["Email"] == "email"
    assert data["suggested_mappings"]["Phone"] == "phone"
    assert data["suggested_mappings"]["Full Name"] == "name"
    assert data["suggested_mappings"]["Zip Code"] == "zip_code"


def test_preview_acculynx_format(client, auth_headers):
    csv = (
        "Primary Contact: Name,Primary Contact: Email,Primary Contact: Phone\n"
        "John Smith,john@example.com,7655551234\n"
    )
    data = _post_preview(
        client, auth_headers, name="acculynx.csv", content=_csv_bytes(csv)
    ).json()
    sm = data["suggested_mappings"]
    assert sm["Primary Contact: Name"] == "name"
    assert sm["Primary Contact: Email"] == "email"
    assert sm["Primary Contact: Phone"] == "phone"


def test_preview_first_last_name(client, auth_headers):
    csv = "First Name,Last Name,Email\nJohn,Smith,j@example.com\n"
    data = _post_preview(
        client, auth_headers, name="x.csv", content=_csv_bytes(csv)
    ).json()
    sm = data["suggested_mappings"]
    assert sm["First Name"] == "first_name"
    assert sm["Last Name"] == "last_name"
    assert data["importable_rows"] == 1
    assert data["warnings"] == []


def test_preview_empty_file(client, auth_headers):
    resp = _post_preview(
        client, auth_headers, name="empty.csv", content=b""
    )
    assert resp.status_code == 400


def test_preview_no_name_column(client, auth_headers):
    csv = "Email,Phone\nfoo@bar.com,5551234567\n"
    resp = _post_preview(
        client, auth_headers, name="x.csv", content=_csv_bytes(csv)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["warnings"]
    assert data["importable_rows"] == 0
    assert data["skip_reasons"]["no_name"] == 1


def test_preview_sample_rows_capped(client, auth_headers):
    header = "Name,Email\n"
    body = "".join(f"Person {i},p{i}@example.com\n" for i in range(60))
    data = _post_preview(
        client, auth_headers, name="x.csv", content=_csv_bytes(header + body)
    ).json()
    assert data["total_rows"] == 60
    assert len(data["sample_rows"]) == 25


def test_preview_large_file_stats(client, auth_headers):
    header = "Name,Email,Phone\n"
    body = "".join(
        f"Person {i},p{i}@example.com,555000{i:04d}\n" for i in range(1200)
    )
    data = _post_preview(
        client, auth_headers, name="x.csv", content=_csv_bytes(header + body)
    ).json()
    assert data["total_rows"] == 1200
    assert data["importable_rows"] == 1200


def test_preview_unsupported_format(client, auth_headers):
    resp = _post_preview(
        client, auth_headers, name="bad.txt", content=b"foo\nbar"
    )
    assert resp.status_code == 400


def test_preview_unauthorized(client):
    resp = client.post(
        "/api/import/contacts/preview",
        files={"file": ("x.csv", io.BytesIO(b"Name\nJoe\n"), "text/csv")},
    )
    assert resp.status_code == 401


# ---------- Confirm ----------


def _do_preview(client, auth_headers, csv_text):
    return _post_preview(
        client, auth_headers, name="x.csv", content=_csv_bytes(csv_text)
    ).json()


def test_confirm_imports_contacts(client, auth_headers, db_session):
    csv = "Name,Email,Phone\nJohn Smith,john@x.com,7655551234\nJane Doe,jane@x.com,7655555678\n"
    preview = _do_preview(client, auth_headers, csv)
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["imported"] == 2
    assert data["skipped_invalid"] == 0
    assert data["skipped_duplicates"] == 0
    assert db_session.query(Contact).filter(Contact.import_id == data["import_id"]).count() == 2


def test_confirm_applies_mappings(client, auth_headers, db_session):
    csv = (
        "Customer,Mail,Cell,Street,Town\n"
        "Sam Smith,sam@x.com,7651112222,123 Main St,Kokomo\n"
    )
    preview = _do_preview(client, auth_headers, csv)
    mappings = {
        "Customer": "name",
        "Mail": "email",
        "Cell": "phone",
        "Street": "address",
        "Town": "city",
    }
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": mappings,
            "options": {},
        },
    )
    assert resp.status_code == 200
    contact = (
        db_session.query(Contact)
        .filter(Contact.email == "sam@x.com")
        .first()
    )
    assert contact is not None
    assert contact.name == "Sam Smith"
    assert contact.phone == "7651112222"
    assert contact.address == "123 Main St"
    assert contact.city == "Kokomo"


def test_confirm_combines_first_last_name(client, auth_headers, db_session):
    csv = "First Name,Last Name,Email\nJohn,Doe,john@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    )
    assert resp.status_code == 200
    contact = db_session.query(Contact).filter(Contact.email == "john@x.com").first()
    assert contact is not None
    assert contact.name == "John Doe"


def test_confirm_default_client_type(client, auth_headers, db_session):
    csv = "Name,Email\nJoe Bloggs,joe@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {"default_client_type": "commercial"},
        },
    )
    assert resp.status_code == 200
    contact = db_session.query(Contact).filter(Contact.email == "joe@x.com").first()
    assert contact.client_type == "commercial"


def test_confirm_default_lead_source(client, auth_headers, db_session):
    csv = "Name,Email\nJoe Bloggs,joe@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {"default_lead_source": "AccuLynx Migration"},
        },
    )
    assert resp.status_code == 200
    contact = db_session.query(Contact).filter(Contact.email == "joe@x.com").first()
    assert contact.lead_source == "AccuLynx Migration"


def test_confirm_skip_duplicates(client, auth_headers, db_session):
    _seed_existing_contact(client, auth_headers, name="John Smith", email="dup@x.com")
    csv = "Name,Email\nJohn Smith,dup@x.com\nJane Doe,jane@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    assert preview["potential_duplicates"] == 1
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {"duplicate_handling": "skip"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert data["skipped_duplicates"] == 1


def test_confirm_import_duplicates(client, auth_headers, db_session):
    _seed_existing_contact(client, auth_headers, name="John Smith", email="dup@x.com")
    csv = "Name,Email\nJohn Smith,dup@x.com\nJane Doe,jane@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {"duplicate_handling": "import"},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["skipped_duplicates"] == 0


def test_confirm_combine_unmapped_to_notes(client, auth_headers, db_session):
    csv = (
        "Name,Email,Job Type,Salesperson\n"
        "Test Person,t@x.com,Roofing,Josh\n"
    )
    preview = _do_preview(client, auth_headers, csv)
    mappings = {"Name": "name", "Email": "email"}
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": mappings,
            "options": {"combine_unmapped_to_notes": True},
        },
    )
    assert resp.status_code == 200
    from app.models.note import Note
    notes = db_session.query(Note).filter(Note.entity_type == "contact").all()
    assert len(notes) == 1
    assert "Job Type: Roofing" in notes[0].content
    assert "Salesperson: Josh" in notes[0].content


def test_confirm_sets_import_id(client, auth_headers, db_session):
    csv = "Name,Email\nA Person,a@x.com\nB Person,b@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    )
    import_id = resp.json()["import_id"]
    contacts = db_session.query(Contact).filter(Contact.import_id == import_id).all()
    assert len(contacts) == 2
    assert all(c.import_id == import_id for c in contacts)


def test_confirm_invalid_token(client, auth_headers):
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": "bogus-token-does-not-exist",
            "field_mappings": {},
            "options": {},
        },
    )
    assert resp.status_code == 400


def test_confirm_phone_normalization(client, auth_headers, db_session):
    csv = "Name,Phone\nA Person,(765) 555-9999\n"
    preview = _do_preview(client, auth_headers, csv)
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    )
    assert resp.status_code == 200
    c = db_session.query(Contact).filter(Contact.name == "A Person").first()
    # Phone preserved as-is for display
    assert c.phone == "(765) 555-9999"


def test_confirm_email_validation(client, auth_headers, db_session):
    csv = "Name,Email\nGood Person,good@x.com\nBad Person,not-an-email\n"
    preview = _do_preview(client, auth_headers, csv)
    resp = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    bad = db_session.query(Contact).filter(Contact.name == "Bad Person").first()
    assert bad.email is None  # invalid email dropped, row imported


def test_confirm_unauthorized(client):
    resp = client.post(
        "/api/import/contacts/confirm",
        json={"preview_token": "x", "field_mappings": {}, "options": {}},
    )
    assert resp.status_code == 401


# ---------- History ----------


def test_import_history(client, auth_headers, db_session):
    csv = "Name,Email\nA,a@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    )
    resp = client.get("/api/import/history", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["imported_count"] == 1
    assert data["items"][0]["file_name"] == "x.csv"


def test_import_history_unauthorized(client):
    resp = client.get("/api/import/history")
    assert resp.status_code == 401


# ---------- Undo ----------


def test_undo_import(client, auth_headers, db_session):
    csv = "Name,Email\nA,a@x.com\nB,b@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    confirm = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    ).json()
    import_id = confirm["import_id"]
    resp = client.post(
        f"/api/import/contacts/{import_id}/undo", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["soft_deleted"] == 2
    # Soft-deleted contacts hidden from list endpoint
    listing = client.get("/api/contacts", headers=auth_headers).json()
    listing_imported = [c for c in listing["items"] if c.get("name") in ("A", "B")]
    assert listing_imported == []
    # But contacts still exist in DB with deleted_at set
    rows = (
        db_session.query(Contact).filter(Contact.import_id == import_id).all()
    )
    assert len(rows) == 2
    assert all(r.deleted_at is not None for r in rows)


def test_undo_only_affects_import(client, auth_headers, db_session):
    manual = _seed_existing_contact(
        client, auth_headers, name="Hand Made", email="hand@x.com"
    )
    csv = "Name,Email\nA Person,a@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    confirm = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    ).json()
    client.post(
        f"/api/import/contacts/{confirm['import_id']}/undo",
        headers=auth_headers,
    )
    resp = client.get(f"/api/contacts/{manual['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Hand Made"


def test_undo_unauthorized(client):
    resp = client.post("/api/import/contacts/anything/undo")
    assert resp.status_code == 401


def test_undo_unknown_import(client, auth_headers):
    resp = client.post(
        "/api/import/contacts/does-not-exist/undo", headers=auth_headers
    )
    assert resp.status_code == 404


def test_undo_already_undone(client, auth_headers, db_session):
    csv = "Name,Email\nA,a@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    confirm = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    ).json()
    client.post(
        f"/api/import/contacts/{confirm['import_id']}/undo",
        headers=auth_headers,
    )
    second = client.post(
        f"/api/import/contacts/{confirm['import_id']}/undo",
        headers=auth_headers,
    )
    assert second.status_code == 400


def test_contact_list_filter_by_import_id(client, auth_headers, db_session):
    csv = "Name,Email\nA,a@x.com\nB,b@x.com\n"
    preview = _do_preview(client, auth_headers, csv)
    confirm = client.post(
        "/api/import/contacts/confirm",
        headers=auth_headers,
        json={
            "preview_token": preview["preview_token"],
            "field_mappings": preview["suggested_mappings"],
            "options": {},
        },
    ).json()
    listing = client.get(
        "/api/contacts",
        headers=auth_headers,
        params={"import_id": confirm["import_id"]},
    ).json()
    assert listing["total"] == 2
