import pytest
from ramazan.core.planner import PlanValidator, PlanRejectedError
from ramazan.schemas.task import Task


def test_planner_rejects_malformed_json():
    """Acceptance Criterion: Corrupt / malformed JSON must be strictly rejected."""
    malformed_json = '{"tasks": [{"id": "TASK-001", "title": "Incomplete json'
    with pytest.raises(PlanRejectedError) as exc_info:
        PlanValidator.validate_raw_json(malformed_json)
    assert "Malformed or unparseable JSON" in str(exc_info.value)


def test_planner_rejects_missing_schema_fields():
    """Acceptance Criterion: Missing required schema fields must be rejected."""
    invalid_schema = """[
        {
            "id": "TASK-001",
            "title": "Missing description and type"
        }
    ]"""
    with pytest.raises(PlanRejectedError) as exc_info:
        PlanValidator.validate_raw_json(invalid_schema)
    assert "Schema validation failed" in str(exc_info.value)


def test_planner_rejects_circular_dependencies():
    """
    Acceptance Criterion: Circular DAG dependencies must be caught by NetworkX
    and strictly rejected.
    """
    circular_plan = [
        Task(
            id="TASK-001",
            title="Task 1",
            description="Desc 1",
            dependencies=["TASK-002"],
            files=["src/a.py"],
            acceptanceCriteria=["HTTP 200 response returned."]
        ),
        Task(
            id="TASK-002",
            title="Task 2",
            description="Desc 2",
            dependencies=["TASK-001"],
            files=["src/b.py"],
            acceptanceCriteria=["Service passes all integration assertions."]
        )
    ]
    with pytest.raises(PlanRejectedError) as exc_info:
        PlanValidator.validate_plan(circular_plan)
    assert "Circular dependency detected" in str(exc_info.value)


def test_planner_rejects_undeclared_dependencies():
    """Acceptance Criterion: Depending on a ghost task must be rejected."""
    plan = [
        Task(
            id="TASK-001",
            title="Task 1",
            description="Desc 1",
            dependencies=["TASK-999"],
            files=["src/a.py"],
            acceptanceCriteria=["HTTP 200 response returned."]
        )
    ]
    with pytest.raises(PlanRejectedError) as exc_info:
        PlanValidator.validate_plan(plan)
    assert "depends on undeclared task 'TASK-999'" in str(exc_info.value)


def test_planner_rejects_unmeasurable_acceptance_criteria():
    """
    Acceptance Criterion: Vague, hand-waving criteria like 'çalışıyor', 'iyi görünüyor',
    'test et', 'done' must be rejected.
    """
    vague_phrases = ["çalışıyor", "iyi görünüyor", "test et", "done", "works", "ok"]

    for phrase in vague_phrases:
        plan = [
            Task(
                id="TASK-001",
                title="Task 1",
                description="Desc 1",
                dependencies=[],
                files=["src/a.py"],
                acceptanceCriteria=[phrase]
            )
        ]
        with pytest.raises(PlanRejectedError) as exc_info:
            PlanValidator.validate_plan(plan)
        assert "unmeasurable vague acceptance criterion" in str(exc_info.value) or "too brief" in str(exc_info.value)


def test_planner_accepts_valid_dag_and_measurable_criteria():
    """Acceptance Criterion: Clean, structured DAG with measurable criteria succeeds."""
    valid_json = """[
        {
            "id": "TASK-001",
            "title": "Domain Layer",
            "description": "Implement domain models and validations",
            "type": "implementation",
            "priority": "high",
            "complexity": "low",
            "dependencies": [],
            "files": ["src/domain/models.py", "tests/test_domain_models.py"],
            "acceptanceCriteria": [
                "EntityModel schema validation rejects invalid email format",
                "Unit tests pass with 100% assertions"
            ]
        },
        {
            "id": "TASK-002",
            "title": "Service Layer",
            "description": "Implement service repository operations",
            "type": "implementation",
            "priority": "high",
            "complexity": "medium",
            "dependencies": ["TASK-001"],
            "files": ["src/domain/service.py", "tests/test_domain_service.py"],
            "acceptanceCriteria": [
                "Service retrieves entity by ID from in-memory repository",
                "Integration tests pass without errors"
            ]
        }
    ]"""
    tasks = PlanValidator.validate_raw_json(valid_json)
    assert len(tasks) == 2
    assert tasks[0].id == "TASK-001"
    assert tasks[1].dependencies == ["TASK-001"]
