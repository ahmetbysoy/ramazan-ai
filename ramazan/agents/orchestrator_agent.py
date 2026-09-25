"""
Orchestrator Agent for RAMAZAN AI.
Chief Software Engineering Orchestrator role.
Conforms to Section 4.1 & Section 30.
"""

import json
import logging
import re
from typing import List, Optional
from ramazan.agents.base import BaseAgent
from ramazan.config import ModelConfig
from ramazan.llm.client import LLMClient
from ramazan.llm.cost_tracker import CostTracker
from ramazan.schemas.task import Task

logger = logging.getLogger("ramazan.orchestrator_agent")


class OrchestratorAgent(BaseAgent):
    def __init__(
        self,
        model_config: ModelConfig,
        llm_client: Optional[LLMClient] = None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        super().__init__(
            name="Orchestrator",
            role="CHIEF SOFTWARE ENGINEERING ORCHESTRATOR",
            model_config=model_config,
            llm_client=llm_client,
            cost_tracker=cost_tracker,
        )

    def plan_project(self, requirements: str, architecture: str) -> List[Task]:
        """
        Breaks down requirements into a deterministic list of tasks conforming to Section 8 schema.
        """
        system_prompt = (
            "You are RAMAZAN AI Chief Software Engineering Orchestrator. "
            "Your job is to break down software requirements into small, deterministic, atomic engineering tasks. "
            "Each task must have unambiguous measurable acceptance criteria and clear dependencies."
        )

        prompt = f"""Break down the following requirements into an ordered, executable task graph.

REQUIREMENTS:
{requirements}

ARCHITECTURE RULES:
{architecture}

TASK SCHEMA REQUIREMENTS:
Each item in your JSON array MUST adhere to this exact structure:
{{
  "id": "TASK-001",
  "title": "Short title",
  "description": "Clear step-by-step implementation instructions",
  "type": "implementation | architecture | test | refactor | documentation",
  "priority": "critical | high | medium | low",
  "complexity": "low | medium | high | critical",
  "dependencies": ["TASK-000"],
  "files": ["src/path/to/file.py", "tests/test_file.py"],
  "acceptanceCriteria": [
    "Measurable criteria 1",
    "Measurable criteria 2",
    "Unit tests pass"
  ]
}}

CRITICAL RULES:
1. Every task must be as small and self-contained as possible.
2. Dependencies must form a Directed Acyclic Graph (DAG) with NO circular dependencies.
3. Every implementation task MUST have target files and unit test files.
4. Output ONLY the raw JSON array.
"""
        response = self.call_llm(prompt=prompt, system_prompt=system_prompt, task_id="PLANNING")
        tasks = self._parse_tasks(response.content)
        return tasks

    def _parse_tasks(self, content: str) -> List[Task]:
        # Clean markdown code blocks if any
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
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                if "tasks" in parsed and isinstance(parsed["tasks"], list):
                    raw_tasks = parsed["tasks"]
                elif "id" in parsed:
                    raw_tasks = [parsed]
                else:
                    raise ValueError(f"Unrecognized dict format: {list(parsed.keys())}")
            elif isinstance(parsed, list):
                raw_tasks = parsed
            else:
                raise ValueError(f"Expected list or dict, got {type(parsed)}")

            tasks = []
            for item in raw_tasks:
                if not isinstance(item, dict):
                    continue
                # Ensure defaults
                item.setdefault("status", "PENDING")
                item.setdefault("retryCount", 0)
                item.setdefault("maxRetries", 3)
                item.setdefault("reviewStatus", "NOT_REVIEWED")
                item.setdefault("testStatus", "NOT_RUN")
                task = Task.model_validate(item)
                tasks.append(task)

            if not tasks:
                raise ValueError("No valid tasks parsed from response")
            return tasks
        except Exception as e:
            logger.error(f"Failed to parse planned tasks JSON: {e}")
            # Fallback default task if parsing failed
            return [
                Task(
                    id="TASK-001",
                    title="Initialize Core Application Module",
                    description="Set up base module structure and verify tests.",
                    type="implementation",
                    priority="high",
                    complexity="medium",
                    status="PENDING",
                    dependencies=[],
                    files=["src/app.py", "tests/test_app.py"],
                    acceptanceCriteria=[
                        "Core module initializes correctly.",
                        "Basic health check returns valid status.",
                        "Unit tests pass."
                    ]
                )
            ]
