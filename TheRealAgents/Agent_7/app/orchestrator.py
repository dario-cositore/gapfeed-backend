"""
Agent_7 — Orchestrator

Main state machine: CHECK_AGENTS -> CHECK_SERVER -> CHECK_DB -> CHECK_SYSTEM -> DIAGNOSE -> REPORT -> NOTIFY -> SLEEP
"""

import json
import logging
import signal as signal_mod
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SAM_ROOT = Path(__file__).resolve().parent.parent
TUXO_DIR = SAM_ROOT.parent.parent
sys.path.insert(0, str(TUXO_DIR))

from .config import load_config
from .monitors import check_agents, check_server, check_database, check_system
from .reporter import write_report, write_state
from .notifier import TelegramNotifier
from shared.llm_client import llm_call

logger = logging.getLogger(__name__)


class SamOrchestrator:
    """The main state machine for Agent_7."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.running = False
        self.cycle_count = 0
        self.total_checks = 0
        self.total_alerts = 0

        # Paths
        self.memory_dir = Path(self.config['paths']['memory_dir'])
        self.state_dir = Path(self.config['paths']['state_dir'])
        self.logs_dir = Path(self.config['paths']['logs_dir'])

        for d in [self.memory_dir, self.state_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Telegram notifier
        telegram_config = self.config.get('telegram', {})
        self.notifier = None
        if telegram_config.get('enabled', False):
            self.notifier = TelegramNotifier(
                bot_token=telegram_config['bot_token'],
                chat_id=telegram_config['chat_id'],
                cooldown_minutes=telegram_config.get('cooldown_minutes', 15),
                state_file=str(self.state_dir / 'notifier_state.json'),
            )

    def _run_cycle(self):
        """Execute one monitoring cycle."""
        self.cycle_count += 1
        logger.info(f"=== Sam Check #{self.cycle_count} ===")

        report = {
            'cycle': self.cycle_count,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'ok',
        }
        alerts = []

        try:
            # 1. Check Agents
            logger.info("[1/4] Checking agents...")
            if self.config['monitors']['agents']['enabled']:
                agent_config = self.config['monitors']['agents']
                agent_result = check_agents(
                    expected_agents=agent_config['expected_agents'],
                    log_max_age_minutes=agent_config.get('log_max_age_minutes', 15),
                )
                report['agents'] = agent_result
                if agent_result.get('alerts'):
                    alerts.extend(agent_result['alerts'])
                logger.info(f"  Agents: {agent_result['status']}")
            else:
                report['agents'] = {'status': 'skipped'}

            # 2. Check Server
            logger.info("[2/4] Checking server...")
            if self.config['monitors']['server']['enabled']:
                server_config = self.config['monitors']['server']
                server_result = check_server(
                    url=server_config['url'],
                    timeout=server_config.get('timeout', 15),
                    api_key=server_config.get('api_key'),
                )
                report['server'] = server_result
                if server_result.get('alert'):
                    alerts.append(server_result['alert'])
                logger.info(f"  Server: {server_result['status']}")
            else:
                report['server'] = {'status': 'skipped'}

            # 3. Check Database
            logger.info("[3/4] Checking database...")
            if self.config['monitors']['database']['enabled']:
                db_config = self.config['monitors']['database']
                db_result = check_database(
                    api_url=db_config.get('api_url'),
                    api_key=db_config.get('api_key'),
                )
                report['database'] = db_result
                if db_result.get('alert'):
                    alerts.append(db_result['alert'])
                logger.info(f"  Database: {db_result['status']}")
            else:
                report['database'] = {'status': 'skipped'}

            # 4. Check System
            logger.info("[4/4] Checking system...")
            if self.config['monitors']['system']['enabled']:
                sys_config = self.config['monitors']['system']
                sys_result = check_system(
                    check_disk=sys_config.get('check_disk', True),
                    check_processes=sys_config.get('check_processes', True),
                )
                report['system'] = sys_result
                if sys_result.get('alert'):
                    alerts.append(sys_result['alert'])
                logger.info(f"  System: {sys_result['status']}")
            else:
                report['system'] = {'status': 'skipped'}

            # Determine overall status
            all_statuses = [
                report.get('agents', {}).get('status'),
                report.get('server', {}).get('status'),
                report.get('database', {}).get('status'),
                report.get('system', {}).get('status'),
            ]
            if 'critical' in all_statuses:
                report['status'] = 'critical'
            elif 'warning' in all_statuses:
                report['status'] = 'warning'
            else:
                report['status'] = 'ok'

            report['alerts'] = alerts
            self.total_checks += 1
            if alerts:
                self.total_alerts += len(alerts)

            # 5. LLM Diagnosis (if alerts and LLM enabled)
            llm_config = self.config.get('llm', {})
            if alerts and llm_config.get('enabled', True):
                logger.info("[5/5] DIAGNOSE: running LLM analysis on alerts...")
                diagnosis = self._diagnose_alerts(report, alerts, llm_config)
                report['diagnosis'] = diagnosis
                if diagnosis:
                    # Sanitize unicode for Windows console
                    safe_diag = diagnosis.encode('ascii', errors='replace').decode('ascii')
                    logger.info(f"  Diagnosis: {safe_diag[:200]}...")
            else:
                report['diagnosis'] = None

            # Write report
            write_report(report, str(self.memory_dir))
            write_state(report, str(self.state_dir))

            # Notify on critical alerts
            if alerts and self.notifier:
                critical_alerts = [a for a in alerts if 'critical' in report.get('status', '').lower() 
                                   or 'agent' in a.lower() or 'server' in a.lower() or 'database' in a.lower()]
                if critical_alerts or report.get('status') == 'critical':
                    logger.info("[6/6] NOTIFY: sending Telegram alert...")
                    message = self.notifier.format_alert(report, alerts)
                    sent = self.notifier.send(message)
                    if sent:
                        logger.info("  Notification sent")
                    else:
                        logger.info("  Notification skipped (cooldown or error)")

            # Log summary
            status_icon = '[OK]' if report['status'] == 'ok' else '[WARN]' if report['status'] == 'warning' else '[CRIT]'
            logger.info(f"{status_icon} Cycle {self.cycle_count} complete: {report['status']}")
            if alerts:
                for alert in alerts:
                    logger.warning(f"  ALERT: {alert}")

        except Exception as e:
            logger.error(f"Cycle {self.cycle_count} failed: {e}", exc_info=True)
            report['status'] = 'critical'
            report['error'] = str(e)

    def start(self):
        """Start the monitoring loop."""
        self.running = True

        signal_mod.signal(signal_mod.SIGINT, self._shutdown)
        signal_mod.signal(signal_mod.SIGTERM, self._shutdown)

        logger.info("Agent_7 starting up")
        logger.info(f"Agents: {self.config['monitors']['agents'].get('expected_agents', [])}")
        logger.info(f"Server: {self.config['monitors']['server'].get('url', 'N/A')}")
        logger.info(f"Cycle interval: {self.config['cycle']['sleep_between_cycles']}s")

        sleep_seconds = self.config['cycle']['sleep_between_cycles']

        while self.running:
            try:
                self._run_cycle()
            except Exception as e:
                logger.error(f"Orchestrator error: {e}", exc_info=True)

            if self.running:
                logger.info(f"Sleeping {sleep_seconds}s...")
                for _ in range(sleep_seconds):
                    if not self.running:
                        break
                    time.sleep(1)

    def _diagnose_alerts(self, report: dict, alerts: list, llm_config: dict) -> str | None:
        """Use LLM to diagnose alerts and suggest fixes."""
        try:
            # Build context from report
            context_parts = []
            for section in ['agents', 'server', 'database', 'system']:
                data = report.get(section, {})
                if data.get('status') != 'skipped':
                    context_parts.append(f"{section}: {json.dumps(data, indent=2)}")

            context = '\n\n'.join(context_parts)
            alerts_text = '\n'.join(f"- {a}" for a in alerts)

            prompt = f"""You are Agent_7, a system monitor for the TuXo platform. Analyze these health check alerts and provide a concise diagnosis.

ALERTS:
{alerts_text}

SYSTEM STATE:
{context}

Provide a 2-3 sentence diagnosis:
1. What's the root cause?
2. What should be done to fix it?
3. How urgent is it?

Be specific and actionable. If you can't determine the root cause, say so."""

            diagnosis = llm_call(
                prompt=prompt,
                system_prompt="You are a system diagnostics assistant. Be concise, specific, and actionable.",
                model=llm_config.get('model', 'mimo-v2.6-flash'),
                max_tokens=llm_config.get('max_tokens', 2000),
                temperature=llm_config.get('temperature', 0.2),
                timeout=llm_config.get('timeout', 30),
            )
            return diagnosis if diagnosis else None
        except Exception as e:
            logger.error(f"LLM diagnosis failed: {e}")
            return None

    def _shutdown(self, signum=None, frame=None):
        logger.info(f"Shutting down (signal {signum})...")
        self.running = False
        logger.info(f"Stats: {self.cycle_count} checks, {self.total_alerts} alerts")
