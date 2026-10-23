"""
Confidence scoring — field-level and profile-level.

Computes how much to trust each enriched field, and an overall
profile confidence score. Uses multiple signals:
- directness (did the user state it directly?)
- source_reliability (how trustworthy is the platform?)
- evidence_count (how many independent clues support it?)
- rule_agreement (do deterministic rules agree?)
- model_agreement (do multiple methods agree? — filled in later by LLM)
"""

from typing import Optional


# ---------------------------------------------------------------------------
# Source reliability scores (0-1)
# ---------------------------------------------------------------------------

SOURCE_RELIABILITY = {
    # Forums / communities (people give detailed context)
    'reddit.com':       0.70,
    'news.ycombinator.com': 0.75,
    'stackoverflow.com': 0.65,
    'quora.com':        0.55,
    'producthunt.com':  0.60,
    # Review platforms (structured, verified users)
    'g2.com':           0.80,
    'capterra.com':     0.80,
    'trustpilot.com':   0.75,
    'yelp.com':         0.70,
    # Social (unstructured, noisy)
    'twitter.com':      0.45,
    'x.com':            0.45,
    'facebook.com':     0.40,
    # Tech community
    'github.com':       0.80,
    'dev.to':           0.65,
    'medium.com':       0.60,
    # Default
    '_default':         0.50,
}


def get_source_reliability(source_domain: Optional[str]) -> float:
    """Get reliability score for a source domain."""
    if not source_domain:
        return SOURCE_RELIABILITY['_default']
    return SOURCE_RELIABILITY.get(source_domain, SOURCE_RELIABILITY['_default'])


# ---------------------------------------------------------------------------
# Field importance weights (for profile-level confidence)
# ---------------------------------------------------------------------------

FIELD_IMPORTANCE = {
    'pain_description':  1.0,
    'pain_category':     1.0,
    'urgency':           0.9,
    'location':          0.8,
    'business_context':  0.9,
    'intent':            0.8,
    'business_size':     0.6,
}


# ---------------------------------------------------------------------------
# Directness scoring
# ---------------------------------------------------------------------------

def _score_directness(quality: str) -> float:
    """
    How directly was this field stated?
    confirmed = user said it explicitly → 1.0
    inferred = reasoned from context → 0.75
    guessed = estimated → 0.4
    unknown = no data → 0.0
    """
    return {
        'confirmed': 1.0,
        'inferred':  0.75,
        'guessed':   0.4,
        'unknown':   0.0,
    }.get(quality, 0.0)


# ---------------------------------------------------------------------------
# Evidence scoring
# ---------------------------------------------------------------------------

def _score_evidence(evidence_count: int) -> float:
    """
    More independent evidence = higher confidence.
    0 items → 0.0, 1 → 0.4, 2 → 0.7, 3+ → 0.9
    """
    if evidence_count == 0:
        return 0.0
    elif evidence_count == 1:
        return 0.4
    elif evidence_count == 2:
        0.7
        return 0.7
    else:
        return 0.9


# ---------------------------------------------------------------------------
# Rule agreement scoring
# ---------------------------------------------------------------------------

def _score_rule_agreement(rule_method: str, has_value: bool) -> float:
    """
    Did the rule engine produce a result?
    rule + has value → 0.8
    rule + no value → 0.2
    no rule attempted → 0.5 (neutral)
    """
    if rule_method == 'rule' and has_value:
        return 0.8
    elif rule_method == 'rule' and not has_value:
        return 0.2
    return 0.5


# ---------------------------------------------------------------------------
# Field-level confidence
# ---------------------------------------------------------------------------

def score_field_confidence(
    quality: str,
    method: str,
    evidence_count: int,
    source_domain: Optional[str] = None,
    model_agreement: Optional[float] = None,
) -> float:
    """
    Compute confidence for a single enriched field.

    confidence = w1*directness + w2*source_reliability + w3*evidence + w4*rule_agreement + w5*model_agreement

    Weights (tuned for enrichment):
    - directness:      0.30  (most important: did they say it?)
    - source:          0.15  (is the platform trustworthy?)
    - evidence:        0.25  (how many clues support it?)
    - rule_agreement:  0.15  (do deterministic rules agree?)
    - model_agreement: 0.15  (does LLM agree? defaults to neutral if not available)
    """
    directness = _score_directness(quality)
    source = get_source_reliability(source_domain)
    evidence = _score_evidence(evidence_count)
    rule = _score_rule_agreement(method, quality != 'unknown')
    model = model_agreement if model_agreement is not None else 0.5

    confidence = (
        0.30 * directness +
        0.15 * source +
        0.25 * evidence +
        0.15 * rule +
        0.15 * model
    )

    return round(min(max(confidence, 0.0), 1.0), 3)


