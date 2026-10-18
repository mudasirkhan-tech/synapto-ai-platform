from app.config import Settings, get_settings
from app.main import app as fastapi_app
from app.services import llm, titles


def _stream(tokens):
    async def fake(base_url, model, messages, num_ctx):
        for t in tokens:
            yield t
    return fake


def _post_stream(client, path, headers, **body):
    with client.stream("POST", path, json=body, headers=headers) as r:
        assert r.status_code == 200
        return "".join(r.iter_text())


def test_clean_title():
    assert llm.clean_title('"Fibonacci in Python."\nextra') == "Fibonacci in Python"
    assert llm.clean_title("Title: **Study plan**") == "Study plan"
    assert llm.clean_title("   ") is None
    assert len(llm.clean_title("word " * 40)) <= 60


def test_title_event_updates_conversation(client, monkeypatch, guest_headers):
    monkeypatch.setattr(llm, "stream_chat", _stream(["Hi"]))

    async def title(settings, keys, first_message, provider, model):
        return "Friendly greeting"

    monkeypatch.setattr(titles, "generate", title)
    body = _post_stream(client, "/api/v1/chat/stream", guest_headers, message="hello there")
    assert "event: title" in body and body.index("event: done") < body.index("event: title")
    convs = client.get("/api/v1/conversations", headers=guest_headers).json()
    assert convs[0]["title"] == "Friendly greeting"


def test_model_is_forwarded_and_stored(client, monkeypatch, guest_headers):
    seen = {}

    async def spy(base_url, model, messages, num_ctx):
        seen["model"] = model
        yield "ok"

    monkeypatch.setattr(llm, "stream_chat", spy)
    _post_stream(client, "/api/v1/chat/stream", guest_headers, message="hi", model="codellama:7b")
    assert seen["model"] == "codellama:7b"
    cid = client.get("/api/v1/conversations", headers=guest_headers).json()[0]["id"]
    msgs = client.get(f"/api/v1/conversations/{cid}/messages", headers=guest_headers).json()
    assert msgs[-1]["model"] == "codellama:7b"

    bad = client.post("/api/v1/chat/stream", json={"message": "x", "model": "bad name;rm"}, headers=guest_headers)
    assert bad.status_code == 422


def test_regenerate_replaces_last_answer(client, monkeypatch, guest_headers):
    monkeypatch.setattr(llm, "stream_chat", _stream(["first"]))
    _post_stream(client, "/api/v1/chat/stream", guest_headers, message="question")
    cid = client.get("/api/v1/conversations", headers=guest_headers).json()[0]["id"]

    monkeypatch.setattr(llm, "stream_chat", _stream(["second"]))
    body = _post_stream(client, "/api/v1/chat/regenerate", guest_headers, conversation_id=cid)
    assert "second" in body

    msgs = client.get(f"/api/v1/conversations/{cid}/messages", headers=guest_headers).json()
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "question"), ("assistant", "second")]


def test_regenerate_is_owner_only(client, monkeypatch, guest_headers):
    monkeypatch.setattr(llm, "stream_chat", _stream(["x"]))
    _post_stream(client, "/api/v1/chat/stream", guest_headers, message="q")
    cid = client.get("/api/v1/conversations", headers=guest_headers).json()[0]["id"]
    other = {"Authorization": "Bearer " + client.post("/api/v1/auth/guest").json()["access_token"]}
    res = client.post("/api/v1/chat/regenerate", json={"conversation_id": cid}, headers=other)
    assert res.status_code == 404


def test_models_endpoint_when_runtime_down(client, guest_headers):
    fastapi_app.dependency_overrides[get_settings] = lambda: Settings(ollama_url="http://127.0.0.1:1")
    res = client.get("/api/v1/models", headers=guest_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["reachable"] is False and body["models"] == [] and body["default"] == "llama3.2"
    assert client.get("/api/v1/models").status_code == 401
