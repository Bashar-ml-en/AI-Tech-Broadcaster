"""
End-to-end simulated broadcast cycle test with deterministic offline monkeypatching.
"""

import time
import sqlite3
from pathlib import Path
from src.pipeline import execute_broadcast_cycle
from src.webhook_server import DATABASE_PATH


def test_e2e_simulated_post_cycle(monkeypatch, tmp_path):
    source_content = "OpenAI announces general availability for developer testing with 85% benchmark accuracy."
    fake_candidate = {
        "tier": 1,
        "source_name": "OpenAI News",
        "headline": "OpenAI Matrix Reasoning Model General Availability",
        "url": f"https://openai.com/news/matrix-reasoning-ga-{time.time_ns()}",
        "summary": source_content,
        "curation_scores": {"total": 35},
        "curation_justification": "High consequence developer release"
    }

    # 0. Isolate lock file so active background daemon doesn't block the test
    monkeypatch.setattr("src.pipeline.CYCLE_LOCK_PATH", tmp_path / ".cycle.lock")

    # 1. Monkeypatch deduplication
    monkeypatch.setattr("src.pipeline.is_already_covered", lambda url, h="": False)

    # 2. Monkeypatch harvester
    monkeypatch.setattr("src.pipeline.harvest_candidate_stories", lambda: [fake_candidate])

    # 3. Monkeypatch score_story_curation
    monkeypatch.setattr("src.pipeline.score_story_curation", lambda h, s, u: {
        "scores": {"total": 35},
        "qualifies": True,
        "justification": "Offline qualification"
    })

    # 4. Monkeypatch web fetch
    monkeypatch.setattr("src.pipeline.tool_web_fetch", lambda url: {
        "content": source_content,
        "status": 200
    })

    # 5. Monkeypatch canonical script generation to be fully grounded in source_content
    monkeypatch.setattr("src.pipeline.generate_canonical_script", lambda cand, content, format_target: {
        "title": cand["headline"],
        "core_hook": "OpenAI announces general availability for developer testing.",
        "technical_mechanism": "Matrix reasoning architecture achieves 85% benchmark accuracy.",
        "engineering_implication": "Developers can now deploy complex multi-agent workflows.",
        "benchmark_or_proof": "85% benchmark accuracy.",
        "forward_question": "Will you test this model today?"
    })

    # 6. Create dummy carousel slide (1080x1080 valid png)
    from PIL import Image
    dummy_slide = tmp_path / "slide_1.png"
    img = Image.new("RGB", (1080, 1080), color=(20, 20, 30))
    img.save(dummy_slide, format="PNG")
    monkeypatch.setattr("src.pipeline.generate_carousel_deck", lambda brief, prefix: [str(dummy_slide)])

    # Execute POST cycle
    res = execute_broadcast_cycle(target_format="post")
    assert res is not None
    assert res["status"] == "success"
    assert "dispatch_result" in res

    d = res["dispatch_result"]
    assert d["overall"] == "simulated"
    post_id = res["post_id"]

    # Verify database row
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT id, publish_status, approval_status FROM posts WHERE id = ?", (post_id,)).fetchone()
        assert row is not None
        assert row["publish_status"] == "simulated"

        # Cleanup
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        conn.commit()
