import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from src.publisher_x import (
    is_x_configured,
    build_oauth1_header,
    format_tweet_text,
    publish_to_x,
    diagnose_x_connection,
)

def test_build_oauth1_header():
    header = build_oauth1_header(
        method="POST",
        url="https://api.x.com/2/tweets",
        api_key="mock_consumer_key",
        api_secret="mock_consumer_secret",
        token="mock_token",
        token_secret="mock_token_secret",
    )
    assert header.startswith("OAuth ")
    assert "oauth_consumer_key=\"mock_consumer_key\"" in header
    assert "oauth_signature_method=\"HMAC-SHA1\"" in header
    assert "oauth_signature=" in header

def test_format_tweet_text_short():
    headline = "Google Unveils Gemini 2.5 Pro Deep Think"
    hook = "Parallel test-time reasoning is now live."
    url = "https://blog.google/gemini"
    primary, thread = format_tweet_text(headline, hook, url, lab="Google")
    assert "Google Unveils Gemini 2.5 Pro Deep Think" in primary
    assert url in primary
    assert len(primary) <= 280

def test_format_tweet_text_long_splits_thread():
    headline = "Extremely Long Headline That Needs To Fit Perfectly Within The 280 Character Limit On Modern X " * 3
    hook = "Detailed breakdown paragraph " * 15
    url = "https://blog.google/gemini"
    primary, thread = format_tweet_text(headline, hook, url, lab="Google")
    assert len(primary) <= 280
    assert len(thread) > 0

def test_publish_to_x_simulated():
    record = {
        "id": 9999,
        "headline": "Test AI Broadcast",
        "source_url": "https://example.com/ai",
        "hook_narration": "Test Hook",
    }
    with patch("src.publisher_x.is_x_configured", return_value=False):
        res = publish_to_x(record)
        assert res["platform"] == "x"
        assert res["status"] == "simulated"
        assert res["mode"] == "simulated"
        assert res.get("permalink") is not None
        assert "x.com" in res["permalink"]

def test_diagnose_x_connection_unconfigured():
    with patch("src.publisher_x.is_x_configured", return_value=False):
        diag = diagnose_x_connection()
        assert diag["configured"] is False
        assert diag["status_badge"] == "NEEDS X API KEYS"
        assert diag["mode"] == "simulated"
