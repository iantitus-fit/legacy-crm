"""Sprint 20a — file uploads with folders, photos, visibility."""
import io


def _create_contact(client, auth_headers, name="Test Customer"):
    resp = client.post(
        "/api/contacts", json={"name": name}, headers=auth_headers
    )
    return resp.json()


def _create_job(client, auth_headers, contact_id):
    pipelines = client.get("/api/pipelines", headers=auth_headers).json()["items"]
    pipeline = next(p for p in pipelines if p["slug"] == "jobs")
    stages = client.get(
        f"/api/pipeline-stages?pipeline_id={pipeline['id']}",
        headers=auth_headers,
    ).json()["items"]
    resp = client.post(
        "/api/jobs",
        json={
            "pipeline_id": pipeline["id"],
            "contact_id": contact_id,
            "stage_id": stages[0]["id"],
            "work_type": "retail",
        },
        headers=auth_headers,
    )
    return resp.json()


def _create_estimate(client, auth_headers, contact_id):
    job = _create_job(client, auth_headers, contact_id)
    resp = client.post(
        "/api/estimates",
        json={"job_id": job["id"], "name": "Test Estimate"},
        headers=auth_headers,
    )
    return resp.json()


def _upload(
    client,
    auth_headers,
    *,
    contact_id=None,
    job_id=None,
    estimate_id=None,
    folder="General",
    description=None,
    show_in_work_order=False,
    show_in_estimate=False,
    filename="test.pdf",
    content=b"file content",
    content_type="application/pdf",
):
    data = {
        "folder": folder,
        "show_in_work_order": str(show_in_work_order).lower(),
        "show_in_estimate": str(show_in_estimate).lower(),
    }
    if contact_id is not None:
        data["contact_id"] = str(contact_id)
    if job_id is not None:
        data["job_id"] = str(job_id)
    if estimate_id is not None:
        data["estimate_id"] = str(estimate_id)
    if description is not None:
        data["description"] = description

    return client.post(
        "/api/documents",
        data=data,
        files=[("files", (filename, io.BytesIO(content), content_type))],
        headers=auth_headers,
    )


# --- Multi-entity attachment ---


def test_upload_to_estimate(client, auth_headers, seeded_stages, temp_upload_dir):
    contact = _create_contact(client, auth_headers)
    est = _create_estimate(client, auth_headers, contact["id"])

    resp = _upload(client, auth_headers, estimate_id=est["id"])
    assert resp.status_code == 201
    doc = resp.json()[0]
    assert doc["estimate_id"] == est["id"]
    assert doc["contact_id"] is None
    assert doc["job_id"] is None


