"""
LLM adjudication layer — Stage D of enrichment.

Only fires when deterministic extraction (A) + rules (B) can't resolve
a field confidently. The LLM handles:
- missing critical fields
- ambiguous classifications
- confidence synthesis
- evidence-backed inference

Uses shared/llm_client.py for LLM calls. Structured JSON output enforced.
"""

import json
import re
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Add project root for shared module access
# File: tuxo/TheRealAgents/Agent_1/app/enrichment/llm_reasoner.py
# Need: tuxo/ (5 levels up from __file__)
import sys
from pathlib import Path
_DEPTH = Path(__file__).resolve()
for _ in range(5):
    _DEPTH = _DEPTH.parent
sys.path.insert(0, str(_DEPTH))

from shared.llm_client import llm_call, llm_json

# ---------------------------------------------------------------------------
# Taxonomy lists (embedded in prompts for LLM context)
# ---------------------------------------------------------------------------

_PAIN_CATEGORIES_LIST = """payment_hold, payment_failure, checkout_failure, chargeback_issue,
refund_dispute, billing_spike, pricing_change_pain, account_ban, account_review_delay,
account_lockout, feature_breakage, api_breaking_change, service_outage, performance_issue,
data_loss, support_unresponsive, support_unhelpful, lead_shortage, ad_account_ban,
shipping_delay, compliance_confusion, competitor_complaint, missing_feature,
switching_pain, general_frustration, uncategorized"""

_INTENT_LIST = """seeking_help, seeking_vendor, seeking_workaround, venting_only,
considering_switch, request_recommendation, warning_others, asking_for_legal_help"""

_BUSINESS_SIZE_LIST = "solo, small_business, mid_business, enterprise, unknown"


# ---------------------------------------------------------------------------
# Extraction prompt builder
# ---------------------------------------------------------------------------

def _build_extraction_prompt(text: str, extracted: dict, rule_results: dict,
                              missing_fields: list[str]) -> str:
    """Build the LLM prompt for enrichment adjudication."""

    # What the deterministic stages already found
    money = extracted.get('money_mentions', [])
    locations = extracted.get('location_mentions', [])
    products = extracted.get('product_mentions', [])
    pain_verbs = extracted.get('pain_verbs', {})
    durations = extracted.get('duration_mentions', [])
    intents = extracted.get('intent_markers', [])

    existing_context = f"""DETERMINISTIC EXTRACTION:
- Money mentions: {money if money else 'none'}
- Location mentions: {locations if locations else 'none'}
- Product mentions: {products if products else 'none'}
- Pain verbs: high={pain_verbs.get('high', [])}, medium={pain_verbs.get('medium', [])}
- Duration mentions: {durations if durations else 'none'}
- Intent markers: {intents if intents else 'none'}
- Pain severity: {extracted.get('pain_severity', 'none')}

RULE INFERENCE:
- Pain category: {rule_results.get('pain_category', {}).get('value', 'unknown')}
- Business context: {rule_results.get('business_context', {}).get('value', 'unknown')}
- Business size: {rule_results.get('business_size', {}).get('value', 'unknown')}
- Signal type: {rule_results.get('signal_type', {}).get('value', 'unknown')}
- Intent: {rule_results.get('intent', {}).get('value', 'unknown')}
- Urgency: {rule_results.get('urgency', {}).get('value', 'unknown')}"""

    fields_instruction = ", ".join(missing_fields) if missing_fields else "all fields"

    return f"""You are a data enrichment analyst. Your job is to extract structured intelligence from a raw internet post.

SOURCE TEXT:
\"\"\"{text[:2000]}\"\"\"

{existing_context}

The deterministic extraction and rule engine could not confidently resolve these fields: {fields_instruction}

YOUR TASK:
Analyze the source text and fill in the missing fields. For each field you provide:
- value: the extracted/inferred value
- quality: "confirmed" (user stated it), "inferred" (reasoned from context), or "guessed" (best estimate)
- confidence: 0.0-1.0 how confident you are
- evidence: list of exact quotes from the text that support your answer
- reasoning: ONE short sentence explaining your inference

PAIN CATEGORY (pick one): {_PAIN_CATEGORIES_LIST}
INTENT (pick one): {_INTENT_LIST}
BUSINESS SIZE (pick one): {_BUSINESS_SIZE_LIST}
URGENCY: integer 1-10

RULES:
- Only infer if you have evidence in the text. Do NOT invent facts.
- If a field truly cannot be determined, set quality="unknown" and confidence=0.0.
- Location: extract city, state, country if mentioned. If only country is implied, use that.
- Business context: what platform/industry is this person in? Use product mentions + context clues.
- Evidence must be EXACT QUOTES from the text, not paraphrases.

RESPOND IN VALID JSON ONLY:
{{
  "pain_description": "one sentence summarizing the pain",
  "pain_category": "<from list above>",
  "urgency": <1-10>,
  "signal_type": "complaint|want|question|review|discussion",
  "location": {{
    "value": "<city, state, country or null>",
    "quality": "confirmed|inferred|guessed|unknown",
    "confidence": <0.0-1.0>,
    "evidence": ["<exact quote>"],
    "reasoning": "<one sentence>"
  }},
  "business_context": {{
    "value": "<context string or null>",
    "quality": "confirmed|inferred|guessed|unknown",
    "confidence": <0.0-1.0>,
    "evidence": ["<exact quote>"],
    "reasoning": "<one sentence>"
  }},
  "business_size": {{
    "value": "<solo|small_business|mid_business|enterprise or null>",
    "quality": "confirmed|inferred|guessed|unknown",
    "confidence": <0.0-1.0>,
    "evidence": ["<exact quote>"],
    "reasoning": "<one sentence>"
  }},
  "intent": {{
    "value": "<from list above or null>",
    "quality": "confirmed|inferred|guessed|unknown",
    "confidence": <0.0-1.0>,
    "evidence": ["<exact quote>"],
    "reasoning": "<one sentence>"
  }},
  "personalization_data": ["<key detail 1>", "<key detail 2>"],
  "confidence": <overall 0.0-1.0>,
  "discard": false,
  "discard_reason": null
}}"""


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_llm_response(response: str) -> Optional[dict]:
    """Parse LLM response, handling both clean JSON and markdown-wrapped JSON."""
    if not response:
        return None

    # Try direct JSON parse first
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object in the response
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.error(f"Could not parse LLM response as JSON: {response[:300]}")
    return None


