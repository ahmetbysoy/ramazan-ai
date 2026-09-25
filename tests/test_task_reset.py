import pytest
from pathlib import Path
from ramazan.core.task_engine import TaskEngine
from ramazan.schemas.task import Task, TaskStatus


def test_task_reset_and_locking(tmp_path: Path):
    engine = TaskEngine(tmp_path)

    # 1. Add task that fails and escalates
    t1 = Task(
        id="TASK-001",
        title="Payment Gateway",
        description="Integrate Stripe",
        status=TaskStatus.ESCALATED.value,
        retryCount=3,
        lastError="Test failed: Stripe secret key required",
        files=["src/payment.py"]
    )
    engine.add_task(t1)

    # 2. Reset task after human review
    reset_t = engine.reset_task("TASK-001")
    assert reset_t.status == TaskStatus.READY.value
    assert reset_t.retryCount == 0
    assert reset_t.lastError is None

    # 3. Test unresolved tasks
    t2 = Task(
        id="TASK-002",
        title="Payment Receipts",
        description="Send receipts after payment",
        status=TaskStatus.PENDING.value,
        dependencies=["TASK-001", "TASK-999"]  # TASK-999 does not exist
    )
    engine.add_task(t2)

    unresolved = engine.unresolved_tasks(completed_task_ids=["TASK-001"])
    assert len(unresolved) == 1
    assert unresolved[0].id == "TASK-002"

    # 4. Test locked files prevention
    active_task = Task(
        id="TASK-003",
        title="Active Worker Task",
        description="Currently working",
        status=TaskStatus.IN_PROGRESS.value,
        files=["src/shared.py"]
    )
    engine.add_task(active_task)

    locked = engine.locked_files()
    assert "src/shared.py" in locked
