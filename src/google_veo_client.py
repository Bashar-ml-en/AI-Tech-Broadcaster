"""
Google GenAI Video Generation Client (Gemini Omni 1.1 Flash & Veo 3.1)
Interfaces with Google Gemini Interactions API and Models API:
- gemini-omni-1.1-flash (First-frame-to-video & character-referenced 1080p 9:16 generation)
- veo-3.1-fast-generate-preview (High-velocity short-form 9:16 generation)
Includes asynchronous polling, reference portrait upload, and graceful fallback handling.
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
DEFAULT_OMNI_MODEL = os.getenv("GEMINI_OMNI_VIDEO_MODEL", "gemini-omni-1.1-flash")
DEFAULT_VEO_MODEL = os.getenv("GOOGLE_VEO_MODEL", "veo-3.1-fast-generate-preview")


def is_veo_available() -> bool:
    """Check if Gemini API key is configured and google-genai is installed."""
    key = os.getenv("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY
    if not key or "YOUR_GEMINI" in key:
        return False
    try:
        from google import genai  # noqa: F401
        return True
    except ImportError:
        return False


def generate_veo_video(
    prompt: str,
    output_filename: str = "veo_render",
    model: Optional[str] = None,
    aspect_ratio: str = "9:16",
    resolution: str = "1080p",
    first_frame_path: Optional[Path] = None,
    timeout_seconds: int = 180
) -> Optional[Path]:
    """
    Submit a 9:16 video generation request to Gemini Omni 1.1 Flash (or Veo 3.1)
    and poll until complete. Supports passing the CEO's portrait as a reference image.
    """
    if not is_veo_available():
        logger.info("Gemini API key not configured; using local 30fps CEO Character Animator engine.")
        return None

    api_key = os.getenv("GEMINI_API_KEY", "").strip() or GEMINI_API_KEY
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        # Tier 1: Gemini Omni 1.1 Flash via Interactions API (if available in SDK)
        if hasattr(client, "interactions"):
            try:
                inputs: list = []
                full_prompt = prompt
                if first_frame_path and Path(first_frame_path).exists():
                    uploaded = client.files.upload(file=str(first_frame_path))
                    inputs.append(uploaded)
                    full_prompt = f"[# References <IMAGE_REF_0>@Image1] {prompt} Use Image1 as character reference."
                inputs.append(full_prompt)

                interaction = client.interactions.create(
                    model=DEFAULT_OMNI_MODEL,
                    input=inputs,
                    config={
                        "aspect_ratio": aspect_ratio,
                        "resolution": resolution,
                        "duration_seconds": 8,
                    },
                )
                out_path = STAGING_DIR / f"{output_filename}.mp4"
                if hasattr(interaction, "output_video") and interaction.output_video:
                    Path(out_path).write_bytes(interaction.output_video.data)
                    return out_path
            except Exception as omni_err:
                logger.info("Gemini Omni 1.1 Flash fallback to Veo 3.1: %s", omni_err)

        # Tier 2: Veo 3.1 Generate Videos API
        target_model = model or DEFAULT_VEO_MODEL
        operation = client.models.generate_videos(
            model=target_model,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                aspect_ratio=aspect_ratio,
                resolution="720p" if resolution not in ("720p", "1080p") else resolution,
            ),
        )

        start_time = time.time()
        while not operation.done:
            if time.time() - start_time > timeout_seconds:
                return None
            time.sleep(8)
            operation = client.operations.get(operation)

        if operation.response and operation.response.generated_videos:
            gen_video = operation.response.generated_videos[0]
            out_path = STAGING_DIR / f"{output_filename}.mp4"
            client.files.download(file=gen_video.video)
            gen_video.video.save(str(out_path))
            return out_path
        return None
    except Exception as e:
        logger.warning("Cloud video generation unavailable (%s); using local 30fps CEO Character Animator.", e)
        return None


def test_veo_connection() -> Dict[str, Any]:
    """Quick diagnostic for Google GenAI SDK and Omni/Veo capability."""
    available = is_veo_available()
    return {
        "sdk_installed": available,
        "api_key_set": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "omni_model": DEFAULT_OMNI_MODEL,
        "target_model": DEFAULT_VEO_MODEL,
    }


generate_veo_broll = generate_veo_video
