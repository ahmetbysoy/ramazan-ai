"""
Safe Terminal Execution conforming to RAMAZAN AI Tool Security and Terminal Policy.
"""

import subprocess
import shlex
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ramazan.terminal")


class CommandInvocation(BaseModel):
    command: str = Field(description="The shell command to execute")
    purpose: str = Field(description="Why this command must be run")
    expectedEffect: str = Field(description="What will happen after this command completes")
    risk: str = Field(default="low", description="Assessed risk level: low, medium, high, critical")


class CommandResult(BaseModel):
    command: str
    exitCode: int
    stdout: str
    stderr: str
    success: bool
    duration: float


DEFAULT_FORBIDDEN_PATTERNS = [
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    ":(){ :|:& };:",
    "dd if=/dev/zero",
    "> /dev/sda",
    "shutdown",
    "reboot",
    "init 0",
    "poweroff",
    "chmod -R 777 /",
    "chown -R root /",
]


class TerminalRunner:
    def __init__(self, cwd: Optional[Path] = None, forbidden_patterns: Optional[List[str]] = None):
        self.cwd = (cwd or Path.cwd()).resolve()
        self.forbidden_patterns = forbidden_patterns or DEFAULT_FORBIDDEN_PATTERNS

    def is_safe(self, command: str) -> bool:
        cmd_clean = command.strip().lower()
        for pattern in self.forbidden_patterns:
            if pattern.lower() in cmd_clean:
                return False
        return True

    def execute(self, invocation: CommandInvocation, timeout: int = 60) -> CommandResult:
        import time

        if not self.is_safe(invocation.command):
            logger.error(f"BLOCKED dangerous command: {invocation.command}")
            return CommandResult(
                command=invocation.command,
                exitCode=126,
                stdout="",
                stderr=f"Security violation: Command '{invocation.command}' violates tool safety policy.",
                success=False,
                duration=0.0
            )

        logger.info(
            f"Executing Command: '{invocation.command}' | Purpose: {invocation.purpose} | Risk: {invocation.risk}"
        )

        start_t = time.time()
        try:
            res = subprocess.run(
                invocation.command,
                shell=True,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            duration = round(time.time() - start_t, 3)
            return CommandResult(
                command=invocation.command,
                exitCode=res.returncode,
                stdout=res.stdout,
                stderr=res.stderr,
                success=(res.returncode == 0),
                duration=duration
            )
        except subprocess.TimeoutExpired as te:
            duration = round(time.time() - start_t, 3)
            return CommandResult(
                command=invocation.command,
                exitCode=124,
                stdout=te.stdout or "",
                stderr=f"Command timed out after {timeout} seconds",
                success=False,
                duration=duration
            )
        except Exception as e:
            duration = round(time.time() - start_t, 3)
            return CommandResult(
                command=invocation.command,
                exitCode=1,
                stdout="",
                stderr=str(e),
                success=False,
                duration=duration
            )
