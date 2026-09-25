import pytest
from ramazan.config import RamazanConfig
from ramazan.llm.key_detector import SmartKeyDetector


def test_detect_provider_prefixes():
    # Anthropic
    anth_key = "sk-ant-api03-123456789012345678901234"
    res_anth = SmartKeyDetector.detect_provider(anth_key)
    assert res_anth is not None
    assert res_anth[0] == "anthropic"

    # Gemini
    gem_key = "AIzaSyD-1234567890abcdef1234567890abcdef"
    res_gem = SmartKeyDetector.detect_provider(gem_key)
    assert res_gem is not None
    assert res_gem[0] == "gemini"

    # Groq
    groq_key = "gsk_1234567890abcdef1234567890abcdef12345678"
    res_groq = SmartKeyDetector.detect_provider(groq_key)
    assert res_groq is not None
    assert res_groq[0] == "groq"

    # Ollama
    res_ollama = SmartKeyDetector.detect_provider("http://localhost:11434")
    assert res_ollama is not None
    assert res_ollama[0] == "ollama"


def test_auto_mapping_gemini_only():
    config = RamazanConfig()
    updated = SmartKeyDetector.auto_map_providers(
        {"gemini": "AIzaSyD-1234567890abcdef1234567890abcdef"},
        config
    )
    assert updated.models.orchestrator.provider == "gemini"
    assert updated.models.worker.low.provider == "gemini"


def test_auto_mapping_multi_provider():
    config = RamazanConfig()
    updated = SmartKeyDetector.auto_map_providers(
        {
            "anthropic": "sk-ant-test",
            "deepseek": "sk-deepseek-test"
        },
        config
    )
    # Orchestrator & Reviewer should prefer strong Claude
    assert updated.models.orchestrator.provider == "anthropic"
    assert updated.models.reviewer.provider == "anthropic"
    # Worker should leverage fast DeepSeek
    assert updated.models.worker.medium.provider == "deepseek"
