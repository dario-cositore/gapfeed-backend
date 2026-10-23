#!/usr/bin/env python3
"""
Memory Manager Module for Luna Hart
Manages long-term learning and persistent data storage.
"""
import os
import json
from datetime import datetime, timedelta
from collections import defaultdict


class MemoryManager:
    """Manages Luna Hart's long-term memory."""

    def __init__(self, memory_dir, logger):
        """
        Initialize MemoryManager.

        Args:
            memory_dir: Path to memory directory
            logger: Logger instance
        """
        self.memory_dir = memory_dir
        self.logger = logger

        # Create memory directory if it doesn't exist
        os.makedirs(memory_dir, exist_ok=True)

        # Define file paths
        self.audience_file = os.path.join(memory_dir, 'audience.json')
        self.content_log_file = os.path.join(memory_dir, 'content_log.json')
        self.trends_file = os.path.join(memory_dir, 'trends.json')
        self.blog_log_file = os.path.join(memory_dir, 'blog_log.json')

        # Load all memory files
        self.audience = self.load_audience()
        self.content_log = self.load_content_log()
        self.trends = self.load_trends()
        self.blog_log = self.load_blog_log()

    def load_audience(self):
        """Load audience.json."""
        try:
            with open(self.audience_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"insights": {}, "preferences": {}, "top_performing_content": [], "audience_segments": {}}

    def save_audience(self):
        """Save audience.json."""
        with open(self.audience_file, 'w') as f:
            json.dump(self.audience, f, indent=2)

    def load_content_log(self):
        """Load content_log.json."""
        try:
            with open(self.content_log_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"posts": [], "total_posts": 0, "avg_engagement_rate": 0, "best_performing_type": None}

    def save_content_log(self):
        """Save content_log.json."""
        with open(self.content_log_file, 'w') as f:
            json.dump(self.content_log, f, indent=2)

    def load_trends(self):
        """Load trends.json."""
        try:
            with open(self.trends_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"tracked_trends": [], "predictions": [], "accuracy": 0}

    def save_trends(self):
        """Save trends.json."""
        with open(self.trends_file, 'w') as f:
            json.dump(self.trends, f, indent=2)

    def load_blog_log(self):
        """Load blog_log.json."""
        try:
            with open(self.blog_log_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"posts": [], "total_posts": 0, "avg_traffic": 0, "top_performing_post": None}

    def save_blog_log(self):
        """Save blog_log.json."""
        with open(self.blog_log_file, 'w') as f:
            json.dump(self.blog_log, f, indent=2)

    def add_post_to_log(self, post_data):
        """
        Add a post to the content log.

        Args:
            post_data: Dict with post information
        """
        post_data['added_at'] = datetime.now().isoformat()
        self.content_log['posts'].append(post_data)
        self.content_log['total_posts'] += 1
        self.save_content_log()
        self.logger.info(f"Added post to log: {post_data.get('title', 'untitled')}")

    def update_post_engagement(self, post_id, engagement):
        """
        Update engagement metrics for a specific post.

        Args:
            post_id: Post identifier
            engagement: Dict with likes, replies, shares, etc.
        """
        for post in self.content_log['posts']:
            if post.get('id') == post_id:
                post['engagement'] = engagement
                self.save_content_log()
                return
        self.logger.warning(f"Post {post_id} not found in content log")

    def add_blog_post(self, post_data):
        """
        Add a blog post to the blog log.

        Args:
            post_data: Dict with blog post information
        """
        post_data['added_at'] = datetime.now().isoformat()
        self.blog_log['posts'].append(post_data)
        self.blog_log['total_posts'] += 1
        self.save_blog_log()
        self.logger.info(f"Added blog post to log: {post_data.get('title', 'untitled')}")

    def get_top_performing_content(self, content_type="all", limit=10):
        """
        Get top performing posts by engagement.

        Args:
            content_type: Filter by type (x, linkedin, blog, or all)
            limit: Number of top posts to return

        Returns:
            List of top posts
        """
        posts = self.content_log.get('posts', [])

        if content_type != "all":
            posts = [p for p in posts if p.get('platform') == content_type or p.get('type') == content_type]

        # Sort by engagement score (simplified)
        def engagement_score(post):
            e = post.get('engagement', {})
            return (e.get('likes', 0) * 2 + e.get('replies', 0) * 3 + e.get('shares', 0) * 1.5)

        posts.sort(key=engagement_score, reverse=True)
        return posts[:limit]

    def get_audience_insights(self):
        """
        Analyze content log to find patterns.

        Returns:
            Dict with insights about best times, content types, topics
        """
        insights = {
            'best_posting_times': {},
            'best_content_types': {},
            'best_topics': defaultdict(int),
            'avg_engagement_by_platform': defaultdict(list)
        }

        for post in self.content_log.get('posts', []):
            # Extract posting time
            if 'scheduled_date' in post:
                dt = datetime.fromisoformat(post['scheduled_date'].replace('Z', '+00:00'))
                hour = dt.hour
                insights['best_posting_times'][hour] = insights['best_posting_times'].get(hour, 0) + 1

            # Content type
            platform = post.get('platform', 'unknown')
            insights['best_content_types'][platform] = insights['best_content_types'].get(platform, 0) + 1

            # Engagement by platform
            e = post.get('engagement', {})
            engagement = e.get('likes', 0) + e.get('replies', 0) + e.get('shares', 0)
            insights['avg_engagement_by_platform'][platform].append(engagement)

        return insights

    def archive_old_posts(self, days=30):
        """
        Move posts older than specified days to archive.

        Args:
            days: Number of days before archiving

        Returns:
            Number of posts archived
        """
        cutoff = datetime.now() - timedelta(days=days)
        archive = []
        keep = []

        for post in self.content_log.get('posts', []):
            added = post.get('added_at')
            if added:
                try:
                    if datetime.fromisoformat(added) < cutoff:
                        archive.append(post)
                    else:
                        keep.append(post)
                except ValueError:
                    keep.append(post)
            else:
                keep.append(post)

        if archive:
            self.content_log['posts'] = keep
            self.content_log['archived'] = self.content_log.get('archived', []) + archive
            self.save_content_log()
            self.logger.info(f"Archived {len(archive)} old posts")
            return len(archive)

        return 0

    def get_memory_summary(self):
        """
        Get summary of all memory files.

        Returns:
            Dict with summary statistics
        """
        return {
            'total_posts': self.content_log.get('total_posts', 0),
            'total_blog_posts': self.blog_log.get('total_posts', 0),
            'tracked_trends': len(self.trends.get('tracked_trends', [])),
            'audience_insights': len(self.audience.get('insights', {})),
        }
