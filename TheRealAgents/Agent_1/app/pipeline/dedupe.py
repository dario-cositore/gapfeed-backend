"""
Deduplicate — prevent duplicate profiles from hitting the database.

Two layers:
1. Exact/near-exact dedup: fingerprint matching on raw signals
2. Issue clustering: group similar profiles under a broader pain event

Uses:
- SHA256 fingerprinting for exact dedup
- Text similarity for near-dup detection
- Category + product clustering for issue grouping
"""

import hashlib
import logging
import re
from typing import Optional
from pathlib import Path
import sys

ALEX_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ALEX_ROOT))

from app.models.raw_signal import RawSignal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fingerprinting (exact dedup)
# ---------------------------------------------------------------------------

def compute_fingerprint(signal: RawSignal) -> str:
    """
    Compute a dedup fingerprint for a raw signal.

    Fingerprint = SHA256 of normalized URL + text chunk + author + time bucket.

    Similar posts from the same author at the same time will collide.
    Cross-platform reposts will partially match.
    """
    normalized_url = signal.source_url.lower().strip()
    text_chunk = signal.text[:500].lower().strip()
    author = (signal.author_handle or "anon").lower()

    # Time bucket: same hour
    if signal.created_at:
        time_bucket = signal.created_at.strftime("%Y-%m-%d%H")
    else:
        time_bucket = "unknown"

    raw = f"{normalized_url}|{text_chunk}|{author}|{time_bucket}"
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_content_hash(text: str) -> str:
    """
    Compute a content-only hash (ignores URL and author).

    Catches the same complaint posted by different people
    (e.g., copy-paste reviews, viral complaints).
    """
    # Normalize: lowercase, strip whitespace, remove URLs
    cleaned = re.sub(r'https?://\S+', '', text.lower())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Take first 1000 chars
    chunk = cleaned[:1000]
    return hashlib.sha256(chunk.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Near-duplicate detection
# ---------------------------------------------------------------------------

def _text_similarity(text_a: str, text_b: str) -> float:
    """
    Simple word-overlap similarity (Jaccard index).

    Fast, no external dependencies. Good enough for near-dup detection.
    """
    words_a = set(re.findall(r'\w+', text_a.lower()))
    words_b = set(re.findall(r'\w+', text_b.lower()))

    if not words_a or not words_b:
        return 0.0

    intersection = words_a & words_b
    union = words_a | words_b

    return len(intersection) / len(union)


class DedupeChecker:
    """
    Stateful dedup checker. Maintains seen fingerprints and content hashes
    within a round (and optionally across rounds via file persistence).
    """

    def __init__(self, state_file: str = None):
        self.state_file = state_file
        self.seen_fingerprints = set()
        self.seen_content_hashes = set()
        self.seen_texts = []  # For near-dup similarity checking
        self._load_state()

    def _load_state(self):
        """Load previous fingerprints from file."""
        if not self.state_file:
            return
        try:
            import json
            p = Path(self.state_file)
            if p.exists():
                with open(p) as f:
                    data = json.load(f)
                    self.seen_fingerprints = set(data.get('fingerprints', []))
                    self.seen_content_hashes = set(data.get('content_hashes', []))
        except Exception as e:
            logger.warning(f"Failed to load dedup state: {e}")

    def _save_state(self):
        """Persist fingerprints to file."""
        if not self.state_file:
            return
        try:
            import json
            p = Path(self.state_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'fingerprints': list(self.seen_fingerprints)[-50000:],
                'content_hashes': list(self.seen_content_hashes)[-50000:],
            }
            with open(p, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save dedup state: {e}")

    def is_duplicate(self, signal: RawSignal, near_dup_threshold: float = 0.85) -> tuple[bool, str]:
        """
        Check if a signal is a duplicate.

        Returns (is_duplicate, reason).
        """
        # Layer 1: Exact fingerprint
        fingerprint = compute_fingerprint(signal)
        if fingerprint in self.seen_fingerprints:
            return True, "exact_fingerprint_match"

        # Layer 2: Content hash
        content_hash = compute_content_hash(signal.text)
        if content_hash in self.seen_content_hashes:
            return True, "content_hash_match"

        # Layer 3: Near-duplicate (word overlap)
        for prev_text in self.seen_texts[-500:]:  # Check last 500 only
            similarity = _text_similarity(signal.text, prev_text)
            if similarity >= near_dup_threshold:
                return True, f"near_duplicate (similarity={similarity:.2f})"

        return False, ""

    def mark_seen(self, signal: RawSignal):
        """Mark a signal as seen for future dedup checks."""
        fingerprint = compute_fingerprint(signal)
        content_hash = compute_content_hash(signal.text)

        self.seen_fingerprints.add(fingerprint)
        self.seen_content_hashes.add(content_hash)
        self.seen_texts.append(signal.text[:500])

        # Cap the seen_texts list to prevent memory growth
        if len(self.seen_texts) > 1000:
            self.seen_texts = self.seen_texts[-500:]

    def dedup_batch(self, signals: list[RawSignal]) -> tuple[list[RawSignal], list[tuple[RawSignal, str]]]:
        """
        Deduplicate a batch of signals.

        Returns (unique_signals, duplicates_with_reasons).
        """
        unique = []
        duplicates = []

        for signal in signals:
            is_dup, reason = self.is_duplicate(signal)
            if is_dup:
                duplicates.append((signal, reason))
            else:
                self.mark_seen(signal)
                unique.append(signal)

        self._save_state()

        if duplicates:
            logger.info(f"Dedup: {len(unique)} unique, {len(duplicates)} duplicates")

        return unique, duplicates


# ---------------------------------------------------------------------------
# Issue clustering
# ---------------------------------------------------------------------------

def compute_cluster_id(pain_category: str, product_mentions: list[str],
                        time_window: str = None) -> str:
    """
    Compute a cluster ID for grouping similar pain profiles.

    Same pain category + same product + same time window = same cluster.
    """
    products = "_".join(sorted(product_mentions[:2])) if product_mentions else "general"
    window = time_window or "ongoing"

    raw = f"{pain_category}|{products}|{window}"
    return f"cluster_{hashlib.md5(raw.encode()).hexdigest()[:12]}"


# ---------------------------------------------------------------------------
# Cross-source correlation (signal amplifier)
# ---------------------------------------------------------------------------

def correlate_cross_source(signals: list, window_hours: int = 48) -> list:
    """
    Boost urgency when same pain appears on 2+ sources within time window.

    Groups signals by content similarity (using first 200 chars normalized).
    If the same pain topic appears on multiple sources, multiply urgency by:
      - 2 sources: 2x
      - 3+ sources: 3x

    Modifies signals in-place (adds cross_source_confidence metadata).
    Returns the same list with boosted signals.
    """
    from collections import defaultdict

    # Group signals by normalized content key
    content_groups = defaultdict(list)

    for signal in signals:
        # Normalize content for grouping
        text = getattr(signal, 'text', '') or ''
        if not text:
            text = getattr(signal, 'content', '') or ''
        # Use first 200 chars, lowercased, stripped
        key = text[:200].lower().strip()
        if key:
            content_groups[key].append(signal)

    # Also group by title for title-based signals
    for signal in signals:
        title = getattr(signal, 'title', '') or ''
        if title:
            key = f"title:{title[:100].lower().strip()}"
            content_groups[key].append(signal)

    boosted_count = 0

    for key, group_signals in content_groups.items():
        if len(group_signals) < 2:
            continue

        # Get unique sources in this group
        sources = set()
        for s in group_signals:
            src = getattr(s, 'source', None) or getattr(s, 'source_type', 'unknown')
            sources.add(src)

        if len(sources) < 2:
            continue  # Same source doesn't count as cross-source

        # Calculate boost factor
        source_count = len(sources)
        if source_count >= 3:
            boost = 3.0
        else:
            boost = 2.0

        # Apply boost to all signals in the group
        for s in group_signals:
            # Boost urgency if it exists
            if hasattr(s, 'urgency') and s.urgency is not None:
                s.urgency = min(1.0, s.urgency * boost)
            elif hasattr(s, 'metadata') and isinstance(s.metadata, dict):
                if 'urgency' in s.metadata:
                    s.metadata['urgency'] = min(1.0, s.metadata['urgency'] * boost)

            # Add cross-source confidence metadata
            if hasattr(s, 'metadata') and isinstance(s.metadata, dict):
                s.metadata['cross_source'] = True
                s.metadata['cross_source_sources'] = list(sources)
                s.metadata['cross_source_boost'] = boost
            elif hasattr(s, '__dict__'):
                s.__dict__['cross_source'] = True
                s.__dict__['cross_source_boost'] = boost

            boosted_count += 1

    if boosted_count:
        logger.info(f"Cross-source correlation: boosted {boosted_count} signals from {len(content_groups)} groups")

    return signals
