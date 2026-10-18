import json

from app.config import Settings, get_settings
from app.main import app as fastapi_app
from app.routers import chat as chat_router
from app.routers import features
from app.schemas import WebResult
from app.services import imagegen, llm, voice
from tests.conftest import make_headers

PNG = b"\x89PNG\r\n\x1a\n" + b"1" * 40


def configure(test_settings, **kw):
    merged = Settings(**{**test_settings.model_dump(), **kw})
    fastapi_app.dependency_overrides[get_settings] = lambda: merged


def test_capabilities_report_shape(client, guest_headers, test_settings):
    configure(test_settings, ollama_url="http://127.0.0.1:1")
    body = client.get("/api/v1/capabilities", headers=guest_headers).json()
    assert set(body) == {"embeddings", "voice", "web_search", "image_generation"}
    assert body["web_search"]["available"] is False and body["image_generation"]["available"] is False
    assert body["embeddings"]["installed"] is None  # runtime unreachable -> unknown, not a fake "ok"


def test_unconfigured_features_return_501_with_setup_help(client, monkeypatch, guest_headers):
    monkeypatch.setattr(voice, "available", lambda: False)
    r = client.post("/api/v1/voice/transcribe", files={"audio": ("a.webm", b"123", "audio/webm")}, headers=guest_headers)
    assert r.status_code == 501 and "uv sync --extra voice" in r.json()["error"]["message"]
    assert client.post("/api/v1/search", json={"query": "x"}, headers=guest_headers).status_code == 501
    assert client.post("/api/v1/images/generate", json={"prompt": "a city"}, headers=guest_headers).status_code == 501
    r = client.post("/api/v1/chat/stream", json={"message": "x", "web_search": True}, headers=guest_headers)
    assert r.status_code == 501
    assert client.get("/api/v1/conversations", headers=guest_headers).json() == []  # nothing saved on failure


def test_voice_transcription_when_available(client, monkeypatch, guest_headers):
    monkeypatch.setattr(voice, "available", lambda: True)
    monkeypatch.setattr(voice, "transcribe", lambda data, model, lang: ("سلام دنیا", "ur"))
    r = client.post("/api/v1/voice/transcribe", files={"audio": ("a.webm", b"123", "audio/webm")}, data={"language": "ur"}, headers=guest_headers)
    assert r.status_code == 200 and r.json() == {"text": "سلام دنیا", "language": "ur"}
    bad = client.post("/api/v1/voice/transcribe", files={"audio": ("a.webm", b"123", "audio/webm")}, data={"language": "../etc"}, headers=guest_headers)
    assert bad.status_code == 422


def test_web_search_results_become_cited_sources(client, monkeypatch, guest_headers, test_settings):
    configure(test_settings, searxng_url="http://search.local")

    async def fake_search(base_url, query, limit=5):
        return [WebResult(title="Python 3.13 released", url="https://python.org/news", snippet="Python 3.13 is out.")]

    monkeypatch.setattr(features, "web_search", fake_search)
    monkeypatch.setattr(chat_router, "web_search", fake_search)
    assert client.post("/api/v1/search", json={"query": "python"}, headers=guest_headers).json()[0]["url"] == "https://python.org/news"

    seen = {}

    async def spy(base_url, model, messages, num_ctx):
        seen["messages"] = messages
        yield "ok"

    monkeypatch.setattr(llm, "stream_chat", spy)
    with client.stream("POST", "/api/v1/chat/stream", json={"message": "latest python?", "web_search": True}, headers=guest_headers) as r:
        body = "".join(r.iter_text())
    block = [b for b in body.split("\n\n") if b.startswith("event: sources")][0]
    src = json.loads(block.split("data: ", 1)[1])["sources"][0]
    assert src["kind"] == "web" and src["url"] == "https://python.org/news" and src["n"] == 1
    assert "Python 3.13 is out." in seen["messages"][-1]["content"]


def test_image_generation_and_gallery(client, monkeypatch, guest_headers, test_settings):
    configure(test_settings, imagegen_url="http://sd.local")

    async def fake_txt2img(*_a, **_k):
        return PNG

    monkeypatch.setattr(imagegen, "txt2img", fake_txt2img)
    doc = client.post("/api/v1/images/generate", json={"prompt": "a futuristic city", "width": 512, "height": 512}, headers=guest_headers).json()
    assert doc["scope"] == "generated" and doc["kind"] == "image"
    assert [d["id"] for d in client.get("/api/v1/images", headers=guest_headers).json()] == [doc["id"]]
    assert client.get(f"/api/v1/documents/{doc['id']}/file", headers=guest_headers).content == PNG
    assert client.get("/api/v1/images", headers=make_headers(client)).json() == []
    assert client.post("/api/v1/images/generate", json={"prompt": "x", "width": 100}, headers=guest_headers).status_code == 422
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=guest_headers).status_code == 204


def test_calculator_and_units(client, guest_headers):
    ok = client.post("/api/v1/tools/calculate", json={"expression": "2+3*4"}, headers=guest_headers)
    assert ok.json()["result"] == 14
    for bad in ["__import__('os')", "2**5000", "1/0"]:
        assert client.post("/api/v1/tools/calculate", json={"expression": bad}, headers=guest_headers).status_code == 422
    conv = client.post("/api/v1/tools/convert", json={"value": 100, "from_unit": "c", "to_unit": "f"}, headers=guest_headers)
    assert round(conv.json()["result"], 6) == 212
    assert client.post("/api/v1/tools/convert", json={"value": 1, "from_unit": "kg", "to_unit": "m"}, headers=guest_headers).status_code == 422
    assert "length" in client.get("/api/v1/tools/units", headers=guest_headers).json()


def test_export_and_delete_all(client, monkeypatch, guest_headers):
    async def fake(base_url, model, messages, num_ctx):
        yield "hello"

    monkeypatch.setattr(llm, "stream_chat", fake)
    with client.stream("POST", "/api/v1/chat/stream", json={"message": "hi"}, headers=guest_headers) as r:
        "".join(r.iter_text())
    exported = client.get("/api/v1/conversations/export", headers=guest_headers).json()
    assert exported["conversations"][0]["messages"][1]["content"] == "hello"
    assert client.delete("/api/v1/conversations", headers=guest_headers).status_code == 204
    assert client.get("/api/v1/conversations", headers=guest_headers).json() == []
