"""
Unit tests for Next-Gen Multi-Style AI Video Generation & B-Roll Engine
"""

from pathlib import Path
from src.stock_video_client import (
    extract_broll_keywords,
    generate_procedural_tech_broll,
    get_or_create_broll_clip,
)
from src.open_video_models import WAN_DEFAULT_SPACE, LIVEPORTRAIT_DEFAULT_SPACE


def test_extract_broll_keywords():
    text = "Nvidia Blackwell Ultra GPU architecture powers next-gen AI datacenters with NVLink"
    keywords = extract_broll_keywords(text)
    assert any("gpu" in k or "datacenter" in k or "hardware" in k for k in keywords)


def test_extract_broll_keywords_fallback():
    text = "General statement without explicit tech terms"
    keywords = extract_broll_keywords(text)
    assert len(keywords) > 0
    assert "artificial intelligence" in keywords or "technology" in keywords[0]


def test_generate_procedural_tech_broll_all_themes(tmp_path):
    themes = ["keynote", "cyberpunk", "minimalist", "news_desk"]
    for theme in themes:
        out_file = tmp_path / f"test_{theme}.mp4"
        success = generate_procedural_tech_broll(theme, out_file, duration=1.0, width=540, height=960)
        assert success is True
        assert out_file.exists()
        assert out_file.stat().st_size > 1000


def test_get_or_create_broll_clip_offline(tmp_path):
    out_file = tmp_path / "broll_clip.mp4"
    res_path = get_or_create_broll_clip(
        theme="cyberpunk",
        keywords=["robotics", "datacenter"],
        output_path=out_file,
        duration=1.0
    )
    assert res_path == out_file
    assert out_file.exists()
    assert out_file.stat().st_size > 1000


def test_open_video_models_configuration():
    assert "Wan" in WAN_DEFAULT_SPACE
    assert "LivePortrait" in LIVEPORTRAIT_DEFAULT_SPACE
