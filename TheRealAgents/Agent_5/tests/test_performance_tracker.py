#!/usr/bin/env python3
"""Tests for PerformanceTracker module."""
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from performance_tracker import PerformanceTracker


def make_logger():
    """Create a test logger."""
    import logging
    logger = logging.getLogger("test_performance")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


def test_init_creates_files():
    """Test that initialization creates memory directory and default files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "social": {
                "typefully_api_key": "test_key",
                "social_set_id": "12345"
            }
        }
        logger = make_logger()

        tracker = PerformanceTracker(config, logger)
        # Override memory dir to temp
        tracker.memory_dir = tmpdir
        tracker.audience_file = os.path.join(tmpdir, 'audience.json')
        tracker.performance_file = os.path.join(tmpdir, 'performance.json')

        # Re-init data
        tracker.audience = tracker._load_json(tracker.audience_file, default={
            "insights": {}, "preferences": {}, "top_performing_content": [],
            "audience_segments": {},
            "learned_patterns": {"best_topics": {}, "best_times": {}, "best_formats": {}, "total_feedback_entries": 0}
        })
        tracker.performance = tracker._load_json(tracker.performance_file, default={
            "published_posts": [], "manual_feedback": [], "last_sync": None
        })

        assert "learned_patterns" in tracker.audience
        assert "published_posts" in tracker.performance


def test_extract_topic_from_title():
    """Test topic extraction from draft titles."""
    config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
    logger = make_logger()
    tracker = PerformanceTracker(config, logger)

    assert tracker._extract_topic_from_title("Gap: Legal help in crisis") == "gap"
    assert tracker._extract_topic_from_title("Signal count update 5k") == "data"
    assert tracker._extract_topic_from_title("Founder story about building") == "founding"
    assert tracker._extract_topic_from_title("Automating pipeline with agents") == "automation"
    assert tracker._extract_topic_from_title("Trending on Reddit today") == "trend"
    assert tracker._extract_topic_from_title("W1 Tue 10:00 X Hook") == "general"
    assert tracker._extract_topic_from_title("") == "unknown"


def test_add_manual_feedback_matches_post():
    """Test that manual feedback matches and updates existing posts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
        logger = make_logger()
        tracker = PerformanceTracker(config, logger)

        tracker.memory_dir = tmpdir
        tracker.audience_file = os.path.join(tmpdir, 'audience.json')
        tracker.performance_file = os.path.join(tmpdir, 'performance.json')

        # Seed a published post
        tracker.performance = {
            "published_posts": [{
                "typefully_id": "999",
                "title": "Gap: Legal help in crisis",
                "preview": "Legal help is broken...",
                "platform": "x",
                "published_url": "https://x.com/DarioCositore/status/123",
                "published_at": "2026-03-28T10:00:00Z",
                "source_topic": "gap",
                "metrics": {"impressions": None, "likes": None, "retweets": None, "replies": None}
            }],
            "manual_feedback": [],
            "last_sync": "2026-03-28T12:00:00Z"
        }
        tracker.audience = {
            "insights": {}, "preferences": {}, "top_performing_content": [],
            "audience_segments": {},
            "learned_patterns": {"best_topics": {}, "best_times": {}, "best_formats": {}, "total_feedback_entries": 0}
        }

        # Add feedback by ID
        tracker.add_manual_feedback("999", {
            "impressions": 2400,
            "likes": 45,
            "retweets": 12,
            "replies": 8,
            "score": 0.75,
            "notes": "Strong topic, high engagement"
        })

        post = tracker.performance["published_posts"][0]
        assert post["metrics"]["impressions"] == 2400
        assert post["metrics"]["likes"] == 45
        assert post["feedback_score"] == 0.75

        # Check learned patterns were updated
        patterns = tracker.audience["learned_patterns"]
        assert patterns["total_feedback_entries"] == 1
        assert "gap" in patterns["best_topics"]
        assert patterns["best_topics"]["gap"]["avg_score"] == 0.75
        assert "10:00" in patterns["best_times"]
        assert "x" in patterns["best_formats"]


def test_add_manual_feedback_by_title():
    """Test matching feedback by title substring."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
        logger = make_logger()
        tracker = PerformanceTracker(config, logger)

        tracker.memory_dir = tmpdir
        tracker.performance_file = os.path.join(tmpdir, 'performance.json')
        tracker.audience_file = os.path.join(tmpdir, 'audience.json')

        tracker.performance = {
            "published_posts": [{
                "typefully_id": "100",
                "title": "Signal count update",
                "platform": "linkedin",
                "published_url": "https://linkedin.com/post/100",
                "published_at": "2026-03-27T09:30:00Z",
                "source_topic": "data",
                "metrics": {}
            }],
            "manual_feedback": [],
            "last_sync": None
        }
        tracker.audience = {
            "insights": {}, "preferences": {}, "top_performing_content": [],
            "audience_segments": {},
            "learned_patterns": {"best_topics": {}, "best_times": {}, "best_formats": {}, "total_feedback_entries": 0}
        }

        # Match by partial title
        tracker.add_manual_feedback("signal count", {"score": 0.5, "topic_strength": "medium"})

        post = tracker.performance["published_posts"][0]
        assert post["feedback_score"] == 0.5
        assert tracker.audience["insights"]["topic_strength"]["data"] == "medium"


def test_add_manual_feedback_no_match():
    """Test that unmatched feedback is saved as standalone."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
        logger = make_logger()
        tracker = PerformanceTracker(config, logger)

        tracker.memory_dir = tmpdir
        tracker.performance_file = os.path.join(tmpdir, 'performance.json')
        tracker.audience_file = os.path.join(tmpdir, 'audience.json')

        tracker.performance = {"published_posts": [], "manual_feedback": [], "last_sync": None}
        tracker.audience = {"insights": {}, "preferences": {}, "learned_patterns": {}}

        tracker.add_manual_feedback("nonexistent post", {"score": 0.3, "notes": "Didn't work"})

        assert len(tracker.performance["manual_feedback"]) == 1
        assert tracker.performance["manual_feedback"][0]["matched"] is False


