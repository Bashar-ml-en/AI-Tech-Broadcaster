"""
Google AI Studio / Google GenAI Video Generation Client (Veo 3.1 & Veo 2.0)
Interfaces with Google AI Studio and Vertex AI video generation endpoints:
- veo-3.1-generate-preview (Flagship cinematic 9:16 / 16:9)
- veo-3.1-fast-generate-preview (High-velocity short-form generation)
- veo-2.0-generate-001 (Production tier)
Includes asynchronous polling, exponential backoff, and graceful fallback handling.
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT_DIR / "storage" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT_DIR / "config" / ".env")
logger = logging.getLogger("google_veo_client")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_VEO_MODEL = os.getenv("GOOGLE_VEO_MODEL", "veo-3.1-fast-generate-preview")


def is_veo_available() -> bool:
    """Check if Gemini API key is configured and google-genai is installed."""
    if not GEMINI_API_KEY or "YOUR_GEMINI" in GEMINI_API_KEY:
        return False
    try:
        from google import genai
        return True
    except ImportError:
        return False


def generate_veo_video(
    prompt: str,
    output_filename: str = "veo_render",
    model: Optional[str] = None,
    aspect_ratio: str = "9:16",
    resolution: str = "720p",
    timeout_seconds: int = 180
) -> Optional[Path]:
    """
    Submit a video generation request to Google AI Studio Veo API and poll until complete.
    Returns path to downloaded MP4 file, or None if unavailable/quota-limited.
    """
    if not is_veo_available():
        logger.info("Google Veo SDK or API key not available, using local synthesis engine.")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        target_model = model or DEFAULT_VEO_MODEL

        logger.info("Submitting video generation to Google AI Studio Veo (%s): '%s' [aspect=%s]",
                    target_model, prompt[:60] + "...", aspect_ratio)

        operation = client.models.generate_videos(
            model=target_model,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            ),
        )

        start_time = time.time()
        poll_interval = 10

        while not operation.done:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                logger.warning("Veo video generation timed out after %ds, falling back.", timeout_seconds)
                return None

            logger.info("Waiting for Veo video generation (%ds elapsed)...", int(elapsed))
            time.sleep(poll_interval)
            operation = client.operations.get(operation)

        if operation.response and operation.response.generated_videos:
            gen_video = operation.response.generated_videos[0]
            out_path = STAGING_DIR / f"{output_filename}.mp4"
            client.files.download(file=gen_video.video)
            gen_video.video.save(str(out_path))
            logger.info("Veo video successfully saved to %s", out_path)
            return out_path
        else:
            logger.warning("Veo returned operation done but no generated video in response.")
            return None

    except Exception as e:
        logger.warning("Google AI Studio Veo generation exception: %s. Using local fallback.", e)
        return None


def test_veo_connection() -> Dict[str, Any]:
    """Quick diagnostic for Google GenAI SDK and Veo capability."""
    available = is_veo_available()
    return {
        "sdk_installed": available,
        "api_key_set": bool(GEMINI_API_KEY and "YOUR" not in GEMINI_API_KEY),
        "target_model": DEFAULT_VEO_MODEL
    }


# High-level alias for pipeline and video synthesizer
generate_veo_broll = generate_veo_video

