from __future__ import annotations

import json
import logging
import os
import time
from uuid import uuid4
from typing import Any, Callable, Sequence

import requests

from ..config import (
    AGENT_MODEL,
    AGENT_PLANNER_NUM_PREDICT,
    AGENT_PLANNER_TIMEOUT,
    OLLAMA_BASE_URL,
)
from .tools import _contains_unsafe_code

logger = logging.getLogger(__name__)


class OllamaUnavailable(RuntimeError):
    """Raised when the local Ollama service cannot be reached."""


class OllamaPlanGenerator:
    """Ask Ollama for JSON only; this adapter never invokes registered tools."""

    def __init__(
        self,
        model: str | None = None,
        api_url: str | None = None,
        timeout: float | None = None,
        request_post: Callable[..., Any] | None = None,
        request_get: Callable[..., Any] | None = None,
    ) -> None:
        self.model = model or AGENT_MODEL
        self.api_url = api_url or os.getenv("OLLAMA_API_URL", f"{OLLAMA_BASE_URL}/api/chat")
        self.timeout = timeout if timeout is not None else AGENT_PLANNER_TIMEOUT
        self._request_post = request_post or requests.post
        self._request_get = request_get or requests.get
        self._model_verified: bool | None = None

    def _prompt(self, goal: str, available_tools: Sequence[Any]) -> str:
        lowered_goal = goal.lower()
        relevant_names = set()
        if any(word in lowered_goal for word in ("file", "files", "search")):
            relevant_names.add("find_files")
        if "weather" in lowered_goal:
            relevant_names.add("get_weather")
        if "note" in lowered_goal:
            relevant_names.add("create_note")
        if "todo" in lowered_goal:
            relevant_names.add("create_todo")
        if not relevant_names:
            relevant_names = {tool.name for tool in available_tools}

        tools = []
        for tool in available_tools:
            if tool.name not in relevant_names:
                continue
            properties = tool.input_schema.get("properties", {})
            tools.append({
                "name": tool.name,
                "description": tool.description[:120],
                "arguments": {
                    name: details.get("type", "string")
                    for name, details in properties.items()
                },
                "required": tool.input_schema.get("required", []),
            })
        schema = {
            "type": "object",
            "required": ["goal", "steps"],
            "additionalProperties": False,
            "properties": {
                "goal": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "tool", "arguments", "reason"],
                        "additionalProperties": False,
                        "properties": {
                            "id": {"type": "integer", "minimum": 1},
                            "tool": {"type": "string"},
                            "arguments": {"type": "object"},
                            "reason": {"type": "string"},
                        },
                    },
                },
            },
        }
        return json.dumps(
            {
                "instruction": (
                    "Return ONLY ONE single-line minified JSON object matching the schema. "
                    "Select only registered tools. Never return Python, shell commands, "
                    "or execution instructions."
                ),
                "output_style": (
                    "CRITICAL: your entire reply must be ONE line of minified JSON like the "
                    "examples below. NO newlines, NO indentation, NO spaces after ':' or ','. "
                    "Pretty-printed output will be rejected as truncated."
                ),
                "format_rules": [
                    "Number steps SEQUENTIALLY from 1: the first step has \"id\": 1, the second \"id\": 2, and so on. Every id MUST be a JSON integer. NEVER reuse or repeat an id.",
                    "Never use step1, step_1, string 1, or any other string as an id.",
                    "The tool must exactly match one available tool.",
                    "Arguments must always be a JSON object.",
                    "When a later step needs an earlier step's output, pass {\"ref\": <earlier step id>, \"field\": \"result\"} as the argument value. NEVER invent placeholder text for data another step provides.",
                    "Keep each reason AT MOST 15 characters (e.g. \"Get weather.\", \"Save note.\").",
                    "Use short titles of at most 12 characters.",
                    "No markdown fences, no prose outside JSON, no Python, no shell commands, no eval, no exec.",
                ],
                "examples": [
                    {
                        "goal": "Find my Python project files",
                        "steps": [{"id": 1, "tool": "find_files", "arguments": {"query": "Python"}, "reason": "Find files."}],
                    },
                    {
                        "goal": "Check the weather in Delhi and create a note with the result.",
                        "steps": [
                            {"id": 1, "tool": "get_weather", "arguments": {"city": "Delhi"}, "reason": "Get weather."},
                            {"id": 2, "tool": "create_note", "arguments": {"title": "Weather", "content": {"ref": 1, "field": "result"}}, "reason": "Save note."},
                        ],
                    },
                ],
                "schema": schema,
                "available_tools": tools,
                "goal": goal,
            },
            separators=(",", ":"),
        )

    def _reject_unsafe_output(self, value: Any) -> None:
        if isinstance(value, str) and (_contains_unsafe_code(value) or any(token in value.lower() for token in ("shell=true", "compile(", "subprocess", "os.system"))):
            raise ValueError("Unsafe instructions in AI plan output.")
        if isinstance(value, dict):
            for item in value.values():
                self._reject_unsafe_output(item)
        elif isinstance(value, list):
            for item in value:
                self._reject_unsafe_output(item)

    def _ensure_planner_model_available(self) -> None:
        """Refuse structured planning when the dedicated agent model is missing.

        The planner must NEVER silently fall back to the smaller conversation
        model. If Ollama cannot be reached at all, the check is skipped and the
        chat request itself will surface the real connection error.
        """
        if self._model_verified:
            return
        try:
            tags_url = os.getenv(
                "OLLAMA_TAGS_URL", f"{OLLAMA_BASE_URL}/api/tags"
            )
            response = self._request_get(tags_url, timeout=3.0)
            response.raise_for_status()
            installed = {
                str(entry.get("name", "")).strip()
                for entry in response.json().get("models", [])
                if isinstance(entry, dict)
            }
            base_names = {name.split(":")[0] for name in installed}
            if self.model not in installed and self.model not in base_names:
                raise OllamaUnavailable(
                    f"Agent planner model '{self.model}' is not installed in Ollama. "
                    "Structured planning is unavailable; nothing was executed."
                )
            self._model_verified = True
        except OllamaUnavailable:
            raise
        except Exception:
            # Availability unknown (Ollama offline / transient error):
            # let the actual planning request report the failure.
            logger.debug("Planner model availability check skipped", exc_info=True)

    def __call__(self, goal: str, available_tools: Sequence[Any]) -> Sequence[dict[str, Any]]:
        request_id = str(uuid4())
        started = time.perf_counter()
        self._ensure_planner_model_available()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a task planner. Output strict JSON only. Do not execute tools."},
                {"role": "user", "content": self._prompt(goal, available_tools)},
            ],
            "stream": False,
            "format": {
                "type": "object",
                "required": ["goal", "steps"],
                "additionalProperties": False,
                "properties": {
                    "goal": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["id", "tool", "arguments", "reason"],
                            "additionalProperties": False,
                            "properties": {
                                "id": {"type": "integer", "minimum": 1},
                                "tool": {"type": "string"},
                                "arguments": {"type": "object"},
                                "reason": {"type": "string"},
                            },
                        },
                    },
                },
            },
            # repeat_penalty discourages the model from anchoring on the
            # previous step's id token (observed: emitting "id": 1 twice).
            "options": {
                "num_predict": AGENT_PLANNER_NUM_PREDICT,
                "temperature": 0,
                "repeat_penalty": 1.3,
            },
            "think": False,
        }
        logger.debug(
            "planner request_start request_id=%s model=%s timeout=%s num_predict=%s",
            request_id,
            self.model,
            self.timeout,
            AGENT_PLANNER_NUM_PREDICT,
        )
        try:
            response = self._request_post(self.api_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            logger.debug("planner response_received request_id=%s elapsed_ms=%.0f", request_id, (time.perf_counter() - started) * 1000)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as exc:
            raise OllamaUnavailable("Ollama is unavailable; agent planning did not run.") from exc

        try:
            response_data = response.json()
            content = response_data["message"]["content"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Ollama returned an unreadable planner response.") from exc

        # A truncated generation can never yield a complete plan; report the
        # real cause instead of a generic parse error.
        if response_data.get("done_reason") == "length":
            logger.warning(
                "planner output truncated request_id=%s model=%s num_predict=%s",
                request_id,
                self.model,
                AGENT_PLANNER_NUM_PREDICT,
            )
            raise ValueError(
                "Ollama planner output was truncated before the JSON plan completed."
            )

        try:
            plan_data = json.loads(content)
            logger.debug("planner json_parsed request_id=%s elapsed_ms=%.0f", request_id, (time.perf_counter() - started) * 1000)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("Ollama returned an invalid JSON task plan.") from exc

        self._reject_unsafe_output(plan_data)
        if not isinstance(plan_data, dict) or set(plan_data) != {"goal", "steps"} or plan_data["goal"] != goal:
            raise ValueError("Ollama returned a malformed task plan.")
        if not isinstance(plan_data["steps"], list):
            raise ValueError("Ollama plan steps must be a list.")
        return plan_data["steps"]


__all__ = ["OllamaPlanGenerator", "OllamaUnavailable"]
