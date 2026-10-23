"""
Utility functions for Alex Chen.
"""

from .hashing import short_hash, content_hash, fingerprint_hash
from .time import now_iso, parse_timestamp, time_ago
from .text import truncate, clean_text, word_count
from .rate_limit import RateLimiter, with_backoff
