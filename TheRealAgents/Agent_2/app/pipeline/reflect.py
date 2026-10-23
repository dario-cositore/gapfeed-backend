"""
Reflect — Alex's post-round self-reflection.

After each round, Alex writes:
1. A journal entry (natural language)
2. Updated source stats
3. Updated plan if strategy changed
4. Self-evaluation scores

This is what makes Alex a reasoning agent, not a scraper.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
import sys

ALEX_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ALEX_ROOT))

logger = logging.getLogger(__name__)


def generate_reflection(
    round_id: str,
    plan_reasoning: str,
    sources_scanned: list[str],
    raw_signals_found: int,
    profiles_stored: int,
    profiles_discarded: int,
    profiles_duplicate: int,
    avg_confidence: float,
    avg_actionability: float,
    top_pain_categories: list[str],
    enrichment_successes: list[str],
    enrichment_failures: list[str],
    llm_calls_made: int,
    errors: list[str],
) -> str:
    """
    Generate a natural language journal entry for this round.

    This is written in Alex's voice. It becomes part of his memory
    and feeds into future reasoning.
    """
    now = datetime.now(timezone.utc).strftime('%B %d, %Y — %H:%M UTC')

    lines = [
        f"## Round {round_id} — {now}",
        "",
        f"**Plan:** {plan_reasoning[:200] if plan_reasoning else 'No reasoning recorded'}",
        "",
        f"**Sources:** {', '.join(sources_scanned) if sources_scanned else 'none'}",
        f"**Raw signals:** {raw_signals_found} found",
        f"**Profiles stored:** {profiles_stored} (avg confidence: {avg_confidence:.2f}, avg actionability: {avg_actionability:.2f})",
        f"**Discarded:** {profiles_discarded} | **Duplicates:** {profiles_duplicate}",
        f"**LLM calls:** {llm_calls_made}",
        "",
    ]

    # Pain categories found
    if top_pain_categories:
        lines.append("**Top pain categories:**")
        for cat in top_pain_categories[:5]:
            lines.append(f"- {cat}")
        lines.append("")

    # What worked
    if enrichment_successes:
        lines.append("**What worked:**")
        for s in enrichment_successes[:5]:
            lines.append(f"- {s}")
        lines.append("")

    # What didn't work
    if enrichment_failures or errors:
        lines.append("**What didn't work:**")
        for s in (enrichment_failures + errors)[:5]:
            lines.append(f"- {s}")
        lines.append("")

    # Self-evaluation
    yield_rate = profiles_stored / max(raw_signals_found, 1)
    lines.append("**Self-evaluation:**")
    if yield_rate > 0.5:
        lines.append(f"- Yield rate {yield_rate:.0%} is strong. Sources are well-targeted.")
    elif yield_rate > 0.2:
        lines.append(f"- Yield rate {yield_rate:.0%} is decent. Some noise in sources.")
    else:
        lines.append(f"- Yield rate {yield_rate:.0%} is low. Need to refine source selection or queries.")

    if avg_confidence > 0.7:
        lines.append(f"- Enrichment quality is high ({avg_confidence:.2f}). Extraction pipeline working well.")
    else:
        lines.append(f"- Enrichment quality is moderate ({avg_confidence:.2f}). May need better extraction or more LLM budget.")

    lines.append("")
    lines.append("---")
    lines.append("")

    return "\n".join(lines)


def append_to_journal(journal_path: str, entry: str):
    """Append a reflection entry to the journal file."""
    try:
        p = Path(journal_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        with open(p, 'a', encoding='utf-8') as f:
            f.write(entry)

        logger.info(f"Journal entry written to {journal_path}")
    except Exception as e:
        logger.error(f"Failed to write journal: {e}")


def generate_source_stats(
    source_performance: dict,
) -> str:
    """
    Generate markdown summary of source performance.

    source_performance = {
        'reddit:r/shopify': {'raw': 30, 'stored': 12, 'avg_confidence': 0.72, 'noise_rate': 0.34},
        ...
    }
    """
    lines = [
        "## Source Performance",
        "",
        "| Source | Raw | Stored | Avg Conf | Noise |",
        "|--------|-----|--------|----------|-------|",
    ]

    for source, stats in sorted(source_performance.items(), key=lambda x: x[1].get('stored', 0), reverse=True):
        raw = stats.get('raw', 0)
        stored = stats.get('stored', 0)
        conf = stats.get('avg_confidence', 0)
        noise = stats.get('noise_rate', 0)
        lines.append(f"| {source} | {raw} | {stored} | {conf:.2f} | {noise:.0%} |")

    lines.append("")
    return "\n".join(lines)
