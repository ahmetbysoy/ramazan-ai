"""
Smart API Key Auto-Detector and Provider Dynamic Mapping for RAMAZAN AI.
Automatically detects provider based on API key prefix/signature and dynamically
reconfigures agent model assignments.
"""

import os
import re
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from ramazan.config import ModelConfig, ModelsConfig, RamazanConfig, WorkerModels


class DetectedKey(BaseModel):
    provider: str
    key_name: str
    suggested_models: Dict[str, str]
    confidence: float
    description: str


# Pattern signatures for popular AI model providers
PROVIDER_SIGNATURES = [
    {
        "provider": "anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "pattern": re.compile(r"^sk-ant-[a-zA-Z0-9_\-]{20,}$"),
        "name": "Anthropic Claude",
        "models": {
            "orchestrator": "claude-3-7-sonnet-20250219",
            "architect": "claude-3-7-sonnet-20250219",
            "worker_high": "claude-3-7-sonnet-20250219",
            "worker_medium": "claude-3-5-haiku-20241022",
            "worker_low": "claude-3-5-haiku-20241022",
            "reviewer": "claude-3-7-sonnet-20250219",
        }
    },
    {
        "provider": "openai",
        "env_var": "OPENAI_API_KEY",
        "pattern": re.compile(r"^(sk-proj-[a-zA-Z0-9_\-]{30,}|sk-admin-[a-zA-Z0-9_\-]{30,}|sk-[a-zA-Z0-9]{32,})$"),
        "name": "OpenAI",
        "models": {
            "orchestrator": "gpt-4o",
            "architect": "gpt-4o",
            "worker_high": "gpt-4o",
            "worker_medium": "gpt-4o-mini",
            "worker_low": "gpt-4o-mini",
            "reviewer": "gpt-4o",
        }
    },
    {
        "provider": "gemini",
        "env_var": "GEMINI_API_KEY",
        "pattern": re.compile(r"^(AIza[0-9A-Za-z\-_]{35}|AQ\.[0-9A-Za-z\-_]{30,})$"),
        "name": "Google Gemini",
        "models": {
            "orchestrator": "gemini-flash-lite-latest",
            "architect": "gemini-flash-lite-latest",
            "worker_high": "gemini-flash-lite-latest",
            "worker_medium": "gemini-flash-lite-latest",
            "worker_low": "gemini-flash-lite-latest",
            "reviewer": "gemini-flash-lite-latest",
        }
    },
    {
        "provider": "deepseek",
        "env_var": "DEEPSEEK_API_KEY",
        "pattern": re.compile(r"^sk-[a-f0-9]{32}$"),
        "name": "DeepSeek",
        "models": {
            "orchestrator": "deepseek/deepseek-chat",
            "architect": "deepseek/deepseek-reasoner",
            "worker_high": "deepseek/deepseek-chat",
            "worker_medium": "deepseek/deepseek-chat",
            "worker_low": "deepseek/deepseek-chat",
            "reviewer": "deepseek/deepseek-reasoner",
        }
    },
    {
        "provider": "groq",
        "env_var": "GROQ_API_KEY",
        "pattern": re.compile(r"^gsk_[a-zA-Z0-9]{40,}$"),
        "name": "Groq",
        "models": {
            "orchestrator": "groq/llama-3.3-70b-versatile",
            "architect": "groq/llama-3.3-70b-versatile",
            "worker_high": "groq/llama-3.3-70b-versatile",
            "worker_medium": "groq/llama-3.1-8b-instant",
            "worker_low": "groq/llama-3.1-8b-instant",
            "reviewer": "groq/llama-3.3-70b-versatile",
        }
    },
    {
        "provider": "xai",
        "env_var": "XAI_API_KEY",
        "pattern": re.compile(r"^xai-[a-zA-Z0-9]{40,}$"),
        "name": "xAI Grok",
        "models": {
            "orchestrator": "xai/grok-2",
            "architect": "xai/grok-2",
            "worker_high": "xai/grok-2",
            "worker_medium": "xai/grok-2-mini",
            "worker_low": "xai/grok-2-mini",
            "reviewer": "xai/grok-2",
        }
    },
]


