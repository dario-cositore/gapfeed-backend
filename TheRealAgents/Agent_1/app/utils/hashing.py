"""Hashing utilities."""

import hashlib


def short_hash(text: str, length: int = 12) -> str:
    """Short hash for IDs and fingerprints."""
    return hashlib.sha256(text.encode()).hexdigest()[:length]


def content_hash(text: str) -> str:
    """Content-only hash (normalized text)."""
    normalized = text.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def fingerprint_hash(*parts: str) -> str:
    """Combined fingerprint from multiple parts."""
    combined = "|".join(p.lower().strip() for p in parts if p)
    return hashlib.sha256(combined.encode()).hexdigest()
