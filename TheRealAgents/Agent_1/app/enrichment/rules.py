"""
Rule-based inference layer — Stage B of enrichment.

Takes deterministic extraction output and applies rules to infer:
- pain_category
- business_context
- business_size
- signal_type
- urgency estimate
- intent

No LLM calls. Pure logic. Fast and free.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Taxonomies (controlled vocabularies)
# ---------------------------------------------------------------------------

PAIN_CATEGORIES = {
    # Payment / Financial
    'payment_hold':         'Payment processor holding funds',
    'payment_failure':      'Payment not going through',
    'checkout_failure':     'Checkout/cart broken',
    'chargeback_issue':     'Chargebacks / disputes',
    'refund_dispute':       'Refund problems',
    'billing_spike':        'Unexpected billing increase',
    'pricing_change_pain':  'Pricing changed unfavorably',
    # Account
    'account_ban':          'Account banned/suspended',
    'account_review_delay': 'Account stuck in review',
    'account_lockout':      'Cannot access account',
    # Technical
    'feature_breakage':     'Feature broken after update',
    'api_breaking_change':  'API changed, broke integration',
    'service_outage':       'Service down/unavailable',
    'performance_issue':    'Slow, timeouts, degraded',
    'data_loss':            'Data lost or corrupted',
    # Support
    'support_unresponsive': 'Support not responding',
    'support_unhelpful':    'Support not solving problem',
    # Business
    'lead_shortage':        'Not getting enough customers/leads',
    'ad_account_ban':       'Ad platform banned account',
    'shipping_delay':       'Shipping/logistics issues',
    'compliance_confusion': 'Regulations, compliance unclear',
    # General
    'competitor_complaint': 'Competitor doing it better',
    'missing_feature':      'Feature doesn\'t exist, needs it',
    'switching_pain':       'Pain from migrating between tools',
    'general_frustration':  'Catch-all dissatisfaction',
}

INTENT_TAXONOMY = [
    'seeking_help',
    'seeking_vendor',
    'seeking_workaround',
    'venting_only',
    'considering_switch',
    'requesting_recommendation',
    'warning_others',
    'asking_for_legal_help',
]

SIGNAL_TYPES = ['complaint', 'want', 'question', 'review', 'discussion']


# ---------------------------------------------------------------------------
# Pain category rules
# ---------------------------------------------------------------------------

_CATEGORY_RULES = [
    # Payment / financial
    (r'\b(?:held|frozen|freeze|holding|reserve)\b.*\b(?:payout|funds?|money|payment|balance)\b', 'payment_hold'),
    (r'\b(?:payout|funds?|money|payment)\b.*\b(?:held|frozen|freeze|holding|reserve)\b', 'payment_hold'),
    (r"\b(?:won'?t|not|can'?t|doesn'?t)\s+(?:process|go\s+through|work|accept)\b.*\b(?:payment|card|charge)\b", 'payment_failure'),
    (r'\b(?:payment|card|charge)\b.*\b(?:fail|error|decline|reject)\b', 'payment_failure'),
    (r'\bcheckout\b.*\b(?:broke|broken|fail|error|crash)\b', 'checkout_failure'),
    (r'\b(?:broke|broken|fail|error|crash)\b.*\bcheckout\b', 'checkout_failure'),
    (r'\bchargeback\b', 'chargeback_issue'),
    (r"\b(?:refund|return)\b.*\b(?:denied|reject|won'?t|dispute)\b", 'refund_dispute'),
    (r'\b(?:bill(?:ing)?|invoice)\b.*\b(?:spike|surprise|wrong|overcharg|tripled|doubled)\b', 'billing_spike'),
    (r'\bpric(?:e|ing)\b.*\b(?:increase|change|went\s+up|higher|ripoff|expensive)\b', 'pricing_change_pain'),

    # Account
    (r'\b(?:bann?ed|suspend|terminated|closed|locked)\b.*\baccount\b', 'account_ban'),
    (r'\baccount\b.*\b(?:bann?ed|suspend|terminated|closed|locked)\b', 'account_ban'),
    (r'\baccount\b.*\b(?:review|pending|waiting|stuck)\b', 'account_review_delay'),
    (r'\b(?:can\'?t|cannot|unable)\b.*\b(?:log\s*in|access|sign\s*in)\b', 'account_lockout'),

    # Technical
    (r'\bbroke[n]?\b.*\b(?:after|since|update|upgrade|deploy)\b', 'feature_breakage'),
    (r'\bapi\b.*\b(?:broke|broken|change|deprecat)\b', 'api_breaking_change'),
    (r'\boutage\b|\bdown\b.*\b(?:hour|day|since|still)\b', 'service_outage'),
    (r'\b(?:slow|timeout|lag|latency)\b', 'performance_issue'),
    (r'\blost\b.*\b(?:data|files?|content|database)\b', 'data_loss'),

    # Support
    (r'\bsupport\b.*\b(?:won\'?t|not|never|no\s+response|ignor)\b', 'support_unresponsive'),
    (r'\b(?:no\s+one|nobody)\b.*\b(?:respond|answer|help|reply)\b', 'support_unresponsive'),

    # Business
    (r'\b(?:no\s+leads?|no\s+customers?|no\s+traffic|dead\s+leads?)\b', 'lead_shortage'),
    (r'\bad\s+account\b.*\b(?:bann?ed|suspend|disabled)\b', 'ad_account_ban'),
    (r'\b(?:shipping|delivery|fulfillment)\b.*\b(?:delay|late|slow|lost)\b', 'shipping_delay'),
]


def infer_pain_category(extracted: dict, text: str) -> str:
    """Infer pain category from extraction + text."""
    text_lower = text.lower()

    # Rule-based matching
    for pattern, category in _CATEGORY_RULES:
        if re.search(pattern, text_lower):
            return category

    # Fallback: pain severity + product context
    pain_severity = extracted.get('pain_severity', 'none')
    products = extracted.get('product_mentions', [])

    if pain_severity == 'high' and products:
        return 'general_frustration'
    if pain_severity in ('high', 'medium') and extracted.get('intent_markers'):
        return 'general_frustration'

    return 'uncategorized'


# ---------------------------------------------------------------------------
# Business context rules
# ---------------------------------------------------------------------------

_PLATFORM_CONTEXTS = {
    'shopify': 'ecommerce_shopify',
    'amazon': 'ecommerce_amazon',
    'etsy': 'ecommerce_etsy',
    'ebay': 'ecommerce_ebay',
    'woocommerce': 'ecommerce_woocommerce',
    'bigcommerce': 'ecommerce_bigcommerce',
    'stripe': 'payments_stripe',
    'paypal': 'payments_paypal',
    'square': 'payments_square',
    'hubspot': 'crm_hubspot',
    'salesforce': 'crm_salesforce',
    'zoho': 'crm_zoho',
    'slack': 'communication_slack',
    'notion': 'productivity_notion',
    'github': 'development_github',
    'vercel': 'hosting_vercel',
    'heroku': 'hosting_heroku',
    'aws': 'cloud_aws',
    'mailchimp': 'email_marketing_mailchimp',
    'sendgrid': 'email_marketing_sendgrid',
    'zendesk': 'support_zendesk',
    'intercom': 'support_intercom',
    'openai': 'ai_openai',
}


def infer_business_context(extracted: dict) -> Optional[str]:
    """Infer business context from product mentions."""
    products = extracted.get('product_mentions', [])
    if not products:
        return None

    # Return the context for the most prominent product
    for product in products:
        if product in _PLATFORM_CONTEXTS:
            return _PLATFORM_CONTEXTS[product]

    # Generic: if a product is mentioned but not in our dict
    return f'platform_{products[0]}'


# ---------------------------------------------------------------------------
# Business size rules
# ---------------------------------------------------------------------------

_SIZE_RULES = [
    # Enterprise signals
    (r'\b(?:enterprise|corporation|thousands?\s+of\s+employ|500\+|1000\+)\b', 'enterprise'),
    (r'\b(?:our\s+team\s+of\s+\d{3,}|company\s+of\s+\d{3,})\b', 'enterprise'),

    # Mid-size signals
    (r'\b(?:our\s+team|company\s+of|employ)\s*(?:of\s+)?(\d{2,3})\b', 'mid_business'),
    (r'\b(?:50|100|200)\s*(?:employees?|people|staff)\b', 'mid_business'),

    # Small business signals
    (r'\b(?:small\s+business|smb|mom\s+and\s+pop|local\s+shop|side\s+hustle|freelanc)\b', 'small_business'),
    (r'\b(?:our\s+team\s+of\s+\d{1,2}|just\s+(?:me|us\s+two|us\s+three))\b', 'small_business'),

    # Solo signals
    (r'\b(?:solo|alone|just\s+me|one\s+person|by\s+myself|indie)\b', 'solo'),
    (r'\b(?:my\s+blog|my\s+store|my\s+shop|my\s+project)\b', 'solo'),
]


def infer_business_size(extracted: dict, text: str) -> Optional[str]:
    """Infer business size from extraction + text."""
    text_lower = text.lower()

    for pattern, size in _SIZE_RULES:
        if re.search(pattern, text_lower):
            return size

    # Money-based heuristic
    money = extracted.get('money_mentions', [])
    if money:
        max_amount = max(money)
        if max_amount >= 100000:
            return 'mid_business'
        elif max_amount >= 10000:
            return 'small_business'
        elif max_amount >= 1000:
            return 'solo'

    return None


# ---------------------------------------------------------------------------
# Signal type rules
# ---------------------------------------------------------------------------

def infer_signal_type(extracted: dict, text: str) -> str:
    """Classify the signal type."""
    intent_markers = extracted.get('intent_markers', [])
    has_question = extracted.get('has_question', False)
    pain_severity = extracted.get('pain_severity', 'none')

    if 'warning_others' in intent_markers:
        return 'complaint'
    if 'venting' in intent_markers:
        return 'complaint'
    if pain_severity in ('high', 'medium'):
        if has_question:
            return 'question'
        return 'complaint'
    if 'seeking_help' in intent_markers or 'seeking_alternative' in intent_markers:
        return 'question'
    if pain_severity == 'low':
        return 'want'
    if has_question:
        return 'question'

    return 'discussion'


# ---------------------------------------------------------------------------
# Intent rules
# ---------------------------------------------------------------------------

def infer_intent(extracted: dict) -> Optional[str]:
    """Infer intent from extraction markers."""
    markers = extracted.get('intent_markers', [])

    if 'seeking_help' in markers:
        return 'seeking_help'
    if 'seeking_alternative' in markers:
        return 'considering_switch'
    if 'warning_others' in markers:
        return 'warning_others'
    if 'venting' in markers:
        return 'venting_only'

    # Check for legal intent
    text_combined = " ".join(extracted.get('location_mentions', []))
    if any(w in str(extracted) for w in ['lawyer', 'attorney', 'legal', 'sue', 'lawsuit']):
        return 'asking_for_legal_help'

    return None


# ---------------------------------------------------------------------------
# Urgency estimation
# ---------------------------------------------------------------------------

def estimate_urgency(extracted: dict, text: str) -> int:
    """
    Estimate urgency on 1-10 scale using rules only.
    LLM can override later if needed.
    """
    score = 3  # baseline

    pain_severity = extracted.get('pain_severity', 'none')
    if pain_severity == 'high':
        score += 4
    elif pain_severity == 'medium':
        score += 2
    elif pain_severity == 'low':
        score += 0

    # Money at stake increases urgency
    money = extracted.get('money_mentions', [])
    if money:
        max_amount = max(money)
        if max_amount >= 50000:
            score += 3
        elif max_amount >= 10000:
            score += 2
        elif max_amount >= 1000:
            score += 1

    # Urgency language
    text_lower = text.lower()
    if re.search(r'\b(?:urgent|emergency|immediately|asap|right\s+now|critical)\b', text_lower):
        score += 2
    if re.search(r'\b(?:deadline|due\s+tomorrow|payroll|rent)\b', text_lower):
        score += 2
    if re.search(r'\b(?:desperate|stuck|trapped|nowhere\s+to\s+turn)\b', text_lower):
        score += 1

    return min(max(score, 1), 10)


# ---------------------------------------------------------------------------
# Master rule engine
# ---------------------------------------------------------------------------

def apply_rules(extracted: dict, text: str) -> dict:
    """
    Apply all rule-based inference. Returns enrichment suggestions
    that feed into Stage C (LLM) or directly into profile building.

    Each field gets: value, quality, method.
    """
    pain_category = infer_pain_category(extracted, text)
    business_context = infer_business_context(extracted)
    business_size = infer_business_size(extracted, text)
    signal_type = infer_signal_type(extracted, text)
    intent = infer_intent(extracted)
    urgency = estimate_urgency(extracted, text)

    return {
        'pain_category': {
            'value': pain_category,
            'quality': 'inferred' if pain_category != 'uncategorized' else 'unknown',
            'method': 'rule',
        },
        'business_context': {
            'value': business_context,
            'quality': 'inferred' if business_context else 'unknown',
            'method': 'rule',
        },
        'business_size': {
            'value': business_size,
            'quality': 'inferred' if business_size else 'unknown',
            'method': 'rule',
        },
        'signal_type': {
            'value': signal_type,
            'quality': 'inferred',
            'method': 'rule',
        },
        'intent': {
            'value': intent,
            'quality': 'inferred' if intent else 'unknown',
            'method': 'rule',
        },
        'urgency': {
            'value': urgency,
            'quality': 'inferred',
            'method': 'rule',
        },
    }
