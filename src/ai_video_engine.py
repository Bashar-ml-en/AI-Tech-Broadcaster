"""
AutoProdcaster - Photorealistic AI Video Presenter Engine
Integrates free AI video generation & authentic archival keynote splicing:
1. Tier 1: Authentic Archival Keynote Video Looping (Real 4K footage of CEO on stage)
2. Tier 2: EchoMimic / LivePortrait Audio-Driven Neural Video Diffusion (Hugging Face Spaces API)
3. Tier 3: Local Full-Body Keynote Compositor with Active Arm Gesturing & Viseme Articulation (Zero-Downtime Fallback)
"""

import os
import sys
import time
import shutil
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

import imageio_ffmpeg
from gradio_client import Client, handle_file

logger = logging.getLogger("ai_video_engine")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "storage" / "assets"
PERSONAS_DIR = ASSETS_DIR / "personas"
FULLBODY_DIR = PERSONAS_DIR / "fullbody"
VIDEOS_DIR = PERSONAS_DIR / "videos"

ECHOMIMIC_DEFAULT_SPACE = os.getenv("ECHOMIMIC_SPACE", "fffiloni/EchoMimic")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN", os.getenv("HF_TOKEN", None))


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


async def _generate_echomimic_video(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    space_name: str = ECHOMIMIC_DEFAULT_SPACE,
    timeout_sec: float = 90.0
) -> bool:
    """
    Call EchoMimic Hugging Face Space to generate an audio-synchronized photorealistic video.
    """
    logger.info("Attempting EchoMimic audio-driven neural video diffusion via Space '%s'...", space_name)

    def _sync_echomimic():
        client = Client(space_name, token=HF_TOKEN, verbose=False)
        result = client.predict(
            uploaded_img=handle_file(str(image_path)),
            uploaded_audio=handle_file(str(audio_path)),
            width=512,
            height=512,
            length=1200,
            seed=420,
            facemask_dilation_ratio=0.1,
            facecrop_dilation_ratio=0.5,
            context_frames=12,
            context_overlap=3,
            cfg=2.5,
            steps=25,
            sample_rate=16000,
            fps=24,
            device="cuda",
            api_name="/generate_video"
        )
        return result

    try:
        loop = asyncio.get_running_loop()
        res_video = await asyncio.wait_for(loop.run_in_executor(None, _sync_echomimic), timeout=timeout_sec)
        if res_video and Path(res_video).exists() and Path(res_video).stat().st_size > 5000:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            # Transcode to 1080x1920 30fps vertical format
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(res_video),
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-r", "30",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-b:v", "4500k",
                str(output_path)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            logger.info("EchoMimic neural video successfully generated: %s (%d bytes)", output_path.name, output_path.stat().st_size)
            return True
    except asyncio.TimeoutError:
        logger.warning("EchoMimic Hugging Face Space timed out after %ds (queue busy)", timeout_sec)
    except Exception as e:
        logger.warning("EchoMimic video generation failed: %s", e)

    return False


def _render_archival_loop_video(
    video_loop_path: Path,
    audio_path: Path,
    output_path: Path
) -> bool:
    """
    Loop real archival 4K/HD keynote footage of the CEO walking/talking on stage
    for the exact duration of the audio, and mux with the cloned speech track.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    duration = _get_audio_duration(audio_path)
    logger.info("Muxing real archival keynote footage for %s (%.1fs duration)...", video_loop_path.name, duration)

    cmd = [
        ffmpeg_exe, "-y",
        "-stream_loop", "-1",
        "-i", str(video_loop_path),
        "-i", str(audio_path),
        "-t", f"{duration:.2f}",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-b:v", "4500k",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_path)
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if output_path.exists() and output_path.stat().st_size > 10000:
            logger.info("Archival keynote video successfully rendered: %s", output_path.name)
            return True
    except Exception as e:
        logger.warning("Archival keynote video rendering failed: %s", e)
    return False


async def generate_presenter_video(
    persona: Dict[str, Any],
    audio_path: Path,
    output_video_path: Path,
    brief: Dict[str, Any],
    prefer_ai_diffusion: bool = True
) -> Path:
    """
    Main entry point for generating the CEO Presenter Reel.
    Cascades through:
    1. Tier 1: Real Archival Keynote Video Footage (if available in storage/assets/personas/videos/)
    2. Tier 2: EchoMimic Audio-Driven Neural Video Diffusion
    3. Tier 3: Local FullBodyKeynotePresenter Fallback
    """
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    ceo_id = persona.get("id", "sundar_pichai")
    headline = brief.get("title") or brief.get("headline") or ""

    # Mix voiceover with trending background music
    from src.audio_music_engine import mix_voiceover_with_music
    balanced_audio = audio_path.with_name(f"balanced_{audio_path.stem}.mp3")
    try:
        mix_voiceover_with_music(
            voiceover_path=audio_path,
            output_path=balanced_audio,
            persona=persona,
            headline=headline
        )
        if balanced_audio.exists() and balanced_audio.stat().st_size > 1000:
            audio_path = balanced_audio
    except Exception as mix_err:
        logger.warning("Audio mix error: %s; using raw voiceover.", mix_err)

    # Tier 1: Check for real archival video loop
    archival_video = VIDEOS_DIR / f"{ceo_id}_keynote_loop.mp4"
    if archival_video.exists() and archival_video.stat().st_size > 50000:
        success = _render_archival_loop_video(archival_video, audio_path, output_video_path)
        if success and output_video_path.exists() and output_video_path.stat().st_size > 10000:
            return output_video_path

    # Tier 2: Audio-Driven Neural Video Diffusion via EchoMimic
    if prefer_ai_diffusion:
        # Prefer full-body stage plate or clear front-facing portrait
        candidate_images = [
            FULLBODY_DIR / f"{ceo_id}_stage_center.png",
            FULLBODY_DIR / f"{ceo_id}_stage_center.jpg",
            PERSONAS_DIR / f"{ceo_id}.png",
            PERSONAS_DIR / persona.get("avatar_file", "sundar_pichai.png")
        ]
        source_image = next((p for p in candidate_images if p.exists() and p.stat().st_size > 2000), None)
        if source_image:
            success = await _generate_echomimic_video(
                image_path=source_image,
                audio_path=audio_path,
                output_path=output_video_path,
                timeout_sec=50.0
            )
            if success and output_video_path.exists() and output_video_path.stat().st_size > 10000:
                return output_video_path

    # Tier 3: High-Fidelity Local FullBodyKeynotePresenter Fallback
    logger.info("Falling back to local FullBodyKeynotePresenter engine for %s...", ceo_id)
    from src.video_synthesizer import render_motion_video
    render_motion_video(
        directive=brief,
        audio_path=audio_path,
        output_video_path=output_video_path,
        fps=30,
        persona=persona,
        spoken_script=brief.get("hook_narration", "") + " " + brief.get("body_narration", "")
    )
    return output_video_path