# ---------------------------------------------------------------------------
# Profile-level confidence
# ---------------------------------------------------------------------------

def score_profile_confidence(field_scores: dict[str, float]) -> float:
    """
    Compute overall profile confidence from field-level scores.

    Uses importance weights from FIELD_IMPORTANCE.

    confidence_profile = sum(importance_i * confidence_i) / sum(importance_i)
    """
    weighted_sum = 0.0
    total_weight = 0.0

    for field_name, importance in FIELD_IMPORTANCE.items():
        field_conf = field_scores.get(field_name, 0.0)
        weighted_sum += importance * field_conf
        total_weight += importance

    if total_weight == 0:
        return 0.0

    return round(weighted_sum / total_weight, 3)


# ---------------------------------------------------------------------------
# Actionability scoring
# ---------------------------------------------------------------------------

def score_actionability(
    urgency: int,
    specificity: float,
    freshness_hours: float,
    intent_clarity: float,
    business_identifiability: float,
) -> float:
    """
    How actionable is this profile?

    actionability = 0.35*urgency + 0.25*specificity + 0.20*recency + 0.10*intent + 0.10*business_id

    All inputs normalized to [0, 1].
    """
    # Normalize urgency from 1-10 to 0-1
    urgency_norm = (urgency - 1) / 9.0

    # Recency: fresher = more actionable. Decay over 72 hours.
    import math
    recency_norm = max(0.0, 1.0 - (freshness_hours / 72.0))

    actionability = (
        0.35 * urgency_norm +
        0.25 * specificity +
        0.20 * recency_norm +
        0.10 * intent_clarity +
        0.10 * business_identifiability
    )

    return round(min(max(actionability, 0.0), 1.0), 3)


# ---------------------------------------------------------------------------
# Full scoring pipeline
# ---------------------------------------------------------------------------

def score_enriched_profile(
    enriched_fields: dict,
    extracted: dict,
    source_domain: Optional[str] = None,
    freshness_hours: float = 0.0,
) -> dict:
    """
    Score an entire enriched profile.

    Takes enrichment output (from rules.py / llm_reasoner.py) and computes:
    - field-level confidence for each field
    - overall profile confidence
    - actionability score

    Returns dict with scores attached.
    """
    field_scores = {}

    for field_name in FIELD_IMPORTANCE:
        field_data = enriched_fields.get(field_name, {})

        # Handle both dict and string formats (LLM merge can produce strings)
        if isinstance(field_data, dict):
            quality = field_data.get('quality', 'unknown')
            method = field_data.get('method', 'direct')
            evidence = field_data.get('evidence', [])
        else:
            # String or other type — treat as confirmed with no evidence
            quality = 'inferred'
            method = 'direct'
            evidence = []

        conf = score_field_confidence(
            quality=quality,
            method=method,
            evidence_count=len(evidence),
            source_domain=source_domain,
        )
        field_scores[field_name] = conf

    profile_confidence = score_profile_confidence(field_scores)

    # Actionability inputs
    urgency = enriched_fields.get('urgency', {}).get('value', 5)
    if isinstance(urgency, dict):
        urgency = 5

    # Specificity: how many fields are populated beyond 'unknown'
    populated = sum(1 for f in enriched_fields.values()
                    if isinstance(f, dict) and f.get('quality') != 'unknown')
    specificity = populated / max(len(enriched_fields), 1)

    intent_data = enriched_fields.get('intent', {})
    intent_clarity = 1.0 if intent_data.get('quality') == 'confirmed' else (
        0.6 if intent_data.get('quality') == 'inferred' else 0.2
    )

    biz_data = enriched_fields.get('business_context', {})
    biz_id = 1.0 if biz_data.get('quality') == 'confirmed' else (
        0.6 if biz_data.get('quality') == 'inferred' else 0.2
    )

    actionability = score_actionability(
        urgency=urgency,
        specificity=specificity,
        freshness_hours=freshness_hours,
        intent_clarity=intent_clarity,
        business_identifiability=biz_id,
    )

    return {
        'field_scores': field_scores,
        'profile_confidence': profile_confidence,
        'actionability': actionability,
    }
