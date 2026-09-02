"""Regression tests: AI_MODEL / AGENT_MODEL separation and deterministic memory.

Covers:
1.  AI_MODEL selection
2.  AGENT_MODEL selection
3.  normal AI uses AI_MODEL
4.  planner uses AGENT_MODEL
5.  missing AGENT_MODEL handled safely (no silent fallback)
6.  stored name returns without Ollama calls
7.  unknown personal fact handled safely without Ollama calls
8.  unrelated prompt gets no personal memory injection
"""
from __future__ import annotations

import json

import pytest

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


def _tags_response(*names: str) -> _JsonResponse:
    return _JsonResponse({"models": [{"name": name} for name in names]})


# ---------------------------------------------------------------------------
# 1-2. Model configuration selection
# ---------------------------------------------------------------------------

def test_ai_model_is_the_small_conversation_model():
    assert cfg.AI_MODEL == "qwen3:1.7b"


def test_agent_model_is_the_dedicated_planner_model():
    assert cfg.AGENT_MODEL == "qwen3:4b"
    # Backward-compatible alias must always mirror AGENT_MODEL.
    assert cfg.AGENT_PLANNER_MODEL == cfg.AGENT_MODEL
    # The planner model must never silently be the conversation model.
    assert cfg.AGENT_MODEL != cfg.AI_MODEL


# ---------------------------------------------------------------------------
# 3. Normal AI uses AI_MODEL
# ---------------------------------------------------------------------------

def test_normal_ai_client_sends_ai_model(monkeypatch):
    from app.ai.ollama import OllamaClient

    captured: dict = {}

    def post(url, **kwargs):
        captured.update(kwargs["json"])
        return _ChatResponse("ok")

    monkeypatch.setattr("app.ai.ollama.requests.post", post)
    OllamaClient().ask("hello")

    assert captured["model"] == cfg.AI_MODEL


def test_normal_ai_config_uses_ai_model():
    from app.ai.config import config

    assert config.model == cfg.AI_MODEL


# ---------------------------------------------------------------------------
# 4. Planner uses AGENT_MODEL
# ---------------------------------------------------------------------------

def test_planner_generator_defaults_to_agent_model():
    from app.agent.ollama_planner import OllamaPlanGenerator

    generator = OllamaPlanGenerator()
    assert generator.model == cfg.AGENT_MODEL


def test_planner_payload_sends_agent_model():
    from app.agent.ollama_planner import OllamaPlanGenerator
    from app.agent.tools import default_registry

    captured: dict = {}

    def post(url, **kwargs):
        captured.update(kwargs)
        return _ChatResponse(
            '{"goal":"Find Python files","steps":[{"id":1,"tool":"find_files",'
            '"arguments":{"query":"Python"},"reason":"search"}]}'
        )

    generator = OllamaPlanGenerator(
        request_post=post,
        request_get=lambda *a, **k: _tags_response(cfg.AGENT_MODEL),
    )
    generator("Find Python files", default_registry().list_tools())

    assert captured["json"]["model"] == cfg.AGENT_MODEL


# ---------------------------------------------------------------------------
# 5. Missing AGENT_MODEL handled safely — no silent fallback to AI_MODEL
# ---------------------------------------------------------------------------

def test_missing_agent_model_raises_controlled_planner_failure():
    from app.agent.ollama_planner import OllamaPlanGenerator, OllamaUnavailable
    from app.agent.tools import default_registry

    posts: list = []

    def post(url, **kwargs):  # pragma: no cover - must never be reached
        posts.append(kwargs)
        raise AssertionError("planner POST must not run when model is missing")

    generator = OllamaPlanGenerator(
        request_post=post,
        request_get=lambda *a, **k: _tags_response(cfg.AI_MODEL),  # planner model absent
    )
    with pytest.raises(OllamaUnavailable, match="not installed"):
        generator("Find files", default_registry().list_tools())
    assert posts == []


def test_task_planner_does_not_fall_back_to_heuristics_when_ai_planner_unavailable():
    from app.agent.ollama_planner import OllamaUnavailable
    from app.agent.planner import TaskPlanner
    from app.agent.tools import default_registry

    def unavailable(goal, tools):
        raise OllamaUnavailable("Ollama is unavailable; agent planning did not run.")

    planner = TaskPlanner(default_registry(), ai_planner=unavailable)
    with pytest.raises(OllamaUnavailable):
        planner.create_plan("Find my Python project files and tell me what you found.")


def test_router_reports_planner_unavailable_without_executing(monkeypatch):
    import app.agent.router as router
    from app.agent.ollama_planner import OllamaUnavailable

    class UnavailableAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run_goal(self, goal, require_approval=False):
            raise OllamaUnavailable(
                "Agent planner model 'qwen3:4b' is not installed in Ollama."
            )

    monkeypatch.setattr(router, "AstraAgent", UnavailableAgent)
    result = router.handle_agent_request("Find my Python project files and tell me what you found.")

    assert result["mode"] == "agent"
    assert result["status"] == "planner_unavailable"
    assert "unavailable" in result["response"].lower()


# ---------------------------------------------------------------------------
# 6-8. Deterministic memory behaviour
# ---------------------------------------------------------------------------

def _counting_manager(monkeypatch, facts: dict[str, str]):
    from app.ai.manager import AIManager
    import app.ai.conversation_memory as memory

    calls = {"provider": 0}

    def provider(prompt, history):
        calls["provider"] += 1
        return "model answer"

    monkeypatch.setattr(memory, "get_all_user_facts", lambda: dict(facts))
    manager = AIManager()
    manager._provider = provider
    return manager, calls


def test_stored_name_answered_with_zero_ollama_calls(monkeypatch):
    manager, calls = _counting_manager(monkeypatch, {"name": "Rohit"})

    assert manager.ask_ai("What is my name?") == "Your name is Rohit."
    assert calls["provider"] == 0


def test_unknown_personal_fact_safe_with_zero_ollama_calls(monkeypatch):
    manager, calls = _counting_manager(monkeypatch, {})

    assert manager.ask_ai("What is my name?") == "I don't know your name yet."
    assert calls["provider"] == 0


def test_unrelated_prompt_gets_no_personal_memory_and_single_call(monkeypatch):
    manager, calls = _counting_manager(monkeypatch, {"name": "Rohit"})
    prompts: list[str] = []

    original_provider = manager._provider

    def recording_provider(prompt, history):
        prompts.append(prompt)
        return original_provider(prompt, history)

    manager._provider = recording_provider
    response = manager.ask_ai("What is Python?")

    assert response == "model answer"
    assert calls["provider"] == 1
    assert prompts and "KNOWN USER FACTS" not in prompts[0]