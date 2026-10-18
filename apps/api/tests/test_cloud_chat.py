import json

from app.config import Settings, get_settings
from app.main import app as fastapi_app
from app.providers import PROVIDERS
from app.services import titles
from tests.conftest import make_headers
from tests.fakes import FakeProvider, err, install

KEY = "sk-live-ABCDEF0123456789"


def events(body: str):
    out = []
    for block in body.strip().split("\n\n"):
        name = data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if name:
            out.append((name, data))
    return out


def chat(client, headers, **body):
    with client.stream("POST", "/api/v1/chat/stream", json=body, headers=headers) as r:
        assert r.status_code == 200, r.read()
        return events("".join(r.iter_text()))


def names(evs):
    return [n for n, _ in evs]


def add_keys(client, headers, *providers):
    for p in providers:
        key = KEY if p == "deepseek" else "AIzaSyFakeFakeFakeFakeFake123456"
        assert client.put(f"/api/v1/providers/{p}/key", json={"api_key": key}, headers=headers).status_code == 200


def first(evs, name):
    return next(d for n, d in evs if n == name)


def test_auto_uses_deepseek_first_and_reports_provider_and_usage(client, guest_headers, monkeypatch, test_settings):
    add_keys(client, guest_headers, "deepseek", "gemini")
    ds, gm = FakeProvider("deepseek", True, [["Hi", " there"]]), FakeProvider("gemini", True)
    install(monkeypatch, deepseek=ds, gemini=gm)
    evs = chat(client, guest_headers, message="hello")
    assert first(evs, "status")["message"] == "Connecting to DeepSeek..."
    tokens = [d for n, d in evs if n == "token"]
    assert [t["seq"] for t in tokens] == [1, 2] and "".join(t["text"] for t in tokens) == "Hi there"
    done = first(evs, "done")
    assert done["provider"] == "deepseek" and done["model"] == test_settings.deepseek_chat_model and done["finish"] == "complete"
    assert done["usage"] == {"prompt_tokens": 3, "completion_tokens": 4} and gm.calls == 0

    cid = client.get("/api/v1/conversations", headers=guest_headers).json()[0]["id"]
    msg = client.get(f"/api/v1/conversations/{cid}/messages", headers=guest_headers).json()[-1]
    assert (msg["provider"], msg["finish"], msg["content"]) == ("deepseek", "complete", "Hi there")


def test_manual_selection_overrides_auto_and_regenerate_honours_it(client, guest_headers, monkeypatch):
    add_keys(client, guest_headers, "deepseek", "gemini")
    ds, gm = FakeProvider("deepseek", True), FakeProvider("gemini", True, [["gemini says hi"], ["second try"]])
    install(monkeypatch, deepseek=ds, gemini=gm)
    done = first(chat(client, guest_headers, message="hello", model="gemini:pro"), "done")
    assert done["provider"] == "gemini" and ds.calls == 0
    cid = client.get("/api/v1/conversations", headers=guest_headers).json()[0]["id"]
    with client.stream("POST", "/api/v1/chat/regenerate", json={"conversation_id": cid, "model": "gemini:flash"}, headers=guest_headers) as r:
        again = events("".join(r.iter_text()))
    assert first(again, "done")["label"] == "Gemini Flash"


def test_fallback_to_local_is_announced_as_slow(client, guest_headers, monkeypatch):
    add_keys(client, guest_headers, "deepseek")
    ds = FakeProvider("deepseek", True, [[err("rate_limit")]] * 4)
    ol = FakeProvider("ollama", False, [["local reply"]])
    install(monkeypatch, deepseek=ds, ollama=ol)
    evs = chat(client, guest_headers, message="hello")
    fb = first(evs, "fallback")
    assert fb["slow"] is True and fb["to"].startswith("llama3.2")
    assert first(evs, "done")["provider"] == "ollama"
    off = chat(client, guest_headers, message="again", fallback=False)
    assert "fallback" not in names(off) and "error" in names(off)


def test_provider_failure_mid_stream_saves_partial_as_incomplete(client, guest_headers, monkeypatch):
    add_keys(client, guest_headers, "deepseek")
    install(monkeypatch, deepseek=FakeProvider("deepseek", True, [["Hel", err("unavailable", "DeepSeek is temporarily unavailable.")]]),
            gemini=FakeProvider("gemini", True), ollama=FakeProvider("ollama", False))
    evs = chat(client, guest_headers, message="hello")
    assert "incomplete" in first(evs, "error")["message"] and first(evs, "done")["finish"] == "error" and "title" not in names(evs)
    cid = client.get("/api/v1/conversations", headers=guest_headers).json()[0]["id"]
    msg = client.get(f"/api/v1/conversations/{cid}/messages", headers=guest_headers).json()[-1]
    assert (msg["content"], msg["finish"]) == ("Hel", "error")


