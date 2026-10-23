"""
Cluster Context Builder - Phase 1

Precomputes market context for a signal cluster BEFORE gap generation.
Replaces live DDG lookups with pre-aggregated, evidence-based context.

Usage:
    from src.engines.cluster_context_builder import build_cluster_context
    context = build_cluster_context(signals)
    # Pass context to gap detector's LLM prompt
"""
import json
import re
import logging
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)

# Path resolution
import sys
from pathlib import Path
TUXO_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(TUXO_DIR))

from src.engines.mention_resolver import resolve_mentions_from_signals
from src.engines.competitor_scorer import score_entities, format_scoring_for_gap


def _extract_pain_phrases(signals: list[dict], max_phrases: int = 8) -> list[str]:
    """
    Extract representative pain phrases from signals.
    Prioritizes signals with high urgency and specific complaints.
    """
    pain_indicators = [
        'frustrated', 'annoying', 'hate', 'terrible', 'broken', 'nightmare',
        'impossible', 'can\'t', 'unable', 'waste', 'horrible', 'sucks',
        'worst', 'pain', 'struggling', 'desperate', 'need help',
    ]

    scored_signals = []
    for s in signals:
        text = (s.get('content') or '') + ' ' + (s.get('title') or '')
        text_lower = text.lower()
        urgency = float(s.get('urgency_score', 0) or 0)

        # Score: urgency + pain word density
        pain_hits = sum(1 for p in pain_indicators if p in text_lower)
        score = urgency + (pain_hits * 0.1)

        if score > 0.2 and len(text) > 30:
            scored_signals.append((score, text))

    scored_signals.sort(key=lambda x: -x[0])

    phrases = []
    seen_fragments = set()
    for _, text in scored_signals[:max_phrases * 2]:
        # Extract a clean snippet (first 2 sentences or 150 chars)
        snippet = text.replace('\n', ' ').strip()
        # Find sentence boundaries
        for sep in ['. ', '! ', '? ', '.\n']:
            idx = snippet.find(sep)
            if 20 < idx < 150:
                snippet = snippet[:idx + 1]
                break
        else:
            snippet = snippet[:150].strip()
            if not snippet.endswith('.'):
                snippet += '...'

        # Dedupe by first 40 chars
        fragment_key = snippet[:40].lower()
        if fragment_key not in seen_fragments:
            seen_fragments.add(fragment_key)
            phrases.append(snippet)
            if len(phrases) >= max_phrases:
                break

    return phrases


def _extract_who_is_affected(signals: list[dict], max_personas: int = 4) -> list[str]:
    """
    Extract who is affected from signal content.
    Looks for role/company indicators.
    """
    persona_patterns = [
        (r'\b(freelancer|freelance)\b', 'freelancers'),
        (r'\b(startup|founder|co-?founder)\b', 'startup founders'),
        (r'\b(small business|smb|small team)\b', 'small business owners'),
        (r'\b(developer|dev|engineer|programmer)\b', 'developers'),
        (r'\b(designer|ux|ui designer)\b', 'designers'),
        (r'\b(marketer|marketing|growth)\b', 'marketers'),
        (r'\b(agencies|agency owner)\b', 'agency owners'),
        (r'\b(ecommerce|e-?commerce|merchant|shop owner|store owner)\b', 'ecommerce merchants'),
        (r'\b(saas|software company)\b', 'SaaS operators'),
        (r'\b(remote worker|remote team|distributed team)\b', 'remote workers'),
        (r'\b(student|university|college)\b', 'students'),
        (r'\b(consultant|consulting)\b', 'consultants'),
        (r'\b(project manager|pm|product manager)\b', 'project/product managers'),
        (r'\b(hiring|recruit|hr |human resource)\b', 'hiring managers'),
        (r'\b(real estate|realtor|property)\b', 'real estate professionals'),
        (r'\b(finance|accountant|bookkeep)\b', 'finance professionals'),
        (r'\b(content creator|creator|influencer)\b', 'content creators'),
        (r'\b(enterprise|corporate|large company)\b', 'enterprise teams'),
    ]

    persona_counts = Counter()
    for s in signals:
        text = ((s.get('content') or '') + ' ' + (s.get('title') or '')).lower()
        for pattern, label in persona_patterns:
            if re.search(pattern, text):
                persona_counts[label] += 1

    return [label for label, _ in persona_counts.most_common(max_personas)]


def _extract_money_and_time(signals: list[dict]) -> dict:
    """Extract money amounts and time wastes mentioned in signals."""
    money_pattern = r'\$[\d,]+(?:\.\d{2})?(?:k|K|million|M)?'
    time_pattern = r'(\d+)\s*(hours?|hrs?|minutes?|mins?|days?|weeks?|months?)\s*(?:per|a|every|/)?\s*(day|week|month|year)?'

    money_mentions = []
    time_mentions = []

    for s in signals:
        text = (s.get('content') or '') + ' ' + (s.get('title') or '')

        for m in re.findall(money_pattern, text):
            if m not in money_mentions:
                money_mentions.append(m)

        for match in re.findall(time_pattern, text.lower()):
            amount, unit, period = match
            time_mentions.append(f"{amount} {unit}" + (f" per {period}" if period else ""))

    return {
        "money_mentions": money_mentions[:5],
        "time_mentions": time_mentions[:5],
    }


