"""
Safe Terminal Execution conforming to RAMAZAN AI Tool Security and Terminal Policy.
Enforces Sections 28 & 29 of the specification with versioned regex policies,
mandatory structured invocation audits, and detailed forensic logging.
"""

import subprocess
import shlex
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("ramazan.terminal")


class DangerousCommand(Exception):
    """Raised when a command violates the deterministic Terminal Safety Policy."""
    pass


class CommandInvocation(BaseModel):
    """
    Section 29: Mandatory structured invocation schema.
    No command can be executed without documented purpose, expected effect, and risk level.
    """
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


# Versioned deterministic safety patterns (Section 28 & 29)
STRUCTURED_POLICY_PATTERNS: Dict[str, str] = {
    # 1. Destructive rm (path-independent: rm -r, rm -rf, rm --recursive, etc.)
    "destructive_rm": r"\brm\s+([^\s]*\s+)*(-[a-zA-Z]*r[a-zA-Z]*|--recursive)\b",
    # 2. Filesystem creation & formatting
    "filesystem_format": r"\b(mkfs(\.[a-zA-Z0-9_-]+)?|format)\b",
    # 3. Raw block device direct write / imaging
    "raw_disk_dd": r"\bdd\s+([^\s]*\s+)*(if=|of=/dev/)",
    # 4. Low level disk partitioning
    "disk_partitioning": r"\b(fdisk|gdisk|parted|diskpart)\b",
    # 5. Raw block device redirection
    "raw_device_redirect": r">\s*/dev/(sd|nvme|hd|vd|disk|mapper|null\s*;\s*rm)",
    # 6. Fork bombs
    "fork_bomb": r"(:\(\)\s*\{\s*:\|:&\s*\};:|bomb\(\)\s*\{\s*bomb\s*\|\s*bomb\s*&\s*\};)",
    # 7. Git destructive reset
    "git_hard_reset": r"\bgit\s+reset\s+--hard\b",
    # 8. Git destructive clean
    "git_destructive_clean": r"\bgit\s+clean\s+([^\s]*\s+)*(-[a-zA-Z]*f[a-zA-Z]*|--force)\b",
    # 9. Git force push
    "git_force_push": r"\bgit\s+push\s+([^\s]*\s+)*(--force|-f\b)",
    # 10. Pipe to shell arbitrary execution
    "pipe_to_shell": r"\b(curl|wget)\b[^\n|;&]*\|\s*(ba|z)?sh\b",
    # 11. Eval dynamic shell execution
    "eval_execution": r"\beval\s+[\"\']?(\$|\`|\()",
    # 12. Overly permissive recursive permissions
    "reckless_chmod_777": r"\bchmod\s+(-[a-zA-Z]*R|--recursive)\s+777\b|\bchmod\s+777\s+(-[a-zA-Z]*R|--recursive)\b",
    # 13. Recursive chown
    "recursive_chown": r"\bchown\s+(-[a-zA-Z]*R|--recursive)\b",
    # 14. SQL DROP TABLE / DATABASE
    "sql_drop": r"\bDROP\s+(TABLE|DATABASE|SCHEMA|VIEW)\b",
    # 15. SQL TRUNCATE TABLE
    "sql_truncate": r"\bTRUNCATE(\s+TABLE)?\s+[a-zA-Z0-9_.]+",
    # 16. SQL DELETE without WHERE clause
    "sql_delete_without_where": r"\bDELETE\s+FROM\s+[a-zA-Z0-9_.]+(\s*;|\s*$)",
    # 17. Terraform infrastructure destruction/mutation
    "terraform_destroy": r"\bterraform\s+(destroy|apply\s+.*-auto-approve)\b",
    # 18. Kubernetes deletion
    "kubectl_delete": r"\bkubectl\s+(delete|drain)\b",
    # 19. Docker system wipe / forced rm
    "docker_wipe": r"\bdocker\s+(system\s+prune|rm\s+-f|rmi\s+-f)\b",
    # 20. Cloud CLI destructive actions
    "cloud_cli_delete": r"\b(aws\s+s3\s+rm\s+.*--recursive|gcloud\s+.*delete|az\s+.*delete)\b",
    # 21. System shutdown and reboot
    "system_shutdown": r"\b(shutdown|reboot|poweroff|init\s+0|halt)\b",
}


