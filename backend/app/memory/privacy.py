from __future__ import annotations

import re

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Gap #5: Sensitive data patterns (India-focused + general)
SENSITIVE_PATTERNS = [
    (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "Aadhaar number"),
    (r"\b[A-Z]{5}\d{4}[A-Z]\b", "PAN card"),
    (r"\b\d{10}\b", "Phone number"),
    (r"password\s*[:=]\s*\S+", "Password"),
    (r"secret\s*[:=]\s*\S+", "Secret"),
    (r"api[_-]?key\s*[:=]\s*\S+", "API key"),
    (r"\b\d{16}\b", "Card number"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
]


def contains_sensitive_data(text: str) -> tuple[bool, list[str]]:
    """Check if text contains sensitive data patterns.

    Returns:
        (has_sensitive, list of detected pattern types)
    """
    detected = []
    for pattern, name in SENSITIVE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            detected.append(name)

    if detected:
        logger.warning("sensitive_data_detected", types=detected)

    return bool(detected), detected


def redact_sensitive_data(text: str) -> str:
    """Replace sensitive data with [REDACTED] markers."""
    redacted = text
    for pattern, name in SENSITIVE_PATTERNS:
        redacted = re.sub(pattern, f"[REDACTED {name}]", redacted, flags=re.IGNORECASE)
    return redacted


def is_forget_command(text: str) -> tuple[bool, str]:
    """Check if the message is a 'forget' command.

    Returns:
        (is_forget, what_to_forget)

    Examples:
        "forget my password" → (True, "password")
        "forget my Aadhaar number" → (True, "Aadhaar number")
        "forget everything about Infosys" → (True, "Infosys")
    """
    lower = text.lower().strip()

    forget_patterns = [
        r"^forget\s+(?:my\s+)?(.+)$",
        r"^delete\s+(?:my\s+)?(.+?)(?:\s+from\s+memory)?$",
        r"^remove\s+(?:my\s+)?(.+?)(?:\s+from\s+memory)?$",
    ]

    for pattern in forget_patterns:
        match = re.match(pattern, lower)
        if match:
            return True, match.group(1).strip()

    return False, ""
