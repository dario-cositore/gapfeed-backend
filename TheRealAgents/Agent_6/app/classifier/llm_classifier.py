"""
LLM-based signal classification — the deep analysis step.

Takes a signal + pre-classification context and uses the LLM to produce
a structured classification with urgency, specificity, buyer intent,
quality tier, sentiment, and more.
"""

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Path resolution: Maya root -> tuxo root for shared imports
MAYA_DIR = Path(__file__).resolve().parent.parent.parent
TUXO_DIR = MAYA_DIR.parent.parent
sys.path.insert(0, str(TUXO_DIR))

from shared.llm_client import llm_json, llm_call

from .schema import enforce_quality_tier, validate_classification
from ..utils.text import truncate_for_llm, clean_text


CLASSIFICATION_SYSTEM_PROMPT = """You are a signal classifier for a business intelligence platform.
You analyze raw text signals (from Reddit, forums, review sites, etc.) and produce structured classifications.

You MUST respond with a valid JSON object. No other text before or after the JSON.

The JSON must have these exact fields:
{
  "pain_category": "<one of: account_issues, payment_problems, billing_disputes, service_outage, poor_support, missing_features, performance_issues, security_concerns, data_loss, migration_pain, integration_problems, pricing_complaints, ux_frustration, compliance_issues, onboarding_difficulty, competitor_comparison, feature_request, bug_report, refund_request, scam_warning, immigration, visa_issues, legal_complaints, uncategorized>",
  "urgency_score": <float 0.0-1.0>,
  "specificity_score": <float 0.0-1.0>,
  "buyer_intent": <float 0.0-1.0>,
  "quality_tier": "<noise|bronze|silver|gold>",
  "sentiment": "<negative|neutral|positive>",
  "signal_type": "<complaint|question|review|discussion|recommendation>",
  "location": "<extracted location or null>",
  "product_category": "<the product/service being discussed or null>",
  "competitor_mentions": ["<list of competitor names mentioned, or empty>"],
  "reasoning": "<1-2 sentences explaining your classification>"
}

=== SCORING GUIDELINES WITH EXAMPLES ===

URGENCY (most signals should score 0.3-0.6):
- 0.9-1.0: "My account was hacked and money is being drained RIGHT NOW"
- 0.7-0.8: "We've been down for 3 hours and losing customers, need help ASAP"
- 0.5-0.6: "The new update broke our workflow, it's frustrating"
- 0.3-0.4: "I wish there was a better way to do X, it's been annoying me"
- 0.1-0.2: "Interesting that nobody has built a tool for X yet"

BUYER INTENT (most signals should score 0.2-0.5):
- 0.9-1.0: "I'll pay anything for a tool that does X, taking recommendations NOW"
- 0.7-0.8: "Looking for alternatives to [product], budget is $50/mo, what do you use?"
- 0.5-0.6: "Does anyone know of a good solution for X?"
- 0.3-0.4: "X is annoying but I've learned to live with it"
- 0.1-0.2: "Just venting about how bad X is lol"

SENTIMENT (target: ~50% negative, ~30% neutral, ~20% positive. NOT everything is negative):
- negative: ONLY when there is actual frustration, anger, or complaint in the language
  "This app is broken, can't believe they haven't fixed this"
  "Worst customer service I've ever dealt with"
  "I'm so done with this tool, switching immediately"
- neutral: Questions, searching, discussing without strong emotion
  "Is there a tool that does X? I've been looking everywhere"
  "How do I do X? Anyone have experience with this?"
  "What's the best way to handle X?"
  "I've been using Y for 6 months, it's ok"
- positive: Sharing solutions, suggesting alternatives, expressing satisfaction
  "I solved this with a workaround, here's what worked"
  "I switched to X and it's been great"
  "Finally found a good solution for this problem"

KEY SENTIMENT RULES:
- "I wish there was an app for X" = neutral/positive (willingness to buy, NOT negative)
- "Does anyone know how to..." = neutral (question, not complaint)
- "Looking for alternatives to X" = neutral (searching, not necessarily angry)
- Sharing a pain point without anger = neutral (just describing reality)
- Only mark negative when the LANGUAGE itself shows frustration/anger/complaint

SPECIFICITY (varies by detail level):
- 0.8-1.0: Detailed account with steps to reproduce, exact error messages, dates, amounts
- 0.5-0.7: Describes the problem with some context and examples
- 0.3-0.4: General complaint without much detail
- 0.1-0.2: One-liner, vague, no context

=== FEW-SHOT EXAMPLES ===

Example 1: "Anyone else having trouble with Stripe payouts? Mine have been delayed 5 days"
- urgency: 0.5 (annoying but not emergency)
- buyer_intent: 0.3 (not actively shopping, just checking if others have same issue)
- sentiment: neutral (asking a question, not raging)
- specificity: 0.5 (mentions Stripe, 5 days delay)
- quality_tier: silver

Example 2: "Just discovered Notion can't do X, spent 3 hours trying, switching to something else, budget $100/mo"
- urgency: 0.6 (painful but manageable)
- buyer_intent: 0.85 (actively switching, has budget)
- sentiment: negative (frustrated, actively leaving)
- specificity: 0.7 (mentions product, time spent, budget)
- quality_tier: gold

Example 3: "What tools do you all use for project management? Curious what's out there"
- urgency: 0.1 (no urgency at all)
- buyer_intent: 0.4 (curious, might buy if something good comes up)
- sentiment: neutral (casual question)
- specificity: 0.2 (very vague)
- quality_tier: bronze

Example 4: "I wish there was a simple app for tracking freelance invoices, I keep losing track"
- urgency: 0.3 (annoyance but not angry)
- buyer_intent: 0.6 (expressing need, would buy if it existed)
- sentiment: neutral (stating a need, no frustration in the language)
- specificity: 0.4 (describes the problem vaguely)
- quality_tier: silver

Example 5: "I solved the Zapier pricing issue by switching to n8n, here's my migration guide"
- urgency: 0.4 (past problem, now resolved)
- buyer_intent: 0.1 (already found solution)
- sentiment: positive (sharing what worked, helping others)
- specificity: 0.8 (specific solution with details)
- quality_tier: bronze

Example 6: "Our data got corrupted during migration from MySQL to Postgres, lost 3 weeks of customer records, legal is involved"
- urgency: 0.9 (data loss + legal = serious)
- buyer_intent: 0.2 (not buying, dealing with crisis)
- sentiment: negative (crisis situation)
- specificity: 0.9 (specific details: migration path, duration, consequences)
- quality_tier: silver (high urgency but low buyer intent)

Be precise. Vary your scores. Not everything is urgent. Not everyone wants to buy. Read the actual content and score accordingly."""