def _normalize_llm_output(data: dict) -> dict:
    """
    Normalize LLM output to ensure all fields have the expected dict structure.
    The LLM sometimes returns strings instead of {value, quality, confidence, evidence} dicts.
    """
    field_names = ['location', 'business_context', 'business_size', 'intent']

    for field_name in field_names:
        field = data.get(field_name)
        if isinstance(field, str):
            # Convert string to dict structure
            data[field_name] = {
                'value': field if field and field != 'null' else None,
                'quality': 'inferred',
                'confidence': 0.6,
                'evidence': [],
                'reasoning': f'LLM returned string directly',
            }
        elif isinstance(field, dict):
            # Ensure all sub-keys exist
            field.setdefault('value', None)
            field.setdefault('quality', 'unknown')
            field.setdefault('confidence', 0.0)
            field.setdefault('evidence', [])
            field.setdefault('reasoning', '')
        elif field is None:
            data[field_name] = {
                'value': None,
                'quality': 'unknown',
                'confidence': 0.0,
                'evidence': [],
                'reasoning': '',
            }

    # Normalize urgency (should be int)
    urgency = data.get('urgency')
    if isinstance(urgency, str):
        try:
            data['urgency'] = int(urgency)
        except ValueError:
            data['urgency'] = 5
    elif urgency is None:
        data['urgency'] = 5

    # Normalize signal_type
    signal_type = data.get('signal_type')
    if not signal_type or not isinstance(signal_type, str):
        data['signal_type'] = 'discussion'

    # Normalize pain_description
    if not data.get('pain_description'):
        data['pain_description'] = 'No description provided'

    # Normalize pain_category
    if not data.get('pain_category'):
        data['pain_category'] = 'uncategorized'

    return data


def _validate_llm_output(data: dict) -> bool:
    """Validate that LLM output has required structure."""
    required_top = ['pain_description', 'pain_category', 'urgency', 'signal_type']
    required_fields = ['location', 'business_context', 'business_size', 'intent']

    for key in required_top:
        if key not in data:
            logger.warning(f"LLM output missing required field: {key}")
            return False

    for key in required_fields:
        if key not in data:
            logger.warning(f"LLM output missing field: {key}")
            return False
        field = data[key]
        if not isinstance(field, dict):
            logger.warning(f"LLM field {key} is not a dict: {type(field)}")
            return False
        for sub_key in ['value', 'quality', 'confidence', 'evidence']:
            if sub_key not in field:
                logger.warning(f"LLM field {key} missing sub-field: {sub_key}")
                return False

    return True


# ---------------------------------------------------------------------------
# Merge LLM results with deterministic results
# ---------------------------------------------------------------------------