class TerminalPolicy:
    """
    Evaluates shell commands against versioned security policies
    and maintains structured audit logs in .ramazan/logs/.
    """
    VERSION = "2.0.0"

    def __init__(self, root_dir: Optional[Path] = None, custom_patterns: Optional[List[str]] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.logs_dir = self.root_dir / ".ramazan" / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.custom_patterns = custom_patterns or []

    def evaluate(self, command: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Returns (is_allowed, policy_rule_name, reason).
        """
        cmd_clean = command.strip()

        # 1. Check versioned regex patterns
        for rule_name, pattern in STRUCTURED_POLICY_PATTERNS.items():
            if re.search(pattern, cmd_clean, re.IGNORECASE):
                reason = f"Violates safety policy [{rule_name}]: matched regex '{pattern}'"
                return False, rule_name, reason

        # 2. Check custom config forbidden patterns
        cmd_lower = cmd_clean.lower()
        for custom_pat in self.custom_patterns:
            if custom_pat.lower() in cmd_lower:
                reason = f"Violates custom configured forbidden pattern: '{custom_pat}'"
                return False, "custom_forbidden", reason

        return True, None, None

    def log_blocked(self, invocation: CommandInvocation, reason: str, rule: str) -> None:
        """Log blocked command violation to .ramazan/logs/blocked_commands.log."""
        log_file = self.logs_dir / "blocked_commands.log"
        ts = datetime.now(timezone.utc).isoformat()
        entry = (
            f"[{ts}] BLOCKED (Rule: {rule})\n"
            f"  Command:         {invocation.command}\n"
            f"  Reason:          {reason}\n"
            f"  Purpose:         {invocation.purpose}\n"
            f"  Expected Effect: {invocation.expectedEffect}\n"
            f"  Assessed Risk:   {invocation.risk}\n"
            f"{'-'*60}\n"
        )
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"Failed to write to blocked_commands.log: {e}")

    def log_execution(self, invocation: CommandInvocation, result: CommandResult) -> None:
        """Section 29: Log executed command audit to .ramazan/logs/command_audit.log."""
        log_file = self.logs_dir / "command_audit.log"
        ts = datetime.now(timezone.utc).isoformat()
        entry = (
            f"[{ts}] EXECUTED (ExitCode: {result.exitCode}, Duration: {result.duration:.3f}s)\n"
            f"  Command:         {invocation.command}\n"
            f"  Purpose:         {invocation.purpose}\n"
            f"  Expected Effect: {invocation.expectedEffect}\n"
            f"  Assessed Risk:   {invocation.risk}\n"
            f"{'-'*60}\n"
        )
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            logger.error(f"Failed to write to command_audit.log: {e}")


class TerminalRunner:
    """
    Executes shell commands with strict TerminalPolicy enforcement,
    non-zero timeout protection, and Section 29 audit logging.
    """
    def __init__(
        self,
        cwd: Optional[Path] = None,
        forbidden_patterns: Optional[List[str]] = None,
        policy: Optional[TerminalPolicy] = None
    ):
        self.cwd = (cwd or Path.cwd()).resolve()
        self.policy = policy or TerminalPolicy(root_dir=self.cwd, custom_patterns=forbidden_patterns)

    def is_safe(self, command: str) -> bool:
        allowed, _, _ = self.policy.evaluate(command)
        return allowed

    def check_policy(self, command: str) -> None:
        allowed, rule, reason = self.policy.evaluate(command)
        if not allowed:
            raise DangerousCommand(reason)

    def execute(self, invocation: CommandInvocation, timeout: int = 60) -> CommandResult:
        import time

        allowed, rule, reason = self.policy.evaluate(invocation.command)
        if not allowed:
            self.policy.log_blocked(invocation, reason=reason or "Security violation", rule=rule or "unknown")
            logger.error(f"BLOCKED dangerous command: {invocation.command} - {reason}")
            return CommandResult(
                command=invocation.command,
                exitCode=126,
                stdout="",
                stderr=f"Security violation: {reason}",
                success=False,
                duration=0.0
            )

        logger.info(
            f"Executing Command: '{invocation.command}' | Purpose: {invocation.purpose} | Risk: {invocation.risk}"
        )
        start_time = time.time()
        try:
            proc = subprocess.run(
                invocation.command,
                shell=True,
                cwd=str(self.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            duration = time.time() - start_time
            res = CommandResult(
                command=invocation.command,
                exitCode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                success=(proc.returncode == 0),
                duration=duration
            )
            self.policy.log_execution(invocation, res)
            return res

        except subprocess.TimeoutExpired as e:
            duration = time.time() - start_time
            logger.warning(f"Command timed out after {timeout}s: {invocation.command}")
            res = CommandResult(
                command=invocation.command,
                exitCode=124,
                stdout=e.stdout or "" if isinstance(e.stdout, str) else "",
                stderr=f"Command timed out after {timeout} seconds",
                success=False,
                duration=duration
            )
            self.policy.log_execution(invocation, res)
            return res
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Command execution error: {e}")
            res = CommandResult(
                command=invocation.command,
                exitCode=1,
                stdout="",
                stderr=str(e),
                success=False,
                duration=duration
            )
            self.policy.log_execution(invocation, res)
            return res
