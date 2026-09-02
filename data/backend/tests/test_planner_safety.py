"""Regression tests: planner validation, approval gates, weather, security.

Covers:
9.  valid integer step ID accepted
10. "step1" rejected
11. malformed JSON rejected
12. unknown tool rejected
13. invalid arguments rejected
14. invalid references rejected
15. note requires approval (also covered in test_backend_integration)
16. weather missing key handled safely
17. planner timeout handled safely (also covered in test_backend_integration)
18. router does not retry indefinitely (also covered in test_backend_integration)
19. invalid/unapproved plans never execute
20. no unsafe execution primitives in project source
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.agent.planner import TaskPlanner
from app.agent.tools import default_registry

import app.config as cfg


class _JsonResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _ChatResponse:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self):
        return None

    def json(self):
        return {"message": {"content": self._content}}


def _planner_with_content(content: str) -> TaskPlanner:
    from app.agent.ollama_planner import OllamaPlanGenerator

    generator = OllamaPlanGenerator(
        request_post=lambda *a, **k: _ChatResponse(content),
        request_get=lambda *a, **k: _JsonResponse(
            {"models": [{"name": cfg.AGENT_MODEL}]}
        ),
    )
    return TaskPlanner(default_registry(), plan_generator=generator)


# ---------------------------------------------------------------------------
# 9-10. Step id handling
# ---------------------------------------------------------------------------

def test_valid_integer_step_ids_accepted_with_references():
    plan = TaskPlanner(default_registry(), ai_planner=None).create_plan(
        "multi",
        [
            {"id": 1, "tool": "find_files", "arguments": {"query": "Python"}, "reason": "search"},
            {
                "id": 2,
                "tool": "echo",
                "arguments": {"text": {"ref": 1, "field": "tool"}},
                "reason": "use previous tool name",
            },
        ],
    )
    assert [step.step_id for step in plan.steps] == [1, 2]
    assert not plan.requires_approval


def test_string_step_id_step1_is_rejected():
    with pytest.raises(ValueError, match="positive integer"):
        TaskPlanner(default_registry(), ai_planner=None).create_plan(
            "bad",
            [{"id": "step1", "tool": "find_files", "arguments": {"query": "x"}, "reason": "r"}],
        )


def test_duplicate_step_ids_are_rejected():
    step = {"id": 1, "tool": "echo", "arguments": {"text": "a"}, "reason": "r"}
    with pytest.raises(ValueError, match="Duplicate step id"):
        TaskPlanner(default_registry(), ai_planner=None).create_plan("bad", [step, dict(step)])


# ---------------------------------------------------------------------------
# 11. Malformed JSON from the model is rejected, never repaired
# ---------------------------------------------------------------------------

def test_malformed_json_plan_rejected_without_execution():
    with pytest.raises(ValueError, match="invalid JSON"):
        _planner_with_content("this is definitely not json").create_plan("bad")


def test_truncated_json_plan_rejected():
    with pytest.raises(ValueError, match="invalid JSON"):
        _planner_with_content('{"goal":"bad","steps":[{"id":1,"too').create_plan("bad")


def test_truncated_generation_reported_as_truncation():
    from app.agent.ollama_planner import OllamaPlanGenerator

    class _TruncatedResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "done_reason": "length",
                "message": {"content": '{"goal":"bad","steps":[{"id":1,"too'},
            }

    generator = OllamaPlanGenerator(
        request_post=lambda *a, **k: _TruncatedResponse(),
        request_get=lambda *a, **k: _JsonResponse({"models": [{"name": cfg.AGENT_MODEL}]}),
    )
    with pytest.raises(ValueError, match="truncated"):
        TaskPlanner(default_registry(), plan_generator=generator).create_plan("bad")


def test_wrong_goal_in_plan_rejected():
    content = (
        '{"goal":"different goal","steps":[{"id":1,"tool":"find_files",'
        '"arguments":{"query":"Python"},"reason":"search"}]}'
    )
    with pytest.raises(ValueError, match="malformed task plan"):
        _planner_with_content(content).create_plan("bad")


# ---------------------------------------------------------------------------
# 12-14. Tool allowlist, argument and reference validation
# ---------------------------------------------------------------------------

def test_unknown_tool_rejected():
    with pytest.raises(ValueError, match="Unknown tool"):
        TaskPlanner(default_registry(), ai_planner=None).create_plan(
            "bad",
            [{"id": 1, "tool": "run_shell", "arguments": {}, "reason": "r"}],
        )


def test_invalid_argument_type_rejected():
    with pytest.raises(ValueError, match="must be a string"):
        TaskPlanner(default_registry(), ai_planner=None).create_plan(
            "bad",
            [{"id": 1, "tool": "find_files", "arguments": {"query": 123}, "reason": "r"}],
        )


def test_unknown_argument_rejected():
    with pytest.raises(ValueError, match="Unknown argument"):
        TaskPlanner(default_registry(), ai_planner=None).create_plan(
            "bad",
            [{"id": 1, "tool": "echo", "arguments": {"text": "hi", "cmd": "ls"}, "reason": "r"}],
        )


def test_forward_reference_rejected():
    with pytest.raises(ValueError, match="previous step"):
        TaskPlanner(default_registry(), ai_planner=None).create_plan(
            "bad",
            [{
                "id": 1,
                "tool": "echo",
                "arguments": {"text": {"ref": 2, "field": "result"}},
                "reason": "r",
            }],
        )


def test_invalid_reference_field_rejected():
    with pytest.raises(ValueError, match="Invalid reference field"):
        TaskPlanner(default_registry(), ai_planner=None).create_plan(
            "bad",
            [{
                "id": 1,
                "tool": "echo",
                "arguments": {"text": {"ref": 1, "field": "password"}},
                "reason": "r",
            }],
        )


# ---------------------------------------------------------------------------
# 15. Approval gate for persistent writes
# ---------------------------------------------------------------------------

def test_note_plan_requires_approval_before_any_write(tmp_path, monkeypatch):
    import app.agent.tools as tools
    from app.agent.executor import Executor
    from app.agent.models import TaskPlan, TaskStep

    monkeypatch.setattr(tools, "DATA_DIR", tmp_path)
    plan = TaskPlan(
        plan_id="p-test",
        goal="create note",
        steps=[TaskStep(1, "create_note", {"title": "T", "content": "C"}, "r")],
        requires_approval=True,
        safe_only=False,
    )
    executor = Executor(default_registry())

    with pytest.raises(ValueError, match="requires approval"):
        executor.execute(plan)

    assert not (tmp_path / "notes.json").exists()


# ---------------------------------------------------------------------------
# 16. Weather configuration handling — never fabricate
# ---------------------------------------------------------------------------

def test_weather_missing_key_raises_configuration_required(monkeypatch):
    import app.weather as weather

    monkeypatch.setenv("WEATHER_API_KEY", "")
    with pytest.raises(RuntimeError, match="WEATHER_API_KEY"):
        weather.fetch_weather("Delhi")


def test_weather_tool_surfaces_config_failure(monkeypatch):
    import app.weather as weather

    monkeypatch.setenv("WEATHER_API_KEY", "")
    tool = default_registry().get_tool("get_weather")
    with pytest.raises(RuntimeError, match="not configured"):
        tool.func("Delhi")


def test_weather_tool_returns_real_data(monkeypatch):
    import app.agent.tools as tools

    monkeypatch.setattr(
        tools,
        "weather_fetch_weather",
        lambda city: {"city": city, "temperature_c": 30, "summary": f"hot in {city}"},
    )
    result = tools._safe_get_weather("Delhi")
    assert result["city"] == "Delhi"
    assert result["temperature_c"] == 30


# ---------------------------------------------------------------------------
# 19. Invalid or unapproved plans never execute
# ---------------------------------------------------------------------------

def test_invalid_plan_creation_never_invokes_tools(monkeypatch):
    import app.agent.tools as tools

    executed: list[str] = []
    original_echo = tools._echo

    def spy_echo(text):
        executed.append(text)
        return original_echo(text)

    monkeypatch.setattr(tools, "_echo", spy_echo)
    with pytest.raises(ValueError):
        TaskPlanner(default_registry(), ai_planner=None).create_plan(
            "bad",
            [{"id": 1, "tool": "run_shell", "arguments": {}, "reason": "r"}],
        )
    assert executed == []


# ---------------------------------------------------------------------------
# 20. No unsafe execution primitives in shipped source
# ---------------------------------------------------------------------------

def test_no_unsafe_execution_primitives_in_source():
    root = Path(__file__).resolve().parents[1]
    scan_targets = [root / "app", root / "main.py"]
    exclude_dirs = {".venv", ".git", "__pycache__", "cache", ".pytest_cache"}
    patterns = {
        "eval(": re.compile(r"\beval\s*\("),
        "exec(": re.compile(r"\bexec\s*\("),
        "shell=True": re.compile(r"shell\s*=\s*True"),
        "os.system(": re.compile(r"os\.system\s*\("),
    }

    offenders: list[str] = []
    for target in scan_targets:
        files = [target] if target.is_file() else sorted(target.rglob("*.py"))
        for path in files:
            if exclude_dirs & set(path.parts):
                continue
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            for lineno, line in enumerate(lines, 1):
                for label, pattern in patterns.items():
                    if pattern.search(line):
                        offenders.append(f"{path.name}:{lineno} [{label}]")

    # The only permitted occurrences are the literal blocklist tokens inside
    # the input-validation denylist itself (app/agent/tools.py).
    assert offenders == ["tools.py:26 [eval(]", "tools.py:27 [exec(]"]