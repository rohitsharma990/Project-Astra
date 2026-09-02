from __future__ import annotations

import time
from typing import Any

from .models import TaskPlan, TaskStep
from .planner import TaskPlanner
from .tools import ToolRegistry, _contains_unsafe_code


class Executor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self._approved_plans: set[str] = set()

    def _resolve_reference(self, value: Any, previous_results: dict[int, dict[str, Any]]) -> Any:
        if isinstance(value, dict) and set(value.keys()) == {"ref", "field"}:
            step_id = value["ref"]
            field = value["field"]
            if step_id not in previous_results:
                raise ValueError(f"Result reference {step_id} is not available.")
            if field not in previous_results[step_id]:
                raise ValueError(f"Field '{field}' is not available for step {step_id}.")
            return previous_results[step_id][field]

        if isinstance(value, dict):
            return {key: self._resolve_reference(item, previous_results) for key, item in value.items()}

        if isinstance(value, list):
            return [self._resolve_reference(item, previous_results) for item in value]

        return value

    def _contains_reference(self, value: Any) -> bool:
        if isinstance(value, dict) and set(value.keys()) == {"ref", "field"}:
            return True
        if isinstance(value, dict):
            return any(self._contains_reference(item) for item in value.values())
        if isinstance(value, list):
            return any(self._contains_reference(item) for item in value)
        return False

    def _validate_step_arguments(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self.registry.get_tool(tool_name)
        schema = tool.input_schema
        required = set(schema.get("required", []))
        properties = schema.get("properties", {})

        for key in required:
            if key not in arguments:
                raise ValueError(f"Missing required argument '{key}' for tool '{tool_name}'.")

        for key, value in arguments.items():
            if key not in properties:
                raise ValueError(f"Unknown argument '{key}' for tool '{tool_name}'.")

            if isinstance(value, dict) and set(value.keys()) == {"ref", "field"}:
                if not isinstance(value.get("field"), str):
                    raise ValueError(f"Reference field for '{key}' must be a string.")
                continue

            expected_type = properties[key].get("type")
            if expected_type == "string":
                if isinstance(value, (dict, list)):
                    continue
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

    def approve_plan(self, plan_id: str) -> None:
        """Mark a plan as explicitly approved."""
        self._approved_plans.add(plan_id)

    def is_plan_approved(self, plan_id: str) -> bool:
        """Check if a plan has been explicitly approved."""
        return plan_id in self._approved_plans

    def execute(self, plan: TaskPlan | dict[str, Any]) -> dict[str, Any]:
        """Execute a TaskPlan or legacy dict-based plan.
        
        If the plan requires approval, it will not execute without explicit approval.
        """
        # Handle legacy dict plans by converting to TaskPlan-like structure
        if isinstance(plan, dict) and not isinstance(plan, TaskPlan):
            # Legacy dict format - convert to execution format
            steps = plan.get("steps", [])
            if not steps:
                raise ValueError("Plan must include at least one step.")

            # Validate the entire plan before invoking any tool. Legacy callers
            # retain the historical return shape, but never bypass validation.
            validated_plan = TaskPlanner(self.registry).create_plan(
                plan.get("goal", ""), steps, validate_references=False
            )
            steps = [
                {
                    "id": step.step_id,
                    "tool": step.tool,
                    "arguments": step.arguments,
                    "reason": step.reason,
                }
                for step in validated_plan.steps
            ]

            previous_results: dict[int, dict[str, Any]] = {}
            execution_log = []
            failed = False

            for step in steps:
                step_id = step["id"]
                tool_name = step["tool"]
                raw_arguments = step["arguments"]

                try:
                    arguments = self._resolve_reference(raw_arguments, previous_results)
                    if self._contains_reference(raw_arguments):
                        arguments = self._validate_step_arguments(tool_name, arguments)
                    else:
                        arguments = self._validate_step_arguments(tool_name, arguments)
                    tool = self.registry.get_tool(tool_name)
                    result = tool.func(**arguments)

                    record = {
                        "step_id": step_id,
                        "tool": tool_name,
                        "status": "success",
                        "result": result,
                    }
                    previous_results[step_id] = {"result": result, "status": "success", "tool": tool_name}
                    execution_log.append(record)
                except Exception as exc:
                    failed = True
                    record = {
                        "step_id": step_id,
                        "tool": tool_name,
                        "status": "failed",
                        "result": {"error": str(exc)},
                    }
                    previous_results[step_id] = {"result": {"error": str(exc)}, "status": "failed", "tool": tool_name}
                    execution_log.append(record)
                    break

            return {"goal": plan.get("goal", ""), "status": "failed" if failed else "success", "steps": execution_log}

        # Handle TaskPlan objects
        if not isinstance(plan, TaskPlan):
            raise ValueError("Plan must be a TaskPlan or dict.")

        # Revalidate at the execution boundary in case a caller modified the
        # plan after creation or supplied an object from an untrusted source.
        TaskPlanner(self.registry).create_plan(
            plan.goal,
            [
                {"id": step.step_id, "tool": step.tool, "arguments": step.arguments, "reason": step.reason}
                for step in plan.steps
            ],
        )

        # Check if approval is required and validate
        if plan.requires_approval and not self.is_plan_approved(plan.plan_id):
            raise ValueError(f"Plan {plan.plan_id} requires approval before execution.")

        # Execute the plan
        plan.status = "executing"
        plan.execution_timestamp = time.time()

        previous_results: dict[int, dict[str, Any]] = {}
        execution_log = []
        failed = False

        for step in plan.steps:
            step_id = step.step_id
            tool_name = step.tool
            raw_arguments = step.arguments

            try:
                arguments = self._resolve_reference(raw_arguments, previous_results)
                if self._contains_reference(raw_arguments):
                    arguments = self._validate_step_arguments(tool_name, arguments)
                else:
                    arguments = self._validate_step_arguments(tool_name, arguments)

                tool = self.registry.get_tool(tool_name)
                result = tool.func(**arguments)

                step.status = "success"
                step.result = result

                record = {
                    "step_id": step_id,
                    "tool": tool_name,
                    "status": "success",
                    "result": result,
                }
                previous_results[step_id] = {"result": result, "status": "success", "tool": tool_name}
                execution_log.append(record)
            except Exception as exc:
                failed = True
                step.status = "failed"
                step.error = str(exc)

                record = {
                    "step_id": step_id,
                    "tool": tool_name,
                    "status": "failed",
                    "result": {"error": str(exc)},
                }
                previous_results[step_id] = {"result": {"error": str(exc)}, "status": "failed", "tool": tool_name}
                execution_log.append(record)
                break

        plan.status = "completed" if not failed else "failed"

        return {
            "plan_id": plan.plan_id,
            "goal": plan.goal,
            "status": "failed" if failed else "success",
            "steps": execution_log,
            "requires_approval": plan.requires_approval,
        }


__all__ = ["Executor"]
