"""
Open-Source Video Foundation Models Adapter for AI Tech Broadcaster
Provides unified Gradio Client integration for Wan2.1, LivePortrait, EchoMimicV2, and MuseTalk.
Runs asynchronously against Hugging Face ZeroGPU Spaces without demanding local GPU compute.
"""

import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import imageio_ffmpeg
import subprocess

from gradio_client import Client, handle_file

logger = logging.getLogger("open_video_models")

HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN", os.getenv("HF_TOKEN", None))

WAN_DEFAULT_SPACE = os.getenv("WAN_SPACE", "Wan-AI/Wan2.1")
LIVEPORTRAIT_DEFAULT_SPACE = os.getenv("LIVEPORTRAIT_SPACE", "KlingAIResearch/LivePortrait")
ECHOMIMIC_DEFAULT_SPACE = os.getenv("ECHOMIMIC_SPACE", "fffiloni/EchoMimic")


async def generate_wan_scene(
    prompt: str,
    output_path: Path,
    space_name: str = WAN_DEFAULT_SPACE,
    timeout_sec: float = 60.0
) -> bool:
    """
    Generate photorealistic 9:16 B-roll footage via Alibaba Wan2.1 DiT model.
    """
    logger.info("[OpenVideo] Requesting Wan2.1 video generation for: '%s'...", prompt[:50])

    def _call_wan():
        client = Client(space_name, token=HF_TOKEN, verbose=False)
        result = client.predict(
            prompt=prompt,
            resolution="720*1280",
            seed=-1,
            api_name="/generate_video"
        )
        return result

    try:
        loop = asyncio.get_running_loop()
        res_video = await asyncio.wait_for(loop.run_in_executor(None, _call_wan), timeout=timeout_sec)
        if res_video and Path(res_video).exists() and Path(res_video).stat().st_size > 5000:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(res_video),
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-an",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "veryfast",
                str(output_path)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path.exists() and output_path.stat().st_size > 1000
    except Exception as e:
        logger.warning("[OpenVideo] Wan2.1 generation failed or timed out: %s", e)

    return False


async def generate_liveportrait_video(
    source_image: Path,
    driving_video: Path,
    output_path: Path,
    space_name: str = LIVEPORTRAIT_DEFAULT_SPACE,
    timeout_sec: float = 45.0
) -> bool:
    """
    Reenact portrait using LivePortrait's keypoint-based zero-distortion deformation.
    """
    logger.info("[OpenVideo] Requesting LivePortrait reenactment for %s...", source_image.name)

    def _call_liveportrait():
        client = Client(space_name, token=HF_TOKEN, verbose=False)
        result = client.predict(
            source_image=handle_file(str(source_image)),
            driving_video=handle_file(str(driving_video)),
            flag_relative=True,
            flag_do_crop=True,
            flag_remap=True,
            api_name="/animate"
        )
        return result

    try:
        loop = asyncio.get_running_loop()
        res_video = await asyncio.wait_for(loop.run_in_executor(None, _call_liveportrait), timeout=timeout_sec)
        if res_video and Path(res_video).exists() and Path(res_video).stat().st_size > 5000:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(res_video),
                "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "veryfast",
                str(output_path)
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return output_path.exists() and output_path.stat().st_size > 1000
    except Exception as e:
        logger.warning("[OpenVideo] LivePortrait generation failed or timed out: %s", e)

    return False
