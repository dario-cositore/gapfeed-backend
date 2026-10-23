"""
Text preprocessing utilities.
"""

import re


def truncate_signal(text: str, max_len: int = 4000) -> str:
    """Truncate signal text to max_len, preserving word boundaries."""
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Try to cut at last sentence boundary
    last_period = truncated.rfind('.')
    last_newline = truncated.rfind('\n')
    cut_point = max(last_period, last_newline)
    if cut_point > max_len * 0.5:
        return truncated[:cut_point + 1]
    return truncated + '...'


def clean_text(text: str) -> str:
    """Clean text: strip HTML, normalize whitespace, remove markdown artifacts."""
    if not text:
        return ''
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove markdown links but keep text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove markdown headers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove markdown bold/italic
    text = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', text)
    # Remove reddit-style quote markers
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def truncate_for_llm(text: str, max_tokens_estimate: int = 3000) -> str:
    """Truncate text to roughly fit within token budget.
    
    Rule of thumb: 1 token ~ 4 chars for English.
    """
    max_chars = max_tokens_estimate * 4
    return truncate_signal(text, max_chars)
