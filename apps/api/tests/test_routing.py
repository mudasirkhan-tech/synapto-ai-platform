import asyncio

from app.config import Settings
from app.providers.base import ModelSpec
from app.services import routing
from tests.fakes import FakeProvider, err, install

KEYS = {"deepseek": "k1", "gemini": "k2"}


def S(**kw):
    return Settings(deepseek_api_key=None, gemini_api_key=None, provider_retry_backoff_s=0.0, **kw)


async def collect(plan, settings, keys=KEYS, messages=None):
    return [e async for e in routing.route_stream(plan, messages or [{"role": "user", "content": "hi"}], settings=settings, keys=keys)]


def plan_for(selection="auto", settings=None, keys=KEYS, **kw):
    settings = settings or S()
    return routing.build_plan(routing.parse_selection(selection, settings), settings, keys, **kw), settings


def types_of(events):
    return [e["type"] for e in events]


def test_parse_selection():
    s = S()
    assert routing.parse_selection(None, s).auto and routing.parse_selection("auto", s).auto
    assert routing.parse_selection("deepseek:chat", s).spec.model == s.deepseek_chat_model
    assert routing.parse_selection("ollama:llama3.2:latest", s).spec.model == "llama3.2:latest"
    assert routing.parse_selection("llama3.2:latest", s).spec.provider == "ollama"  # legacy bare Ollama name
    try:
        routing.parse_selection("deepseek:nope", s)
        assert False
    except ValueError:
        pass


def test_default_priority_is_cloud_first_with_ollama_last():
    plan, _ = plan_for()
    assert [c.ref for c in plan.candidates] == ["deepseek:chat", "gemini:pro", "gemini:flash", f"ollama:{S().chat_model}"]
    plan, _ = plan_for(keys={"gemini": "k"})
    assert [c.ref for c in plan.candidates][0] == "gemini:pro"
    plan, _ = plan_for(keys={})
    assert [c.provider for c in plan.candidates] == ["ollama"] and "No cloud API key" in plan.notes[0]


def test_reasoner_chosen_for_hard_prompts_and_manual_choice_wins():
    plan, _ = plan_for(query="Please prove that the square root of two is irrational using a clean argument.")
    assert plan.candidates[0].ref == "deepseek:reasoner"
    plan, _ = plan_for(query="hi there")
    assert plan.candidates[0].ref == "deepseek:chat"
    plan, _ = plan_for("gemini:flash", query="prove this theorem about prime numbers and how they are distributed")
    assert plan.candidates[0].ref == "gemini:flash" and not plan.auto


def test_vision_filter_removes_non_vision_models(monkeypatch):
    s = S()
    real = routing.cloud_specs

    def patched(settings):
        specs = real(settings)
        specs["deepseek:chat"] = ModelSpec("deepseek", "m", "chat", "DeepSeek Chat", thinking=False, vision=False)
        return specs

    monkeypatch.setattr(routing, "cloud_specs", patched)
    plan = routing.build_plan(routing.parse_selection("auto", s), s, KEYS, needs_vision=True)
    assert "deepseek:chat" not in [c.ref for c in plan.candidates] and plan.candidates[0].ref == "gemini:pro"


def test_happy_path_streams_without_touching_other_providers(monkeypatch):
    ds, gm = FakeProvider("deepseek", True, [["Hel", "lo"]]), FakeProvider("gemini", True)
    install(monkeypatch, deepseek=ds, gemini=gm)
    plan, s = plan_for()
    events = asyncio.run(collect(plan, s))
    assert types_of(events) == ["status", "token", "token", "finished"]
    assert events[0]["message"] == "Connecting to DeepSeek..." and events[-1]["provider"] == "deepseek"
    assert events[-1]["usage"] == {"prompt_tokens": 3, "completion_tokens": 4} and events[-1]["first_token_ms"] is not None
    assert gm.calls == 0


def test_rate_limit_retries_once_then_falls_back_to_gemini(monkeypatch):
    ds = FakeProvider("deepseek", True, [[err("rate_limit")], [err("rate_limit")]])
    gm = FakeProvider("gemini", True, [["from gemini"]])
    install(monkeypatch, deepseek=ds, gemini=gm)
    plan, s = plan_for()
    events = asyncio.run(collect(plan, s))
    assert ds.calls == 2  # initial attempt + exactly one retry: no infinite retries
    fb = [e for e in events if e["type"] == "fallback"][0]
    assert fb["from"] == "DeepSeek Chat" and fb["to"] == "Gemini Pro" and fb["slow"] is False
    assert events[-1]["type"] == "finished" and events[-1]["provider"] == "gemini" and events[-1]["fallback_used"] is True


