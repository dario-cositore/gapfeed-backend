"""
Signal reader — fetches unprocessed signals from the database.
"""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Path resolution for shared imports
MAYA_DIR = Path(__file__).resolve().parent.parent.parent
TUXO_DIR = MAYA_DIR.parent.parent
sys.path.insert(0, str(TUXO_DIR))

from shared.remote_db import RemoteDB


def get_unprocessed_signals(limit: int = 10, min_text_length: int = 50,
                            vertical: str = None) -> list[dict]:
    """
    Fetch unprocessed signals from the database.

    Args:
        limit: Maximum number of signals to fetch.
        min_text_length: Minimum text length to include.
        vertical: Optional vertical filter.

    Returns:
        List of signal dicts with 'id', 'text', 'source', etc.
    """
    try:
        db = RemoteDB()
        signals = db.get_signals(
            vertical=vertical,
            is_processed=0,
            limit=limit,
            order='collected_at ASC',  # Process oldest first
        )

        if not signals:
            return []

        # Filter by text length
        filtered = []
        for s in signals:
            text = f"{s.get('title', '')} {s.get('content', '')}".strip()
            if len(text) >= min_text_length:
                filtered.append(s)
            else:
                # Mark very short signals as noise immediately
                logger.debug(f"Skipping short signal {s.get('id')}: {len(text)} chars")
                _mark_as_noise(db, s.get('id'))

        logger.info(f"Fetched {len(filtered)}/{len(signals)} unprocessed signals (min_length={min_text_length})")
        return filtered

    except Exception as e:
        logger.error(f"Failed to fetch unprocessed signals: {e}")
        return []


def _mark_as_noise(db: RemoteDB, signal_id: int):
    """Mark a short signal as noise without LLM processing."""
    try:
        db.update_signal(
            signal_id,
            quality_tier='noise',
            pain_category='uncategorized',
            urgency_score=0.0,
            specificity_score=0.0,
            buyer_intent=0.0,
            sentiment='neutral',
            signal_type='discussion',
            is_processed=1,
        )
    except Exception as e:
        logger.error(f"Failed to mark signal {signal_id} as noise: {e}")
