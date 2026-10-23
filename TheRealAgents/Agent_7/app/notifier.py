"""
Agent_7 — Telegram Notifier

Sends alert notifications via Telegram Bot API.
Only sends on critical alerts, with rate limiting to avoid spam.
"""

import json
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Sends Telegram messages on critical alerts."""

    def __init__(self, bot_token: str, chat_id: str, 
                 cooldown_minutes: int = 15,
                 state_file: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.cooldown_minutes = cooldown_minutes
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.state_file = state_file
        self.last_sent = self._load_last_sent()

    def _load_last_sent(self) -> Optional[datetime]:
        """Load last notification timestamp from state file."""
        if not self.state_file:
            return None
        try:
            path = Path(self.state_file)
            if path.exists():
                data = json.loads(path.read_text())
                return datetime.fromisoformat(data.get('last_sent', ''))
        except Exception:
            pass
        return None

    def _save_last_sent(self):
        """Save last notification timestamp."""
        if not self.state_file:
            return
        try:
            path = Path(self.state_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                'last_sent': datetime.now(timezone.utc).isoformat()
            }))
        except Exception as e:
            logger.error(f"Failed to save notifier state: {e}")

    def _is_cooldown_active(self) -> bool:
        """Check if we're within the cooldown period."""
        if not self.last_sent:
            return False
        elapsed = (datetime.now(timezone.utc) - self.last_sent).total_seconds()
        return elapsed < (self.cooldown_minutes * 60)

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a Telegram message. Returns True if sent successfully.
        Respects cooldown to avoid notification spam.
        """
        if self._is_cooldown_active():
            logger.info("Notification cooldown active, skipping send")
            return False

        try:
            payload = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': True,
            }
            resp = requests.post(self.api_url, json=payload, timeout=10)
            resp.raise_for_status()
            result = resp.json()

            if result.get('ok'):
                self.last_sent = datetime.now(timezone.utc)
                self._save_last_sent()
                logger.info("Telegram notification sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {result}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False

    def format_alert(self, report: dict, alerts: list) -> str:
        """Format alert data into a readable Telegram message."""
        status = report.get('status', 'unknown')
        status_icon = {
            'ok': '✅',
            'warning': '⚠️',
            'critical': '🚨'
        }.get(status, '❓')

        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

        lines = [
            f"{status_icon} <b>Agent_7 Alert</b>",
            f"<i>{timestamp}</i>",
            "",
            f"<b>Status:</b> {status.upper()}",
            "",
            "<b>Issues:</b>",
        ]

        for alert in alerts:
            lines.append(f"  • {alert}")

        # Add diagnosis if available
        diagnosis = report.get('diagnosis')
        if diagnosis:
            lines.append("")
            lines.append("<b>Diagnosis:</b>")
            # Truncate long diagnoses
            diag_text = diagnosis[:500]
            lines.append(f"<i>{diag_text}</i>")

        return "\n".join(lines)