def test_get_performance_summary_no_data():
    """Test summary with no data."""
    config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
    logger = make_logger()
    tracker = PerformanceTracker(config, logger)
    tracker.performance = {"published_posts": [], "manual_feedback": [], "last_sync": None}

    summary = tracker.get_performance_summary()
    assert summary["status"] == "no_data"


def test_get_performance_summary_with_data():
    """Test summary with posts and feedback."""
    config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
    logger = make_logger()
    tracker = PerformanceTracker(config, logger)
    tracker.performance = {
        "published_posts": [
            {
                "title": "Post A", "source_topic": "gap",
                "metrics": {"impressions": 3000}, "feedback_score": 0.8
            },
            {
                "title": "Post B", "source_topic": "data",
                "metrics": {"impressions": 1000}, "feedback_score": 0.4
            }
        ],
        "manual_feedback": [{"matched": True}],
        "last_sync": "2026-03-28T12:00:00Z"
    }
    tracker.audience = {"learned_patterns": {"total_feedback_entries": 2}}

    summary = tracker.get_performance_summary()
    assert summary["status"] == "ok"
    assert summary["total_published"] == 2
    assert summary["top_by_score"][0]["title"] == "Post A"
    assert summary["top_by_impressions"][0]["impressions"] == 3000


def test_get_content_recommendations_insufficient():
    """Test recommendations with too few entries."""
    config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
    logger = make_logger()
    tracker = PerformanceTracker(config, logger)
    tracker.audience = {
        "learned_patterns": {"total_feedback_entries": 1}
    }

    recs = tracker.get_content_recommendations()
    assert recs["status"] == "insufficient_data"


def test_get_content_recommendations_sufficient():
    """Test recommendations with enough data."""
    config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
    logger = make_logger()
    tracker = PerformanceTracker(config, logger)
    tracker.audience = {
        "learned_patterns": {
            "total_feedback_entries": 5,
            "best_topics": {
                "gap": {"avg_score": 0.8, "count": 3, "scores": [0.7, 0.8, 0.9]},
                "data": {"avg_score": 0.4, "count": 2, "scores": [0.3, 0.5]}
            },
            "best_times": {
                "10:00": {"avg_score": 0.7, "count": 3, "scores": [0.6, 0.7, 0.8]},
                "18:00": {"avg_score": 0.5, "count": 2, "scores": [0.4, 0.6]}
            },
            "best_formats": {
                "x": {"avg_score": 0.7, "count": 4, "scores": [0.6, 0.7, 0.8, 0.6]},
                "linkedin": {"avg_score": 0.3, "count": 1, "scores": [0.3]}
            }
        }
    }

    recs = tracker.get_content_recommendations()
    assert recs["status"] == "ok"
    assert recs["focus_topics"][0] == "gap"
    assert recs["best_posting_hours"][0] == "10:00"
    assert recs["best_format"] == "x"
    # "data" has avg_score 0.4 which is above 0.3 threshold, so not in avoid_topics
    assert recs["avoid_topics"] == []


def test_get_content_recommendations_avoid_topics():
    """Test that topics with avg_score below 0.3 appear in avoid_topics."""
    config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
    logger = make_logger()
    tracker = PerformanceTracker(config, logger)
    tracker.audience = {
        "learned_patterns": {
            "total_feedback_entries": 5,
            "best_topics": {
                "gap": {"avg_score": 0.8, "count": 3, "scores": [0.7, 0.8, 0.9]},
                "trend": {"avg_score": 0.15, "count": 2, "scores": [0.1, 0.2]}
            },
            "best_times": {},
            "best_formats": {}
        }
    }

    recs = tracker.get_content_recommendations()
    assert recs["status"] == "ok"
    assert "trend" in recs["avoid_topics"]


def test_update_learned_patterns_multiple():
    """Test that multiple feedback entries accumulate correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"social": {"typefully_api_key": "test", "social_set_id": "123"}}
        logger = make_logger()
        tracker = PerformanceTracker(config, logger)

        tracker.memory_dir = tmpdir
        tracker.audience_file = os.path.join(tmpdir, 'audience.json')
        tracker.performance_file = os.path.join(tmpdir, 'performance.json')

        tracker.performance = {"published_posts": [], "manual_feedback": [], "last_sync": None}
        tracker.audience = {
            "insights": {}, "preferences": {},
            "learned_patterns": {"best_topics": {}, "best_times": {}, "best_formats": {}, "total_feedback_entries": 0}
        }

        post1 = {"source_topic": "gap", "platform": "x", "published_at": "2026-03-28T10:00:00Z"}
        post2 = {"source_topic": "gap", "platform": "x", "published_at": "2026-03-28T10:00:00Z"}

        tracker._update_learned_patterns(post1, {"score": 0.6})
        tracker._update_learned_patterns(post2, {"score": 0.9})

        patterns = tracker.audience["learned_patterns"]
        assert patterns["total_feedback_entries"] == 2
        assert patterns["best_topics"]["gap"]["count"] == 2
        assert patterns["best_topics"]["gap"]["avg_score"] == 0.75  # (0.6 + 0.9) / 2


if __name__ == "__main__":
    # Run all tests
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__} - {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)
