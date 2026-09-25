import pytest
from pathlib import Path
from ramazan.audit.final_audit import (
    FinalAuditor,
    BuildCheck,
    TestsCheck,
    LintCheck,
    SecurityCheck,
    ArchitectureCheck,
    DependenciesCheck,
    DeadCodeCheck,
    ErrorHandlingCheck,
    PerformanceCheck,
    DocumentationCheck,
    SecretsCheck,
    GitStatusCheck,
)


def test_all_12_checks_instantiated_and_executed(tmp_path: Path):
    """
    Acceptance Criterion:
    Each of the 12 checks defined in Spec Section 45 is present and verified.
    """
    auditor = FinalAuditor(tmp_path)
    report = auditor.run_audit()

    # Verify exactly 12 checks executed
    assert len(report.checks) == 12
    check_names = [c.name for c in report.checks]
    assert any("Build" in name for name in check_names)
    assert any("Test" in name for name in check_names)
    assert any("Lint" in name for name in check_names)
    assert any("Security" in name for name in check_names)
    assert any("Architecture" in name for name in check_names)
    assert any("Dependencies" in name for name in check_names)
    assert any("Dead Code" in name for name in check_names)
    assert any("Error Handling" in name for name in check_names)
    assert any("Performance" in name for name in check_names)
    assert any("Documentation" in name for name in check_names)
    assert any("Secrets" in name for name in check_names)
    assert any("Git" in name for name in check_names)


def test_secret_scanner_detects_real_embedded_secret(tmp_path: Path):
    """
    Acceptance Criterion:
    Secret scanner catches a real embedded API key and returns status='FAIL'.
    """
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    leaked_file = src_dir / "service.py"
    leaked_file.write_text(
        'OPENAI_KEY = "sk-proj-abc123456789012345678901234567890"\nprint("connected")\n',
        encoding="utf-8"
    )

    secrets_check = SecretsCheck(tmp_path)
    res = secrets_check.run()
    assert res.status == "FAIL"
    assert "secret pattern" in res.evidence.lower() or "credentials detected" in res.details.lower()


def test_audit_with_skipped_yields_partial_not_passed(tmp_path: Path):
    """
    Acceptance Criterion:
    An audit containing any SKIPPED checks must yield status='PARTIAL' (passed=False),
    never 'PASSED'.
    """
    # Create minimal project files so other checks pass or skip
    (tmp_path / "README.md").write_text("# Project Docs\nMore than 100 characters of valid documentation for testing purposes.\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (tmp_path / ".ramazan").mkdir()
    (tmp_path / ".ramazan" / "architecture.md").write_text("# Architecture\n", encoding="utf-8")

    # Auditor with lint_command="SKIP" produces an explicit SKIPPED for LintCheck
    auditor = FinalAuditor(tmp_path, lint_command="SKIP", test_command="python3 -c 'exit(0)'")
    report = auditor.run_audit()

    skipped_checks = [c for c in report.checks if c.status == "SKIPPED"]
    assert len(skipped_checks) > 0

    # Must be PARTIAL, not PASSED
    assert report.status == "PARTIAL"
    assert report.passed is False
    assert "PARTIAL" in report.summary


def test_dead_code_check_detects_zero_byte_source(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "dead_module.py").write_text("", encoding="utf-8")

    check = DeadCodeCheck(tmp_path)
    res = check.run()
    assert res.status == "FAIL"
    assert "dead_module.py" in res.evidence


def test_error_handling_check_detects_bare_except(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True)
    (src_dir / "risky.py").write_text(
        "try:\n    x = 1 / 0\nexcept:\n    pass\n",
        encoding="utf-8"
    )

    check = ErrorHandlingCheck(tmp_path)
    res = check.run()
    assert res.status == "FAIL"
    assert "risky.py" in res.evidence
