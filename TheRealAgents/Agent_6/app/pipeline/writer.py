"""
Classification writer — pushes classification results back to the database.
Also persists resolved entity mentions for Phase 3 real-time tracking.
"""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Path resolution for shared imports
MAYA_DIR = Path(__file__).resolve().parent.parent.parent
TUXO_DIR = MAYA_DIR.parent.parent
sys.path.insert(0, str(TUXO_DIR))

from shared.remote_db import RemoteDB


def _persist_mentions(signal_id: int, classification: dict):
    """
    Resolve mentions from classification data and persist to entity tables.
    Runs fire-and-forget (errors are logged but don't block classification).
    """
    try:
        db = RemoteDB()
        mentions_to_insert = []

        # Source 1: product_category
        pc = classification.get('product_category')
        if pc:
            from src.engines.mention_resolver import resolve_product_category, extract_mention_context
            resolved = resolve_product_category(pc)
            if resolved:
                canonical, etype = resolved
                eid = _get_or_create_entity(db, canonical, etype)
                if eid:
                    mentions_to_insert.append({
                        'signal_id': signal_id,
                        'entity_id': eid,
                        'raw_mention': pc,
                        'mention_type': 'product_category',
                        'confidence': 0.9,
                        'sentiment': classification.get('sentiment', 'neutral'),
                    })

        # Source 2: competitor_mentions
        competitors = classification.get('competitor_mentions', [])
        if isinstance(competitors, str):
            try:
                competitors = json.loads(competitors)
            except json.JSONDecodeError:
                competitors = []
        if isinstance(competitors, list):
            from src.engines.mention_resolver import resolve_mention
            for m in competitors:
                resolved = resolve_mention(str(m))
                if resolved:
                    canonical, etype = resolved
                    eid = _get_or_create_entity(db, canonical, etype)
                    if eid:
                        mentions_to_insert.append({
                            'signal_id': signal_id,
                            'entity_id': eid,
                            'raw_mention': str(m),
                            'mention_type': 'competitor',
                            'confidence': 0.85,
                            'sentiment': classification.get('sentiment', 'neutral'),
                        })

        # Bulk insert if we have mentions
        if mentions_to_insert:
            db._request('insert_mentions_bulk', {'mentions': mentions_to_insert})
            logger.debug(f"Persisted {len(mentions_to_insert)} entity mentions for signal {signal_id}")

    except Exception as e:
        # Fire and forget - don't block classification
        logger.debug(f"Mention persistence failed for signal {signal_id}: {e}")


# Cache entity lookups to avoid repeated API calls per cycle
_entity_cache = {}

def _get_or_create_entity(db, canonical_name: str, entity_type: str) -> int:
    """Get or create entity, return ID. Uses in-memory cache."""
    if canonical_name in _entity_cache:
        return _entity_cache[canonical_name]

    result = db._request('upsert_entity', {
        'canonical_name': canonical_name,
        'entity_type': entity_type,
        'aliases': [canonical_name.lower()],
    })
    eid = result.get('id')
    if eid:
        _entity_cache[canonical_name] = eid
    return eid


def write_classification(signal_id: int, classification: dict) -> bool:
    """
    Write a classification result back to the database.

    Args:
        signal_id: The signal's database ID.
        classification: Dict with classification fields.

    Returns:
        True if write succeeded, False otherwise.
    """
    try:
        db = RemoteDB()

        # Build update dict
        update = {
            'pain_category': classification.get('pain_category', 'uncategorized'),
            'urgency_score': float(classification.get('urgency_score', 0)),
            'specificity_score': float(classification.get('specificity_score', 0)),
            'buyer_intent': float(classification.get('buyer_intent', 0)),
            'quality_tier': classification.get('quality_tier', 'noise'),
            'sentiment': classification.get('sentiment', 'neutral'),
            'signal_type': classification.get('signal_type', 'discussion'),
            'location': classification.get('location') or '',
            'product_category': classification.get('product_category') or '',
            'is_processed': 1,
        }

        # Handle competitor_mentions (must be JSON string for DB)
        competitors = classification.get('competitor_mentions', [])
        if isinstance(competitors, list):
            update['competitor_mentions'] = json.dumps(competitors)
        elif isinstance(competitors, str):
            update['competitor_mentions'] = competitors
        else:
            update['competitor_mentions'] = '[]'

        db.update_signal(signal_id, **update)
        logger.debug(f"Wrote classification for signal {signal_id}: tier={update['quality_tier']}")

        # Phase 3: persist entity mentions (fire and forget)
        if update['quality_tier'] in ('gold', 'silver', 'bronze'):
            _persist_mentions(signal_id, classification)

        return True

    except Exception as e:
        logger.error(f"Failed to write classification for signal {signal_id}: {e}")
        return False


def write_batch(classifications: list[dict]) -> tuple[int, int]:
    """
    Write multiple classifications to the database.

    Args:
        classifications: List of dicts, each must have 'signal_id' field.

    Returns:
        (success_count, failure_count)
    """
    successes = 0
    failures = 0

    for c in classifications:
        signal_id = c.get('signal_id')
        if not signal_id:
            logger.warning(f"Classification missing signal_id: {c}")
            failures += 1
            continue

        if write_classification(signal_id, c):
            successes += 1
        else:
            failures += 1

    logger.info(f"Batch write: {successes} succeeded, {failures} failed")
    return successes, failures
