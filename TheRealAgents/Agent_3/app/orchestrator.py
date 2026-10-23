"""
Agent_3 - Gap Validator Agent

Validates market gaps by searching for existing competitors/solutions.
Runs periodically (every 10 minutes) to validate unvalidated gaps.

State machine:
1. FETCH_UNVALIDATED - Get gaps that haven't been validated yet
2. SEARCH_COMPETITORS - Search for existing solutions
3. EXTRACT_DATA - Extract competitor info from search results
4. UPDATE_GAP - Store competitors and update gap_validity
5. SLEEP - Wait for next round
"""

import json
import logging
import signal as signal_mod
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parent.parent
TUXO_ROOT = AGENT_ROOT.parent.parent  # Goes up to tuxo/
SHARED_ROOT = TUXO_ROOT / 'shared'
sys.path.insert(0, str(AGENT_ROOT))
sys.path.insert(0, str(SHARED_ROOT))

# Import shared modules
import importlib.util
spec = importlib.util.spec_from_file_location("competitor_lookup", SHARED_ROOT / "competitor_lookup.py")
competitor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(competitor_module)
CompetitorLookup = competitor_module.CompetitorLookup

from app.config import load_config
from remote_db import RemoteDB

logger = logging.getLogger(__name__)

class JakeOrchestrator:
    """The main state machine for Agent_3."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.running = False
        self.round_count = 0
        self.gaps_validated = 0

        # Paths
        self.memory_dir = Path(self.config['paths']['memory_dir'])
        self.state_dir = Path(self.config['paths']['state_dir'])
        self.logs_dir = Path(self.config['paths']['logs_dir'])

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Components
        self.db = RemoteDB()
        self.lookup = CompetitorLookup()

    def _fetch_unvalidated_gaps(self) -> list[dict]:
        """Fetch gaps that need validation."""
        try:
            # Get all active gaps
            result = self.db._request('get_gaps', {
                'limit': 50,
                'offset': 0
            })
            
            if 'error' in result:
                logger.error(f"Failed to fetch gaps: {result['error']}")
                return []
            
            gaps = result.get('gaps', [])
            
            # Filter for unvalidated gaps
            if self.config['validation']['only_validate_unvalidated']:
                gaps = [g for g in gaps if not g.get('last_validated_at')]
            
            # Only validate gaps with enough signals
            min_signals = self.config['validation']['min_signals_for_validation']
            gaps = [g for g in gaps if g.get('evidence_count', 0) >= min_signals]
            
            return gaps[:self.config['validation']['batch_size']]
            
        except Exception as e:
            logger.error(f"Error fetching gaps: {e}")
            return []

    def _validate_gap(self, gap: dict) -> bool:
        """Validate a single gap by searching for competitors."""
        gap_id = gap.get('id')
        title = gap.get('title', '')
        category = gap.get('category', '')
        description = gap.get('description', '')
        
        logger.info(f"Validating gap {gap_id}: {title}")
        
        try:
            # Calculate demand score from evidence_count and heat_score
            evidence = gap.get('evidence_count', 0)
            heat = gap.get('heat_score', 0)
            demand_score = min(1.0, (evidence / 50) * 0.5 + heat * 0.5)
            
            # Get pain signals for this gap (from signal_ids)
            signal_ids = gap.get('signal_ids', [])
            pain_signals = []
            if signal_ids:
                try:
                    # Fetch signals by gap_id
                    sig_result = self.db._request('get_signals', {
                        'gap_id': gap_id,
                        'limit': 30
                    })
                    pain_signals = sig_result.get('signals', [])
                except Exception as e:
                    logger.warning(f"Failed to fetch signals for gap {gap_id}: {e}")
            
            # Run validation with LLM client
            from llm_client import llm_call
            self.lookup.llm_client = llm_call
            
            result = self.lookup.validate_gap(
                gap_title=title,
                category=category,
                description=description,
                pain_signals=pain_signals,
                demand_score=demand_score
            )
            
            # Update gap with competitor data and new scoring
            update_result = self.db._request('update_gap_competitors', {
                'gap_id': gap_id,
                'competitors': result['competitors'],
                'gap_validity': result['scoring']['verdict'],
                'opportunity_score': result['scoring']['opportunity_score'],
            })
            
            if update_result.get('ok'):
                logger.info(f"Gap {gap_id} validated: {result['competitor_count']} valid competitors, "
                          f"opportunity={result['scoring']['opportunity_score']:.2f}, "
                          f"verdict={result['scoring']['verdict']}")
                self.gaps_validated += 1
                return True
            else:
                logger.error(f"Failed to update gap {gap_id}: {update_result}")
                return False
                
        except Exception as e:
            logger.error(f"Error validating gap {gap_id}: {e}")
            return False

    def _run_round(self):
        """Execute one validation round."""
        self.round_count += 1
        logger.info(f"=== Round {self.round_count} ===")

        # Fetch unvalidated gaps
        gaps = self._fetch_unvalidated_gaps()
        logger.info(f"Found {len(gaps)} gaps to validate")

        if not gaps:
            logger.info("No gaps need validation this round")
            return

        # Validate each gap
        for gap in gaps:
            if not self.running:
                break
            self._validate_gap(gap)
            time.sleep(2)  # Rate limit between searches

        logger.info(f"Round {self.round_count} complete: validated {len(gaps)} gaps")

    def start(self):
        """Start the validator loop."""
        self.running = True

        # Signal handlers for graceful shutdown
        signal_mod.signal(signal_mod.SIGINT, self._shutdown)
        signal_mod.signal(signal_mod.SIGTERM, self._shutdown)

        logger.info(f"Agent_3 starting up")
        logger.info(f"Config: {json.dumps({k: v for k, v in self.config.items() if k != 'api_keys'}, indent=2)}")

        sleep_seconds = self.config['round']['sleep_between_rounds']

        while self.running:
            try:
                self._run_round()
            except Exception as e:
                logger.error(f"Orchestrator error: {e}", exc_info=True)

            if self.running:
                logger.info(f"Sleeping {sleep_seconds}s until next round...")
                for _ in range(sleep_seconds):
                    if not self.running:
                        break
                    time.sleep(1)

    def _shutdown(self, signum=None, frame=None):
        """Graceful shutdown."""
        logger.info(f"Shutting down (signal {signum})...")
        self.running = False
        logger.info(f"Final stats: {self.round_count} rounds, {self.gaps_validated} gaps validated")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [Agent_3] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    orchestrator = JakeOrchestrator()
    orchestrator.start()
