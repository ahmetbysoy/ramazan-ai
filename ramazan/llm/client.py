"""
LLM Client with LiteLLM integration and robust Mock/Fallback support.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from ramazan.llm.errors import ConfigurationError, ModelCallError, is_retriable_error

logger = logging.getLogger("ramazan.llm")

_last_gemini_call = 0.0


def _throttle_gemini():
    global _last_gemini_call
    import time
    elapsed = time.time() - _last_gemini_call
    if elapsed < 4.0:
        time.sleep(4.0 - elapsed)
    _last_gemini_call = time.time()


class LLMResponse(BaseModel):
    content: str = ""
    model: str
    inputTokens: int = 0
    outputTokens: int = 0
    tool_calls: Optional[List[Dict[str, Any]]] = None
    raw: Optional[Dict[str, Any]] = None


def _auto_load_env_keys():
    """Load API keys from local or home directory .env files if not set in os.environ."""
    candidates = [
        Path.cwd() / ".ramazan" / ".env",
        Path.cwd() / ".env",
        Path.home() / ".ramazan" / ".env",
        Path.home() / ".env",
    ]
    for p in candidates:
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("'\"")
                        if k and v and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass


class LLMClient:
    def __init__(self, use_mock: Optional[bool] = None):
        _auto_load_env_keys()
        has_keys = bool(
            os.environ.get("ANTHROPIC_API_KEY") or
            os.environ.get("OPENAI_API_KEY") or
            os.environ.get("GEMINI_API_KEY") or
            os.environ.get("DEEPSEEK_API_KEY") or
            os.environ.get("XAI_API_KEY")
        )
        if use_mock is not None:
            self.use_mock = use_mock
        elif os.environ.get("RAMAZAN_MOCK") in ["1", "true", "True"]:
            self.use_mock = True
        else:
            self.use_mock = not has_keys

    def generate(self, model: str, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.2) -> LLMResponse:
        if self.use_mock:
            return self._generate_mock(model, prompt, system_prompt)

        try:
            import litellm

            litellm_model = model
            if (litellm_model.startswith("gemini-") or "gemini" in litellm_model) and not litellm_model.startswith("gemini/"):
                litellm_model = f"gemini/{litellm_model}"

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            candidate_models = [litellm_model]
            if "gemini" in litellm_model:
                _throttle_gemini()
                for alt in ["gemini/gemini-flash-lite-latest", "gemini/gemini-3.5-flash-lite", "gemini/gemini-3.6-flash"]:
                    if alt not in candidate_models:
                        candidate_models.append(alt)

            last_err = None
            for cur_model in candidate_models:
                try:
                    if "gemini" in cur_model:
                        _throttle_gemini()
                    resp = litellm.completion(
                        model=cur_model,
                        messages=messages,
                        temperature=temperature,
                    )

                    content = resp.choices[0].message.content or ""
                    if not isinstance(content, str):
                        content = str(content)
                    usage = getattr(resp, "usage", None)
                    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
                    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0

                    return LLMResponse(
                        content=content,
                        model=cur_model,
                        inputTokens=in_tok,
                        outputTokens=out_tok,
                    )
                except Exception as e:
                    last_err = e
                    err_msg = str(e).lower()
                    if any(token in err_msg for token in ["503", "unavailable", "demand", "429", "resource_exhausted", "quota", "ratelimit"]):
                        logger.warning(f"Model {cur_model} throttled or busy ({e}), trying alternate candidate...")
                        continue
                    raise e

            if last_err:
                raise last_err
        except Exception as e:
            logger.error(f"LiteLLM call failed for {model}: {e}")
            raise ModelCallError(model=model, original_error=e, retriable=is_retriable_error(e)) from e

    def generate_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.2,
    ) -> LLMResponse:
        """
        Executes a turn with tools using LiteLLM.
        Returns LLMResponse containing content and any tool_calls.
        """
        if self.use_mock:
            return self._generate_mock_with_tools(model, messages, tools)

        try:
            import litellm

            litellm_model = model
            if (litellm_model.startswith("gemini-") or "gemini" in litellm_model) and not litellm_model.startswith("gemini/"):
                litellm_model = f"gemini/{litellm_model}"

            kwargs: Dict[str, Any] = {
                "model": litellm_model,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools

            import time
            max_attempts = 3
            resp = None
            for attempt in range(max_attempts):
                try:
                    if "gemini" in litellm_model:
                        _throttle_gemini()
                    resp = litellm.completion(**kwargs)
                    break
                except Exception as e:
                    err_msg = str(e).lower()
                    if any(t in err_msg for t in ["429", "resource_exhausted", "quota", "rate limit"]) and attempt < max_attempts - 1:
                        logger.warning(f"Rate limited by Gemini on turn, waiting 20s before retry (attempt {attempt+1}/{max_attempts})...")
                        time.sleep(20)
                        continue
                    raise e

            choice = resp.choices[0]
            msg = choice.message
            content = msg.content or ""
            if not isinstance(content, str):
                content = str(content)

            tool_calls_data = None
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls_data = []
                for tc in msg.tool_calls:
                    if hasattr(tc, "model_dump"):
                        tool_calls_data.append(tc.model_dump())
                    elif isinstance(tc, dict):
                        tool_calls_data.append(tc)
                    else:
                        tool_calls_data.append({
                            "id": getattr(tc, "id", "call_1"),
                            "type": "function",
                            "function": {
                                "name": getattr(tc.function, "name", ""),
                                "arguments": getattr(tc.function, "arguments", "{}")
                            }
                        })

            usage = getattr(resp, "usage", None)
            in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
            out_tok = getattr(usage, "completion_tokens", 0) if usage else 0

            return LLMResponse(
                content=content,
                model=litellm_model,
                inputTokens=in_tok,
                outputTokens=out_tok,
                tool_calls=tool_calls_data,
            )
        except Exception as e:
            logger.error(f"LiteLLM tool completion failed for {model}: {e}")
            raise ModelCallError(model=model, original_error=e, retriable=is_retriable_error(e)) from e

    def _generate_mock_with_tools(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """
        Mock responder for multi-turn tool calling.
        """
        system_prompt = None
        user_prompt = ""
        for m in messages:
            if m.get("role") == "system":
                system_prompt = m.get("content")
            elif m.get("role") == "user":
                user_prompt = m.get("content", "")

        return self._generate_mock(model, user_prompt, system_prompt)

    def _generate_mock(self, model: str, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Deterministic mock responder for testing and bootstrapping without live API credentials.
        Extracts requirements from prompt and provides appropriate structured responses.
        """
        # 1. Reviewer Prompt Detection
        if "expert code reviewer" in prompt or "ROLE: You are an expert code reviewer" in (system_prompt or ""):
            if "FAIL" in prompt or ("error" in prompt.lower() and "zero division" in prompt.lower()):
                content = json.dumps({
                    "status": "CHANGES_REQUIRED",
                    "severity": "HIGH",
                    "summary": "Detected potential unhandled zero division and missing test assertions.",
                    "issues": [
                        {
                            "file": "src/calculator.py",
                            "line": 14,
                            "category": "edge_cases",
                            "description": "Division by zero is not handled properly.",
                            "requiredFix": "Add check for denominator == 0 and raise ZeroDivisionError with explicit message."
                        }
                    ]
                }, indent=2)
            else:
                content = json.dumps({
                    "status": "APPROVED",
                    "severity": "LOW",
                    "summary": "Code satisfies acceptance criteria, passes automated tests, and adheres to architecture.",
                    "issues": []
                }, indent=2)

        # 2. Planning & Orchestrator Breakdown Detection
        elif "TASK SCHEMA REQUIREMENTS" in prompt or "Break down the following requirements" in prompt or (system_prompt and "Chief Software Engineering Orchestrator" in system_prompt):
            content = json.dumps([
                {
                    "id": "TASK-001",
                    "title": "Core Domain Models and Schema Validation",
                    "description": "Implement baseline domain data structures and input validation logic.",
                    "type": "implementation",
                    "priority": "high",
                    "complexity": "low",
                    "dependencies": [],
                    "files": ["src/domain/models.py"],
                    "acceptanceCriteria": [
                        "Domain model defined with attributes.",
                        "Validation methods implemented.",
                        "Unit tests verify valid and invalid inputs."
                    ]
                },
                {
                    "id": "TASK-002",
                    "title": "Business Service Layer and Repository Interface",
                    "description": "Implement business service logic and repository abstractions.",
                    "type": "implementation",
                    "priority": "high",
                    "complexity": "medium",
                    "dependencies": ["TASK-001"],
                    "files": ["src/domain/service.py"],
                    "acceptanceCriteria": [
                        "Service operations implemented.",
                        "Repository interfaces defined.",
                        "Unit tests pass with 100% assertions."
                    ]
                },
                {
                    "id": "TASK-003",
                    "title": "Public API Controller and Health Verification",
                    "description": "Expose public interface endpoints and health check diagnostics.",
                    "type": "implementation",
                    "priority": "medium",
                    "complexity": "low",
                    "dependencies": ["TASK-002"],
                    "files": ["src/domain/api.py"],
                    "acceptanceCriteria": [
                        "Health check diagnostic route operational.",
                        "Service endpoints respond with valid JSON.",
                        "Integration tests pass."
                    ]
                }
            ], indent=2)

        # If Worker prompt
        elif "REQUIRED OUTPUT FORMAT" in prompt and "fileModifications" in prompt:
            # Generate genuine code based on task files mentioned in prompt
            file_mods = []
            test_mods = []

            # Check if prompt specifies explicit target files
            files_found = re.findall(r"### File:\s*([^\n\r]+)", prompt)
            if not files_found:
                m = re.search(r"target files:\s*([^\n\r.]+)", prompt)
                if m and m.group(1).strip():
                    files_found = [f.strip() for f in m.group(1).split(",") if f.strip() and f.strip() != "Specified in task"]

            if files_found and not any(f in ["src/domain/models.py", "src/domain/service.py", "src/domain/api.py"] for f in files_found):
                for f in files_found:
                    file_mods.append({
                        "path": f,
                        "content": f'"""Module {f}"""\n\ndef run():\n    return True\n'
                    })
                safe_name = files_found[0].replace("/", "_").replace(".py", "")
                test_mods = [{
                    "path": f"tests/test_{safe_name}.py",
                    "content": f"import pytest\n\ndef test_{safe_name}():\n    assert True\n"
                }]
            elif "src/domain/models.py" in prompt or "TASK-001" in prompt:
                file_mods.append({
                    "path": "src/domain/models.py",
                    "content": '''"""Core Domain Models"""
from typing import Optional
from pydantic import BaseModel, Field

class EntityModel(BaseModel):
    id: str = Field(description="Unique entity identifier")
    name: str = Field(description="Entity name")
    status: str = Field(default="ACTIVE")
    metadata: dict = Field(default_factory=dict)

    def is_active(self) -> bool:
        return self.status == "ACTIVE"
'''
                })
                test_mods.append({
                    "path": "tests/test_domain_models.py",
                    "content": '''import pytest
from src.domain.models import EntityModel

def test_entity_model_creation():
    entity = EntityModel(id="E-001", name="Test Entity")
    assert entity.id == "E-001"
    assert entity.is_active() is True
    assert entity.status == "ACTIVE"

def test_entity_inactive():
    entity = EntityModel(id="E-002", name="Inactive", status="ARCHIVED")
    assert entity.is_active() is False
'''
                })

            elif "src/domain/service.py" in prompt or "TASK-002" in prompt:
                file_mods.append({
                    "path": "src/domain/service.py",
                    "content": '''"""Business Service Layer"""
from typing import Dict, List, Optional
from src.domain.models import EntityModel

class EntityService:
    def __init__(self):
        self._store: Dict[str, EntityModel] = {}

    def register_entity(self, entity: EntityModel) -> EntityModel:
        self._store[entity.id] = entity
        return entity

    def get_entity(self, entity_id: str) -> Optional[EntityModel]:
        return self._store.get(entity_id)

    def list_active(self) -> List[EntityModel]:
        return [e for e in self._store.values() if e.is_active()]
'''
                })
                test_mods.append({
                    "path": "tests/test_domain_service.py",
                    "content": '''import pytest
from src.domain.models import EntityModel
from src.domain.service import EntityService

def test_service_crud():
    svc = EntityService()
    entity = EntityModel(id="E-100", name="Service Entity")
    svc.register_entity(entity)
    retrieved = svc.get_entity("E-100")
    assert retrieved is not None
    assert retrieved.name == "Service Entity"
    assert len(svc.list_active()) == 1
'''
                })

            elif "src/domain/api.py" in prompt or "TASK-003" in prompt:
                file_mods.append({
                    "path": "src/domain/api.py",
                    "content": '''"""Public API Gateway"""
from src.domain.service import EntityService

class AppGateway:
    def __init__(self):
        self.service = EntityService()

    def health_check(self) -> dict:
        return {"status": "HEALTHY", "service": "ramazan_engine", "version": "1.0.0"}
'''
                })
                test_mods.append({
                    "path": "tests/test_domain_api.py",
                    "content": '''import pytest
from src.domain.api import AppGateway

def test_health_check():
    gw = AppGateway()
    status = gw.health_check()
    assert status["status"] == "HEALTHY"
    assert "version" in status
'''
                })

            content = json.dumps({
                "explanation": "Implemented domain components with 100% test coverage and architecture compliance.",
                "fileModifications": file_mods,
                "tests": test_mods,
                "potentialRisks": "None identified."
            }, indent=2)
        else:
            content = json.dumps({"status": "SUCCESS", "message": "Simulated output."})

        return LLMResponse(
            content=content,
            model=model,
            inputTokens=len(prompt) // 4,
            outputTokens=len(content) // 4
        )
