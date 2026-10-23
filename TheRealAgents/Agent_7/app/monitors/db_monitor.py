"""
Database Monitor — Check MySQL API health and signal counts.
"""

import sys
import time
from pathlib import Path
from typing import Dict

# Path resolution to tuxo/
TUXO_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(TUXO_DIR))

from shared.remote_db import RemoteDB


def check_database(api_url: str = None, api_key: str = None) -> Dict:
    """
    Check MySQL API health and signal statistics.
    
    Returns dict with:
    - status: 'ok' | 'warning' | 'critical'
    - signal_count: dict or None
    - unprocessed: int or None
    - response_time_ms: float or None
    - alert: str or None
    """
    result = {
        'status': 'critical',
        'signal_count': None,
        'unprocessed': None,
        'response_time_ms': None,
        'alert': None,
    }
    
    try:
        db = RemoteDB(api_url=api_url, api_key=api_key)
        
        # Check signal count
        start = time.time()
        counts = db.get_signal_count()
        elapsed = (time.time() - start) * 1000
        
        result['signal_count'] = counts
        result['response_time_ms'] = round(elapsed, 1)
        
        # Check unprocessed signals
        try:
            unprocessed_signals = db.get_signals(is_processed=0, limit=1)
            result['unprocessed'] = len(unprocessed_signals)
        except Exception:
            result['unprocessed'] = None
        
        # Determine status
        total = counts.get('total', 0)
        
        if total == 0:
            result['status'] = 'warning'
            result['alert'] = 'Database has 0 signals'
        elif elapsed > 5000:
            result['status'] = 'warning'
            result['alert'] = f'Database slow: {elapsed:.0f}ms response'
        else:
            result['status'] = 'ok'
    
    except Exception as e:
        result['alert'] = f'Database unreachable: {str(e)}'
    
    return result
