"""Time utilities."""

from datetime import datetime, timezone, timedelta
from typing import Optional


def now_iso() -> str:
    """Current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(ts: str) -> Optional[datetime]:
    """Parse various timestamp formats to datetime."""
    if not ts:
        return None

    # ISO format
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        pass

    # Unix timestamp
    try:
        ts_float = float(ts)
        if ts_float > 1e12:
            ts_float /= 1000
        return datetime.fromtimestamp(ts_float, tz=timezone.utc)
    except (ValueError, OSError):
        pass

    return None


def time_ago(dt: datetime) -> str:
    """Human-readable time ago string."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    delta = now - dt

    if delta < timedelta(minutes=1):
        return "just now"
    elif delta < timedelta(hours=1):
        mins = int(delta.total_seconds() / 60)
        return f"{mins}m ago"
    elif delta < timedelta(days=1):
        hours = int(delta.total_seconds() / 3600)
        return f"{hours}h ago"
    elif delta < timedelta(days=30):
        days = delta.days
        return f"{days}d ago"
    else:
        months = delta.days // 30
        return f"{months}mo ago"
