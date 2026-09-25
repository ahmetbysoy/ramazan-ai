import pytest
from pathlib import Path
from ramazan.core.task_engine import TaskEngine
from ramazan.schemas.task import Task, TaskStatus


def test_task_engine_dependencies_and_priority(tmp_path: Path):
    engine = TaskEngine(root_dir=tmp_path)

    t1 = Task(
        id="TASK-001",
        title="Setup DB",
        description="Configure DB connection",
        priority="high",
        complexity="medium",
        dependencies=[],
        files=["db.py"]
    )
    t2 = Task(
        id="TASK-002",
        title="User Migration",
        description="Migrate user table",
        priority="critical",
        complexity="high",
        dependencies=["TASK-001"],
        files=["migrations/user.py"]
    )
    t3 = Task(
        id="TASK-003",
        title="Documentation",
        description="Write docs",
        priority="low",
        complexity="low",
        dependencies=[],
        files=["docs.md"]
    )

    engine.add_task(t1)
    engine.add_task(t2)
    engine.add_task(t3)

    # Initially, TASK-001 and TASK-003 have no dependencies.
    # TASK-001 has high priority, TASK-003 has low priority.
    # TASK-002 depends on TASK-001, so it cannot be selected yet.
    ready = engine.get_ready_tasks(completed_task_ids=[])
    ready_ids = [t.id for t in ready]
    assert "TASK-001" in ready_ids
    assert "TASK-003" in ready_ids
    assert "TASK-002" not in ready_ids

    # Next ready task should be TASK-001 due to higher priority
    next_t = engine.select_next_ready_task(completed_task_ids=[])
    assert next_t.id == "TASK-001"

    # Once TASK-001 is completed, TASK-002 should become ready and have higher priority than TASK-003
    next_after = engine.select_next_ready_task(completed_task_ids=["TASK-001"])
    assert next_after.id == "TASK-002"


def test_task_engine_circular_detection(tmp_path: Path):
    engine = TaskEngine(root_dir=tmp_path)
    t1 = Task(id="TASK-001", title="T1", description="D1", dependencies=["TASK-002"])
    t2 = Task(id="TASK-002", title="T2", description="D2", dependencies=["TASK-001"])
    engine.add_task(t1)
    engine.add_task(t2)

    cycles = engine.check_circular_dependencies()
    assert len(cycles) > 0
