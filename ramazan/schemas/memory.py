"""
Project task memory schema for RAMAZAN AI (.ramazan/memory/TASK-XXX.md).
"""

from typing import List
from pydantic import BaseModel, Field


class TaskMemory(BaseModel):
    taskId: str = Field(description="Task ID, e.g. TASK-001")
    completed: str = Field(description="Summary of work completed")
    filesChanged: List[str] = Field(default_factory=list, description="Files created or modified")
    importantDecisions: List[str] = Field(default_factory=list, description="Key design decisions made")
    problems: List[str] = Field(default_factory=list, description="Obstacles encountered during execution")
    resolution: str = Field(default="", description="How issues were resolved")
    tests: str = Field(default="", description="Test verification evidence summary")
    futureConsiderations: str = Field(default="", description="Notes for upcoming tasks")

    def to_markdown(self) -> str:
        files = "\n".join([f"- {f}" for f in self.filesChanged]) if self.filesChanged else "- None"
        decisions = "\n".join([f"- {d}" for d in self.importantDecisions]) if self.importantDecisions else "- None"
        problems = "\n".join([f"- {p}" for p in self.problems]) if self.problems else "- None"

        return f"""# {self.taskId}

## Completed
{self.completed}

## Files Changed
{files}

## Important Decisions
{decisions}

## Problems
{problems}

## Resolution
{self.resolution}

## Tests
{self.tests}

## Future Considerations
{self.futureConsiderations}
"""
