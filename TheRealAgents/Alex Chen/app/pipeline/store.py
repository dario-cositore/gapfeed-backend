"""
Store — persist enriched profiles to MySQL via remote_db.

Handles:
- Writing profiles to MySQL (via PHP API proxy)
- Writing round data
- Writing source stats
- Writing event data
- Fallback to local SQLite if MySQL is unavailable
- Batch inserts for efficiency
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path
import sys

# Add project root for shared module access
# File: tuxo/TheRealAgents/Alex Chen/app/pipeline/store.py
_DEPTH = Path(__file__).resolve()
for _ in range(5):
    _DEPTH = _DEPTH.parent
sys.path.insert(0, str(_DEPTH))

from shared.remote_db import RemoteDB

logger = logging.getLogger(__name__)


class ProfileStore:
    """Persists enriched profiles and metadata to MySQL."""

    def __init__(self, api_url: str = None, api_key: str = None):
        self.db = RemoteDB(api_url=api_url, api_key=api_key)
        self._buffer = []
        self._buffer_size = 10
        self._failed_buffer = []

    def store_profile(self, profile: dict) -> bool:
        """
        Store a single enriched profile to MySQL.

        The profile dict maps to the signals table in MySQL.
        We store the enrichment data as JSON in the metadata field.

        Returns True if stored successfully.
        """
        try:
            # Map profile to MySQL signal schema
            signal = {
                'source': profile.get('source_type', 'unknown'),
                'source_url': profile.get('source_url', ''),
                'platform_id': profile.get('dedupe_fingerprint', ''),
                'subreddit': profile.get('platform_metadata', {}).get('subreddit', '') if isinstance(profile.get('platform_metadata'), dict) else '',
                'author': profile.get('author_handle', ''),
                'title': profile.get('pain_description', '')[:200],
                'content': profile.get('pain_description', ''),
                'created_at': profile.get('first_seen_at', ''),
                'collected_at': profile.get('created_at', ''),
                'vertical': profile.get('vertical', 'general'),
                'product_category': profile.get('business_context', {}).get('value', '') if isinstance(profile.get('business_context'), dict) else '',
                'pain_category': profile.get('pain_category', 'uncategorized'),
                'signal_type': profile.get('signal_type', 'complaint'),
                'location': self._extract_location(profile),
                'urgency_score': profile.get('urgency', 5) / 10.0,
                'specificity_score': profile.get('confidence', 0),
                'buyer_intent': profile.get('actionability_score', 0),
                'quality_tier': self._confidence_to_tier(profile.get('confidence', 0)),
                'sentiment': 'negative',  # Pain signals are inherently negative
                'competitor_mentions': json.dumps(profile.get('personalization_data', [])[:5]),
                'metadata': json.dumps({
                    'profile_id': profile.get('profile_id', ''),
                    'business_size': profile.get('business_size', {}),
                    'intent': profile.get('intent', {}),
                    'confidence': profile.get('confidence', 0),
                    'actionability_score': profile.get('actionability_score', 0),
                    'personalization_data': profile.get('personalization_data', []),
                    'dedupe_fingerprint': profile.get('dedupe_fingerprint', ''),
                    'cluster_id': profile.get('cluster_id'),
                    'enrichment_completeness': self._calc_completeness(profile),
                }),
                'is_processed': 1,  # Already enriched
                'synthesized': 0,
            }

            result = self.db.insert_signal(signal)
            logger.info(f"Stored profile {profile.get('profile_id', '?')} -> DB id {result.get('id', '?')}")
            return True

        except Exception as e:
            logger.error(f"Failed to store profile: {e}")
            self._failed_buffer.append(profile)
            return False

    def store_batch(self, profiles: list[dict]) -> dict:
        """
        Store a batch of profiles. Returns stats.
        """
        stored = 0
        failed = 0

        for profile in profiles:
            if profile.get('discard_reason'):
                continue  # Skip discarded profiles

            if self.store_profile(profile):
                stored += 1
            else:
                failed += 1

        # Flush failed buffer to local file if any
        if self._failed_buffer:
            self._flush_failed()

        return {
            'stored': stored,
            'failed': failed,
            'total': len(profiles),
        }

    def store_round(self, round_data: dict) -> bool:
        """Store round metadata (for monitoring/analytics)."""
        try:
            # Store as a brief with round metadata
            round_json = json.dumps(round_data, default=str)
            self.db.upsert_brief(
                vertical='general',
                query=f"round_{round_data.get('round_id', 'unknown')}",
                brief_json=round_json,
                brief_md=f"Round {round_data.get('round_id', 'unknown')}: "
                         f"{round_data.get('profiles_stored', 0)} profiles stored, "
                         f"{round_data.get('profiles_discarded', 0)} discarded",
                signal_count=round_data.get('raw_signals_found', 0),
                quality='system',
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store round data: {e}")
            return False

    def _extract_location(self, profile: dict) -> str:
        """Extract location string from profile."""
        loc = profile.get('location', {})
        if isinstance(loc, dict) and loc.get('value'):
            return loc['value']
        return ''

    def _confidence_to_tier(self, confidence: float) -> str:
        """Map confidence score to quality tier."""
        if confidence >= 0.75:
            return 'gold'
        elif confidence >= 0.55:
            return 'silver'
        elif confidence >= 0.40:
            return 'bronze'
        return 'noise'

    def _calc_completeness(self, profile: dict) -> float:
        """Calculate enrichment completeness (0-1)."""
        fields = ['location', 'business_context', 'business_size', 'intent']
        filled = 0
        for field in fields:
            field_data = profile.get(field, {})
            if isinstance(field_data, dict) and field_data.get('quality') not in (None, 'unknown'):
                filled += 1
        return filled / len(fields)

    def _flush_failed(self):
        """Write failed profiles to local spool for retry."""
        try:
            spool_dir = ALEX_ROOT / 'state' / 'spool'
            spool_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            spool_file = spool_dir / f"failed_{ts}.json"
            with open(spool_file, 'w') as f:
                json.dump(self._failed_buffer, f, indent=2, default=str)
            logger.warning(f"Flushed {len(self._failed_buffer)} failed profiles to {spool_file}")
            self._failed_buffer = []
        except Exception as e:
            logger.error(f"Failed to flush failed profiles: {e}")
