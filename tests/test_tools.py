import pytest
from pathlib import Path
from ramazan.tools.fs import FileSystemTools, FileLockManager, FileLockException
from ramazan.tools.test_runner import TestEngine
from ramazan.tools.git_manager import GitManager


def test_fs_tools_crud(tmp_path: Path):
    fs = FileSystemTools(tmp_path)
    test_file = "src/example.txt"

    assert fs.write_file(test_file, "initial text") is True
    assert fs.file_exists(test_file) is True
    assert fs.read_file(test_file) == "initial text"

    assert fs.edit_file(test_file, "initial", "updated") is True
    assert fs.read_file(test_file) == "updated text"


def test_file_lock_manager():
    lock_mgr = FileLockManager()
    files = ["src/auth.py", "src/user.py"]

    # Task 1 acquires locks
    lock_mgr.acquire_locks("TASK-001", files)
    assert lock_mgr.is_locked("src/auth.py") == "TASK-001"

    # Task 2 trying to acquire same file should raise exception
    with pytest.raises(FileLockException):
        lock_mgr.acquire_locks("TASK-002", ["src/auth.py"])

    # Task 1 releases locks
    lock_mgr.release_locks("TASK-001")
    assert lock_mgr.is_locked("src/auth.py") is None

    # Now Task 2 can acquire
    assert lock_mgr.acquire_locks("TASK-002", ["src/auth.py"]) is True
    lock_mgr.release_locks("TASK-002")


def test_test_engine_run(tmp_path: Path):
    engine = TestEngine(root_dir=tmp_path)
    res = engine.run_tests(command="python3 -c 'print(\"Test passed\"); exit(0)'")
    assert res.passed is True
    assert res.exitCode == 0
    assert "Test passed" in res.stdout
