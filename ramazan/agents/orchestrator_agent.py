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
        from ramazan.core.planner import PlanValidator

        system_prompt = (
            "You are RAMAZAN AI Chief Software Engineering Orchestrator. "
            "Your job is to break down software requirements into small, deterministic, atomic engineering tasks. "
            "Each task must have unambiguous measurable acceptance criteria and clear dependencies forming a strict DAG."
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
  "type": "implementation",
  "priority": "high",
  "complexity": "medium",
  "dependencies": [],
  "files": ["src/path/to/file.py", "tests/test_file.py"],
  "acceptanceCriteria": [
    "HTTP 200 response with validated schema",
    "Unit tests pass with 100% assertions"
  ]
}}

CRITICAL RULES:
1. Every task must be as small and self-contained as possible.
2. Dependencies must form a Directed Acyclic Graph (DAG) with NO circular dependencies.
3. Every implementation task MUST have target implementation files AND unit test files in its "files" array (e.g. files: ["src/path/to/file.py", "tests/test_file.py"]). NEVER create a separate task just for tests; each task must implement its code and tests together.
4. Acceptance criteria must be objective and measurable (avoid vague words like 'works' or 'looks good').
5. Output ONLY the raw JSON array.
"""
        response = self.call_llm(prompt=prompt, system_prompt=system_prompt, task_id="PLANNING")
        tasks = PlanValidator.validate_raw_json(response.content)
        return tasks
