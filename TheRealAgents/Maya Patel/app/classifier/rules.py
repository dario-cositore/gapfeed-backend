"""
Rule-based pre-classification — fast heuristics before LLM.

Runs on every signal. Filters obvious noise, extracts features,
and provides context for the LLM classification step.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Pain verb dictionaries
# ---------------------------------------------------------------------------

HIGH_PAIN = {
    'broke', 'broken', 'crashed', 'down', 'outage', 'froze', 'frozen',
    'lost', 'denied', 'rejected', 'banned', 'blocked', 'suspended',
    'deleted', 'removed', 'terminated', 'cancelled', 'stolen', 'hacked',
    'scammed', 'fraud', 'disaster', 'nightmare', 'urgent', 'emergency',
    'desperate', 'critical', 'immediately', 'stuck', 'trapped', 'screwed',
    'lawsuit', 'sued', 'court', 'attorney', 'lawyer', 'deported',
    'detained', 'arrested', 'evicted', 'foreclosure',
}

MEDIUM_PAIN = {
    'slow', 'frustrating', 'annoying', 'bug', 'buggy', 'failing', 'error',
    'issue', 'problem', 'complaint', 'disappointed', 'terrible', 'horrible',
    'worst', 'hate', 'awful', 'useless', 'overpriced', 'expensive',
    'ripoff', 'misleading', 'waste', 'ridiculous', 'unacceptable',
    'incompetent', 'unprofessional', 'scam',
}

LOW_PAIN = {
    'wish', 'missing', 'lacking', 'needs', 'should', 'could be better',
    'not great', 'mediocre', 'underwhelming', 'meh', 'disappointing',
    'confusing', 'unclear', 'complicated',
}

# ---------------------------------------------------------------------------
# Intent markers (regex patterns)
# ---------------------------------------------------------------------------

SEEKING_HELP = [
    r'(?:anyone|anybody)\s+(?:else|know|have|had)',
    r'what\s+(?:should|do|can)\s+(?:i|we)',
    r'how\s+(?:do|can|should)\s+(?:i|we)',
    r'need\s+(?:help|advice|recommendation)',
    r'looking\s+for',
    r'any\s+suggestions',
    r'does\s+anyone\s+know',
]

SEEKING_ALT = [
    r'(?:alternative|replacement|instead|switch(?:ing)?\s+to)',
    r'what\s+(?:do\s+you\s+use|are\s+you\s+using)',
    r'(?:better|best)\s+(?:alternative|option|tool)',
]

VENTING = [
    r'(?:just|had\s+to)\s+(?:rant|vent)',
    r'sick\s+of', r'fed\s+up', r"i'?m\s+done",
    r'this\s+is\s+(?:ridiculous|unacceptable|insane)',
]

WARNING = [
    r'(?:heads\s+up|be\s+careful|watch\s+out|beware|psa|warning)',
    r"don'?t\s+(?:use|buy|trust|go\s+with)",
]

# ---------------------------------------------------------------------------
# Noise patterns (things that are almost certainly not pain signals)
# ---------------------------------------------------------------------------

NOISE_PATTERNS = [
    r'^(?:lol|haha|lmao|rofl|nice|cool|awesome|great|thanks|ty|thx)\s*[!.]*$',
    r'^(?:upvoted?|downvoted?|this|same|agree|disagree|source\??|sauce\??)\s*[!.]*$',
    r'^(?:\+1|bump|following|subscribed|bookmark)\s*[!.]*$',
    r'^(?:removed|deleted)\s*[!.]*$',
    r'^\[removed\]$', r'^\[deleted\]$',
]

# ---------------------------------------------------------------------------
# Product dictionary (subset of most important ones)
# ---------------------------------------------------------------------------

PRODUCTS = {
    'shopify': 'shopify', 'amazon': 'amazon', 'etsy': 'etsy',
    'stripe': 'stripe', 'paypal': 'paypal', 'square': 'square',
    'slack': 'slack', 'notion': 'notion', 'jira': 'jira',
    'hubspot': 'hubspot', 'salesforce': 'salesforce',
    'aws': 'aws', 'heroku': 'heroku', 'vercel': 'vercel',
    'openai': 'openai', 'chatgpt': 'openai', 'github': 'github',
    'zendesk': 'zendesk', 'mailchimp': 'mailchimp',
    'godaddy': 'godaddy', 'bluehost': 'bluehost', 'ionos': 'ionos',
    'google': 'google', 'facebook': 'facebook', 'instagram': 'instagram',
    'twitter': 'twitter', 'linkedin': 'linkedin', 'youtube': 'youtube',
    'uber': 'uber', 'lyft': 'lyft', 'airbnb': 'airbnb',
}


def _word_hits(text_lower: str, words: set) -> list[str]:
    """Find word matches in text."""
    found = []
    text_tokens = set(re.findall(r'\b\w+\b', text_lower))
    for word in words:
        if ' ' in word:
            if word in text_lower:
                found.append(word)
        elif word in text_tokens:
            found.append(word)
    return found


def _regex_hits(text: str, patterns: list[str]) -> list[str]:
    """Find regex pattern matches."""
    found = []
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            found.append(pattern)
    return found


def pre_classify(text: str, source: str = '') -> dict:
    """
    Run rule-based pre-classification on a signal.

    Returns dict with:
    - is_noise: bool (True if this looks like noise)
    - noise_reason: str or None
    - pain_severity: 'none' | 'low' | 'medium' | 'high'
    - pain_hits: list of matched pain words
    - intent_markers: list of detected intents
    - product_mentions: list of detected products
    - has_question: bool
    - text_length: int
    - pre_urgency: float (0-1)
    - pre_specificity: float (0-1)
    - pre_buyer_intent: float (0-1)
    - pre_quality_tier: str
    - skip_llm: bool (if True, no need for LLM)
    """
    if not text or not text.strip():
        return {
            'is_noise': True, 'noise_reason': 'empty_text',
            'pain_severity': 'none', 'pain_hits': [],
            'intent_markers': [], 'product_mentions': [],
            'has_question': False, 'text_length': 0,
            'pre_urgency': 0.0, 'pre_specificity': 0.0,
            'pre_buyer_intent': 0.0, 'pre_quality_tier': 'noise',
            'skip_llm': True,
        }

    text_lower = text.lower().strip()

    # Check noise patterns
    for pattern in NOISE_PATTERNS:
        if re.match(pattern, text_lower):
            return {
                'is_noise': True, 'noise_reason': f'matches_noise_pattern',
                'pain_severity': 'none', 'pain_hits': [],
                'intent_markers': [], 'product_mentions': [],
                'has_question': False, 'text_length': len(text),
                'pre_urgency': 0.0, 'pre_specificity': 0.0,
                'pre_buyer_intent': 0.0, 'pre_quality_tier': 'noise',
                'skip_llm': True,
            }

    # Very short text is likely noise
    if len(text_lower) < 30:
        return {
            'is_noise': True, 'noise_reason': 'too_short',
            'pain_severity': 'none', 'pain_hits': [],
            'intent_markers': [], 'product_mentions': [],
            'has_question': False, 'text_length': len(text),
            'pre_urgency': 0.0, 'pre_specificity': 0.0,
            'pre_buyer_intent': 0.0, 'pre_quality_tier': 'noise',
            'skip_llm': True,
        }

    # Pain verb analysis
    high_hits = _word_hits(text_lower, HIGH_PAIN)
    medium_hits = _word_hits(text_lower, MEDIUM_PAIN)
    low_hits = _word_hits(text_lower, LOW_PAIN)

    if high_hits:
        pain_severity = 'high'
    elif medium_hits:
        pain_severity = 'medium'
    elif low_hits:
        pain_severity = 'low'
    else:
        pain_severity = 'none'

    all_pain_hits = high_hits + medium_hits + low_hits

    # Intent markers
    intent_markers = []
    if _regex_hits(text, SEEKING_HELP):
        intent_markers.append('seeking_help')
    if _regex_hits(text, SEEKING_ALT):
        intent_markers.append('seeking_alternative')
    if _regex_hits(text, VENTING):
        intent_markers.append('venting')
    if _regex_hits(text, WARNING):
        intent_markers.append('warning_others')

    # Product mentions
    product_mentions = []
    for keyword, canonical in PRODUCTS.items():
        if keyword in text_lower:
            product_mentions.append(canonical)
    product_mentions = list(dict.fromkeys(product_mentions))

    # Question detection
    has_question = '?' in text

    # Pre-scores
    pre_urgency = 0.0
    if pain_severity == 'high':
        pre_urgency = 0.7
    elif pain_severity == 'medium':
        pre_urgency = 0.4
    elif pain_severity == 'low':
        pre_urgency = 0.2

    # Boost urgency for certain intents
    if 'warning_others' in intent_markers:
        pre_urgency = min(1.0, pre_urgency + 0.15)
    if 'venting' in intent_markers:
        pre_urgency = min(1.0, pre_urgency + 0.1)

    # Specificity: longer text + products + location clues = more specific
    pre_specificity = 0.0
    if len(text) > 500:
        pre_specificity += 0.3
    elif len(text) > 200:
        pre_specificity += 0.2
    elif len(text) > 100:
        pre_specificity += 0.1

    if product_mentions:
        pre_specificity += 0.2
    if has_question:
        pre_specificity += 0.1
    if any(m in text_lower for m in ['$', 'usd', 'eur', 'dollar', 'euro']):
        pre_specificity += 0.15

    pre_specificity = min(1.0, pre_specificity)

    # Buyer intent
    pre_buyer_intent = 0.0
    if 'seeking_alternative' in intent_markers:
        pre_buyer_intent += 0.5
    if 'seeking_help' in intent_markers:
        pre_buyer_intent += 0.3
    if product_mentions:
        pre_buyer_intent += 0.1
    if any(m in text_lower for m in ['recommend', 'suggest', 'switch', 'alternative', 'better option']):
        pre_buyer_intent += 0.2

    pre_buyer_intent = min(1.0, pre_buyer_intent)

    # Pre-quality tier
    if pre_urgency >= 0.7 and pre_specificity >= 0.5:
        pre_tier = 'gold'
    elif pre_urgency >= 0.4 or pre_specificity >= 0.4:
        pre_tier = 'silver'
    elif pre_urgency >= 0.15 or pre_specificity >= 0.15 or pain_severity != 'none':
        pre_tier = 'bronze'
    else:
        pre_tier = 'noise'

    # Skip LLM if clearly noise and no pain signals at all
    skip_llm = (pain_severity == 'none' and not intent_markers
                and not product_mentions and not has_question)

    return {
        'is_noise': False,
        'noise_reason': None,
        'pain_severity': pain_severity,
        'pain_hits': all_pain_hits,
        'intent_markers': intent_markers,
        'product_mentions': product_mentions,
        'has_question': has_question,
        'text_length': len(text),
        'pre_urgency': round(pre_urgency, 2),
        'pre_specificity': round(pre_specificity, 2),
        'pre_buyer_intent': round(pre_buyer_intent, 2),
        'pre_quality_tier': pre_tier,
        'skip_llm': skip_llm,
    }
