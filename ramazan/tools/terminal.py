"""
Safe Terminal Execution conforming to RAMAZAN AI Tool Security and Terminal Policy.
"""

import subprocess
import shlex
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ramazan.terminal")


class DangerousCommand(Exception):
    pass


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


# Section 28 & Spec dangerous patterns (strictly blocked from autonomous execution)
DANGEROUS_REGEX_PATTERNS = [
    r"\brm\s+-[a-zA-Z]*[rf][a-zA-Z]*\s",
    r"\bmkfs\b",
    r"\bformat\b",
    r"\bdd\s+if=",
    r"\bfdisk\b",
    r"\bdiskpart\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r">\s*/dev/(sd|nvme|disk)",
    r"\bgit\s+push\b.*(--force|-f\b)",
    r"\bgit\s+reset\s+--hard",
    r"\bgit\s+clean\s+-[a-z]*f",
    r"\bchmod\s+-R\s+777",
    r"\b(curl|wget)\b.*\|\s*(ba|z)?sh\b",
    r"\bkubectl\s+(apply|delete)\b",
    r"\bterraform\s+(apply|destroy)\b",
    r"\bdocker\s+(rm|rmi|system\s+prune)\b",
    r"\b(aws|gcloud|az)\b.*\b(delete|deploy)\b",
    r"\bDROP\s+(TABLE|DATABASE)\b",
    r":\(\)\{\s*:\|:&\s*\};:",
]

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
        cmd_clean = command.strip()
        # 1. Regex checks
        for pat in DANGEROUS_REGEX_PATTERNS:
            if re.search(pat, cmd_clean, re.IGNORECASE):
                return False
        # 2. String checks
        cmd_lower = cmd_clean.lower()
        for pattern in self.forbidden_patterns:
            if pattern.lower() in cmd_lower:
                return False
        return True

    def check_policy(self, command: str) -> None:
        cmd_clean = command.strip()
        for pat in DANGEROUS_REGEX_PATTERNS:
            if re.search(pat, cmd_clean, re.IGNORECASE):
                raise DangerousCommand(f"Blocked by policy: {command!r} (matched regex {pat!r})")
        cmd_lower = cmd_clean.lower()
        for pattern in self.forbidden_patterns:
            if pattern.lower() in cmd_lower:
                raise DangerousCommand(f"Blocked by policy: {command!r} (matched {pattern!r})")

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
