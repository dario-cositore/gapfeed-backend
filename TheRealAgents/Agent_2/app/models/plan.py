"""
Plan — Alex's structured scouting plan for a round.

Generated from reasoning, stored both as structured JSON and rendered as markdown.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class PlanTarget(BaseModel):
    """A specific source to scout."""
    source_key: str = Field(..., description="e.g., reddit:r/shopify, web:'stripe froze account'")
    priority: float = Field(1.0, ge=0.0, description="Relative priority (higher = scan first)")
    reason: Optional[str] = Field(None, description="Why this target was chosen")


class PlanEnrichmentFocus(BaseModel):
    """What to focus on during enrichment this round."""
    fields: list[str] = Field(
        default_factory=lambda: ["location", "business_context", "business_size", "intent"],
        description="Which enrichment fields to prioritize"
    )
    extraction_methods: list[str] = Field(
        default_factory=lambda: ["regex", "rules", "llm"],
        description="Which extraction methods to use"
    )


class StopConditions(BaseModel):
    """When to stop this round."""
    max_raw_signals: int = Field(60, description="Stop after collecting this many raw signals")
    max_llm_calls: int = Field(15, description="LLM budget for this round")
    min_marginal_yield: float = Field(0.08, description="Stop if new signals per minute drops below this")
    max_round_minutes: int = Field(15, description="Hard time limit per round")


class Plan(BaseModel):
    """Alex's scouting plan for this round."""

    round_id: str = Field(..., description="Which round this plan belongs to")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # What's happening
    reasoning: str = Field("", description="Alex's natural language reasoning for this plan")
    top_events: list[dict] = Field(default_factory=list, description="Event IDs + priorities")
    target_segments: list[str] = Field(default_factory=list, description="Who to look for")

    # Where to look
    targets: list[PlanTarget] = Field(default_factory=list, description="Sources to scout")

    # How to enrich
    enrichment_focus: PlanEnrichmentFocus = Field(default_factory=PlanEnrichmentFocus)

    # When to stop
    stop_conditions: StopConditions = Field(default_factory=StopConditions)

    def to_markdown(self) -> str:
        """Render plan as human-readable markdown for memory/plan.md."""
        lines = [
            f"# Plan — {self.created_at.strftime('%B %d, %Y')} (Round {self.round_id})",
            "",
            "## Reasoning",
            self.reasoning or "No reasoning provided.",
            "",
            "## Targets",
        ]
        for t in sorted(self.targets, key=lambda x: x.priority, reverse=True):
            reason = f" — {t.reason}" if t.reason else ""
            lines.append(f"- [{t.priority:.1f}] `{t.source_key}`{reason}")

        lines.extend([
            "",
            "## Enrichment Focus",
            f"- Fields: {', '.join(self.enrichment_focus.fields)}",
            f"- Methods: {', '.join(self.enrichment_focus.extraction_methods)}",
            "",
            "## Stop Conditions",
            f"- Max signals: {self.stop_conditions.max_raw_signals}",
            f"- Max LLM calls: {self.stop_conditions.max_llm_calls}",
            f"- Max time: {self.stop_conditions.max_round_minutes} min",
        ])
        return "\n".join(lines)
