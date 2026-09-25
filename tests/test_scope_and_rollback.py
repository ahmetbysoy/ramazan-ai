import pytest
from pathlib import Path
from ramazan.schemas.task import Task
from ramazan.agents.worker_agent import WorkerAgent, ScopeViolationError, is_test_path
from ramazan.config import ModelConfig
from ramazan.tools.fs import FileSystemTools, SnapshotManager


def test_is_test_path():
    assert is_test_path("tests/test_foo.py") is True
    assert is_test_path("test/sub/test_bar.py") is True
    assert is_test_path("src/module_test.py") is True
    assert is_test_path("src/components/button.spec.ts") is True
    assert is_test_path("src/components/button.test.tsx") is True
    assert is_test_path("src/core/app.py") is False
    assert is_test_path("cops_robbers_game.html") is False


def test_scope_violation_check(tmp_path: Path):
    worker = WorkerAgent(model_config=ModelConfig(), root_dir=tmp_path)
    task = Task(
        id="TASK-010",
        title="Test Task",
        description="Test Scope",
        files=["src/allowed.py"]
    )

    # Allowed: task files and test files
    assert worker.check_scope_violation(task, ["src/allowed.py", "tests/test_allowed.py"]) is None

    # Violation: file outside task scope
    violation = worker.check_scope_violation(task, ["src/allowed.py", "src/unauthorized.py"])
    assert violation is not None
    assert "Files outside task scope" in violation

    # Violation: system-owned path
    sys_violation = worker.check_scope_violation(task, [".ramazan/config.json"])
    assert sys_violation is not None
    assert "system-owned" in sys_violation


def test_snapshot_and_restore(tmp_path: Path):
    fs = FileSystemTools(tmp_path)

    # 1. Create initial file
    existing_file = "src/original.py"
    fs.write_file(existing_file, "print('initial')\n")

    new_file = "src/created_by_worker.py"

    # 2. Take snapshot before worker touches anything
    snapshot = fs.snapshots.create_snapshot([existing_file, new_file])
    assert snapshot[existing_file] == "print('initial')\n"
    assert snapshot[new_file] is None

    # 3. Simulate worker modifying existing file and creating new file
    fs.write_file(existing_file, "print('broken corrupted code')\n")
    fs.write_file(new_file, "print('temporary bad file')\n")

    assert "broken corrupted code" in fs.read_file(existing_file)
    assert fs.file_exists(new_file) is True

    # 4. Trigger atomic rollback on circuit breaker / escalation
    fs.snapshots.restore_snapshot(snapshot)

    # Verify original file restored
    assert fs.read_file(existing_file) == "print('initial')\n"
    # Verify new temporary file was cleanly deleted
    assert fs.file_exists(new_file) is False
