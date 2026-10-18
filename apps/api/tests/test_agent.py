import json

from app.config import Settings, get_settings
from app.main import app as fastapi_app
from app.providers.base import Completion, ProviderError
from app.services import routing
from tests.conftest import make_headers


def J(**kw) -> str:
    return json.dumps(kw)


def script(monkeypatch, replies, seen=None):
    it = iter(replies)

    async def fake(plan, messages, *, settings, keys, json_mode=False):
        if seen is not None:
            seen.append(messages)
        return Completion(text=next(it), provider="ollama", model="fake")

    monkeypatch.setattr(routing, "complete", fake)


def configure(test_settings, **kw):
    merged = Settings(**{**test_settings.model_dump(), **kw})
    fastapi_app.dependency_overrides[get_settings] = lambda: merged


def create(client, headers, goal="do it", **kw):
    r = client.post("/api/v1/agent/tasks", json={"goal": goal, **kw}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def get(client, headers, task_id):
    return client.get(f"/api/v1/agent/tasks/{task_id}", headers=headers).json()


def real(task):
    """Steps without the leading "Task created" info row."""
    return [s for s in task["steps"] if s["kind"] != "info"]


def kinds(task):
    return [s["kind"] for s in task["steps"] if s["kind"] != "info"]


def test_calculator_task_completes_with_audit_trail(client, monkeypatch, guest_headers):
    seen = []
    script(monkeypatch, [
        J(action="tool", tool="calculator", args={"expression": "12*12"}, why="exact maths"),
        J(action="final", answer="12 × 12 = 144"),
    ], seen)
    task = get(client, guest_headers, create(client, guest_headers, "What is 12*12?"))
    assert task["status"] == "completed" and task["final_answer"] == "12 × 12 = 144"
    assert kinds(task) == ["tool_call", "tool_result", "final"]
    assert real(task)[1]["content"] == "144"
    # tool output reaches the model only inside <tool_result> tags
    assert '<tool_result tool="calculator">' in seen[1][-1]["content"]


def test_side_effect_tool_needs_approval(client, monkeypatch, guest_headers):
    script(monkeypatch, [
        J(action="tool", tool="save_note", args={"title": "Plan", "content": "# Plan\nBuy milk"}, why="save it"),
        J(action="final", answer="Saved."),
    ])
    tid = create(client, guest_headers, "Save a plan note")
    task = get(client, guest_headers, tid)
    assert task["status"] == "waiting_approval"
    assert task["steps"][-1]["status"] == "pending_approval" and task["steps"][-1]["args"]["title"] == "Plan"
    assert client.get("/api/v1/documents?scope=library", headers=guest_headers).json() == []  # nothing happened yet

    done = client.post(f"/api/v1/agent/tasks/{tid}/decision", json={"approve": True}, headers=guest_headers)
    assert done.status_code == 200
    task = get(client, guest_headers, tid)
    assert task["status"] == "completed"
    library = client.get("/api/v1/documents?scope=library", headers=guest_headers).json()
    assert [d["filename"] for d in library] == ["Plan.md"] and library[0]["status"] == "ready"

    again = client.post(f"/api/v1/agent/tasks/{tid}/decision", json={"approve": True}, headers=guest_headers)
    assert again.status_code == 409


def test_denied_action_is_not_executed(client, monkeypatch, guest_headers):
    script(monkeypatch, [
        J(action="tool", tool="save_note", args={"title": "X", "content": "y"}),
        J(action="final", answer="Understood, I did not save it."),
    ])
    tid = create(client, guest_headers)
    client.post(f"/api/v1/agent/tasks/{tid}/decision", json={"approve": False}, headers=guest_headers)
    task = get(client, guest_headers, tid)
    assert task["status"] == "completed"
    assert "denied" in task["steps"][-2]["content"]
    assert client.get("/api/v1/documents?scope=library", headers=guest_headers).json() == []


def test_bad_replies_are_retried_then_abandoned(client, monkeypatch, guest_headers):
    script(monkeypatch, ["not json", J(action="tool", tool="rm_rf", args={}), J(action="final", answer="ok")])
    task = get(client, guest_headers, create(client, guest_headers))
    assert task["status"] == "completed" and kinds(task) == ["note", "note", "final"]

    script(monkeypatch, ["x", "x", "x"])
    failed = get(client, guest_headers, create(client, guest_headers))
    assert failed["status"] == "failed" and "unusable replies" in failed["error"]


def test_invalid_tool_arguments_are_rejected_before_running(client, monkeypatch, guest_headers):
    script(monkeypatch, [J(action="tool", tool="calculator", args={}), J(action="final", answer="ok")])
    task = get(client, guest_headers, create(client, guest_headers))
    assert kinds(task) == ["note", "final"] and "Invalid arguments" in real(task)[0]["content"]


def test_step_and_tool_budgets_are_enforced(client, monkeypatch, guest_headers, test_settings):
    configure(test_settings, agent_max_turns=4, agent_max_tool_calls=10)
    script(monkeypatch, [J(action="tool", tool="calculator", args={"expression": "1+1"})] * 6)
    task = get(client, guest_headers, create(client, guest_headers))
    assert task["status"] == "failed" and "step limit" in task["error"]

    configure(test_settings, agent_max_turns=8, agent_max_tool_calls=1)
    calc = J(action="tool", tool="calculator", args={"expression": "1+1"})
    script(monkeypatch, [calc, calc, J(action="final", answer="2")])
    task = get(client, guest_headers, create(client, guest_headers))
    assert task["status"] == "completed" and kinds(task) == ["tool_call", "tool_result", "note", "final"]
    assert "budget" in real(task)[2]["content"]


def test_cancel_and_ownership(client, monkeypatch, guest_headers):
    script(monkeypatch, [J(action="tool", tool="save_note", args={"title": "a", "content": "b"})])
    tid = create(client, guest_headers)
    other = make_headers(client)
    for method, path in [("get", f"/api/v1/agent/tasks/{tid}"), ("post", f"/api/v1/agent/tasks/{tid}/cancel"),
                         ("delete", f"/api/v1/agent/tasks/{tid}")]:
        assert getattr(client, method)(path, headers=other).status_code == 404
    assert client.get("/api/v1/agent/tasks", headers=other).json() == []

    cancelled = client.post(f"/api/v1/agent/tasks/{tid}/cancel", headers=guest_headers).json()
    assert cancelled["status"] == "cancelled"
    assert client.post(f"/api/v1/agent/tasks/{tid}/decision", json={"approve": True}, headers=guest_headers).status_code == 409
    assert client.delete(f"/api/v1/agent/tasks/{tid}", headers=guest_headers).status_code == 204


def test_library_search_tool_only_when_enabled(client, monkeypatch, guest_headers):
    up = client.post("/api/v1/documents", files={"file": ("notes.txt", b"The secret codename is Bluebird.", "text/plain")},
                     data={"scope": "library"}, headers=guest_headers).json()
    assert client.get(f"/api/v1/documents/{up['id']}", headers=guest_headers).json()["status"] == "ready"

    search = J(action="tool", tool="search_documents", args={"query": "codename"})
    script(monkeypatch, [search, J(action="final", answer="Bluebird")])
    task = get(client, guest_headers, create(client, guest_headers, "find the codename", use_knowledge=True))
    assert task["status"] == "completed" and "Bluebird" in real(task)[1]["content"]

    script(monkeypatch, [search, J(action="final", answer="no access")])
    task = get(client, guest_headers, create(client, guest_headers, "find the codename", use_knowledge=False))
    assert kinds(task) == ["note", "final"] and "Unknown tool" in real(task)[0]["content"]


def test_model_failure_marks_task_failed_and_web_needs_config(client, monkeypatch, guest_headers):
    async def down(*_a, **_k):
        raise ProviderError("unavailable", "Cannot reach Ollama at http://127.0.0.1:11434. Is `ollama serve` running?")

    monkeypatch.setattr(routing, "complete", down)
    task = get(client, guest_headers, create(client, guest_headers))
    assert task["status"] == "failed" and "ollama serve" in task["error"]

    assert client.post("/api/v1/agent/tasks", json={"goal": "x", "web_search": True}, headers=guest_headers).status_code == 501
    tools = {t["name"]: t for t in client.get("/api/v1/agent/tools", headers=guest_headers).json()}
    assert tools["save_note"]["requires_approval"] is True and tools["web_search"]["available"] is False