def _query_cluster_entities(signals: list[dict]) -> list[dict]:
    """Query DB for entities across this cluster's signals."""
    signal_ids = [s['id'] for s in signals if s.get('id')]
    if not signal_ids:
        return []
    
    try:
        from shared.remote_db import RemoteDB
        db = RemoteDB()
        result = db._request('get_cluster_entities', {'signal_ids': signal_ids[:200]})
        return result.get('entities', [])
    except Exception as e:
        logger.debug(f"DB entity query failed (using in-memory): {e}")
        return []


def _merge_db_entities(mention_data: dict, db_entities: list[dict]) -> dict:
    """Merge DB-resolved entities into in-memory mention data. DB takes priority."""
    # Build lookup from DB results
    db_by_name = {}
    for e in db_entities:
        db_by_name[e['canonical_name'].lower()] = e
    
    # Merge competitors
    existing_names = {c['name'].lower(): c for c in mention_data.get('competitors', [])}
    for e in db_entities:
        name_lower = e['canonical_name'].lower()
        etype = e.get('entity_type', 'competitor')
        bucket = mention_data.get(f"{etype}s", mention_data.get('competitors', []))
        
        if name_lower in existing_names:
            # Update existing with DB stats
            existing = existing_names[name_lower]
            existing['mention_count'] = max(existing.get('mention_count', 0), int(e.get('mention_count', 0)))
            existing['author_count'] = max(existing.get('author_count', 0), int(e.get('author_count', 0)))
            existing['negative_rate'] = float(e.get('negative_rate', existing.get('negative_rate', 0)))
            existing['source'] = 'db+memory'
        else:
            # Add new from DB
            entry = {
                'name': e['canonical_name'],
                'type': etype,
                'mention_count': int(e.get('mention_count', 0)),
                'author_count': int(e.get('author_count', 0)),
                'negative_rate': float(e.get('negative_rate', 0)),
                'sample_pain_phrases': [],
                'signal_ids': [],
                'source': 'db',
            }
            bucket.append(entry)
    
    # Re-sort buckets
    for key in ['competitors', 'substitutes', 'platforms', 'tools']:
        if key in mention_data:
            mention_data[key].sort(key=lambda x: x.get('mention_count', 0), reverse=True)
    
    return mention_data


def build_cluster_context(category: str, signals: list[dict],
                           cluster_id: str = None) -> dict:
    """
    Build complete market context for a signal cluster.

    This is the artifact that gap_detector.py receives instead of doing
    its own competitor discovery.

    Tries DB first (Phase 2), falls back to in-memory resolution (Phase 1).

    Args:
        category: pain_category for this cluster
        signals: list of signal dicts in this cluster
        cluster_id: optional identifier

    Returns:
        Structured context object ready for LLM gap generation.
    """
    if not signals:
        return {"error": "empty cluster"}

    # 1. Try DB-resolved entities first (Phase 2)
    db_entities = _query_cluster_entities(signals)
    
    # 2. In-memory resolution (always run as supplement/fallback)
    mention_data = resolve_mentions_from_signals(signals)

    # 3. Merge DB entities with in-memory results
    # DB takes priority for entities that exist in both
    if db_entities:
        mention_data = _merge_db_entities(mention_data, db_entities)

    # 2. Extract pain phrases
    pain_phrases = _extract_pain_phrases(signals)

    # 3. Extract who is affected
    who = _extract_who_is_affected(signals)

    # 4. Extract money/time
    metrics = _extract_money_and_time(signals)

    # 5. Compute basic stats
    urgencies = [float(s.get('urgency_score', 0) or 0) for s in signals]
    avg_urgency = sum(urgencies) / len(urgencies) if urgencies else 0
    sources = Counter(s.get('source', 'unknown') for s in signals)

    # 6. Build sample quotes with provenance
    sample_quotes = []
    for s in sorted(signals, key=lambda x: -float(x.get('urgency_score', 0) or 0))[:5]:
        text = (s.get('content') or s.get('title') or '')[:200]
        if text:
            sample_quotes.append({
                "text": text.replace('\n', ' ').strip(),
                "source": s.get('source', 'unknown'),
                "author": s.get('author'),
                "url": s.get('source_url', ''),
                "urgency": s.get('urgency_score', 0),
            })

    # 7. Compute confidence (how rich is this context?)
    confidence_factors = [
        len(mention_data['competitors']) > 0,  # Has competitor data
        len(mention_data['substitutes']) > 0,   # Has substitute data
        len(pain_phrases) > 2,                   # Has specific pain
        len(who) > 0,                            # Knows who's affected
        mention_data['coverage'] > 0.3,          # Good mention coverage
        len(signals) >= 10,                      # Decent sample size
    ]
    confidence = sum(confidence_factors) / len(confidence_factors)

    # 8. Score competitors (Phase 3)
    all_entities = mention_data['competitors'] + mention_data['substitutes']
    if all_entities:
        scored = score_entities(all_entities, signals)
        scoring_summary = format_scoring_for_gap(scored[:10], top_n=5)
    else:
        scoring_summary = {'top_competitors': [], 'threat_assessment': 'No data', 'opportunity_signal': 'unknown'}

    context = {
        "cluster_id": cluster_id or f"cluster_{category}",
        "signal_count": len(signals),
        "category": category,

        # The core evidence
        "competitors": mention_data['competitors'][:8],
        "substitutes": mention_data['substitutes'][:5],
        "platforms": mention_data['platforms'][:3],
        "tools": mention_data['tools'][:5],

        # Pain evidence
        "pain_phrases": pain_phrases,
        "who_is_affected": who,
        "money_mentions": metrics['money_mentions'],
        "time_mentions": metrics['time_mentions'],

        # Provenance
        "sample_quotes": sample_quotes,
        "source_distribution": dict(sources.most_common(5)),

        # Quality
        "avg_urgency": round(avg_urgency, 2),
        "mention_coverage": mention_data['coverage'],
        "confidence": round(confidence, 2),
        
        # Scoring (Phase 3)
        "top_scored": scoring_summary.get('top_competitors', []),
        "threat_assessment": scoring_summary.get('threat_assessment', ''),
        "opportunity_signal": scoring_summary.get('opportunity_signal', 'unknown'),
    }

    logger.info(
        f"Built context for '{category}': {len(signals)} signals, "
        f"{len(mention_data['competitors'])} competitors, "
        f"{len(mention_data['substitutes'])} substitutes, "
        f"confidence={confidence:.2f}"
    )

    return context


