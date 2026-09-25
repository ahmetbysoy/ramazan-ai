"""
Cost tracking and Token Budget management for RAMAZAN AI.
Conforms to Sections 39 & 40 of specification.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("ramazan.budget")

# Approximate pricing per 1k tokens for cost estimation
MODEL_COST_PER_1K = {
    "claude-3-7-sonnet-20250219": {"input": 0.003, "output": 0.015},
    "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    "claude-3-5-haiku-20241022": {"input": 0.0008, "output": 0.004},
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "mock": {"input": 0.0, "output": 0.0},
}


class UsageRecord(BaseModel):
    taskId: str
    model: str
    inputTokens: int
    outputTokens: int
    estimatedCostUsd: float
    timestamp: str


class CostTracker:
    def __init__(self, max_budget_usd: float = 20.0, warning_threshold: float = 0.8):
        self.max_budget_usd = max_budget_usd
        self.warning_threshold = warning_threshold
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.records: List[UsageRecord] = []
        self._warning_emitted = False

    def record_usage(self, task_id: str, model: str, input_tokens: int, output_tokens: int) -> float:
        import datetime

        rates = MODEL_COST_PER_1K.get(model, {"input": 0.002, "output": 0.008})
        cost = (input_tokens / 1000.0 * rates["input"]) + (output_tokens / 1000.0 * rates["output"])

        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost_usd += cost

        record = UsageRecord(
            taskId=task_id,
            model=model,
            inputTokens=input_tokens,
            outputTokens=output_tokens,
            estimatedCostUsd=round(cost, 5),
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )
        self.records.append(record)

        # Budget checks
        ratio = self.total_cost_usd / max(self.max_budget_usd, 0.01)
        if ratio >= self.warning_threshold and not self._warning_emitted:
            logger.warning(
                f"BUDGET ALERT: Spent ${self.total_cost_usd:.2f} of ${self.max_budget_usd:.2f} ({ratio*100:.1f}%)."
            )
            self._warning_emitted = True

        if self.total_cost_usd >= self.max_budget_usd:
            logger.critical(
                f"BUDGET EXCEEDED: Total cost ${self.total_cost_usd:.2f} reached or exceeded limit ${self.max_budget_usd:.2f}!"
            )

        return cost

    def is_budget_exceeded(self) -> bool:
        return self.total_cost_usd >= self.max_budget_usd
