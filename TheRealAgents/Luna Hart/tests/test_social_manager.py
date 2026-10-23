#!/usr/bin/env python3
"""
Tests for social_manager.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from app.social_manager import SocialManager


class TestSocialManager:
    """Test suite for SocialManager class."""

    def test_init(self):
        """Test SocialManager initialization."""
        config = {
            'social': {
                'typefully_api_key': 'test_key',
                'social_set_id': 292721
            }
        }
        logger = Mock()
        manager = SocialManager(config, logger)
        assert manager.api_key == 'test_key'
        assert manager.social_set_id == 292721

    def test_init_missing_key(self):
        """Test SocialManager initialization with missing API key."""
        config = {'social': {'social_set_id': 292721}}
        logger = Mock()
        manager = SocialManager(config, logger)
        assert manager.api_key is None
        assert logger.error.called

    def test_api_base_url(self):
        """Test that API base URL is correct."""
        config = {
            'social': {
                'typefully_api_key': 'test_key',
                'social_set_id': 292721
            }
        }
        logger = Mock()
        manager = SocialManager(config, logger)
        assert manager.API_BASE == "https://api.typefully.com/v2"
