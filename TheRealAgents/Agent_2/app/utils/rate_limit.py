"""Rate limiting and backoff utilities."""

import time
import logging
import functools
from typing import Callable, Any

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, max_calls: int, period_seconds: float = 60.0):
        self.max_calls = max_calls
        self.period = period_seconds
        self.calls = []

    def acquire(self) -> bool:
        """Try to acquire a token. Returns True if allowed, False if rate limited."""
        now = time.time()

        # Clean old calls
        self.calls = [t for t in self.calls if now - t < self.period]

        if len(self.calls) >= self.max_calls:
            return False

        self.calls.append(now)
        return True

    def wait_time(self) -> float:
        """How long until a token is available."""
        if not self.calls:
            return 0.0

        now = time.time()
        oldest = min(self.calls)
        wait = self.period - (now - oldest)
        return max(0.0, wait)

    def acquire_or_wait(self):
        """Acquire a token, waiting if necessary."""
        while not self.acquire():
            wait = self.wait_time()
            if wait > 0:
                logger.debug(f"Rate limited, waiting {wait:.1f}s")
                time.sleep(min(wait, 5.0))


def with_backoff(max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, retry_on: tuple = None):
    """
    Decorator for exponential backoff on function calls.

    Args:
        max_retries: Max number of retries
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        retry_on: Tuple of exception types to retry on (default: Exception)
    """
    if retry_on is None:
        retry_on = (Exception,)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"{func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise

                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s")
                    time.sleep(delay)

            raise last_exception

        return wrapper
    return decorator
