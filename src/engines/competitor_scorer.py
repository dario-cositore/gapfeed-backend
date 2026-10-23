"""
Competitor Scoring - Phase 3

Scores entities by their competitive significance using multiple signals:
- Mention frequency (how often they appear)
- Distinct authors (breadth of complaints)
- Negative context rate (how much people complain about them)
- Recency (when they were last mentioned)
- Cluster relevance (how central they are to the gap)

Score formula:
  score = 0.35 * frequency_norm
        + 0.25 * author_norm
        + 0.20 * negative_norm
        + 0.10 * recency_norm
        + 0.10 * relevance_norm

Each component normalized 0-1 within the cluster context.
"""
import math
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def score_entities(entities: list[dict], cluster_signals: list[dict] = None) -> list[dict]:
    """
    Score a list of entities within a cluster context.
    
    Args:
        entities: list of entity dicts from DB or mention resolver
                 Must have: mention_count, author_count, negative_rate
                 Optional: last_seen, signal_ids
        cluster_signals: the signals in this cluster (for relevance scoring)
    
    Returns:
        entities list sorted by score (descending), each with added 'score' field
    """
    if not entities:
        return []
    
    # Extract raw values for normalization
    mentions = [float(e.get('mention_count', e.get('total_mentions', 0))) for e in entities]
    authors = [float(e.get('author_count', e.get('total_authors', 0))) for e in entities]
    negatives = [float(e.get('negative_rate', e.get('avg_negative_rate', 0))) for e in entities]
    
    max_mentions = max(mentions) if mentions else 1
    max_authors = max(authors) if authors else 1
    
    # Recency: compute days since last seen
    now = datetime.now(timezone.utc)
    recency_days = []
    for e in entities:
        last_seen = e.get('last_seen')
        if last_seen:
            try:
                if isinstance(last_seen, str):
                    ls = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                else:
                    ls = last_seen
                days = (now - ls).days
            except (ValueError, TypeError):
                days = 30  # default if unparseable
        else:
            days = 30
        recency_days.append(days)
    
    max_recency = max(recency_days) if recency_days else 30
    
    for i, entity in enumerate(entities):
        # Frequency: normalized mention count (0-1)
        freq = mentions[i] / max_mentions if max_mentions > 0 else 0
        
        # Author breadth: normalized distinct author count (0-1)
        auth = authors[i] / max_authors if max_authors > 0 else 0
        
        # Negative rate: already 0-1
        neg = min(1.0, negatives[i])
        
        # Recency: 1.0 = today, decays linearly (0 at max_recency)
        recency = max(0, 1.0 - (recency_days[i] / max(max_recency, 1)))
        
        # Cluster relevance: what fraction of cluster signals mention this entity
        relevance = 0.0
        if cluster_signals and entity.get('signal_ids'):
            entity_signals = set(entity['signal_ids'])
            cluster_ids = set(s['id'] for s in cluster_signals if s.get('id'))
            if cluster_ids:
                relevance = len(entity_signals & cluster_ids) / len(cluster_ids)
        elif entity.get('mention_count') and cluster_signals:
            # Fallback: approximate
            relevance = min(1.0, entity['mention_count'] / len(cluster_signals))
        
        # Composite score
        score = (
            0.35 * freq +
            0.25 * auth +
            0.20 * neg +
            0.10 * recency +
            0.10 * relevance
        )
        
        entity['score'] = round(score, 3)
        entity['score_components'] = {
            'frequency': round(freq, 3),
            'author_breadth': round(auth, 3),
            'negative_rate': round(neg, 3),
            'recency': round(recency, 3),
            'cluster_relevance': round(relevance, 3),
        }
    
    # Sort by score descending
    entities.sort(key=lambda x: x.get('score', 0), reverse=True)
    return entities


def classify_threat(score: float, negative_rate: float) -> str:
    """
    Classify a competitor's threat level based on score and sentiment.
    
    Returns: 'dominant_hated', 'dominant_neutral', 'weak', 'irrelevant'
    """
    if score > 0.6 and negative_rate > 0.5:
        return 'dominant_hated'  # Big player, people complain = opportunity
    elif score > 0.6:
        return 'dominant_neutral'  # Big player, people ok with it
    elif score > 0.3:
        return 'weak'  # Present but not dominant
    else:
        return 'irrelevant'  # Barely mentioned


def format_scoring_for_gap(entities: list[dict], top_n: int = 5) -> dict:
    """
    Format scored entities into a gap-ready competitor summary.
    
    Returns dict with top_competitors, threat_assessment, opportunity_signal.
    """
    scored = score_entities(entities)
    top = scored[:top_n]
    
    competitors = []
    dominant_hated_count = 0
    for e in top:
        threat = classify_threat(
            e.get('score', 0),
            float(e.get('negative_rate', e.get('avg_negative_rate', 0)))
        )
        if threat == 'dominant_hated':
            dominant_hated_count += 1
        
        competitors.append({
            'name': e.get('name', e.get('canonical_name', '?')),
            'score': e.get('score', 0),
            'mentions': e.get('mention_count', e.get('total_mentions', 0)),
            'authors': e.get('author_count', e.get('total_authors', 0)),
            'negative_rate': float(e.get('negative_rate', e.get('avg_negative_rate', 0))),
            'threat': threat,
        })
    
    # Opportunity signal: high if multiple competitors are dominant but hated
    if dominant_hated_count >= 2:
        opportunity = 'high'
        signal = f"{dominant_hated_count} major players are failing users. Incumbents are vulnerable."
    elif dominant_hated_count == 1:
        opportunity = 'moderate'
        signal = "One dominant player has clear weaknesses. Room for differentiation."
    elif competitors and competitors[0].get('score', 0) > 0.5:
        opportunity = 'low'
        signal = "Market has strong players. Hard to compete head-on."
    else:
        opportunity = 'open'
        signal = "No dominant competitor. Wide open market."
    
    return {
        'top_competitors': competitors,
        'threat_assessment': signal,
        'opportunity_signal': opportunity,
        'dominant_hated_count': dominant_hated_count,
    }
