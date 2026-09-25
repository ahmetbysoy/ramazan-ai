"""
Worker Agent for RAMAZAN AI.
Conforms to Sections 4.3, 25, 34, 35 of specification.
Responsible for producing verified atomic code and test implementations.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from ramazan.agents.base import BaseAgent
from ramazan.config import ModelConfig
from ramazan.llm.client import LLMClient
from ramazan.llm.cost_tracker import CostTracker
from ramazan.schemas.task import Task
from ramazan.tools.fs import FileSystemTools, global_file_locks

logger = logging.getLogger("ramazan.worker_agent")


class FileModification(BaseModel):
    path: str
    content: str


class WorkerOutput(BaseModel):
    explanation: str = Field(description="Summary of work performed")
    fileModifications: List[FileModification] = Field(default_factory=list)
    tests: List[FileModification] = Field(default_factory=list)
    potentialRisks: str = Field(default="None")


class WorkerAgent(BaseAgent):
    def __init__(
        self,
        model_config: ModelConfig,
        root_dir: Optional[Path] = None,
        llm_client: Optional[LLMClient] = None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        super().__init__(
            name="Worker",
            role="IMPLEMENTATION WORKER",
            model_config=model_config,
            llm_client=llm_client,
            cost_tracker=cost_tracker,
        )
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.fs = FileSystemTools(self.root_dir)

    def execute_task(
        self,
        task: Task,
        context_prompt: str,
    ) -> WorkerOutput:
        """
        Executes code generation and applies modifications to filesystem under file locks.
        """
        # Section 25: Acquire file lock before modifying files
        global_file_locks.acquire_locks(task.id, task.files)

        try:
            system_prompt = (
                "You are an expert software engineer adhering to strict engineering discipline. "
                "You write minimal, clean, robust code with 100% test coverage. "
                "You NEVER modify files outside your explicit scope. "
                "You ALWAYS output strictly formatted valid JSON."
            )

            resp = self.call_llm(prompt=context_prompt, system_prompt=system_prompt, task_id=task.id)
            worker_output = self._parse_output(resp.content)

            # Apply file modifications to disk
            for mod in worker_output.fileModifications:
                logger.info(f"Worker writing file: {mod.path}")
                self.fs.write_file(mod.path, mod.content)

            for test_mod in worker_output.tests:
                logger.info(f"Worker writing test file: {test_mod.path}")
                self.fs.write_file(test_mod.path, test_mod.content)

            return worker_output

        finally:
            # Release file locks after changes are written
            global_file_locks.release_locks(task.id)

    def _parse_output(self, content: str) -> WorkerOutput:
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
            return WorkerOutput.model_validate(data)
        except Exception as e:
            logger.warning(f"Could not parse worker JSON ({e}). Falling back to empty modification set.")
            return WorkerOutput(
                explanation="Simulated or unparsed response",
                fileModifications=[],
                tests=[],
                potentialRisks="Failed to parse structured JSON output."
            )
