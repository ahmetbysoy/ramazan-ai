import pytest
from ramazan.schemas.task import Task, TaskStatus, TaskPriority, TaskComplexity
from ramazan.schemas.state import ProjectState
from ramazan.schemas.review import ReviewResult, ReviewIssue
from ramazan.schemas.adr import ArchitectureDecisionRecord
from ramazan.schemas.memory import TaskMemory


def test_task_schema_instantiation():
    task = Task(
        id="TASK-001",
        title="Test Task Title",
        description="Test task description",
        type="implementation",
        priority="high",
        complexity="medium",
        status="PENDING",
        dependencies=[],
        files=["src/demo.py"],
        acceptanceCriteria=["Function works", "Tests pass"]
    )
    assert task.id == "TASK-001"
    assert task.maxRetries == 3
    assert task.retryCount == 0
    assert task.status == TaskStatus.PENDING.value


def test_project_state_progress_calculation():
    state = ProjectState(
        project="test_proj",
        version=1,
        totalTasks=4,
        completedTasks=["TASK-001", "TASK-002"]
    )
    assert state.calculate_progress() == 50.0
    state.touch()
    assert state.progress == 50.0


def test_review_result():
    res_clean = ReviewResult(status="APPROVED", severity="LOW", issues=[])
    assert res_clean.is_approved is True

    res_dirty = ReviewResult(
        status="CHANGES_REQUIRED",
        severity="HIGH",
        issues=[
            ReviewIssue(
                file="auth.py",
                line=20,
                category="security",
                description="Plaintext token storage",
                requiredFix="Use vault"
            )
        ]
    )
    assert res_dirty.is_approved is False


def test_adr_markdown():
    adr = ArchitectureDecisionRecord(
        id="ADR-001",
        title="State Pattern",
        decision="Use JSON state",
        context="Deterministic workflow",
        alternatives=["SQLite"],
        reason="Human readable",
        consequences="Simple serialization"
    )
    md = adr.to_markdown()
    assert "# ADR-001" in md
    assert "Use JSON state" in md


def test_task_memory_markdown():
    mem = TaskMemory(
        taskId="TASK-001",
        completed="Initial service built",
        filesChanged=["src/service.py"],
        importantDecisions=["Used dependency injection"],
        problems=[],
        resolution="None needed",
        tests="All 5 unit tests passed",
        futureConsiderations="Add caching"
    )
    md = mem.to_markdown()
    assert "# TASK-001" in md
    assert "src/service.py" in md
