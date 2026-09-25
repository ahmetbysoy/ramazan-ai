"""
Structured Review protocol schema for Reviewer Agent.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    file: str = Field(description="Target file path")
    line: Optional[int] = Field(default=None, description="Line number if applicable")
    category: str = Field(
        default="general",
        description="Category: security, correctness, architecture, performance, testing, edge_case"
    )
    description: str = Field(description="Problem description with evidence")
    requiredFix: str = Field(description="Explicit required corrective action")


class ReviewResult(BaseModel):
    status: str = Field(description="'APPROVED' or 'CHANGES_REQUIRED'")
    severity: str = Field(default="LOW", description="'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'")
    issues: List[ReviewIssue] = Field(default_factory=list, description="List of found issues")
    summary: str = Field(default="", description="High level review summary")

    @property
    def is_approved(self) -> bool:
        return self.status == "APPROVED" and len(self.issues) == 0
