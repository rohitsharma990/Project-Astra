from __future__ import annotations

import re
from typing import Any, Callable, Sequence
from uuid import uuid4

from .models import TaskStep, TaskPlan
from .tools import ToolRegistry, _contains_unsafe_code


class TaskPlanner:
    """Create validated plans from an injected generator or simple language rules."""

    def __init__(self, registry: ToolRegistry, plan_generator: Callable[[str, Sequence[Any]], Sequence[dict[str, Any]]] | None = None, ai_planner: Callable[[str, Sequence[Any]], Sequence[dict[str, Any]]] | None = None):
        self.registry = registry
        self.plan_generator = plan_generator
        self.ai_planner = ai_planner

    def _validate_tool_name(self, tool_name: str) -> str:
        if not isinstance(tool_name, str):
            raise ValueError("Tool name must be a string.")

        cleaned = tool_name.strip()
        if not cleaned:
            raise ValueError("Tool name cannot be empty.")

        if _contains_unsafe_code(cleaned):
            raise ValueError(f"Unsafe tool name rejected: {tool_name}")

        if not self.registry.has_tool(cleaned):
            raise ValueError(f"Unknown tool: {cleaned}")

        return cleaned

    def _validate_arguments(self, arguments: Any, tool_name: str) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ValueError(f"Tool '{tool_name}' requires a dictionary of arguments.")

        tool = self.registry.get_tool(tool_name)
        schema = tool.input_schema
        if schema.get("type") != "object":
            raise ValueError(f"Tool '{tool_name}' has an invalid schema.")

        required = set(schema.get("required", []))
        properties = schema.get("properties", {})

        for key in required:
            if key not in arguments:
                raise ValueError(f"Missing required argument '{key}' for tool '{tool_name}'.")

        for key, value in arguments.items():
            if key not in properties:
                raise ValueError(f"Unknown argument '{key}' for tool '{tool_name}'.")

            if isinstance(value, dict) and set(value.keys()) == {"ref", "field"}:
                if not isinstance(value.get("ref"), int) or value["ref"] < 1:
                    raise ValueError(f"Reference for '{key}' must be a positive step id.")
                if value.get("field") not in {"result", "status", "tool"}:
                    raise ValueError(f"Invalid reference field for '{key}'.")
                continue

            expected_type = properties[key].get("type")
            if expected_type == "string":
                if not isinstance(value, str):
                    raise ValueError(f"Argument '{key}' for tool '{tool_name}' must be a string.")
                if _contains_unsafe_code(value):
                    raise ValueError(f"Unsafe value rejected for argument '{key}' on tool '{tool_name}'.")
            elif expected_type == "integer" and not isinstance(value, int):
                raise ValueError(f"Argument '{key}' for tool '{tool_name}' must be an integer.")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                raise ValueError(f"Argument '{key}' for tool '{tool_name}' must be numeric.")
            elif expected_type == "boolean" and not isinstance(value, bool):
                raise ValueError(f"Argument '{key}' for tool '{tool_name}' must be a boolean.")
            elif expected_type == "object" and not isinstance(value, dict):
                raise ValueError(f"Argument '{key}' for tool '{tool_name}' must be an object.")

        return dict(arguments)

    def _validate_references(self, value: Any, step_id: int, step_ids: set[int]) -> None:
        if isinstance(value, dict) and set(value.keys()) == {"ref", "field"}:
            reference = value["ref"]
            if reference not in step_ids or reference >= step_id:
                raise ValueError(f"Result reference {reference} must point to a previous step.")
            return
        if isinstance(value, dict):
            for item in value.values():
                self._validate_references(item, step_id, step_ids)
        elif isinstance(value, list):
            for item in value:
                self._validate_references(item, step_id, step_ids)

    def _check_plan_requires_approval(self, steps: list[TaskStep]) -> bool:
        """Check if any step requires approval based on tool safety level."""
        for step in steps:
            tool = self.registry.get_tool(step.tool)
            if tool.safety_level == "requires_approval":
                return True
        return False

    def _validate_steps(self, steps: Sequence[dict[str, Any]], validate_references: bool = True) -> list[TaskStep]:
        """Validate and convert raw step dictionaries to TaskStep objects."""
        if steps is None:
            raise ValueError("A plan requires at least one step.")

        validated_steps = []
        seen_ids = set()

        for raw_step in steps:
            if not isinstance(raw_step, dict):
                raise ValueError("Each plan step must be a dictionary.")

            if set(raw_step.keys()) != {"id", "tool", "arguments", "reason"}:
                raise ValueError("Each plan step must include: id, tool, arguments, reason.")

            step_id = raw_step["id"]
            if not isinstance(step_id, int) or step_id < 1:
                raise ValueError("Step id must be a positive integer.")
            
            if step_id in seen_ids:
                raise ValueError(f"Duplicate step id: {step_id}")
            seen_ids.add(step_id)

            tool_name = self._validate_tool_name(raw_step["tool"])
            arguments = self._validate_arguments(raw_step["arguments"], tool_name)
            if not isinstance(raw_step["reason"], str):
                raise ValueError(f"Step {step_id} reason must be a string.")
            reason = raw_step["reason"].strip()
            if not reason:
                raise ValueError(f"Step {step_id} requires a non-empty reason.")

            task_step = TaskStep(
                step_id=step_id,
                tool=tool_name,
                arguments=arguments,
                reason=reason,
            )
            validated_steps.append(task_step)

        if not validated_steps:
            raise ValueError("A plan requires at least one step.")

        if validate_references:
            step_ids: set[int] = set()
            for step in validated_steps:
                self._validate_references(step.arguments, step.step_id, step_ids | {step.step_id})
                step_ids.add(step.step_id)

        return validated_steps

    def _natural_language_steps(self, goal: str) -> list[dict[str, Any]]:
        lowered = goal.lower()
        steps: list[dict[str, Any]] = []
        wants_weather = "weather" in lowered
        wants_files = any(word in lowered for word in ("find", "search")) and "file" in lowered
        wants_note = "note" in lowered or "notes" in lowered

        if wants_weather:
            city_match = re.search(r"weather\s+(?:in|for)\s+([\w .'-]+?)(?:\s+and\s+|[,.!?]|$)", goal, re.IGNORECASE)
            city = city_match.group(1).strip() if city_match else "London"
            steps.append({"id": 1, "tool": "get_weather", "arguments": {"city": city}, "reason": "Get the current weather."})
        elif wants_files:
            search_text = re.split(r"\s+(?:and|then)\s+(?:create|save|write)\b", goal, maxsplit=1, flags=re.IGNORECASE)[0]
            query_match = re.search(r"(?:find|search)(?:\s+for)?\s+(?:my\s+)?(?:project\s+)?(?:files?\s*)?(?:named\s+)?([^,.!?]+)?", search_text, re.IGNORECASE)
            query = (query_match.group(1) or "project").strip() if query_match else "project"
            query = query if query.lower() not in {"and", "and create a note"} else "project"
            steps.append({"id": 1, "tool": "find_files", "arguments": {"query": query}, "reason": "Find files matching the request."})

        if wants_note:
            title_match = re.search(r"(?:titled|called)\s+[\"']?([^\"']+?)[\"']?(?:\s+with|\s+and|\s+containing|\.|$)", goal, re.IGNORECASE)
            content_match = re.search(r"(?:content|containing|listing)\s+(?:is\s+)?[\"']?(.+?)[\"']?$", goal, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else ("Weather" if wants_weather else "Project Files" if wants_files else "Astra Note")
            content: Any = {"ref": 1, "field": "result"} if steps else (content_match.group(1).strip() if content_match else goal)
            steps.append({"id": len(steps) + 1, "tool": "create_note", "arguments": {"title": title, "content": content}, "reason": "Save the requested information in a note."})

        if not steps and "todo" in lowered:
            steps.append({"id": 1, "tool": "create_todo", "arguments": {"title": goal}, "reason": "Create the requested todo item."})
        if not steps:
            raise ValueError("The goal could not be mapped to a registered tool.")
        return steps

    def create_plan(self, goal: str, steps: Sequence[dict[str, Any]] | None = None, available_tools: Sequence[Any] | None = None, validate_references: bool = True) -> TaskPlan:
        """Create a validated task plan from a goal and steps.
        
        Returns a TaskPlan object (not a dict) with validation and approval classification.
        """
        cleaned_goal = (goal or "").strip()
        if not cleaned_goal:
            raise ValueError("Goal cannot be empty.")

        if steps is None:
            if self.plan_generator is not None:
                steps = self.plan_generator(cleaned_goal, available_tools or self.registry.list_tools())
            elif self.ai_planner is not None:
                # Controlled failure: never silently fall back to heuristic
                # natural-language planning when the AI planner is unavailable.
                # Nothing is executed when planning fails.
                steps = self.ai_planner(cleaned_goal, available_tools or self.registry.list_tools())
            else:
                steps = self._natural_language_steps(cleaned_goal)

        validated_steps = self._validate_steps(steps, validate_references=validate_references)

        # Determine if approval is required
        requires_approval = self._check_plan_requires_approval(validated_steps)

        # Create and return TaskPlan
        plan = TaskPlan(
            plan_id=str(uuid4()),
            goal=cleaned_goal,
            steps=validated_steps,
            requires_approval=requires_approval,
            safe_only=not requires_approval,
            status="created",
        )

        return plan


Planner = TaskPlanner

__all__ = ["TaskPlanner", "Planner"]
