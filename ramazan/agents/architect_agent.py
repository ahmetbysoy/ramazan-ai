"""
Architect Agent for RAMAZAN AI.
Conforms to Section 4.2, 16, 17 of specification.
Manages architecture.md, creates ADRs, and checks architecture immutability.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Optional
from ramazan.agents.base import BaseAgent
from ramazan.config import ModelConfig
from ramazan.llm.client import LLMClient
from ramazan.llm.cost_tracker import CostTracker
from ramazan.schemas.adr import ArchitectureDecisionRecord
from ramazan.tools.fs import FileSystemTools

logger = logging.getLogger("ramazan.architect_agent")


class ArchitectAgent(BaseAgent):
    def __init__(
        self,
        model_config: ModelConfig,
        root_dir: Optional[Path] = None,
        llm_client: Optional[LLMClient] = None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        super().__init__(
            name="Architect",
            role="SYSTEM ARCHITECT",
            model_config=model_config,
            llm_client=llm_client,
            cost_tracker=cost_tracker,
        )
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.fs = FileSystemTools(self.root_dir)

    def create_adr(
        self,
        adr_id: str,
        title: str,
        decision: str,
        context: str,
        alternatives: List[str],
        reason: str,
        consequences: str,
    ) -> ArchitectureDecisionRecord:
        adr = ArchitectureDecisionRecord(
            id=adr_id,
            title=title,
            decision=decision,
            context=context,
            alternatives=alternatives,
            reason=reason,
            consequences=consequences,
        )
        adr_path = f".ramazan/decisions/{adr_id}.md"
        self.fs.write_file(adr_path, adr.to_markdown())
        logger.info(f"Created ADR: {adr_path}")
        return adr

    def evaluate_architecture_proposal(self, proposal: str, current_architecture: str) -> dict:
        """
        Evaluates a proposed architectural modification per Section 17.
        """
        system_prompt = (
            "You are the RAMAZAN AI Chief Architect. "
            "You rigorously protect the system architecture and evaluate proposed modifications for safety, "
            "scalability, and backward compatibility."
        )
        prompt = f"""EVALUATE ARCHITECTURE PROPOSAL:

CURRENT ARCHITECTURE:
{current_architecture}

PROPOSAL:
{proposal}

Respond with JSON:
{{
  "approved": true | false,
  "reason": "Detailed architectural rationale",
  "recommendedAdr": "ADR title if approved, or null",
  "consequences": "Project impacts"
}}
"""
        resp = self.call_llm(prompt, system_prompt=system_prompt)
        clean = resp.content.strip()
        if "```json" in clean:
            clean = re.search(r"```json\s*(.*?)\s*```", clean, re.DOTALL).group(1)
        elif "```" in clean:
            clean = re.search(r"```\s*(.*?)\s*```", clean, re.DOTALL).group(1)

        try:
            return json.loads(clean)
        except Exception:
            return {"approved": False, "reason": "Could not parse architectural proposal evaluation."}
