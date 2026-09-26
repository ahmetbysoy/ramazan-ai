"""
Unit tests for Provider Role Distribution and Configuration (FAZ 2.3).
"""

from ramazan.config import RamazanConfig
from ramazan.llm.key_detector import SmartKeyDetector


def test_smart_key_detector_triad_mapping():
    """
    Test user triad rule: Architect = Claude, Worker = DeepSeek, Reviewer = Grok.
    """
    keys = {
        "anthropic": "mock-anthropic-key",
        "deepseek": "mock-deepseek-key",
        "xai": "mock-xai-key"
    }

    config = RamazanConfig()
    mapped = SmartKeyDetector.auto_map_providers(keys, config)

    # Architect -> Claude
    assert "claude" in mapped.models.architect.model.lower()
    assert mapped.models.architect.provider == "anthropic"

    # Worker -> DeepSeek
    assert "deepseek" in mapped.models.worker.high.model.lower()
    assert mapped.models.worker.high.provider == "deepseek"

    # Reviewer -> Grok
    assert "grok" in mapped.models.reviewer.model.lower()
    assert mapped.models.reviewer.provider == "xai"


def test_smart_key_detector_fallback_when_partial_keys():
    """
    If only DeepSeek and Gemini are present, Worker uses DeepSeek and Reviewer/Architect use Gemini.
    """
    keys = {
        "deepseek": "mock-deepseek-key",
        "gemini": "mock-gemini-key"
    }

    config = RamazanConfig()
    mapped = SmartKeyDetector.auto_map_providers(keys, config)

    assert "deepseek" in mapped.models.worker.high.model.lower()
    assert "gemini" in mapped.models.architect.model.lower()
    assert "gemini" in mapped.models.reviewer.model.lower()
