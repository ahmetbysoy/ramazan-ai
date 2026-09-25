"""
Circuit Breaker and Human-In-The-Loop Escalation for RAMAZAN AI.
Conforms to Sections 21, 22, 23 of specification.
Prevents infinite retry loops and triggers escalation strategies.
"""

from enum import Enum
import logging
from typing import List, Optional
from pydantic import BaseModel, Field

from ramazan.schemas.task import Task, TaskStatus

logger = logging.getLogger("ramazan.circuit_breaker")


class CircuitBreakerAction(str, Enum):
    RETRY_WITH_FEEDBACK = "RETRY_WITH_FEEDBACK"
    OPTION_A_CHANGE_APPROACH = "OPTION_A_CHANGE_APPROACH"
    OPTION_B_SWITCH_MODEL = "OPTION_B_SWITCH_MODEL"
    OPTION_C_HUMAN_ESCALATION = "OPTION_C_HUMAN_ESCALATION"


class EscalationReport(BaseModel):
    taskId: str
    problem: str
    attempts: int
    options: List[str]
    recommendation: str
    status: str = "USER_INTERVENTION_REQUIRED"


class CircuitBreaker:
    def __init__(self, default_max_retries: int = 3):
        self.default_max_retries = default_max_retries

    def check(self, task: Task, failure_reason: str) -> CircuitBreakerAction:
        """
        Evaluates task failure and decides whether to retry or trip the circuit breaker.
        """
        task.retryCount += 1
        max_allowed = task.maxRetries or self.default_max_retries

        logger.warning(
            f"CircuitBreaker check for {task.id}: Attempt {task.retryCount}/{max_allowed} | Reason: {failure_reason}"
        )

        if task.retryCount <= max_allowed:
            task.status = TaskStatus.RETRYING.value
            return CircuitBreakerAction.RETRY_WITH_FEEDBACK

        # Tripped circuit breaker
        task.status = TaskStatus.ESCALATED.value
        logger.critical(
            f"CIRCUIT BREAKER TRIPPED for {task.id}: Maximum retries ({max_allowed}) exceeded!"
        )

        # Decide escalation option
        complexity = (task.complexity or "medium").lower()
        if complexity in ["high", "critical"] or "security" in failure_reason.lower():
            return CircuitBreakerAction.OPTION_C_HUMAN_ESCALATION
        elif task.retryCount == max_allowed + 1:
            return CircuitBreakerAction.OPTION_B_SWITCH_MODEL
        else:
            return CircuitBreakerAction.OPTION_A_CHANGE_APPROACH

    def generate_escalation_report(self, task: Task, failure_summary: str) -> EscalationReport:
        options = [
            "A) Change approach: Reject current design and break down into simpler sub-tasks",
            "B) Switch model: Execute with an alternate high-reasoning model",
            "C) User intervention: Manual review and intervention required",
        ]
        return EscalationReport(
            taskId=task.id,
            problem=f"Task {task.id} failed after {task.retryCount} attempts. {failure_summary}",
            attempts=task.retryCount,
            options=options,
            recommendation="Do not proceed automatically. Resolve conflict or approve revised approach."
        )
