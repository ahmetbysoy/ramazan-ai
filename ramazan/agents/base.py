"""
Base Agent abstraction for RAMAZAN AI.
"""

from abc import ABC, abstractmethod
import logging
from typing import Optional
from ramazan.config import ModelConfig
from ramazan.llm.client import LLMClient, LLMResponse
from ramazan.llm.cost_tracker import CostTracker

logger = logging.getLogger("ramazan.agent")


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        role: str,
        model_config: ModelConfig,
        llm_client: Optional[LLMClient] = None,
        cost_tracker: Optional[CostTracker] = None,
    ):
        self.name = name
        self.role = role
        self.model_config = model_config
        self.llm_client = llm_client or LLMClient()
        self.cost_tracker = cost_tracker

    def call_llm(self, prompt: str, system_prompt: Optional[str] = None, task_id: str = "GLOBAL") -> LLMResponse:
        logger.info(f"Agent [{self.name}] ({self.role}) calling model {self.model_config.model}")
        resp = self.llm_client.generate(
            model=self.model_config.model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=self.model_config.temperature
        )
        if self.cost_tracker:
            self.cost_tracker.record_usage(
                task_id=task_id,
                model=self.model_config.model,
                input_tokens=resp.inputTokens,
                output_tokens=resp.outputTokens
            )
        return resp
