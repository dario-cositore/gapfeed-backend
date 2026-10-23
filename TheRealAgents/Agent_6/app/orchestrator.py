"""
Agent_6 — Signal Classifier
Orchestrator — the state machine that runs Maya's classification loop.

Controls cycle execution through explicit stages:
LOAD_STATE → FETCH_SIGNALS → PRE_CLASSIFY → LLM_CLASSIFY → SCORE → WRITE_BACK → SLEEP

Each stage has failure handling and logging.
"""

import json
import logging
import signal as signal_mod
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

MAYA_DIR = Path(__file__).resolve().parent.parent
TUXO_DIR = MAYA_DIR.parent.parent
sys.path.insert(0, str(MAYA_DIR))
sys.path.insert(0, str(TUXO_DIR))

from app.config import load_config
from app.classifier.rules import pre_classify
from app.classifier.llm_classifier import classify_signal, classify_batch
from app.classifier.confidence import score_confidence
from app.pipeline.reader import get_unprocessed_signals
from app.pipeline.writer import write_classification, write_batch
from app.pipeline.batcher import prepare_batches, enrich_batch_with_rules
from app.models.signal import SignalView
from src.engines.gap_detector import run_gap_detection
from app.pipeline.page_generator import run_full_pipeline

logger = logging.getLogger(__name__)


