"""
GapFeed Remote MySQL Client

Drop-in replacement for signals_db.py that talks to the PHP API
on IONOS hosting instead of local SQLite.

Usage:
    from shared.remote_db import RemoteDB
    db = RemoteDB()
    signals = db.get_signals(vertical='immigration', limit=50)
    db.insert_signal({...})
"""

import json
import hashlib
import os
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

API_URL = "https://gapfeed.com/api/db.php"
API_KEY = os.environ.get("GAPFEED_API_KEY", "")


class RemoteDB:
    """MySQL via PHP API proxy."""

    def __init__(self, api_url: str = None, api_key: str = None):
        self.api_url = api_url or API_URL
        self.api_key = api_key or API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    def _request(self, action: str, data: dict = None) -> dict:
        """Make API request."""
        url = f"{self.api_url}?action={action}"
        resp = requests.post(url, headers=self.headers, json=data or {}, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if 'error' in result:
            raise Exception(f"DB API error: {result['error']}")
        return result

    # --- SIGNALS ---

    def insert_signal(self, signal: dict) -> dict:
        """Insert a single signal. Returns {ok, id}."""
        signal.setdefault('source', 'unknown')
        signal.setdefault('content', '')
        signal.setdefault('created_at', datetime.now(timezone.utc).isoformat())
        signal.setdefault('collected_at', datetime.now(timezone.utc).isoformat())
        signal.setdefault('vertical', 'general')
        signal.setdefault('is_processed', 0)
        signal.setdefault('synthesized', 0)
        signal.setdefault('urgency_score', 0)
        signal.setdefault('specificity_score', 0)
        signal.setdefault('buyer_intent', 0)
        return self._request('insert_signal', signal)

    def insert_signals_bulk(self, signals: List[dict]) -> dict:
        """Bulk insert signals. Returns {ok, inserted}."""
        for s in signals:
            s.setdefault('source', 'unknown')
            s.setdefault('content', '')
            s.setdefault('created_at', datetime.now(timezone.utc).isoformat())
            s.setdefault('collected_at', datetime.now(timezone.utc).isoformat())
            s.setdefault('vertical', 'general')
            s.setdefault('is_processed', 0)
            s.setdefault('synthesized', 0)
            s.setdefault('urgency_score', 0)
            s.setdefault('specificity_score', 0)
            s.setdefault('buyer_intent', 0)
        return self._request('insert_signals_bulk', {'signals': signals})

    def get_signals(self, vertical: str = None, quality_tier: str = None,
                    min_urgency: float = None, is_processed: int = None,
                    signal_type: str = None, gap_id: int = None,
                    limit: int = 50, offset: int = 0, order: str = 'urgency_score DESC') -> List[dict]:
        """Get signals with filters."""
        data = {'limit': limit, 'offset': offset, 'order': order}
        if vertical:
            data['vertical'] = vertical
        if quality_tier:
            data['quality_tier'] = quality_tier
        if min_urgency is not None:
            data['min_urgency'] = min_urgency
        if is_processed is not None:
            data['is_processed'] = is_processed
        if signal_type:
            data['signal_type'] = signal_type
        if gap_id is not None:
            data['gap_id'] = gap_id
        result = self._request('get_signals', data)
        return result.get('signals', [])

    def update_signal(self, signal_id: int, **kwargs) -> dict:
        """Update signal fields. Returns {ok, affected}."""
        kwargs['id'] = signal_id
        return self._request('update_signal', kwargs)

    def signal_exists(self, platform_id: str, source: str) -> dict:
        """Check if signal exists. Returns {exists, id}."""
        return self._request('signal_exists', {'platform_id': platform_id, 'source': source})

    # --- BRIEFS ---

    def upsert_brief(self, vertical: str, query: str, brief_json: str,
                     brief_md: str = None, signal_count: int = 0,
                     quality: str = 'low') -> dict:
        """Insert or update a brief."""
        query_hash = hashlib.md5(f"{vertical}:{query}".encode()).hexdigest()
        return self._request('upsert_brief', {
            'vertical': vertical,
            'query_hash': query_hash,
            'query': query,
            'brief_json': brief_json,
            'brief_md': brief_md or '',
            'signal_count': signal_count,
            'quality': quality,
            'generated_at': datetime.now(timezone.utc).isoformat()
        })

    def get_brief(self, vertical: str, query: str) -> Optional[dict]:
        """Get cached brief."""
        query_hash = hashlib.md5(f"{vertical}:{query}".encode()).hexdigest()
        result = self._request('get_brief', {'vertical': vertical, 'query_hash': query_hash})
        return result.get('brief')

    def get_briefs(self, vertical: str = None, limit: int = 20) -> List[dict]:
        """List cached briefs."""
        data = {'limit': limit}
        if vertical:
            data['vertical'] = vertical
        result = self._request('get_briefs', data)
        return result.get('briefs', [])

    # --- SCAN LOG ---

    def log_scan(self, vertical: str, source: str, category: str = None) -> int:
        """Log scan start. Returns scan_id."""
        result = self._request('log_scan', {
            'vertical': vertical,
            'source': source,
            'category': category or 'general'
        })
        return result.get('id')

    def complete_scan(self, scan_id: int, signals_found: int, signals_new: int):
        """Mark scan complete."""
        return self._request('complete_scan', {
            'scan_id': scan_id,
            'signals_found': signals_found,
            'signals_new': signals_new
        })

    # --- STATS ---

    def get_signal_count(self, vertical: str = None) -> dict:
        """Get signal counts."""
        data = {}
        if vertical:
            data['vertical'] = vertical
        return self._request('signal_count', data)

    # --- GAPS ---

    def insert_gap(self, gap: dict) -> dict:
        """Insert or update a gap. Returns {success, id}."""
        return self._request('insert_gap', gap)

    def get_gaps(self, category: str = None, status: str = None,
                 limit: int = 50, offset: int = 0) -> dict:
        """Get gaps with filters. Returns {gaps, total}."""
        params = f'&limit={limit}&offset={offset}'
        if category:
            params += f'&category={category}'
        if status:
            params += f'&status={status}'
        url = f"{self.api_url}?action=get_gaps{params}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def get_gap_by_slug(self, slug: str) -> Optional[dict]:
        """Get a single gap by slug. Returns gap dict or None."""
        url = f"{self.api_url}?action=get_gap_by_slug&slug={slug}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result.get('gap')

    def update_gap(self, gap_id: int, **kwargs) -> dict:
        """Update gap fields. Returns {success, affected}."""
        kwargs['id'] = gap_id
        return self._request('update_gap', kwargs)

    def delete_gap(self, gap_id: int) -> dict:
        """Soft delete a gap (sets status='stale'). Returns {success}."""
        return self._request('delete_gap', {'id': gap_id})

    def get_gap_count(self, category: str = None, status: str = None) -> int:
        """Count gaps. Returns total count."""
        params = ''
        if category:
            params += f'&category={category}'
        if status:
            params += f'&status={status}'
        url = f"{self.api_url}?action=gap_count{params}"
        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get('total', 0)

    # --- MIGRATION ---

    def create_schema(self) -> dict:
        """Create MySQL tables if they don't exist."""
        return self._request('migrate_schema')


# --- CONVENIENCE FUNCTIONS (matching signals_db.py interface) ---

def bulk_insert_signals_remote(signals: List[dict], db: RemoteDB = None) -> int:
    """Bulk insert, returns count of new signals."""
    db = db or RemoteDB()
    result = db.insert_signals_bulk(signals)
    return result.get('inserted', 0)


def search_signals_remote(query: str, vertical: str = None, min_tier: str = 'bronze',
                           limit: int = 200, db: RemoteDB = None) -> List[dict]:
    """Search signals by content match."""
    db = db or RemoteDB()
    # For now, get all signals and filter client-side
    # (MySQL full-text search could be added later)
    signals = db.get_signals(vertical=vertical, limit=limit)
    query_lower = query.lower()
    return [s for s in signals if query_lower in (s.get('content', '') + s.get('title', '')).lower()]

