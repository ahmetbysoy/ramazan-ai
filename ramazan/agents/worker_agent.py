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
    risks: List[str] = Field(default_factory=list)
    proposals: List[str] = Field(default_factory=list)


class ScopeViolationError(Exception):
    pass


def is_test_path(p: str) -> bool:
    p = str(p).replace("\\", "/")
    name = p.rsplit("/", 1)[-1]
    return (
        p.startswith(("tests/", "test/"))
        or "/tests/" in p
        or "/test/" in p
        or name.startswith("test_")
        or name.startswith("test")
        or name.endswith(
            (
                "_test.py",
                "test.py",
                "_test.go",
                "test.go",
                ".test.ts",
                ".test.tsx",
                ".spec.ts",
                ".test.js",
                "Test.kt",
                "Test.java",
            )
        )
    )


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

    def check_scope_violation(self, task: Task, file_paths: List[str], strict_scope: bool = True) -> Optional[str]:
        if not strict_scope:
            return None
        # System-owned checks must strictly precede allowed checks
        for f in file_paths:
            norm = f.replace("\\", "/")
            if norm.startswith(".ramazan/") or norm.startswith(".git/"):
                return f"Path '{f}' is system-owned and cannot be modified by agents."
        allowed = set(task.files)
        bad = [f for f in file_paths if f not in allowed and not is_test_path(f)]
        if bad:
            return f"Files outside task scope: {bad}. Allowed: {sorted(allowed)} + test files."
        return None

    def execute_task(
        self,
        task: Task,
        context_prompt: str,
        strict_scope: bool = True,
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

            # Check strict scope
            all_files = [m.path for m in worker_output.fileModifications] + [t.path for t in worker_output.tests]
            violation = self.check_scope_violation(task, all_files, strict_scope=strict_scope)
            if violation:
                raise ScopeViolationError(violation)

            # Apply file modifications to disk
            for mod in worker_output.fileModifications:
                logger.info(f"Worker writing file: {mod.path}")
                self.fs.write_file(mod.path, mod.content)
                if mod.path.endswith(".py"):
                    parent = Path(mod.path).parent
                    curr = parent
                    while curr != Path(".") and str(curr) not in ["", "."]:
                        init_f = curr / "__init__.py"
                        if not (self.root_dir / init_f).exists():
                            self.fs.write_file(str(init_f), "")
                        curr = curr.parent

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
