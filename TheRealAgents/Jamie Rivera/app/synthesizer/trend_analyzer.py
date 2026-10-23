"""
Trend analyzer — detect growth/decline in signal patterns.
"""
from datetime import datetime, timedelta
from typing import List


def detect_trend(signals: List[dict]) -> str:
    """
    Detect if the signals show a growing, stable, or declining trend.
    
    Args:
        signals: List of signal dicts with 'created_at' field
        
    Returns:
        'growing', 'stable', or 'declining'
    """
    if not signals:
        return 'stable'
    
    # Simple trend: compare urgency of recent vs older signals
    try:
        # Sort by created_at (most recent first)
        sorted_signals = sorted(signals, key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Take first 10% (recent) and last 10% (older)
        recent_count = max(1, len(sorted_signals) // 10)
        old_count = max(1, len(sorted_signals) // 10)
        
        recent_signals = sorted_signals[:recent_count]
        old_signals = sorted_signals[-old_count:]
        
        recent_avg = sum(float(s.get('urgency_score', 0) or 0) for s in recent_signals) / len(recent_signals)
        old_avg = sum(float(s.get('urgency_score', 0) or 0) for s in old_signals) / len(old_signals)
        
        diff = recent_avg - old_avg
        
        if diff > 0.1:
            return 'growing'
        elif diff < -0.1:
            return 'declining'
        else:
            return 'stable'
            
    except Exception:
        return 'stable'


def detect_trend_from_count(signals: List[dict]) -> str:
    """
    Detect trend based on signal count over time buckets.
    
    A simple heuristic: if signal count is increasing, trend is 'growing'.
    """
    if not signals or len(signals) < 5:
        return 'stable'
    
    # Sort by created_at
    sorted_signals = sorted(signals, key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Split into 2 buckets (old vs new)
    split_point = len(sorted_signals) // 2
    bucket1 = sorted_signals[:split_point]
    bucket2 = sorted_signals[split_point:]
    
    # If bucket2 (newer) has more signals, trend is growing
    if len(bucket2) > len(bucket1) * 1.2:
        return 'growing'
    elif len(bucket1) > len(bucket2) * 1.2:
        return 'declining'
    else:
        return 'stable'
