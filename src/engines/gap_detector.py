"""
Gap Detector - Core Product Logic

Takes Maya's classified signals and clusters them into gaps.
Each gap = a validated problem area with evidence, ready for the "what to build" feed.

Pipeline:
1. Pull classified signals (gold/silver, no gap_id yet)
2. Pre-cluster by pain_category (cheap grouping)
3. Build cluster market context (competitors, substitutes, pain phrases)
4. LLM refines each cluster into a gap using structured evidence
5. Create gap record, link signals via gap_id

No DDG. No web lookups. All evidence comes from Maya's extracted data.

Usage:
    from src.engines.gap_detector import run_gap_detection
    stats = run_gap_detection(vertical='immigration', batch_size=100)
"""
import json
import re
import logging
import sys
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)

# Path resolution
TUXO_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(TUXO_DIR))

from shared.remote_db import RemoteDB
from src.engines.gap_llm import gap_llm_json
from src.engines.cluster_context_builder import build_cluster_context, format_context_for_llm


# ─── Text Sanitizer ──────────────────────────────────────────────

# Compound adjectives that scream "AI wrote this"
_AI_COMPOUNDS = [
    (r'\bmobile-first\b', 'phone-based'),
    (r'\blow-to-moderate\b', 'low and mid'),
    (r'\bend-to-end\b', 'full'),
    (r'\bout-of-the-box\b', 'ready to use'),
    (r'\bhigh-quality\b', 'good'),
    (r'\bdata-driven\b', 'informed'),
    (r'\buser-friendly\b', 'easy'),
    (r'\bcost-effective\b', 'cheap'),
    (r'\bwell-established\b', 'big'),
    (r'\bnext-generation\b', 'new'),
    (r'\bpre-written\b', 'ready'),
    (r'\bpre-built\b', 'ready'),
    (r'\breal-time\b', 'live'),
    (r'\bfull-stack\b', 'full'),
    (r'\bopen-source\b', 'open source'),
    (r'\bwhite-label\b', 'resellable'),
    (r'\bself-serve\b', 'self service'),
]

_AI_PHRASES = [
    (r'\bnavigating the .+ maze\b', None),  # "navigating the legal maze" -> delete
    (r'\bin the realm of\b', 'in'),
    (r'\bin terms of\b', 'for'),
    (r'\bthe fact of the matter is that\b', ''),
    (r"\bit's worth noting that\b", ''),
    (r'\bat the end of the day\b', ''),
    (r'\bparadigm shift\b', 'change'),
    (r'\bleverage\b', 'use'),
    (r'\bsynergy\b', ''),
    (r'\bstreamline\b', 'simplify'),
    (r'\bempower\b', 'help'),
    (r'\bunlock\b', 'get'),
    (r'\bdelve into\b', 'look at'),
    (r'\blandscape\b', 'space'),
    (r'\becosystem\b', 'market'),
    (r'\bseamlessly\b', ''),
    (r'\brobust\b', 'solid'),
    (r'\bscalable\b', 'scales'),
    (r'\bhollistic\b', 'full'),
    (r'\btriage process\b', 'sorting'),
    (r'\bco-pilot\b', 'helper'),
    (r'\bautomates the\b', 'handles the'),
    (r'\breplacing the overwhelming\b', 'instead of the painful'),
]


def sanitize_text(text: str) -> str:
    """Remove AI tells from generated text. Run on all LLM output."""
    if not text:
        return text

    # Remove em dashes and en dashes (replace with comma or period)
    text = text.replace('\u2014', ', ').replace('\u2013', ', ')
    text = text.replace(' -- ', ', ')

    # Replace compound adjectives
    for pattern, replacement in _AI_COMPOUNDS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Remove AI phrases
    for pattern, replacement in _AI_PHRASES:
        if replacement is None:
            # Delete the whole match
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        else:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)

    # Fix orphaned punctuation from deletions
    text = re.sub(r' ,', ',', text)
    text = re.sub(r',,', ',', text)
    text = re.sub(r' \.', '.', text)
    text = re.sub(r'\.\.', '.', text)

    return text.strip()


# ─── Gap Generation Prompt (Phase 1 - Evidence-Based) ────────────