def classify_signal(text: str, source: str = '', pre_classification: dict = None,
                    llm_config: dict = None) -> dict:
    """
    Classify a signal using LLM deep analysis.

    Args:
        text: The signal text (title + content).
        source: Source identifier (e.g., 'reddit:r/immigration').
        pre_classification: Output from rules.pre_classify() for context.
        llm_config: Dict with model, max_tokens, temperature, timeout.

    Returns:
        Classification dict with all fields populated.
    """
    config = llm_config or {}
    model = config.get('model', 'mimo-v2.6-flash')
    max_tokens = config.get('max_tokens', 10000)
    temperature = config.get('temperature', 0.1)
    timeout = config.get('timeout', 60)

    # Clean and truncate text for LLM
    cleaned = clean_text(text)
    truncated = truncate_for_llm(cleaned, max_tokens_estimate=2500)

    # Build context from pre-classification
    context_parts = []
    if pre_classification:
        if pre_classification.get('pain_hits'):
            context_parts.append(f"Rule-detected pain words: {', '.join(pre_classification['pain_hits'][:5])}")
        if pre_classification.get('intent_markers'):
            context_parts.append(f"Detected intents: {', '.join(pre_classification['intent_markers'])}")
        if pre_classification.get('product_mentions'):
            context_parts.append(f"Products mentioned: {', '.join(pre_classification['product_mentions'])}")
        if pre_classification.get('pain_severity'):
            context_parts.append(f"Rule-based severity: {pre_classification['pain_severity']}")

    context_str = '\n'.join(context_parts) if context_parts else 'No pre-classification context available.'

    prompt = f"""Classify this signal:

--- SIGNAL (source: {source}) ---
{truncated}
--- END SIGNAL ---

Pre-classification context:
{context_str}

Respond with the JSON classification object:"""

    # Call LLM
    result = llm_json(
        prompt=prompt,
        system_prompt=CLASSIFICATION_SYSTEM_PROMPT,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )

    if not result:
        logger.warning("LLM returned empty result, falling back to pre-classification")
        return _fallback_classification(pre_classification)

    # Validate
    is_valid, errors = validate_classification(result)
    if not is_valid:
        logger.warning(f"LLM classification invalid: {errors}. Fixing...")
        result = _fix_classification(result, errors)

    # Enforce quality tier based on scores
    result = enforce_quality_tier(result)

    # Ensure competitor_mentions is a list
    if isinstance(result.get('competitor_mentions'), str):
        try:
            result['competitor_mentions'] = json.loads(result['competitor_mentions'])
        except Exception:
            result['competitor_mentions'] = []

    result['llm_used'] = True
    result['pre_classification'] = pre_classification or {}

    return result


