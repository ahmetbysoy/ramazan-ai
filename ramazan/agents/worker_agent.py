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
from ramazan.tools.agent_tools import AgentToolDispatcher, AGENT_TOOLS_SCHEMA, is_test_path

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
        max_turns: int = 15,
    ) -> WorkerOutput:
        """
        Executes multi-turn tool-calling loop or structured code generation under file locks.
        """
        global_file_locks.acquire_locks(task.id, task.files)

        try:
            dispatcher = AgentToolDispatcher(
                root_dir=self.root_dir,
                allowed_files=task.files,
                strict_scope=strict_scope,
            )

            system_prompt = (
                "You are an expert software engineer adhering to strict engineering discipline.\n"
                "You have access to tools to read files, list directories, write files, apply patches, run shell commands, and run tests.\n"
                "Always inspect existing code before modifying. Keep diffs minimal.\n"
                "You MUST ensure corresponding automated unit tests exist or are created.\n"
                "Stay strictly within the allowed task files and test files.\n"
                "When you are done, provide a final explanation of the changes made."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_prompt},
            ]

            turn = 0
            while turn < max_turns:
                turn += 1
                logger.info(f"Worker turn {turn}/{max_turns} for {task.id}")
                resp = self.llm_client.generate_with_tools(
                    model=self.model_config.model,
                    messages=messages,
                    tools=AGENT_TOOLS_SCHEMA,
                    temperature=self.model_config.temperature,
                )
                if self.cost_tracker:
                    self.cost_tracker.record_usage(
                        task_id=task.id,
                        model=self.model_config.model,
                        input_tokens=resp.inputTokens,
                        output_tokens=resp.outputTokens,
                    )

                # Check if tool calls were made
                if resp.tool_calls:
                    messages.append({
                        "role": "assistant",
                        "content": resp.content or "",
                        "tool_calls": resp.tool_calls,
                    })

                    for tc in resp.tool_calls:
                        func = tc.get("function", {})
                        func_name = func.get("name", "")
                        raw_args = func.get("arguments", "{}")
                        if isinstance(raw_args, str):
                            try:
                                args = json.loads(raw_args)
                            except Exception:
                                args = {}
                        else:
                            args = raw_args or {}

                        tool_res = dispatcher.execute_tool(func_name, args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", "call_1"),
                            "content": tool_res,
                        })
                    continue

                # No tool calls: final response or direct JSON response
                # 1. If tools were used during loop to create/modify files
                if dispatcher.modified_files or dispatcher.test_files:
                    mods = []
                    for f in dispatcher.modified_files:
                        p = self.root_dir / f
                        if p.exists() and p.is_file():
                            mods.append(FileModification(path=f, content=p.read_text(encoding="utf-8", errors="replace")))
                    tests = []
                    for t in dispatcher.test_files:
                        tp = self.root_dir / t
                        if tp.exists() and tp.is_file():
                            tests.append(FileModification(path=t, content=tp.read_text(encoding="utf-8", errors="replace")))

                    self._ensure_init_py([m.path for m in mods] + [t.path for t in tests])
                    return WorkerOutput(
                        explanation=resp.content.strip() or "Task completed via tool operations.",
                        fileModifications=mods,
                        tests=tests,
                        potentialRisks="None",
                    )

                # 2. Direct JSON output (single-turn or mock responder)
                worker_output = self._parse_output(resp.content)
                all_files = [m.path for m in worker_output.fileModifications] + [t.path for t in worker_output.tests]
                violation = self.check_scope_violation(task, all_files, strict_scope=strict_scope)
                if violation:
                    raise ScopeViolationError(violation)

                for mod in worker_output.fileModifications:
                    logger.info(f"Worker writing file: {mod.path}")
                    self.fs.write_file(mod.path, mod.content)

                for test_mod in worker_output.tests:
                    logger.info(f"Worker writing test file: {test_mod.path}")
                    self.fs.write_file(test_mod.path, test_mod.content)

                self._ensure_init_py([m.path for m in worker_output.fileModifications] + [t.path for t in worker_output.tests])
                return worker_output

            # If reached max_turns
            logger.warning(f"Worker reached max_turns ({max_turns}) for {task.id}.")
            mods = [FileModification(path=f, content=(self.root_dir / f).read_text(encoding="utf-8", errors="replace")) for f in dispatcher.modified_files if (self.root_dir / f).exists()]
            tests = [FileModification(path=t, content=(self.root_dir / t).read_text(encoding="utf-8", errors="replace")) for t in dispatcher.test_files if (self.root_dir / t).exists()]
            return WorkerOutput(
                explanation=f"Worker completed {max_turns} turns with tool modifications.",
                fileModifications=mods,
                tests=tests,
                potentialRisks="Maximum turn limit reached.",
            )

        finally:
            global_file_locks.release_locks(task.id)

    def _ensure_init_py(self, paths: List[str]):
        for f in paths:
            if f.endswith(".py"):
                parent = Path(f).parent
                curr = parent
                while curr != Path(".") and str(curr) not in ["", "."]:
                    init_f = curr / "__init__.py"
                    if not (self.root_dir / init_f).exists():
                        self.fs.write_file(str(init_f), "")
                    curr = curr.parent

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
