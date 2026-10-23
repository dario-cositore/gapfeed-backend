"""
Brief generator — creates synthesized briefs from signals.
"""
import json
import re
from typing import List
from app.models.signal import Signal
from app.models.brief import Brief, Complaint, Want
from .summarizer import generate_summary
from .trend_analyzer import detect_trend


def group_by_pain_category(signals: List[Signal]) -> dict:
    """Group signals by pain category."""
    groups = {}
    for s in signals:
        cat = s.pain_category or 'uncategorized'
        if cat == 'uncategorized':
            continue
        if cat not in groups:
            groups[cat] = {'signals': [], 'urgencies': [], 'sources': set()}
        groups[cat]['signals'].append(s)
        groups[cat]['urgencies'].append(s.urgency_score)
        if s.subreddit:
            groups[cat]['sources'].add(s.subreddit)
    return groups


def extract_wants(signals: List[Signal]) -> List[Want]:
    """Extract signals with explicit wants (signal_type == 'want')."""
    wants = []
    for s in signals:
        if s.signal_type == 'want':
            wants.append(Want(
                content=(s.content or '')[:200],
                source=s.subreddit or '',
                url=s.source_url or '',
            ))
    return wants


def generate_complaints(groups: dict, top_n: int = 10) -> List[Complaint]:
    """Generate top complaints from grouped signals."""
    complaints = []
    for cat, group in sorted(groups.items(), key=lambda x: len(x[1]['signals']), reverse=True)[:top_n]:
        signals = group['signals']
        urgencies = group['urgencies']
        avg_urgency = sum(urgencies) / len(urgencies) if urgencies else 0
        
        # Find representative signal (highest urgency)
        best = max(signals, key=lambda s: s.urgency_score)
        
        complaints.append(Complaint(
            category=cat,
            avg_urgency=round(avg_urgency, 2),
            sample=(best.content or '')[:200],
            sources=sorted(list(group['sources'])),
            count=len(signals),
            url=best.source_url or '',
        ))
    return complaints


def generate_brief(
    query: str,
    signals: List[Signal],
    max_complaints: int = 10,
    max_wants: int = 10,
    use_llm: bool = True,
) -> Brief:
    """
    Generate a brief from a list of signals.
    
    Args:
        query: The original search query
        signals: List of Signal objects
        max_complaints: Max number of complaint groups
        max_wants: Max number of wants
        use_llm: Whether to use LLM for summary generation
    """
    if not signals:
        return Brief(query=query, signal_count=0)
    
    # Group signals by pain category
    pain_groups = group_by_pain_category(signals)
    
    # Extract wants
    wants = extract_wants(signals)
    
    # Generate top complaints
    complaints = generate_complaints(pain_groups, top_n=max_complaints)
    
    # Generate summary (LLM or rule-based)
    if use_llm:
        summary = generate_summary(query, signals, pain_groups)
    else:
        summary = f"Found {len(signals)} signals related to '{query}'. " \
                  f"Top categories: {', '.join([c.category for c in complaints[:3]])}"
    
    # Detect trend
    trend = detect_trend(signals)
    
    return Brief(
        query=query,
        signal_count=len(signals),
        top_complaints=complaints[:max_complaints],
        top_wants=wants[:max_wants],
        summary=summary,
        trend=trend,
    )