class MayaOrchestrator:
    """The main state machine for Agent_6."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.running = False
        self.cycle_count = 0
        self.total_classified = 0
        self.total_noise = 0
        self.total_errors = 0
        self.total_gold = 0
        self.total_silver = 0
        self.total_bronze = 0
        self.total_gaps_created = 0
        self.total_signals_linked = 0

        # Paths
        self.memory_dir = Path(self.config['paths']['memory_dir'])
        self.state_dir = Path(self.config['paths']['state_dir'])
        self.logs_dir = Path(self.config['paths']['logs_dir'])

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _run_cycle(self):
        """Execute one full classification cycle."""
        self.cycle_count += 1
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M')}_{uuid.uuid4().hex[:4]}"

        logger.info(f"=== Cycle {self.cycle_count} ({cycle_id}) ===")
        cycle_start = time.time()

        try:
            # --- 1. FETCH ---
            logger.info("[1/6] FETCH: pulling unprocessed signals...")
            batch_size = self.config['cycle']['batch_size']
            min_text = self.config['classification']['min_text_length']

            raw_signals = get_unprocessed_signals(
                limit=batch_size,
                min_text_length=min_text,
            )

            if not raw_signals:
                logger.info("No unprocessed signals found. Sleeping...")
                return

            logger.info(f"Fetched {len(raw_signals)} unprocessed signals")

            # Build signal views for processing
            signals = []
            for s in raw_signals:
                sv = SignalView.from_dict(s)
                signals.append({
                    'id': sv.id,
                    'text': sv.full_text,
                    'source': f"{sv.source}:{sv.subreddit}" if sv.subreddit else sv.source,
                    'title': sv.title,
                    'content': sv.content,
                })

            # --- 2. PRE-CLASSIFY ---
            logger.info(f"[2/6] PRE-CLASSIFY: running rules on {len(signals)} signals...")
            for s in signals:
                s['pre_classification'] = pre_classify(s['text'], s.get('source', ''))

            # Separate noise from needs-LLM
            noise_signals = []
            needs_llm = []
            for s in signals:
                pre = s['pre_classification']
                if pre['is_noise'] or pre.get('skip_llm', False):
                    noise_signals.append(s)
                else:
                    needs_llm.append(s)

            logger.info(f"  Pre-classified: {len(noise_signals)} noise, {len(needs_llm)} need LLM")

            # --- 3. LLM CLASSIFY ---
            llm_config = self.config.get('llm', {})
            max_llm_calls = self.config['cycle']['max_llm_calls_per_cycle']
            llm_budget = max_llm_calls
            enable_llm = self.config['classification']['enable_llm']

            classifications = []

            # Process noise signals (no LLM needed)
            for s in noise_signals:
                pre = s['pre_classification']
                c = {
                    'signal_id': s['id'],
                    'pain_category': 'uncategorized',
                    'urgency_score': 0.0,
                    'specificity_score': 0.0,
                    'buyer_intent': 0.0,
                    'quality_tier': 'noise',
                    'sentiment': 'neutral',
                    'signal_type': 'discussion',
                    'location': None,
                    'product_category': None,
                    'competitor_mentions': [],
                    'reasoning': pre.get('noise_reason', 'Filtered by pre-classification rules'),
                    'llm_used': False,
                    'pre_classification': pre,
                    'confidence': 0.8,
                }
                classifications.append(c)

            # Process signals needing LLM
            if needs_llm and enable_llm:
                logger.info(f"[3/6] LLM CLASSIFY: analyzing {len(needs_llm)} signals (budget: {llm_budget})...)")

                # Use batch classification for efficiency
                batch_size_llm = 7
                batches = prepare_batches(needs_llm, batch_size=batch_size_llm)

                # Limit to budget
                total_signals = min(sum(len(b) for b in batches), llm_budget)
                batches = batches[:total_signals // batch_size_llm + (1 if total_signals % batch_size_llm else 0)]

                # Parallel batch classification (3 concurrent)
                def classify_one_batch(batch):
                    try:
                        return classify_batch(batch, llm_config=llm_config)
                    except Exception as e:
                        logger.error(f"Batch LLM classification failed: {e}")
                        return None

                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {executor.submit(classify_one_batch, b): b for b in batches}
                    for future in as_completed(futures):
                        batch = futures[future]
                        batch_results = future.result()

                        if batch_results is None:
                            # Fallback to rule-based for this batch
                            self.total_errors += 1
                            for s in batch:
                                pre = s['pre_classification']
                                c = {
                                    'signal_id': s['id'],
                                    'pain_category': 'uncategorized',
                                    'urgency_score': pre.get('pre_urgency', 0),
                                    'specificity_score': pre.get('pre_specificity', 0),
                                    'buyer_intent': pre.get('pre_buyer_intent', 0),
                                    'quality_tier': pre.get('pre_quality_tier', 'noise'),
                                    'sentiment': 'neutral',
                                    'signal_type': 'discussion',
                                    'location': None,
                                    'product_category': None,
                                    'competitor_mentions': [],
                                    'reasoning': f'LLM error, using rule-based fallback',
                                    'llm_used': False,
                                    'pre_classification': pre,
                                    'confidence': 0.3,
                                }
                                classifications.append(c)
                        else:
                            for result in batch_results:
                                signal_id = result.get('signal_id')
                                matching_signal = next((s for s in batch if s['id'] == signal_id), None)
                                pre = matching_signal['pre_classification'] if matching_signal else {}
                                result['confidence'] = score_confidence(result, pre)
                                result['pre_classification'] = pre
                                classifications.append(result)

            elif needs_llm and not enable_llm:
                logger.info("LLM disabled, using rule-based classification for all")
                for s in needs_llm:
                    pre = s['pre_classification']
                    pm = pre.get('product_mentions') or [None]
                    c = {
                        'signal_id': s['id'],
                        'pain_category': 'uncategorized',
                        'urgency_score': pre.get('pre_urgency', 0),
                        'specificity_score': pre.get('pre_specificity', 0),
                        'buyer_intent': pre.get('pre_buyer_intent', 0),
                        'quality_tier': pre.get('pre_quality_tier', 'bronze'),
                        'sentiment': 'neutral',
                        'signal_type': 'discussion',
                        'location': None,
                        'product_category': pm[0],
                        'competitor_mentions': [],
                        'reasoning': 'LLM disabled, rule-based only',
                        'llm_used': False,
                        'pre_classification': pre,
                        'confidence': 0.5,
                    }
                    classifications.append(c)

            # --- 4. SCORE ---
            logger.info(f"[4/6] SCORE: evaluating {len(classifications)} classifications...")
            for c in classifications:
                if 'confidence' not in c or c['confidence'] == 0:
                    c['confidence'] = score_confidence(c, c.get('pre_classification'))

            # --- 5. WRITE BACK ---
            logger.info(f"[5/6] WRITE: pushing {len(classifications)} classifications to DB...")
            successes, failures = write_batch(classifications)

            # --- 5.5 GAP DETECT ---
            gap_config = self.config.get('gap_detection', {})
            gap_enabled = gap_config.get('enabled', True)
            gap_interval = gap_config.get('run_every_n_cycles', 3)

            if gap_enabled and self.cycle_count % gap_interval == 0:
                logger.info(f"[5.5/6] GAP DETECT: running gap detection (cycle {self.cycle_count})...")
                try:
                    vertical = self.config.get('vertical')
                    gap_stats = run_gap_detection(
                        vertical=vertical if vertical != 'general' else None,
                        batch_size=gap_config.get('batch_size', 500),
                        min_cluster_size=gap_config.get('min_cluster_size', 2),
                    )
                    self.total_gaps_created += gap_stats.get('gaps_created', 0)
                    self.total_signals_linked += gap_stats.get('signals_linked', 0)
                    logger.info(f"  Gaps: created={gap_stats.get('gaps_created', 0)}, "
                                f"linked={gap_stats.get('signals_linked', 0)}, "
                                f"clusters={gap_stats.get('clusters_processed', 0)}")

                    # --- 5.6 PAGE GENERATION ---
                    # After gap detection, regenerate static pages + sitemap + deploy
                    try:
                        page_config = gap_config.get('page_generation', {})
                        if page_config.get('enabled', True):
                            logger.info(f"[5.6/6] PAGE GEN: generating static pages + sitemap + deploy...")
                            page_result = run_full_pipeline(
                                gaps_created_count=gap_stats.get('gaps_created', 0)
                            )
                            logger.info(f"  Pages: {page_result.get('pages_generated', 0)} generated, "
                                        f"{page_result.get('sitemap_urls', 0)} sitemap URLs, "
                                        f"{page_result.get('deployed_items', 0)} items deployed")
                    except Exception as e:
                        logger.error(f"Page generation failed: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Gap detection failed: {e}", exc_info=True)

            # --- 6. STATS ---
            cycle_noise = sum(1 for c in classifications if c.get('quality_tier') == 'noise')
            cycle_gold = sum(1 for c in classifications if c.get('quality_tier') == 'gold')
            cycle_silver = sum(1 for c in classifications if c.get('quality_tier') == 'silver')
            cycle_bronze = sum(1 for c in classifications if c.get('quality_tier') == 'bronze')
            cycle_llm = sum(1 for c in classifications if c.get('llm_used'))
            avg_confidence = sum(c.get('confidence', 0) for c in classifications) / max(len(classifications), 1)

            self.total_classified += successes
            self.total_noise += cycle_noise
            self.total_gold += cycle_gold
            self.total_silver += cycle_silver
            self.total_bronze += cycle_bronze
            self.total_errors += failures

            elapsed = time.time() - cycle_start

            logger.info(f"[6/6] STATS: Cycle {self.cycle_count} complete in {elapsed:.1f}s")
            logger.info(f"  Classified: {successes} (gold={cycle_gold}, silver={cycle_silver}, "
                        f"bronze={cycle_bronze}, noise={cycle_noise})")
            logger.info(f"  LLM calls: {cycle_llm}, Avg confidence: {avg_confidence:.2f}")
            logger.info(f"  Totals: {self.total_classified} classified, {self.total_gold} gold, "
                        f"{self.total_gaps_created} gaps, {self.total_errors} errors")

            # Periodic stats logging
            if self.cycle_count % self.config['memory']['stats_log_interval'] == 0:
                self._write_stats()

        except Exception as e:
            self.total_errors += 1
            logger.error(f"Cycle {self.cycle_count} failed: {e}", exc_info=True)

    def _write_stats(self):
        """Write running stats to memory file."""
        stats = {
            'cycles': self.cycle_count,
            'total_classified': self.total_classified,
            'total_gold': self.total_gold,
            'total_silver': self.total_silver,
            'total_bronze': self.total_bronze,
            'total_noise': self.total_noise,
            'total_gaps_created': self.total_gaps_created,
            'total_signals_linked': self.total_signals_linked,
            'total_errors': self.total_errors,
            'last_updated': datetime.now(timezone.utc).isoformat(),
        }
        stats_file = self.state_dir / 'stats.json'
        try:
            with open(stats_file, 'w') as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write stats: {e}")

    def start(self):
        """Start the orchestrator loop."""
        self.running = True

        # Signal handlers for graceful shutdown
        signal_mod.signal(signal_mod.SIGINT, self._shutdown)
        signal_mod.signal(signal_mod.SIGTERM, self._shutdown)

        logger.info("Agent_6 starting up")
        logger.info(f"Config: {json.dumps({k: v for k, v in self.config.items() if k != 'api_keys'}, indent=2)}")

        sleep_seconds = self.config['cycle']['sleep_between_cycles']

        while self.running:
            try:
                self._run_cycle()
            except Exception as e:
                logger.error(f"Orchestrator error: {e}", exc_info=True)

            if self.running:
                logger.info(f"Sleeping {sleep_seconds}s until next cycle...")
                for _ in range(sleep_seconds):
                    if not self.running:
                        break
                    time.sleep(1)

        self._write_stats()

    def _shutdown(self, signum=None, frame=None):
        """Graceful shutdown."""
        logger.info(f"Shutting down (signal {signum})...")
        self.running = False
        logger.info(f"Final stats: {self.cycle_count} cycles, "
                    f"{self.total_classified} classified, "
                    f"{self.total_gold} gold, {self.total_gaps_created} gaps, {self.total_errors} errors")
