"""
Orchestrator — the state machine that runs Agent_2's main loop.

Jack is the HIGH-VOLUME API SCOUT. He uses HTTP APIs (Reddit JSON, HN Firebase,
Dev.to REST, Stack Overflow, GitHub, RSS) for maximum throughput.
NO search engines (they block headless browsers).
NO browser scraping (too slow for 100k/day).

Target: 100k+ signals/day using pure API calls.
"""

import json
import logging
import signal as signal_mod
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

from app.config import load_config
from app.models.plan import Plan, PlanTarget, PlanEnrichmentFocus, StopConditions
from app.models.round import Round, RoundStatus
from app.enrichment import enrich_signal
from app.adapters.high_volume_scraper import HighVolumeScraper
from app.pipeline.normalize import normalize_batch
from app.pipeline.validate import validate_batch
from app.pipeline.dedupe import DedupeChecker, compute_cluster_id
from app.pipeline.store import ProfileStore
from app.pipeline.reflect import generate_reflection, append_to_journal
from app.pipeline.memory_review import (
    should_review, load_journal, trim_journal,
    save_checkpoint, load_latest_checkpoint,
)

logger = logging.getLogger(__name__)


class JackOrchestrator:
    """The main state machine for Agent_2 - HIGH-VOLUME API SCOUT."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.running = False
        self.round_count = 0
        self.total_profiles_stored = 0

        # Paths
        self.memory_dir = Path(self.config['paths']['memory_dir'])
        self.state_dir = Path(self.config['paths']['state_dir'])
        self.logs_dir = Path(self.config['paths']['logs_dir'])

        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Components (lazy init)
        self._scraper = None
        self._deduper = None
        self._store = None

    @property
    def scraper(self):
        if self._scraper is None:
            cursor_file = str(self.state_dir / 'cursors' / 'high_volume.json')
            self._scraper = HighVolumeScraper(cursor_file=cursor_file)
        return self._scraper

    @property
    def deduper(self):
        if self._deduper is None:
            state_file = str(self.state_dir / 'dedup_state.json')
            self._deduper = DedupeChecker(state_file=state_file)
        return self._deduper

    @property
    def store(self):
        if self._store is None:
            self._store = ProfileStore()
        return self._store

    def _generate_round_id(self) -> str:
        ts = datetime.now().strftime('%Y%m%d_%H%M')
        short_uuid = uuid.uuid4().hex[:4]
        return f"round_{ts}_{short_uuid}"

    def _run_round(self):
        """Execute one full round."""
        round_id = self._generate_round_id()
        self.round_count += 1

        round_obj = Round(
            round_id=round_id,
            trigger='scheduled',
            status=RoundStatus.RUNNING,
        )

        logger.info(f"=== Round {self.round_count} ({round_id}) ===")

        save_checkpoint(
            str(self.memory_dir), round_id, 'STARTED',
            completed_steps=[], llm_budget=0,
        )

        try:
            # --- SCOUT ---
            logger.info("[1/4] SCOUT: high-volume API scraping...")
            raw_signals = self.scraper.scout_round(
                reddit_subs=self.config.get('scout', {}).get('reddit_subs', 15),
                devto_tags=self.config.get('scout', {}).get('devto_tags', 1),
                so_tags=self.config.get('scout', {}).get('so_tags', 1),
                github_searches=self.config.get('scout', {}).get('github_searches', 1),
                rss_categories=self.config.get('scout', {}).get('rss_categories', 2),
            )
            round_obj.raw_signals_found = len(raw_signals)

            if not raw_signals:
                logger.info("No raw signals collected this round")
                round_obj.status = RoundStatus.COMPLETED
                round_obj.ended_at = datetime.now(timezone.utc)
                return

            # --- NORMALIZE ---
            logger.info(f"[2/4] NORMALIZE: processing {len(raw_signals)} raw signals...")
            normalized = normalize_batch(raw_signals)

            # --- VALIDATE + DEDUP ---
            logger.info(f"[3/4] VALIDATE + DEDUP...")
            validated, rejected = validate_batch(normalized)
            unique, duplicates = self.deduper.dedup_batch(validated)
            round_obj.profiles_duplicate = len(duplicates)

            # --- FAST ENRICH + STORE ---
            logger.info(f"[4/4] FAST_ENRICH + STORE: {len(unique)} signals...")
            stored = []
            discarded = []

            for signal in unique:
                try:
                    text = signal.text if hasattr(signal, 'text') else f"{signal.get('title', '')} {signal.get('body', '')}"
                    source_url = signal.source_url if hasattr(signal, 'source_url') else signal.get('source_url', '')

                    result = enrich_signal(
                        text=text,
                        source_url=source_url,
                        source_type='general',
                        vertical=self.config.get('vertical', 'general'),
                        llm_budget_remaining=0,
                        skip_llm=True,
                    )

                    if result['discard_reason']:
                        discarded.append(result)
                        round_obj.profiles_discarded += 1
                        continue

                    profile = result['profile']
                    if profile:
                        profile['cluster_id'] = compute_cluster_id(
                            profile.get('pain_category', 'uncategorized'),
                            profile.get('personalization_data', []),
                        )
                        stored.append(profile)
                        round_obj.profiles_stored += 1

                except Exception as e:
                    round_obj.profiles_discarded += 1

            if stored:
                store_result = self.store.store_batch(stored)
                logger.info(f"Stored {store_result['stored']} profiles to MySQL")

            self.total_profiles_stored += round_obj.profiles_stored

            round_obj.status = RoundStatus.COMPLETED
            round_obj.ended_at = datetime.now(timezone.utc)

            self.store.store_round(round_obj.model_dump())

            logger.info(f"Round {self.round_count} complete: "
                        f"{round_obj.profiles_stored} stored, "
                        f"{round_obj.profiles_discarded} discarded, "
                        f"{round_obj.profiles_duplicate} duplicates, "
                        f"{round_obj.raw_signals_found} raw signals")

        except Exception as e:
            round_obj.status = RoundStatus.FAILED
            round_obj.errors.append(str(e))
            round_obj.ended_at = datetime.now(timezone.utc)
            logger.error(f"Round {self.round_count} failed: {e}", exc_info=True)

    def start(self):
        """Start the orchestrator loop."""
        self.running = True

        signal_mod.signal(signal_mod.SIGINT, self._shutdown)
        signal_mod.signal(signal_mod.SIGTERM, self._shutdown)

        logger.info(f"Agent_2 starting up — HIGH-VOLUME API SCOUT MODE")
        logger.info(f"Config: {json.dumps({k: v for k, v in self.config.items() if k != 'api_keys'}, indent=2)}")

        sleep_seconds = self.config.get('round', {}).get('sleep_between_rounds', 0)

        while self.running:
            try:
                self._run_round()
            except Exception as e:
                logger.error(f"Orchestrator error: {e}", exc_info=True)

            if self.running and sleep_seconds > 0:
                logger.info(f"Sleeping {sleep_seconds}s until next round...")
                for _ in range(sleep_seconds):
                    if not self.running:
                        break
                    time.sleep(1)

    def _shutdown(self, signum=None, frame=None):
        logger.info(f"Shutting down (signal {signum})...")
        self.running = False
        logger.info(f"Final stats: {self.round_count} rounds, {self.total_profiles_stored} total profiles stored")
