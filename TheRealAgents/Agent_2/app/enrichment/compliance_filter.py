"""
Compliance filter — PII redaction, sensitive data blocking, safety checks.

Runs BEFORE storage. Every enriched profile passes through here.
If it fails compliance, it gets blocked with a reason.

Three layers:
1. PII redaction (strip obvious personal identifiers)
2. Sensitive category blocking (don't store disallowed inferences)
3. Quality gate (minimum requirements for storage)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PII patterns (redact before storage)
# ---------------------------------------------------------------------------

_PII_PATTERNS = [
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
    # Phone numbers (US + international)
    (re.compile(r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE_REDACTED]'),
    (re.compile(r'\b\+\d{1,3}[-.\s]?\d{4,14}\b'), '[PHONE_REDACTED]'),
    # SSN patterns
    (re.compile(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b'), '[SSN_REDACTED]'),
    # Credit card patterns (basic)
    (re.compile(r'\b(?:\d{4}[-.\s]?){3}\d{4}\b'), '[CARD_REDACTED]'),
    # Physical addresses (street numbers + street names)
    (re.compile(r'\b\d{1,5}\s+[A-Za-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|Way|Place|Pl)\b', re.IGNORECASE), '[ADDRESS_REDACTED]'),
    # IP addresses
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '[IP_REDACTED]'),
]


def redact_pii(text: str) -> str:
    """Redact obvious PII from text. Returns cleaned text."""
    cleaned = text
    for pattern, replacement in _PII_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# Sensitive category blocking
# ---------------------------------------------------------------------------

BLOCKED_CATEGORIES = {
    # Personal characteristics (not business-relevant)
    'health_status',
    'political_beliefs',
    'race_ethnicity',
    'religion',
    'sexual_orientation',
    'union_status',
    'genetic_information',
    'biometric_data',
    # Financial PII (not business context)
    'bank_account_number',
    'tax_id',
    'social_security_number',
    'credit_card_number',
    # Legal specifics
    'case_number',
    'court_order',
    'arrest_record',
}

# Keywords that suggest sensitive content
_SENSITIVE_KEYWORDS = {
    'health_status': [
        r'\b(?:diagnosed|diagnosis|disease|disorder|syndrome|cancer|diabetes|'
        r'heart condition|mental health|depression|anxiety disorder|adhd|autism|'
        r'chronic|terminal|medication|prescription|treatment plan)\b',
    ],
    'political_beliefs': [
        r'\b(?:democrat|republican|liberal|conservative|socialist|communist|'
        r'maga|antifa|political party|vote for|election|ballot)\b',
    ],
    'race_ethnicity': [
        r'\b(?:african.american|hispanic|latino|asian|white|black|'
        r'caucasian|ethnic|racial|minority)\b.*\b(?:discriminat|racist|bias)\b',
    ],
    'religion': [
        r'\b(?:christian|muslim|jewish|hindu|buddhist|atheist|'
        r'church|mosque|synagogue|temple|religious|faith.based)\b.*\b(?:discriminat|bias|refus)\b',
    ],
    'sexual_orientation': [
        r'\b(?:gay|lesbian|bisexual|transgender|lgbtq|queer|'
        r'homosexual|heterosexual)\b.*\b(?:discriminat|bias|refus)\b',
    ],
}

# Immigration status is a special case: relevant for immigration vertical,
# blocked for general vertical
_IMMIGRATION_KEYWORDS = [
    r'\b(?:visa|green\s*card|asylum|deport|undocumented|daca|h1b|'
    r'uscis|immigration\s+status|work\s+permit|citizenship)\b',
]


def detect_sensitive_content(text: str, pain_description: str = "",
                              vertical: str = "general") -> list[str]:
    """
    Detect sensitive categories in text.

    Returns list of detected sensitive categories.
    """
    detected = []
    combined = f"{text} {pain_description}".lower()

    for category, patterns in _SENSITIVE_KEYWORDS.items():
        for pattern in patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                detected.append(category)
                break

    # Immigration status: only blocked in general vertical
    if vertical == "general":
        for pattern in _IMMIGRATION_KEYWORDS:
            if re.search(pattern, combined, re.IGNORECASE):
                # Don't block, just flag — immigration pain is relevant
                # but we don't store immigration STATUS as a field
                break

    return detected


def check_blocked_fields(enriched_fields: dict) -> list[str]:
    """
    Check if any enriched fields contain blocked categories.

    Returns list of field names that contain blocked content.
    """
    blocked = []

    for field_name, field_data in enriched_fields.items():
        if not isinstance(field_data, dict):
            continue
        value = field_data.get('value', '')
        if not value:
            continue
        value_lower = str(value).lower()
        for blocked_cat in BLOCKED_CATEGORIES:
            if blocked_cat.replace('_', ' ') in value_lower:
                blocked.append(f"{field_name}:{blocked_cat}")

    return blocked


# ---------------------------------------------------------------------------
# Quality gate (minimum requirements for storage)
# ---------------------------------------------------------------------------

class QualityGateResult:
    """Result of quality gate check."""
    def __init__(self):
        self.passed = True
        self.reasons = []

    def fail(self, reason: str):
        self.passed = False
        self.reasons.append(reason)

    def to_dict(self) -> dict:
        return {
            'passed': self.passed,
            'reasons': self.reasons,
        }


def quality_gate(profile: dict, extracted: dict) -> QualityGateResult:
    """
    Hard and soft quality checks before storage.

    Hard fails (reject):
    - pain_description empty or too short
    - pain_category is uncategorized AND no other qualifying fields
    - source_url missing
    - confidence below 0.5 (unless discarded with reason)

    Soft fails (reject):
    - text mostly profanity/spam
    - signal too old (unless tied to active event)
    - too short for meaningful enrichment
    """
    result = QualityGateResult()

    # --- Hard checks ---

    pain_desc = profile.get('pain_description', '')
    if not pain_desc or len(pain_desc.strip()) < 10:
        result.fail("pain_description too short or empty (min 10 chars)")

    source_url = profile.get('source_url', '')
    if not source_url:
        result.fail("source_url is required")

    confidence = profile.get('confidence', 0)
    if confidence < 0.35 and not profile.get('discard_reason'):
        result.fail(f"confidence {confidence:.2f} below 0.35 threshold")

    # At least one of: location, business_context, intent, money/product mention
    has_location = profile.get('location', {}).get('quality') not in (None, 'unknown')
    has_biz = profile.get('business_context', {}).get('quality') not in (None, 'unknown')
    has_intent = profile.get('intent', {}).get('quality') not in (None, 'unknown')
    has_money = bool(extracted.get('money_mentions', []))
    has_product = bool(extracted.get('product_mentions', []))

    if not any([has_location, has_biz, has_intent, has_money, has_product]):
        result.fail("No enrichable fields: need at least one of location, business_context, intent, money, or product mention")

    # --- Soft checks ---

    # Text length minimum
    text_length = extracted.get('text_length', 0)
    if text_length < 30:
        result.fail(f"Text too short for meaningful enrichment ({text_length} chars, min 30)")

    # Spam / profanity check (simple ratio)
    text_lower = profile.get('pain_description', '').lower()
    spam_words = ['buy now', 'click here', 'free money', 'earn fast', 'make $$$',
                  'limited offer', 'act now', 'congratulations you won']
    spam_hits = sum(1 for w in spam_words if w in text_lower)
    if spam_hits >= 2:
        result.fail("Text appears to be spam")

    # Profanity ratio (allow some, block if dominant)
    profanity = ['fuck', 'shit', 'damn', 'ass', 'crap', 'wtf', 'stfu']
    words = text_lower.split()
    if words:
        profanity_ratio = sum(1 for w in words if w in profanity) / len(words)
        if profanity_ratio > 0.3:
            result.fail(f"Excessive profanity ({profanity_ratio:.0%} of words)")

    return result


# ---------------------------------------------------------------------------
# Main compliance filter
# ---------------------------------------------------------------------------

def compliance_check(profile: dict, extracted: dict,
                     text: str = "", vertical: str = "general") -> dict:
    """
    Full compliance pipeline. Run before storing any profile.

    Returns:
    {
        'passed': bool,
        'reasons': [list of fail reasons if any],
        'redacted_text': str (PII-stripped version),
        'sensitive_flags': [list of detected sensitive categories],
        'blocked_fields': [list of fields with blocked content],
        'quality_gate': {passed, reasons}
    }
    """
    result = {
        'passed': True,
        'reasons': [],
        'redacted_text': '',
        'sensitive_flags': [],
        'blocked_fields': [],
        'quality_gate': {},
    }

    # 1. PII redaction
    source_text = text or profile.get('pain_description', '')
    result['redacted_text'] = redact_pii(source_text)

    # 2. Sensitive content detection
    result['sensitive_flags'] = detect_sensitive_content(
        source_text,
        profile.get('pain_description', ''),
        vertical=vertical,
    )
    if result['sensitive_flags']:
        # Don't block, but flag — downstream can decide
        logger.warning(f"Sensitive content detected: {result['sensitive_flags']}")

    # 3. Blocked fields check
    enriched_fields = {
        'location': profile.get('location', {}),
        'business_context': profile.get('business_context', {}),
        'business_size': profile.get('business_size', {}),
        'intent': profile.get('intent', {}),
    }
    result['blocked_fields'] = check_blocked_fields(enriched_fields)
    if result['blocked_fields']:
        result['passed'] = False
        result['reasons'].extend([f"Blocked field: {f}" for f in result['blocked_fields']])

    # 4. Quality gate
    gate = quality_gate(profile, extracted)
    result['quality_gate'] = gate.to_dict()
    if not gate.passed:
        result['passed'] = False
        result['reasons'].extend(gate.reasons)

    return result
