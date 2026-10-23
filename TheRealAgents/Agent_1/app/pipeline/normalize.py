"""
Normalize — convert raw adapter output into consistent RawSignal format.

Every adapter returns slightly different data. This stage normalizes
everything into the canonical RawSignal schema before enrichment.

Handles:
- Field mapping (different adapters use different field names)
- Text cleanup (HTML stripping, whitespace normalization)
- Language detection (basic)
- Timestamp normalization (various formats → ISO)
- Geo hint extraction from platform metadata
"""

import re
import logging
from datetime import datetime, timezone
from typing import Optional
import sys
from pathlib import Path

# Add project root for imports
ALEX_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ALEX_ROOT))

from app.models.raw_signal import RawSignal, SourceType

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common entities."""
    if not text:
        return ""

    # Remove script/style blocks
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)

    # Decode common entities
    entities = {
        '&amp;': '&', '&lt;': '<', '&gt;': '>',
        '&quot;': '"', '&#39;': "'", '&apos;': "'",
        '&nbsp;': ' ', '&#x27;': "'",
    }
    for entity, char in entities.items():
        text = text.replace(entity, char)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def _normalize_whitespace(text: str) -> str:
    """Normalize excessive whitespace and line breaks."""
    if not text:
        return ""

    # Collapse multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Collapse multiple spaces
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


def _normalize_timestamp(ts: Optional[str]) -> Optional[str]:
    """Normalize various timestamp formats to ISO 8601."""
    if not ts:
        return None

    # Already ISO
    if 'T' in ts:
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.isoformat()
        except Exception:
            pass

    # Unix timestamp (string)
    try:
        ts_float = float(ts)
        if ts_float > 1e12:  # milliseconds
            ts_float /= 1000
        return datetime.fromtimestamp(ts_float, tz=timezone.utc).isoformat()
    except (ValueError, OSError):
        pass

    return ts


def _extract_geo_from_subreddit(subreddit: str) -> Optional[str]:
    """Extract geographic hint from subreddit name."""
    geo_subs = {
        'immigration': 'US',
        'uscis': 'US',
        'h1b': 'US',
        'f1visa': 'US',
        'ukvisa': 'UK',
        'ImmigrationCanada': 'Canada',
        'ausvisa': 'Australia',
        'legaladvice': 'US',
        'legaladviceuk': 'UK',
        'personalfinance': 'US',
        'UKPersonalFinance': 'UK',
        'PersonalFinanceCanada': 'Canada',
    }
    return geo_subs.get(subreddit)


def _extract_geo_from_domain(domain: str) -> Optional[str]:
    """Extract geographic hint from domain TLD."""
    if not domain:
        return None
    tld_map = {
        '.uk': 'UK', '.de': 'Germany', '.fr': 'France',
        '.ca': 'Canada', '.au': 'Australia', '.in': 'India',
        '.jp': 'Japan', '.br': 'Brazil', '.mx': 'Mexico',
    }
    for tld, country in tld_map.items():
        if domain.endswith(tld):
            return country
    return None


def normalize_signal(raw: dict, source_hint: str = None) -> Optional[RawSignal]:
    """
    Normalize a raw adapter dict into a RawSignal model.

    Args:
        raw: Raw dict from any adapter
        source_hint: Override source_type if adapter doesn't set it

    Returns:
        RawSignal instance, or None if normalization fails.
    """
    try:
        # Determine source type
        source_type_str = raw.get('source_type', source_hint or 'other')
        try:
            source_type = SourceType(source_type_str)
        except ValueError:
            source_type = SourceType.OTHER

        # Normalize text fields
        title = _strip_html(raw.get('title', '') or '')
        body = _strip_html(raw.get('body', '') or '')
        body = _normalize_whitespace(body)

        # Skip if no meaningful content
        combined = f"{title} {body}".strip()
        if len(combined) < 20:
            logger.debug(f"Signal too short after normalization ({len(combined)} chars), skipping")
            return None

        # Normalize timestamps
        created_at = _normalize_timestamp(raw.get('created_at'))
        collected_at = _normalize_timestamp(raw.get('collected_at'))
        if not collected_at:
            collected_at = datetime.now(timezone.utc).isoformat()

        # Extract geo hints
        geo_hint = raw.get('geo_hint')
        platform_meta = raw.get('platform_metadata', {})

        if not geo_hint and source_type == SourceType.REDDIT:
            subreddit = platform_meta.get('subreddit', '')
            geo_hint = _extract_geo_from_subreddit(subreddit)

        if not geo_hint:
            domain = platform_meta.get('domain', '')
            geo_hint = _extract_geo_from_domain(domain)

        # Build signal
        signal = RawSignal(
            raw_signal_id=raw.get('raw_signal_id', f"sig_{source_type.value}_{hash(combined) & 0xFFFFFFFF:08x}"),
            source_type=source_type,
            source_subtype=raw.get('source_subtype'),
            author_handle=raw.get('author_handle'),
            source_url=raw.get('source_url', ''),
            title=title if title else None,
            body=body,
            created_at=datetime.fromisoformat(created_at) if created_at else None,
            platform_metadata=platform_meta,
            language=raw.get('language', 'en'),
            geo_hint=geo_hint,
            product_mentions=raw.get('product_mentions', []),
            money_mentions=raw.get('money_mentions', []),
        )

        return signal

    except Exception as e:
        logger.error(f"Failed to normalize signal: {e}\nRaw: {str(raw)[:300]}")
        return None


def normalize_batch(raw_signals: list[dict], source_hint: str = None) -> list[RawSignal]:
    """
    Normalize a batch of raw adapter dicts.

    Returns list of valid RawSignal instances (skips failures).
    """
    normalized = []
    failed = 0

    for raw in raw_signals:
        signal = normalize_signal(raw, source_hint)
        if signal:
            normalized.append(signal)
        else:
            failed += 1

    if failed > 0:
        logger.info(f"Normalized {len(normalized)} signals, {failed} failed")

    return normalized
