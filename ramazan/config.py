"""
Configuration management for RAMAZAN AI.
Enforces strict schema validation with extra="forbid" (TASK-102).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, ValidationError


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelConfig(StrictBaseModel):
    model: str = "claude-3-5-sonnet-latest"
    provider: str = "anthropic"
    temperature: float = 0.2


class WorkerModels(StrictBaseModel):
    low: ModelConfig = Field(default_factory=lambda: ModelConfig(model="gpt-4o-mini", provider="openai", temperature=0.2))
    medium: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-5-haiku-latest", provider="anthropic", temperature=0.2))
    high: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-5-sonnet-latest", provider="anthropic", temperature=0.2))
    critical: ModelConfig = Field(default_factory=lambda: ModelConfig(model="gpt-4o", provider="openai", temperature=0.1))


class ModelsConfig(StrictBaseModel):
    orchestrator: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-5-sonnet-latest", provider="anthropic", temperature=0.2))
    architect: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-5-sonnet-latest", provider="anthropic", temperature=0.2))
    worker: WorkerModels = Field(default_factory=WorkerModels)
    reviewer: ModelConfig = Field(default_factory=lambda: ModelConfig(model="claude-3-5-sonnet-latest", provider="anthropic", temperature=0.1))


class SystemConfig(StrictBaseModel):
    name: str = "RAMAZAN AI"
    version: str = "1.0"
    autonomyMode: str = "step_by_step"  # "step_by_step", "semi_autonomous", "fully_autonomous"
    maxRetries: int = 3
    maxBudgetUsd: float = 20.0
    budgetWarningThreshold: float = 0.8
    autoGitCommit: bool = True
    humanInTheLoopOnCritical: bool = True
    strictScope: bool = True  # Worker task.files dışına çıkarsa FAIL (Section 14 & 20)
    reviewEnabled: bool = True  # Reviewer agent devrede mi
    logLevel: str = "INFO"


class ToolsConfig(StrictBaseModel):
    testCommand: str = "pytest -v"
    buildCommand: Optional[str] = None
    lintCommand: str = "pytest -q"
    allowTerminal: bool = True
    policyVersion: str = "2.0.0"
    forbiddenCommands: List[str] = Field(
        default_factory=lambda: [
            "rm -rf /",
            "rm -rf ./src",
            "mkfs",
            ":(){ :|:& };:",
            "dd if=/dev/zero",
            "git reset --hard",
            "git clean -fd",
            "git push --force",
            "chmod -R 777",
            "curl | sh",
            "terraform destroy",
            "kubectl delete",
            "docker system prune",
            "DROP TABLE",
            "shutdown",
            "reboot"
        ]
    )


class RamazanConfig(StrictBaseModel):
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

        # Check global user configuration at ~/.ramazan/config.json
        user_global_cfg = Path.home() / ".ramazan" / "config.json"
        if user_global_cfg.exists() and user_global_cfg != config_path:
            try:
                with open(user_global_cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return cls.model_validate(data)
            except Exception:
                pass

        # Auto-map from environment variables if present
        cfg = cls()
        if os.environ.get("GEMINI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"):
            try:
                from ramazan.llm.key_detector import SmartKeyDetector
                return SmartKeyDetector.auto_map_providers({}, cfg)
            except Exception:
                return cfg
        return cfg

    @classmethod
    def load_strict(cls, root_dir: Optional[Path] = None) -> "RamazanConfig":
        """Loads and raises ValidationError if config schema is invalid or has unknown fields."""
        if root_dir is None:
            root_dir = find_project_root()
        config_path = root_dir / ".ramazan" / "config.json"
        if not config_path.exists():
            return cls()
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.model_validate(data)

    def save(self, root_dir: Optional[Path] = None) -> Path:
        if root_dir is None:
            root_dir = find_project_root()
        config_path = root_dir / ".ramazan" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2) + "\n")
        return config_path


def find_project_root(start: Optional[Path] = None) -> Path:
    curr = (start or Path.cwd()).resolve()
    while curr != curr.parent:
        if (curr / ".ramazan").exists():
            return curr
        curr = curr.parent
    return Path.cwd().resolve()
