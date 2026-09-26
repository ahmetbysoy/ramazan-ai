"""
LLM Exception Hierarchy for RAMAZAN AI.
Ensures accurate failure semantics without silent mock fallback.
"""

from typing import Optional


class ModelCallError(Exception):
    """Raised when an LLM provider call fails."""

    def __init__(
        self,
        model: str,
        original_error: Exception,
        retriable: bool = False,
        message: Optional[str] = None,
    ):
        self.model = model
        self.original_error = original_error
        self.retriable = retriable
        msg = message or f"Model call failed for '{model}' (retriable={retriable}): {original_error}"
        super().__init__(msg)


class ConfigurationError(Exception):
    """Raised when required API credentials or configurations are missing."""
    pass


def is_retriable_error(e: Exception) -> bool:
    """Determine whether an LLM error is temporary / retriable."""
    err_str = str(e).lower()
    retriable_tokens = [
        "429",
        "500",
        "502",
        "503",
        "504",
        "rate limit",
        "ratelimit",
        "resource_exhausted",
        "resource exhausted",
        "resourceexhausted",
        "quota",
        "temporarily unavailable",
        "timeout",
        "timed out",
        "overloaded",
        "connection reset",
        "service unavailable",
        "deadline exceeded",
    ]
    return any(token in err_str for token in retriable_tokens)
