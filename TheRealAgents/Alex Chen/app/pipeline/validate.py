"""
Validate — pre-enrichment quality checks on normalized signals.

Before spending LLM time on enrichment, check if the signal is worth processing.
This is the cheap filter that throws out garbage early.

Two levels:
1. Structural validation (instant): length, format, language
2. Content validation (cheap): spam detection, relevance scoring
"""

import re
import logging
from typing import Optional
from pathlib import Path
import sys

ALEX_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ALEX_ROOT))

from app.models.raw_signal import RawSignal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structural checks
# ---------------------------------------------------------------------------

MIN_TEXT_LENGTH = 50       # Minimum chars for meaningful enrichment
MAX_TEXT_LENGTH = 50000    # Truncate beyond this (probably a wall of text / copy-paste)


def check_length(signal: RawSignal) -> tuple[bool, str]:
    """Check text meets minimum length requirement."""
    text_len = len(signal.text)
    if text_len < MIN_TEXT_LENGTH:
        return False, f"Text too short ({text_len} chars, min {MIN_TEXT_LENGTH})"
    return True, ""


def check_not_empty_body(signal: RawSignal) -> tuple[bool, str]:
    """Check the signal has actual content (not just a title)."""
    if not signal.body and not signal.title:
        return False, "No content at all"
    return True, ""


def check_valid_url(signal: RawSignal) -> tuple[bool, str]:
    """Check source URL is present and looks valid."""
    url = signal.source_url
    if not url:
        return False, "No source URL"
    if not url.startswith(('http://', 'https://')):
        return False, f"Invalid URL scheme: {url[:50]}"
    return True, ""


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------

# Common spam patterns
_SPAM_PATTERNS = [
    re.compile(r'\b(buy\s+now|click\s+here|free\s+money|earn\s+\$?\d+|make\s+money\s+fast)\b', re.IGNORECASE),
    re.compile(r'\b(limited\s+time\s+offer|act\s+now|congratulations\s+you\s+won)\b', re.IGNORECASE),
    re.compile(r'(https?://\S+\s*){3,}'),  # Multiple URLs in a row
    re.compile(r'\b(subscribe\s+to\s+my|check\s+out\s+my\s+channel|follow\s+me)\b', re.IGNORECASE),
    re.compile(r'(.)\1{10,}'),  # Repeated characters (aaaaaaaaa)
]


def check_not_spam(signal: RawSignal) -> tuple[bool, str]:
    """Detect obvious spam."""
    text = signal.text
    spam_score = 0

    for pattern in _SPAM_PATTERNS:
        if pattern.search(text):
            spam_score += 1

    if spam_score >= 2:
        return False, f"Spam detected ({spam_score} indicators)"
    return True, ""


# Patterns that suggest link-only / no-content posts
_LINK_ONLY_PATTERNS = [
    re.compile(r'^https?://\S+$'),  # Entire body is just a URL
    re.compile(r'^(check\s+out|see|read|watch)\s+https?://\S+$', re.IGNORECASE),
]


def check_not_link_only(signal: RawSignal) -> tuple[bool, str]:
    """Reject posts that are just a link with no context."""
    body = (signal.body or '').strip()
    for pattern in _LINK_ONLY_PATTERNS:
        if pattern.match(body):
            return False, "Link-only post, no meaningful content"
    return True, ""


# Bot / automated post patterns
_BOT_PATTERNS = [
    re.compile(r'\b(i\s+am\s+a\s+bot|this\s+(?:action|post)\s+was\s+performed\s+automatically)\b', re.IGNORECASE),
    re.compile(r'\b(automated\s+message|auto-?generated|do\s+not\s+reply)\b', re.IGNORECASE),
]


def check_not_bot(signal: RawSignal) -> tuple[bool, str]:
    """Detect bot/automated posts."""
    text = signal.text
    for pattern in _BOT_PATTERNS:
        if pattern.search(text):
            return False, "Bot/automated post"
    return True, ""


# Deleted / removed content
_DELETED_PATTERNS = [
    re.compile(r'^\[deleted\]$'),
    re.compile(r'^\[removed\]$'),
    re.compile(r'^<removed>$'),
    re.compile(r'^This post has been removed'),
]


