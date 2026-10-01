import io


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


def _upload_file(
    client, auth_headers, job_id,
    filename="test.pdf", content=b"fake pdf content",
    content_type="application/pdf",
):
    return client.post(
        "/api/documents",
        data={"job_id": str(job_id)},
        files=[("files", (filename, io.BytesIO(content), content_type))],
        headers=auth_headers,
    )


# --- Upload ---


def test_upload_single_file(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = _upload_file(client, auth_headers, job["id"])
    assert resp.status_code == 201
    data = resp.json()
    assert len(data) == 1
    assert data[0]["original_filename"] == "test.pdf"
    assert data[0]["content_type"] == "application/pdf"
    assert data[0]["file_size"] == len(b"fake pdf content")


def test_upload_multiple_files(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = client.post(
        "/api/documents",
        data={"job_id": str(job["id"])},
        files=[
            ("files", ("a.pdf", io.BytesIO(b"pdf1"), "application/pdf")),
            ("files", ("b.png", io.BytesIO(b"png1"), "image/png")),
        ],
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 2


def test_upload_invalid_type(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    job = _create_job(client, auth_headers, seeded_stages)
    resp = _upload_file(
        client, auth_headers, job["id"],
        filename="malware.exe",
        content_type="application/octet-stream",
    )
    assert resp.status_code == 400
    assert "not allowed" in resp.json()["detail"]


def test_upload_invalid_job(client, auth_headers, temp_upload_dir):
    resp = _upload_file(client, auth_headers, 9999)
    assert resp.status_code == 400


# --- List ---


def test_list_documents_by_job(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    job = _create_job(client, auth_headers, seeded_stages)
    _upload_file(client, auth_headers, job["id"], filename="a.pdf")
    _upload_file(client, auth_headers, job["id"], filename="b.pdf")

    resp = client.get(
        "/api/documents",
        params={"job_id": job["id"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


# --- Download ---


def test_download_file(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    job = _create_job(client, auth_headers, seeded_stages)
    content = b"real pdf content here"
    upload_resp = _upload_file(
        client, auth_headers, job["id"], content=content
    )
    doc_id = upload_resp.json()[0]["id"]

    resp = client.get(
        f"/api/documents/{doc_id}/download", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.content == content
    assert "application/pdf" in resp.headers.get("content-type", "")


def test_download_not_found(client, auth_headers):
    resp = client.get(
        "/api/documents/9999/download", headers=auth_headers
    )
    assert resp.status_code == 404


# --- Delete ---


def test_delete_document(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    job = _create_job(client, auth_headers, seeded_stages)
    upload_resp = _upload_file(client, auth_headers, job["id"])
    doc_id = upload_resp.json()[0]["id"]

    resp = client.delete(
        f"/api/documents/{doc_id}", headers=auth_headers
    )
    assert resp.status_code == 204

    # Verify gone
    resp = client.get(
        "/api/documents",
        params={"job_id": job["id"]},
        headers=auth_headers,
    )
    assert resp.json()["total"] == 0


def test_delete_document_not_found(client, auth_headers):
    resp = client.delete("/api/documents/9999", headers=auth_headers)
    assert resp.status_code == 404


# --- Auth ---


def test_documents_require_auth(client):
    resp = client.get("/api/documents", params={"job_id": 1})
    assert resp.status_code == 401


# --- Sprint 15a: Contact-centric uploads and dual lookup ---


def test_upload_by_contact_id(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    """Uploading with contact_id instead of job_id should succeed."""
    contact = _create_contact(client, auth_headers, name="Direct Contact")
    resp = client.post(
        "/api/documents",
        data={"contact_id": str(contact["id"])},
        files=[("files", ("note.pdf", io.BytesIO(b"hi"), "application/pdf"))],
        headers=auth_headers,
    )
    assert resp.status_code == 201
    doc = resp.json()[0]
    assert doc["contact_id"] == contact["id"]


def test_upload_requires_job_or_contact(
    client, auth_headers, temp_upload_dir
):
    resp = client.post(
        "/api/documents",
        files=[("files", ("x.pdf", io.BytesIO(b"y"), "application/pdf"))],
        headers=auth_headers,
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "job_id" in detail and "contact_id" in detail


def test_list_documents_by_contact_includes_legacy_job_docs(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    """Listing by contact_id returns docs linked directly AND via legacy job."""
    job = _create_job(client, auth_headers, seeded_stages)
    contact_id = job["contact_id"]

    # Upload one via job_id (legacy path)
    _upload_file(client, auth_headers, job["id"], filename="legacy.pdf")
    # Upload one via contact_id (new path)
    client.post(
        "/api/documents",
        data={"contact_id": str(contact_id)},
        files=[("files", ("direct.pdf", io.BytesIO(b"z"), "application/pdf"))],
        headers=auth_headers,
    )

    resp = client.get(
        "/api/documents",
        params={"contact_id": contact_id},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    names = sorted(d["original_filename"] for d in resp.json()["items"])
    assert names == ["direct.pdf", "legacy.pdf"]
