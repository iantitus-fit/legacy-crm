def _create_contact(client, auth_headers, **kwargs):
    defaults = {"name": "Test User"}
    defaults.update(kwargs)
    resp = client.post("/api/contacts", headers=auth_headers, json=defaults)
    assert resp.status_code == 201
    return resp.json()


def test_search_by_name(client, auth_headers):
    _create_contact(client, auth_headers, name="John Smith", phone="765-555-0001")
    _create_contact(client, auth_headers, name="Jane Doe", phone="765-555-0002")

    resp = client.get("/api/contacts/search", headers=auth_headers, params={"q": "John"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "John Smith"


def test_search_response_shape(client, auth_headers):
    _create_contact(
        client, auth_headers,
        name="John Smith", email="john@test.com", phone="765-555-0001",
        company="Acme Roofing", address="123 Main St", city="Kokomo",
    )
    resp = client.get("/api/contacts/search", headers=auth_headers, params={"q": "John"})
    data = resp.json()
    assert len(data) == 1
    result = data[0]
    assert "id" in result
    assert result["name"] == "John Smith"
    assert result["email"] == "john@test.com"
    assert result["phone"] == "765-555-0001"
    assert result["company"] == "Acme Roofing"
    assert result["address"] == "123 Main St"


def test_search_short_query_returns_empty(client, auth_headers):
    _create_contact(client, auth_headers, name="John Smith")
    resp = client.get("/api/contacts/search", headers=auth_headers, params={"q": "J"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_no_matches(client, auth_headers):
    _create_contact(client, auth_headers, name="John Smith")
    resp = client.get("/api/contacts/search", headers=auth_headers, params={"q": "zzzzz"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_by_phone(client, auth_headers):
    _create_contact(client, auth_headers, name="John Smith", phone="765-555-1234")
    resp = client.get("/api/contacts/search", headers=auth_headers, params={"q": "765-555"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "John Smith"


def test_search_by_company(client, auth_headers):
    _create_contact(client, auth_headers, name="John Smith", company="Legacy Exteriors")
    resp = client.get("/api/contacts/search", headers=auth_headers, params={"q": "Legacy"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["company"] == "Legacy Exteriors"


def test_search_missing_q_returns_empty(client, auth_headers):
    _create_contact(client, auth_headers, name="John Smith")
    resp = client.get("/api/contacts/search", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_unauthenticated(client):
    resp = client.get("/api/contacts/search", params={"q": "John"})
    assert resp.status_code == 401


def test_search_respects_limit(client, auth_headers):
    for i in range(5):
        _create_contact(client, auth_headers, name=f"Smith {i}", phone=f"765-000-000{i}")
    resp = client.get("/api/contacts/search", headers=auth_headers, params={"q": "Smith", "limit": 3})
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_search_case_insensitive(client, auth_headers):
    _create_contact(client, auth_headers, name="John Smith")
    resp = client.get("/api/contacts/search", headers=auth_headers, params={"q": "john"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "John Smith"
