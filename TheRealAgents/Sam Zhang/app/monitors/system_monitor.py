"""
System Monitor — Check disk space, memory, Python processes.
"""

import os
import subprocess
from pathlib import Path
from typing import Dict


def check_system(check_disk: bool = True, check_processes: bool = True) -> Dict:
    """
    Check system resources.
    
    Returns dict with:
    - status: 'ok' | 'warning' | 'critical'
    - disk: dict with free/used/total
    - processes: list of python processes
    - alert: str or None
    """
    result = {
        'status': 'ok',
        'disk': None,
        'processes': None,
        'alert': None,
    }
    
    alerts = []
    
    # Check disk space
    if check_disk:
        try:
            usage = shutil.disk_usage(str(Path.home()))
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            used_pct = (usage.used / usage.total) * 100
            
            result['disk'] = {
                'free_gb': round(free_gb, 1),
                'total_gb': round(total_gb, 1),
                'used_pct': round(used_pct, 1),
            }
            
            if free_gb < 5:
                result['status'] = 'critical'
                alerts.append(f'Low disk space: {free_gb:.1f} GB free')
            elif free_gb < 20:
                if result['status'] != 'critical':
                    result['status'] = 'warning'
                alerts.append(f'Disk space low: {free_gb:.1f} GB free')
        except Exception as e:
            alerts.append(f'Disk check failed: {e}')
    
    # Check Python processes
    if check_processes:
        try:
            result['processes'] = []
            cmd = 'Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, CPU, WS | ConvertTo-Json'
            proc = subprocess.run(
                ['powershell', '-Command', cmd],
                capture_output=True, text=True, timeout=10
            )
            if proc.stdout.strip():
                import json
                procs = json.loads(proc.stdout)
                if isinstance(procs, dict):
                    procs = [procs]
                result['processes'] = procs
            
            # Check total memory usage
            total_mem_mb = sum(p.get('WS', 0) for p in result['processes']) / (1024**2)
            if total_mem_mb > 2000:
                if result['status'] != 'critical':
                    result['status'] = 'warning'
                alerts.append(f'High Python memory usage: {total_mem_mb:.0f} MB')
        except Exception as e:
            alerts.append(f'Process check failed: {e}')
    
    if alerts:
        result['alert'] = '; '.join(alerts)
    
    return result


# Import shutil for disk usage
import shutil
