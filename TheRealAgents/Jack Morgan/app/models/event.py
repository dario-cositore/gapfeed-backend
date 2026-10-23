"""
WorldEvent — something happening in the world that may create pain.

Examples:
- Shopify policy change
- Stripe outage
- Tax filing deadline
- Visa deadline
- Layoffs at a big SaaS company
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    OUTAGE = "outage"
    POLICY_CHANGE = "policy_change"
    PRICING_CHANGE = "pricing_change"
    LAYOFF = "layoff"
    REGULATION = "regulation"
    DEADLINE = "deadline"
    PRODUCT_LAUNCH = "product_launch"
    SECURITY_BREACH = "security_breach"
    VIRAL_COMPLAINT = "viral_complaint"
    SEASONAL = "seasonal"
    OTHER = "other"


class EventStatus(str, Enum):
    ACTIVE = "active"
    FADING = "fading"
    RESOLVED = "resolved"


class WorldEvent(BaseModel):
    """A world event that may be creating pain signals."""

    event_id: str = Field(..., description="Unique event identifier (e.g., evt_2026_03_26_shopify_payments)")
    title: str = Field(..., description="Human-readable event title")
    event_type: EventType = Field(..., description="Category of event")
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    time_window_start: Optional[datetime] = Field(None, description="When the event impact started")
    time_window_end: Optional[datetime] = Field(None, description="When the event impact is expected to end")
    impacted_segments: list[str] = Field(default_factory=list, description="Who is affected (e.g., shopify_merchants)")
    evidence_urls: list[str] = Field(default_factory=list, description="URLs confirming this event")
    severity: float = Field(0.0, ge=0.0, le=1.0, description="How severe (0-1)")
    novelty: float = Field(0.0, ge=0.0, le=1.0, description="How new/unusual (0-1)")
    status: EventStatus = Field(EventStatus.ACTIVE)
    metadata: dict = Field(default_factory=dict, description="Extra context")
