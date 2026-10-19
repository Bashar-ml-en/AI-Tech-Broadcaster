"""
Unit tests for the AI Video Presenter Engine (ai_video_engine.py).
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.ai_video_engine import (
    _get_audio_duration,
    _render_archival_loop_video,
    generate_presenter_video,
    ASSETS_DIR
)
from src.persona_manager import get_persona_by_id


def test_get_audio_duration():
    """Verify audio duration extraction from a real audio file."""
    test_audio = Path("storage/staging/test_short_voice.wav")
    if test_audio.exists():
        dur = _get_audio_duration(test_audio)
        assert dur > 0.5
        assert dur < 10.0


@pytest.mark.anyio
async def test_generate_presenter_video_local_fallback(tmp_path):
    """Verify generate_presenter_video gracefully falls back to local motion renderer."""
    persona = get_persona_by_id("sundar_pichai")
    test_audio = Path("storage/staging/test_short_voice.wav")
    if not test_audio.exists():
        pytest.skip("Test short voice file not found")

    out_video = tmp_path / "test_fallback_reel.mp4"
    brief = {
        "title": "Unit Test Broadcast",
        "hook_narration": "Hi everyone, Sundar Pichai here.",
        "body_narration": "Testing fallback rendering in video engine.",
        "call_to_action": "Check out the repo."
    }

    res = await generate_presenter_video(
        persona=persona,
        audio_path=test_audio,
        output_video_path=out_video,
        brief=brief,
        prefer_ai_diffusion=False
    )
    assert res.exists()
    assert res.stat().st_size > 10000


def test_archival_loop_video_missing_file(tmp_path):
    """Verify archival looper returns False gracefully if loop video does not exist."""
    fake_video = tmp_path / "nonexistent.mp4"
    test_audio = Path("storage/staging/test_short_voice.wav")
    out_video = tmp_path / "out.mp4"

    success = _render_archival_loop_video(fake_video, test_audio, out_video)
    assert success is False
