"""
Task data schemas and lifecycle states for RAMAZAN AI.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    # Lifecycle states
    PENDING = "PENDING"
    READY = "READY"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    IMPLEMENTED = "IMPLEMENTED"
    TESTING = "TESTING"
    REVIEWING = "REVIEWING"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"

    # Error & Escalation states
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    RETRYING = "RETRYING"
    ESCALATED = "ESCALATED"


class TaskPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskComplexity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TaskType(str, Enum):
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    TEST = "test"
    REVIEW = "review"
    DOCUMENTATION = "documentation"
    REFACTOR = "refactor"


class ReviewStatus(str, Enum):
    NOT_REVIEWED = "NOT_REVIEWED"
    APPROVED = "APPROVED"
    CHANGES_REQUIRED = "CHANGES_REQUIRED"


class TestStatus(str, Enum):
    NOT_RUN = "NOT_RUN"
    PASSED = "PASSED"
    FAILED = "FAILED"


class Task(BaseModel):
    id: str = Field(description="Unique Task identifier e.g. TASK-001")
    title: str = Field(description="Short descriptive task title")
    description: str = Field(description="Detailed task instructions")
    type: str = Field(default="implementation", description="Task category")
    priority: str = Field(default="medium", description="Task priority")
    complexity: str = Field(default="medium", description="Task complexity")
    status: str = Field(default="PENDING", description="Current lifecycle state")
    dependencies: List[str] = Field(default_factory=list, description="IDs of prerequisite tasks")
    files: List[str] = Field(default_factory=list, description="Target files for this task")
    acceptanceCriteria: List[str] = Field(
        default_factory=list,
        description="Measurable objective acceptance criteria"
    )
    assignedAgent: Optional[str] = Field(default=None, description="Assigned agent role")
    assignedModel: Optional[str] = Field(default=None, description="Assigned AI model name")
    retryCount: int = Field(default=0, description="Current retry attempt number")
    maxRetries: int = Field(default=3, description="Maximum retry limit before circuit breaker")
    reviewStatus: str = Field(default="NOT_REVIEWED", description="Status of code review")
    testStatus: str = Field(default="NOT_RUN", description="Status of automated tests")
    testOutput: Optional[str] = Field(default=None, description="Latest test stdout/stderr")
    reviewFeedback: Optional[str] = Field(default=None, description="Latest reviewer notes")
