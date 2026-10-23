"""
Reporter — Log monitoring results to memory and console.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


def write_report(report: Dict, memory_dir: str = None):
    """
    Write a monitoring report to the memory directory.
    
    Appends to daily file: memory/YYYY-MM-DD.md
    """
    if not memory_dir:
        return
    
    mem_path = Path(memory_dir)
    mem_path.mkdir(parents=True, exist_ok=True)
    
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    report_file = mem_path / f'{today}.md'
    
    timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
    
    status = report.get('status', 'unknown')
    
    with open(report_file, 'a', encoding='utf-8') as f:
        f.write(f"\n## Sam Check - {timestamp} [{status.upper()}]\n\n")
        
        # Agents
        agents = report.get('agents', {})
        if agents.get('agents'):
            f.write("### Agents\n\n")
            for a in agents['agents']:
                status_icon = "✅" if a.get('status') == 'ok' else "⚠️" if a.get('status') == 'warning' else "❌"
                f.write(f"- {status_icon} **{a['name']}**: {a.get('status', 'unknown')}\n")
                if a.get('last_log'):
                    f.write(f"  Last: `{a['last_log'][:80]}`\n")
        
        # Server
        server = report.get('server', {})
        if server:
            srv_status = "✅" if server.get('status') == 'ok' else "⚠️" if server.get('status') == 'warning' else "❌"
            f.write(f"\n### Server\n\n")
            f.write(f"- {srv_status} Status: {server.get('status', 'unknown')}\n")
            if server.get('response_time_ms'):
                f.write(f"- Response: {server['response_time_ms']}ms\n")
            if server.get('alert'):
                f.write(f"- Alert: {server['alert']}\n")
        
        # Database
        db = report.get('database', {})
        if db:
            db_status = "✅" if db.get('status') == 'ok' else "⚠️" if db.get('status') == 'warning' else "❌"
            f.write(f"\n### Database\n\n")
            f.write(f"- {db_status} Status: {db.get('status', 'unknown')}\n")
            if db.get('signal_count'):
                f.write(f"- Total signals: {db['signal_count'].get('total', 0)}\n")
            if db.get('unprocessed') is not None:
                f.write(f"- Unprocessed: {db['unprocessed']}\n")
            if db.get('response_time_ms'):
                f.write(f"- Response: {db['response_time_ms']}ms\n")
        
        # System
        sys_info = report.get('system', {})
        if sys_info:
            sys_status = "✅" if sys_info.get('status') == 'ok' else "⚠️" if sys_info.get('status') == 'warning' else "❌"
            f.write(f"\n### System\n\n")
            f.write(f"- {sys_status} Status: {sys_info.get('status', 'unknown')}\n")
            if sys_info.get('disk'):
                d = sys_info['disk']
                f.write(f"- Disk: {d['free_gb']}GB free / {d['total_gb']}GB total ({d['used_pct']}% used)\n")
            if sys_info.get('processes'):
                f.write(f"- Python processes: {len(sys_info['processes'])}\n")
        
        # Alerts
        all_alerts = []
        if agents.get('alerts'):
            all_alerts.extend(agents['alerts'])
        if server.get('alert'):
            all_alerts.append(server['alert'])
        if db.get('alert'):
            all_alerts.append(db['alert'])
        if sys_info.get('alert'):
            all_alerts.append(sys_info['alert'])
        
        if all_alerts:
            f.write(f"\n### Alerts\n\n")
            for alert in all_alerts:
                f.write(f"- ⚠️ {alert}\n")
        
        f.write("\n")
    
    logger.info(f"Report written to {report_file}")


def write_state(report: Dict, state_dir: str = None):
    """Write latest state to state/latest.json for external consumers."""
    if not state_dir:
        return
    
    state_path = Path(state_dir)
    state_path.mkdir(parents=True, exist_ok=True)
    
    state_file = state_path / 'latest.json'
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
