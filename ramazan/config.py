"""
Configuration management for RAMAZAN AI.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    model: str = "claude-3-7-sonnet-20250219"
    provider: str = "anthropic"
    temperature: float = 0.2


class WorkerModels(BaseModel):
    low: ModelConfig = Field(default_factory=lambda: ModelConfig(model="gpt-4o-mini", provider="openai", temperature=0.2))
    medium: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-5-haiku-20241022", provider="anthropic", temperature=0.2))
    high: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.2))
    critical: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.1))


class ModelsConfig(BaseModel):
    orchestrator: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.2))
    architect: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.2))
    worker: WorkerModels = Field(default_factory=WorkerModels)
    reviewer: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.1))


class SystemConfig(BaseModel):
    name: str = "RAMAZAN AI"
    version: str = "1.0"
    maxRetries: int = 3
    maxBudgetUsd: float = 20.0
    budgetWarningThreshold: float = 0.8
    autoGitCommit: bool = True
    humanInTheLoopOnCritical: bool = True
    logLevel: str = "INFO"


class ToolsConfig(BaseModel):
    testCommand: str = "pytest -v"
    lintCommand: str = "pytest -q"
    allowTerminal: bool = True
    forbiddenCommands: List[str] = Field(
        default_factory=lambda: [
            "rm -rf /",
            "mkfs",
            ":(){ :|:& };:",
            "dd if=/dev/zero",
            "shutdown",
            "reboot"
        ]
    )


class RamazanConfig(BaseModel):
    system: SystemConfig = Field(default_factory=SystemConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)

    @classmethod
    def load(cls, root_dir: Optional[Path] = None) -> "RamazanConfig":
        if root_dir is None:
            root_dir = find_project_root()
        config_path = root_dir / ".ramazan" / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls.model_validate(data)
            except Exception:
                return cls()
        return cls()

    def save(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            root_dir = find_project_root()
        config_path = root_dir / ".ramazan" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))


def find_project_root(start_dir: Optional[Path] = None) -> Path:
    current = start_dir or Path.cwd()
    current = current.resolve()
    for p in [current, *current.parents]:
        if (p / ".ramazan").exists():
            return p
    return current
