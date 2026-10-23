"""
Server Monitor — Check if Flask server is alive and returning data.
"""

import time
import urllib.request
import urllib.error
import json
from typing import Dict


def check_server(url: str = 'https://gapfeed.com/api/stats', timeout: int = 15, api_key: str = None) -> Dict:
    """
    Check if the Flask server is responding.
    
    Returns dict with:
    - status: 'ok' | 'warning' | 'critical'
    - response_time_ms: float or None
    - status_code: int or None
    - data: dict or None
    - alert: str or None
    """
    result = {
        'status': 'critical',
        'response_time_ms': None,
        'status_code': None,
        'data': None,
        'alert': None,
    }
    
    try:
        start = time.time()
        headers = {}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        req = urllib.request.Request(url, method='GET', headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = (time.time() - start) * 1000
            body = resp.read().decode('utf-8')
            
            result['status_code'] = resp.status
            result['response_time_ms'] = round(elapsed, 1)
            
            try:
                result['data'] = json.loads(body)
            except json.JSONDecodeError:
                result['data'] = {'raw': body[:200]}
            
            if resp.status == 200 and elapsed < 10000:
                result['status'] = 'ok'
            elif resp.status == 200 and elapsed >= 10000:
                result['status'] = 'warning'
                result['alert'] = f'Server slow: {elapsed:.0f}ms response time'
            else:
                result['status'] = 'critical'
                result['alert'] = f'Server returned HTTP {resp.status}'
    
    except urllib.error.HTTPError as e:
        result['status_code'] = e.code
        result['alert'] = f'Server HTTP error: {e.code} {e.reason}'
    
    except urllib.error.URLError as e:
        result['alert'] = f'Server unreachable: {e.reason}'
    
    except Exception as e:
        result['alert'] = f'Server check failed: {str(e)}'
    
    return result
