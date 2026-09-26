"""
Unit tests for Mock Fallback Removal and Error Semantics (FAZ 2.2).
"""

import sys
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest

# Ensure litellm is mockable in environments where it is not installed
if "litellm" not in sys.modules:
    sys.modules["litellm"] = MagicMock()

from ramazan.llm.client import LLMClient
from ramazan.llm.errors import ModelCallError, ConfigurationError, is_retriable_error
from ramazan.schemas.task import Task
from ramazan.config import RamazanConfig
from ramazan.core.orchestrator import Orchestrator


def test_is_retriable_error_classification():
    assert is_retriable_error(Exception("429 Too Many Requests: rate limit exceeded")) is True
    assert is_retriable_error(Exception("503 Service Unavailable: server overloaded")) is True
    assert is_retriable_error(Exception("ResourceExhausted: quota depleted temporarily")) is True

    assert is_retriable_error(Exception("401 Unauthorized: Invalid API key")) is False
    assert is_retriable_error(Exception("400 Bad Request: model does not support schema")) is False
    assert is_retriable_error(Exception("404 Not Found: Model claude-fake does not exist")) is False


def test_llm_client_raises_model_call_error_without_mock():
    # LLMClient with use_mock=False must raise ModelCallError when litellm fails
    client = LLMClient(use_mock=False)

    with patch("litellm.completion", side_effect=RuntimeError("Connection refused by provider")):
        with pytest.raises(ModelCallError) as exc_info:
            client.generate(model="claude-3-7-sonnet-20250219", prompt="hello")

        assert "claude-3-7-sonnet-20250219" in str(exc_info.value)
        assert isinstance(exc_info.value, ModelCallError)


def test_orchestrator_blocks_task_on_non_retriable_model_call_error(tmp_path: Path):
    ramazan_dir = tmp_path / ".ramazan"
    ramazan_dir.mkdir(parents=True, exist_ok=True)
    (ramazan_dir / "architecture.md").write_text("# Architecture\nStandard rules", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Project Docs\nValid description.", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")

    config = RamazanConfig()
    config.system.autoGitCommit = False
    config.system.maxRetries = 1

    orch = Orchestrator(root_dir=tmp_path, config=config, use_mock_llm=False)

    task = Task(
        id="TASK-999",
        title="Failing Model Task",
        description="Fails due to auth error",
        type="implementation",
        priority="high",
        complexity="low",
        status="PENDING",
        dependencies=[],
        files=["src/fail.py"],
        acceptanceCriteria=["Should fail cleanly"]
    )
    orch.task_engine.add_task(task)
    orch.state_manager.set_total_tasks(1)

    # Patch litellm.completion with 401 unauthorized (non-retriable)
    with patch("litellm.completion", side_effect=RuntimeError("401 Unauthorized: Invalid API key provided")):
        result = orch.run_all(max_iterations=1)
        assert result.success is False

    # Verify task is BLOCKED or ESCALATED and not marked COMPLETED
    t = orch.task_engine.get_task("TASK-999")
    assert t.status in ["BLOCKED", "ESCALATED"]
    assert "TASK-999" in orch.state_manager.load().blockedTasks
