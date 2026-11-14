"""
Unit tests for Multimodal Vision Quality Gate & Frame Inspection
"""

from pathlib import Path
from PIL import Image
from src.vision_qa_gate import (
    audit_frame_quality,
    audit_rendered_video_visuals,
)


def test_audit_frame_quality_pass(tmp_path):
    img_path = tmp_path / "valid_frame.jpg"
    # Create 1080x1920 9:16 vertical image with reasonable contrast
    img = Image.new("RGB", (1080, 1920), color=(120, 140, 160))
    img.save(img_path)

    res = audit_frame_quality(img_path)
    assert res["passed"] is True
    assert res["resolution"] == "1080x1920"
    assert res["score"] >= 7.0
    assert len(res["errors"]) == 0


def test_audit_frame_quality_black_screen(tmp_path):
    img_path = tmp_path / "black_frame.jpg"
    img = Image.new("RGB", (1080, 1920), color=(0, 0, 0))
    img.save(img_path)

    res = audit_frame_quality(img_path)
    assert res["passed"] is False
    assert any("Black screen" in err for err in res["errors"])


def test_audit_frame_quality_wrong_aspect_ratio(tmp_path):
    img_path = tmp_path / "landscape_frame.jpg"
    img = Image.new("RGB", (1920, 1080), color=(100, 100, 100))
    img.save(img_path)

    res = audit_frame_quality(img_path)
    assert res["passed"] is False
    assert any("Aspect ratio deviation" in err for err in res["errors"])


def test_audit_rendered_video_missing_file():
    res = audit_rendered_video_visuals(Path("/nonexistent/video.mp4"))
    assert res["passed"] is False
    assert res["overall_score"] == 0.0
