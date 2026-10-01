from decimal import Decimal


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts", json={"name": name}, headers=auth_headers
    )
    return resp.json()


def _create_job(client, auth_headers, seeded_stages, **overrides):
    contact = _create_contact(client, auth_headers)
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    data = {
        "pipeline_id": pipeline["id"],
        "contact_id": contact["id"],
        "stage_id": stages[0]["id"],
        "work_type": "retail",
        **overrides,
    }
    resp = client.post("/api/jobs", json=data, headers=auth_headers)
    return resp.json()


def _create_estimate(client, auth_headers, job_id, **overrides):
    data = {"job_id": job_id, "name": "Test Estimate", **overrides}
    resp = client.post("/api/estimates", json=data, headers=auth_headers)
    return resp.json()


def _add_line_item(client, auth_headers, estimate_id, **overrides):
    data = {
        "description": "Shingles",
        "qty": "3.00",
        "unit_price": "100.00",
        **overrides,
    }
    resp = client.post(
        f"/api/estimates/{estimate_id}/line-items",
        json=data,
        headers=auth_headers,
    )
    return resp.json()


# --- Estimate CRUD ---


def test_create_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Roof Estimate"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Roof Estimate"
    assert Decimal(data["tax_rate"]) == Decimal("0.0700")
    assert Decimal(data["subtotal"]) == Decimal("0")
    assert data["job_id"] == job["id"]


