"""
Rate limiting utilities.
"""

import time


class TokenBucket:
    """Simple token bucket rate limiter."""

    def __init__(self, max_tokens: int, refill_rate: float):
        """
        Args:
            max_tokens: Maximum tokens in the bucket.
            refill_rate: Tokens added per second.
        """
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.tokens = float(max_tokens)
        self.last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def wait_for(self, tokens: int = 1) -> float:
        """Return seconds to wait before tokens are available."""
        self._refill()
        if self.tokens >= tokens:
            return 0.0
        deficit = tokens - self.tokens
        return deficit / self.refill_rate


class RateLimiter:
    """Track calls per time window."""

    def __init__(self, max_calls: int, window_seconds: int = 3600):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls: list[float] = []

    def _prune(self):
        cutoff = time.monotonic() - self.window
        self.calls = [t for t in self.calls if t > cutoff]

    def can_call(self) -> bool:
        self._prune()
        return len(self.calls) < self.max_calls

    def record(self):
        self.calls.append(time.monotonic())

    def remaining(self) -> int:
        self._prune()
        return max(0, self.max_calls - len(self.calls))
