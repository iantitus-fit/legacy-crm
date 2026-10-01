def test_setup_creates_admin(client):
    response = client.post(
        "/api/auth/setup",
        json={
            "email": "admin@legacy.com",
            "full_name": "Admin User",
            "password": "testpassword123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_setup_fails_when_user_exists(client, admin_token):
    response = client.post(
        "/api/auth/setup",
        json={
            "email": "another@legacy.com",
            "full_name": "Another",
            "password": "pass123",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Setup already completed"


def test_login_success(client, admin_token):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@legacy.com",
            "password": "testpassword123",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_wrong_password(client, admin_token):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "admin@legacy.com",
            "password": "wrongpassword",
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_email(client):
    response = client.post(
        "/api/auth/login",
        json={
            "email": "nobody@legacy.com",
            "password": "pass123",
        },
    )
    assert response.status_code == 401


def test_me_returns_current_user(client, admin_token, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@legacy.com"
    assert data["full_name"] == "Admin User"
    assert data["role"] == "admin"


def test_me_fails_without_token(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_register_as_admin(client, admin_token, auth_headers):
    response = client.post(
        "/api/auth/register",
        headers=auth_headers,
        json={
            "email": "staff@legacy.com",
            "full_name": "Staff User",
            "password": "staffpass123",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "staff@legacy.com"
    assert data["role"] == "staff"


def test_register_fails_without_admin(client, admin_token, auth_headers):
    # First create a staff user
    client.post(
        "/api/auth/register",
        headers=auth_headers,
        json={
            "email": "staff@legacy.com",
            "full_name": "Staff User",
            "password": "staffpass123",
        },
    )
    # Login as staff
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "staff@legacy.com", "password": "staffpass123"},
    )
    staff_token = login_resp.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Try to register as staff user
    response = client.post(
        "/api/auth/register",
        headers=staff_headers,
        json={
            "email": "another@legacy.com",
            "full_name": "Another",
            "password": "pass123",
        },
    )
    assert response.status_code == 403


def test_register_duplicate_email(client, admin_token, auth_headers):
    client.post(
        "/api/auth/register",
        headers=auth_headers,
        json={
            "email": "staff@legacy.com",
            "full_name": "Staff User",
            "password": "staffpass123",
        },
    )
    response = client.post(
        "/api/auth/register",
        headers=auth_headers,
        json={
            "email": "staff@legacy.com",
            "full_name": "Duplicate",
            "password": "pass123",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"
