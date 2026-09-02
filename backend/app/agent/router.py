from __future__ import annotations

import logging
import re
from typing import Any

from .agent import AstraAgent
from .ollama_planner import OllamaUnavailable
from .planner import Planner
from .tools import default_registry

logger = logging.getLogger(__name__)


TASK_HINTS = (
    "create a note",
    "save the summary",
    "find my project files",
    "search for",
    "check the weather",
    "open youtube",
    "create a todo",
    "find files",
    "and create",
    "then",
    "save",
    "remember",
    "look up",
    "compare",
)


def _looks_like_task_request(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return False

    lowered = cleaned.lower()
    if lowered in {"hello", "hi", "hey", "greetings", "good morning", "good afternoon", "good evening"}:
        return False

    if lowered.endswith("?"):
        return False

    if any(keyword in lowered for keyword in TASK_HINTS):
        return True

    if re.search(r"\b(create|save|find|search|look|check|open|compare|summarize|write)\b", lowered):
        return True

    return False


def route(user_input: str) -> dict[str, Any]:
    cleaned = (user_input or "").strip()
    if not cleaned:
        return {"mode": "normal"}

    if not _looks_like_task_request(cleaned):
        return {"mode": "normal"}

    return {"mode": "agent", "goal": cleaned}


def build_agent_steps(goal: str) -> list[dict[str, Any]]:
    """Build agent steps for a given goal.
    
    This maintains backward compatibility with the existing interface
    while now using the improved planner internally.
    """
    cleaned = (goal or "").strip()
    if not cleaned:
        raise ValueError("Goal cannot be empty.")

    plan = Planner(default_registry()).create_plan(cleaned)
    # Convert TaskPlan to dict format for backward compatibility
    return [
        {
            "id": step.step_id,
            "tool": step.tool,
            "arguments": step.arguments,
            "reason": step.reason,
        }
        for step in plan.steps
    ]


def handle_agent_request(user_input: str, agent: AstraAgent | None = None) -> dict[str, Any]:
    """Handle a request that routes to the agent.
    
    Updated to support the approval layer while maintaining backward compatibility.
    """
    decision = route(user_input)
    if decision["mode"] != "agent":
        return {
            "mode": "normal",
            "response": "This request stayed on the safe normal path.",
        }

    goal = decision["goal"]
    try:
        active_agent = agent or AstraAgent()
        result = active_agent.run_goal(goal, require_approval=False)
    except TimeoutError:
        # Bounded behavior: the router attempts planning exactly once.
        logger.warning("Agent planning timed out for goal: %s", goal)
        return {
            "mode": "normal",
            "response": "The task agent could not complete the request safely, so I kept the normal flow.",
        }
    except OllamaUnavailable as exc:
        # Controlled planner-unavailable response. Never falls back to the
        # smaller conversation model and never executes anything.
        logger.warning("Agent planner unavailable for goal %s: %s", goal, exc)
        return {
            "mode": "agent",
            "status": "planner_unavailable",
            "goal": goal,
            "response": f"The agent planner is unavailable right now. {exc}",
        }
    except ValueError as exc:
        # Controlled planner-failure response for malformed/invalid plans.
        logger.warning("Agent plan rejected for goal %s: %s", goal, exc)
        return {
            "mode": "agent",
            "status": "planner_failed",
            "goal": goal,
            "response": "I could not build a safe, valid plan for that request, so nothing was executed.",
        }
    except Exception:
        logger.exception("Agent request failed for goal: %s", goal)
        return {
            "mode": "normal",
            "response": "The task agent could not complete the request safely, so I kept the normal flow.",
        }

    # Handle approval_required response
    if result.get("status") == "approval_required":
        return {
            "mode": "agent",
            "status": "approval_required",
            "plan_id": result.get("plan_id"),
            "goal": goal,
            "steps": result.get("steps"),
            "response": f"I need your approval to execute this plan: {goal}. Please use agent.approve_plan('{result.get('plan_id')}') to proceed.",
        }

    if result.get("status") == "failed":
        failure_detail = next(
            (
                step.get("result", {}).get("error")
                for step in result.get("steps", [])
                if step.get("status") == "failed" and isinstance(step.get("result"), dict)
            ),
            None,
        )
        detail = f" Reason: {failure_detail}" if failure_detail else ""
        return {
            "mode": "normal",
            "response": f"The task agent could not complete the request safely, so I kept the normal flow.{detail}",
        }

    note_title = next(
        (
            step.get("arguments", {}).get("title")
            for step in result.get("steps", [])
            if step.get("tool") == "create_note"
        ),
        None,
    )
    response = (
        f"Task completed successfully: {result['status']}"
        if note_title is None
        else f"Task completed successfully: created note '{note_title}'."
    )
    return {"mode": "agent", "goal": goal, "result": result, "response": response}


__all__ = ["route", "build_agent_steps", "handle_agent_request"]
