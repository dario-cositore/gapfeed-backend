"""
Enrichment pipeline — the full A→B→C→D→E pipeline.

Usage:
    from app.enrichment import enrich_signal

    result = enrich_signal(
        text="Stripe froze my $12k, I'm in Austin, been using them 2 years",
        source_url="https://reddit.com/r/smallbusiness/post123",
        source_type="reddit",
    )
"""

import logging
from typing import Optional

from .extractors import extract_all
from .rules import apply_rules
from .confidence import score_enriched_profile, score_field_confidence
from .llm_reasoner import llm_enrich
from .compliance_filter import compliance_check, redact_pii

logger = logging.getLogger(__name__)


def enrich_signal(
    text: str,
    source_url: str = "",
    source_type: str = "other",
    source_domain: str = None,
    vertical: str = "general",
    llm_budget_remaining: int = 5,
    skip_llm: bool = False,
) -> dict:
    """
    Run the full enrichment pipeline on a raw signal.

    Args:
        text: The raw signal text (title + body)
        source_url: Link to original content
        source_type: reddit, hn, web_search, etc.
        source_domain: Extracted domain (e.g., reddit.com)
        vertical: Which vertical this belongs to
        llm_budget_remaining: LLM calls left this round
        skip_llm: If True, skip LLM stage entirely

    Returns:
        {
            'profile': dict (the enriched profile, or None if discarded),
            'extracted': dict (stage A output),
            'rules': dict (stage B output),
            'scores': dict (stage C output),
            'llm_used': bool,
            'compliance': dict (stage E output),
            'discard_reason': str or None,
        }
    """
    result = {
        'profile': None,
        'extracted': {},
        'rules': {},
        'scores': {},
        'llm_used': False,
        'compliance': {},
        'discard_reason': None,
    }

    if not text or len(text.strip()) < 30:
        result['discard_reason'] = 'Text too short for enrichment'
        return result

    # --- Stage A: Deterministic extraction ---
    extracted = extract_all(text, source_url)
    result['extracted'] = extracted

    # --- Stage B: Rule-based inference ---
    rules = apply_rules(extracted, text)
    result['rules'] = rules

    # --- Stage C: Confidence scoring ---
    freshness_hours = 0.0  # Default, caller can override
    scores = score_enriched_profile(rules, extracted, source_domain, freshness_hours)
    result['scores'] = scores

    # --- Stage D: LLM adjudication (if needed and budget allows) ---
    enriched_fields = rules
    if not skip_llm and scores.get('profile_confidence', 0) < 0.7:
        llm_result = llm_enrich(
            text=text,
            extracted=extracted,
            rule_results=rules,
            llm_budget_remaining=llm_budget_remaining,
        )

        if llm_result:
            if llm_result.get('discard'):
                result['discard_reason'] = llm_result.get('discard_reason', 'LLM discarded')
                return result
            enriched_fields = llm_result
            result['llm_used'] = True

            # Re-score after LLM enrichment
            scores = score_enriched_profile(enriched_fields, extracted, source_domain, freshness_hours)
            result['scores'] = scores

    # Helper: extract value from field (handles both dict and string formats)
    def _val(field_data, default=None):
        if isinstance(field_data, dict):
            return field_data.get('value', default)
        elif isinstance(field_data, str):
            return field_data if field_data else default
        return default

    # --- Build profile dict ---
    import hashlib
    import uuid
    from datetime import datetime, timezone

    # Dedupe fingerprint
    text_chunk = text[:500].lower().strip()
    author = "anon"
    time_bucket = "unknown"
    raw = f"{source_url.lower().strip()}|{text_chunk}|{author}|{time_bucket}"
    fingerprint = hashlib.sha256(raw.encode()).hexdigest()

    profile = {
        'profile_id': f"prof_{uuid.uuid4().hex[:12]}",
        'raw_signal_id': '',  # Set by caller
        'event_id': None,
        'pain_description': enriched_fields.get('pain_description', text[:200])
            if isinstance(enriched_fields.get('pain_description'), str)
            else _val(enriched_fields.get('pain_description'), text[:200]),
        'pain_category': _val(enriched_fields.get('pain_category'), 'uncategorized'),
        'urgency': _val(enriched_fields.get('urgency'), 5),
        'signal_type': _val(enriched_fields.get('signal_type'), 'discussion'),
        'source_url': source_url,
        'location': enriched_fields.get('location', {}) if isinstance(enriched_fields.get('location'), dict) else {},
        'business_context': enriched_fields.get('business_context', {}) if isinstance(enriched_fields.get('business_context'), dict) else {},
        'business_size': enriched_fields.get('business_size', {}) if isinstance(enriched_fields.get('business_size'), dict) else {},
        'intent': enriched_fields.get('intent', {}) if isinstance(enriched_fields.get('intent'), dict) else {},
        'personalization_data': enriched_fields.get('personalization_data', [])
            if isinstance(enriched_fields.get('personalization_data'), list) else [],
        'confidence': scores.get('profile_confidence', 0),
        'actionability_score': scores.get('actionability', 0),
        'first_seen_at': datetime.now(timezone.utc).isoformat(),
        'last_seen_at': datetime.now(timezone.utc).isoformat(),
        'freshness_hours': freshness_hours,
        'is_spike_related': False,
        'dedupe_fingerprint': fingerprint,
        'cluster_id': None,
        'vertical': vertical,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'discard_reason': None,
    }

    # --- Stage E: Compliance check ---
    compliance = compliance_check(profile, extracted, text, vertical)
    result['compliance'] = compliance

    if not compliance['passed']:
        result['discard_reason'] = '; '.join(compliance['reasons'])
        profile['discard_reason'] = result['discard_reason']
        result['profile'] = profile  # Store with discard reason for logging
        return result

    # Redact PII from pain_description
    profile['pain_description'] = redact_pii(profile['pain_description'])

    result['profile'] = profile
    return result
