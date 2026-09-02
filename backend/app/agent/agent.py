from __future__ import annotations

import json
from typing import Any

from .executor import Executor
from .models import TaskAgent, TaskPlan, ApprovalRequest
from .ollama_planner import OllamaPlanGenerator
from .planner import TaskPlanner
from .tools import ToolRegistry, default_registry


class AstraAgent(TaskAgent):
    def __init__(self, registry: ToolRegistry | None = None):
        super().__init__()
        self.registry = registry or default_registry()
        self.planner = TaskPlanner(self.registry, ai_planner=OllamaPlanGenerator())
        self.executor = Executor(self.registry)
        self._pending_plans: dict[str, TaskPlan] = {}

    def run_goal(self, goal: str, steps: list[dict] | None = None, require_approval: bool = False) -> dict[str, Any]:
        """Run a goal with optional approval requirement.
        
        Args:
            goal: The natural language goal or task description
            steps: Pre-defined steps (for backward compatibility)
            require_approval: Whether approval is required before execution (not override)
        
        Returns:
            If approval is required and plan needs it:
                {"status": "approval_required", "plan_id": "...", "goal": "...", "steps": [...]}
            If plan executes:
                {"status": "success"/"failed", "steps": [...]}
        """
        # Create the plan
        plan = self.planner.create_plan(goal, steps)

        # Check if this plan should require approval
        actually_requires_approval = plan.requires_approval or require_approval

        # If approval is required and we haven't approved it, return approval request
        if actually_requires_approval and not self.executor.is_plan_approved(plan.plan_id):
            self._pending_plans[plan.plan_id] = plan
            return {
                "status": "approval_required",
                "plan_id": plan.plan_id,
                "goal": plan.goal,
                "steps": [
                    {
                        "step_id": s.step_id,
                        "tool": s.tool,
                        "arguments": s.arguments,
                        "reason": s.reason,
                    }
                    for s in plan.steps
                ],
            }

        # Execute the plan
        result = self.executor.execute(plan)
        return result

    def approve_plan(self, plan_id: str) -> dict[str, Any]:
        """Approve a pending plan and execute it.
        
        Returns:
            Execution result
        """
        if plan_id not in self._pending_plans:
            raise ValueError(f"Plan not found: {plan_id}")

        plan = self._pending_plans[plan_id]
        self.executor.approve_plan(plan_id)

        try:
            result = self.executor.execute(plan)
            del self._pending_plans[plan_id]
            return result
        except Exception as exc:
            del self._pending_plans[plan_id]
            raise

    approve = approve_plan

    def create_plan(self, goal: str) -> TaskPlan:
        return self.planner.create_plan(goal)

    def execute_approved(self, plan_id: str) -> dict[str, Any]:
        return self.approve_plan(plan_id)

    def get_pending_plans(self) -> dict[str, TaskPlan]:
        """Get all pending plans awaiting approval."""
        return dict(self._pending_plans)

    def reject_plan(self, plan_id: str) -> None:
        """Discard a plan that the user declined."""
        if plan_id not in self._pending_plans:
            raise ValueError(f"Plan not found: {plan_id}")
        del self._pending_plans[plan_id]


__all__ = ["AstraAgent"]
