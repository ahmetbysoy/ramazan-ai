"""
Deterministic Plan Validation and DAG Enforcement (TASK-105).
Validates planner LLM outputs against Pydantic schemas, strict DAG constraints,
and objective, measurable acceptance criteria (rejecting vague hand-waving).
"""

import json
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
import networkx as nx
from pydantic import ValidationError

from ramazan.schemas.task import Task, TaskPriority, TaskComplexity, TaskType

logger = logging.getLogger("ramazan.planner")


class PlanRejectedError(ValueError):
    """Raised when an LLM planning output fails schema, DAG, or criteria quality gates."""
    pass


# Vague / unmeasurable slogans that are strictly forbidden as acceptance criteria
UNMEASURABLE_PATTERNS = [
    r"^(çalışıyor|calisiyor|works|it works|working)$",
    r"^(iyi görünüyor|looks good|seems fine)$",
    r"^(test et|test it|testing)$",
    r"^(yapıldı|yapildi|done|finished|completed)$",
    r"^(ok|tamam|fine|good)$",
]


class PlanValidator:
    """
    Validates structured plan outputs.
    Guarantees:
    1. Schema conformance (Pydantic validation).
    2. Zero circular dependencies (Strict DAG resolution via NetworkX).
    3. Non-trivial, measurable acceptance criteria.
    4. Task dependencies point to valid declared task IDs.
    """

    @classmethod
    def validate_raw_json(cls, raw_content: str) -> List[Task]:
        """
        Parses and validates raw LLM output.
        Raises PlanRejectedError if JSON is corrupt or fails quality gates.
        """
        clean = raw_content.strip()
        if "```json" in clean:
            match = re.search(r"```json\s*(.*?)\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1).strip()
        elif "```" in clean:
            match = re.search(r"```\s*(.*?)\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1).strip()

        try:
            parsed = json.loads(clean)
        except Exception as e:
            raise PlanRejectedError(f"Plan rejected: Malformed or unparseable JSON: {e}")

        if isinstance(parsed, dict):
            if "tasks" in parsed and isinstance(parsed["tasks"], list):
                raw_tasks = parsed["tasks"]
            elif "id" in parsed:
                raw_tasks = [parsed]
            else:
                raise PlanRejectedError(f"Plan rejected: Expected 'tasks' list in JSON, found keys: {list(parsed.keys())}")
        elif isinstance(parsed, list):
            raw_tasks = parsed
        else:
            raise PlanRejectedError(f"Plan rejected: Expected JSON list or dict with 'tasks', got {type(parsed).__name__}")

        if not raw_tasks:
            raise PlanRejectedError("Plan rejected: Task list is empty")

        tasks: List[Task] = []
        for idx, item in enumerate(raw_tasks):
            if not isinstance(item, dict):
                raise PlanRejectedError(f"Plan rejected: Task at index {idx} is not an object")
            try:
                # Ensure operational defaults
                item.setdefault("status", "PENDING")
                item.setdefault("retryCount", 0)
                item.setdefault("maxRetries", 3)
                item.setdefault("reviewStatus", "NOT_REVIEWED")
                item.setdefault("testStatus", "NOT_RUN")
                task = Task.model_validate(item)
                tasks.append(task)
            except ValidationError as ve:
                raise PlanRejectedError(f"Plan rejected: Schema validation failed for task {item.get('id', idx)}: {ve}")

        cls.validate_plan(tasks)
        return tasks

    @classmethod
    def validate_plan(cls, tasks: List[Task]) -> None:
        """
        Validates an existing list of Task models for DAG integrity and criteria measurability.
        """
        if not tasks:
            raise PlanRejectedError("Plan rejected: No tasks provided.")

        task_ids: Set[str] = {t.id for t in tasks}

        # 1. Dependency Existence Check
        for task in tasks:
            for dep in task.dependencies:
                if dep not in task_ids:
                    raise PlanRejectedError(
                        f"Plan rejected: Task {task.id} depends on undeclared task '{dep}'."
                    )

        # 2. DAG & Circular Dependency Check
        graph = nx.DiGraph()
        for t in tasks:
            graph.add_node(t.id)
            for dep in t.dependencies:
                graph.add_edge(dep, t.id)

        if not nx.is_directed_acyclic_graph(graph):
            cycles = list(nx.simple_cycles(graph))
            raise PlanRejectedError(
                f"Plan rejected: Circular dependency detected in task graph: {cycles}"
            )

        # 3. Measurable Acceptance Criteria Quality Gate
        for task in tasks:
            if not task.acceptanceCriteria:
                raise PlanRejectedError(
                    f"Plan rejected: Task {task.id} must have at least one measurable acceptance criterion."
                )

            for criterion in task.acceptanceCriteria:
                crit_clean = criterion.strip().lower()
                for pat in UNMEASURABLE_PATTERNS:
                    if re.match(pat, crit_clean):
                        raise PlanRejectedError(
                            f"Plan rejected: Task {task.id} contains unmeasurable vague acceptance criterion: '{criterion}'. "
                            f"Criteria must state objective, verifiable assertions (e.g. 'HTTP 200 with JSON payload containing entity ID')."
                        )
                if len(crit_clean) < 4:
                    raise PlanRejectedError(
                        f"Plan rejected: Task {task.id} criterion '{criterion}' is too brief to be verifiable."
                    )
