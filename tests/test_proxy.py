import json

import pytest


@pytest.mark.asyncio
async def test_chat_completion_no_api_key(client):
    resp = await client.post("/v1/chat/completions", json={
        "model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_models_no_api_key(client):
    resp = await client.get("/v1/models")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_chat_completion_model_not_found(client):
    # Register and get API key
    await client.post("/api/auth/register", json={"email": "proxy@test.com", "password": "password123"})
    login = await client.post("/api/auth/login", json={"email": "proxy@test.com", "password": "password123"})
    token = login.json()["access_token"]

    # Create API key
    key_resp = await client.post("/api/users/me/keys", json={"name": "test"},
                                  headers={"Authorization": f"Bearer {token}"})
    full_key = key_resp.json()["full_key"]

    # Try calling with nonexistent model
    resp = await client.post("/v1/chat/completions",
        json={"model": "nonexistent-model", "messages": [{"role": "user", "content": "hi"}]},
        headers={"Authorization": f"Bearer {full_key}"}
    )
    assert resp.status_code == 404
    data = json.loads(resp.content)
    assert data["error"]["code"] == "model_not_found"


@pytest.mark.asyncio
async def test_models_list(client):
    # Register and get API key
    await client.post("/api/auth/register", json={"email": "models@test.com", "password": "password123"})
    login = await client.post("/api/auth/login", json={"email": "models@test.com", "password": "password123"})
    token = login.json()["access_token"]

    key_resp = await client.post("/api/users/me/keys", json={"name": "test"},
                                  headers={"Authorization": f"Bearer {token}"})
    full_key = key_resp.json()["full_key"]

    resp = await client.get("/v1/models", headers={"Authorization": f"Bearer {full_key}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_api_key_crud(client):
    # Register
    await client.post("/api/auth/register", json={"email": "keys@test.com", "password": "password123"})
    login = await client.post("/api/auth/login", json={"email": "keys@test.com", "password": "password123"})
    token = login.json()["access_token"]

    # Create key
    resp = await client.post("/api/users/me/keys", json={"name": "my-key"},
                              headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    key_data = resp.json()
    assert key_data["name"] == "my-key"
    assert key_data["full_key"].startswith("tsk-")

    # List keys
    resp = await client.get("/api/users/me/keys", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    # Delete key
    resp = await client.delete(f"/api/users/me/keys/{key_data['id']}",
                                headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204

    # Verify deleted
    resp = await client.get("/api/users/me/keys", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()) == 0
