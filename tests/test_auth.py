import pytest


@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/api/auth/register", json={
        "email": "newuser@test.com",
        "password": "password123"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newuser@test.com"
    assert data["role"] == "user"
    assert data["credit_balance"] == 0


@pytest.mark.asyncio
async def test_register_duplicate(client):
    await client.post("/api/auth/register", json={"email": "dup@test.com", "password": "pass123"})
    resp = await client.post("/api/auth/register", json={"email": "dup@test.com", "password": "pass456"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_admin(client):
    # Admin is auto-created from env
    resp = await client.post("/api/auth/login", json={
        "email": "admin@tokenrelay.com",
        "password": "admin123456"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid(client):
    resp = await client.post("/api/auth/login", json={
        "email": "no@user.com",
        "password": "wrong"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client):
    # Register, login, then access /me
    await client.post("/api/auth/register", json={"email": "me@test.com", "password": "pass123"})
    login_resp = await client.post("/api/auth/login", json={"email": "me@test.com", "password": "pass123"})
    token = login_resp.json()["access_token"]

    resp = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.com"


@pytest.mark.asyncio
async def test_refresh_token(client):
    resp = await client.post("/api/auth/login", json={
        "email": "admin@tokenrelay.com",
        "password": "admin123456"
    })
    refresh = resp.json()["refresh_token"]

    resp2 = await client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert resp2.status_code == 200
    assert "access_token" in resp2.json()
