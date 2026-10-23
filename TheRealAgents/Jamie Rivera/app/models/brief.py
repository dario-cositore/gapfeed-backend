"""
Brief data structure.
"""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Complaint:
    """A grouped complaint category with representative signal."""
    category: str
    avg_urgency: float
    sample: str
    sources: List[str]
    count: int
    url: str = ''


@dataclass
class Want:
    """A user want/need/request."""
    content: str
    source: str
    url: str = ''


@dataclass
class Brief:
    """Complete synthesis brief for a query."""
    query: str
    signal_count: int
    top_complaints: List[Complaint] = field(default_factory=list)
    top_wants: List[Want] = field(default_factory=list)
    summary: str = ''
    trend: str = 'stable'  # 'growing', 'stable', 'declining'
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON response."""
        return {
            'query': self.query,
            'signal_count': self.signal_count,
            'top_complaints': [c.__dict__ for c in self.top_complaints],
            'top_wants': [w.__dict__ for w in self.top_wants],
            'summary': self.summary,
            'trend': self.trend,
        }