def test_local_fallback_is_flagged_as_slow(monkeypatch):
    ds = FakeProvider("deepseek", True, [[err("unavailable")]] * 2)
    ol = FakeProvider("ollama", False, [["local answer"]])
    install(monkeypatch, deepseek=ds, ollama=ol)
    plan, s = plan_for(keys={"deepseek": "k"})
    events = asyncio.run(collect(plan, s, keys={"deepseek": "k"}))
    fb = [e for e in events if e["type"] == "fallback"][0]
    assert fb["slow"] is True and "much slower" in fb["message"]
    assert events[-1]["provider"] == "ollama"


def test_failure_after_text_started_is_reported_not_replaced(monkeypatch):
    ds = FakeProvider("deepseek", True, [["Hel", err("unavailable")]])
    gm = FakeProvider("gemini", True)
    install(monkeypatch, deepseek=ds, gemini=gm)
    plan, s = plan_for()
    events = asyncio.run(collect(plan, s))
    assert types_of(events)[-1] == "error" and "incomplete" in events[-1]["message"]
    assert "fallback" not in types_of(events) and gm.calls == 0 and ds.calls == 1


def test_auth_errors_fall_back_in_auto_but_not_for_manual_choice(monkeypatch):
    ds = FakeProvider("deepseek", True, [[err("auth", "DeepSeek rejected the API key.")]])
    gm = FakeProvider("gemini", True, [["ok"]])
    install(monkeypatch, deepseek=ds, gemini=gm)
    plan, s = plan_for()
    assert asyncio.run(collect(plan, s))[-1]["provider"] == "gemini"

    ds2 = FakeProvider("deepseek", True, [[err("auth", "DeepSeek rejected the API key.")]])
    gm2 = FakeProvider("gemini", True)
    install(monkeypatch, deepseek=ds2, gemini=gm2)
    plan, s = plan_for("deepseek:chat")
    events = asyncio.run(collect(plan, s))
    assert events[-1]["type"] == "error" and "rejected the API key" in events[-1]["message"] and gm2.calls == 0


def test_fallback_can_be_disabled(monkeypatch):
    ds = FakeProvider("deepseek", True, [[err("rate_limit")]] * 2)
    gm = FakeProvider("gemini", True)
    install(monkeypatch, deepseek=ds, gemini=gm)
    plan, s = plan_for(fallback=False)
    events = asyncio.run(collect(plan, s))
    assert events[-1]["type"] == "error" and gm.calls == 0


def test_missing_key_and_all_failed_messages(monkeypatch):
    install(monkeypatch, deepseek=FakeProvider("deepseek", True), gemini=FakeProvider("gemini", True))
    plan, s = plan_for("deepseek:chat", keys={})
    events = asyncio.run(collect(plan, s, keys={}))
    assert events[-1]["type"] == "error" and "API key is missing" in events[-1]["message"]

    install(monkeypatch, deepseek=FakeProvider("deepseek", True, [[err("unavailable")]] * 2),
            gemini=FakeProvider("gemini", True, [[err("unavailable", pid="gemini")]] * 4),
            ollama=FakeProvider("ollama", False, [[err("unavailable", "Cannot reach Ollama.", "ollama")]] * 2))
    plan, s = plan_for()
    assert "No provider could answer" in asyncio.run(collect(plan, s))[-1]["message"]


def test_stalled_provider_times_out_and_falls_back(monkeypatch):
    class Stalled(FakeProvider):
        async def stream(self, ctx, spec, messages):
            self.calls += 1
            await asyncio.sleep(5)
            yield None  # pragma: no cover

    install(monkeypatch, deepseek=Stalled("deepseek", True), gemini=FakeProvider("gemini", True, [["fine"]]))
    s = S(provider_first_token_timeout_s=0.05, provider_max_retries=0)
    plan, _ = plan_for(settings=s)
    events = asyncio.run(collect(plan, s))
    assert [e for e in events if e["type"] == "fallback"][0]["reason"].endswith("did not respond in time.")
    assert events[-1]["provider"] == "gemini"


def test_complete_uses_same_fallback_policy(monkeypatch):
    ds = FakeProvider("deepseek", True, [[err("rate_limit")]] * 2)
    gm = FakeProvider("gemini", True, [["answer"]])
    install(monkeypatch, deepseek=ds, gemini=gm)
    plan, s = plan_for()
    done = asyncio.run(routing.complete(plan, [{"role": "user", "content": "x"}], settings=s, keys=KEYS))
    assert done.text == "answer" and done.provider == "gemini" and ds.calls == 2
