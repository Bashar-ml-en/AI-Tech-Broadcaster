"""
Unit tests for the Neural CEO Voice Cloning Engine (voice_cloner.py).
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.voice_cloner import (
    load_voice_metadata,
    synthesize_ceo_voice,
    _clone_voice_elevenlabs,
    _synthesize_edge_fallback,
    VOICES_DIR
)
from src.persona_manager import get_persona_by_id


def test_voice_metadata_loaded():
    """Verify master voice reference metadata is present for key CEOs."""
    meta = load_voice_metadata()
    assert isinstance(meta, dict)
    assert "sundar_pichai" in meta
    assert "sam_altman" in meta
    assert "jensen_huang" in meta
    assert meta["sundar_pichai"]["edge_voice"] == "en-IN-PrabhatNeural"
    assert (VOICES_DIR / meta["sundar_pichai"]["wav_file"]).exists()


@pytest.mark.anyio
async def test_edge_fallback_synthesis(tmp_path):
    """Test calibrated Edge-TTS fallback generation."""
    persona = get_persona_by_id("sundar_pichai")
    out_file = tmp_path / "test_sundar_edge.mp3"

    res = await _synthesize_edge_fallback(
        narration_text="This is an automated test of the CEO voice synthesizer.",
        output_path=out_file,
        persona=persona
    )
    assert res.exists()
    assert res.stat().st_size > 1000


@pytest.mark.anyio
async def test_elevenlabs_mock(tmp_path):
    """Test ElevenLabs provider when configured."""
    out_file = tmp_path / "test_eleven.mp3"
    fake_audio = b"ID3\x04\x00\x00" + b"\x00" * 2000

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = fake_audio
        mock_post.return_value = mock_resp

        success = await _clone_voice_elevenlabs(
            narration_text="Test speech",
            voice_id="fake_voice_123",
            output_path=out_file,
            api_key="fake_key"
        )
        assert success is True
        assert out_file.exists()
        assert out_file.stat().st_size == len(fake_audio)


@pytest.mark.anyio
async def test_synthesize_ceo_voice_cascades_cleanly(tmp_path):
    """Verify synthesize_ceo_voice returns valid audio even when zero-shot is disabled or fails."""
    persona = get_persona_by_id("sam_altman")
    out_file = tmp_path / "test_sam_cascade.mp3"

    res = await synthesize_ceo_voice(
        narration_text="OpenAI DevDay keynote test announcement.",
        output_path=out_file,
        persona=persona,
        prefer_zero_shot=False
    )
    assert res.exists()
    assert res.stat().st_size > 1000