GAP_SYSTEM_PROMPT = """You are a startup founder explaining a market opportunity to a friend over coffee. Casual, direct, no bullshit.

You MUST respond with a valid JSON object. No other text before or after the JSON.

The JSON must have these exact fields:
{
  "title": "<max 80 chars. Write it like you'd title a Notion doc or a tweet. Sharp, specific. Examples:
    - 'Shopify merchants lose $8k+ to return scams with no recourse'
    - 'Freelancers can't track visa timelines across 4 different government portals'
    - 'Small teams waste 10+ hours/week manually reconciling Stripe payouts'>",

  "description": "<Write this like you're explaining the opportunity to a friend. 2-4 sentences max. Cover: who's hurting, what they tried that sucks, what they're doing instead, why now matters. Use the evidence provided. Name real tools from the evidence. Include numbers when you have them. Sound like a human, not a McKinsey report.>",

  "category": "<specific subcategory. E.g. 'ecommerce fraud' not 'security', 'visa tracking' not 'immigration'>",

  "heat_score": <float 0.0-1.0. 0.8+ = massive need with paying users. 0.5-0.7 = real gap. <0.5 = minor annoyance>,

  "evidence_summary": "<1 sentence with real numbers from the evidence>",

  "failed_tools": ["<ONLY tools from the evidence. No guessing. If no tools named, use the substitutes.>"],

  "substitutes": ["<the workarounds: spreadsheets, manual work, email, WhatsApp, etc.>"],

  "why_now": "<1 sentence. What's changed that makes this gap new or worse.>"
}

HOW TO WRITE (READ THIS CAREFULLY):

DO write like this:
- "Gig workers get hit with surprise bills they can't pay. They scramble through Reddit trying to figure out which to skip. Most end up using spreadsheets or just ignoring it until collections calls."
- "Shopify store owners lose thousands to return scams. Shopify's built-in tools don't flag suspicious patterns. Owners either eat the loss or spend hours manually reviewing every return."

DO NOT write like this (these are banned):
- "A mobile-first financial co-pilot for gig workers and low-to-moderate income earners..." (robot speak)
- "Navigating the legal, financial, and logistical maze of international relocation..." (AI phrase soup)
- "Current tools like X focus on long-term Y, not immediate Z." (formulaic comparison)
- "It automates the triage process of prioritizing bills..." (nobody says triage process)
- Any compound adjective like "end-to-end", "mobile-first", "data-driven", "pre-written"
- Any phrase like "paradigm shift", "leverage", "streamline", "empower", "unlock"
- Em dashes (-). Use commas or periods instead.

HARD RULES:
- NEVER start titles with "No unified platform for", "No reliable tool for", or any "No [adjective] [noun] for" pattern.
- ONLY use competitor names from the evidence. Don't invent tools.
- If evidence is vague, set heat_score below 0.4.
- Read your description out loud. If it sounds like a press release, rewrite it."""


# ─── Helpers ──────────────────────────────────────────────────────

def _slugify(title: str) -> str:
    """Convert title to URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:500]


def _signal_summary(signal: dict) -> str:
    """Extract compact summary from a signal for LLM input."""
    title = (signal.get('title') or '')[:100]
    content = (signal.get('content') or '')[:200]
    source = signal.get('subreddit') or signal.get('source', '')
    urgency = signal.get('urgency_score', 0)
    return f"[{source}, urgency={urgency}] {title}: {content}".strip()


def _compute_heat_score(signals: list[dict]) -> float:
    """Rule-based heat score: volume + urgency + recency."""
    if not signals:
        return 0.0

    count = len(signals)
    avg_urgency = sum(float(s.get('urgency_score', 0) or 0) for s in signals) / count

    # Volume score (logarithmic: 1 signal = 0.1, 10 = 0.4, 50+ = 0.7)
    import math
    volume_score = min(0.7, 0.1 + 0.15 * math.log1p(count))

    # Urgency score (weighted)
    urgency_score = avg_urgency * 0.8

    return round(min(1.0, volume_score + urgency_score), 3)


# ─── Core Logic ───────────────────────────────────────────────────

def fetch_unprocessed_signals(db: RemoteDB, vertical: str = None,
                               limit: int = 500) -> list[dict]:
    """Fetch gold/silver signals that haven't been assigned to a gap yet."""
    signals = []

    for tier in ['gold', 'silver']:
        batch = db.get_signals(
            vertical=vertical,
            quality_tier=tier,
            limit=limit,
        )
        # Filter: must have pain_category, must not have gap_id
        for s in batch:
            if s.get('gap_id'):
                continue
            cat = s.get('pain_category')
            if not cat or cat == 'uncategorized':
                continue
            signals.append(s)

    # Dedupe by id
    seen = set()
    unique = []
    for s in signals:
        sid = s.get('id')
        if sid not in seen:
            seen.add(sid)
            unique.append(s)

    logger.info(f"Fetched {len(unique)} unprocessed signals (gold+silver, no gap_id)")
    return unique


