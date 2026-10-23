"""
Classification schema — defines expected fields and validation.
"""

VALID_QUALITY_TIERS = ['noise', 'bronze', 'silver', 'gold']
VALID_SIGNAL_TYPES = ['complaint', 'question', 'review', 'discussion', 'recommendation']
VALID_SENTIMENTS = ['negative', 'neutral', 'positive']

PAIN_CATEGORIES = [
    'account_issues', 'payment_problems', 'billing_disputes',
    'service_outage', 'poor_support', 'missing_features',
    'performance_issues', 'security_concerns', 'data_loss',
    'migration_pain', 'integration_problems', 'pricing_complaints',
    'ux_frustration', 'compliance_issues', 'onboarding_difficulty',
    'competitor_comparison', 'feature_request', 'bug_report',
    'refund_request', 'scam_warning',
    'immigration', 'visa_issues', 'legal_complaints',
    'uncategorized'
]


def validate_classification(classification: dict) -> tuple[bool, list[str]]:
    """
    Validate a classification dict. Returns (is_valid, errors).
    """
    errors = []

    # Quality tier
    tier = classification.get('quality_tier', '')
    if tier not in VALID_QUALITY_TIERS:
        errors.append(f"Invalid quality_tier: '{tier}'. Must be one of {VALID_QUALITY_TIERS}")

    # Scores
    for field in ('urgency_score', 'specificity_score', 'buyer_intent'):
        val = classification.get(field, None)
        if val is None:
            errors.append(f"Missing field: {field}")
        elif not isinstance(val, (int, float)):
            errors.append(f"Field {field} must be numeric, got {type(val).__name__}")
        elif not (0.0 <= val <= 1.0):
            errors.append(f"Field {field} must be 0.0-1.0, got {val}")

    # Sentiment
    sentiment = classification.get('sentiment', '')
    if sentiment not in VALID_SENTIMENTS:
        errors.append(f"Invalid sentiment: '{sentiment}'. Must be one of {VALID_SENTIMENTS}")

    # Signal type
    signal_type = classification.get('signal_type', '')
    if signal_type not in VALID_SIGNAL_TYPES:
        errors.append(f"Invalid signal_type: '{signal_type}'. Must be one of {VALID_SIGNAL_TYPES}")

    return len(errors) == 0, errors


def enforce_quality_tier(classification: dict) -> dict:
    """
    Enforce quality tier based on scores.
    If scores don't match tier, adjust the tier.
    """
    urgency = classification.get('urgency_score', 0)
    specificity = classification.get('specificity_score', 0)
    buyer = classification.get('buyer_intent', 0)

    # Compute expected tier from scores
    if urgency >= 0.7 and specificity >= 0.6 and buyer >= 0.3:
        expected = 'gold'
    elif urgency >= 0.4 or specificity >= 0.4:
        expected = 'silver'
    elif urgency >= 0.15 or specificity >= 0.15:
        expected = 'bronze'
    else:
        expected = 'noise'

    # Always enforce: scores dictate the tier, not the LLM's opinion
    classification['quality_tier'] = expected
    return classification
