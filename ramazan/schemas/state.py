"""
Project state schema for RAMAZAN AI (.ramazan/state.json).
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field


class ProjectState(BaseModel):
    project: str = Field(default="ramazan_project", description="Project identifier")
    version: int = Field(default=1, description="State schema version")
    status: str = Field(default="INITIALIZED", description="Global project status")
    currentTask: Optional[str] = Field(default=None, description="Active task id")
    completedTasks: List[str] = Field(default_factory=list, description="IDs of successfully completed tasks")
    failedTasks: List[str] = Field(default_factory=list, description="IDs of failed tasks")
    blockedTasks: List[str] = Field(default_factory=list, description="IDs of blocked tasks")
    totalTasks: int = Field(default=0, description="Total number of planned tasks")
    progress: float = Field(default=0.0, description="Completion percentage (0 to 100)")
    lastUpdated: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp of last state transition"
    )

    def calculate_progress(self) -> float:
        if self.totalTasks == 0:
            return 0.0
        return round((len(self.completedTasks) / self.totalTasks) * 100.0, 1)

    def touch(self):
        self.lastUpdated = datetime.now(timezone.utc).isoformat()
        self.progress = self.calculate_progress()
