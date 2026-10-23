#!/usr/bin/env python3
"""
Performance Tracker for Agent_5
Pulls published post data from Typefully, accepts manual feedback,
and updates audience.json with learned insights.
"""
import json
import os
import logging
import requests
from datetime import datetime, timedelta, timezone
from collections import defaultdict


class PerformanceTracker:
    """
    Tracks published post performance by:
    1. Querying Typefully API for recently published drafts
    2. Accepting manual feedback (via Telegram or direct)
    3. Updating audience.json with learned patterns
    """

    def __init__(self, config: dict, logger: logging.Logger):
        self.logger = logger
        self.memory_dir = os.path.join(
            os.path.dirname(__file__), '..', 'memory'
        )

        social_config = config.get("social", {})
        self.api_key = social_config.get("typefully_api_key")
        self.social_set_id = social_config.get("social_set_id")
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self.api_base = "https://api.typefully.com/v2"

        # File paths
        self.audience_file = os.path.join(self.memory_dir, 'audience.json')
        self.performance_file = os.path.join(self.memory_dir, 'performance.json')
        self.content_log_file = os.path.join(self.memory_dir, 'content_log.json')

        # Load existing data
        self.audience = self._load_json(self.audience_file, default={
            "insights": {},
            "preferences": {},
            "top_performing_content": [],
            "audience_segments": {},
            "learned_patterns": {
                "best_topics": {},
                "best_times": {},
                "best_formats": {},
                "total_feedback_entries": 0
            }
        })
        self.performance = self._load_json(self.performance_file, default={
            "published_posts": [],
            "manual_feedback": [],
            "last_sync": None
        })

    def _load_json(self, path: str, default=None):
        """Load JSON file with fallback."""
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default or {}

    def _save_json(self, path: str, data):
        """Save JSON file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def _typefully_request(self, endpoint: str, params: dict = None):
        """Make Typefully API request."""
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        try:
            response = requests.get(
                url, headers=self.headers, params=params, timeout=15
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Typefully API error ({endpoint}): {e}")
            return None

    def sync_published_posts(self):
        """
        Fetch all published drafts from Typefully.
        Cross-references with performance.json to find new ones.
        Returns list of newly discovered published posts.
        """
        self.logger.info("Syncing published posts from Typefully...")

        # Get published drafts (max 50 per Typefully API)
        response = self._typefully_request(
            f"social-sets/{self.social_set_id}/drafts",
            params={"limit": 50, "status": "published"}
        )

        if not response or "results" not in response:
            self.logger.warning("No response from Typefully or empty results.")
            return []

        published_drafts = response["results"]
        self.logger.info(f"Found {len(published_drafts)} published drafts on Typefully.")

        # Build set of known IDs
        known_ids = {str(p.get("typefully_id")) for p in self.performance.get("published_posts", [])}

        new_posts = []
        for draft in published_drafts:
            draft_id = str(draft.get("id"))
            if draft_id in known_ids:
                continue

            # Determine platform and URL
            platform = "x"
            published_url = draft.get("x_published_url")
            if draft.get("linkedin_post_published_at") and draft.get("linkedin_published_url"):
                platform = "linkedin"
                published_url = draft.get("linkedin_published_url")
            elif draft.get("x_post_published_at") and draft.get("x_published_url"):
                platform = "x"
                published_url = draft.get("x_published_url")

            post_entry = {
                "typefully_id": draft_id,
                "title": draft.get("draft_title", ""),
                "preview": draft.get("preview", "")[:200],
                "platform": platform,
                "published_url": published_url,
                "published_at": draft.get("published_at"),
                "created_at": draft.get("created_at"),
                "tags": draft.get("tags", []),
                "metrics": {
                    "impressions": None,
                    "likes": None,
                    "retweets": None,
                    "replies": None,
                    "profile_clicks": None
                },
                "feedback_score": None,
                "source_topic": self._extract_topic_from_title(draft.get("draft_title", ""))
            }

            new_posts.append(post_entry)
            self.performance["published_posts"].append(post_entry)

        self.performance["last_sync"] = datetime.now(timezone.utc).isoformat()
        self._save_json(self.performance_file, self.performance)

        self.logger.info(f"Synced {len(new_posts)} new published posts.")
        return new_posts

    def _extract_topic_from_title(self, title: str) -> str:
        """
        Extract topic category from Luna's draft titles.
        Titles follow patterns like: 'W1 Tue 10:00 X Hook', 'Gap: Legal help'
        """
        if not title:
            return "unknown"

        # Check for explicit topic markers
        title_lower = title.lower()
        topic_keywords = {
            "gap": ["gap", "pain", "problem", "unsolved"],
            "data": ["signal", "data", "stat", "number", "metric"],
            "founding": ["founder", "build", "startup", "indie"],
            "automation": ["automat", "agent", "system", "pipeline"],
            "trend": ["trend", "viral", "hot", "rising"],
            "comparison": ["vs", "compare", "better", "worse"],
            "story": ["story", "learned", "journey", "origin"],
            "engagement": ["question", "poll", "what", "how", "why"]
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in title_lower for kw in keywords):
                return topic

        return "general"

    def add_manual_feedback(self, post_identifier: str, feedback: dict):
        """
        Add manual feedback for a published post.
        Called when Dario reports metrics via Telegram or directly.

        Args:
            post_identifier: Typefully ID, title substring, or URL
            feedback: Dict with optional keys:
                - impressions: int
                - likes: int
                - retweets: int
                - replies: int
                - profile_clicks: int
                - score: float (0.0-1.0, subjective quality)
                - notes: str (free text insight)
                - topic_strength: str ("strong", "medium", "weak")
        """
        self.logger.info(f"Adding manual feedback for: {post_identifier}")

        # Find the matching post
        matched_post = None
        for post in self.performance.get("published_posts", []):
            if (str(post.get("typefully_id")) == str(post_identifier) or
                post_identifier.lower() in post.get("title", "").lower() or
                post_identifier in post.get("published_url", "")):
                matched_post = post
                break

        if not matched_post:
            # Create standalone feedback entry
            feedback_entry = {
                "identifier": post_identifier,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "feedback": feedback,
                "matched": False
            }
            self.performance.setdefault("manual_feedback", []).append(feedback_entry)
            self._save_json(self.performance_file, self.performance)
            self.logger.warning(f"No matching post found for '{post_identifier}'. Saved as standalone feedback.")
            return

        # Update the post's metrics
        metrics = matched_post.get("metrics", {})
        for key in ["impressions", "likes", "retweets", "replies", "profile_clicks"]:
            if key in feedback and feedback[key] is not None:
                metrics[key] = feedback[key]
        matched_post["metrics"] = metrics

        if "score" in feedback:
            matched_post["feedback_score"] = feedback["score"]

        # Save feedback log
        feedback_entry = {
            "typefully_id": matched_post.get("typefully_id"),
            "title": matched_post.get("title"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "feedback": feedback,
            "matched": True
        }
        self.performance.setdefault("manual_feedback", []).append(feedback_entry)

        # Update audience insights based on this feedback
        self._update_learned_patterns(matched_post, feedback)

        self._save_json(self.performance_file, self.performance)
        self._save_json(self.audience_file, self.audience)

        self.logger.info(f"Feedback applied to post '{matched_post.get('title')}'. Insights updated.")

    def _update_learned_patterns(self, post: dict, feedback: dict):
        """
        Update audience.json learned patterns based on post performance.
        Tracks: best topics, best posting times, best formats, score trends.
        """
        patterns = self.audience.setdefault("learned_patterns", {
            "best_topics": {},
            "best_times": {},
            "best_formats": {},
            "total_feedback_entries": 0
        })

        patterns["total_feedback_entries"] = patterns.get("total_feedback_entries", 0) + 1

        # Extract topic
        topic = post.get("source_topic", "unknown")

        # Calculate composite score from available data
        score = feedback.get("score")
        if score is None:
            # Auto-calculate from metrics if available
            metrics = post.get("metrics", {})
            impressions = metrics.get("impressions") or 0
            likes = metrics.get("likes") or 0
            retweets = metrics.get("retweets") or 0
            replies = metrics.get("replies") or 0
            if impressions > 0:
                engagement = likes + retweets * 2 + replies * 3
                score = min(1.0, engagement / impressions * 10)
            elif likes > 0 or retweets > 0 or replies > 0:
                score = min(1.0, (likes + retweets * 2 + replies * 3) / 100)

        if score is not None:
            # Update topic scores
            topic_data = patterns["best_topics"].setdefault(topic, {
                "scores": [], "count": 0, "avg_score": 0
            })
            topic_data["scores"].append(score)
            topic_data["count"] += 1
            topic_data["avg_score"] = sum(topic_data["scores"]) / len(topic_data["scores"])

            # Update time scores (posting hour)
            published_at = post.get("published_at")
            if published_at:
                try:
                    dt = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                    hour = dt.hour
                    time_key = f"{hour:02d}:00"
                    time_data = patterns["best_times"].setdefault(time_key, {
                        "scores": [], "count": 0, "avg_score": 0
                    })
                    time_data["scores"].append(score)
                    time_data["count"] += 1
                    time_data["avg_score"] = sum(time_data["scores"]) / len(time_data["scores"])
                except (ValueError, TypeError):
                    pass

            # Update format scores
            platform = post.get("platform", "unknown")
            format_data = patterns["best_formats"].setdefault(platform, {
                "scores": [], "count": 0, "avg_score": 0
            })
            format_data["scores"].append(score)
            format_data["count"] += 1
            format_data["avg_score"] = sum(format_data["scores"]) / len(format_data["scores"])

        # Store qualitative notes in preferences
        if "notes" in feedback:
            notes = self.audience.setdefault("preferences", {}).setdefault("performance_notes", [])
            notes.append({
                "post_title": post.get("title"),
                "note": feedback["notes"],
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            # Keep only last 50 notes
            if len(notes) > 50:
                self.audience["preferences"]["performance_notes"] = notes[-50:]

        # Topic strength insight
        if "topic_strength" in feedback:
            strength = feedback["topic_strength"]
            topic_insights = self.audience.setdefault("insights", {}).setdefault("topic_strength", {})
            topic_insights[topic] = strength

    def get_performance_summary(self) -> dict:
        """
        Generate a summary of all tracked performance data.
        Returns insights for the LEARN state to consume.
        """
        posts = self.performance.get("published_posts", [])
        feedback = self.performance.get("manual_feedback", [])

        if not posts and not feedback:
            return {"status": "no_data", "message": "No published posts or feedback yet."}

        # Calculate overall stats
        posts_with_metrics = [p for p in posts if p.get("metrics", {}).get("impressions") is not None]
        posts_with_scores = [p for p in posts if p.get("feedback_score") is not None]

        # Best performing by score
        top_by_score = sorted(posts_with_scores, key=lambda x: x.get("feedback_score", 0), reverse=True)[:5]

        # Best performing by impressions
        top_by_impressions = sorted(
            posts_with_metrics,
            key=lambda x: x.get("metrics", {}).get("impressions", 0),
            reverse=True
        )[:5]

        # Topic breakdown
        topic_scores = defaultdict(list)
        for p in posts_with_scores:
            topic = p.get("source_topic", "unknown")
            topic_scores[topic].append(p.get("feedback_score", 0))

        topic_averages = {
            topic: sum(scores) / len(scores)
            for topic, scores in topic_scores.items()
        }

        summary = {
            "total_published": len(posts),
            "total_with_metrics": len(posts_with_metrics),
            "total_with_feedback": len(posts_with_scores),
            "total_manual_feedback": len(feedback),
            "top_by_score": [
                {"title": p.get("title"), "score": p.get("feedback_score"), "topic": p.get("source_topic")}
                for p in top_by_score
            ],
            "top_by_impressions": [
                {"title": p.get("title"), "impressions": p.get("metrics", {}).get("impressions"), "topic": p.get("source_topic")}
                for p in top_by_impressions
            ],
            "topic_performance": dict(topic_averages),
            "learned_patterns": self.audience.get("learned_patterns", {}),
            "last_sync": self.performance.get("last_sync"),
            "status": "ok"
        }

        return summary

    def get_content_recommendations(self) -> dict:
        """
        Generate content recommendations based on learned patterns.
        Called during PLAN_CONTENT to influence what Luna creates.
        """
        patterns = self.audience.get("learned_patterns", {})
        feedback_count = patterns.get("total_feedback_entries", 0)

        if feedback_count < 3:
            return {
                "status": "insufficient_data",
                "message": f"Only {feedback_count} feedback entries. Need at least 3 for reliable recommendations."
            }

        # Best topics (sorted by avg score)
        best_topics = patterns.get("best_topics", {})
        sorted_topics = sorted(
            best_topics.items(),
            key=lambda x: x[1].get("avg_score", 0),
            reverse=True
        )

        # Best times
        best_times = patterns.get("best_times", {})
        sorted_times = sorted(
            best_times.items(),
            key=lambda x: x[1].get("avg_score", 0),
            reverse=True
        )

        # Best formats
        best_formats = patterns.get("best_formats", {})
        sorted_formats = sorted(
            best_formats.items(),
            key=lambda x: x[1].get("avg_score", 0),
            reverse=True
        )

        recommendations = {
            "status": "ok",
            "feedback_entries": feedback_count,
            "focus_topics": [t[0] for t in sorted_topics[:3]],
            "avoid_topics": [t[0] for t in sorted_topics[-2:] if t[1].get("avg_score", 0) < 0.3],
            "best_posting_hours": [t[0] for t in sorted_times[:2]],
            "best_format": sorted_formats[0][0] if sorted_formats else "x",
            "detailed": {
                "topics": {t[0]: {"avg_score": round(t[1].get("avg_score", 0), 2), "count": t[1].get("count", 0)}
                           for t in sorted_topics},
                "times": {t[0]: {"avg_score": round(t[1].get("avg_score", 0), 2), "count": t[1].get("count", 0)}
                          for t in sorted_times},
                "formats": {t[0]: {"avg_score": round(t[1].get("avg_score", 0), 2), "count": t[1].get("count", 0)}
                            for t in sorted_formats}
            }
        }

        return recommendations
