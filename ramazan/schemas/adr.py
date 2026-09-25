"""
Architecture Decision Record (ADR) schema for RAMAZAN AI.
"""

from typing import List
from pydantic import BaseModel, Field


class ArchitectureDecisionRecord(BaseModel):
    id: str = Field(description="ADR ID, e.g. ADR-001")
    title: str = Field(default="", description="ADR Title")
    decision: str = Field(description="Core decision made")
    context: str = Field(description="Context and motivation")
    alternatives: List[str] = Field(default_factory=list, description="Considered alternatives")
    reason: str = Field(description="Justification for selection")
    consequences: str = Field(description="Impact and trade-offs")

    def to_markdown(self) -> str:
        alts = "\n".join([f"- {a}" for a in self.alternatives]) if self.alternatives else "- None"
        return f"""# {self.id}: {self.title or self.decision}

## Decision
{self.decision}

## Context
{self.context}

## Alternatives
{alts}

## Reason
{self.reason}

## Consequences
{self.consequences}
"""
