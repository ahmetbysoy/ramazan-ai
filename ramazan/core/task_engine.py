"""
Task Engine and Dependency Graph Resolution for RAMAZAN AI.
Conforms to Sections 8, 9, 10, 30, 31, 32, 33 of specification.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
import networkx as nx

from ramazan.schemas.task import Task, TaskPriority, TaskStatus

logger = logging.getLogger("ramazan.task_engine")

PRIORITY_WEIGHTS = {
    TaskPriority.CRITICAL.value: 4,
    "critical": 4,
    TaskPriority.HIGH.value: 3,
    "high": 3,
    TaskPriority.MEDIUM.value: 2,
    "medium": 2,
    TaskPriority.LOW.value: 1,
    "low": 1,
}

VALID_TRANSITIONS = {
    TaskStatus.PENDING.value: [TaskStatus.READY.value, TaskStatus.BLOCKED.value],
    TaskStatus.READY.value: [TaskStatus.ASSIGNED.value, TaskStatus.IN_PROGRESS.value, TaskStatus.BLOCKED.value],
    TaskStatus.ASSIGNED.value: [TaskStatus.IN_PROGRESS.value, TaskStatus.BLOCKED.value],
    TaskStatus.IN_PROGRESS.value: [TaskStatus.IMPLEMENTED.value, TaskStatus.FAILED.value, TaskStatus.RETRYING.value],
    TaskStatus.IMPLEMENTED.value: [TaskStatus.TESTING.value, TaskStatus.FAILED.value],
    TaskStatus.TESTING.value: [TaskStatus.REVIEWING.value, TaskStatus.FAILED.value, TaskStatus.RETRYING.value],
    TaskStatus.REVIEWING.value: [TaskStatus.APPROVED.value, TaskStatus.FAILED.value, TaskStatus.RETRYING.value],
    TaskStatus.APPROVED.value: [TaskStatus.COMPLETED.value],
    TaskStatus.RETRYING.value: [TaskStatus.IN_PROGRESS.value, TaskStatus.ESCALATED.value, TaskStatus.FAILED.value],
    TaskStatus.ESCALATED.value: [TaskStatus.READY.value, TaskStatus.BLOCKED.value, TaskStatus.FAILED.value],
    TaskStatus.FAILED.value: [TaskStatus.RETRYING.value, TaskStatus.BLOCKED.value],
    TaskStatus.BLOCKED.value: [TaskStatus.READY.value, TaskStatus.PENDING.value],
    TaskStatus.COMPLETED.value: [],
}


class TaskEngine:
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.tasks_dir = self.root_dir / ".ramazan" / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: Dict[str, Task] = {}
        self.load_tasks()

    def load_tasks(self) -> Dict[str, Task]:
        self.tasks = {}
        if not self.tasks_dir.exists():
            return self.tasks

        for f in sorted(self.tasks_dir.glob("TASK-*.json")):
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
                    task = Task.model_validate(data)
                    self.tasks[task.id] = task
            except Exception as e:
                logger.error(f"Error loading {f.name}: {e}")
        return self.tasks

    def save_task(self, task: Task) -> Path:
        self.tasks[task.id] = task
        file_path = self.tasks_dir / f"{task.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(task.model_dump_json(indent=2))
        return file_path

    def add_task(self, task: Task) -> Path:
        return self.save_task(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def update_task_status(self, task_id: str, new_status: str) -> Task:
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found.")

        current = task.status
        allowed = VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed and new_status != current:
            logger.warning(
                f"Transition from {current} to {new_status} is unconventional for {task_id}. Allowing with warning."
            )

        task.status = new_status
        self.save_task(task)
        return task

    def build_dependency_graph(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        for t_id, task in self.tasks.items():
            graph.add_node(t_id)
            for dep in task.dependencies:
                graph.add_edge(dep, t_id)
        return graph

    def check_circular_dependencies(self) -> List[List[str]]:
        graph = self.build_dependency_graph()
        try:
            cycles = list(nx.simple_cycles(graph))
            return cycles
        except Exception:
            return []

    def next_task_id(self) -> str:
        nums = []
        for t_id in self.tasks:
            m = re.match(r"TASK-(\d+)", t_id)
            if m:
                nums.append(int(m.group(1)))
        next_num = max(nums) + 1 if nums else 1
        return f"TASK-{next_num:03d}"

    def locked_files(self) -> Set[str]:
        """
        Section 25 & Spec: Active tasks lock their target files to prevent concurrent collision.
        """
        active_statuses = {
            TaskStatus.ASSIGNED.value,
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.IMPLEMENTED.value,
            TaskStatus.TESTING.value,
            TaskStatus.REVIEWING.value,
            TaskStatus.RETRYING.value,
        }
        return {f for t in self.tasks.values() if t.status in active_statuses for f in t.files}

    def reset_task(self, task_id: str) -> Task:
        """
        Section 23 & Spec: Resets an ESCALATED, BLOCKED, or FAILED task back to READY
        following human-in-the-loop intervention.
        """
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task {task_id} not found.")

        task.status = TaskStatus.READY.value
        task.retryCount = 0
        task.lastError = None
        task.testStatus = "NOT_RUN"
        task.reviewStatus = "NOT_REVIEWED"
        self.save_task(task)
        logger.info(f"Task {task_id} has been reset to READY after human review.")
        return task

    def unresolved_tasks(self, completed_task_ids: List[str]) -> List[Task]:
        """
        Section 49 & Spec: Tasks that can never become READY due to missing or blocked dependencies.
        """
        completed_set = set(completed_task_ids)
        return [
            t for t in self.tasks.values()
            if t.status in [TaskStatus.PENDING.value, TaskStatus.BLOCKED.value, TaskStatus.ESCALATED.value]
            and any(d not in completed_set for d in t.dependencies)
        ]

    def get_ready_tasks(self, completed_task_ids: List[str]) -> List[Task]:
        """
        Returns all tasks whose dependencies are fully met and that are PENDING or READY.
        Section 10: PENDING -> READY: Yalnızca dependency'leri tamamlandıysa.
        """
        ready_tasks = []
        completed_set = set(completed_task_ids)
        locked = self.locked_files()

        for task_id, task in self.tasks.items():
            if task.status in [TaskStatus.COMPLETED.value, TaskStatus.BLOCKED.value, TaskStatus.ESCALATED.value]:
                continue

            # Check if all dependencies are in completed_set
            deps_satisfied = all(dep in completed_set for dep in task.dependencies)

            if deps_satisfied and task.status in [TaskStatus.PENDING.value, TaskStatus.READY.value, TaskStatus.RETRYING.value]:
                # Skip task if its files intersect with currently locked files of other active tasks
                if task.status in [TaskStatus.PENDING.value, TaskStatus.READY.value] and set(task.files) & locked:
                    continue

                if task.status == TaskStatus.PENDING.value:
                    task.status = TaskStatus.READY.value
                    self.save_task(task)
                ready_tasks.append(task)

        # Sort by priority (CRITICAL > HIGH > MEDIUM > LOW) then by ID
        ready_tasks.sort(
            key=lambda t: (
                PRIORITY_WEIGHTS.get(t.priority.lower(), 2),
                -int(t.id.split("-")[-1]) if t.id.replace("TASK-", "").isdigit() else 0
            ),
            reverse=True
        )
        return ready_tasks

    def select_next_ready_task(self, completed_task_ids: List[str]) -> Optional[Task]:
        ready = self.get_ready_tasks(completed_task_ids)
        if ready:
            return ready[0]
        return None

    def has_pending_tasks(self, completed_task_ids: List[str]) -> bool:
        completed_set = set(completed_task_ids)
        return any(t.id not in completed_set and t.status != TaskStatus.COMPLETED.value for t in self.tasks.values())
