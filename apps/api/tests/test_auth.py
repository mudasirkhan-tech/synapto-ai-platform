def test_register_login_me(client):
    reg = client.post("/api/v1/auth/register", json={"email": "A@Example.com", "password": "correct horse"})
    assert reg.status_code == 200
    assert reg.json()["user"]["email"] == "a@example.com"

    dup = client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "correct horse"})
    assert dup.status_code == 409

    bad = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong password"})
    assert bad.status_code == 401

    ok = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "correct horse"})
    token = ok.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200 and me.json()["is_guest"] is False


def test_guest_and_unauthenticated(client):
    assert client.get("/api/v1/conversations").status_code == 401
    guest = client.post("/api/v1/auth/guest").json()
    assert guest["user"]["is_guest"] is True
    res = client.get("/api/v1/conversations", headers={"Authorization": f"Bearer {guest['access_token']}"})
    assert res.status_code == 200 and res.json() == []