def classify_batch(signals: list[dict], llm_config: dict = None) -> list[dict]:
    """
    Classify multiple signals in a single LLM call for efficiency.

    Args:
        signals: List of dicts with 'id', 'text', 'source', 'pre_classification'.
        llm_config: LLM configuration dict.

    Returns:
        List of classification dicts, one per signal.
    """
    if len(signals) == 1:
        s = signals[0]
        result = classify_signal(
            text=s['text'],
            source=s.get('source', ''),
            pre_classification=s.get('pre_classification'),
            llm_config=llm_config,
        )
        result['signal_id'] = s['id']
        return [result]

    config = llm_config or {}
    model = config.get('model', 'mimo-v2.6-flash')
    max_tokens = config.get('max_tokens', 10000)
    temperature = config.get('temperature', 0.1)
    timeout = config.get('timeout', 60)

    # Build batch prompt
    signal_blocks = []
    for i, s in enumerate(signals):
        cleaned = clean_text(s['text'])
        truncated = truncate_for_llm(cleaned, max_tokens_estimate=800)
        pre = s.get('pre_classification', {})
        context_parts = []
        if pre.get('pain_hits'):
            context_parts.append(f"pain: {', '.join(pre['pain_hits'][:3])}")
        if pre.get('product_mentions'):
            context_parts.append(f"products: {', '.join(pre['product_mentions'])}")
        ctx = ' | '.join(context_parts) if context_parts else 'no context'

        signal_blocks.append(
            f"### Signal {i+1} (id={s['id']}, source={s.get('source', '?')})\n"
            f"Context: {ctx}\n"
            f"Text: {truncated}\n"
        )

    batch_text = '\n'.join(signal_blocks)

    batch_system = CLASSIFICATION_SYSTEM_PROMPT + """

When classifying multiple signals, respond with a JSON array of classification objects.
Each object must have all the standard fields plus a "signal_id" field matching the input.

Format: [{"signal_id": 1, "pain_category": "...", ...}, {"signal_id": 2, ...}]"""

    prompt = f"""Classify these {len(signals)} signals:

{batch_text}

Respond with a JSON array of {len(signals)} classification objects:"""

    # Try batch LLM call
    result = llm_json(
        prompt=prompt,
        system_prompt=batch_system,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout + 30,  # Extra time for batch
    )

    if not result:
        logger.warning("Batch LLM call failed, falling back to individual classification")
        results = []
        for s in signals:
            r = classify_signal(
                text=s['text'],
                source=s.get('source', ''),
                pre_classification=s.get('pre_classification'),
                llm_config=llm_config,
            )
            r['signal_id'] = s['id']
            results.append(r)
        return results

    # Handle both array and single object responses
    if isinstance(result, dict):
        # LLM returned a single object instead of array
        classifications = [result]
    elif isinstance(result, list):
        classifications = result
    else:
        logger.warning(f"Unexpected batch result type: {type(result)}")
        return classify_batch(signals, llm_config)  # Retry as individual

    # If we got fewer results than signals, fill in with individual calls
    classified_ids = {c.get('signal_id') for c in classifications if c.get('signal_id')}
    for s in signals:
        if s['id'] not in classified_ids:
            logger.warning(f"Missing classification for signal {s['id']}, classifying individually")
            r = classify_signal(
                text=s['text'],
                source=s.get('source', ''),
                pre_classification=s.get('pre_classification'),
                llm_config=llm_config,
            )
            r['signal_id'] = s['id']
            classifications.append(r)

    # Validate and fix each classification
    for c in classifications:
        c = enforce_quality_tier(c)
        if isinstance(c.get('competitor_mentions'), str):
            try:
                c['competitor_mentions'] = json.loads(c['competitor_mentions'])
            except Exception:
                c['competitor_mentions'] = []
        c['llm_used'] = True

    return classifications


