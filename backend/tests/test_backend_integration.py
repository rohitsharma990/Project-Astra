from __future__ import annotations

from pathlib import Path

import pytest

from app.agent.planner import TaskPlanner
from app.agent.tools import default_registry
from app.runtime import BackendRuntime


class _PlannerResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


def _memory_manager(monkeypatch, facts: dict[str, str]):
    from app.ai.manager import AIManager
    import app.ai.conversation_memory as memory

    monkeypatch.setattr(memory, "get_all_user_facts", lambda: dict(facts))
    manager = AIManager()
    manager._provider = lambda prompt, history: "model fallback"
    return manager


def test_normal_ai_uses_stored_name(monkeypatch):
    manager = _memory_manager(monkeypatch, {"name": "Rohit"})

    assert manager.ask_ai("What is my name?") == "Your name is Rohit."


def test_normal_ai_unknown_personal_fact_is_safe(monkeypatch):
    manager = _memory_manager(monkeypatch, {})

    assert manager.ask_ai("What is my name?") == "I don't know your name yet."


def test_normal_ai_does_not_inject_personal_memory_for_unrelated_question(monkeypatch):
    manager = _memory_manager(monkeypatch, {"name": "Rohit"})
    prompts: list[str] = []
    manager._provider = lambda prompt, history: prompts.append(prompt) or "Python answer"

    assert manager.ask_ai("What is Python?") == "Python answer"
    assert "KNOWN USER FACTS" not in prompts[0]


def test_normal_question_reaches_single_response_boundary(monkeypatch):
    responses: list[str] = []
    import app.parser as parser

    monkeypatch.setattr(parser, "ask_ai", lambda prompt: "Python is a programming language.")
    monkeypatch.setattr(parser.ui, "speak_assistant_reply", lambda response: responses.append(response))

    result = BackendRuntime().process("What is Python?")

    assert result["mode"] == "normal"
    assert responses == ["Python is a programming language."]


def test_memory_returns_stored_name_without_invention(monkeypatch):
    import app.parser as parser
    from app.ai import user_facts

    monkeypatch.setattr(parser, "get_user_fact", lambda key: "Astra User" if key == "name" else None)
    responses: list[str] = []
    monkeypatch.setattr(parser.ui, "assistant_message", lambda response: responses.append(response))

    parser.parse_command("What is my name?")

    assert responses == ["Your name is Astra User."]


def test_agent_note_requires_explicit_approval(tmp_path: Path, monkeypatch):
    import app.agent.tools as tools

    monkeypatch.setattr(tools, "DATA_DIR", tmp_path)
    agent = __import__("app.agent", fromlist=["AstraAgent"]).AstraAgent()
    plan = agent.run_goal(
        "Create a note titled Backend Test with content Astra backend is working.",
        [{
            "id": 1,
            "tool": "create_note",
            "arguments": {"title": "Backend Test", "content": "Astra backend is working."},
            "reason": "Save the requested backend test note.",
        }],
    )

    assert plan["status"] == "approval_required"
    assert not (tmp_path / "notes.json").exists()

    result = agent.approve_plan(plan["plan_id"])

    assert result["status"] == "success"
    assert (tmp_path / "notes.json").exists()


def test_multi_step_weather_then_note_uses_reference(tmp_path: Path, monkeypatch):
    import app.agent.tools as tools

    monkeypatch.setattr(tools, "DATA_DIR", tmp_path)
    monkeypatch.setattr(tools, "weather_fetch_weather", lambda city: {"city": city})
    planner = TaskPlanner(default_registry(), ai_planner=None)
    plan = planner.create_plan("Check the weather in Delhi and create a note with the result.")

    assert [step.tool for step in plan.steps] == ["get_weather", "create_note"]
    assert plan.steps[1].arguments["content"] == {"ref": 1, "field": "result"}
    assert plan.requires_approval


def test_file_search_request_maps_to_safe_registered_tool():
    planner = TaskPlanner(default_registry(), ai_planner=None)

    plan = planner.create_plan("Find my Python project files and tell me what you found.")

    assert len(plan.steps) == 1
    assert plan.steps[0].tool == "find_files"
    assert plan.steps[0].arguments["query"]
    assert not plan.requires_approval


def test_invalid_and_unsafe_plans_are_rejected():
    planner = TaskPlanner(default_registry(), ai_planner=None)

    with pytest.raises(ValueError, match="Unknown tool"):
        planner.create_plan("bad", [{"id": 1, "tool": "run_shell", "arguments": {}, "reason": "bad"}])

    with pytest.raises(ValueError, match="Unsafe"):
        planner.create_plan("bad", [{"id": 1, "tool": "echo", "arguments": {"text": "eval("}, "reason": "bad"}])

    with pytest.raises(ValueError, match="Missing required"):
        planner.create_plan("bad", [{"id": 1, "tool": "create_note", "arguments": {"title": "x"}, "reason": "bad"}])