def pre_cluster_signals(signals: list[dict]) -> dict[str, list[dict]]:
    """Group signals by pain_category as a first-pass clustering."""
    clusters = defaultdict(list)
    for s in signals:
        cat = s.get('pain_category', 'uncategorized')
        clusters[cat].append(s)

    # Sort by cluster size descending
    sorted_clusters = dict(sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True))
    logger.info(f"Pre-clustered into {len(sorted_clusters)} categories")
    return sorted_clusters


def refine_cluster_with_llm(category: str, signals: list[dict],
                              cluster_context: dict = None,
                              max_signals: int = 20) -> dict | None:
    """
    Send a signal cluster to LLM for gap extraction.
    Uses pre-built cluster context (competitors, substitutes, pain phrases)
    instead of raw signal dumps.

    Args:
        category: pain_category name
        signals: list of signals in this cluster
        cluster_context: pre-built context from cluster_context_builder (optional)
        max_signals: max raw signals to include as supplementary evidence

    Returns:
        gap metadata dict or None if LLM fails.
    """
    # Build context if not provided
    if cluster_context is None:
        cluster_context = build_cluster_context(category, signals)

    # Format structured evidence for LLM
    evidence_block = format_context_for_llm(cluster_context)

    # Add a small sample of raw signals as supplementary evidence
    sample = signals[:max_signals]
    signal_blocks = []
    for i, s in enumerate(sample[:8]):  # Just 8 raw signals, context does the heavy lifting
        summary = _signal_summary(s)
        signal_blocks.append(f"{i+1}. {summary}")

    signals_text = '\n'.join(signal_blocks)

    prompt = f"""Analyze this market gap based on {len(signals)} user pain signals.

{evidence_block}

--- RAW SIGNAL SAMPLE (supplementary) ---
{signals_text}
--- END ---

Based on the evidence above, generate the gap JSON object.
IMPORTANT: Only name competitors/substitutes that appear in the evidence. Do not invent tool names.
If no named competitors exist, frame the gap around the substitutes people use instead."""

    result = gap_llm_json(
        prompt=prompt,
        system_prompt=GAP_SYSTEM_PROMPT,
        max_tokens=2000,
        temperature=0.3,
        timeout=45,
    )

    # Check for errors
    if result.get('_error'):
        logger.warning(f"LLM failed for cluster '{category}': {result['_error']}")
        return _fallback_gap(category, signals, cluster_context)

    if not result or not result.get('title'):
        logger.warning(f"LLM returned empty for cluster '{category}'")
        return _fallback_gap(category, signals, cluster_context)

    # Log token usage for cost tracking
    meta = result.get('_meta', {})
    if meta:
        logger.info(f"Gap LLM: {meta.get('model', '?')} | {meta.get('tokens_in', 0)}+{meta.get('tokens_out', 0)} tokens | {meta.get('elapsed', 0)}s")

    # Sanitize AI tells from title and description
    result['title'] = sanitize_text(result.get('title', ''))
    result['description'] = sanitize_text(result.get('description', ''))
    if result.get('why_now'):
        result['why_now'] = sanitize_text(result['why_now'])
    if result.get('evidence_summary'):
        result['evidence_summary'] = sanitize_text(result['evidence_summary'])

    return result