def test_upload_rejects_missing_entity(client, auth_headers, temp_upload_dir):
    resp = client.post(
        "/api/documents",
        files=[("files", ("a.pdf", io.BytesIO(b"x"), "application/pdf"))],
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "job_id" in resp.json()["detail"]
    assert "contact_id" in resp.json()["detail"]
    assert "estimate_id" in resp.json()["detail"]


def test_upload_rejects_multiple_entities(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    est = _create_estimate(client, auth_headers, contact["id"])
    resp = _upload(
        client,
        auth_headers,
        contact_id=contact["id"],
        estimate_id=est["id"],
    )
    assert resp.status_code == 400
    assert "only one" in resp.json()["detail"]


def test_upload_rejects_unknown_estimate(client, auth_headers, temp_upload_dir):
    resp = _upload(client, auth_headers, estimate_id=999)
    assert resp.status_code == 400


# --- Folder organization ---


def test_upload_with_folder(client, auth_headers, seeded_stages, temp_upload_dir):
    contact = _create_contact(client, auth_headers)
    resp = _upload(
        client,
        auth_headers,
        contact_id=contact["id"],
        folder="Contracts",
        filename="contract.pdf",
    )
    assert resp.status_code == 201
    assert resp.json()[0]["folder"] == "Contracts"


def test_upload_default_folder(client, auth_headers, seeded_stages, temp_upload_dir):
    contact = _create_contact(client, auth_headers)
    resp = client.post(
        "/api/documents",
        data={"contact_id": str(contact["id"])},
        files=[("files", ("x.pdf", io.BytesIO(b"x"), "application/pdf"))],
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()[0]["folder"] == "General"


def test_list_filter_by_folder(client, auth_headers, seeded_stages, temp_upload_dir):
    contact = _create_contact(client, auth_headers)
    _upload(client, auth_headers, contact_id=contact["id"], folder="Photos",
            filename="a.png", content_type="image/png")
    _upload(client, auth_headers, contact_id=contact["id"], folder="Contracts",
            filename="b.pdf")
    _upload(client, auth_headers, contact_id=contact["id"], folder="Contracts",
            filename="c.pdf")

    resp = client.get(
        "/api/documents",
        params={"contact_id": contact["id"], "folder": "Contracts"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    names = sorted(d["original_filename"] for d in resp.json()["items"])
    assert names == ["b.pdf", "c.pdf"]


def test_list_folders_with_counts(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    _upload(client, auth_headers, contact_id=contact["id"], folder="Photos",
            filename="p1.png", content_type="image/png")
    _upload(client, auth_headers, contact_id=contact["id"], folder="Photos",
            filename="p2.png", content_type="image/png")
    _upload(client, auth_headers, contact_id=contact["id"], folder="Contracts",
            filename="c.pdf")

    resp = client.get(
        "/api/documents/folders",
        params={"contact_id": contact["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_files"] == 3
    by_name = {f["name"]: f for f in data["items"]}
    assert by_name["Photos"]["file_count"] == 2
    assert by_name["Photos"]["photo_count"] == 2
    assert by_name["Contracts"]["file_count"] == 1
    assert by_name["Contracts"]["photo_count"] == 0


def test_list_folders_requires_entity(client, auth_headers):
    resp = client.get("/api/documents/folders", headers=auth_headers)
    assert resp.status_code == 400


# --- Photo auto-detect + filter ---


def test_image_upload_marks_is_photo(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    resp = _upload(
        client,
        auth_headers,
        contact_id=contact["id"],
        filename="roof.jpg",
        content=b"\xff\xd8\xff",
        content_type="image/jpeg",
    )
    assert resp.status_code == 201
    assert resp.json()[0]["is_photo"] is True


def test_pdf_upload_is_not_photo(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    resp = _upload(client, auth_headers, contact_id=contact["id"])
    assert resp.json()[0]["is_photo"] is False


def test_heic_upload_allowed(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    resp = _upload(
        client,
        auth_headers,
        contact_id=contact["id"],
        filename="iphone.heic",
        content=b"heic-bytes",
        content_type="image/heic",
    )
    assert resp.status_code == 201
    assert resp.json()[0]["is_photo"] is True


def test_list_filter_is_photo_true(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    _upload(client, auth_headers, contact_id=contact["id"],
            filename="a.png", content_type="image/png")
    _upload(client, auth_headers, contact_id=contact["id"], filename="b.pdf")

    resp = client.get(
        "/api/documents",
        params={"contact_id": contact["id"], "is_photo": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["original_filename"] == "a.png"


def test_list_filter_is_photo_false(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    _upload(client, auth_headers, contact_id=contact["id"],
            filename="a.png", content_type="image/png")
    _upload(client, auth_headers, contact_id=contact["id"], filename="b.pdf")

    resp = client.get(
        "/api/documents",
        params={"contact_id": contact["id"], "is_photo": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["original_filename"] == "b.pdf"


# --- Visibility toggles ---


def test_upload_with_visibility_flags(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    resp = _upload(
        client,
        auth_headers,
        contact_id=contact["id"],
        show_in_work_order=True,
        show_in_estimate=True,
    )
    assert resp.status_code == 201
    doc = resp.json()[0]
    assert doc["show_in_work_order"] is True
    assert doc["show_in_estimate"] is True


def test_visibility_defaults_to_false(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    resp = _upload(client, auth_headers, contact_id=contact["id"])
    doc = resp.json()[0]
    assert doc["show_in_work_order"] is False
    assert doc["show_in_estimate"] is False


# --- Description ---


def test_upload_with_description(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    resp = _upload(
        client,
        auth_headers,
        contact_id=contact["id"],
        description="Front elevation, post-install",
    )
    assert resp.json()[0]["description"] == "Front elevation, post-install"


# --- Update endpoint ---


def test_update_folder(client, auth_headers, seeded_stages, temp_upload_dir):
    contact = _create_contact(client, auth_headers)
    up = _upload(client, auth_headers, contact_id=contact["id"], folder="General")
    doc_id = up.json()[0]["id"]

    resp = client.patch(
        f"/api/documents/{doc_id}",
        json={"folder": "Insurance Documents"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["folder"] == "Insurance Documents"


def test_update_visibility(client, auth_headers, seeded_stages, temp_upload_dir):
    contact = _create_contact(client, auth_headers)
    up = _upload(client, auth_headers, contact_id=contact["id"])
    doc_id = up.json()[0]["id"]

    resp = client.patch(
        f"/api/documents/{doc_id}",
        json={"show_in_work_order": True, "show_in_estimate": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["show_in_work_order"] is True
    assert body["show_in_estimate"] is True


def test_update_description(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    up = _upload(client, auth_headers, contact_id=contact["id"])
    doc_id = up.json()[0]["id"]

    resp = client.patch(
        f"/api/documents/{doc_id}",
        json={"description": "Updated caption"},
        headers=auth_headers,
    )
    assert resp.json()["description"] == "Updated caption"


def test_update_partial_does_not_touch_other_fields(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    up = _upload(
        client,
        auth_headers,
        contact_id=contact["id"],
        folder="Photos",
        description="original",
    )
    doc_id = up.json()[0]["id"]

    client.patch(
        f"/api/documents/{doc_id}",
        json={"show_in_work_order": True},
        headers=auth_headers,
    )
    resp = client.get(f"/api/documents/{doc_id}", headers=auth_headers)
    body = resp.json()
    assert body["folder"] == "Photos"
    assert body["description"] == "original"
    assert body["show_in_work_order"] is True


def test_update_not_found(client, auth_headers):
    resp = client.patch(
        "/api/documents/9999", json={"folder": "X"}, headers=auth_headers
    )
    assert resp.status_code == 404


# --- Get single ---


def test_get_document(client, auth_headers, seeded_stages, temp_upload_dir):
    contact = _create_contact(client, auth_headers)
    up = _upload(client, auth_headers, contact_id=contact["id"])
    doc_id = up.json()[0]["id"]

    resp = client.get(f"/api/documents/{doc_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == doc_id


def test_get_document_not_found(client, auth_headers):
    resp = client.get("/api/documents/9999", headers=auth_headers)
    assert resp.status_code == 404


# --- Uploader tracking ---


def test_uploaded_by_is_set(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    up = _upload(client, auth_headers, contact_id=contact["id"])
    doc = up.json()[0]
    assert doc["uploaded_by"] is not None
    assert doc["uploader_name"] == "Admin User"


# --- Per-entity isolation ---


def test_estimate_files_isolated_from_other_estimates(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    est_a = _create_estimate(client, auth_headers, contact["id"])
    est_b = _create_estimate(client, auth_headers, contact["id"])
    _upload(client, auth_headers, estimate_id=est_a["id"], filename="a.pdf")
    _upload(client, auth_headers, estimate_id=est_b["id"], filename="b.pdf")

    resp = client.get(
        "/api/documents",
        params={"estimate_id": est_a["id"]},
        headers=auth_headers,
    )
    names = [d["original_filename"] for d in resp.json()["items"]]
    assert names == ["a.pdf"]
