"""
RawSignal — one complaint/question/post/review/comment from the internet.

Before enrichment. This is the raw material Alex collects.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"
    WEB_SEARCH = "web_search"
    RSS = "rss"
    TWITTER = "twitter"
    FORUM = "forum"
    REVIEW = "review"
    OTHER = "other"


class SignalStatus(str, Enum):
    CANDIDATE = "candidate"       # Raw, not yet processed
    ENRICHED = "enriched"         # Enrichment attempted
    STORED = "stored"             # Profile created and stored
    DISCARDED = "discarded"       # Failed quality/compliance check
    DUPLICATE = "duplicate"       # Already seen this signal


class RawSignal(BaseModel):
    """One raw signal from the internet."""

    raw_signal_id: str = Field(..., description="Unique ID (e.g., sig_reddit_t3_abc123)")
    source_type: SourceType = Field(..., description="Where it came from")
    source_subtype: Optional[str] = Field(None, description="post, comment, review, article, etc.")
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    author_handle: Optional[str] = Field(None, description="Username/handle if available")
    source_url: str = Field(..., description="Link to original content")
    title: Optional[str] = Field(None, description="Post/article title")
    body: str = Field("", description="The actual content")
    created_at: Optional[datetime] = Field(None, description="When the original content was posted")
    platform_metadata: dict = Field(default_factory=dict, description="Subreddit, score, comments, etc.")
    language: str = Field("en", description="Detected language")
    geo_hint: Optional[str] = Field(None, description="Location hint from platform (e.g., subreddit implies country)")
    product_mentions: list[str] = Field(default_factory=list, description="Products/brands mentioned")
    money_mentions: list[float] = Field(default_factory=list, description="Dollar amounts found")
    status: SignalStatus = Field(SignalStatus.CANDIDATE)

    @property
    def text(self) -> str:
        """Combined title + body for processing."""
        parts = [p for p in [self.title, self.body] if p]
        return "\n".join(parts)

    @property
    def fingerprint(self) -> str:
        """Dedup fingerprint."""
        import hashlib
        normalized_url = self.source_url.lower().strip()
        text_chunk = self.text[:500].lower().strip()
        author = (self.author_handle or "anon").lower()
        time_bucket = self.created_at.strftime("%Y-%m-%d%H") if self.created_at else "unknown"
        raw = f"{normalized_url}|{text_chunk}|{author}|{time_bucket}"
        return hashlib.sha256(raw.encode()).hexdigest()
