"""Tests for GET /api/contacts/{contact_id}/documents (Sprint 15.6b)."""
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


def _upload_for_contact(
    client,
    auth_headers,
    contact_id,
    filename="contact-doc.pdf",
    content=b"contact direct content",
):
    return client.post(
        "/api/documents",
        data={"contact_id": str(contact_id)},
        files=[("files", (filename, io.BytesIO(content), "application/pdf"))],
        headers=auth_headers,
    )


def _upload_for_job(
    client,
    auth_headers,
    job_id,
    filename="job-doc.pdf",
    content=b"job content",
):
    return client.post(
        "/api/documents",
        data={"job_id": str(job_id)},
        files=[("files", (filename, io.BytesIO(content), "application/pdf"))],
        headers=auth_headers,
    )


def test_contact_documents_returns_documents_linked_directly(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    _upload_for_contact(client, auth_headers, contact["id"])

    resp = client.get(
        f"/api/contacts/{contact['id']}/documents", headers=auth_headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["original_filename"] == "contact-doc.pdf"


def test_contact_documents_returns_documents_linked_via_job(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact = _create_contact(client, auth_headers)
    job = _create_job(client, auth_headers, contact["id"])
    _upload_for_job(client, auth_headers, job["id"], filename="legacy.pdf")

    resp = client.get(
        f"/api/contacts/{contact['id']}/documents", headers=auth_headers
    )
    assert resp.status_code == 200
    titles = [d["original_filename"] for d in resp.json()["items"]]
    assert "legacy.pdf" in titles


def test_contact_documents_excludes_other_contact_documents(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    contact_a = _create_contact(client, auth_headers, "Client A")
    contact_b = _create_contact(client, auth_headers, "Client B")
    _upload_for_contact(client, auth_headers, contact_a["id"], filename="a.pdf")
    _upload_for_contact(client, auth_headers, contact_b["id"], filename="b.pdf")

    resp = client.get(
        f"/api/contacts/{contact_a['id']}/documents", headers=auth_headers
    )
    titles = [d["original_filename"] for d in resp.json()["items"]]
    assert titles == ["a.pdf"]


def test_contact_documents_returns_empty_for_contact_with_no_docs(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    resp = client.get(
        f"/api/contacts/{contact['id']}/documents", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


def test_contact_documents_requires_auth(
    client, auth_headers, seeded_stages
):
    contact = _create_contact(client, auth_headers)
    resp = client.get(f"/api/contacts/{contact['id']}/documents")
    assert resp.status_code == 401


def test_contact_documents_404_for_unknown_contact(client, auth_headers):
    resp = client.get("/api/contacts/9999/documents", headers=auth_headers)
    assert resp.status_code == 404


def test_contact_documents_dedupes_when_doc_has_both_links(
    client, auth_headers, seeded_stages, temp_upload_dir
):
    """Uploading via contact_id also stamps job_id (most-recent job).
    The dual-lookup query must not return that doc twice."""
    contact = _create_contact(client, auth_headers)
    _create_job(client, auth_headers, contact["id"])  # ensures upload links a job_id
    _upload_for_contact(client, auth_headers, contact["id"], filename="dual.pdf")

    resp = client.get(
        f"/api/contacts/{contact['id']}/documents", headers=auth_headers
    )
    data = resp.json()
    assert len([d for d in data["items"] if d["original_filename"] == "dual.pdf"]) == 1
