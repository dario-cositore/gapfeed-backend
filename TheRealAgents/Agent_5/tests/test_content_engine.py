#!/usr/bin/env python3
"""
Tests for content_engine.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.content_engine import ContentEngine


class TestContentEngine:
    """Test suite for ContentEngine class."""

    def test_init(self):
        """Test ContentEngine initialization with valid config."""
        config = {
            'llm': {
                'primary': 'deepseek/deepseek-v3.2',
                'fallback': 'mimo-v2.6-flash',
                'max_tokens': 2000,
                'temperature': 0.7
            }
        }
        logger = Mock()
        engine = ContentEngine(config, logger)
        assert engine.primary_model == 'deepseek/deepseek-v3.2'
        assert engine.fallback_model == 'mimo-v2.6-flash'
        assert engine.max_tokens == 2000
        assert engine.temperature == 0.7

    def test_init_default_values(self):
        """Test ContentEngine initialization with missing config."""
        config = {}
        logger = Mock()
        engine = ContentEngine(config, logger)
        assert engine.primary_model == 'deepseek/deepseek-v3.2'
        assert engine.fallback_model == 'mimo-v2.6-flash'
        assert engine.max_tokens == 2000
        assert engine.temperature == 0.7

    def test_sanitize_output_removes_em_dash(self):
        """Test that sanitize_output removes em dashes."""
        config = {'llm': {'max_tokens': 100}}
        logger = Mock()
        engine = ContentEngine(config, logger)

        # Test em dash removal
        test_text = "This is an em dash—should be removed."
        result = engine._sanitize_output(test_text)
        assert "—" not in result

    def test_sanitize_output_removes_en_dash(self):
        """Test that sanitize_output removes en dashes."""
        config = {'llm': {'max_tokens': 100}}
        logger = Mock()
        engine = ContentEngine(config, logger)

        # Test en dash removal
        test_text = "This has an en dash–should be removed."
        result = engine._sanitize_output(test_text)
        assert "–" not in result

    def test_validate_post_valid(self):
        """Test that valid posts pass validation."""
        config = {'llm': {'max_tokens': 100}}
        logger = Mock()
        engine = ContentEngine(config, logger)

        # Valid post with question
        valid_text = "This is a topic statement. What do you think?"
        assert engine._validate_post(valid_text, "x") == True

    def test_validate_post_no_question(self):
        """Test that posts without questions fail validation."""
        config = {'llm': {'max_tokens': 100}}
        logger = Mock()
        engine = ContentEngine(config, logger)

        # Invalid: no question
        invalid_text = "This is a topic statement. No question here."
        assert engine._validate_post(invalid_text, "x") == False

    def test_validate_post_em_dash(self):
        """Test that posts with em dashes fail validation."""
        config = {'llm': {'max_tokens': 100}}
        logger = Mock()
        engine = ContentEngine(config, logger)

        # Invalid: em dash
        invalid_text = "This has an em dash—what do you think?"
        assert engine._validate_post(invalid_text, "x") == False

    def test_validate_post_too_long(self):
        """Test that posts over 280 chars fail validation for X."""
        config = {'llm': {'max_tokens': 100}}
        logger = Mock()
        engine = ContentEngine(config, logger)

        # Invalid: too long (>280 chars)
        long_text = "A" * 281 + "?"
        assert engine._validate_post(long_text, "x") == False
