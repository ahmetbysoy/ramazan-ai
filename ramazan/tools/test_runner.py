"""
Test Engine for RAMAZAN AI.
Strict non-LLM objective verification runner.
"""

import json
import logging
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ramazan.test_engine")


class TestExecutionResult(BaseModel):
    __test__ = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    command: str
    passed: bool
    exitCode: int
    stdout: str
    stderr: str
    duration: float
    summary: str
    failures: int = 0
    errors: int = 0
    testsRun: int = 0


class TestEngine:
    __test__ = False
    def __init__(self, root_dir: Optional[Path] = None, default_command: str = "pytest -v"):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.default_command = default_command

    def run_tests(self, command: Optional[str] = None, timeout: int = 120) -> TestExecutionResult:
        cmd = command or self.default_command
        logger.info(f"Running Test Suite: {cmd}")
        start_t = time.time()

        env = dict(subprocess.os.environ)
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"src:.:{existing_pp}" if existing_pp else "src:."

        try:
            res = subprocess.run(
                cmd,
                shell=True,
                cwd=str(self.root_dir),
                capture_output=True,
                text=True,
                env=env,
                timeout=timeout
            )
            duration = round(time.time() - start_t, 3)
            passed = (res.returncode == 0)
            stdout = res.stdout or ""
            stderr = res.stderr or ""

            # Basic parsing of test counts from pytest or standard runners
            failures = 0
            errors = 0
            tests_run = 0

            # Pytest summary parsing
            for line in stdout.splitlines():
                if "failed" in line and ("passed" in line or "error" in line):
                    import re
                    f_match = re.search(r"(\d+)\s+failed", line)
                    if f_match:
                        failures = int(f_match.group(1))
                    p_match = re.search(r"(\d+)\s+passed", line)
                    passed_count = int(p_match.group(1)) if p_match else 0
                    tests_run = failures + passed_count

            summary = "All tests passed successfully." if passed else f"Tests failed with exit code {res.returncode}."

            result = TestExecutionResult(
                command=cmd,
                passed=passed,
                exitCode=res.returncode,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                summary=summary,
                failures=failures,
                errors=errors,
                testsRun=tests_run
            )

            self._save_latest_result(result)
            return result

        except subprocess.TimeoutExpired as te:
            duration = round(time.time() - start_t, 3)
            result = TestExecutionResult(
                command=cmd,
                passed=False,
                exitCode=124,
                stdout=te.stdout or "",
                stderr=f"Test run timed out after {timeout} seconds",
                duration=duration,
                summary="Test run timed out.",
                failures=1,
                errors=1,
                testsRun=0
            )
            self._save_latest_result(result)
            return result
        except Exception as e:
            duration = round(time.time() - start_t, 3)
            result = TestExecutionResult(
                command=cmd,
                passed=False,
                exitCode=1,
                stdout="",
                stderr=str(e),
                duration=duration,
                summary=f"Test runner error: {str(e)}",
                failures=1,
                errors=1,
                testsRun=0
            )
            self._save_latest_result(result)
            return result

    def _save_latest_result(self, result: TestExecutionResult):
        test_dir = self.root_dir / ".ramazan" / "tests"
        test_dir.mkdir(parents=True, exist_ok=True)
        latest_file = test_dir / "latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