class SmartKeyDetector:
    @staticmethod
    def detect_provider(key: str) -> Optional[Tuple[str, str, Dict[str, str]]]:
        """
        Inspects key string and identifies the provider, env var, and default recommended models.
        Returns (provider_id, env_var_name, models_dict) or None if unrecognized.
        """
        cleaned_key = key.strip()

        # Check local Ollama endpoint
        if "localhost:11434" in cleaned_key or "127.0.0.1:11434" in cleaned_key or cleaned_key.lower() == "ollama":
            return (
                "ollama",
                "OLLAMA_API_BASE",
                {
                    "orchestrator": "ollama/qwen2.5-coder:32b",
                    "architect": "ollama/qwen2.5-coder:32b",
                    "worker_high": "ollama/qwen2.5-coder:14b",
                    "worker_medium": "ollama/qwen2.5-coder:7b",
                    "worker_low": "ollama/qwen2.5-coder:7b",
                    "reviewer": "ollama/qwen2.5-coder:32b",
                }
            )

        for spec in PROVIDER_SIGNATURES:
            if spec["pattern"].match(cleaned_key):
                return (spec["provider"], spec["env_var"], spec["models"])

        # Fallback heuristic checks
        if cleaned_key.startswith("sk-ant-"):
            return ("anthropic", "ANTHROPIC_API_KEY", PROVIDER_SIGNATURES[0]["models"])
        elif cleaned_key.startswith("AIza") or cleaned_key.startswith("AQ."):
            return ("gemini", "GEMINI_API_KEY", PROVIDER_SIGNATURES[2]["models"])
        elif cleaned_key.startswith("gsk_"):
            return ("groq", "GROQ_API_KEY", PROVIDER_SIGNATURES[4]["models"])
        elif cleaned_key.startswith("xai-"):
            return ("xai", "XAI_API_KEY", PROVIDER_SIGNATURES[5]["models"])
        elif cleaned_key.startswith("sk-"):
            return ("openai", "OPENAI_API_KEY", PROVIDER_SIGNATURES[1]["models"])

        return None

    @staticmethod
    def auto_map_providers(available_keys: Dict[str, str], current_config: RamazanConfig) -> RamazanConfig:
        """
        Dynamically configures agents based on all currently available API keys.
        Multi-model optimal distribution:
        - Architect: Claude (Anthropic)
        - Worker: DeepSeek (DeepSeek)
        - Reviewer: Grok (xAI) or Claude
        Falls back smoothly to whichever providers are available.
        """
        has_anthropic = "anthropic" in available_keys or bool(os.environ.get("ANTHROPIC_API_KEY"))
        has_deepseek = "deepseek" in available_keys or bool(os.environ.get("DEEPSEEK_API_KEY"))
        has_xai = "xai" in available_keys or bool(os.environ.get("XAI_API_KEY"))
        has_openai = "openai" in available_keys or bool(os.environ.get("OPENAI_API_KEY"))
        has_gemini = "gemini" in available_keys or bool(os.environ.get("GEMINI_API_KEY"))
        has_groq = "groq" in available_keys or bool(os.environ.get("GROQ_API_KEY"))
        has_ollama = "ollama" in available_keys or bool(os.environ.get("OLLAMA_API_BASE"))

        # 1. Determine Architect & Orchestrator
        if has_anthropic:
            orch_model = ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.2)
            arch_model = ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.2)
        elif has_openai:
            orch_model = ModelConfig(model="gpt-4o", provider="openai", temperature=0.2)
            arch_model = ModelConfig(model="gpt-4o", provider="openai", temperature=0.2)
        elif has_gemini:
            orch_model = ModelConfig(model="gemini-flash-lite-latest", provider="gemini", temperature=0.2)
            arch_model = ModelConfig(model="gemini-flash-lite-latest", provider="gemini", temperature=0.2)
        elif has_deepseek:
            orch_model = ModelConfig(model="deepseek/deepseek-chat", provider="deepseek", temperature=0.2)
            arch_model = ModelConfig(model="deepseek/deepseek-reasoner", provider="deepseek", temperature=0.2)
        elif has_groq:
            orch_model = ModelConfig(model="groq/llama-3.3-70b-versatile", provider="groq", temperature=0.2)
            arch_model = ModelConfig(model="groq/llama-3.3-70b-versatile", provider="groq", temperature=0.2)
        elif has_ollama:
            orch_model = ModelConfig(model="ollama/qwen2.5-coder:32b", provider="ollama", temperature=0.2)
            arch_model = ModelConfig(model="ollama/qwen2.5-coder:32b", provider="ollama", temperature=0.2)
        else:
            orch_model = current_config.models.orchestrator
            arch_model = current_config.models.architect

        # 2. Determine Worker (Prefer DeepSeek for coding efficiency & cost)
        if has_deepseek:
            worker_low = ModelConfig(model="deepseek/deepseek-chat", provider="deepseek", temperature=0.2)
            worker_med = ModelConfig(model="deepseek/deepseek-chat", provider="deepseek", temperature=0.2)
            worker_high = ModelConfig(model="deepseek/deepseek-chat", provider="deepseek", temperature=0.2)
            worker_crit = ModelConfig(model="deepseek/deepseek-reasoner", provider="deepseek", temperature=0.1)
        elif has_gemini:
            worker_low = ModelConfig(model="gemini-flash-lite-latest", provider="gemini", temperature=0.2)
            worker_med = ModelConfig(model="gemini-flash-lite-latest", provider="gemini", temperature=0.2)
            worker_high = ModelConfig(model="gemini-flash-lite-latest", provider="gemini", temperature=0.2)
            worker_crit = ModelConfig(model="gemini-flash-lite-latest", provider="gemini", temperature=0.1)
        elif has_anthropic:
            worker_low = ModelConfig(model="claude-3-5-haiku-20241022", provider="anthropic", temperature=0.2)
            worker_med = ModelConfig(model="claude-3-5-haiku-20241022", provider="anthropic", temperature=0.2)
            worker_high = ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.2)
            worker_crit = ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.1)
        elif has_openai:
            worker_low = ModelConfig(model="gpt-4o-mini", provider="openai", temperature=0.2)
            worker_med = ModelConfig(model="gpt-4o-mini", provider="openai", temperature=0.2)
            worker_high = ModelConfig(model="gpt-4o", provider="openai", temperature=0.2)
            worker_crit = ModelConfig(model="gpt-4o", provider="openai", temperature=0.1)
        else:
            worker_low = current_config.models.worker.low
            worker_med = current_config.models.worker.medium
            worker_high = current_config.models.worker.high
            worker_crit = current_config.models.worker.critical

        # 3. Determine Reviewer (Prefer Grok if xAI is present, else Claude Sonnet / OpenAI)
        if has_xai:
            reviewer_model = ModelConfig(model="xai/grok-2", provider="xai", temperature=0.1)
        elif has_anthropic:
            reviewer_model = ModelConfig(model="claude-3-7-sonnet-20250219", provider="anthropic", temperature=0.1)
        elif has_openai:
            reviewer_model = ModelConfig(model="gpt-4o", provider="openai", temperature=0.1)
        elif has_gemini:
            reviewer_model = ModelConfig(model="gemini-flash-lite-latest", provider="gemini", temperature=0.1)
        elif has_deepseek:
            reviewer_model = ModelConfig(model="deepseek/deepseek-reasoner", provider="deepseek", temperature=0.1)
        else:
            reviewer_model = current_config.models.reviewer

        current_config.models.orchestrator = orch_model
        current_config.models.architect = arch_model
        current_config.models.worker = WorkerModels(
            low=worker_low,
            medium=worker_med,
            high=worker_high,
            critical=worker_crit
        )
        current_config.models.reviewer = reviewer_model
        return current_config
