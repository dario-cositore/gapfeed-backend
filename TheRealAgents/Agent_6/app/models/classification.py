"""
Classification result data model.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional


QUALITY_TIERS = ['noise', 'bronze', 'silver', 'gold']
SIGNAL_TYPES = ['complaint', 'question', 'review', 'discussion', 'recommendation']
SENTIMENTS = ['negative', 'neutral', 'positive']


@dataclass
class ClassificationResult:
    """Result of classifying a single signal."""
    signal_id: int = 0
    pain_category: str = 'uncategorized'
    urgency_score: float = 0.0
    specificity_score: float = 0.0
    buyer_intent: float = 0.0
    quality_tier: str = 'noise'
    sentiment: str = 'neutral'
    signal_type: str = 'discussion'
    location: Optional[str] = None
    product_category: Optional[str] = None
    competitor_mentions: list = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ''
    llm_used: bool = False
    pre_classification: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dict suitable for database update."""
        d = asdict(self)
        # Remove internal-only fields
        d.pop('reasoning', None)
        d.pop('llm_used', None)
        d.pop('pre_classification', None)
        d.pop('confidence', None)
        return d

    def to_db_update(self) -> dict:
        """Convert to dict matching RemoteDB update_signal() kwargs."""
        import json
        return {
            'pain_category': self.pain_category,
            'urgency_score': self.urgency_score,
            'specificity_score': self.specificity_score,
            'buyer_intent': self.buyer_intent,
            'quality_tier': self.quality_tier,
            'sentiment': self.sentiment,
            'signal_type': self.signal_type,
            'location': self.location or '',
            'product_category': self.product_category or '',
            'competitor_mentions': json.dumps(self.competitor_mentions),
            'is_processed': 1,
        }

    @property
    def is_noise(self) -> bool:
        return self.quality_tier == 'noise'

    @property
    def is_actionable(self) -> bool:
        return self.quality_tier in ('gold', 'silver')