def test_missing_key_unknown_model_and_no_key_notice(client, guest_headers, monkeypatch):
    install(monkeypatch, deepseek=FakeProvider("deepseek", True), gemini=FakeProvider("gemini", True),
            ollama=FakeProvider("ollama", False, [["local"]]))
    assert client.post("/api/v1/chat/stream", json={"message": "x", "model": "deepseek:nope"}, headers=guest_headers).status_code == 422
    evs = chat(client, guest_headers, message="hello", model="deepseek:chat", fallback=False)
    assert "API key is missing" in first(evs, "error")["message"]
    auto = chat(client, guest_headers, message="hello")
    assert any(d.get("phase") == "info" and "No cloud API key" in d["message"] for n, d in auto if n == "status")
    assert first(auto, "done")["provider"] == "ollama"


def test_tool_use_streams_progress_and_hides_tool_json(client, guest_headers, monkeypatch):
    add_keys(client, guest_headers, "deepseek")
    ds = FakeProvider("deepseek", True, [['{"tool": "calc', 'ulator", "args": {"expression": "6*7"}}'], ["The answer", " is 42."]])
    install(monkeypatch, deepseek=ds)
    evs = chat(client, guest_headers, message="what is 6*7?", tools=True)
    assert names(evs).index("tool_start") < names(evs).index("tool_result") < names(evs).index("token")
    assert first(evs, "tool_start")["tool"] == "calculator" and first(evs, "tool_start")["message"] == "Calculating..."
    assert first(evs, "tool_result")["ok"] is True and first(evs, "tool_result")["preview"] == "42"
    assert "".join(d["text"] for n, d in evs if n == "token") == "The answer is 42."  # no raw JSON leaked to the user
    assert "calculator(" in ds.seen_messages[0][0]["content"]
    assert '<tool_result tool="calculator">' in ds.seen_messages[1][-1]["content"]
    assert [m for m in ds.seen_messages[1] if m["role"] == "assistant"][0]["content"].startswith('{"tool"')


def test_chat_tools_never_offer_actions_that_change_data(client, guest_headers, monkeypatch):
    add_keys(client, guest_headers, "deepseek")
    ds = FakeProvider("deepseek", True, [['{"tool":"save_note","args":{"title":"a","content":"b"}}'], ["I could not save it."]])
    install(monkeypatch, deepseek=ds)
    chat(client, guest_headers, message="save a note", tools=True)
    assert "save_note" not in ds.seen_messages[0][0]["content"]
    assert "Unknown tool" in ds.seen_messages[1][-1]["content"]
    assert client.get("/api/v1/documents?scope=library", headers=guest_headers).json() == []


def test_json_looking_answer_that_is_not_a_tool_call_is_shown_as_text(client, guest_headers, monkeypatch):
    add_keys(client, guest_headers, "deepseek")
    install(monkeypatch, deepseek=FakeProvider("deepseek", True, [["{ not json at all"]]))
    evs = chat(client, guest_headers, message="hi", tools=True)
    assert "".join(d["text"] for n, d in evs if n == "token") == "{ not json at all" and first(evs, "done")["finish"] == "complete"


def test_titles_use_the_same_provider_as_the_answer(client, guest_headers, monkeypatch):
    seen = []

    async def spy(settings, keys, text, provider, model):
        seen.append(provider)
        return "A title"

    monkeypatch.setattr(titles, "generate", spy)
    add_keys(client, guest_headers, "deepseek")
    install(monkeypatch, deepseek=FakeProvider("deepseek", True, [["ok"]]), ollama=FakeProvider("ollama", False, [["ok"]]))
    chat(client, guest_headers, message="hello")
    chat(client, guest_headers, message="hello again", model="ollama:llama3.2")
    assert seen == ["deepseek", "ollama"]


def test_model_catalog_reports_real_availability(client, guest_headers, monkeypatch, test_settings):
    merged = Settings(**{**test_settings.model_dump(), "ollama_url": "http://127.0.0.1:1"})
    fastapi_app.dependency_overrides[get_settings] = lambda: merged
    body = client.get("/api/v1/models", headers=guest_headers).json()
    states = {m["ref"]: m["state"] for g in body["groups"] for m in g["models"]}
    assert states["deepseek:chat"] == "needs_key" and states["gemini:pro"] == "needs_key"
    assert body["auto"]["ref"] is None and "Nothing is available" in body["auto"]["note"]
    assert [g["id"] for g in body["groups"]] == ["deepseek", "gemini", "ollama"]

    add_keys(client, guest_headers, "deepseek")

    async def remote(ctx):
        return {merged.deepseek_chat_model}

    monkeypatch.setattr(PROVIDERS["deepseek"], "list_remote_models", remote)
    body = client.get("/api/v1/models", headers=guest_headers).json()
    assert body["auto"]["ref"] == "deepseek:chat"

    async def retired(ctx):
        return {"something-else"}

    monkeypatch.setattr(PROVIDERS["deepseek"], "list_remote_models", retired)
    from app.services import catalog

    catalog.clear_cache()
    states = {m["ref"]: m for g in client.get("/api/v1/models", headers=guest_headers).json()["groups"] for m in g["models"]}
    assert states["deepseek:chat"]["state"] == "unavailable" and "retired" in states["deepseek:chat"]["detail"]