def format_context_for_llm(context: dict) -> str:
    """
    Format the cluster context into a string block for the LLM prompt.
    This replaces the raw signal dump in gap_detector.py.
    """
    lines = []

    lines.append(f"=== CLUSTER: {context['category']} ===")
    lines.append(f"Signals: {context['signal_count']} | Avg urgency: {context['avg_urgency']} | Confidence: {context['confidence']}")
    lines.append("")

    # Competitors
    if context.get('competitors'):
        lines.append("NAMED COMPETITORS (from user signals):")
        for c in context['competitors'][:5]:
            neg = f", {c['negative_rate']:.0%} negative" if c.get('negative_rate') else ""
            lines.append(f"  - {c['name']} ({c['mention_count']} mentions, {c['author_count']} authors{neg})")
            for phrase in c.get('sample_pain_phrases', [])[:1]:
                lines.append(f"    Example: \"{phrase}\"")
        lines.append("")

    # Substitutes
    if context.get('substitutes'):
        lines.append("CURRENT SUBSTITUTES (what people use instead):")
        for s in context['substitutes'][:4]:
            lines.append(f"  - {s['name']} ({s['mention_count']} mentions)")
        lines.append("")

    # Threat assessment (Phase 3)
    if context.get('threat_assessment'):
        lines.append(f"MARKET ASSESSMENT: {context['threat_assessment']}")
        if context.get('top_scored'):
            lines.append("Scored competitors:")
            for sc in context['top_scored'][:3]:
                lines.append(f"  - {sc['name']}: score={sc.get('score', 0):.2f}, {sc.get('mentions', 0)} mentions, {sc.get('negative_rate', 0):.0%} negative, threat={sc.get('threat', '?')}")
        lines.append("")

    # Who is affected
    if context.get('who_is_affected'):
        lines.append(f"AFFECTED USERS: {', '.join(context['who_is_affected'])}")
        lines.append("")

    # Pain phrases
    if context.get('pain_phrases'):
        lines.append("PAIN EVIDENCE:")
        for p in context['pain_phrases'][:4]:
            lines.append(f"  - \"{p}\"")
        lines.append("")

    # Money/time
    if context.get('money_mentions'):
        lines.append(f"MONEY MENTIONED: {', '.join(context['money_mentions'][:3])}")
    if context.get('time_mentions'):
        lines.append(f"TIME WASTED: {', '.join(context['time_mentions'][:3])}")
    if context.get('money_mentions') or context.get('time_mentions'):
        lines.append("")

    # Sample quotes
    if context.get('sample_quotes'):
        lines.append("TOP SIGNAL QUOTES (by urgency):")
        for q in context['sample_quotes'][:3]:
            lines.append(f"  [{q.get('source', '?')}, urgency={q.get('urgency', 0)}] \"{q['text'][:150]}\"")
        lines.append("")

    return '\n'.join(lines)
