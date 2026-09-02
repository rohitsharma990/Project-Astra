from dataclasses import dataclass, field
from typing import Any, List, Optional
from uuid import uuid4
import time


@dataclass
class TaskStep:
    """Represents a single step in a task plan."""
    step_id: int
    tool: str
    arguments: dict[str, Any]
    reason: str
    status: str = "pending"
    result: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class TaskPlan:
    """Represents a complete task plan that can be executed or approved."""
    plan_id: str
    goal: str
    steps: List[TaskStep]
    requires_approval: bool = False
    safe_only: bool = True
    status: str = "created"  # created, pending_approval, approved, executing, completed, failed
    approval_timestamp: Optional[float] = None
    execution_timestamp: Optional[float] = None
    
    def has_approval_required_tools(self) -> bool:
        """Check if plan contains any approval-required tools."""
        return not self.safe_only


@dataclass
class ApprovalRequest:
    """Represents a request for user approval of a task plan."""
    plan_id: str
    goal: str
    steps: List[TaskStep]
    reason: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Task:
    title: str
    priority: str = "medium"
    status: str = "pending"
    task_id: str = field(default_factory=lambda: str(uuid4()))


class TaskAgent:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def add_task(self, title: str, priority: str = "medium") -> Task:
        cleaned_title = (title or "").strip()
        if not cleaned_title:
            raise ValueError("Task title cannot be empty.")

        normalized_priority = (priority or "medium").strip().lower()
        if normalized_priority not in {"low", "medium", "high"}:
            raise ValueError("Priority must be one of: low, medium, high.")

        task = Task(title=cleaned_title, priority=normalized_priority, status="pending")
        self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> Task:
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        return task

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        tasks = list(self._tasks.values())
        if status is None:
            return tasks

        normalized_status = status.strip().lower()
        return [task for task in tasks if task.status == normalized_status]

    def complete_task(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        task.status = "completed"
        return task

    def delete_task(self, task_id: str) -> None:
        if task_id not in self._tasks:
            raise ValueError(f"Task not found: {task_id}")
        del self._tasks[task_id]


__all__ = ["Task", "TaskAgent", "TaskStep", "TaskPlan", "ApprovalRequest"]
