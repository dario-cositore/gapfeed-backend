#!/usr/bin/env python3
"""
Luna Hart - Orchestrator
Main state machine that coordinates all modules.
"""
import time
import json
import os
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path

# --- Environment Setup for Shared Modules ---
# Path adjustment as per requirement for shared LLM client
try:
    # orchestrator.py is in C:\...\tuxo\TheRealAgents\Luna Hart\app
    # shared is in C:\...\tuxo\shared
    # So we need to go up 3 levels: app -> Luna Hart -> TheRealAgents -> tuxo
    tuxo_root = Path(__file__).resolve().parent.parent.parent.parent
    sys.path.insert(0, str(tuxo_root))
    from shared.llm_client import llm_call
except Exception as e:
    # Handle case where path adjustment or import fails (e.g., running outside expected structure)
    print(f"Warning: Could not adjust path or import llm_call: {e}")
    llm_call = None  # Define a placeholder if import fails

# --- Module Imports ---
from trend_scout import TrendScout
from social_manager import SocialManager
from analytics import Analytics
from content_engine import ContentEngine
from memory import MemoryManager # Memory management module
from performance_tracker import PerformanceTracker
from blog_manager import BlogManager

class Orchestrator:
    """Main orchestrator for Luna Hart agent."""

    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.state_file = os.path.join(
            os.path.dirname(__file__), '..', 'state', 'current.json'
        )
        self.memory_dir = os.path.join(
            os.path.dirname(__file__), '..', 'memory'
        )
        self.state = {} # Initialize state now
        self.trends_file = os.path.join(os.path.dirname(self.state_file), 'trends.json')
        self.content_plan = None # To store the result of plan_content
        self.load_state()

    def load_state(self):
        """Load current state from file."""
        try:
            with open(self.state_file, 'r') as f:
                self.state = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.state = {
                "current_cycle": 0,
                "last_trend_scout": None,
                "last_content_creation": None,
                "last_engagement_check": None,
                "posts_today": 0,
                "blog_posts_this_week": 0,
                "last_plan_context": None
            }
        self.logger.info(f"State loaded: cycle {self.state.get('current_cycle', 0)}")

    def save_state(self):
        """Save current state to file."""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def run(self):
        """Main run loop."""
        self.logger.info("Starting main loop...")

        while True:
            try:
                self.cycle()
                sleep_time = self.config.get('cycle', {}).get('sleep_between_cycles', 3600)
                self.logger.info(f"Cycle complete. Sleeping {sleep_time}s...")
                time.sleep(sleep_time)
            except KeyboardInterrupt:
                self.logger.info("Shutdown requested")
                break
            except Exception as e:
                self.logger.error(f"Cycle error: {e}")
                time.sleep(60)  # Wait before retry

    def cycle(self):
        """Execute one cycle of the state machine."""
        self.state['current_cycle'] = self.state.get('current_cycle', 0) + 1
        cycle_num = self.state['current_cycle']
        self.logger.info(f"=== Cycle {cycle_num} starting ===")

        # State machine
        states = [
            ("SCOUT_TRENDS", self.scout_trends),
            ("SYNC_PERFORMANCE", self.sync_performance),
            ("ANALYZE_DATA", self.analyze_data),
            ("PLAN_CONTENT", self.plan_content),
            ("CREATE_CONTENT", self.create_content),
            ("CREATE_DRAFTS", self.create_drafts),
            ("CHECK_ENGAGEMENT", self.check_engagement),
            ("LEARN", self.learn),
        ]

        for state_name, state_func in states:
            self.logger.info(f"  -> {state_name}")
            try:
                state_func()
            except Exception as e:
                self.logger.error(f"  {state_name} failed: {e}")

        self.save_state()
        self.logger.info(f"=== Cycle {cycle_num} complete ===")

    def scout_trends(self):
        """1. Create TrendScout, call scout_all(), save to trends.json"""
        self.logger.info("Executing scout_trends: Initializing TrendScout.")
        trends_data = None
        try:
            trend_scout = TrendScout(self.config, self.logger)
            trends_data = trend_scout.scout_all()
            self.logger.info(f"Trend scout found {len(trends_data) if trends_data else 0} items.")

            # Save results to trends.json
            os.makedirs(os.path.dirname(self.trends_file), exist_ok=True)
            with open(self.trends_file, 'w') as f:
                json.dump(trends_data, f, indent=2)
            self.logger.info(f"Successfully saved trends to {self.trends_file}")

            # Update state
            self.state['last_trend_scout'] = datetime.now().isoformat()
            self.state['recent_trends'] = trends_data # Keep recent trends in state for planning access

        except Exception as e:
            self.logger.error(f"Error in scout_trends: {e}")

        # Save state after scout_trends per instruction
        self.save_state()

    def sync_performance(self):
        """1.5. Sync published posts from Typefully and get performance summary."""
        self.logger.info("Executing sync_performance: Fetching published post data.")
        try:
            tracker = PerformanceTracker(self.config, self.logger)
            new_posts = tracker.sync_published_posts()
            self.logger.info(f"Synced {len(new_posts)} new published posts from Typefully.")

            summary = tracker.get_performance_summary()
            self.state['performance_summary'] = summary
            self.state['last_performance_sync'] = datetime.now().isoformat()

            recommendations = tracker.get_content_recommendations()
            self.state['content_recommendations'] = recommendations
            self.logger.info(f"Content recommendations: {recommendations.get('status', 'unknown')}")

        except Exception as e:
            self.logger.error(f"Error in sync_performance: {e}")

        self.save_state()

    def analyze_data(self):
        """2. Create Analytics, get TuXo stats, get top posts from memory, get performance insights, return data context"""
        self.logger.info("Executing analyze_data: Initializing Analytics.")
        data_context = {}
        try:
            analytics = Analytics(self.config, self.logger)

            # Get TuXo stats
            tuxo_stats = analytics.get_tuxo_stats()
            data_context['tuxo_stats'] = tuxo_stats
            self.logger.info("Retrieved TuXo stats: " + str(tuxo_stats.get('signal_count', 0)) + " signals found.")

            # Get top posts from memory
            memory_manager = MemoryManager(self.memory_dir, self.logger)
            top_memory_posts = memory_manager.get_top_performing_content(content_type="all", limit=10)
            data_context['top_memory_posts'] = top_memory_posts
            self.logger.info("Retrieved " + str(len(top_memory_posts)) + " top memory posts.")

            # Include performance insights from sync_performance
            perf_summary = self.state.get('performance_summary', {})
            data_context['performance_summary'] = perf_summary
            recommendations = self.state.get('content_recommendations', {})
            data_context['content_recommendations'] = recommendations
            self.logger.info("Performance data attached: " + str(perf_summary.get('total_published', 0)) + " published posts tracked.")

            # Update state
            self.state['last_data_analysis'] = datetime.now().isoformat()
            self.state['data_context'] = data_context # Store context for potential later use/reference

        except Exception as e:
            self.logger.error(f"Error in analyze_data: {e}")
            # Ensure context is still set even on failure for planning stage dependency
            data_context = {"error": str(e)}

        self.state['current_data_context'] = data_context # Persist context for planning next step
        # No explicit save_state here, done at end of cycle

    def plan_content(self):
        """3. Check trends + data + last content, decide what to create, return content plan"""
        self.logger.info("Executing plan_content: Deciding content strategy.")
        plan_result = None
        try:
            # Fetch necessary inputs from state (truncate to keep prompt manageable)
            trends = self.state.get('recent_trends', [])[:10]  # Top 10 trends only
            data_context = self.state.get('current_data_context', {})
            last_content = self.content_plan  # Use the plan from the last successful creation/planning step

            # Build prompt with truncated data
            trends_summary = json.dumps(trends, indent=2)
            if len(trends_summary) > 2000:
                trends_summary = trends_summary[:2000] + "..."

            # Include learned performance recommendations
            recommendations = data_context.get('content_recommendations', {})
            rec_text = ""
            if recommendations.get('status') == 'ok':
                focus = recommendations.get('focus_topics', [])
                avoid = recommendations.get('avoid_topics', [])
                best_hours = recommendations.get('best_posting_hours', [])
                best_fmt = recommendations.get('best_format', 'x')
                rec_text = f"""
            Performance insights (from {recommendations.get('feedback_entries', 0)} feedback entries):
            - Focus topics (best performing): {', '.join(focus) if focus else 'not enough data yet'}
            - Avoid topics (low performing): {', '.join(avoid) if avoid else 'none'}
            - Best posting hours: {', '.join(best_hours) if best_hours else 'not enough data yet'}
            - Best format: {best_fmt}
            """

            prompt = f"""
            You are Luna Hart, marketing AI for TuXo.
            
            Recent trends (top 10):
            {trends_summary}
            
            Data context:
            {json.dumps(data_context, indent=2) if data_context else 'No stats available'}
            
            {rec_text}
            Last content created: {last_content if last_content else 'None'}
            
            Decide the NEXT piece of content to create. Consider:
            - What trending topic would resonate with indie hackers and founders?
            - What hasn't been covered recently?
            - What showcases TuXo's value?
            
            Return ONLY a JSON object with this structure:
            {{"type": "x_post", "topic": "...", "style": "insight", "reason": "brief explanation"}}
            
            Types: x_post, x_thread, linkedin_post, blog_post
            Styles: insight, stat, gap, engagement, trend_take
            """

            # NOTE: Using placeholder for llm_call as it depends on shared directory structure setup
            # If llm_call is available, use it. Otherwise, use a default plan.
            if llm_call:
                raw_response = llm_call(
                    prompt=prompt,
                    model=self.config.get("llm", {}).get("primary", "mimo-v2.6-flash"),
                    max_tokens=5000,
                    temperature=0.7,
                    timeout=30
                )
                # Parse JSON from response (handle markdown code blocks)
                response_text = raw_response.strip()
                
                # Extract JSON from markdown code blocks if present
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    response_text = response_text[start:end].strip()
                elif "```" in response_text:
                    start = response_text.find("```") + 3
                    end = response_text.find("```", start)
                    response_text = response_text[start:end].strip()
                
                # Try to find JSON object in response
                if response_text and not response_text.startswith("{"):
                    json_start = response_text.find("{")
                    json_end = response_text.rfind("}") + 1
                    if json_start >= 0 and json_end > json_start:
                        response_text = response_text[json_start:json_end]
                
                plan_result = json.loads(response_text)
            else:
                # Default plan if LLM fails or path is bad
                self.logger.warning("LLM not fully initialized. Generating default plan.")
                if trends:
                     plan_result = {
                        "type": "x_post",
                        "topic": trends[0].get('title', 'A recent trend'),
                        "style": "trend_take",
                        "context": {"source_trend": trends[0]}
                    }
                else:
                     plan_result = {
                        "type": "x_post",
                        "topic": "System performance update",
                        "style": "stat",
                        "context": {"tuxo_stats_snapshot": data_context.get('tuxo_stats')}
                    }


            # Validate plan structure requirement
            if isinstance(plan_result, dict) and all(k in plan_result for k in ["type", "topic", "style"]):
                # Always inject real TuXo stats into the context
                if "context" not in plan_result:
                    plan_result["context"] = {}
                if "reason" in plan_result and "reason" not in plan_result["context"]:
                    plan_result["context"]["reason"] = plan_result["reason"]
                # Add live stats
                plan_result["context"]["signal_count"] = data_context.get("tuxo_stats", {}).get("signal_count", 0)
                plan_result["context"]["gap_count"] = data_context.get("tuxo_stats", {}).get("gap_count", 0)
                
                self.content_plan = plan_result
                self.logger.info("Content plan decided: Type=" + str(plan_result.get('type')) + ", Topic='" + str(plan_result.get('topic')) + "'")
            else:
                self.logger.error("Content plan generation failed: Did not return expected dict format. Got keys: " + str(list(plan_result.keys()) if plan_result else "None"))
                self.content_plan = None

        except Exception as e:
            self.logger.error(f"Error during content planning: {e}")
            self.content_plan = None

        # Update state
        self.state['last_plan_iteration'] = datetime.now().isoformat()
        # No explicit save_state here, done at end of cycle

    def create_content(self):
        """4. Create ContentEngine, generate content based on plan, validate, return Key details"""
        self.logger.info("Executing create_content: Initializing ContentEngine.")
        if not self.content_plan:
            self.logger.warning("No content plan available. Skipping content creation.")
            return

        plan = self.content_plan
        content_details = None
        try:
            content_engine = ContentEngine(self.config, self.logger)
            content_type = plan.get('type')
            context = plan.get('context', {})

            generated_content = None

            if content_type == "x_post":
                generated_content = content_engine.generate_x_post(plan['topic'], context, plan.get('style', 'insight'))
            elif content_type == "x_thread":
                generated_content = content_engine.generate_x_thread(plan['topic'], context)
            elif content_type == "linkedin_post":
                generated_content = content_engine.generate_linkedin_post(plan['topic'], context, plan.get('style', 'insight'))
            elif content_type == "blog_post":
                generated_content = content_engine.generate_blog_post(plan['topic'], context, [])
                # Blog posts get special handling: outline goes to pending approval
                if generated_content and isinstance(generated_content, dict) and "error" not in generated_content:
                    draft_id = f"blog_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    slug = self._slugify(generated_content.get('title', plan['topic']))
                    draft_data = {
                        "id": draft_id,
                        "topic": plan['topic'],
                        "type": "blog_post",
                        "title": generated_content.get('title', ''),
                        "meta_description": generated_content.get('meta_description', ''),
                        "sections": generated_content.get('sections', []),
                        "slug": slug,
                        "status": "pending",
                        "created_at": datetime.now().isoformat()
                    }
                    self._save_pending_approval(draft_data)
                    self._notify_blog_approval(draft_data)
                    self.logger.info(f"Blog draft created and awaiting approval: {draft_id}")
                    self.state['last_content_creation'] = datetime.now().isoformat()
                    return
                else:
                    self.logger.error(f"Blog post generation failed: {generated_content}")
                    self.state['last_content_creation'] = datetime.now().isoformat()
                    return
            else:
                self.logger.error(f"Unknown content type requested: {content_type}")
                return

            # Validation placeholder
            if generated_content and self.validate_content(generated_content):
                self.logger.info("Content generated and validated successfully for type " + str(content_type) + ".")
                # In a real system, we would return key details or pass to scheduler, here we capture to state
                content_details = {
                    "type": content_type,
                    "topic": plan['topic'],
                    "status": "READY_FOR_SCHEDULE",
                    "data": generated_content # Assuming generated_content contains title, text, etc.
                }
                # Add to pending posts for scheduling
                if "pending_posts" not in self.state:
                    self.state["pending_posts"] = []
                self.state["pending_posts"].append(content_details)
                self.logger.info("Added to pending_posts queue for approval.")
            else:
                self.logger.error("Content validation failed.")
                self.logger.error("Generated content was: " + str(generated_content)[:300] if generated_content else "None")
                content_details = {"status": "VALIDATION_FAILED"}


        except Exception as e:
            self.logger.error(f"Error in create_content: {e}")
            content_details = {"status": f"ENGINE_ERROR: {str(e)}"}

        # Update state
        self.state['last_content_creation'] = datetime.now().isoformat()
        self.state['last_content_output'] = content_details
        # Specific counters update would go here, e.g., self.state['posts_today'] += 1
        
    # Helper method added for placeholder validation
    def validate_content(self, content):
        """Validate content meets requirements."""
        if content is None:
            return False
        
        if isinstance(content, str):
            # Reject error messages from content_engine
            if content.startswith("Could not generate") or content.startswith("ERROR") or content.startswith("LLM_API_ERROR"):
                self.logger.warning("Content is an error message, rejecting.")
                return False
            # Check for em dashes
            if re.search(r'[—–]', content):
                self.logger.warning("Validation failed: Content contains prohibited dashes.")
                return False
            return True
        
        if isinstance(content, dict):
            content_str = json.dumps(content)
            if re.search(r'[—–]', content_str):
                self.logger.warning("Validation failed: Content contains prohibited dashes.")
                return False
            return True
        
        if isinstance(content, list):
            for item in content:
                if isinstance(item, str) and re.search(r'[—–]', item):
                    self.logger.warning("Validation failed: Thread contains prohibited dashes.")
                    return False
            return True
        
        return False

    # --- Helper Methods ---
    def _create_social_manager(self):
        """Helper to create a SocialManager instance."""
        try:
            manager = SocialManager(self.config, self.logger)
            self.logger.info("SocialManager created successfully.")
            return manager
        except Exception as e:
            self.logger.error(f"Failed to create SocialManager: {e}")
            return None

    def _create_analytics(self):
        """Helper to create an Analytics instance."""
        try:
            manager = Analytics(self.config, self.logger)
            self.logger.info("Analytics instance created successfully.")
            return manager
        except Exception as e:
            self.logger.error(f"Failed to create Analytics: {e}")
            return None

    def _create_memory_manager(self):
        """Helper to create a MemoryManager instance."""
        try:
            manager = MemoryManager(self.memory_dir, self.logger)
            self.logger.info(f"MemoryManager created successfully, using directory: {self.memory_dir}")
            return manager
        except Exception as e:
            self.logger.error(f"Failed to create MemoryManager: {e}")
            return None

    # --- Scheduled Methods ---
    def _check_posting_gap(self):
        """Check if enough time has passed since last post (4h minimum)."""
        last_post_time = self.state.get("last_scheduled_post_time")
        if not last_post_time:
            return True  # No previous post, OK to post
        
        try:
            last_time = datetime.fromisoformat(last_post_time)
            hours_since = (datetime.now() - last_time).total_seconds() / 3600
            min_gap_hours = self.config.get("post_gap_hours", 4)
            
            if hours_since >= min_gap_hours:
                self.logger.info("Posting gap OK: " + str(round(hours_since, 1)) + "h since last post (min " + str(min_gap_hours) + "h)")
                return True
            else:
                self.logger.info("Posting gap too short: " + str(round(hours_since, 1)) + "h since last post (min " + str(min_gap_hours) + "h)")
                return False
        except (ValueError, TypeError):
            return True  # Can't parse, assume OK

    def _calculate_proposed_time(self, platforms, is_viral):
        """Calculate the best time to post on T+1 (tomorrow) ONLY.
        Never schedules past tomorrow to keep data fresh."""
        tomorrow = (datetime.now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        social_config = self.config.get("social", {})
        post_times = social_config.get("post_times_cet", {})
        
        # Default posting times from config
        x_times = post_times.get("x", ["10:00", "18:00"])
        linkedin_times = post_times.get("linkedin", ["09:30"])
        
        # Always use tomorrow (T+1), never T+2
        if "x" in platforms and x_times:
            for time_str in x_times:
                hour, minute = map(int, time_str.split(":"))
                proposed = tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)
                # Only return T+1 slots
                if proposed.date() == tomorrow.date():
                    return proposed.isoformat()
        
        elif "linkedin" in platforms and linkedin_times:
            time_str = linkedin_times[0]
            hour, minute = map(int, time_str.split(":"))
            return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()
        
        # Fallback: tomorrow 10:00
        return tomorrow.replace(hour=10, minute=0, second=0, microsecond=0).isoformat()

    def _calculate_proposed_time_old(self, platforms, is_viral):
        """OLD: Calculate the best time to post based on platform and viral status."""
        now = datetime.now()
        social_config = self.config.get("social", {})
        post_times = social_config.get("post_times_cet", {})
        
        # Default posting times from config
        x_times = post_times.get("x", ["10:00", "18:00"])
        linkedin_times = post_times.get("linkedin", ["09:30"])
        
        # Get the last scheduled post time to respect 4h gap
        last_post_str = self.state.get("last_scheduled_post_time")
        min_gap_hours = self.config.get("post_gap_hours", 4)
        
        # Determine next available slot
        if "x" in platforms and x_times:
            # Find next available X post time
            for time_str in x_times:
                hour, minute = map(int, time_str.split(":"))
                proposed = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If this time is in the past today, try tomorrow
                if proposed <= now:
                    proposed = proposed + timedelta(days=1)
                
                # Check if it respects the 4h gap
                if last_post_str:
                    try:
                        last_post = datetime.fromisoformat(last_post_str)
                        if (proposed - last_post).total_seconds() / 3600 >= min_gap_hours:
                            return proposed.isoformat()
                    except (ValueError, TypeError):
                        pass
                else:
                    return proposed.isoformat()
            
            # If no time today respects the gap, use first time tomorrow
            hour, minute = map(int, x_times[0].split(":"))
            return (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()
        
        elif "linkedin" in platforms and linkedin_times:
            time_str = linkedin_times[0]
            hour, minute = map(int, time_str.split(":"))
            proposed = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if proposed <= now:
                proposed = proposed + timedelta(days=1)
            return proposed.isoformat()
        
        # Fallback: next hour
        return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).isoformat()

    def _check_viral_override(self):
        """Check if there's a viral trend worth posting about even with short gap."""
        trends = self.state.get("recent_trends", [])
        if not trends:
            return False
        
        viral_threshold = self.config.get("viral_threshold", 0.8)
        
        for trend in trends:
            score = trend.get("heat_score", 0) or trend.get("score", 0)
            if score >= viral_threshold:
                self.logger.info(f"Viral trend detected: {trend.get('title', 'unknown')} (score: {score})")
                return True
        
        return False

    def _notify_approval(self, draft_data, platforms):
        """Send Telegram notification with URL buttons for Typefully review."""
        try:
            telegram_config = self.config.get("telegram", {})
            if not telegram_config.get("enabled"):
                return
            
            bot_token = telegram_config.get("bot_token")
            chat_id = telegram_config.get("chat_id")
            
            if not bot_token or not chat_id:
                return
            
            # Clean up content (remove list brackets if content_engine returned a list)
            content_raw = draft_data.get("content", "")
            if isinstance(content_raw, list):
                content_raw = " ".join(content_raw)
            content_raw = str(content_raw)
            # Strip leading/trailing brackets and quotes from stringified lists
            content_raw = content_raw.strip("[]'\"")
            content_preview = content_raw[:3500]
            
            topic = str(draft_data.get("topic", "Unknown"))
            platform_str = ", ".join(platforms)
            viral = draft_data.get("viral", False)
            draft_id = str(draft_data.get("id", "N/A"))
            proposed_time = draft_data.get("proposed_time", "Not set")
            
            if proposed_time and proposed_time != "Not set":
                try:
                    dt = datetime.fromisoformat(proposed_time)
                    proposed_time_str = dt.strftime("%A %H:%M CET")
                except (ValueError, TypeError):
                    proposed_time_str = proposed_time
            else:
                proposed_time_str = "Not set"
            
            message = "LUNA HART DRAFT" + "\n\n"
            message += "Topic: " + topic + "\n"
            message += "Platforms: " + platform_str + "\n"
            message += "Post time: " + proposed_time_str + "\n"
            message += "Viral: " + ("Yes" if viral else "No") + "\n\n"
            message += content_preview
            
            import requests
            url = "https://api.telegram.org/bot" + bot_token + "/sendMessage"
            
            # URL buttons (no callback handler needed, they open links directly)
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "Review on Typefully", "url": draft_data.get("typefully_url", "https://typefully.com/drafts")}
                    ]
                ]
            }
            
            payload = {
                "chat_id": chat_id,
                "text": message,
                "reply_markup": json.dumps(keyboard)
            }
            
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                self.logger.info("Telegram notification sent for draft " + draft_id)
            else:
                self.logger.error("Telegram notification failed: " + str(response.status_code))
                
        except Exception as e:
            self.logger.error("Failed to send Telegram notification: " + str(e))

    def _slugify(self, text):
        """Convert text to URL-friendly slug."""
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        slug = re.sub(r'-+', '-', slug)
        slug = slug.strip('-')
        return slug[:60] if slug else 'post'

    def _notify_blog_approval(self, draft_data):
        """Send Telegram notification for blog post approval."""
        try:
            telegram_config = self.config.get("telegram", {})
            if not telegram_config.get("enabled"):
                return

            bot_token = telegram_config.get("bot_token")
            chat_id = telegram_config.get("chat_id")
            if not bot_token or not chat_id:
                return

            title = draft_data.get("title", "Untitled")
            meta = draft_data.get("meta_description", "")[:150]
            sections = draft_data.get("sections", [])
            draft_id = draft_data.get("id", "N/A")

            section_summary = ""
            for s in sections[:5]:
                heading = s.get("heading", "")
                points = s.get("points", [])
                section_summary += f"  - {heading}\n"
                for p in points[:2]:
                    section_summary += f"    - {p}\n"

            message = "LUNA HART BLOG DRAFT" + "\n\n"
            message += "Title: " + title + "\n"
            message += "Meta: " + meta + "\n\n"
            message += "Sections:\n" + section_summary + "\n"
            message += "Approve to publish to dariocositore.com/blog/"

            import requests
            url = "https://api.telegram.org/bot" + bot_token + "/sendMessage"

            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "Approve", "callback_data": "blog_approve_" + draft_id},
                        {"text": "Reject", "callback_data": "blog_reject_" + draft_id}
                    ]
                ]
            }

            payload = {
                "chat_id": chat_id,
                "text": message,
                "reply_markup": json.dumps(keyboard)
            }

            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                self.logger.info(f"Blog approval notification sent: {draft_id}")
            else:
                self.logger.error(f"Blog Telegram notification failed: {response.status_code}")

        except Exception as e:
            self.logger.error(f"Failed to send blog approval notification: {e}")

    def _save_pending_approval(self, draft_data):
        """Save draft to pending approval file."""
        pending_file = os.path.join(self.memory_dir, "pending_approval.json")
        
        try:
            if os.path.exists(pending_file):
                with open(pending_file, 'r') as f:
                    pending = json.load(f)
            else:
                pending = {"drafts": []}
            
            pending["drafts"].append(draft_data)
            
            with open(pending_file, 'w') as f:
                json.dump(pending, f, indent=2)
            
            self.logger.info(f"Draft saved to pending approval: {draft_data.get('id')}")
            
        except Exception as e:
            self.logger.error(f"Failed to save pending approval: {e}")

    def _check_approved_drafts(self):
        """Check for approved drafts (social + blog) and deploy/schedule them."""
        pending_file = os.path.join(self.memory_dir, "pending_approval.json")
        
        if not os.path.exists(pending_file):
            return
        
        try:
            with open(pending_file, 'r') as f:
                pending = json.load(f)
            
            approved = [d for d in pending.get("drafts", []) if d.get("status") == "approved"]
            rejected = [d for d in pending.get("drafts", []) if d.get("status") == "rejected"]
            waiting = [d for d in pending.get("drafts", []) if d.get("status") == "pending"]
            
            for draft in approved:
                draft_type = draft.get("type", "social")
                
                if draft_type == "blog_post":
                    # Blog post: create HTML and deploy via SFTP
                    self._deploy_approved_blog(draft)
                else:
                    # Social post: schedule via Typefully
                    self._schedule_approved_social(draft)
            
            # Save back with only waiting drafts (remove approved/rejected)
            pending["drafts"] = waiting
            
            with open(pending_file, 'w') as f:
                json.dump(pending, f, indent=2)
                
            self.logger.info(f"Approved drafts: {len(approved)}, Rejected: {len(rejected)}, Waiting: {len(waiting)}")
            
        except Exception as e:
            self.logger.error(f"Failed to check approved drafts: {e}")

    def _deploy_approved_blog(self, draft):
        """Deploy an approved blog post: create HTML + SFTP deploy."""
        try:
            blog_manager = BlogManager(self.config, self.logger)
            title = draft.get("title", "Untitled")
            meta = draft.get("meta_description", "")
            slug = draft.get("slug", self._slugify(title))
            sections = draft.get("sections", [])

            # Convert sections JSON to HTML
            content_html = self._sections_to_html(sections)

            # Create HTML file locally
            filepath = blog_manager.create_blog_post(title, meta, content_html, slug)
            if not filepath:
                self.logger.error(f"Failed to create blog HTML for: {title}")
                return

            # Deploy via SFTP
            deploy_config = self.config.get("blog", {})
            if deploy_config.get("deploy_after_create", True):
                success = blog_manager.deploy_post(slug)
                if success:
                    self.logger.info(f"Blog post deployed: {slug}")
                    # Update blog index
                    blog_manager.update_index(slug)
                else:
                    self.logger.error(f"Blog SFTP deployment failed for: {slug}")
            else:
                self.logger.info(f"Blog post created locally (deploy disabled): {slug}")

            # Log to memory
            draft["status"] = "deployed"
            draft["deployed_at"] = datetime.now().isoformat()
            draft["local_path"] = filepath

        except Exception as e:
            self.logger.error(f"Failed to deploy approved blog: {e}")

    def _sections_to_html(self, sections):
        """Convert blog outline sections to HTML content."""
        if not sections:
            return "<p>Content pending.</p>"

        html = ""
        for section in sections:
            heading = section.get("heading", "")
            points = section.get("points", [])

            if heading:
                html += f"<h2>{heading}</h2>\n"

            if points:
                html += "<ul>\n"
                for point in points:
                    html += f"  <li>{point}</li>\n"
                html += "</ul>\n"

        return html if html else "<p>Content pending.</p>"

    def _schedule_approved_social(self, draft):
        """Schedule an approved social post via Typefully."""
        try:
            social_manager = self._create_social_manager()
            if not social_manager:
                self.logger.error("Cannot schedule: SocialManager failed.")
                return

            platforms = draft.get("platforms", ["x"])
            content = draft.get("content", "")
            scheduled_time = draft.get("scheduled_time")

            result = social_manager.create_draft(
                content=content,
                platforms=platforms,
                schedule_time=scheduled_time
            )

            if result:
                self.logger.info(f"Approved social draft scheduled: {draft.get('id')}")
                draft["status"] = "scheduled"
                draft["scheduled_at"] = datetime.now().isoformat()
                self.state["last_scheduled_post_time"] = datetime.now().isoformat()

        except Exception as e:
            self.logger.error(f"Failed to schedule approved social draft: {e}")

    def create_drafts(self):
        """Create Typefully drafts and request approval via Telegram.
        
        Scheduling rule: Posts are ONLY scheduled for T+1 (tomorrow).
        Data freshness matters - we never go past tomorrow so every post
        reflects the most recent data we have.
        
        Flow:
        1. Check what's already scheduled on Typefully for tomorrow
        2. Calculate remaining available slots
        3. If no slots available, skip (tomorrow is full)
        4. If slots available, create drafts for those slots only
        """
        self.logger.info("Executing schedule_posts (T+1 only, draft mode with approval).")
        
        # First, check for any approved drafts from previous cycles
        self._check_approved_drafts()
        
        social_manager = self._create_social_manager()
        if not social_manager:
            self.logger.warning("Cannot schedule posts: SocialManager failed to initialize.")
            return
        
        pending_posts = self.state.get("pending_posts", [])
        
        if not pending_posts:
            self.logger.info("No pending posts found in state.")
            return
        
        # Check posting gap (4h minimum unless viral override)
        can_post = self._check_posting_gap()
        viral_override = self._check_viral_override()
        
        if not can_post and not viral_override:
            self.logger.info("Posting gap too short and no viral trend. Saving for next cycle.")
            return
        
        # --- T+1 ONLY: Check available slots for tomorrow ---
        try:
            available_slots = social_manager.get_available_slots_for_tomorrow(self.config)
        except Exception as e:
            self.logger.warning(f"Could not check tomorrow slots: {e}. Falling back to old behavior.")
            available_slots = None
        
        if available_slots is not None and len(available_slots) == 0:
            tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            self.logger.info(f"Tomorrow ({tomorrow_str}) is fully scheduled. Skipping draft creation.")
            return
        
        try:
            for post in pending_posts:
                # T+1 only: check if we still have available slots
                if available_slots is not None and len(available_slots) == 0:
                    self.logger.info("No more available slots for tomorrow. Stopping.")
                    break
                # Generate unique draft ID
                draft_id = f"draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{post.get('type', 'post')}"
                
                # Create draft in Typefully (as DRAFT, not scheduled)
                content = post.get("data", post.get("content", ""))
                platforms = ["x"] if post.get("type") in ["x_post", "x_thread"] else ["linkedin"]
                
                # T+1 only: use the first available slot from checked list
                if available_slots:
                    proposed_time = available_slots.pop(0)
                else:
                    proposed_time = self._calculate_proposed_time(platforms, viral_override)
                
                # Create draft in Typefully immediately (as unscheduled draft)
                typefully_url = None
                try:
                    typefully_response = social_manager.create_draft(
                        content=str(content)[:9999] if isinstance(content, str) else content,
                        platforms=platforms,
                        title="Luna: " + str(post.get("topic", "Draft"))[:50]
                    )
                    if typefully_response and isinstance(typefully_response, dict):
                        typefully_id = typefully_response.get("id")
                        if typefully_id:
                            typefully_url = "https://typefully.com/drafts/" + str(typefully_id)
                except Exception as e:
                    self.logger.warning("Could not create Typefully draft: " + str(e))
                
                # Save to pending approval
                draft_data = {
                    "id": draft_id,
                    "topic": post.get("topic", "Unknown"),
                    "type": post.get("type", "x_post"),
                    "content": content if isinstance(content, str) else json.dumps(content),
                    "platforms": platforms,
                    "viral": viral_override,
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                    "proposed_time": proposed_time,
                    "scheduled_time": None,
                    "typefully_url": typefully_url
                }
                
                self._save_pending_approval(draft_data)
                self._notify_approval(draft_data, platforms)
                
                self.logger.info(f"Draft created and awaiting approval: {draft_id}")
            
            # Clear pending posts from state
            del self.state["pending_posts"]
            self.logger.info("All pending posts converted to drafts awaiting approval.")
            
        except Exception as e:
            self.logger.error(f"Error during draft creation: {e}")
        
        self.save_state()

    def check_engagement(self):
        """Create Analytics, get engagement summary, update memory."""
        self.logger.info("Executing check_engagement.")
        analytics = self._create_analytics()
        memory_manager = self._create_memory_manager()

        if not analytics or not memory_manager:
            self.logger.warning("Cannot check engagement: Manager(s) failed to initialize.")
            return

        try:
            # Get top posts from memory manager
            top_posts = memory_manager.get_top_performing_content(content_type="all", limit=5)
            self.logger.info(f"Retrieved {len(top_posts)} top performing posts from memory.")

            # Use Analytics to get engagement summary
            engagement_summary = analytics.get_engagement_summary()
            engagement_summary["status"] = "SUCCESS"
            engagement_summary["top_posts"] = top_posts
            self.logger.info("Engagement summary generated.")

            # Update state with engagement data
            self.state["last_engagement_report"] = datetime.now().isoformat()
            self.state["engagement_summary"] = engagement_summary

        except Exception as e:
            self.logger.error(f"Error during check_engagement execution: {e}")
            self.state["engagement_summary"] = {"status": "ERROR", "error_detail": str(e)}

        self.save_state()

    def learn(self):
        """Create MemoryManager, archive old posts, update audience insights with performance data, save trends."""
        self.logger.info("Executing learn.")
        memory_manager = self._create_memory_manager()

        if not memory_manager:
            self.logger.warning("Cannot start learning: MemoryManager failed to initialize.")
            return

        learning_results = {"status": "FAILED", "details": []}
        try:
            # Archive posts older than 30 days
            archive_date = datetime.now() - timedelta(days=30)
            archived_count = memory_manager.archive_old_posts(days=30)
            learning_results["details"].append(f"Archived {archived_count} posts older than {archive_date.date()}.")
            self.logger.info(f"Archiving complete. Archived {archived_count} posts.")

            # Get audience insights from memory
            audience_insights = memory_manager.get_audience_insights()
            learning_results["audience_insights"] = audience_insights
            self.logger.info("Audience insights retrieved.")

            # Merge performance tracker insights into audience.json
            try:
                tracker = PerformanceTracker(self.config, self.logger)
                perf_summary = tracker.get_performance_summary()
                learning_results["performance_summary"] = perf_summary

                recommendations = tracker.get_content_recommendations()
                learning_results["content_recommendations"] = recommendations
                self.logger.info(f"Performance learning: {perf_summary.get('total_published', 0)} posts, "
                               f"{perf_summary.get('total_with_feedback', 0)} with feedback.")

                # Save audience (includes learned_patterns from performance_tracker)
                tracker._save_json(tracker.audience_file, tracker.audience)
            except Exception as e:
                self.logger.warning(f"Performance tracking sync failed in learn: {e}")
                learning_results["details"].append(f"Performance sync warning: {str(e)}")

            # Save all memory files
            memory_manager.save_audience()
            memory_manager.save_content_log()
            memory_manager.save_trends()
            memory_manager.save_blog_log()
            learning_results["details"].append("Memory files saved successfully.")
            self.logger.info("All memory files saved.")

            learning_results["status"] = "SUCCESS"

        except Exception as e:
            self.logger.error(f"Error during learn phase: {e}")
            learning_results["details"].append(f"Critical error during learning: {str(e)}")

        # Update state
        self.state["last_learning_run"] = datetime.now().isoformat()
        self.state["latest_learning_report"] = learning_results
        self.logger.info("Learning phase complete.")
        self.save_state()
