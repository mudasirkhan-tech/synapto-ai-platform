import io
import json

from docx import Document as DocxDocument

from app.config import Settings, get_settings
from app.main import app as fastapi_app
from app.services import embeddings, llm
from app.services.chunking import chunk_sections
from tests.conftest import make_headers

FACT = "The secret project codename is Bluebird-77 and it launches in March."
FILLER = [f"Filler paragraph number {i} about weather and gardening and nothing else." for i in range(40)]
BIG_DOC = "\n\n".join(FILLER[:20] + [FACT] + FILLER[20:])


def upload(client, headers, name, data, scope="library"):
    res = client.post("/api/v1/documents", files={"file": (name, data, "application/octet-stream")}, data={"scope": scope}, headers=headers)
    assert res.status_code == 200, res.text
    return client.get(f"/api/v1/documents/{res.json()['id']}", headers=headers).json()  # background job has finished


def chat(client, headers, **body):
    with client.stream("POST", "/api/v1/chat/stream", json=body, headers=headers) as r:
        assert r.status_code == 200, r.read()
        return "".join(r.iter_text())


def sources_event(body: str):
    for block in body.split("\n\n"):
        if block.startswith("event: sources"):
            return json.loads(block.split("data: ", 1)[1])["sources"]
    return None


def spy_llm(monkeypatch):
    seen = {}

    async def spy(base_url, model, messages, num_ctx):
        seen["messages"] = messages
        yield "ok"

    monkeypatch.setattr(llm, "stream_chat", spy)
    return seen


def test_chunking_respects_size_pages_and_unicode():
    urdu = "پاکستان ایک خوبصورت ملک ہے۔ " * 60
    chunks = chunk_sections([(1, urdu), (2, "second page")], 300, 30)
    assert all(len(text) <= 300 + 30 + 2 for _, text in chunks)
    assert chunks[-1] == (2, "second page") and {p for p, _ in chunks} == {1, 2}


def test_library_document_is_retrieved_only_when_enabled(client, monkeypatch, guest_headers):
    seen = spy_llm(monkeypatch)
    doc = upload(client, guest_headers, "plan.txt", BIG_DOC.encode())
    assert doc["status"] == "ready" and doc["embedded"] is True and doc["chunk_count"] > 3

    body = chat(client, guest_headers, message="What is the secret project codename?", use_knowledge=True)
    assert "Bluebird-77" in seen["messages"][-1]["content"]
    sources = sources_event(body)
    assert sources and sources[0]["title"] == "plan.txt" and sources[0]["n"] == 1

    chat(client, guest_headers, message="What is the secret project codename?", use_knowledge=False)
    assert "<sources>" not in seen["messages"][-1]["content"]


def test_embedding_failure_degrades_to_keyword_search(client, monkeypatch, guest_headers):
    def broken(*_a, **_k):
        raise embeddings.EmbedError("Embedding model 'bge-m3' is not installed. Run: ollama pull bge-m3")

    monkeypatch.setattr(embeddings, "embed_texts", broken)
    seen = spy_llm(monkeypatch)
    doc = upload(client, guest_headers, "plan.txt", BIG_DOC.encode())
    assert doc["status"] == "ready" and doc["embedded"] is False and doc["error"].startswith("Keyword search only")
    chat(client, guest_headers, message="secret project codename", use_knowledge=True)
    assert "Bluebird-77" in seen["messages"][-1]["content"]


def test_small_chat_attachment_is_sent_whole_and_used_once(client, monkeypatch, guest_headers):
    seen = spy_llm(monkeypatch)
    doc = upload(client, guest_headers, "notes.txt", b"The launch code is 4242.", scope="chat")
    chat(client, guest_headers, message="what is the code?", document_ids=[doc["id"]])
    last = seen["messages"][-1]["content"]
    assert "<sources>" in last and "4242" in last and "[Attached files: notes.txt]" in last
    again = client.post("/api/v1/chat/stream", json={"message": "x", "document_ids": [doc["id"]]}, headers=guest_headers)
    assert again.status_code == 404


def test_documents_are_isolated_between_users(client, monkeypatch, guest_headers):
    seen = spy_llm(monkeypatch)
    doc = upload(client, guest_headers, "plan.txt", BIG_DOC.encode())
    other = make_headers(client)
    assert client.get(f"/api/v1/documents/{doc['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=other).status_code == 404
    assert client.get("/api/v1/documents", headers=other).json() == []
    body = chat(client, other, message="secret project codename", use_knowledge=True)
    assert sources_event(body) is None and "Bluebird" not in seen["messages"][-1]["content"]


def test_docx_and_failure_paths(client, guest_headers):
    buf = io.BytesIO()
    d = DocxDocument()
    d.add_paragraph("Quarterly report. Revenue grew by twelve percent.")
    d.save(buf)
    assert upload(client, guest_headers, "report.docx", buf.getvalue())["status"] == "ready"

    empty = upload(client, guest_headers, "blank.txt", b"   \n  ")
    assert empty["status"] == "failed" and "No readable text" in empty["error"]

    assert client.post("/api/v1/documents", files={"file": ("a.exe", b"MZ", "x/y")}, headers=guest_headers).status_code == 415
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    assert client.post("/api/v1/documents", files={"file": ("a.png", png, "image/png")}, data={"scope": "library"}, headers=guest_headers).status_code == 415
    assert client.post("/api/v1/documents", files={"file": ("a.png", b"not a png", "image/png")}, data={"scope": "chat"}, headers=guest_headers).status_code == 422


def test_image_attachment_goes_to_vision_model_and_is_served_to_owner_only(client, monkeypatch, guest_headers):
    seen = spy_llm(monkeypatch)
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    img = upload(client, guest_headers, "photo.png", png, scope="chat")
    assert img["kind"] == "image" and img["status"] == "ready"
    chat(client, guest_headers, message="describe this", document_ids=[img["id"]])
    assert seen["messages"][-1]["images"]

    assert client.get(f"/api/v1/documents/{img['id']}/file", headers=guest_headers).content == png
    assert client.get(f"/api/v1/documents/{img['id']}/file", headers=make_headers(client)).status_code == 404

    from app.services import runtime

    async def text_only(*_a, **_k):
        return {"completion"}

    monkeypatch.setattr(runtime, "get_capabilities", text_only)
    img2 = upload(client, guest_headers, "photo2.png", png, scope="chat")
    res = client.post("/api/v1/chat/stream", json={"message": "x", "document_ids": [img2["id"]]}, headers=guest_headers)
    assert res.status_code == 422 and "vision" in res.json()["error"]["message"]


def test_deleting_conversation_removes_its_files(client, monkeypatch, guest_headers, test_settings):
    spy_llm(monkeypatch)
    img = upload(client, guest_headers, "photo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 20, scope="chat")
    chat(client, guest_headers, message="hi", document_ids=[img["id"]])
    cid = client.get("/api/v1/conversations", headers=guest_headers).json()[0]["id"]
    from pathlib import Path
    files = list(Path(test_settings.data_dir).rglob("*.png"))
    assert len(files) == 1
    assert client.delete(f"/api/v1/conversations/{cid}", headers=guest_headers).status_code == 204
    assert not list(Path(test_settings.data_dir).rglob("*.png"))
