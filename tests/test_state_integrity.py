import pytest
from pathlib import Path
from typer.testing import CliRunner
from ramazan.core.state_manager import StateManager
from ramazan.core.task_engine import TaskEngine
from ramazan.schemas.task import Task
from ramazan.cli import app

runner = CliRunner()


def test_state_integrity_and_byte_identical_idempotency(tmp_path: Path):
    """
    Acceptance Criterion:
    state.json must always be consistent with TaskStore.
    Reloading state 3 times without changes must produce byte-identical output.
    """
    mgr = StateManager(root_dir=tmp_path)
    engine = TaskEngine(root_dir=tmp_path)

    # Add 2 tasks
    t1 = Task(id="TASK-001", title="Task One", description="Desc 1", status="COMPLETED")
    t2 = Task(id="TASK-002", title="Task Two", description="Desc 2", status="READY")
    engine.save_task(t1)
    engine.save_task(t2)

    state = mgr.recompute(engine)
    assert state.totalTasks == 2
    assert state.completedTasks == ["TASK-001"]
    assert state.progress == 50.0
    assert state.status == "IN_PROGRESS"

    # Save state and read content
    mgr.save()
    content1 = mgr.state_file.read_bytes()

    # Load 1
    mgr.load()
    content2 = mgr.state_file.read_bytes()

    # Load 2
    mgr.load()
    content3 = mgr.state_file.read_bytes()

    assert content1 == content2 == content3, "StateManager loading must be byte-identical and idempotent"


def test_task_004_and_repo_state_integrity():
    """
    Acceptance Criterion:
    Verify TASK-004 exists in repository TaskStore and state.json is fully consistent.
    ramazan status output shows totalTasks equals len(completedTasks) when complete.
    """
    root_dir = Path.cwd()
    engine = TaskEngine(root_dir)
    mgr = StateManager(root_dir)
    state = mgr.recompute(engine)

    # TASK-004 exists and is recorded properly
    assert "TASK-004" in engine.tasks, "TASK-004 must exist in TaskEngine"
    task_4 = engine.tasks["TASK-004"]
    assert task_4.status == "COMPLETED"
    assert "TASK-004" in state.completedTasks

    # All completed tasks match TaskStore
    completed_in_engine = [t.id for t in engine.tasks.values() if t.status == "COMPLETED"]
    assert sorted(state.completedTasks) == sorted(completed_in_engine)
    assert state.totalTasks == len(engine.tasks)

    # CLI status output matches
    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert f"{len(state.completedTasks)}/{state.totalTasks} tasks completed" in res.stdout
    assert "COMPLETED" in res.stdout
