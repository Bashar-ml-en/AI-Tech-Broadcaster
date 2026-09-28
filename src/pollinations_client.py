"""
Pollinations.ai Free Generative AI Client
Provides 100% free, unlimited, zero-key image generation using FLUX.1 Schnell & SDXL.
Generates ultra-photorealistic visuals for:
- 7-Page Poster Carousels (1080x1080)
- 9:16 Vertical Video Motion Backgrounds (1080x1920)
- 9:16 Ephemeral Story Decks (1080x1920)
"""

import os
import sys
import time
import random
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import quote
import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT_DIR / "storage" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("pollinations_client")


def generate_pollinations_image(
    prompt: str,
    output_filename: str,
    width: int = 1080,
    height: int = 1080,
    model: str = "flux",
    seed: Optional[int] = None
) -> Optional[Path]:
    """
    Fetch a photorealistic image from Pollinations.ai free API.
    Zero API key required, unlimited usage.
    """
    seed_val = seed if seed is not None else random.randint(1000, 999999)
    encoded_prompt = quote(prompt.strip())
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model={model}&nologo=true&seed={seed_val}"

    out_path = STAGING_DIR / f"{output_filename}.jpg"

    logger.info("Generating free FLUX image via Pollinations.ai: '%s' [%dx%d]", prompt[:60] + "...", width, height)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Tech-Broadcaster/2.0"
    }

    for attempt in range(2):
        try:
            with httpx.Client(timeout=45.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    with open(out_path, "wb") as f:
                        f.write(resp.content)
                    logger.info("Pollinations FLUX image saved: %s (%d bytes)", out_path.name, len(resp.content))
                    return out_path
                else:
                    logger.warning("Pollinations.ai returned status %s on attempt %d", resp.status_code, attempt + 1)
                    time.sleep(1.5)
                    # Retry with alternate seed
                    seed_val = random.randint(1000, 999999)
                    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&model={model}&nologo=true&seed={seed_val}"
        except Exception as e:
            logger.warning("Error fetching Pollinations image (attempt %d): %s", attempt + 1, e)
            time.sleep(1.5)
    return None


def generate_visual_for_story(
    headline: str,
    category: str = "core_chip",
    aspect_ratio: str = "1:1",
    seed: Optional[int] = None
) -> Optional[Path]:
    """
    Generate an executive-grade photorealistic AI visual based on the technical story topic.
    Aspect ratios:
    - '1:1' -> 1080x1080 (Square for Carousel Deck)
    - '9:16' -> 1080x1920 (Vertical for Reels & Stories)
    """
    width, height = (1080, 1080) if aspect_ratio == "1:1" else (1080, 1920)

    # Clean headline for prompt
    clean_topic = headline.split(":")[0] if ":" in headline else headline

    prompt_templates = [
        f"Cinematic photorealistic 8k studio render of {clean_topic}, advanced artificial intelligence neural processor with glowing cyan and amber photonic waveguides, volumetric lighting, dark obsidian reflections, shallow depth of field, hyper-detailed tech masterpiece",
        f"Ultra-detailed conceptual 3D render of {clean_topic}, crystalline semiconductor chip glowing with teal holographic data streams, clean executive tech aesthetic, volumetric rim lighting, 8k resolution, Unreal Engine 5 render",
        f"Futuristic AI supercomputing cluster and neural interconnects representing {clean_topic}, macro lens photography, dark glassmorphism, iridescent circuits, crisp studio lighting, 8k"
    ]

    selected_prompt = random.choice(prompt_templates)
    timestamp = int(time.time())
    safe_name = f"flux_visual_{timestamp}_{random.randint(10, 99)}"

    return generate_pollinations_image(
        prompt=selected_prompt,
        output_filename=safe_name,
        width=width,
        height=height,
        model="flux",
        seed=seed
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing Pollinations.ai FLUX generation...")
    test_img = generate_visual_for_story("Claude 3.7 Sonnet: Hybrid Reasoning Architecture", aspect_ratio="1:1")
    if test_img and test_img.exists():
        print(f"SUCCESS: Generated {test_img} (Size: {test_img.stat().st_size} bytes)")
    else:
        print("FAILED to generate image.")