def _fallback_classification(pre_classification: dict = None) -> dict:
    """Fall back to rule-based classification when LLM fails."""
    if not pre_classification:
        return {
            'pain_category': 'uncategorized',
            'urgency_score': 0.0,
            'specificity_score': 0.0,
            'buyer_intent': 0.0,
            'quality_tier': 'noise',
            'sentiment': 'neutral',
            'signal_type': 'discussion',
            'location': None,
            'product_category': None,
            'competitor_mentions': [],
            'reasoning': 'LLM classification failed, no pre-classification available',
            'llm_used': False,
            'pre_classification': {},
        }

    # Use pre-classification scores
    category = 'uncategorized'
    if pre_classification.get('product_mentions'):
        product = pre_classification['product_mentions'][0]
        category = f'{product}_related'

    severity = pre_classification.get('pain_severity', 'none')
    if severity == 'high':
        sentiment = 'negative'
    elif severity == 'medium':
        sentiment = 'negative'
    elif severity == 'low':
        sentiment = 'neutral'
    else:
        sentiment = 'neutral'

    result = {
        'pain_category': category,
        'urgency_score': pre_classification.get('pre_urgency', 0.0),
        'specificity_score': pre_classification.get('pre_specificity', 0.0),
        'buyer_intent': pre_classification.get('pre_buyer_intent', 0.0),
        'quality_tier': pre_classification.get('pre_quality_tier', 'noise'),
        'sentiment': sentiment,
        'signal_type': 'discussion',
        'location': None,
        'product_category': (pre_classification.get('product_mentions') or [None])[0],
        'competitor_mentions': [],
        'reasoning': 'LLM classification failed, using rule-based fallback',
        'llm_used': False,
        'pre_classification': pre_classification,
    }

    result = enforce_quality_tier(result)
    return result


def _fix_classification(result: dict, errors: list[str]) -> dict:
    """Fix common LLM classification errors."""
    # Fix quality_tier
    if result.get('quality_tier') not in ('noise', 'bronze', 'silver', 'gold'):
        result['quality_tier'] = 'bronze'

    # Fix scores
    for field in ('urgency_score', 'specificity_score', 'buyer_intent'):
        val = result.get(field)
        if not isinstance(val, (int, float)):
            result[field] = 0.0
        else:
            result[field] = max(0.0, min(1.0, float(val)))

    # Fix sentiment
    if result.get('sentiment') not in ('negative', 'neutral', 'positive'):
        result['sentiment'] = 'neutral'

    # Fix signal_type
    if result.get('signal_type') not in ('complaint', 'question', 'review', 'discussion', 'recommendation'):
        result['signal_type'] = 'discussion'

    # Fix competitor_mentions
    if not isinstance(result.get('competitor_mentions'), list):
        result['competitor_mentions'] = []

    return result
