"""
Reviewer Agent for RAMAZAN AI.
Conforms to Sections 4.4, 18, 36 of specification.
Performs independent, non-lenient code critique and produces structured JSON reviews.
"""

import json
import logging
import re
from pathlib import Path
from typing import Optional
from ramazan.agents.base import BaseAgent
from ramazan.config import ModelConfig
from ramazan.llm.client import LLMClient
from ramazan.llm.cost_tracker import CostTracker
from ramazan.schemas.review import ReviewIssue, ReviewResult
from ramazan.schemas.task import Task
from ramazan.tools.fs import FileSystemTools

logger = logging.getLogger("ramazan.reviewer_agent")


class ReviewerAgent(BaseAgent):
    def __init__(
        self,
        model_config: ModelConfig,
        root_dir: Optional[Path] = None,
        llm_client: Optional[LLMClient] = None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        super().__init__(
            name="Reviewer",
            role="CODE REVIEWER & AUDITOR",
            model_config=model_config,
            llm_client=llm_client,
            cost_tracker=cost_tracker,
        )
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.fs = FileSystemTools(self.root_dir)

    def review_task(
        self,
        task: Task,
        context_prompt: str,
    ) -> ReviewResult:
        """
        Executes strict review and saves markdown review record to .ramazan/reviews/TASK-XXX.md.
        """
        system_prompt = (
            "You are an elite, uncompromising software auditor and security reviewer. "
            "You never say 'Looks good to me' without inspecting every line. "
            "You identify edge case defects, potential race conditions, security flaws, and architectural drift. "
            "You MUST respond ONLY with valid JSON conforming to the ReviewResult schema."
        )

        resp = self.call_llm(prompt=context_prompt, system_prompt=system_prompt, task_id=task.id)
        result = self._parse_review_result(resp.content)

        # Save review to .ramazan/reviews/
        self._save_review_record(task.id, result)
        return result

    def _parse_review_result(self, content: str) -> ReviewResult:
        clean = content.strip()
        if "```json" in clean:
            match = re.search(r"```json\s*(.*?)\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1).strip()
        elif "```" in clean:
            match = re.search(r"```\s*(.*?)\s*```", clean, re.DOTALL)
            if match:
                clean = match.group(1).strip()

        try:
            data = json.loads(clean)
            return ReviewResult.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to parse review JSON ({e}). Output was: {content[:200]}")
            return ReviewResult(
                status="CHANGES_REQUIRED",
                severity="HIGH",
                summary="Review parsing failed. Manual verification or retry required.",
                issues=[
                    ReviewIssue(
                        file="output",
                        category="correctness",
                        description="Reviewer could not parse structured validation output.",
                        requiredFix="Ensure valid JSON response."
                    )
                ]
            )

    def _save_review_record(self, task_id: str, result: ReviewResult):
        review_dir = self.root_dir / ".ramazan" / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        review_file = review_dir / f"{task_id}.md"

        issues_md = ""
        for i in result.issues:
            line_info = f" (line {i.line})" if i.line else ""
            issues_md += f"- **[{i.category.upper()}]** `{i.file}`{line_info}: {i.description}\n  - *Required Fix:* {i.requiredFix}\n"

        if not issues_md:
            issues_md = "_No issues found. Code meets acceptance criteria._\n"

        content = f"""# Review for {task_id}

**Status:** `{result.status}`
**Severity:** `{result.severity}`

## Summary
{result.summary}

## Issues Identified
{issues_md}
"""
        with open(review_file, "w", encoding="utf-8") as f:
            f.write(content)
