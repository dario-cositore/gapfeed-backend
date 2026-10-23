"""
Orchestrator — the state machine that runs Alex's main loop.

Controls round execution through explicit stages:
LOAD_STATE → READ → PLAN → SCOUT → NORMALIZE → VALIDATE → DEDUP
→ ENRICH → COMPLIANCE → STORE → REFLECT → SCHEDULE_NEXT → IDLE

Each stage has failure handling, backoff, and checkpointing.
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

ALEX_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ALEX_ROOT))

from app.config import load_config
from app.models.plan import Plan, PlanTarget, PlanEnrichmentFocus, StopConditions
from app.models.round import Round, RoundStatus
from app.enrichment import enrich_signal
from app.adapters import get_reddit, get_hn, get_rss, get_stackoverflow, get_devto, get_youtube
from app.adapters.indiehackers_adapter import get_indiehackers
from app.adapters.github_issues_adapter import get_github
from app.adapters.gnews_adapter import get_google_news
from app.adapters.github_discussions_adapter import get_github_discussions
from app.query_generator import QueryGenerator
from app.query_ledger import QueryLedger
from app.adapters.producthunt_adapter import get_producthunt
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.pipeline.normalize import normalize_batch
from app.pipeline.validate import validate_batch
from app.pipeline.dedupe import DedupeChecker, compute_cluster_id
from app.pipeline.store import ProfileStore
from app.pipeline.reflect import generate_reflection, append_to_journal, generate_source_stats
from app.pipeline.memory_review import (
    should_review, load_journal, trim_journal,
    update_source_stats, save_checkpoint, load_latest_checkpoint,
)

logger = logging.getLogger(__name__)


class AlexOrchestrator:
    """The main state machine for Alex Chen."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.running = False
        self.round_count = 0
        self.total_profiles_stored = 0

        # Paths
        self.memory_dir = Path(self.config['paths']['memory_dir'])
        self.state_dir = Path(self.config['paths']['state_dir'])
        self.logs_dir = Path(self.config['paths']['logs_dir'])

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Components (lazy init)
        self._reddit = None
        self._hn = None
        self._rss = None
        self._stackoverflow = None
        self._devto = None
        self._youtube = None
        self._indiehackers = None
        self._github = None
        self._gnews = None
        self._github_discussions = None
        self._query_generator = None
        self._query_ledger = None
        self._producthunt = None
        self._deduper = None
        self._store = None

    # --- Lazy component initialization ---

    @property
    def reddit(self):
        if self._reddit is None:
            cursor_file = str(self.state_dir / 'cursors' / 'reddit.json')
            self._reddit = get_reddit(cursor_file=cursor_file)
        return self._reddit

    @property
    def hn(self):
        if self._hn is None:
            cursor_file = str(self.state_dir / 'cursors' / 'hn.json')
            self._hn = get_hn(cursor_file=cursor_file)
        return self._hn

    @property
    def rss(self):
        if self._rss is None:
            cursor_file = str(self.state_dir / 'cursors' / 'rss.json')
            self._rss = get_rss(cursor_file=cursor_file)
        return self._rss

    @property
    def stackoverflow(self):
        if self._stackoverflow is None:
            cursor_file = str(self.state_dir / 'cursors' / 'stackoverflow.json')
            self._stackoverflow = get_stackoverflow(cursor_file=cursor_file)
        return self._stackoverflow

    @property
    def devto(self):
        if self._devto is None:
            cursor_file = str(self.state_dir / 'cursors' / 'devto.json')
            self._devto = get_devto(cursor_file=cursor_file)
        return self._devto

    @property
    def youtube(self):
        if self._youtube is None:
            cursor_file = str(self.state_dir / 'cursors' / 'youtube.json')
            api_key = self.config.get('api_keys', {}).get('youtube_api_key', '')
            self._youtube = get_youtube(api_key=api_key, cursor_file=cursor_file)
        return self._youtube

    @property
    def indiehackers(self):
        if self._indiehackers is None:
            cursor_file = str(self.state_dir / 'cursors' / 'indiehackers.json')
            self._indiehackers = get_indiehackers(cursor_file=cursor_file)
        return self._indiehackers

    @property
    def github(self):
        if self._github is None:
            cursor_file = str(self.state_dir / 'cursors' / 'github.json')
            token = self.config.get('api_keys', {}).get('github_token', '')
            self._github = get_github(token=token, cursor_file=cursor_file)
        return self._github

    @property
    def gnews(self):
        if self._gnews is None:
            cursor_file = str(self.state_dir / 'cursors' / 'gnews.json')
            self._gnews = get_google_news(cursor_file=cursor_file)
        return self._gnews

    @property
    def github_discussions(self):
        if self._github_discussions is None:
            cursor_file = str(self.state_dir / 'cursors' / 'github_discussions.json')
            token = self.config.get('api_keys', {}).get('github_token', '')
            self._github_discussions = get_github_discussions(token=token, cursor_file=cursor_file)
        return self._github_discussions

    @property
    def query_generator(self):
        if self._query_generator is None:
            self._query_generator = QueryGenerator()
        return self._query_generator

    @property
    def query_ledger(self):
        if self._query_ledger is None:
            ledger_file = str(self.state_dir / 'cursors' / 'query_ledger.json')
            self._query_ledger = QueryLedger(ledger_file=ledger_file)
        return self._query_ledger

    @property
    def producthunt(self):
        if self._producthunt is None:
            cursor_file = str(self.state_dir / 'cursors' / 'producthunt.json')
            self._producthunt = get_producthunt(cursor_file=cursor_file)
        return self._producthunt

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

    # --- State machine stages ---

    def _generate_round_id(self) -> str:
        """Generate a unique round ID."""
        ts = datetime.now().strftime('%Y%m%d_%H%M')
        short_uuid = uuid.uuid4().hex[:4]
        return f"round_{ts}_{short_uuid}"

    def _read_world(self) -> dict:
        """
        READ stage: consume world context.

        Returns dict with:
        - trending_topics: list of hot topics
        - world_events: list of detected events
        - context: natural language summary
        """
        context = {
            'trending_topics': [],
            'world_events': [],
            'context': '',
            'rss_items': [],
        }

        # Read RSS feeds for world context
        try:
            feeds = self.rss.get_default_feeds()
            all_items = []
            for category, feed_urls in feeds.items():
                items = self.rss.fetch_multiple(feed_urls[:2], limit_per_feed=5)
                all_items.extend(items)

            context['rss_items'] = all_items
            context['context'] = f"Read {len(all_items)} articles from {len(feeds)} feed categories"

            # Extract trending topics from titles
            titles = [item.get('title', '') for item in all_items if item.get('title')]
            context['trending_topics'] = titles[:10]

            # Also fetch HN top stories for trending context
            try:
                hn_stories = self.hn.fetch_top_stories(limit=15)
                for story in hn_stories:
                    context['trending_topics'].append({
                        'title': story.get('title', ''),
                        'url': story.get('url', ''),
                        'source': 'hackernews',
                    })
            except Exception as e:
                logger.warning(f"HN fetch for trending failed: {e}")

            # Convert RSS titles to dicts too
            context['trending_topics'] = [
                {'title': t, 'url': '', 'source': 'rss'} if isinstance(t, str) else t
                for t in context['trending_topics']
            ]

        except Exception as e:
            logger.error(f"READ stage failed: {e}")
            context['context'] = f"RSS read failed: {e}"

        return context

    def _make_plan(self, world_context: dict, round_id: str) -> Plan:
        """
        PLAN stage: decide what to scout this round.

        Simple strategy for now:
        - Scan 2-3 subreddits (rotating)
        - Run 1-2 web searches (pain patterns)
        - Fetch HN top stories
        """
        targets = []
        reasoning_parts = []

        # Reddit targets (rotate through subreddits)
        if self.config['sources']['reddit']:
            subreddits = self.reddit.get_available_subreddits()
            # Simple rotation: pick 8 based on round count
            idx = (self.round_count * 3) % len(subreddits)
            selected_subs = subreddits[idx:idx + 3]
            for sub in selected_subs:
                targets.append(PlanTarget(
                    source_key=f"reddit:r/{sub}",
                    priority=1.0,
                    reason=f"Rotating scan of r/{sub}",
                ))
            reasoning_parts.append(f"Reddit: scanning {', '.join(f'r/{s}' for s in selected_subs)}")

        # HN
        if self.config['sources'].get('hackernews', True):
            targets.append(PlanTarget(
                source_key="hn:top",
                priority=0.7,
                reason="Hacker News top stories",
            ))
            reasoning_parts.append("HN: top stories")

        # Stack Overflow (rotate through tags)
        if self.config['sources'].get('stackoverflow', True):
            tags = self.stackoverflow.get_tag_rotation()
            idx = self.round_count % len(tags)
            tag = tags[idx]
            targets.append(PlanTarget(
                source_key=f"so:tag:{tag}",
                priority=0.6,
                reason=f"Stack Overflow tag: {tag}",
            ))
            targets.append(PlanTarget(
                source_key="so:unanswered",
                priority=0.8,
                reason="Stack Overflow unanswered questions",
            ))
            reasoning_parts.append(f"SO: tag {tag} + unanswered")

        # Dev.to (rotate through tags)
        if self.config['sources'].get('devto', True):
            tags = self.devto.get_tag_rotation()
            idx = self.round_count % len(tags)
            tag = tags[idx]
            targets.append(PlanTarget(
                source_key=f"devto:tag:{tag}",
                priority=0.5,
                reason=f"Dev.to tag: {tag}",
            ))
            targets.append(PlanTarget(
                source_key="devto:latest",
                priority=0.4,
                reason="Dev.to latest articles",
            ))
            reasoning_parts.append(f"Dev.to: tag {tag} + latest")

        # YouTube (rotate through queries, budget-conscious)
        if self.config['sources'].get('youtube', True):
            targets.append(PlanTarget(
                source_key="youtube:scout",
                priority=0.5,
                reason="YouTube pain signal scout",
            ))
            reasoning_parts.append("YouTube: pain query scout")

        # Indie Hackers
        targets.append(PlanTarget(
            source_key="indiehackers:feed",
            priority=0.8,
            reason="Indie Hackers RSS feed - founder pain signals",
        ))
        reasoning_parts.append("Indie Hackers: RSS feed")

        # GitHub Issues
        targets.append(PlanTarget(
            source_key="github:pain",
            priority=0.8,
            reason="GitHub pain-focused issue search",
        ))
        reasoning_parts.append("GitHub: pain issue search")

        # Google News
        targets.append(PlanTarget(
            source_key="gnews:pain",
            priority=0.7,
            reason="Google News pain-focused articles",
        ))
        reasoning_parts.append("GNews: news pain articles")

        # GitHub Discussions
        targets.append(PlanTarget(
            source_key="github:discussions",
            priority=0.8,
            reason="GitHub Discussions pain signals",
        ))
        reasoning_parts.append("GitHub: discussions")

        # Product Hunt
        targets.append(PlanTarget(
            source_key="producthunt:scout",
            priority=0.7,
            reason="Product Hunt launches and discussions",
        ))
        reasoning_parts.append("Product Hunt: category scout")

        # Intelligent PLAN: Generate dynamic queries from trending topics
        trending = world_context.get('trending_topics', [])
        if trending:
            reasoning_parts.append(f"World context: {len(trending)} trending topics from RSS")

        # Generate dynamic queries if we have trending topics
        dynamic_queries = []
        if trending:
            try:
                pain_seeds = []  # Will use the ones baked into adapters
                dynamic_queries = self.query_generator.get_cached_or_generate(trending, pain_seeds)
                if dynamic_queries:
                    # Log dynamic queries used this round
                    reasoning_parts.append(f"Dynamic queries: {len(dynamic_queries)} generated from trends")
                    logger.info(f"Generated {len(dynamic_queries)} dynamic queries from trends")
            except Exception as e:
                logger.warning(f"Dynamic query generation failed: {e}")

        plan = Plan(
            round_id=round_id,
            reasoning=". ".join(reasoning_parts) if reasoning_parts else "Default scouting rotation",
            targets=targets,
            enrichment_focus=PlanEnrichmentFocus(),
            stop_conditions=StopConditions(
                max_raw_signals=self.config['round']['max_raw_signals_per_round'],
                max_llm_calls=self.config['round']['max_llm_calls_per_round'],
                max_round_minutes=self.config['round']['max_round_minutes'],
            ),
            dynamic_queries=dynamic_queries,
        )

        return plan

    def _scout_sources(self, plan: Plan) -> list[dict]:
        """
        SCOUT stage: execute plan targets and collect raw signals.
        Uses ThreadPoolExecutor to fetch from all sources in parallel.
        """
        all_raw = []
        sources_scanned = []

        def _fetch_target(target):
            """Fetch signals from a single target. Returns (source_key, signals)."""
            source_key = target.source_key
            raw_signals = []
            scan_id = None
            try:
                # Map source_key to source name for logging
                source_name = 'unknown'
                if source_key.startswith('reddit:'):
                    source_name = 'reddit'
                elif source_key.startswith('hn:'):
                    source_name = 'hackernews'
                elif source_key.startswith('so:'):
                    source_name = 'stackoverflow'
                elif source_key.startswith('devto:'):
                    source_name = 'devto'
                elif source_key.startswith('youtube:'):
                    source_name = 'youtube'
                elif source_key.startswith('indiehackers:'):
                    source_name = 'indiehackers'
                elif source_key.startswith('github:'):
                    source_name = 'github'
                elif source_key.startswith('gnews:'):
                    source_name = 'google_news'
                elif source_key.startswith('github:') and 'discussions' in source_key:
                    source_name = 'github_discussions'
                elif source_key.startswith('producthunt:'):
                    source_name = 'producthunt'
                
                # Log scan start
                try:
                    scan_id = self.store.db.log_scan(
                        vertical=self.config.get('vertical', 'general'),
                        source=source_name,
                        category=source_key
                    )
                except Exception as e:
                    logger.warning(f"Failed to log scan start for {source_key}: {e}")

                if source_key.startswith('reddit:'):
                    sub = source_key.replace('reddit:r/', '')
                    raw_signals = self.reddit.fetch_subreddit_posts(sub, sort='new', limit=30)

                elif source_key.startswith('hn:'):
                    raw_signals = self.hn.fetch_top_stories(limit=50)

                elif source_key.startswith('so:tag:'):
                    tag = source_key.replace('so:tag:', '')
                    raw_signals = self.stackoverflow.fetch_recent_questions(tag=tag, limit=30)

                elif source_key == 'so:unanswered':
                    raw_signals = self.stackoverflow.fetch_unanswered(limit=30)

                elif source_key.startswith('devto:tag:'):
                    tag = source_key.replace('devto:tag:', '')
                    raw_signals = self.devto.fetch_recent(tag=tag, limit=30)

                elif source_key == 'devto:latest':
                    raw_signals = self.devto.fetch_latest(limit=30)

                elif source_key == 'youtube:scout':
                    raw_signals = self.youtube.scout(limit_per_query=15)

                elif source_key == 'indiehackers:feed':
                    raw_signals = self.indiehackers.scout(max_results=30)

                elif source_key == 'github:pain':
                    raw_signals = self.github.scout(max_results=30)

                elif source_key == 'gnews:pain':
                    raw_signals = self.gnews.scout(max_results=50)

                elif source_key == 'github:discussions':
                    raw_signals = self.github_discussions.scout(max_results=30)

                elif source_key == 'producthunt:scout':
                    raw_signals = self.producthunt.scout(max_results=30)

            except Exception as e:
                logger.error(f"Scout failed for {source_key}: {e}")
            finally:
                # Log scan completion
                if scan_id is not None:
                    try:
                        self.store.db.complete_scan(
                            scan_id=scan_id,
                            signals_found=len(raw_signals),
                            signals_new=len(raw_signals)  # Assume all new for now
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log scan completion for {source_key}: {e}")

            return source_key, raw_signals

        # Fetch all targets in parallel (up to 7 threads)
        with ThreadPoolExecutor(max_workers=7) as executor:
            futures = {executor.submit(_fetch_target, t): t for t in plan.targets}
            for future in as_completed(futures):
                source_key, raw_signals = future.result()
                all_raw.extend(raw_signals)
                sources_scanned.append(source_key)
                logger.info(f"Scouted {source_key}: {len(raw_signals)} raw signals")

        logger.info(f"Scout complete: {len(all_raw)} total signals from {len(sources_scanned)} sources")
        return all_raw

    def _enrich_signals(self, signals: list, plan: Plan,
                        round_obj: Round) -> tuple[list[dict], list[dict]]:
        """
        ENRICH stage: run enrichment pipeline on validated signals.

        Returns (stored_profiles, discarded_profiles).
        """
        stored = []
        discarded = []
        llm_budget = plan.stop_conditions.max_llm_calls

        for signal in signals:
            try:
                # Use enrichment pipeline
                text = signal.text if hasattr(signal, 'text') else f"{signal.get('title', '')} {signal.get('body', '')}"
                source_url = signal.source_url if hasattr(signal, 'source_url') else signal.get('source_url', '')

                result = enrich_signal(
                    text=text,
                    source_url=source_url,
                    source_type='general',
                    vertical=self.config['vertical'],
                    llm_budget_remaining=llm_budget,
                    skip_llm = llm_budget <= 0 or self.config.get('enrichment', {}).get('skip_llm', False),
                )

                if result['llm_used']:
                    llm_budget -= 1
                    round_obj.llm_calls_made += 1

                if result['discard_reason']:
                    discarded.append(result)
                    round_obj.profiles_discarded += 1
                    continue

                profile = result['profile']
                if profile:
                    # Add cluster ID
                    profile['cluster_id'] = compute_cluster_id(
                        profile.get('pain_category', 'uncategorized'),
                        profile.get('personalization_data', []),
                    )
                    stored.append(profile)
                    round_obj.profiles_stored += 1

                    # Update confidence average
                    n = round_obj.profiles_stored
                    old_avg = round_obj.avg_confidence
                    round_obj.avg_confidence = old_avg + (profile.get('confidence', 0) - old_avg) / n

            except Exception as e:
                import traceback
                logger.error(f"Enrichment failed for signal: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                round_obj.profiles_discarded += 1

        return stored, discarded

    def _run_round(self):
        """Execute one full round of the state machine."""
        round_id = self._generate_round_id()
        self.round_count += 1

        round_obj = Round(
            round_id=round_id,
            trigger='scheduled',
            status=RoundStatus.RUNNING,
        )

        logger.info(f"=== Round {self.round_count} ({round_id}) ===")

        # Save checkpoint: round started
        save_checkpoint(
            str(self.memory_dir), round_id, 'STARTED',
            completed_steps=[], llm_budget=self.config['round']['max_llm_calls_per_round'],
        )

        try:
            # --- 1. READ ---
            logger.info("[1/8] READ: consuming world context...")
            world_context = self._read_world()

            save_checkpoint(str(self.memory_dir), round_id, 'READ',
                          completed_steps=['LOAD_STATE', 'READ'])

            # --- 2. PLAN ---
            logger.info("[2/8] PLAN: deciding what to scout...")
            plan = self._make_plan(world_context, round_id)

            # Write plan to file
            plan_path = self.memory_dir / 'plan.md'
            with open(plan_path, 'w') as f:
                f.write(plan.to_markdown())
            round_obj.plan_path = str(plan_path)

            save_checkpoint(str(self.memory_dir), round_id, 'PLAN',
                          completed_steps=['LOAD_STATE', 'READ', 'PLAN'])

            # --- 3. SCOUT ---
            logger.info("[3/8] SCOUT: collecting raw signals...")
            raw_signals = self._scout_sources(plan)
            round_obj.raw_signals_found = len(raw_signals)
            round_obj.sources_scanned = [t.source_key for t in plan.targets]

            save_checkpoint(str(self.memory_dir), round_id, 'SCOUT',
                          completed_steps=['LOAD_STATE', 'READ', 'PLAN', 'SCOUT'])

            if not raw_signals:
                logger.info("No raw signals collected this round")
                round_obj.status = RoundStatus.COMPLETED
                round_obj.ended_at = datetime.now(timezone.utc)
                return

            # --- 4. NORMALIZE ---
            logger.info(f"[4/8] NORMALIZE: processing {len(raw_signals)} raw signals...")
            normalized = normalize_batch(raw_signals)

            save_checkpoint(str(self.memory_dir), round_id, 'NORMALIZE',
                          completed_steps=['LOAD_STATE', 'READ', 'PLAN', 'SCOUT', 'NORMALIZE'])

            # --- 5. VALIDATE ---
            logger.info(f"[5/8] VALIDATE: checking {len(normalized)} signals...")
            validated, rejected = validate_batch(normalized)

            save_checkpoint(str(self.memory_dir), round_id, 'VALIDATE',
                          completed_steps=['LOAD_STATE', 'READ', 'PLAN', 'SCOUT', 'NORMALIZE', 'VALIDATE'])

            # --- 6. DEDUP ---
            logger.info(f"[6/8] DEDUP: removing duplicates from {len(validated)} signals...")
            unique, duplicates = self.deduper.dedup_batch(validated)
            round_obj.profiles_duplicate = len(duplicates)

            # --- 6b. CROSS-SOURCE CORRELATION ---
            if unique:
                logger.info(f"[6b] CORRELATE: checking cross-source patterns in {len(unique)} signals...")
                from app.pipeline.dedupe import correlate_cross_source
                unique = correlate_cross_source(unique)

            save_checkpoint(str(self.memory_dir), round_id, 'DEDUP',
                          completed_steps=['LOAD_STATE', 'READ', 'PLAN', 'SCOUT', 'NORMALIZE', 'VALIDATE', 'DEDUP'])

            # --- 7. ENRICH + STORE ---
            logger.info(f"[7/8] ENRICH: enriching {len(unique)} unique signals...")
            stored_profiles, discarded_profiles = self._enrich_signals(unique, plan, round_obj)

            # Store to MySQL
            if stored_profiles:
                store_result = self.store.store_batch(stored_profiles)
                logger.info(f"Stored {store_result['stored']} profiles to MySQL")

                # Record outcomes to query ledger
                try:
                    source_counts = {}
                    high_relevance_by_source = {}
                    for p in stored_profiles:
                        src = p.get('source_type', 'unknown')
                        source_counts[src] = source_counts.get(src, 0) + 1
                        if p.get('confidence', 0) >= 0.7:
                            high_relevance_by_source[src] = high_relevance_by_source.get(src, 0) + 1

                    # Record for each dynamic query used this round
                    if hasattr(plan, 'dynamic_queries') and plan.dynamic_queries:
                        for query in plan.dynamic_queries[:10]:
                            # Attribute to the source that ran it (ddg for web searches)
                            self.query_ledger.record_outcome(
                                query=query,
                                source='ddg',
                                signals_found=source_counts.get('web_search', 0),
                                high_relevance=high_relevance_by_source.get('web_search', 0),
                                gaps_created=0  # Gaps recorded separately
                            )
                except Exception as e:
                    logger.warning(f"Query ledger recording failed: {e}")

            self.total_profiles_stored += round_obj.profiles_stored

            save_checkpoint(str(self.memory_dir), round_id, 'STORE',
                          completed_steps=['LOAD_STATE', 'READ', 'PLAN', 'SCOUT', 'NORMALIZE',
                                          'VALIDATE', 'DEDUP', 'ENRICH', 'STORE'])

            # --- 8. REFLECT ---
            logger.info("[8/8] REFLECT: writing journal entry...")

            # Collect enrichment successes/failures for reflection
            successes = []
            failures = []
            for p in stored_profiles[:5]:
                conf = p.get('confidence', 0)
                cat = p.get('pain_category', '?')
                successes.append(f"{cat} (confidence: {conf:.2f})")

            # Generate and append reflection
            entry = generate_reflection(
                round_id=round_id,
                plan_reasoning=plan.reasoning,
                sources_scanned=round_obj.sources_scanned,
                raw_signals_found=round_obj.raw_signals_found,
                profiles_stored=round_obj.profiles_stored,
                profiles_discarded=round_obj.profiles_discarded,
                profiles_duplicate=round_obj.profiles_duplicate,
                avg_confidence=round_obj.avg_confidence,
                avg_actionability=round_obj.avg_actionability,
                top_pain_categories=[p.get('pain_category', '?') for p in stored_profiles[:5]],
                enrichment_successes=successes,
                enrichment_failures=failures,
                llm_calls_made=round_obj.llm_calls_made,
                errors=round_obj.errors,
            )

            journal_path = str(self.memory_dir / 'journal.md')
            append_to_journal(journal_path, entry)
            round_obj.notes_path = journal_path

            # Periodic memory review
            if should_review(self.round_count, self.config['memory']['review_interval']):
                logger.info("Running memory review...")
                trim_journal(journal_path, self.config['memory']['journal_max_lines'])

            # Update source stats
            source_perf = {}
            for target in plan.targets:
                raw_count = sum(1 for s in raw_signals
                               if target.source_key.split(':')[1] in str(s.get('platform_metadata', {})))
                stored_count = round_obj.profiles_stored // max(len(plan.targets), 1)
                source_perf[target.source_key] = {
                    'raw': raw_count,
                    'stored': stored_count,
                    'avg_confidence': round_obj.avg_confidence,
                    'noise_rate': round_obj.profiles_discarded / max(round_obj.raw_signals_found, 1),
                }
            update_source_stats(str(self.memory_dir), source_perf)

            round_obj.status = RoundStatus.COMPLETED
            round_obj.ended_at = datetime.now(timezone.utc)

            # Store round metadata
            self.store.store_round(round_obj.model_dump())

            logger.info(f"Round {self.round_count} complete: "
                        f"{round_obj.profiles_stored} stored, "
                        f"{round_obj.profiles_discarded} discarded, "
                        f"{round_obj.profiles_duplicate} duplicates, "
                        f"{round_obj.llm_calls_made} LLM calls")

        except Exception as e:
            round_obj.status = RoundStatus.FAILED
            round_obj.errors.append(str(e))
            round_obj.ended_at = datetime.now(timezone.utc)
            logger.error(f"Round {self.round_id if hasattr(self, 'round_id') else '?'} failed: {e}", exc_info=True)

    def start(self):
        """Start the orchestrator loop."""
        self.running = True

        # Signal handlers for graceful shutdown
        signal_mod.signal(signal_mod.SIGINT, self._shutdown)
        signal_mod.signal(signal_mod.SIGTERM, self._shutdown)

        logger.info(f"Alex Chen starting up")
        logger.info(f"Config: {json.dumps({k: v for k, v in self.config.items() if k != 'api_keys'}, indent=2)}")

        # Check for crash recovery checkpoint
        checkpoint = load_latest_checkpoint(str(self.memory_dir))
        if checkpoint:
            logger.info(f"Found checkpoint: round {checkpoint.get('round_id')}, stage {checkpoint.get('stage')}")
            logger.info("Starting fresh round (checkpoint recovery not yet implemented)")

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
        logger.info(f"Final stats: {self.round_count} rounds, {self.total_profiles_stored} total profiles stored")
