"""
EnrichedProfile — the intelligence object.

A raw signal that has been enriched with extracted/inferred context.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class QualityLevel(str, Enum):
    CONFIRMED = "confirmed"    # User stated directly
    INFERRED = "inferred"      # Reasoned from context, high confidence
    GUESSED = "guessed"        # Estimated, lower confidence
    UNKNOWN = "unknown"        # No data


class ExtractionMethod(str, Enum):
    DIRECT = "direct"          # Stated by the user
    REGEX = "regex"            # Deterministic extraction
    RULE = "rule"              # Rule-based inference
    LLM = "llm"               # LLM reasoning
    HYBRID = "hybrid"          # Multiple methods combined


class FieldQuality(BaseModel):
    """Quality metadata for a single enriched field."""
    value: Optional[str] = None
    quality: QualityLevel = QualityLevel.UNKNOWN
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list, description="Evidence snippets from source")
    reasoning: Optional[str] = Field(None, description="Short explanation of inference")
    method: ExtractionMethod = ExtractionMethod.DIRECT


class EnrichedProfile(BaseModel):
    """Structured intelligence profile built from a raw signal."""

    profile_id: str = Field(..., description="Unique profile ID")
    raw_signal_id: str = Field(..., description="Source raw signal ID")
    event_id: Optional[str] = Field(None, description="Linked world event if applicable")

    # Core fields (always populated)
    pain_description: str = Field(..., min_length=10, description="What the person is struggling with")
    pain_category: str = Field(..., description="From controlled taxonomy")
    urgency: int = Field(..., ge=1, le=10, description="How urgent (1-10)")
    signal_type: str = Field(..., description="complaint, want, question, etc.")
    source_url: str = Field(..., description="Original source URL")

    # Enriched fields (with quality metadata)
    location: FieldQuality = Field(default_factory=FieldQuality)
    business_context: FieldQuality = Field(default_factory=FieldQuality)
    business_size: FieldQuality = Field(default_factory=FieldQuality)
    intent: FieldQuality = Field(default_factory=FieldQuality)

    # Personalization
    personalization_data: list[str] = Field(default_factory=list, description="Key details for outreach")

    # Scoring
    confidence: float = Field(0.0, ge=0.0, le=1.0, description="Overall profile confidence")
    actionability_score: float = Field(0.0, ge=0.0, le=1.0, description="How actionable")

    # Temporal
    first_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    freshness_hours: float = Field(0.0, ge=0.0, description="Hours since original post")
    is_spike_related: bool = False

    # Dedup
    dedupe_fingerprint: str = Field("", description="SHA256 for deduplication")
    cluster_id: Optional[str] = Field(None, description="Issue cluster if grouped")

    # Meta
    vertical: str = Field("general", description="Which vertical this belongs to")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    discard_reason: Optional[str] = Field(None, description="Why discarded, if applicable")

    @model_validator(mode='after')
    def validate_confidence_threshold(self):
        """Reject profiles below minimum confidence unless discarded with reason."""
        if self.confidence < 0.35 and not self.discard_reason:
            raise ValueError(f"Confidence {self.confidence} below 0.35 threshold. Provide discard_reason or improve enrichment.")
        return self

    @property
    def has_location(self) -> bool:
        return self.location.quality != QualityLevel.UNKNOWN and self.location.value is not None

    @property
    def enrichment_completeness(self) -> float:
        """What fraction of key fields are populated."""
        fields = [self.location, self.business_context, self.business_size, self.intent]
        filled = sum(1 for f in fields if f.quality != QualityLevel.UNKNOWN)
        return filled / len(fields)