def check_not_deleted(signal: RawSignal) -> tuple[bool, str]:
    """Detect deleted/removed posts."""
    body = (signal.body or '').strip()
    title = (signal.title or '').strip()
    combined = f"{title} {body}"

    for pattern in _DELETED_PATTERNS:
        if pattern.match(combined) or pattern.match(body):
            return False, "Deleted/removed content"
    return True, ""


# ---------------------------------------------------------------------------
# Relevance scoring (soft check)
# ---------------------------------------------------------------------------

# Words that suggest the content might contain pain signals
_PAIN_INDICATORS = [
    'problem', 'issue', 'bug', 'error', 'broken', 'fail', 'crash',
    'frustrat', 'annoy', 'terrible', 'horrible', 'worst', 'hate',
    'scam', 'fraud', 'ripoff', 'overcharged', 'stolen',
    'help', 'stuck', 'lost', 'denied', 'rejected', 'banned',
    'slow', 'expensive', 'waste', 'useless', 'disappointed',
    'complaint', 'sucks', 'nightmare', 'disaster',
    'urgent', 'emergency', 'critical', 'desperate',
]


def relevance_score(signal: RawSignal) -> float:
    """
    Score how likely this signal contains pain (0-1).

    Not a hard pass/fail, but used for prioritization.
    """
    text = signal.text.lower()
    words = text.split()
    if not words:
        return 0.0

    # Count pain indicator hits
    hits = sum(1 for indicator in _PAIN_INDICATORS if indicator in text)
    indicator_ratio = min(hits / 5.0, 1.0)  # Normalize: 5+ hits = max

    # Has a question mark? (someone might be asking for help)
    has_question = 1.0 if '?' in text else 0.0

    # Has negative sentiment words?
    negative_words = ['not', 'no', 'never', 'can\'t', 'won\'t', 'don\'t',
                      'nothing', 'nowhere', 'nobody']
    neg_count = sum(1 for w in negative_words if f' {w} ' in f' {text} ')
    neg_score = min(neg_count / 3.0, 1.0)

    # Combined score
    score = (0.5 * indicator_ratio + 0.3 * neg_score + 0.2 * has_question)
    return round(score, 3)


# ---------------------------------------------------------------------------
# Master validation
# ---------------------------------------------------------------------------

class ValidationResult:
    """Result of signal validation."""
    def __init__(self):
        self.passed = True
        self.reasons = []
        self.relevance = 0.0

    def fail(self, reason: str):
        self.passed = False
        self.reasons.append(reason)

    def to_dict(self) -> dict:
        return {
            'passed': self.passed,
            'reasons': self.reasons,
            'relevance': self.relevance,
        }


def validate_signal(signal: RawSignal) -> ValidationResult:
    """
    Run all validation checks on a normalized signal.

    Returns ValidationResult with pass/fail and relevance score.
    """
    result = ValidationResult()

    # Hard checks (any fail = reject)
    checks = [
        check_length,
        check_not_empty_body,
        check_valid_url,
        check_not_spam,
        check_not_link_only,
        check_not_bot,
        check_not_deleted,
    ]

    for check_fn in checks:
        passed, reason = check_fn(signal)
        if not passed:
            result.fail(reason)

    # Relevance scoring (always computed, not a hard fail)
    result.relevance = relevance_score(signal)

    # Very low relevance + barely passes length = probably not useful
    if result.passed and result.relevance < 0.1 and len(signal.text) < 100:
        result.fail(f"Low relevance ({result.relevance}) with short text")

    return result


def validate_batch(signals: list[RawSignal]) -> tuple[list[RawSignal], list[tuple[RawSignal, str]]]:
    """
    Validate a batch of signals.

    Returns (passed_signals, rejected_signals_with_reasons).
    """
    passed = []
    rejected = []

    for signal in signals:
        result = validate_signal(signal)
        if result.passed:
            passed.append(signal)
        else:
            reason = '; '.join(result.reasons)
            rejected.append((signal, reason))

    logger.info(f"Validation: {len(passed)} passed, {len(rejected)} rejected")
    return passed, rejected