def _fallback_gap(category: str, signals: list[dict], cluster_context: dict = None) -> dict:
    """Generate gap metadata without LLM when it fails. Uses context if available."""
    count = len(signals)
    cat_display = category.replace('_', ' ').title()
    avg_urgency = sum(float(s.get('urgency_score', 0) or 0) for s in signals) / count if signals else 0

    # Use context data if available
    if cluster_context:
        competitors = [c['name'] for c in cluster_context.get('competitors', [])[:3]]
        substitutes = [s['name'] for s in cluster_context.get('substitutes', [])[:2]]
        who = cluster_context.get('who_is_affected', [])

        comp_str = ', '.join(competitors) if competitors else None
        sub_str = ', '.join(substitutes) if substitutes else None
        who_str = ', '.join(who[:2]) if who else 'people'

        # Build description in a natural voice
        parts = []
        parts.append(f"{count} people are stuck on {cat_display.lower()} problems.")
        if comp_str:
            parts.append(f"They're using {comp_str} but it's not cutting it.")
        if sub_str:
            parts.append(f"Falling back to {sub_str} just to get by.")
        parts.append(f"Urgency is real (avg {avg_urgency:.1f}/1.0).")
        description = ' '.join(parts)

        return {
            'title': sanitize_text(f"{cat_display} is hurting {count} users"),
            'description': sanitize_text(description),
            'category': category,
            'heat_score': _compute_heat_score(signals),
            'evidence_summary': f"{count} signals, avg urgency {avg_urgency:.2f}",
            'failed_tools': competitors,
            'substitutes': substitutes,
            'why_now': '',
        }

    return {
        'title': sanitize_text(f"{cat_display} is hurting {count} users"),
        'description': sanitize_text(
            f"{count} people are hitting {cat_display.lower()} issues. "
            f"Urgency avg {avg_urgency:.1f}/1.0. Nobody's solving this well yet."
        ),
        'category': category,
        'heat_score': _compute_heat_score(signals),
        'evidence_summary': f"{count} signals, avg urgency {avg_urgency:.2f}",
    }


def create_gap_from_cluster(db: RemoteDB, gap_meta: dict,
                             signals: list[dict],
                             cluster_context: dict = None) -> dict | None:
    """
    Create a gap record in MySQL and link signals to it.
    Stores competitors/substitutes from context and LLM output.

    Returns {success, id} or None on failure.
    """
    # Minimum evidence threshold - don't create thin gaps
    MIN_SIGNALS = 30
    if len(signals) < MIN_SIGNALS:
        logger.debug(f"Skipping gap with only {len(signals)} signals (min {MIN_SIGNALS})")
        return None

    title = gap_meta.get('title', 'Untitled Gap')
    slug = _slugify(title)
    description = gap_meta.get('description', '')
    heat_score = float(gap_meta.get('heat_score', 0) or 0)
    category = gap_meta.get('category', 'uncategorized')
    signal_ids = [s['id'] for s in signals if s.get('id')]
    source_types = list(set(s.get('source', 'unknown') for s in signals))

    # Build sample quotes as objects with text/source/url for SEO linking
    sample_quotes = []
    for s in signals[:5]:
        text = _signal_summary(s)[:180]
        source = s.get('source', 'unknown')
        url = s.get('source_url', s.get('platform_id', ''))
        sample_quotes.append({
            'text': text,
            'source': source,
            'url': url,
        })

    # Build competitors JSON from context + LLM output
    competitors_data = {
        "failed_tools": gap_meta.get('failed_tools', []),
        "substitutes": gap_meta.get('substitutes', []),
        "why_now": gap_meta.get('why_now', ''),
    }

    # Enrich with context data if available
    if cluster_context:
        competitors_data["top_competitors"] = [
            {"name": c["name"], "mentions": c["mention_count"], "negative_rate": c.get("negative_rate", 0)}
            for c in cluster_context.get('competitors', [])[:5]
        ]
        competitors_data["top_substitutes"] = [
            {"name": s["name"], "mentions": s["mention_count"]}
            for s in cluster_context.get('substitutes', [])[:4]
        ]
        competitors_data["who_is_affected"] = cluster_context.get('who_is_affected', [])
        competitors_data["context_confidence"] = cluster_context.get('confidence', 0)

    # Create gap
    try:
        result = db.insert_gap({
            'title': title,
            'slug': slug,
            'description': description,
            'evidence_count': len(signal_ids),
            'heat_score': heat_score,
            'category': category,
            'source_types': source_types,
            'signal_ids': signal_ids,
            'sample_quotes': sample_quotes,
            'competitors': competitors_data,
        })
        gap_id = result.get('id')
        if not gap_id:
            logger.error(f"Failed to create gap: {result}")
            return None

        logger.info(f"Created gap #{gap_id}: {title} ({len(signal_ids)} signals)")

        # Link signals to gap
        linked = 0
        for s in signals:
            sid = s.get('id')
            if sid:
                try:
                    db.update_signal(sid, gap_id=gap_id, category=category)
                    linked += 1
                except Exception as e:
                    logger.warning(f"Failed to link signal {sid} to gap {gap_id}: {e}")

        logger.info(f"Linked {linked}/{len(signals)} signals to gap #{gap_id}")
        return {'success': True, 'id': gap_id, 'signals_linked': linked}

    except Exception as e:
        logger.error(f"Error creating gap: {e}")
        return None


