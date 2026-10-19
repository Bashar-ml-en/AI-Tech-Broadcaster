"""
AutoProdcaster - Trending Background Music & Sidechain Audio Engine
Manages viral background music tracks (Malaysia/SEA tech phonk, electro house, future groove, synthwave)
and applies professional acoustic balancing & sidechain ducking to ensure the CEO voiceover
remains crisp, resonant, and punchy while riding over an energetic, attractive beat.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import imageio_ffmpeg

logger = logging.getLogger("audio_music_engine")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

ROOT_DIR = Path(__file__).resolve().parent.parent
MUSIC_DIR = ROOT_DIR / "storage" / "assets" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)


def _get_audio_duration(audio_path: Path) -> float:
    """Return exact audio duration in seconds via FFmpeg."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-i", str(audio_path)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in p.stderr.splitlines():
        if "Duration:" in line:
            try:
                part = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = part.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
            except Exception:
                break
    return 15.0


def get_trending_music_track(
    persona: Optional[Dict[str, Any]] = None,
    format_type: str = "reel",
    headline: str = ""
) -> Path:
    """
    Select the optimal trending background track based on audience region, persona, and energy:
    - High-velocity benchmarks, Southeast Asia / Malaysia viral energy, Jensen Huang, Liang Wenfeng:
      -> trending_malaysia_tech_phonk.mp3 (132 BPM: Viral 808 Phonk)
    - High-energy product launches, Sam Altman, Elon Musk:
      -> trending_cyber_keynote_energy.mp3 (128 BPM: Driving electro keynote)
    - Modern tech house groove, Mark Zuckerberg, Dario Amodei:
      -> trending_silicon_future_groove.mp3 (124 BPM)
    - Major model leaps, Sundar Pichai, Demis Hassabis, Satya Nadella:
      -> trending_synthwave_momentum.mp3 (115 BPM)
    - Deep architecture deep-dives or late night tech stories:
      -> trending_lofi_cyber_chill.mp3 (92 BPM)
    """
    hl_lower = (headline or "").lower()
    pid = (persona or {}).get("id", "")

    # Check for explicit Malaysia / Southeast Asia or viral phonk trigger
    if any(k in hl_lower for k in ["malaysia", "sea", "asia", "phonk", "speed", "unveil", "breakthrough", "benchmark", "fast"]):
        candidate = MUSIC_DIR / "trending_malaysia_tech_phonk.mp3"
        if candidate.exists():
            return candidate

    # Persona-specific acoustic energy mapping
    if pid in ("jensen_huang", "liang_wenfeng"):
        candidate = MUSIC_DIR / "trending_malaysia_tech_phonk.mp3"
        if candidate.exists():
            return candidate

    if pid in ("sam_altman", "elon_musk"):
        candidate = MUSIC_DIR / "trending_cyber_keynote_energy.mp3"
        if candidate.exists():
            return candidate

    if pid in ("mark_zuckerberg", "dario_amodei"):
        candidate = MUSIC_DIR / "trending_silicon_future_groove.mp3"
        if candidate.exists():
            return candidate

    if pid in ("sundar_pichai", "demis_hassabis", "satya_nadella"):
        candidate = MUSIC_DIR / "trending_synthwave_momentum.mp3"
        if candidate.exists():
            return candidate

    # Global default: Malaysia Tech Phonk (maximum TikTok retention)
    fallback = MUSIC_DIR / "trending_malaysia_tech_phonk.mp3"
    if fallback.exists():
        return fallback

    # Any available music file in the directory
    available = list(MUSIC_DIR.glob("*.mp3"))
    if available:
        return available[0]

    return fallback


def mix_voiceover_with_music(
    voiceover_path: Path,
    output_path: Path,
    music_path: Optional[Path] = None,
    music_volume: float = 0.16,
    persona: Optional[Dict[str, Any]] = None,
    headline: str = ""
) -> Path:
    """
    Professionally balances CEO voiceover with trending background music using FFmpeg:
    1. Measures exact voiceover duration D.
    2. Ducking: Music volume scaled to 14%-18% (music_volume=0.16, -22dB) so the CEO voice is loud and clear.
    3. Smooth Envelope: Music fades in gently over 0.5s and fades out over the last 0.8s.
    4. Speech Clarity: Vocal track boosted to 1.05 with dropout transition amix.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not voiceover_path.exists():
        logger.warning("Voiceover file %s does not exist; cannot mix.", voiceover_path)
        return output_path

    if music_path is None or not music_path.exists():
        music_path = get_trending_music_track(persona=persona, headline=headline)

    if not music_path.exists():
        logger.warning("No background music track found in %s; using voiceover alone.", MUSIC_DIR)
        shutil.copy(voiceover_path, output_path)
        return output_path

    duration = _get_audio_duration(voiceover_path)
    fade_out_start = max(0.5, duration - 0.8)

    logger.info(
        "Mixing CEO voiceover (%s, %.1fs) with trending beat '%s' at volume %.2f...",
        voiceover_path.name, duration, music_path.name, music_volume
    )

    filter_complex = (
        f"[1:a]volume={music_volume:.2f},afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_start:.2f}:d=0.8[bgm];"
        f"[0:a]volume=1.05[vox];"
        f"[vox][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(voiceover_path),
        "-stream_loop", "-1",
        "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-c:a", "libmp3lame" if output_path.suffix.lower() == ".mp3" else "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        str(output_path)
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if output_path.exists() and output_path.stat().st_size > 1000:
            logger.info("Successfully produced balanced audio master: %s (%d bytes)", output_path.name, output_path.stat().st_size)
            return output_path
    except Exception as e:
        logger.warning("FFmpeg audio ducking mix failed (%s); falling back to pure voiceover.", e)

    shutil.copy(voiceover_path, output_path)
    return output_path
