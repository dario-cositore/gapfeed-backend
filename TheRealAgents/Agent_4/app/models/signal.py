"""
Signal data model.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Signal:
    """A single signal fetched from the database."""
    id: int = 0
    title: str = ''
    content: str = ''
    source_url: str = ''
    subreddit: str = ''
    pain_category: str = 'uncategorized'
    signal_type: Optional[str] = None
    urgency_score: float = 0.0
    specificity_score: float = 0.0
    buyer_intent: float = 0.0
    quality_tier: str = 'noise'
    product_category: str = ''
    source: str = ''
    author: str = ''
    
    @classmethod
    def from_dict(cls, d: dict) -> 'Signal':
        """Create Signal from a database dict."""
        return cls(
            id=d.get('id', 0),
            title=d.get('title', ''),
            content=d.get('content', ''),
            source_url=d.get('source_url', ''),
            subreddit=d.get('subreddit', ''),
            pain_category=d.get('pain_category', 'uncategorized') or 'uncategorized',
            signal_type=d.get('signal_type'),
            urgency_score=float(d.get('urgency_score', 0) or 0),
            specificity_score=float(d.get('specificity_score', 0) or 0),
            buyer_intent=float(d.get('buyer_intent', 0) or 0),
            quality_tier=d.get('quality_tier', 'noise') or 'noise',
            product_category=d.get('product_category', '') or '',
            source=d.get('source', ''),
            author=d.get('author', ''),
        )
