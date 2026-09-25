import pytest
from pathlib import Path
from ramazan.config import RamazanConfig
from ramazan.core.orchestrator import Orchestrator
from ramazan.schemas.task import Task


def test_orchestrator_pipeline_execution(tmp_path: Path):
    # Setup project directory
    ramazan_dir = tmp_path / ".ramazan"
    ramazan_dir.mkdir(parents=True, exist_ok=True)
    (ramazan_dir / "architecture.md").write_text("# Architecture\nStandard rules", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Math App\nTest project documentation with sufficient description.", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")

    config = RamazanConfig()
    config.system.autoGitCommit = False
    config.tools.testCommand = "python3 -c 'exit(0)'"  # Dummy passing test

    orch = Orchestrator(root_dir=tmp_path, config=config, use_mock_llm=True)

    task = Task(
        id="TASK-001",
        title="Setup Math Service",
        description="Implement simple math operations",
        type="implementation",
        priority="high",
        complexity="low",
        status="PENDING",
        dependencies=[],
        files=["src/math.py"],
        acceptanceCriteria=["Math service functions exist", "Tests pass"]
    )
    orch.task_engine.add_task(task)
    orch.state_manager.set_total_tasks(1)

    result = orch.run_all(max_iterations=5)
    assert result.success is True
    assert "TASK-001" in result.state.completedTasks
    assert (ramazan_dir / "memory" / "TASK-001.md").exists()
    assert (ramazan_dir / "reviews" / "TASK-001.md").exists()
    assert (ramazan_dir / "FINAL_AUDIT.md").exists()
