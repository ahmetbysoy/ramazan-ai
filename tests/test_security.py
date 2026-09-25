import pytest
from ramazan.core.security import SecurityAuditor
from ramazan.tools.terminal import TerminalRunner, CommandInvocation


def test_security_auditor_secret_detection():
    clean_code = "def add(a, b): return a + b"
    assert len(SecurityAuditor.scan_for_secrets(clean_code)) == 0

    sample_prefix = "sk-"
    leaked_code = f"OPENAI_API_KEY = '{sample_prefix}12345678901234567890123456789012'"
    leaks = SecurityAuditor.scan_for_secrets(leaked_code)
    assert len(leaks) > 0


def test_terminal_runner_blocks_destructive_commands(tmp_path):
    runner = TerminalRunner(cwd=tmp_path)

    safe_inv = CommandInvocation(
        command="echo hello",
        purpose="Testing echo",
        expectedEffect="Prints hello",
        risk="low"
    )
    res_safe = runner.execute(safe_inv)
    assert res_safe.success is True
    assert "hello" in res_safe.stdout

    danger_inv = CommandInvocation(
        command="rm -rf /",
        purpose="Malicious test",
        expectedEffect="System destruction",
        risk="critical"
    )
    res_danger = runner.execute(danger_inv)
    assert res_danger.success is False
    assert "Security violation" in res_danger.stderr
