"""
Tests for Automated Pre-Publish Quality Gate.
"""

from src.quality_gate import evaluate


def test_quality_gate_clean_post_passes():
    post = {
        "headline": "Anthropic Announces Claude 3.7 with Hybrid Reasoning",
        "source_url": "https://www.anthropic.com/news/claude-3-7-sonnet",
        "format_type": "post",
        "hook_narration": "Anthropic released Claude 3.7 Sonnet.",
        "body_narration": "Benchmark results hit 70.3% on SWE-bench Verified.",
        "call_to_action": "Will you use test-time compute?",
        "captions_json": '{"short_form": "Claude 3.7 hits 70.3% on SWE-bench. #AI #Tech"}'
    }
    source = "Anthropic released Claude 3.7 Sonnet with hybrid reasoning hitting 70.3% on SWE-bench Verified."
    res = evaluate(post, source_text=source)
    assert res["decision"] == "pass"
    assert res["reason"] is None


def test_quality_gate_invented_number_blocks():
    post = {
        "headline": "Anthropic Announces Claude 3.7 with Hybrid Reasoning",
        "source_url": "https://www.anthropic.com/news/claude-3-7-sonnet",
        "format_type": "post",
        "hook_narration": "Claude 3.7 achieved 92.4% on SWE-bench!",
        "body_narration": "Architecture changes everything.",
        "call_to_action": "What are your thoughts?",
        "captions_json": '{"short_form": "92.4% SWE-bench score. #AI"}'
    }
    source = "Anthropic released Claude 3.7 Sonnet hitting 70.3% on SWE-bench."
    res = evaluate(post, source_text=source)
    assert res["decision"] == "block"
    assert "92.4" in str(res["reason"])


def test_quality_gate_stock_ticker_blocks():
    post = {
        "headline": "New Model Challenges $NVDA and $AAPL Chip Ecosystem",
        "source_url": "https://openai.com/news/test",
        "format_type": "post",
        "hook_narration": "AI hardware will disrupt markets.",
        "body_narration": "Performance scales up.",
        "call_to_action": "Which chip wins?",
        "captions_json": "{}"
    }
    source = "AI hardware will disrupt markets."
    res = evaluate(post, source_text=source)
    assert res["decision"] == "block"
    assert "ticker detected: $NVDA" in str(res["reason"])


def test_quality_gate_banned_rumor_blocks():
    post = {
        "headline": "Next Gen Architecture Announced",
        "source_url": "https://openai.com/news/test",
        "format_type": "post",
        "hook_narration": "An unconfirmed leak indicates massive parameter jumps.",
        "body_narration": "Lab engineers are preparing deployment.",
        "call_to_action": "Are you ready?",
        "captions_json": "{}"
    }
    source = "Next Gen Architecture Announced."
    res = evaluate(post, source_text=source)
    assert res["decision"] == "block"
    assert "unconfirmed" in str(res["reason"]).lower()


def test_quality_gate_unauthorized_domain_blocks():
    post = {
        "headline": "Clean News from Random Blog",
        "source_url": "https://random-unverified-blog.xyz/rumors",
        "format_type": "post",
        "hook_narration": "Big tech update today.",
        "body_narration": "Software releases continue.",
        "call_to_action": "Thoughts?",
        "captions_json": "{}"
    }
    source = "Big tech update today."
    res = evaluate(post, source_text=source)
    assert res["decision"] == "block"
    assert "not on the FEED_SOURCES allowlist" in str(res["reason"])


def test_smart_numeric_grounding_boilerplate_does_not_block():
    post = {
        "headline": "OpenAI Releases New Mathematical Benchmark Weights",
        "source_url": "https://openai.com/news/math-benchmark",
        "format_type": "reel",
        "hook_narration": "Watch 30-second breakdown on the new open weights.",
        "body_narration": "Measured inference latency drops 42% on standard evaluations.",
        "call_to_action": "Are you testing this in your stack?",
        "captions_json": '{"short_form": "Watch 30s breakdown! Source: https://news.ycombinator.com/item?id=47613614"}'
    }
    # Note: 42% is in source; 30-second and 47613614 are boilerplate / URL ID
    source = "OpenAI releases mathematical benchmark with 42% latency reduction."
    res = evaluate(post, source_text=source)
    assert res["decision"] == "pass"
    assert res["scorecard"] is not None
    assert res["scorecard"]["reality_score"] >= 8.0
    assert res["scorecard"]["quality_score"] >= 8.0

