"""
Memory review — periodic consolidation of Alex's memory files.

Every N rounds, Alex reviews his own journal and memory files:
- Prunes outdated observations
- Consolidates repeated patterns into concise rules
- Updates source performance data
- Rewrites plan if strategy has shifted

This is the "get smarter over time" mechanism.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import sys

ALEX_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ALEX_ROOT))

logger = logging.getLogger(__name__)


def should_review(round_count: int, review_interval: int = 10) -> bool:
    """Check if it's time for a memory review."""
    return round_count > 0 and round_count % review_interval == 0


def load_journal(journal_path: str, max_lines: int = 2000) -> str:
    """
    Load journal content for review.
    Truncates to max_lines to stay within LLM context window.
    """
    try:
        p = Path(journal_path)
        if not p.exists():
            return ""

        with open(p, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Keep most recent entries
        if len(lines) > max_lines:
            lines = lines[-max_lines:]

        return "".join(lines)
    except Exception as e:
        logger.error(f"Failed to load journal: {e}")
        return ""


def load_memory_files(memory_dir: str) -> dict:
    """Load all memory files for review."""
    memory = {}
    p = Path(memory_dir)

    for file_name in ['observations.md', 'strategies.md', 'patterns.md', 'mistakes.md', 'goals.md']:
        file_path = p / file_name
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    memory[file_name] = f.read()
            except Exception:
                memory[file_name] = ""

    return memory


def save_memory_file(memory_dir: str, file_name: str, content: str):
    """Save a memory file."""
    try:
        p = Path(memory_dir)
        p.mkdir(parents=True, exist_ok=True)
        with open(p / file_name, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to save memory file {file_name}: {e}")


def update_source_stats(memory_dir: str, source_performance: dict):
    """Update source_map.json with latest performance data."""
    stats_path = Path(memory_dir) / 'source_map.json'

    existing = {}
    if stats_path.exists():
        try:
            with open(stats_path) as f:
                existing = json.load(f)
        except Exception:
            pass

    # Merge new stats
    for source, stats in source_performance.items():
        if source in existing:
            # Running average
            old = existing[source]
            n = old.get('_rounds', 1)
            existing[source] = {
                'signal_yield': (old.get('signal_yield', 0) * n + stats.get('raw', 0)) / (n + 1),
                'avg_profile_confidence': (old.get('avg_profile_confidence', 0) * n + stats.get('avg_confidence', 0)) / (n + 1),
                'noise_rate': (old.get('noise_rate', 0) * n + stats.get('noise_rate', 0)) / (n + 1),
                'last_success_at': datetime.now(timezone.utc).isoformat(),
                '_rounds': n + 1,
            }
        else:
            existing[source] = {
                'signal_yield': stats.get('raw', 0),
                'avg_profile_confidence': stats.get('avg_confidence', 0),
                'noise_rate': stats.get('noise_rate', 0),
                'last_success_at': datetime.now(timezone.utc).isoformat(),
                '_rounds': 1,
            }

    try:
        with open(stats_path, 'w') as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save source stats: {e}")


def save_checkpoint(memory_dir: str, round_id: str, stage: str,
                    completed_steps: list[str], pending_ids: list[str] = None,
                    llm_budget: int = 0):
    """Save a checkpoint for crash recovery."""
    checkpoint = {
        'round_id': round_id,
        'stage': stage,
        'completed_steps': completed_steps,
        'pending_signal_ids': pending_ids or [],
        'llm_budget_remaining': llm_budget,
        'updated_at': datetime.now(timezone.utc).isoformat(),
    }

    try:
        ck_dir = Path(memory_dir) / 'checkpoints'
        ck_dir.mkdir(parents=True, exist_ok=True)

        # Save as latest
        with open(ck_dir / 'latest.json', 'w') as f:
            json.dump(checkpoint, f, indent=2)

        # Save named checkpoint
        with open(ck_dir / f'{round_id}.json', 'w') as f:
            json.dump(checkpoint, f, indent=2)

    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")


def load_latest_checkpoint(memory_dir: str) -> Optional[dict]:
    """Load the latest checkpoint for crash recovery."""
    ck_path = Path(memory_dir) / 'checkpoints' / 'latest.json'
    if not ck_path.exists():
        return None

    try:
        with open(ck_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load checkpoint: {e}")
        return None


def trim_journal(journal_path: str, max_lines: int = 3000):
    """
    Trim journal to prevent unbounded growth.
    Keeps the most recent max_lines entries.
    Archives older entries to a dated file.
    """
    try:
        p = Path(journal_path)
        if not p.exists():
            return

        with open(p, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if len(lines) <= max_lines:
            return

        # Archive old lines
        archive_dir = p.parent / 'archive'
        archive_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d')
        archive_path = archive_dir / f'journal_{ts}.md'

        old_lines = lines[:len(lines) - max_lines]
        with open(archive_path, 'w', encoding='utf-8') as f:
            f.writelines(old_lines)

        # Keep recent lines
        with open(p, 'w', encoding='utf-8') as f:
            f.writelines(lines[-max_lines:])

        logger.info(f"Journal trimmed: {len(old_lines)} lines archived to {archive_path}")

    except Exception as e:
        logger.error(f"Failed to trim journal: {e}")