def test_create_estimate_with_line_items(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.post(
        "/api/estimates",
        json={
            "job_id": job["id"],
            "name": "Full Estimate",
            "line_items": [
                {"description": "Shingles", "qty": "10", "unit_price": "50.00"},
                {"description": "Nails", "qty": "5", "unit_price": "20.00"},
            ],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["line_items"]) == 2
    assert Decimal(data["subtotal"]) == Decimal("600.00")
    assert Decimal(data["tax"]) == Decimal("42.00")
    assert Decimal(data["total"]) == Decimal("642.00")


def test_create_estimate_custom_tax_rate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(
        client, auth_headers, job["id"], tax_rate="0.0000"
    )
    assert Decimal(est["tax_rate"]) == Decimal("0.0000")


def test_create_estimate_invalid_job(client, auth_headers):
    resp = client.post(
        "/api/estimates",
        json={"job_id": 9999, "name": "Bad"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_get_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Test Estimate"


def test_get_estimate_not_found(client, auth_headers):
    resp = client.get("/api/estimates/9999", headers=auth_headers)
    assert resp.status_code == 404


def test_list_estimates_by_job(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    _create_estimate(client, auth_headers, job["id"], name="Est 1")
    _create_estimate(client, auth_headers, job["id"], name="Est 2")

    resp = client.get(
        "/api/estimates",
        params={"job_id": job["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_estimates_empty(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.get(
        "/api/estimates",
        params={"job_id": job["id"]},
        headers=auth_headers,
    )
    assert resp.json()["total"] == 0


def test_update_estimate_name(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.put(
        f"/api/estimates/{est['id']}",
        json={"name": "Updated Name"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


def test_update_estimate_tax_rate_recalculates(
    client, auth_headers, seeded_stages
):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    _add_line_item(client, auth_headers, est["id"], qty="10", unit_price="100")

    resp = client.put(
        f"/api/estimates/{est['id']}",
        json={"tax_rate": "0.1000"},
        headers=auth_headers,
    )
    data = resp.json()
    assert Decimal(data["subtotal"]) == Decimal("1000.00")
    assert Decimal(data["tax"]) == Decimal("100.00")
    assert Decimal(data["total"]) == Decimal("1100.00")


def test_delete_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.delete(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    assert resp.status_code == 204
    resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    assert resp.status_code == 404


def test_delete_estimate_not_found(client, auth_headers):
    resp = client.delete("/api/estimates/9999", headers=auth_headers)
    assert resp.status_code == 404


# --- Line Items ---


def test_add_line_item(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Shingles", "qty": "3", "unit_price": "100.50"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert Decimal(data["line_total"]) == Decimal("301.50")

    # Verify estimate totals updated
    est_resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    est_data = est_resp.json()
    assert Decimal(est_data["subtotal"]) == Decimal("301.50")


def test_update_line_item(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    item = _add_line_item(client, auth_headers, est["id"])

    resp = client.put(
        f"/api/estimates/{est['id']}/line-items/{item['id']}",
        json={"qty": "5"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert Decimal(resp.json()["line_total"]) == Decimal("500.00")


def test_delete_line_item(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    item = _add_line_item(client, auth_headers, est["id"])

    resp = client.delete(
        f"/api/estimates/{est['id']}/line-items/{item['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    est_resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    assert Decimal(est_resp.json()["subtotal"]) == Decimal("0")


def test_delete_line_item_not_found(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.delete(
        f"/api/estimates/{est['id']}/line-items/9999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_estimate_totals_calculation(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    _add_line_item(
        client, auth_headers, est["id"],
        description="Shingles", qty="10", unit_price="50.00",
    )
    _add_line_item(
        client, auth_headers, est["id"],
        description="Nails", qty="5", unit_price="20.00",
    )

    resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    data = resp.json()
    # subtotal = 500 + 100 = 600, tax = 600 * 0.07 = 42, total = 642
    assert Decimal(data["subtotal"]) == Decimal("600.00")
    assert Decimal(data["tax"]) == Decimal("42.00")
    assert Decimal(data["total"]) == Decimal("642.00")


# --- Duplicate ---


def test_duplicate_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"], name="Original")
    _add_line_item(client, auth_headers, est["id"])

    resp = client.post(
        f"/api/estimates/{est['id']}/duplicate", headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Original (Copy)"
    assert data["id"] != est["id"]
    assert len(data["line_items"]) == 1
    assert Decimal(data["subtotal"]) == Decimal(est["id"] and "300.00")


def test_duplicate_preserves_tax_rate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(
        client, auth_headers, job["id"], tax_rate="0.1000"
    )
    resp = client.post(
        f"/api/estimates/{est['id']}/duplicate", headers=auth_headers
    )
    assert Decimal(resp.json()["tax_rate"]) == Decimal("0.1000")


# --- Reorder ---


def test_reorder_line_items(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    item1 = _add_line_item(
        client, auth_headers, est["id"], description="First"
    )
    item2 = _add_line_item(
        client, auth_headers, est["id"], description="Second"
    )

    # Reverse order
    resp = client.put(
        f"/api/estimates/{est['id']}/line-items/reorder",
        json={"item_ids": [item2["id"], item1["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["line_items"]
    assert items[0]["description"] == "Second"
    assert items[1]["description"] == "First"


def test_reorder_with_invalid_ids(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    _add_line_item(client, auth_headers, est["id"])

    resp = client.put(
        f"/api/estimates/{est['id']}/line-items/reorder",
        json={"item_ids": [9999]},
        headers=auth_headers,
    )
    assert resp.status_code == 400


# --- Auth ---


def test_estimates_require_auth(client):
    resp = client.get("/api/estimates")
    assert resp.status_code == 401

    resp = client.post("/api/estimates", json={"job_id": 1, "name": "X"})
    assert resp.status_code == 401


# --- Computed fields ---


def test_estimate_has_job_address(client, auth_headers, seeded_stages):
    job = _create_job(
        client, auth_headers, seeded_stages,
        property_address="123 Main St",
    )
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    assert resp.json()["job_address"] == "123 Main St"


# --- Sections ---


def _create_section(client, auth_headers, estimate_id, **overrides):
    data = {"name": "Roofing Materials", **overrides}
    resp = client.post(
        f"/api/estimates/{estimate_id}/sections",
        json=data,
        headers=auth_headers,
    )
    return resp


def test_create_section(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = _create_section(client, auth_headers, est["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Roofing Materials"
    assert data["estimate_id"] == est["id"]
    assert data["sort_order"] == 0
    assert data["line_items"] == []
    assert data["subtotal"] == "0"


def test_create_section_auto_sort_order(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    s1 = _create_section(client, auth_headers, est["id"], name="First").json()
    s2 = _create_section(client, auth_headers, est["id"], name="Second").json()
    assert s1["sort_order"] == 0
    assert s2["sort_order"] == 1


def test_list_sections(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    _create_section(client, auth_headers, est["id"], name="A")
    _create_section(client, auth_headers, est["id"], name="B")

    resp = client.get(
        f"/api/estimates/{est['id']}/sections", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "A"
    assert data[1]["name"] == "B"


def test_update_section(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    section = _create_section(client, auth_headers, est["id"]).json()

    resp = client.put(
        f"/api/estimates/{est['id']}/sections/{section['id']}",
        json={"name": "Updated Name", "description": "<p>Desc</p>"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "<p>Desc</p>"


def test_delete_section_moves_items_to_unsectioned(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    section = _create_section(client, auth_headers, est["id"]).json()

    # Add item to section
    item = _add_line_item(
        client, auth_headers, est["id"], section_id=section["id"]
    )
    assert item["section_id"] == section["id"]

    # Delete section
    resp = client.delete(
        f"/api/estimates/{est['id']}/sections/{section['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    # Item should now be unsectioned
    est_resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    items = est_resp.json()["line_items"]
    assert len(items) == 1
    assert items[0]["section_id"] is None


def test_reorder_sections(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    s1 = _create_section(client, auth_headers, est["id"], name="First").json()
    s2 = _create_section(client, auth_headers, est["id"], name="Second").json()

    resp = client.put(
        f"/api/estimates/{est['id']}/sections/reorder",
        json={"section_ids": [s2["id"], s1["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["name"] == "Second"
    assert data[1]["name"] == "First"


def test_estimate_response_includes_sections(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    section = _create_section(client, auth_headers, est["id"]).json()
    _add_line_item(client, auth_headers, est["id"], section_id=section["id"])

    resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    data = resp.json()
    assert "sections" in data
    assert len(data["sections"]) == 1
    assert data["sections"][0]["name"] == "Roofing Materials"
    assert len(data["sections"][0]["line_items"]) == 1


def test_section_subtotal_computed(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    section = _create_section(client, auth_headers, est["id"]).json()
    _add_line_item(
        client, auth_headers, est["id"],
        qty="2", unit_price="50.00", section_id=section["id"],
    )
    _add_line_item(
        client, auth_headers, est["id"],
        qty="3", unit_price="30.00", section_id=section["id"],
    )

    resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    )
    sections = resp.json()["sections"]
    assert len(sections) == 1
    assert Decimal(sections[0]["subtotal"]) == Decimal("190.00")


def test_add_item_with_section(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    section = _create_section(client, auth_headers, est["id"]).json()

    item = _add_line_item(
        client, auth_headers, est["id"], section_id=section["id"]
    )
    assert item["section_id"] == section["id"]


def test_add_item_with_invalid_section(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])

    resp = client.post(
        f"/api/estimates/{est['id']}/line-items",
        json={"description": "Bad", "qty": "1", "unit_price": "10", "section_id": 99999},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_move_item_to_section(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    section = _create_section(client, auth_headers, est["id"]).json()
    item = _add_line_item(client, auth_headers, est["id"])
    assert item["section_id"] is None

    resp = client.put(
        f"/api/estimates/{est['id']}/line-items/{item['id']}",
        json={"section_id": section["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["section_id"] == section["id"]


def test_duplicate_copies_sections(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"], name="Original")
    section = _create_section(client, auth_headers, est["id"], name="Materials").json()
    _add_line_item(client, auth_headers, est["id"], section_id=section["id"])
    _add_line_item(client, auth_headers, est["id"])  # unsectioned item

    resp = client.post(
        f"/api/estimates/{est['id']}/duplicate", headers=auth_headers
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["sections"]) == 1
    assert data["sections"][0]["name"] == "Materials"
    assert len(data["sections"][0]["line_items"]) == 1
    assert len(data["line_items"]) == 2
    # The sectioned item in the copy should reference the new section
    sectioned_items = [li for li in data["line_items"] if li["section_id"] is not None]
    assert len(sectioned_items) == 1
    assert sectioned_items[0]["section_id"] == data["sections"][0]["id"]


def test_duplicate_line_item(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    item = _add_line_item(
        client,
        auth_headers,
        est["id"],
        description="Shingles",
        qty="3.00",
        unit_price="100.00",
        body="<p>Architectural shingles</p>",
        notes="Crew note",
    )

    resp = client.post(
        f"/api/estimates/{est['id']}/line-items/{item['id']}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    dup = resp.json()
    assert dup["id"] != item["id"]
    assert dup["description"] == "Shingles"
    assert Decimal(str(dup["qty"])) == Decimal("3.00")
    assert Decimal(str(dup["unit_price"])) == Decimal("100.00")
    assert Decimal(str(dup["line_total"])) == Decimal("300.00")
    assert dup["body"] == "<p>Architectural shingles</p>"
    assert dup["notes"] == "Crew note"
    assert dup["sort_order"] > item["sort_order"]

    # Estimate now has two items and subtotal doubled
    est_resp = client.get(
        f"/api/estimates/{est['id']}", headers=auth_headers
    ).json()
    assert len(est_resp["line_items"]) == 2
    assert Decimal(str(est_resp["subtotal"])) == Decimal("600.00")


def test_duplicate_line_item_preserves_section(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])

    section_resp = client.post(
        f"/api/estimates/{est['id']}/sections",
        json={"name": "Roofing"},
        headers=auth_headers,
    )
    section_id = section_resp.json()["id"]

    item = _add_line_item(
        client,
        auth_headers,
        est["id"],
        description="Ridge cap",
        qty="2",
        unit_price="50.00",
        section_id=section_id,
    )

    resp = client.post(
        f"/api/estimates/{est['id']}/line-items/{item['id']}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["section_id"] == section_id


def test_duplicate_line_item_not_found(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])

    resp = client.post(
        f"/api/estimates/{est['id']}/line-items/9999/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_duplicate_line_item_wrong_estimate(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est_a = _create_estimate(client, auth_headers, job["id"], name="A")
    est_b = _create_estimate(client, auth_headers, job["id"], name="B")
    item = _add_line_item(client, auth_headers, est_a["id"])

    resp = client.post(
        f"/api/estimates/{est_b['id']}/line-items/{item['id']}/duplicate",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# --- Sprint 14.5: expiration_date + created_by ---


def test_create_estimate_sets_created_by(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Test"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["created_by_user_id"] is not None
    assert data["created_by_user_name"] is not None


def test_update_estimate_expiration_date(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.put(
        f"/api/estimates/{est['id']}",
        json={"expiration_date": "2026-05-01"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["expiration_date"] == "2026-05-01"


def test_estimate_response_includes_contact_metadata(client, auth_headers, seeded_stages):
    c_resp = client.post(
        "/api/contacts",
        json={
            "name": "Company Contact",
            "company": "Big Corp",
            "phone": "765-555-0001",
            "address": "1 Main St",
        },
        headers=auth_headers,
    )
    contact_id = c_resp.json()["id"]
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}", headers=auth_headers
    ).json()["items"]
    job_resp = client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact_id,
            "stage_id": stages[0]["id"],
            "work_type": "retail",
            "property_address": "99 Job St",
        },
        headers=auth_headers,
    )
    job_id = job_resp.json()["id"]
    est = _create_estimate(client, auth_headers, job_id)

    resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    data = resp.json()
    assert data["contact_company"] == "Big Corp"
    assert data["contact_phone"] == "765-555-0001"
    assert data["contact_address"] == "1 Main St"


def test_estimate_job_phase_fields(client, auth_headers, seeded_stages):
    """Sprint 15a: estimates accept and return job-phase fields."""
    from decimal import Decimal  # noqa: F401

    job = _create_job(client, auth_headers, seeded_stages)

    # Create estimate with job-phase fields
    resp = client.post(
        "/api/estimates",
        json={
            "job_id": job["id"],
            "name": "Phase Test",
            "job_type": "Roofing",
            "work_type": "insurance",
            "location_address": "99 Site Rd",
            "scheduled_start": "2026-05-01",
            "scheduled_end": "2026-05-03",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["job_type"] == "Roofing"
    assert data["work_type"] == "insurance"
    assert data["location_address"] == "99 Site Rd"
    assert data["scheduled_start"] == "2026-05-01"
    assert data["scheduled_end"] == "2026-05-03"

    # Update via PUT — partial update should work
    resp = client.put(
        f"/api/estimates/{data['id']}",
        json={"job_type": "Gutters"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["job_type"] == "Gutters"
    assert resp.json()["work_type"] == "insurance"  # unchanged

    # Newly created estimates without explicit fields should inherit from parent job
    resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Inherit Test"},
        headers=auth_headers,
    )
    inherit = resp.json()
    assert inherit["work_type"] == "retail"  # from job helper default


# --- Sprint 15a: Internal approve ---


def test_internal_approve_estimate(client, auth_headers, seeded_stages, db_session):
    """Internal approve moves estimate to 'approved' and records metadata."""
    from decimal import Decimal  # noqa: F401
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])

    # Simulate 'sent' status via the service that does this normally.
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "sent"
    db_session.commit()

    resp = client.post(
        f"/api/estimates/{est['id']}/approve-internal",
        json={"signer_name": "Marcus Hale"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == "Marcus Hale"
    assert data["approved_at"] is not None

    # Should have moved into Jobs pipeline "Pending Schedule" stage
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    jobs_pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={jobs_pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    pending_stage = next(s for s in stages if s["name"] == "Pending Schedule")
    assert data["pipeline_id"] == jobs_pipeline["id"]
    assert data["stage_id"] == pending_stage["id"]


def test_internal_approve_rejects_already_approved(
    client, auth_headers, seeded_stages, db_session
):
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "approved"
    db_session.commit()

    resp = client.post(
        f"/api/estimates/{est['id']}/approve-internal",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "already approved" in resp.json()["detail"].lower()


def test_internal_approve_default_approver_label(
    client, auth_headers, seeded_stages, db_session
):
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "viewed"
    db_session.commit()

    resp = client.post(
        f"/api/estimates/{est['id']}/approve-internal",
        json={},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["approved_by"] == "internal"


def test_list_estimates_status_filter(client, auth_headers, seeded_stages, db_session):
    """Sprint 15c: listing estimates supports a status filter (single or CSV)."""
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers, seeded_stages)

    # Create 3 estimates in different statuses
    e1 = _create_estimate(client, auth_headers, job["id"], name="Draft1")
    e2 = _create_estimate(client, auth_headers, job["id"], name="SentOne")
    e3 = _create_estimate(client, auth_headers, job["id"], name="ApprovedOne")

    e2_obj = db_session.query(Estimate).filter(Estimate.id == e2["id"]).first()
    e2_obj.status = "sent"
    e3_obj = db_session.query(Estimate).filter(Estimate.id == e3["id"]).first()
    e3_obj.status = "approved"
    db_session.commit()

    # Single status
    resp = client.get(
        "/api/estimates", params={"status": "approved"}, headers=auth_headers
    )
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()["items"]]
    assert "ApprovedOne" in names
    assert "Draft1" not in names

    # CSV status
    resp = client.get(
        "/api/estimates",
        params={"status": "approved,sent"},
        headers=auth_headers,
    )
    names = [e["name"] for e in resp.json()["items"]]
    assert "ApprovedOne" in names
    assert "SentOne" in names
    assert "Draft1" not in names


# --- Sprint 15d: status transitions via PUT /estimates/{id} ---


def test_status_transition_valid_job_phases(
    client, auth_headers, seeded_stages, db_session
):
    """Can transition approved -> in_progress -> complete -> closed."""
    from app.models.estimate import Estimate

    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    # Move to 'sent' then internal-approve
    est_obj = db_session.query(Estimate).filter(Estimate.id == est["id"]).first()
    est_obj.status = "sent"
    db_session.commit()
    client.post(
        f"/api/estimates/{est['id']}/approve-internal",
        json={},
        headers=auth_headers,
    )

    for target in ["in_progress", "complete", "closed"]:
        resp = client.put(
            f"/api/estimates/{est['id']}",
            json={"status": target},
            headers=auth_headers,
        )
        assert resp.status_code == 200, f"{target}: {resp.text}"
        assert resp.json()["status"] == target


def test_status_transition_blocks_approve_shortcut(
    client, auth_headers, seeded_stages
):
    """PUT status=approved from draft should be blocked with a hint."""
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.put(
        f"/api/estimates/{est['id']}",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "approve-internal" in resp.json()["detail"]


def test_status_transition_blocks_in_progress_from_draft(
    client, auth_headers, seeded_stages
):
    """PUT status=in_progress from draft should be blocked."""
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.put(
        f"/api/estimates/{est['id']}",
        json={"status": "in_progress"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Cannot transition" in resp.json()["detail"]


def test_status_transition_rejects_invalid(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.put(
        f"/api/estimates/{est['id']}",
        json={"status": "banana"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Invalid estimate status" in resp.json()["detail"]


# --- Sprint 15.5a: tax_included ---


def test_tax_included_false_calculates_tax_normally(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"], tax_included=False)
    _add_line_item(client, auth_headers, est["id"], qty="10", unit_price="60.00")

    resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    data = resp.json()
    assert Decimal(data["subtotal"]) == Decimal("600.00")
    assert Decimal(data["tax"]) == Decimal("42.00")
    assert Decimal(data["total"]) == Decimal("642.00")
    assert data["tax_included"] is False


def test_tax_included_true_sets_tax_zero(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"], tax_included=True)
    _add_line_item(client, auth_headers, est["id"], qty="10", unit_price="60.00")

    resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    data = resp.json()
    assert Decimal(data["subtotal"]) == Decimal("600.00")
    assert Decimal(data["tax"]) == Decimal("0")
    assert Decimal(data["total"]) == Decimal("600.00")
    assert data["tax_included"] is True


def test_update_tax_included_recalculates_totals(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"], tax_included=False)
    _add_line_item(client, auth_headers, est["id"], qty="10", unit_price="60.00")

    resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    assert Decimal(resp.json()["tax"]) == Decimal("42.00")

    client.put(
        f"/api/estimates/{est['id']}",
        json={"tax_included": True},
        headers=auth_headers,
    )
    resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    data = resp.json()
    assert Decimal(data["tax"]) == Decimal("0")
    assert Decimal(data["total"]) == Decimal("600.00")


def test_duplicate_estimate_preserves_tax_included(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"], tax_included=True)
    _add_line_item(client, auth_headers, est["id"], qty="5", unit_price="20.00")

    resp = client.post(
        f"/api/estimates/{est['id']}/duplicate", headers=auth_headers
    )
    assert resp.status_code == 201
    copy = resp.json()
    assert copy["tax_included"] is True
    assert Decimal(copy["tax"]) == Decimal("0")
    assert Decimal(copy["total"]) == Decimal("100.00")


def test_estimate_response_includes_tax_included(client, auth_headers, seeded_stages):
    job = _create_job(client, auth_headers, seeded_stages)
    est = _create_estimate(client, auth_headers, job["id"])
    resp = client.get(f"/api/estimates/{est['id']}", headers=auth_headers)
    data = resp.json()
    assert "tax_included" in data
    assert data["tax_included"] is False
