"""
Signal data model — wraps a raw DB row.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SignalView:
    """A signal as read from the database."""
    id: int = 0
    source: str = ''
    source_url: str = ''
    platform_id: str = ''
    subreddit: str = ''
    author: str = ''
    title: str = ''
    content: str = ''
    created_at: str = ''
    collected_at: str = ''
    vertical: str = 'general'
    product_category: str = ''
    pain_category: str = 'uncategorized'
    signal_type: Optional[str] = None
    location: Optional[str] = None
    urgency_score: float = 0.0
    specificity_score: float = 0.0
    buyer_intent: float = 0.0
    quality_tier: str = 'noise'
    sentiment: str = 'neutral'
    competitor_mentions: str = '[]'
    metadata: str = '{}'
    is_processed: int = 0
    synthesized: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> 'SignalView':
        """Create from a database row dict."""
        # Only pick fields we know about
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)

    @property
    def full_text(self) -> str:
        """Combine title and content for classification."""
        parts = []
        if self.title:
            parts.append(self.title)
        if self.content:
            parts.append(self.content)
        return '\n'.join(parts)

    @property
    def text_length(self) -> int:
        return len(self.full_text)
