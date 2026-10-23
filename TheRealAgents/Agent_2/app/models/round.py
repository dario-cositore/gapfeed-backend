"""
Round — one execution cycle with metrics and notes.

Every time Alex runs through the state machine, a Round is persisted.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RoundStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class Round(BaseModel):
    """One execution cycle."""

    round_id: str = Field(..., description="Unique round ID (e.g., round_2026_03_26_014)")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = Field(None)
    trigger: str = Field("scheduled", description="What triggered this round")
    status: RoundStatus = Field(RoundStatus.RUNNING)

    # Event metrics
    active_events: int = Field(0, description="World events detected this round")
    sources_scanned: list[str] = Field(default_factory=list)

    # Signal metrics
    raw_signals_found: int = Field(0)
    profiles_stored: int = Field(0)
    profiles_discarded: int = Field(0)
    profiles_duplicate: int = Field(0)

    # Quality metrics
    avg_confidence: float = Field(0.0, ge=0.0, le=1.0)
    avg_actionability: float = Field(0.0, ge=0.0, le=1.0)

    # Budget metrics
    llm_calls_made: int = Field(0)
    source_calls_made: int = Field(0)

    # File references
    notes_path: Optional[str] = Field(None, description="Path to journal entry")
    plan_path: Optional[str] = Field(None, description="Path to plan file")
    checkpoint_path: Optional[str] = Field(None, description="Path to checkpoint file")

    # Error tracking
    errors: list[str] = Field(default_factory=list)
    error_stage: Optional[str] = Field(None, description="Which stage failed, if any")
