from app.services import llm


def _fake_stream(tokens):
    async def fake(base_url, model, messages, num_ctx):
        for t in tokens:
            yield t
    return fake


def _guest(client):
    token = client.post("/api/v1/auth/guest").json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_stream_persists_and_isolates(client, monkeypatch, guest_headers):
    monkeypatch.setattr(llm, "stream_chat", _fake_stream(["Hel", "lo!"]))

    with client.stream("POST", "/api/v1/chat/stream", json={"message": "hi there"}, headers=guest_headers) as r:
        body = "".join(r.iter_text())
    assert "event: meta" in body and body.count("event: token") == 2 and "event: done" in body

    convs = client.get("/api/v1/conversations", headers=guest_headers).json()
    assert len(convs) == 1 and convs[0]["title"] == "hi there"
    msgs = client.get(f"/api/v1/conversations/{convs[0]['id']}/messages", headers=guest_headers).json()
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "hi there"), ("assistant", "Hello!")]

    other = _guest(client)  # a different user must not see or delete it
    assert client.get(f"/api/v1/conversations/{convs[0]['id']}/messages", headers=other).status_code == 404
    assert client.delete(f"/api/v1/conversations/{convs[0]['id']}", headers=other).status_code == 404


def test_llm_error_is_sent_as_event(client, monkeypatch, guest_headers):
    async def broken(base_url, model, messages, num_ctx):
        raise llm.LLMError("Model 'llama3.2' is not installed. Run: ollama pull llama3.2")
        yield  # pragma: no cover

    monkeypatch.setattr(llm, "stream_chat", broken)
    with client.stream("POST", "/api/v1/chat/stream", json={"message": "hi"}, headers=guest_headers) as r:
        body = "".join(r.iter_text())
    assert "event: error" in body and "ollama pull" in body
