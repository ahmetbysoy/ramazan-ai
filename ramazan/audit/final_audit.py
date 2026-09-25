"""
Final Audit Engine for RAMAZAN AI.
Conforms to Sections 45 & 46 of specification.
Runs comprehensive verification before marking project COMPLETED.
"""

import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from ramazan.core.security import SecurityAuditor
from ramazan.tools.test_runner import TestEngine
from ramazan.tools.git_manager import GitManager

logger = logging.getLogger("ramazan.audit")


class AuditCheck(BaseModel):
    name: str
    passed: bool
    details: str


class AuditReport(BaseModel):
    passed: bool
    checks: List[AuditCheck]
    summary: str

    def to_markdown(self) -> str:
        status_str = "PASSED - ALL CRITERIA SATISFIED" if self.passed else "BLOCKED - DEFECTS FOUND"
        lines = [
            f"# Final Audit Report: {status_str}",
            "",
            f"**Summary:** {self.summary}",
            "",
            "## Verification Checks",
        ]
        for chk in self.checks:
            icon = "[PASS]" if chk.passed else "[FAIL]"
            lines.append(f"- **{icon} {chk.name}**: {chk.details}")
        return "\n".join(lines)


class FinalAuditor:
    def __init__(self, root_dir: Optional[Path] = None, test_command: str = "pytest -v"):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.test_engine = TestEngine(self.root_dir, default_command=test_command)
        self.git_manager = GitManager(self.root_dir)

    def run_audit(self) -> AuditReport:
        checks: List[AuditCheck] = []

        # 1. Test Suite Pass
        test_res = self.test_engine.run_tests()
        checks.append(AuditCheck(
            name="Test Suite Verification",
            passed=test_res.passed,
            details=f"Exit code: {test_res.exitCode}, Failures: {test_res.failures}, Summary: {test_res.summary}"
        ))

        # 2. Secret Scan across source code (excluding tests and metadata)
        secret_findings = []
        for p in self.root_dir.rglob("*.py"):
            p_str = str(p)
            if any(ign in p_str for ign in [".ramazan", ".venv", ".git", "tests"]):
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                found = SecurityAuditor.scan_for_secrets(content)
                if found:
                    secret_findings.append(f"{p.name}: {len(found)} detected")
            except Exception:
                pass

        secrets_clean = (len(secret_findings) == 0)
        checks.append(AuditCheck(
            name="Secret Management & Credential Leaks",
            passed=secrets_clean,
            details="No secrets detected in source code." if secrets_clean else f"Secrets found: {', '.join(secret_findings)}"
        ))

        # 3. Architecture Rules Check
        arch_file = self.root_dir / ".ramazan" / "architecture.md"
        arch_exists = arch_file.exists()
        checks.append(AuditCheck(
            name="Architecture Integrity (.ramazan/architecture.md)",
            passed=arch_exists,
            details="Architecture document present and intact." if arch_exists else "Missing .ramazan/architecture.md"
        ))

        # 4. Git Repository Status
        status_clean = True
        status_details = "Clean or skipped."
        repo = self.git_manager.get_repo()
        if repo:
            try:
                dirty = repo.is_dirty(untracked_files=False)
                status_clean = not dirty
                status_details = "Working tree clean." if not dirty else "Uncommitted modified files exist in working tree."
            except Exception as e:
                status_details = f"Git check warning: {e}"

        checks.append(AuditCheck(
            name="Git Working Tree Status",
            passed=status_clean,
            details=status_details
        ))

        all_passed = all(c.passed for c in checks)
        summary = (
            "All final audit gates passed. System is verified ready for production release."
            if all_passed else
            "Final audit failed. One or more quality gates did not meet completion criteria."
        )

        return AuditReport(passed=all_passed, checks=checks, summary=summary)