# ─── Main Runner ──────────────────────────────────────────────────

def run_gap_detection(vertical: str = None, batch_size: int = 500,
                      min_cluster_size: int = 2) -> dict:
    """
    Run the full gap detection pipeline.

    Args:
        vertical: Filter signals by vertical (None = all).
        batch_size: Max signals to fetch per tier.
        min_cluster_size: Minimum signals in a cluster to create a gap.

    Returns:
        Stats dict with gaps_created, signals_linked, clusters_processed, etc.
    """
    db = RemoteDB()

    stats = {
        'gaps_created': 0,
        'signals_linked': 0,
        'clusters_processed': 0,
        'clusters_skipped': 0,
        'errors': 0,
    }

    # Step 1: Fetch unprocessed signals
    signals = fetch_unprocessed_signals(db, vertical=vertical, limit=batch_size)
    if not signals:
        logger.info("No unprocessed signals found. Nothing to do.")
        return stats

    # Step 2: Pre-cluster by pain_category
    clusters = pre_cluster_signals(signals)

    # Step 3: Process each cluster
    for category, cluster_signals in clusters.items():
        if len(cluster_signals) < min_cluster_size:
            stats['clusters_skipped'] += 1
            logger.debug(f"Skipping '{category}': only {len(cluster_signals)} signals (min={min_cluster_size})")
            continue

        stats['clusters_processed'] += 1
        logger.info(f"Processing cluster '{category}': {len(cluster_signals)} signals")

        # Check if a gap for this category already exists
        existing = db.get_gaps(category=category, status='active', limit=1)
        if existing.get('gaps') and len(existing['gaps']) > 0:
            # Update existing gap instead of creating new
            existing_gap = existing['gaps'][0]
            gap_id = existing_gap['id']
            old_ids = set(existing_gap.get('signal_ids', []))
            new_ids = [s['id'] for s in cluster_signals if s.get('id') and s['id'] not in old_ids]

            if new_ids:
                merged_ids = list(old_ids | set(new_ids))
                # Re-compute heat score with all signals
                db.update_gap(gap_id,
                    evidence_count=len(merged_ids),
                    signal_ids=merged_ids,
                    heat_score=_compute_heat_score(cluster_signals),
                )
                # Link new signals
                for sid in new_ids:
                    try:
                        db.update_signal(sid, gap_id=gap_id, category=category)
                        stats['signals_linked'] += 1
                    except Exception:
                        pass
                logger.info(f"Updated existing gap #{gap_id} with {len(new_ids)} new signals")
            continue

        # Build cluster market context (replaces DDG)
        from datetime import datetime
        cycle_id = datetime.now().strftime('%Y%m%d_%H%M')
        cluster_ctx = build_cluster_context(category, cluster_signals,
                                             cluster_id=f"gap_{category}_{cycle_id}")

        # Generate gap metadata via LLM using structured evidence
        gap_meta = refine_cluster_with_llm(category, cluster_signals,
                                            cluster_context=cluster_ctx)
        if not gap_meta:
            stats['errors'] += 1
            continue

        # Use rule-based heat as fallback/supplement
        if not gap_meta.get('heat_score'):
            gap_meta['heat_score'] = _compute_heat_score(cluster_signals)

        # Create gap and link signals (with context for competitor data)
        result = create_gap_from_cluster(db, gap_meta, cluster_signals,
                                          cluster_context=cluster_ctx)
        if result:
            stats['gaps_created'] += 1
            stats['signals_linked'] += result.get('signals_linked', 0)
        else:
            stats['errors'] += 1

    logger.info(f"Gap detection complete: {stats}")
    return stats


# ─── CLI Entry Point ──────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Gap Detector - cluster signals into gaps')
    parser.add_argument('--vertical', default=None, help='Filter by vertical (e.g., immigration)')
    parser.add_argument('--batch-size', type=int, default=500, help='Max signals per tier')
    parser.add_argument('--min-cluster', type=int, default=2, help='Min signals per cluster')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING'])

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level),
                        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    stats = run_gap_detection(
        vertical=args.vertical,
        batch_size=args.batch_size,
        min_cluster_size=args.min_cluster,
    )

    print(json.dumps(stats, indent=2))
