"""
Deterministic State Manager for RAMAZAN AI.
Strictly controls .ramazan/state.json without arbitrary LLM drift.
"""

import json
import logging
from pathlib import Path
from typing import Optional
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

    def save(self) -> None:
        if self._state is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state.touch()
        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write(self._state.model_dump_json(indent=2))

    def start_task(self, task_id: str):
        state = self.get_state()
        state.currentTask = task_id
        state.status = "IN_PROGRESS"
        self.save()

    def complete_task(self, task_id: str):
        state = self.get_state()
        if task_id not in state.completedTasks:
            state.completedTasks.append(task_id)
        if state.currentTask == task_id:
            state.currentTask = None
        if task_id in state.failedTasks:
            state.failedTasks.remove(task_id)
        if task_id in state.blockedTasks:
            state.blockedTasks.remove(task_id)

        if len(state.completedTasks) == state.totalTasks and state.totalTasks > 0:
            state.status = "TASKS_COMPLETED"
        else:
            state.status = "IN_PROGRESS"
        self.save()

    def fail_task(self, task_id: str):
        state = self.get_state()
        if task_id not in state.failedTasks:
            state.failedTasks.append(task_id)
        if state.currentTask == task_id:
            state.currentTask = None
        state.status = "TASK_FAILED"
        self.save()

    def block_task(self, task_id: str):
        state = self.get_state()
        if task_id not in state.blockedTasks:
            state.blockedTasks.append(task_id)
        if state.currentTask == task_id:
            state.currentTask = None
        state.status = "BLOCKED"
        self.save()

    def set_total_tasks(self, total: int):
        state = self.get_state()
        state.totalTasks = total
        self.save()

    def mark_completed(self):
        state = self.get_state()
        state.status = "COMPLETED"
        state.currentTask = None
        self.save()

    def mark_blocked(self):
        state = self.get_state()
        state.status = "PROJECT_BLOCKED"
        self.save()
