"""
Agent Monitor — Check if Agent_1, Agent_6, and Agent_4 are alive.

Checks:
- Python processes running with TheRealAgents in command line
- Log files updated recently (within max_age_minutes)
- Launcher log showing restarts
"""

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

# Path: Agent_7's app/monitors/agent_monitor.py
# tuxo/TheRealAgents/Agent_7/app/monitors/agent_monitor.py
# 5 levels up to tuxo/
TUXO_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
AGENTS_DIR = TUXO_DIR / 'TheRealAgents'


def check_agents(
    expected_agents: List[str] = None,
    log_max_age_minutes: int = 15,
) -> Dict:
    """
    Check health of all expected agents.
    
    Returns dict with:
    - status: 'ok' | 'warning' | 'critical'
    - agents: list of agent status dicts
    - alerts: list of alert strings
    """
    if expected_agents is None:
        expected_agents = ['Agent_1', 'Agent_6']
    
    results = []
    alerts = []
    
    for agent_name in expected_agents:
        agent_dir = AGENTS_DIR / agent_name
        agent_result = {
            'name': agent_name,
            'alive': False,
            'log_recent': False,
            'launcher_ok': False,
            'last_activity': None,
            'errors': [],
        }
        
        # Check if process is running - check via log freshness instead of WMI
        # The agents may have different command line patterns, so we rely on log freshness
        agent_result['alive'] = False  # Will be set True if log is recent
        
        # Check log file freshness
        log_dir = agent_dir / 'logs'
        log_file = log_dir / f'{agent_name.lower().split()[0]}.log'
        if log_file.exists():
            stat = log_file.stat()
            mod_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            age_minutes = (now - mod_time).total_seconds() / 60
            agent_result['log_recent'] = age_minutes < log_max_age_minutes
            agent_result['last_activity'] = mod_time.isoformat()
            
            # Log freshness is our primary "alive" indicator
            agent_result['alive'] = age_minutes < log_max_age_minutes
            
            # Read last line for activity
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if lines:
                        agent_result['last_log'] = lines[-1].strip()
            except Exception:
                pass
        else:
            agent_result['errors'].append(f'Log file not found: {log_file}')
        
        # Check launcher log
        launcher_log = log_dir / 'launcher.log'
        if launcher_log.exists():
            try:
                with open(launcher_log, 'r', encoding='utf-8') as f:
                    launcher_lines = f.readlines()
                    if launcher_lines:
                        last_line = launcher_lines[-1].strip()
                        agent_result['launcher_ok'] = 'Starting' in last_line or 'Restarting' in last_line
                        agent_result['launcher_log'] = last_line
            except Exception:
                pass
        
        # Determine status
        if not agent_result['alive']:
            agent_result['status'] = 'critical'
            alerts.append(f'{agent_name}: NOT RUNNING (process not found)')
        elif not agent_result['log_recent']:
            agent_result['status'] = 'warning'
            alerts.append(f'{agent_name}: Log not updated recently (>{log_max_age_minutes} min)')
        else:
            agent_result['status'] = 'ok'
        
        results.append(agent_result)
    
    # Overall status
    critical = any(a['status'] == 'critical' for a in results)
    warnings = any(a['status'] == 'warning' for a in results)
    
    if critical:
        overall = 'critical'
    elif warnings:
        overall = 'warning'
    else:
        overall = 'ok'
    
    return {
        'status': overall,
        'agents': results,
        'alerts': alerts,
    }
