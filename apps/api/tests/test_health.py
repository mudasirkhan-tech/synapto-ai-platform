from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

client = TestClient(app)


def test_health_ok():
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_status_reports_unreachable_runtime_honestly():
    # Port 1 is closed: the real probe path must report reachable=False, not fake success.
    app.dependency_overrides[get_settings] = lambda: Settings(ollama_url="http://127.0.0.1:1")
    try:
        res = client.get("/api/v1/status")
    finally:
        app.dependency_overrides.clear()
    body = res.json()
    assert res.status_code == 200
    assert body["runtime"]["reachable"] is False
    assert body["runtime"]["model_ready"] is False
    assert body["runtime"]["required_model"] == "llama3.2"


def test_unknown_route_uses_error_envelope():
    res = client.get("/api/v1/nope")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "http_error"
