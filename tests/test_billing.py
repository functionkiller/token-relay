import pytest


@pytest.mark.asyncio
async def test_balance_default_zero(client):
    await client.post("/api/auth/register", json={"email": "bal@test.com", "password": "pass123"})
    login = await client.post("/api/auth/login", json={"email": "bal@test.com", "password": "pass123"})
    token = login.json()["access_token"]

    resp = await client.get("/api/billing/balance", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["credit_balance"] == 0
    assert data["formatted"] == "0.00 credits"


@pytest.mark.asyncio
async def test_transactions_empty(client):
    await client.post("/api/auth/register", json={"email": "txn@test.com", "password": "pass123"})
    login = await client.post("/api/auth/login", json={"email": "txn@test.com", "password": "pass123"})
    token = login.json()["access_token"]

    resp = await client.get("/api/billing/transactions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_admin_add_credits(client):
    admin_login = await client.post("/api/auth/login", json={
        "email": "admin@tokenrelay.com", "password": "admin123456"
    })
    admin_token = admin_login.json()["access_token"]

    # Register a user
    reg = await client.post("/api/auth/register", json={"email": "credit@test.com", "password": "pass123"})
    user_id = reg.json()["id"]

    # Admin adds credits
    resp = await client.post(
        f"/api/admin/users/{user_id}/credits",
        json={"amount": 5000, "note": "test bonus"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["credit_balance"] == 5000

    # User checks balance
    user_login = await client.post("/api/auth/login", json={"email": "credit@test.com", "password": "pass123"})
    user_token = user_login.json()["access_token"]
    bal = await client.get("/api/billing/balance", headers={"Authorization": f"Bearer {user_token}"})
    assert bal.json()["credit_balance"] == 5000

    # User sees transaction
    txns = await client.get("/api/billing/transactions", headers={"Authorization": f"Bearer {user_token}"})
    assert txns.json()["total"] == 1


@pytest.mark.asyncio
async def test_usage_logs_empty(client):
    await client.post("/api/auth/register", json={"email": "log@test.com", "password": "pass123"})
    login = await client.post("/api/auth/login", json={"email": "log@test.com", "password": "pass123"})
    token = login.json()["access_token"]

    resp = await client.get("/api/logs/usage", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    resp = await client.get("/api/logs/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] == 0


@pytest.mark.asyncio
async def test_admin_dashboard(client):
    login = await client.post("/api/auth/login", json={
        "email": "admin@tokenrelay.com", "password": "admin123456"
    })
    token = login.json()["access_token"]

    resp = await client.get("/api/admin/stats/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "revenue_today_cents" in data


@pytest.mark.asyncio
async def test_insufficient_credits(client):
    # Register user with no credits
    await client.post("/api/auth/register", json={"email": "poor@test.com", "password": "pass123"})
    login = await client.post("/api/auth/login", json={"email": "poor@test.com", "password": "pass123"})
    token = login.json()["access_token"]

    key_resp = await client.post("/api/users/me/keys", json={"name": "test"},
                                  headers={"Authorization": f"Bearer {token}"})
    full_key = key_resp.json()["full_key"]

    # Add a model so proxy can resolve it
    admin_login = await client.post("/api/auth/login", json={
        "email": "admin@tokenrelay.com", "password": "admin123456"
    })
    admin_token = admin_login.json()["access_token"]
    await client.post("/api/admin/models", json={
        "provider": "qwen", "model_id": "qwen-turbo", "display_name": "Qwen Turbo", "is_enabled": True
    }, headers={"Authorization": f"Bearer {admin_token}"})

    # Try calling with insufficient credits
    resp = await client.post("/v1/chat/completions",
        json={"model": "qwen-turbo", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 100},
        headers={"Authorization": f"Bearer {full_key}"}
    )
    assert resp.status_code == 402
