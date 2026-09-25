import pytest
from pathlib import Path
from ramazan.core.state_manager import StateManager


def test_state_manager_lifecycle(tmp_path: Path):
    mgr = StateManager(root_dir=tmp_path)
    state = mgr.load()
    assert state.status == "INITIALIZED"
    assert state.completedTasks == []

    mgr.set_total_tasks(3)
    mgr.start_task("TASK-001")
    state = mgr.get_state()
    assert state.currentTask == "TASK-001"
    assert state.status == "IN_PROGRESS"

    mgr.complete_task("TASK-001")
    state = mgr.get_state()
    assert state.currentTask is None
    assert "TASK-001" in state.completedTasks
    assert state.progress == pytest.approx(33.3, 0.1)

    # Test failure tracking
    mgr.start_task("TASK-002")
    mgr.fail_task("TASK-002")
    state = mgr.get_state()
    assert "TASK-002" in state.failedTasks

    # Test completing failed task removes it from failed
    mgr.complete_task("TASK-002")
    state = mgr.get_state()
    assert "TASK-002" not in state.failedTasks
    assert "TASK-002" in state.completedTasks
