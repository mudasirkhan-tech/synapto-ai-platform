import os
import stat

import pytest

from app import db as dbmod
from app.config import Settings, get_settings
from app.main import app as fastapi_app
from app.models import ProviderCredential
from app.providers import PROVIDERS
from app.services import credentials
from tests.conftest import make_headers

KEY = "sk-live-ABCDEF0123456789"


def put(client, headers, provider="deepseek", key=KEY):
    return client.put(f"/api/v1/providers/{provider}/key", json={"api_key": key}, headers=headers)


def test_keys_are_write_only_and_encrypted_at_rest(client, guest_headers, test_settings):
    res = put(client, guest_headers)
    assert res.status_code == 200 and res.json()["configured"] and res.json()["source"] == "user"
    assert res.json()["masked"].endswith("6789") and KEY not in res.text
    listing = client.get("/api/v1/providers", headers=guest_headers)
    assert KEY not in listing.text and {p["id"]: p["configured"] for p in listing.json()} == {"deepseek": True, "gemini": False}

    with dbmod.SessionLocal() as db:
        row = db.query(ProviderCredential).one()
        assert KEY not in row.ciphertext and row.last4 == "6789"
        assert credentials.decrypt(test_settings, row.ciphertext) == KEY
        assert credentials.resolve_keys(db, row.user_id, test_settings) == {"deepseek": KEY}


def test_validation_unknown_provider_delete_and_isolation(client, guest_headers):
    assert put(client, guest_headers, key="short key with spaces").status_code == 422
    assert put(client, guest_headers, provider="openai").status_code == 404
    put(client, guest_headers)
    other = make_headers(client)
    assert all(not p["configured"] for p in client.get("/api/v1/providers", headers=other).json())
    gone = client.delete("/api/v1/providers/deepseek/key", headers=guest_headers).json()
    assert gone["configured"] is False and gone["masked"] is None


def test_server_environment_key_is_used_and_user_key_overrides(client, guest_headers, test_settings):
    merged = Settings(**{**test_settings.model_dump(), "deepseek_api_key": "sk-env-0123456789abcdef"})
    fastapi_app.dependency_overrides[get_settings] = lambda: merged
    first = {p["id"]: p for p in client.get("/api/v1/providers", headers=guest_headers).json()}["deepseek"]
    assert first["source"] == "server" and first["masked"].endswith("cdef")
    assert put(client, guest_headers).json()["source"] == "user"


def test_connection_test_does_not_store_the_key(client, guest_headers, monkeypatch):
    async def fake_test(ctx):
        assert ctx.api_key == KEY
        return True, "Connected. 2 model(s) available to this key."

    monkeypatch.setattr(PROVIDERS["deepseek"], "test", fake_test)
    ok = client.post("/api/v1/providers/deepseek/test", json={"api_key": KEY}, headers=guest_headers)
    assert ok.json() == {"ok": True, "message": "Connected. 2 model(s) available to this key."} and KEY not in ok.text
    assert client.get("/api/v1/providers", headers=guest_headers).json()[0]["configured"] is False
    assert client.post("/api/v1/providers/deepseek/test", json={}, headers=guest_headers).status_code == 422


def test_key_endpoints_are_rate_limited(client, guest_headers):
    codes = [put(client, guest_headers).status_code for _ in range(22)]
    assert codes[:20] == [200] * 20 and codes[-1] == 429


def test_login_attempts_are_limited(client):
    client.post("/api/v1/auth/register", json={"email": "a@example.com", "password": "correct horse"})
    codes = [client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong password"}).status_code for _ in range(12)]
    assert codes[0] == 401 and codes[-1] == 429


def test_master_key_file_is_created_once_with_private_permissions(tmp_path):
    s = Settings(data_dir=str(tmp_path), encryption_key=None, deepseek_api_key=None, gemini_api_key=None)
    token = credentials.encrypt(s, "secret-value-123456")
    path = tmp_path / ".secret_key"
    first = path.read_text()
    assert credentials.decrypt(s, token) == "secret-value-123456"
    credentials.encrypt(s, "another")
    assert path.read_text() == first  # never overwritten
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_undecryptable_rows_are_ignored_not_fatal(client, guest_headers, test_settings):
    put(client, guest_headers)
    wrong = Settings(**{**test_settings.model_dump(), "encryption_key": __import__("cryptography.fernet", fromlist=["Fernet"]).Fernet.generate_key().decode()})
    with dbmod.SessionLocal() as db:
        user_id = db.query(ProviderCredential).one().user_id
        assert credentials.resolve_keys(db, user_id, wrong) == {}


def test_security_headers_and_no_store_on_secret_routes(client, guest_headers):
    health = client.get("/api/v1/health")
    assert health.headers["x-content-type-options"] == "nosniff" and health.headers["x-frame-options"] == "DENY"
    assert client.get("/api/v1/providers", headers=guest_headers).headers["cache-control"] == "no-store"


def test_log_filter_scrubs_secrets():
    import logging

    record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed with key %s", (KEY,), None)
    credentials.RedactingFilter().filter(record)
    assert KEY not in record.getMessage()
