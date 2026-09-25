import pytest
from ramazan.core.circuit_breaker import CircuitBreaker, CircuitBreakerAction
from ramazan.schemas.task import Task, TaskStatus


def test_circuit_breaker_retries():
    cb = CircuitBreaker(default_max_retries=3)
    task = Task(id="TASK-001", title="Feature", description="Test", maxRetries=3)

    # Attempts 1, 2, 3 should permit RETRY_WITH_FEEDBACK
    assert cb.check(task, "Test fail 1") == CircuitBreakerAction.RETRY_WITH_FEEDBACK
    assert task.retryCount == 1

    assert cb.check(task, "Test fail 2") == CircuitBreakerAction.RETRY_WITH_FEEDBACK
    assert task.retryCount == 2

    assert cb.check(task, "Test fail 3") == CircuitBreakerAction.RETRY_WITH_FEEDBACK
    assert task.retryCount == 3

    # Attempt 4 breaches maxRetries=3 -> Trips breaker!
    action = cb.check(task, "Test fail 4")
    assert action in [
        CircuitBreakerAction.OPTION_A_CHANGE_APPROACH,
        CircuitBreakerAction.OPTION_B_SWITCH_MODEL,
        CircuitBreakerAction.OPTION_C_HUMAN_ESCALATION,
    ]
    assert task.status == TaskStatus.ESCALATED.value


def test_circuit_breaker_human_escalation_on_security():
    cb = CircuitBreaker(default_max_retries=1)
    task = Task(id="TASK-AUTH", title="Auth", description="Auth", maxRetries=1, complexity="critical")

    cb.check(task, "Test fail 1")
    action = cb.check(task, "Security vulnerability in refresh token")
    assert action == CircuitBreakerAction.OPTION_C_HUMAN_ESCALATION
