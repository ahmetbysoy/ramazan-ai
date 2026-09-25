"""
Model Router for RAMAZAN AI.
Conforms to Sections 12 & 13 of specification.
Prohibits using the most expensive model for every task.
Routes tasks based on complexity, type, capabilities, and failure history.
"""

import logging
from typing import Dict, Optional
from ramazan.config import ModelsConfig, ModelConfig, RamazanConfig
from ramazan.schemas.task import Task, TaskComplexity

logger = logging.getLogger("ramazan.router")


class ModelRouter:
    def __init__(self, config: Optional[RamazanConfig] = None):
        self.config = config or RamazanConfig()
        self.models_config = self.config.models

    def route_task(self, task: Task) -> ModelConfig:
        """
        Determines the optimal model configuration for a given task.
        """
        complexity = (task.complexity or "medium").lower()
        retry_count = task.retryCount

        logger.info(f"Routing Task '{task.id}' | Complexity: {complexity.upper()} | Retry: {retry_count}")

        # If task has failed multiple times, escalate to higher tier model
        if retry_count >= 2:
            logger.warning(f"Task '{task.id}' has {retry_count} retries. Escalating model to critical reasoning tier.")
            return self.models_config.worker.critical

        if complexity == "low":
            # Boilerplate, simple UI, documentation, simple tests, refactor
            return self.models_config.worker.low
        elif complexity == "medium":
            # Normal feature, API integration, repository, service, component
            return self.models_config.worker.medium
        elif complexity == "high":
            # Architecture, concurrency, security, complex algorithm
            return self.models_config.worker.high
        elif complexity == "critical":
            # Production security, destructive migration, auth architecture
            return self.models_config.worker.critical
        else:
            return self.models_config.worker.medium

    def get_reviewer_model(self) -> ModelConfig:
        return self.models_config.reviewer

    def get_orchestrator_model(self) -> ModelConfig:
        return self.models_config.orchestrator

    def get_architect_model(self) -> ModelConfig:
        return self.models_config.architect
