"""
Post-classification confidence scoring.

Evaluates how confident we are in a classification by checking
agreement between rule-based pre-classification and LLM output.
"""


def score_confidence(classification: dict, pre_classification: dict = None) -> float:
    """
    Score confidence in a classification result.

    Higher confidence when:
    - LLM and rules agree on severity
    - Scores are internally consistent
    - Quality tier matches scores
    - Text was long enough for good analysis

    Returns float 0.0-1.0.
    """
    score = 0.5  # Base confidence

    if not pre_classification:
        return 0.3  # Low confidence without pre-classification context

    # --- 1. Agreement between rules and LLM ---

    # Urgency agreement
    pre_urgency = pre_classification.get('pre_urgency', 0)
    llm_urgency = classification.get('urgency_score', 0)
    urgency_diff = abs(pre_urgency - llm_urgency)

    if urgency_diff < 0.15:
        score += 0.15  # Strong agreement
    elif urgency_diff < 0.3:
        score += 0.05  # Mild agreement
    else:
        score -= 0.1  # Disagreement

    # Pain severity agreement
    pre_severity = pre_classification.get('pain_severity', 'none')
    llm_sentiment = classification.get('sentiment', 'neutral')

    severity_sentiment_map = {
        'high': 'negative',
        'medium': 'negative',
        'low': 'neutral',
        'none': 'neutral',
    }
    expected_sentiment = severity_sentiment_map.get(pre_severity, 'neutral')
    if llm_sentiment == expected_sentiment:
        score += 0.1
    elif (llm_sentiment == 'neutral' and expected_sentiment == 'negative') or \
         (llm_sentiment == 'negative' and expected_sentiment == 'neutral'):
        score += 0.0  # Borderline, don't penalize

    # --- 2. Internal consistency ---

    urgency = classification.get('urgency_score', 0)
    specificity = classification.get('specificity_score', 0)
    buyer_intent = classification.get('buyer_intent', 0)
    quality_tier = classification.get('quality_tier', 'noise')

    # Gold tier should have high scores
    if quality_tier == 'gold':
        if urgency >= 0.6 and specificity >= 0.5:
            score += 0.1
        else:
            score -= 0.15  # Gold with low scores = inconsistent

    # Noise tier should have low scores
    if quality_tier == 'noise':
        if urgency < 0.2 and specificity < 0.2:
            score += 0.1
        else:
            score -= 0.1  # Noise with high scores = inconsistent

    # High urgency + high buyer intent = consistent
    if urgency > 0.6 and buyer_intent > 0.4:
        score += 0.05

    # --- 3. Text length bonus ---

    text_length = pre_classification.get('text_length', 0)
    if text_length > 500:
        score += 0.05
    elif text_length < 100:
        score -= 0.05

    # --- 4. Product mention bonus ---

    if pre_classification.get('product_mentions'):
        score += 0.05

    # --- 5. Pain hits bonus ---

    if pre_classification.get('pain_hits'):
        score += 0.05

    # Clamp
    return max(0.0, min(1.0, round(score, 3)))
