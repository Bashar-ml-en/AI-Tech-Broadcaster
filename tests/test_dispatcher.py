"""
Tests for Master Omnichannel Autonomous Dispatcher.
"""

import sqlite3
from src.publisher_autonomous import (
    dispatch_autonomous_broadcast,
    compute_overall_status
)
from src.publish_types import PlatformResult
from src.webhook_server import DATABASE_PATH


def test_compute_overall_status_rules():
    # 1. All published
    results_all_pub: list[PlatformResult] = [
        {"platform": "facebook", "status": "published", "mode": "live", "attempts": 1, "latency_ms": 10},
        {"platform": "instagram", "status": "published", "mode": "live", "attempts": 1, "latency_ms": 10}
    ]
    assert compute_overall_status(results_all_pub) == "published"

    # 2. Partial (one published, one failed)
    results_partial: list[PlatformResult] = [
        {"platform": "facebook", "status": "published", "mode": "live", "attempts": 1, "latency_ms": 10},
        {"platform": "instagram", "status": "failed", "mode": "live", "attempts": 1, "latency_ms": 10}
    ]
    assert compute_overall_status(results_partial) == "partial"

    # 3. All simulated
    results_sim: list[PlatformResult] = [
        {"platform": "facebook", "status": "simulated", "mode": "simulated", "attempts": 1, "latency_ms": 10},
        {"platform": "threads", "status": "simulated", "mode": "simulated", "attempts": 1, "latency_ms": 10}
    ]
    assert compute_overall_status(results_sim) == "simulated"

    # 4. All failed
    results_fail: list[PlatformResult] = [
        {"platform": "facebook", "status": "failed", "mode": "live", "attempts": 1, "latency_ms": 10},
        {"platform": "instagram", "status": "failed", "mode": "live", "attempts": 1, "latency_ms": 10}
    ]
    assert compute_overall_status(results_fail) == "failed"


def test_dispatcher_idempotency():
    test_id = 8888
    # Insert temporary DB record
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (test_id,))
        conn.execute(
            "INSERT INTO posts (id, source_url, headline, format_type, approval_status, publish_status) VALUES (?, ?, ?, ?, 'auto', 'rendered')",
            (test_id, "https://example.com/item", "Test Item", "post")
        )
        conn.commit()

    post_rec = {"id": test_id, "source_url": "https://example.com/item", "headline": "Test Item", "format_type": "post"}

    # First run: in simulate mode
    res1 = dispatch_autonomous_broadcast(test_id, post_rec, [])
    assert res1["overall"] == "simulated"

    # Second run: must skip already simulated platforms
    res2 = dispatch_autonomous_broadcast(test_id, post_rec, [])
    assert res2["overall"] == "simulated"

    skipped_platforms = [r for r in res2["results"] if r.get("status") == "skipped" and r.get("note") == "already_simulated"]
    assert len(skipped_platforms) >= 3  # FB, IG, Threads

    # Clean up
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("DELETE FROM posts WHERE id = ?", (test_id,))
        conn.commit()
