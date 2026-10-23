#!/usr/bin/env python3
"""Tests for blog approval flow (Orchestrator helpers + BlogManager integration)."""
import json
import os
import sys
import tempfile
import logging
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))


def make_logger():
    logger = logging.getLogger("test_blog_approval")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


def test_slugify():
    """Test slug generation from titles."""
    from orchestrator import Orchestrator

    logger = make_logger()
    config = {"social": {"typefully_api_key": "x", "social_set_id": "1"}, "telegram": {"enabled": False}}
    orch = Orchestrator(config, logger)

    assert orch._slugify("How to Build a Gap Discovery Platform") == "how-to-build-a-gap-discovery-platform"
    assert orch._slugify("What's the Best Way?") == "whats-the-best-way"
    assert orch._slugify("  Multiple   Spaces  ") == "multiple-spaces"
    assert orch._slugify("") == "post"
    assert orch._slugify("A" * 100) == "a" * 60  # Truncated to 60


def test_sections_to_html():
    """Test blog outline sections to HTML conversion."""
    from orchestrator import Orchestrator

    logger = make_logger()
    config = {"social": {"typefully_api_key": "x", "social_set_id": "1"}, "telegram": {"enabled": False}}
    orch = Orchestrator(config, logger)

    # Empty sections
    assert "<p>Content pending.</p>" in orch._sections_to_html([])

    # Normal sections
    sections = [
        {"heading": "Intro", "points": ["Point 1", "Point 2"]},
        {"heading": "Deep Dive", "points": ["Detail A"]},
    ]
    html = orch._sections_to_html(sections)
    assert "<h2>Intro</h2>" in html
    assert "<h2>Deep Dive</h2>" in html
    assert "<li>Point 1</li>" in html
    assert "<li>Detail A</li>" in html

    # Section without heading
    sections = [{"points": ["Just points"]}]
    html = orch._sections_to_html(sections)
    assert "<h2>" not in html
    assert "<li>Just points</li>" in html


def test_save_pending_approval_blog():
    """Test saving blog draft to pending_approval.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from orchestrator import Orchestrator

        logger = make_logger()
        config = {"social": {"typefully_api_key": "x", "social_set_id": "1"}, "telegram": {"enabled": False}}
        orch = Orchestrator(config, logger)
        orch.memory_dir = tmpdir

        draft_data = {
            "id": "blog_20260329_014700",
            "topic": "Gap discovery",
            "type": "blog_post",
            "title": "How to Find Unsolved Problems",
            "meta_description": "A guide to gap discovery",
            "sections": [{"heading": "Intro", "points": ["Finding gaps"]}],
            "slug": "how-to-find-unsolved-problems",
            "status": "pending",
            "created_at": "2026-03-29T01:47:00"
        }

        orch._save_pending_approval(draft_data)

        pending_file = os.path.join(tmpdir, "pending_approval.json")
        assert os.path.exists(pending_file)

        with open(pending_file, 'r') as f:
            data = json.load(f)

        assert len(data["drafts"]) == 1
        assert data["drafts"][0]["type"] == "blog_post"
        assert data["drafts"][0]["status"] == "pending"


def test_callback_handler_blog_approve():
    """Test that callback handler processes blog approval."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from callback_handler import handle_callback, save_pending, load_pending

        # Override PENDING_PATH
        import callback_handler
        callback_handler.PENDING_PATH = os.path.join(tmpdir, "pending_approval.json")

        # Seed a pending blog draft
        save_pending({"drafts": [{
            "id": "blog_test_001",
            "type": "blog_post",
            "title": "Test Blog",
            "status": "pending"
        }]})

        # Mock Telegram API response
        with patch("callback_handler.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            handle_callback("blog_approve_blog_test_001", "query_123", "fake_token")

        pending = load_pending()
        assert pending["drafts"][0]["status"] == "approved"


def test_callback_handler_blog_reject():
    """Test that callback handler processes blog rejection."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from callback_handler import handle_callback, save_pending, load_pending

        import callback_handler
        callback_handler.PENDING_PATH = os.path.join(tmpdir, "pending_approval.json")

        save_pending({"drafts": [{
            "id": "blog_test_002",
            "type": "blog_post",
            "title": "Test Blog Reject",
            "status": "pending"
        }]})

        with patch("callback_handler.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            handle_callback("blog_reject_blog_test_002", "query_456", "fake_token")

        pending = load_pending()
        assert pending["drafts"][0]["status"] == "rejected"


def test_callback_handler_social_still_works():
    """Ensure social approve/reject still works after blog additions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from callback_handler import handle_callback, save_pending, load_pending

        import callback_handler
        callback_handler.PENDING_PATH = os.path.join(tmpdir, "pending_approval.json")

        save_pending({"drafts": [{
            "id": "draft_social_001",
            "type": "x_post",
            "content": "Test post",
            "status": "pending"
        }]})

        with patch("callback_handler.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            handle_callback("approve_draft_social_001", "query_789", "fake_token")

        pending = load_pending()
        assert pending["drafts"][0]["status"] == "approved"


if __name__ == "__main__":
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
            import traceback
            traceback.print_exc()
            failed += 1
    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    if failed > 0:
        sys.exit(1)