def test_ollama_planner_rejects_string_step_id():
    from app.agent.ollama_planner import OllamaPlanGenerator

    generator = OllamaPlanGenerator(
        request_post=lambda *args, **kwargs: _PlannerResponse(
            '{"goal":"bad","steps":[{"id":"step1","tool":"find_files","arguments":{"query":"Python"},"reason":"search"}]}'
        )
    )

    with pytest.raises(ValueError, match="Step id must be a positive integer"):
        TaskPlanner(default_registry(), plan_generator=generator).create_plan("bad")


def test_ollama_planner_accepts_integer_step_id():
    from app.agent.ollama_planner import OllamaPlanGenerator

    generator = OllamaPlanGenerator(
        request_post=lambda *args, **kwargs: _PlannerResponse(
            '{"goal":"good","steps":[{"id":1,"tool":"find_files","arguments":{"query":"Python"},"reason":"search"}]}'
        )
    )

    plan = TaskPlanner(default_registry(), plan_generator=generator).create_plan("good")

    assert plan.steps[0].step_id == 1
    assert plan.steps[0].tool == "find_files"


def test_ollama_client_propagates_configured_timeout(monkeypatch):
    import requests
    from app.ai.ollama import OllamaClient

    observed: dict[str, object] = {}

    def timed_out(*args, **kwargs):
        observed.update(kwargs)
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr("app.ai.ollama.requests.post", timed_out)
    with pytest.raises(RuntimeError, match="took too long"):
        OllamaClient().ask("hello")
    assert observed["timeout"] == OllamaClient().timeout


def test_planner_timeout_is_controlled():
    import requests
    from app.agent.ollama_planner import OllamaPlanGenerator, OllamaUnavailable
    from app.config import AGENT_PLANNER_TIMEOUT

    calls = 0

    def timed_out(*args, **kwargs):
        nonlocal calls
        calls += 1
        assert kwargs["timeout"] == AGENT_PLANNER_TIMEOUT
        raise requests.exceptions.Timeout("timed out")

    with pytest.raises(OllamaUnavailable):
        OllamaPlanGenerator(request_post=timed_out)("Find files", default_registry().list_tools())
    assert calls == 1


def test_router_attempts_agent_once_on_timeout(monkeypatch):
    import app.agent.router as router

    calls = 0

    class TimedOutAgent:
        def run_goal(self, goal, require_approval=False):
            nonlocal calls
            calls += 1
            raise TimeoutError("planner timed out")

    monkeypatch.setattr(router, "AstraAgent", TimedOutAgent)
    result = router.handle_agent_request("Find my Python project files and tell me what you found.")

    assert calls == 1
    assert result["mode"] == "normal"
    assert "safely" in result["response"]


def test_normal_ollama_payload_is_bounded(monkeypatch):
    from app.ai.ollama import OllamaClient

    captured: dict[str, object] = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "answer"}}

    def request(*args, **kwargs):
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr("app.ai.ollama.requests.post", request)
    assert OllamaClient().ask("What is Python?") == "answer"
    payload = captured["json"]
    assert payload["think"] is False
    assert payload["options"]["num_predict"] == 128
    assert payload["options"]["temperature"] == 0


def test_planner_payload_is_compact_and_bounded():
    from app.agent.ollama_planner import OllamaPlanGenerator

    captured: dict[str, object] = {}

    def request(*args, **kwargs):
        captured.update(kwargs)
        return _PlannerResponse(
            '{"goal":"Find Python files","steps":[{"id":1,"tool":"find_files","arguments":{"query":"Python"},"reason":"search"}]}'
        )

    from app.config import AGENT_PLANNER_NUM_PREDICT

    OllamaPlanGenerator(
        request_post=request,
        request_get=lambda *a, **k: type("R", (), {"raise_for_status": lambda s: None, "json": lambda s: {"models": [{"name": "qwen3:4b"}]}})(),
    )("Find Python files", default_registry().list_tools())
    payload = captured["json"]
    assert payload["think"] is False
    assert payload["options"]["num_predict"] == AGENT_PLANNER_NUM_PREDICT
    assert payload["options"]["temperature"] == 0
    assert [tool["name"] for tool in __import__("json").loads(payload["messages"][1]["content"])["available_tools"]] == ["find_files"]
