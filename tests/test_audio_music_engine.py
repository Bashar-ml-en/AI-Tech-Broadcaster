"""
Unit tests for Trending Background Music Engine and Sidechain Audio Ducking.
"""

import pytest
from pathlib import Path
from src.audio_music_engine import (
    get_trending_music_track,
    mix_voiceover_with_music,
    _get_audio_duration,
    MUSIC_DIR
)
from src.persona_manager import get_persona_by_id


def test_music_directory_has_tracks():
    """Verify that all 5 master trending tracks are present and valid."""
    expected = [
        "trending_malaysia_tech_phonk.mp3",
        "trending_cyber_keynote_energy.mp3",
        "trending_silicon_future_groove.mp3",
        "trending_synthwave_momentum.mp3",
        "trending_lofi_cyber_chill.mp3"
    ]
    for track_name in expected:
        track_path = MUSIC_DIR / track_name
        assert track_path.exists(), f"Missing track {track_name}"
        assert track_path.stat().st_size > 10000


def test_get_trending_music_track_mapping():
    """Verify smart acoustic energy selection by persona and region."""
    # Malaysia / SEA viral phonk trigger
    p_jensen = get_persona_by_id("jensen_huang")
    t_my = get_trending_music_track(p_jensen, headline="Massive AI chip breakthrough launches in Malaysia and SEA")
    assert "malaysia" in t_my.name or "phonk" in t_my.name

    # Sam Altman electro keynote
    p_sam = get_persona_by_id("sam_altman")
    t_sam = get_trending_music_track(p_sam, headline="OpenAI announces Operator agent")
    assert "cyber" in t_sam.name or "energy" in t_sam.name or "groove" in t_sam.name

    # Sundar Pichai synthwave
    p_sundar = get_persona_by_id("sundar_pichai")
    t_sundar = get_trending_music_track(p_sundar, headline="Google Gemini 2.5 Flash released")
    assert "synthwave" in t_sundar.name


def test_mix_voiceover_with_music_ducking(tmp_path):
    """Verify that mix_voiceover_with_music balances voice with ducked background beat."""
    vox = Path("storage/staging/test_short_voice.wav")
    if not vox.exists():
        pytest.skip("Test short voice file missing")

    out_mixed = tmp_path / "mixed_test_output.mp3"
    p_jensen = get_persona_by_id("jensen_huang")

    res = mix_voiceover_with_music(
        voiceover_path=vox,
        output_path=out_mixed,
        music_volume=0.15,
        persona=p_jensen,
        headline="Blackwell benchmarks released"
    )

    assert res.exists()
    assert res.stat().st_size > 5000

    # Ensure mixed audio duration closely matches original voice duration
    vox_dur = _get_audio_duration(vox)
    mixed_dur = _get_audio_duration(res)
    assert abs(mixed_dur - vox_dur) < 0.5