def _merge_results(rule_results: dict, llm_data: dict) -> dict:
    """
    Merge LLM adjudication with rule-based results.
    Rules win on fields they resolved confidently.
    LLM fills in gaps and adds evidence.
    """
    merged = {}

    # For each field, prefer rule result if quality is 'inferred' or better,
    # otherwise use LLM result
    for field_name in ['pain_category', 'business_context', 'business_size', 'intent', 'urgency', 'signal_type']:
        rule_val = rule_results.get(field_name, {})
        llm_val = llm_data.get(field_name, {})

        # If rules resolved it with a real value, keep it
        if rule_val.get('quality') in ('inferred', 'confirmed') and rule_val.get('value'):
            merged[field_name] = rule_val
            # Augment with LLM evidence if available
            if isinstance(llm_val, dict) and llm_val.get('evidence'):
                existing_ev = merged[field_name].get('evidence', [])
                merged[field_name]['evidence'] = list(set(existing_ev + llm_val['evidence']))
        else:
            # Use LLM result
            if isinstance(llm_val, dict):
                merged[field_name] = llm_val
            elif field_name == 'urgency' and isinstance(llm_val, (int, float)):
                merged[field_name] = {
                    'value': int(llm_val),
                    'quality': 'inferred',
                    'method': 'llm',
                    'confidence': 0.7,
                    'evidence': [],
                    'reasoning': 'LLM urgency assessment',
                }
            else:
                merged[field_name] = rule_val

    # Pain description always comes from LLM (it writes better summaries)
    merged['pain_description'] = llm_data.get('pain_description', '')

    # Personalization data from LLM
    merged['personalization_data'] = llm_data.get('personalization_data', [])

    # Overall confidence: LLM's or compute from fields
    merged['confidence'] = llm_data.get('confidence', 0.5)

    return merged


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def llm_enrich(text: str, extracted: dict, rule_results: dict,
               missing_fields: list[str] = None,
               llm_budget_remaining: int = 5) -> Optional[dict]:
    """
    Call LLM to adjudicate enrichment for fields the rules couldn't resolve.

    Args:
        text: The raw signal text
        extracted: Output from extractors.extract_all()
        rule_results: Output from rules.apply_rules()
        missing_fields: Which fields need LLM attention (default: all)
        llm_budget_remaining: How many LLM calls we have left this round

    Returns:
        Merged enrichment dict, or None if LLM unavailable/budget exceeded.
    """
    if llm_budget_remaining <= 0:
        logger.warning("LLM budget exhausted, skipping LLM enrichment")
        return None

    # Default: enrich all fields
    if missing_fields is None:
        missing_fields = ['pain_description', 'pain_category', 'urgency',
                         'location', 'business_context', 'business_size', 'intent']

    # Filter to only fields that actually need help
    needs_llm = []
    for field in missing_fields:
        rule_val = rule_results.get(field, {})
        if isinstance(rule_val, dict):
            if rule_val.get('quality') in ('unknown', 'guessed') or not rule_val.get('value'):
                needs_llm.append(field)
        elif field == 'pain_description':
            needs_llm.append(field)

    if not needs_llm:
        logger.info("All fields resolved by rules, skipping LLM")
        return None

    logger.info(f"LLM adjudication needed for: {needs_llm}")

    # Build prompt
    prompt = _build_extraction_prompt(text, extracted, rule_results, needs_llm)

    system_prompt = """You are a precise data enrichment analyst. You extract structured intelligence from raw internet posts.
You NEVER invent facts. You only report what the text actually says or what can be reasonably inferred.
You cite evidence as exact quotes. You are conservative with confidence scores.
You respond ONLY in valid JSON."""

    # Call LLM
    try:
        response = llm_call(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=10000,
            temperature=0.1,
            timeout=60,
        )

        if not response:
            logger.error("LLM returned empty response")
            return None

        # Parse
        llm_data = _parse_llm_response(response)
        if not llm_data:
            return None

        # Normalize fields (LLM sometimes returns strings instead of dicts)
        llm_data = _normalize_llm_output(llm_data)

        # Validate structure
        if not _validate_llm_output(llm_data):
            logger.error("LLM output failed validation")
            return None

        # Check discard decision
        if llm_data.get('discard'):
            logger.info(f"LLM decided to discard: {llm_data.get('discard_reason')}")
            return {'discard': True, 'discard_reason': llm_data.get('discard_reason')}

        # Merge with rule results
        merged = _merge_results(rule_results, llm_data)
        merged['_llm_used'] = True
        merged['_llm_fields'] = needs_llm

        return merged

    except Exception as e:
        logger.error(f"LLM enrichment failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Selective LLM call (for specific fields only)
# ---------------------------------------------------------------------------

def llm_classify_pain(text: str, extracted: dict) -> Optional[dict]:
    """
    Lightweight LLM call: just classify pain category and urgency.
    Used as a fast pre-filter when full enrichment isn't needed.
    """
    prompt = f"""Classify this internet post. Return JSON only.

TEXT: \"\"\"{text[:1000]}\"\"\"

Extracted: money={extracted.get('money_mentions', [])}, products={extracted.get('product_mentions', [])}, pain={extracted.get('pain_severity', 'none')}

Return:
{{"pain_category": "<from: payment_hold, account_ban, service_outage, billing_spike, feature_breakage, support_unresponsive, missing_feature, general_frustration, uncategorized>",
  "urgency": <1-10>,
  "is_actionable": <true/false>}}"""

    try:
        response = llm_call(prompt=prompt, max_tokens=1000, temperature=0.1)
        if response:
            return _parse_llm_response(response)
    except Exception as e:
        logger.error(f"Quick classify failed: {e}")

    return None
