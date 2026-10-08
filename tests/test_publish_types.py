"""
Tests for shared publish contracts and typed structures.
"""

from src.publish_types import PlatformResult, DispatchResult, MediaRef, GateResult


def test_media_ref_structure():
    ref: MediaRef = {
        "local_path": "/tmp/test.mp4",
        "public_url": "https://cdn.example.com/test.mp4",
        "hosted": True,
        "content_type": "video/mp4",
        "duration_sec": 30.5,
        "width": 1080,
        "height": 1920
    }
    assert ref["hosted"] is True
    assert ref["content_type"] == "video/mp4"
    assert ref["width"] == 1080


def test_platform_result_structure():
    res: PlatformResult = {
        "platform": "instagram",
        "status": "published",
        "mode": "live",
        "remote_id": "ig_12345",
        "permalink": "https://instagram.com/p/12345",
        "attempts": 1,
        "latency_ms": 120,
        "note": None
    }
    assert res["platform"] == "instagram"
    assert res["status"] == "published"


def test_dispatch_result_structure():
    disp: DispatchResult = {
        "post_id": 42,
        "overall": "published",
        "results": [
            {
                "platform": "facebook",
                "status": "published",
                "mode": "live",
                "remote_id": "fb_123",
                "permalink": "https://fb.com/123",
                "attempts": 1,
                "latency_ms": 80
            }
        ],
        "timestamp": 1700000000
    }
    assert disp["post_id"] == 42
    assert disp["overall"] == "published"
    assert len(disp["results"]) == 1


def test_gate_result_structure():
    gate: GateResult = {
        "decision": "pass",
        "checks": [
            {"name": "numeric_grounding", "passed": True, "detail": "All grounded"}
        ],
        "reason": None
    }
    assert gate["decision"] == "pass"
    assert gate["checks"][0]["passed"] is True
