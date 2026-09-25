"""
Security validations: secret leak checks and command safety.
Conforms to Sections 28 & 38 of specification.
"""

import re
from typing import List, Tuple

# Patterns that indicate potentially leaked secrets or credentials
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|bearer[_-]?token)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI style
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),   # GitHub Personal Access Token
    re.compile(r"xox[baprs]-[a-zA-Z0-9]{10,}"), # Slack token
    re.compile(r"AIza[0-9A-Za-z-_]{35}"), # Google API Key
]


class SecurityAuditor:
    @staticmethod
    def scan_for_secrets(content: str) -> List[str]:
        findings = []
        for pattern in SECRET_PATTERNS:
            matches = pattern.findall(content)
            if matches:
                findings.append(f"Potential secret detected matching pattern: {pattern.pattern}")
        return findings

    @staticmethod
    def sanitize_content(content: str) -> str:
        sanitized = content
        for pattern in SECRET_PATTERNS:
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized
