"""
Architecture Decision Record (ADR) schema and manager for RAMAZAN AI.
Conforms to Section 16: ADRs are immutable; old ADRs are never deleted, new ones are appended.
"""

from pathlib import Path
import re
from typing import List, Optional
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


class ADRManager:
    @staticmethod
    def get_decisions_dir(root_dir: Path) -> Path:
        d = root_dir / ".ramazan" / "decisions"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def next_adr_id(cls, root_dir: Path) -> str:
        d = cls.get_decisions_dir(root_dir)
        nums = []
        for p in d.glob("ADR-*.md"):
            m = re.match(r"ADR-(\d+)", p.name)
            if m:
                nums.append(int(m.group(1)))
        next_num = max(nums) + 1 if nums else 1
        return f"ADR-{next_num:03d}"

    @classmethod
    def create_adr(
        cls,
        root_dir: Path,
        decision: str,
        context: str,
        alternatives: Optional[List[str]] = None,
        reason: str = "",
        consequences: str = "",
        title: str = ""
    ) -> ArchitectureDecisionRecord:
        adr_id = cls.next_adr_id(root_dir)
        adr = ArchitectureDecisionRecord(
            id=adr_id,
            title=title or decision,
            decision=decision,
            context=context,
            alternatives=alternatives or [],
            reason=reason,
            consequences=consequences
        )
        d = cls.get_decisions_dir(root_dir)
        file_path = d / f"{adr_id}.md"
        file_path.write_text(adr.to_markdown(), encoding="utf-8")
        return adr

    @classmethod
    def list_adrs(cls, root_dir: Path) -> List[ArchitectureDecisionRecord]:
        d = cls.get_decisions_dir(root_dir)
        adrs: List[ArchitectureDecisionRecord] = []
        for p in sorted(d.glob("ADR-*.md")):
            content = p.read_text(encoding="utf-8")
            adr_id = p.stem
            # Parse sections
            title = p.stem
            decision = ""
            context = ""
            alts: List[str] = []
            reason = ""
            consequences = ""

            curr_sec = None
            for line in content.splitlines():
                if line.startswith("# "):
                    title = line.replace("# ", "").strip()
                elif line.startswith("## Decision"):
                    curr_sec = "decision"
                elif line.startswith("## Context"):
                    curr_sec = "context"
                elif line.startswith("## Alternatives"):
                    curr_sec = "alternatives"
                elif line.startswith("## Reason"):
                    curr_sec = "reason"
                elif line.startswith("## Consequences"):
                    curr_sec = "consequences"
                elif curr_sec == "decision" and line.strip():
                    decision += (line + " ")
                elif curr_sec == "context" and line.strip():
                    context += (line + " ")
                elif curr_sec == "alternatives" and line.strip().startswith("- "):
                    alts.append(line.replace("- ", "").strip())
                elif curr_sec == "reason" and line.strip():
                    reason += (line + " ")
                elif curr_sec == "consequences" and line.strip():
                    consequences += (line + " ")

            adrs.append(ArchitectureDecisionRecord(
                id=adr_id,
                title=title,
                decision=decision.strip(),
                context=context.strip(),
                alternatives=alts,
                reason=reason.strip(),
                consequences=consequences.strip()
            ))
        return adrs
