"""
Unit tests for Reviewer git diff integration (FAZ 2.4).
"""

from pathlib import Path
import subprocess
from ramazan.tools.git_manager import GitManager
from ramazan.core.context_builder import ContextBuilder
from ramazan.agents.reviewer_agent import ReviewerAgent
from ramazan.config import ModelConfig
from ramazan.schemas.task import Task
from ramazan.llm.client import LLMClient, LLMResponse


def test_git_manager_diff_for_task(tmp_path: Path):
    gm = GitManager(tmp_path)
    gm.init_if_needed()

    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), check=True, capture_output=True)

    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    f1 = tmp_path / "src" / "app.py"
    f1.write_text("print('v1')\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(tmp_path), check=True, capture_output=True)

    # Modify existing file and create new untracked file
    f1.write_text("print('v2')\n", encoding="utf-8")
    f2 = tmp_path / "src" / "new_module.py"
    f2.write_text("def new_func(): pass\n", encoding="utf-8")

    diff = gm.diff_for_task(files=["src/app.py", "src/new_module.py"])
    assert "print('v2')" in diff or "v2" in diff
    assert "new_func" in diff


def test_reviewer_receives_and_records_git_diff(tmp_path: Path):
    cb = ContextBuilder(tmp_path)
    task = Task(
        id="TASK-099",
        title="Sample Review Task",
        description="Check diff minimality",
        type="implementation",
        status="TESTING",
        files=["src/sample.py"],
        acceptanceCriteria=["Clean implementation"]
    )

    test_diff = "--- a/src/sample.py\n+++ b/src/sample.py\n@@ -1 +1 @@\n-old\n+new"
    prompt = cb.build_reviewer_prompt(
        task=task,
        changes_summary="Updated one line",
        test_output="All tests passed",
        git_diff=test_diff
    )
    assert "GIT DIFF (WHAT CHANGED):" in prompt
    assert test_diff in prompt
    assert "Diff Minimality:" in prompt

    class MockReviewerLLMClient(LLMClient):
        def generate(self, model, prompt, system_prompt=None, temperature=0.1):
            return LLMResponse(
                content='''{
                    "status": "APPROVED",
                    "severity": "LOW",
                    "summary": "Diff is clean and minimal.",
                    "issues": []
                }''',
                model=model
            )

    reviewer = ReviewerAgent(
        model_config=ModelConfig(model="mock-reviewer", provider="anthropic"),
        root_dir=tmp_path,
        llm_client=MockReviewerLLMClient()
    )

    result = reviewer.review_task(task, prompt, git_diff=test_diff)
    assert result.is_approved is True

    review_file = tmp_path / ".ramazan" / "reviews" / "TASK-099.md"
    assert review_file.exists()
    content = review_file.read_text(encoding="utf-8")
    assert "### Git Diff Audited" in content
    assert test_diff in content
