"""
Data loader — fetch signals from MySQL for synthesis.
"""
import sys
from pathlib import Path

# Add project root for shared module access
# Path: .../tuxo/TheRealAgents/Jamie Rivera/app/database/data_loader.py
# 5 levels up: tuxo
JAMIE_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(JAMIE_ROOT))

from shared.remote_db import RemoteDB
from app.models.signal import Signal


def fetch_signals_by_query(
    query: str,
    vertical: str = 'general',
    max_signals: int = 500,
    min_urgency: float = 0.0,
    is_processed: bool = True,
):
    """
    Fetch signals matching query from MySQL.
    
    Returns list of Signal objects.
    """
    try:
        db = RemoteDB()
        
        # Fetch signals from the specific vertical
        all_signals = db.get_signals(
            vertical=vertical,
            limit=max_signals,
            order='urgency_score DESC',
        )
        
        query_lower = query.lower() if query else ''
        
        # Filter and process signals
        filtered = []
        for s in all_signals:
            # Check quality tier (exclude noise unless specified)
            if s.get('quality_tier', 'noise') == 'noise':
                continue
                
            # Check urgency threshold
            urgency = float(s.get('urgency_score', 0) or 0)
            if urgency < min_urgency:
                continue
            
            # If no query, take all matching signals
            if not query_lower:
                filtered.append(Signal.from_dict(s))
                continue
            
            # Filter by query text
            match_fields = [
                s.get('title', ''),
                s.get('content', ''),
                s.get('product_category', ''),
                s.get('pain_category', ''),
            ]
            
            if any(query_lower in str(field).lower() for field in match_fields):
                filtered.append(Signal.from_dict(s))
        
        # Sort by urgency descending
        filtered.sort(key=lambda s: s.urgency_score, reverse=True)
        
        print(f"Jamie: Fetched {len(filtered)} signals for query '{query}'")
        return filtered
        
    except Exception as e:
        print(f"Error fetching signals: {e}")
        import traceback
        traceback.print_exc()
        return []
