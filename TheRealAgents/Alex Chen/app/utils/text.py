"""Text utilities."""

import re


def truncate(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """Truncate text to max_length, breaking at word boundary."""
    if not text or len(text) <= max_length:
        return text
    truncated = text[:max_length - len(suffix)]
    # Break at last space
    last_space = truncated.rfind(' ')
    if last_space > max_length * 0.7:
        truncated = truncated[:last_space]
    return truncated + suffix


def clean_text(text: str) -> str:
    """Basic text cleanup: strip, normalize whitespace."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def word_count(text: str) -> int:
    """Count words in text."""
    if not text:
        return 0
    return len(text.split())
