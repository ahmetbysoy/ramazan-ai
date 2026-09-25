"""
Deterministic State Manager for RAMAZAN AI.
Strictly controls .ramazan/state.json without arbitrary drift.
Single source of truth is TaskEngine / TaskStore (Sections 46 & 49).
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional
from ramazan.schemas.state import ProjectState

logger = logging.getLogger("ramazan.state")


class StateManager:
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.state_file = self.root_dir / ".ramazan" / "state.json"
        self._state: Optional[ProjectState] = None

    def load(self) -> ProjectState:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._state = ProjectState.model_validate(data)
                    return self._state
            except Exception as e:
                logger.error(f"Error loading state.json: {e}")
        # Default fresh state
        self._state = ProjectState(project=self.root_dir.name)
        self.save()
        return self._state

    def get_state(self) -> ProjectState:
        if self._state is None:
            return self.load()
        return self._state

    def save(self, touch: bool = False) -> None:
        if self._state is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        if touch:
            self._state.touch()
        else:
            self._state.progress = self._state.calculate_progress()
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write(self._state.model_dump_json(indent=2) + "\n")

    def recompute(self, task_engine: Optional[Any] = None) -> ProjectState:
        """
        Recompute state deterministically from the underlying TaskStore.
        TaskEngine is the single source of truth for task existence and statuses.
        """
        if task_engine is None:
            from ramazan.core.task_engine import TaskEngine
            task_engine = TaskEngine(self.root_dir)

        tasks = getattr(task_engine, "tasks", {})
        state = self.get_state()

        if tasks:
            completed = sorted([t.id for t in tasks.values() if getattr(t, "status", None) == "COMPLETED"])
            failed = sorted([t.id for t in tasks.values() if getattr(t, "status", None) == "FAILED"])
            blocked = sorted([t.id for t in tasks.values() if getattr(t, "status", None) in ["BLOCKED", "ESCALATED"]])

            state.totalTasks = len(tasks)
            state.completedTasks = completed
            state.failedTasks = failed
            state.blockedTasks = blocked

            if state.totalTasks > 0:
                state.progress = round((len(completed) / state.totalTasks) * 100.0, 1)
            else:
                state.progress = 0.0

            if len(blocked) > 0:
                state.status = "PROJECT_BLOCKED"
            elif len(failed) > 0:
                state.status = "TASK_FAILED"
            elif state.totalTasks > 0 and len(completed) == state.totalTasks and len(failed) == 0:
                state.status = "COMPLETED"
            elif len(completed) > 0 or any(getattr(t, "status", None) in ["IN_PROGRESS", "ASSIGNED", "IMPLEMENTED", "TESTING", "REVIEWING", "APPROVED"] for t in tasks.values()):
                state.status = "IN_PROGRESS"
            else:
                state.status = "INITIALIZED"
        else:
            state.progress = state.calculate_progress()
            if len(state.blockedTasks) > 0:
                state.status = "PROJECT_BLOCKED"
            elif len(state.failedTasks) > 0:
                state.status = "TASK_FAILED"
            elif state.totalTasks > 0 and len(state.completedTasks) == state.totalTasks:
                state.status = "COMPLETED"

        self._state = state
        self.save()
        return self._state

    def start_task(self, task_id: str):
        state = self.get_state()
        state.currentTask = task_id
        state.status = "IN_PROGRESS"
        self.save(touch=True)

    def complete_task(self, task_id: str):
        state = self.get_state()
        if task_id not in state.completedTasks:
            state.completedTasks.append(task_id)
            state.completedTasks = sorted(list(set(state.completedTasks)))
        if state.currentTask == task_id:
            state.currentTask = None
        if task_id in state.failedTasks:
            state.failedTasks.remove(task_id)
        if task_id in state.blockedTasks:
            state.blockedTasks.remove(task_id)

        tasks_dir = self.root_dir / ".ramazan" / "tasks"
        if tasks_dir.exists() and any(tasks_dir.glob("TASK-*.json")):
            self.recompute()
        else:
            if len(state.completedTasks) == state.totalTasks and state.totalTasks > 0:
                state.status = "COMPLETED"
            else:
                state.status = "IN_PROGRESS"
            self.save(touch=True)

    def fail_task(self, task_id: str):
        state = self.get_state()
        if task_id not in state.failedTasks:
            state.failedTasks.append(task_id)
            state.failedTasks = sorted(list(set(state.failedTasks)))
        if state.currentTask == task_id:
            state.currentTask = None
        state.status = "TASK_FAILED"
        self.save(touch=True)

    def block_task(self, task_id: str):
        state = self.get_state()
        if task_id not in state.blockedTasks:
            state.blockedTasks.append(task_id)
            state.blockedTasks = sorted(list(set(state.blockedTasks)))
        if state.currentTask == task_id:
            state.currentTask = None
        state.status = "PROJECT_BLOCKED"
        self.save(touch=True)

    def set_total_tasks(self, total: int):
        state = self.get_state()
        state.totalTasks = total
        state.progress = state.calculate_progress()
        self.save(touch=True)

    def mark_completed(self):
        state = self.get_state()
        state.status = "COMPLETED"
        state.currentTask = None
        self.save(touch=True)

    def mark_blocked(self):
        state = self.get_state()
        state.status = "PROJECT_BLOCKED"
        self.save(touch=True)
