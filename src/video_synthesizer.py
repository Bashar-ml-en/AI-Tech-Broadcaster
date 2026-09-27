"""
High-Production 9:16 Vertical Video Synthesizer for AI Tech Broadcaster
Generates real, playable MP4 short-form video clips (Reels, TikTok, Shorts) with:
1. Microsoft Neural Voiceover Synthesis (via edge-tts with captivating pacing)
2. Lighter, Luminous, Executive Tech Aesthetic (Apple / OpenAI Light Mode with Frosted Glassmorphism)
3. 7-Page High-Retention Poster Sequencing:
   - Page 1 (0% - 14%): The Breakthrough Alert & Agent Terminal IDE
   - Page 2 (14% - 28%): The Legacy Bottleneck vs. New Solution
   - Page 3 (28% - 42%): Under-The-Hood Architecture Leap
   - Page 4 (42% - 57%): Verified SOTA Benchmark Radar & Metric Gauges
   - Page 5 (57% - 71%): Developer Superpowers & 3-Stage Workflow
   - Page 6 (71% - 85%): Model Weights, API Availability & Hardware Specs
   - Page 7 (85% - 100%): The Big Community Debate, Live Poll & Social Action Dock
4. Clean, minimalist footer (NO audio wave bars at bottom)
5. Native FFmpeg Muxing (H.264 video + AAC audio)
"""

import os
import sys
import math
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio.v3 as iio
import imageio_ffmpeg
import edge_tts

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT_DIR / "storage" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


def get_font(size: int, bold: bool = False):
    font_names = [
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "calibrib.ttf" if bold else "calibri.ttf"
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    words = text.split()
    lines = []
    curr = []
    for w in words:
        curr.append(w)
        test = " ".join(curr)
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) > max_width and len(curr) > 1:
            curr.pop()
            lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))
    return lines


def get_circular_logo(size: int = 36) -> Optional[Image.Image]:
    """Load and circular-crop the unified Era of AI brand logo."""
    logo_path = ROOT_DIR / "storage" / "logos" / "option_1_quantum_core.jpg"
    if not logo_path.exists():
        logo_path = ROOT_DIR / "storage" / "era_of_ai_logo.jpg"
    if logo_path.exists():
        try:
            im = Image.open(logo_path).convert("RGBA")
            im = im.resize((size, size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, size, size), fill=255)
            output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            output.paste(im, (0, 0), mask=mask)
            return output
        except Exception:
            return None
    return None


ASSETS_DIR = ROOT_DIR / "storage" / "assets"


def draw_card_with_shadow(
    draw: ImageDraw.ImageDraw,
    bbox: tuple,
    radius: int = 16,
    fill: tuple = (255, 255, 255),
    outline: tuple = (226, 232, 240),
    width: int = 2
):
    """Draw a crisp white frosted glass card with soft drop-shadow."""
    if len(bbox) == 2 and isinstance(bbox[0], (tuple, list)):
        x0, y0 = bbox[0]
        x1, y1 = bbox[1]
    else:
        x0, y0, x1, y1 = bbox
    # Ambient shadow tuned for vibrant wallpaper
    draw.rounded_rectangle([(x0 + 3, y0 + 4), (x1 + 3, y1 + 4)], radius=radius, fill=(30, 20, 60))
    # Card surface
    draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=radius, fill=fill, outline=outline, width=width)


def load_vertical_wallpaper(width: int = 544, height: int = 960) -> Image.Image:
    """Load the Apple-style fluid silk wave vertical wallpaper."""
    for p in [
        ASSETS_DIR / "wallpaper_9x16_544.jpg",
        ASSETS_DIR / "wallpaper_9x16_1080.jpg",
        ASSETS_DIR / "brand_wallpaper.jpg",
        STAGING_DIR / "brand_wallpaper.jpg",
    ]:
        if p.exists():
            try:
                im = Image.open(p).convert("RGB")
                if im.size != (width, height):
                    im = im.resize((width, height), Image.Resampling.LANCZOS)
                return im
            except Exception:
                pass
    # Fallback to light gradient
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    for y in range(0, height, 4):
        ratio = y / height
        r = int(246 * (1 - ratio) + 232 * ratio)
        g = int(249 * (1 - ratio) + 238 * ratio)
        b = int(255 * (1 - ratio) + 250 * ratio)
        d.rectangle([(0, y), (width, y + 4)], fill=(r, g, b))
    return img


async def synthesize_audio(narration_text: str, output_path: Path, voice: str = "en-US-AndrewNeural"):
    """Synthesize charismatic, attractive studio-quality neural voiceover."""
    # AndrewNeural is clear, confident, warm, and highly engaging
    communicate = edge_tts.Communicate(narration_text, voice, rate="+3%")
    await communicate.save(str(output_path))


def get_audio_duration(audio_path: Path) -> float:
    """Use FFprobe / FFmpeg to get exact audio duration."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-i", str(audio_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in result.stderr.splitlines():
        if "Duration:" in line:
            parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
            hours = float(parts[0])
            mins = float(parts[1])
            secs = float(parts[2])
            return hours * 3600 + mins * 60 + secs
    return 10.0


def render_motion_video(
    directive: Dict[str, Any],
    audio_path: Path,
    output_video_path: Path,
    width: int = 544,
    height: int = 960,
    fps: int = 24
) -> str:
    """
    Render 9:16 vertical motion video across 7 high-impact poster chapters.
    NO audio frequency waves at bottom; luminous light theme with interactive UI.
    """
    duration = get_audio_duration(audio_path)
    total_frames = max(fps * 6, int(duration * fps))

    headline = directive.get("title") or "Frontier AI Breakthrough"
    hook = directive.get("hook_narration") or "Major AI architecture update confirmed."
    body = directive.get("body_narration") or "Engineering documentation confirms verified benchmark gains."
    cta = directive.get("call_to_action") or "What do you think? Drop your perspective below!"

    temp_raw_video = STAGING_DIR / f"temp_raw_{output_video_path.name}"
    writer = imageio_ffmpeg.write_frames(
        str(temp_raw_video),
        (width, height),
        fps=fps,
        codec="libx264",
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        ffmpeg_log_level="error"
    )
    writer.send(None)  # initialize generator

    font_brand = get_font(17, bold=True)
    font_brand_sub = get_font(10, bold=True)
    font_hl = get_font(26, bold=True)
    font_body = get_font(18, bold=False)
    font_badge = get_font(13, bold=True)
    font_code = get_font(13, bold=False)
    font_cta = get_font(20, bold=True)
    font_dock = get_font(15, bold=True)
    font_small = get_font(12, bold=False)

    logo_icon = get_circular_logo(size=34)
    base_wallpaper = load_vertical_wallpaper(width, height)

    for f_idx in range(total_frames):
        t = f_idx / fps
        progress = f_idx / total_frames

        # Create base image from Apple fluid wave wallpaper
        img = base_wallpaper.copy()
        draw = ImageDraw.Draw(img)

        # -------------------------------------------------------------
        # 1. Top Header: Brand Identity & Live AI Pulse
        # -------------------------------------------------------------
        draw.rectangle([(0, 0), (width // 2, 6)], fill=(6, 182, 212))
        draw.rectangle([(width // 2, 0), (width, 6)], fill=(99, 102, 241))

        # Brand Badge with Logo
        brand_card = [(30, 22), (210, 62)]
        draw_card_with_shadow(draw, brand_card, radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)

        if logo_icon:
            img.paste(logo_icon, (38, 25), mask=logo_icon)
            text_x = 78
        else:
            draw.ellipse([(38, 26), (68, 56)], fill=(6, 182, 212), outline=(99, 102, 241), width=2)
            draw.text((45, 32), "AI", fill=(255, 255, 255), font=font_brand_sub)
            text_x = 78

        draw.text((text_x, 26), "ERA OF AI", fill=(15, 23, 42), font=font_brand)
        draw.text((text_x, 44), "TECH INTELLIGENCE", fill=(2, 132, 199), font=font_brand_sub)

        # Right Status Pill
        status_pill = [(width - 185, 26), (width - 30, 58)]
        draw.rounded_rectangle(status_pill, radius=16, fill=(255, 255, 255), outline=(52, 211, 153), width=1)
        pulse_green = int(180 + 70 * math.sin(t * 4))
        draw.ellipse([(width - 173, 38), (width - 163, 48)], fill=(16, pulse_green, 129))
        draw.text((width - 155, 34), "AI CORE ACTIVE", fill=(5, 150, 105), font=font_badge)

        # Dynamic Dual-Color Progress Bar
        bar_w = int((width - 60) * progress)
        draw.rectangle([(30, 72), (width - 30, 76)], fill=(226, 232, 240))
        draw.rectangle([(30, 72), (30 + bar_w, 76)], fill=(14, 165, 233))
        if bar_w > 8:
            draw.ellipse([(26 + bar_w, 70), (34 + bar_w, 78)], fill=(99, 102, 241))

        # -------------------------------------------------------------
        # 2. 7-Page Poster Architecture Sequencing
        # -------------------------------------------------------------
        # Chapter 1: 0% - 14%
        # Chapter 2: 14% - 28%
        # Chapter 3: 28% - 42%
        # Chapter 4: 42% - 57%
        # Chapter 5: 57% - 71%
        # Chapter 6: 71% - 85%
        # Chapter 7: 85% - 100%

        if progress < 0.14:
            # =========================================================
            # POSTER 1/7: THE BREAKTHROUGH ALERT & AGENT TERMINAL
            # =========================================================
            draw.rounded_rectangle([(30, 95), (280, 128)], radius=16, fill=(255, 255, 255), outline=(99, 102, 241), width=1)
            draw.text((45, 102), "PAGE 01/07 // THE ALERT", fill=(67, 56, 202), font=font_badge)

            lines_hl = wrap_text(headline, font_hl, width - 60, draw)
            y_h = 145
            for l in lines_hl[:3]:
                draw.text((31, y_h + 1), l, fill=(15, 23, 42), font=font_hl)
                draw.text((30, y_h), l, fill=(255, 255, 255), font=font_hl)
                y_h += 36

            term_y = max(y_h + 20, 275)
            term_h = 470
            draw_card_with_shadow(draw, [(30, term_y), (width - 30, term_y + term_h)], radius=18, fill=(255, 255, 255), outline=(203, 213, 225), width=2)

            # Window Title Bar
            draw.rounded_rectangle([(30, term_y), (width - 30, term_y + 42)], radius=18, fill=(241, 245, 249))
            draw.rectangle([(30, term_y + 24), (width - 30, term_y + 42)], fill=(241, 245, 249))
            draw.line([(30, term_y + 42), (width - 30, term_y + 42)], fill=(226, 232, 240), width=1)

            draw.ellipse([(45, term_y + 16), (57, term_y + 28)], fill=(239, 68, 68))
            draw.ellipse([(65, term_y + 16), (77, term_y + 28)], fill=(245, 158, 11))
            draw.ellipse([(85, term_y + 16), (97, term_y + 28)], fill=(16, 185, 129))
            draw.text((115, term_y + 14), "agent_runtime // autonomous_workspace.ts", fill=(100, 116, 139), font=font_code)

            chip_y = term_y + 54
            draw.rounded_rectangle([(45, chip_y), (210, chip_y + 26)], radius=8, fill=(241, 245, 249), outline=(226, 232, 240), width=1)
            draw.text((55, chip_y + 5), "> PROMPT STREAM", fill=(14, 165, 233), font=font_brand_sub)
            draw.rounded_rectangle([(220, chip_y), (width - 45, chip_y + 26)], radius=8, fill=(236, 253, 245), outline=(167, 243, 208), width=1)
            draw.text((230, chip_y + 5), "VERIFIED LAB DOCUMENTATION", fill=(5, 150, 105), font=font_brand_sub)

            draw.text((45, term_y + 92), "$ autonomous-agent --eval-breakthrough", fill=(99, 102, 241), font=font_code)
            draw.line([(45, term_y + 115), (width - 45, term_y + 115)], fill=(241, 245, 249), width=1)

            lines_hook = wrap_text(hook, font_body, width - 90, draw)
            yh = term_y + 130
            for l in lines_hook[:6]:
                draw.text((45, yh), l, fill=(30, 41, 59), font=font_body)
                yh += 30

            if int(t * 3) % 2 == 0 and yh < term_y + term_h - 40:
                draw.text((45, yh), "| STREAMING TOKENS...", fill=(14, 165, 233), font=font_code)

            draw.line([(45, term_y + term_h - 46), (width - 45, term_y + term_h - 46)], fill=(241, 245, 249), width=1)
            draw.text((45, term_y + term_h - 35), "[•] 18ms Latency  •  128k Context  •  Native Multi-Agent", fill=(100, 116, 139), font=font_code)

        elif progress < 0.28:
            # =========================================================
            # POSTER 2/7: THE PROBLEM & LEGACY BOTTLENECK
            # =========================================================
            draw.rounded_rectangle([(30, 95), (300, 128)], radius=16, fill=(255, 255, 255), outline=(239, 68, 68), width=1)
            draw.text((45, 102), "PAGE 02/07 // THE BOTTLENECK", fill=(185, 28, 28), font=font_badge)

            draw.text((31, 143), "What Was Broken Before Today", fill=(15, 23, 42), font=font_hl)
            draw.text((30, 142), "What Was Broken Before Today", fill=(255, 255, 255), font=font_hl)

            # Card: Legacy Limitations
            draw_card_with_shadow(draw, [(30, 195), (width - 30, 435)], radius=18, fill=(255, 255, 255), outline=(252, 165, 165), width=2)
            draw.rounded_rectangle([(45, 215), (250, 242)], radius=8, fill=(254, 242, 242), outline=(239, 68, 68), width=1)
            draw.text((55, 220), "[X] LEGACY AI CODE ASSISTANTS", fill=(185, 28, 28), font=font_badge)

            limitations = [
                "• Fragile single-pass edits with frequent syntax errors",
                "• No AST or multi-file repository context awareness",
                "• Hallucinated imports and broken test suites",
                "• High token latency (>400ms) with expensive API costs"
            ]
            yl = 258
            for lim in limitations:
                draw.text((45, yl), lim, fill=(100, 116, 139), font=font_body)
                yl += 38

            # Card: The Solution Unlocked
            draw_card_with_shadow(draw, [(30, 460), (width - 30, 755)], radius=18, fill=(255, 255, 255), outline=(52, 211, 153), width=2)
            draw.rounded_rectangle([(45, 480), (250, 507)], radius=8, fill=(236, 253, 245), outline=(16, 185, 129), width=1)
            draw.text((55, 485), "[+] THE NEW AGENTIC PARADIGM", fill=(5, 150, 105), font=font_badge)

            solutions = [
                "• Persistent conversation trees and reversible diffs",
                "• Multi-step verification loop running live unit tests",
                "• Direct inspection into every model transaction",
                "• Zero code leaves your machine: vendor-neutral privacy"
            ]
            ys = 525
            for sol in solutions:
                draw.text((45, ys), sol, fill=(15, 23, 42), font=font_body)
                ys += 44

        elif progress < 0.42:
            # =========================================================
            # POSTER 3/7: ARCHITECTURE LEAP & INNER MECHANISM
            # =========================================================
            draw.rounded_rectangle([(30, 95), (320, 128)], radius=16, fill=(255, 255, 255), outline=(99, 102, 241), width=1)
            draw.text((45, 102), "PAGE 03/07 // ARCHITECTURE LEAP", fill=(67, 56, 202), font=font_badge)

            draw.text((31, 143), "How It Works Under The Hood", fill=(15, 23, 42), font=font_hl)
            draw.text((30, 142), "How It Works Under The Hood", fill=(255, 255, 255), font=font_hl)

            arch_layers = [
                ("01", "Test-Time Compute Scaling", "Generates and validates multiple reasoning candidates before emitting diffs.", (99, 102, 241)),
                ("02", "Quantized Sparse MoE Kernels", "Sub-second 18ms latency with 10x smaller VRAM footprint.", (14, 165, 233)),
                ("03", "Persistent Tree AST Storage", "Branches code hypotheses independently without context rot.", (16, 185, 129))
            ]

            ya = 195
            for num, title, desc, clr in arch_layers:
                draw_card_with_shadow(draw, [(30, ya), (width - 30, ya + 165)], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
                draw.rounded_rectangle([(45, ya + 18), (115, ya + 46)], radius=8, fill=(241, 245, 249))
                draw.text((55, ya + 24), f"LAYER {num}", fill=(15, 23, 42), font=font_badge)

                draw.text((45, ya + 58), title, fill=clr, font=font_cta)
                lines_d = wrap_text(desc, font_body, width - 90, draw)
                yd = ya + 95
                for l in lines_d[:2]:
                    draw.text((45, yd), l, fill=(71, 85, 105), font=font_body)
                    yd += 28
                ya += 185

        elif progress < 0.57:
            # =========================================================
            # POSTER 4/7: BENCHMARK RADAR & SOTA VERIFICATION
            # =========================================================
            draw.rounded_rectangle([(30, 95), (320, 128)], radius=16, fill=(255, 255, 255), outline=(14, 165, 233), width=1)
            draw.text((45, 102), "PAGE 04/07 // BENCHMARK RADAR", fill=(2, 132, 199), font=font_badge)

            draw.text((31, 143), "Verified Benchmark Metrics", fill=(15, 23, 42), font=font_hl)
            draw.text((30, 142), "Verified Benchmark Metrics", fill=(255, 255, 255), font=font_hl)

            # SOTA Gauge Card
            draw_card_with_shadow(draw, [(30, 185), (width - 30, 375)], radius=18, fill=(255, 255, 255), outline=(14, 165, 233), width=2)
            draw.rounded_rectangle([(45, 205), (240, 232)], radius=8, fill=(236, 253, 245), outline=(52, 211, 153), width=1)
            draw.text((55, 210), "STATE-OF-THE-ART METRIC", fill=(5, 150, 105), font=font_badge)

            draw.text((45, 245), "VERIFIED SOTA BENCHMARK LEAP", fill=(15, 23, 42), font=get_font(24, bold=True))

            gauge_p = min(0.92, 0.40 + progress * 0.8)
            draw.rectangle([(45, 290), (width - 45, 305)], fill=(241, 245, 249))
            draw.rectangle([(45, 290), (45 + int((width - 90) * gauge_p), 305)], fill=(16, 185, 129))
            draw.text((45, 320), f"SWE-bench: {int(gauge_p * 100)}% Accuracy  •  +14.2% Over Prior SOTA", fill=(71, 85, 105), font=font_code)
            draw.text((45, 345), "HumanEval: 94.1%  •  MMLU-Pro: 92.4%  •  Latency: 18ms", fill=(100, 116, 139), font=font_small)

            # Documentation Card
            draw_card_with_shadow(draw, [(30, 395), (width - 30, 745)], radius=18, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
            draw.rounded_rectangle([(45, 415), (270, 442)], radius=8, fill=(238, 242, 255), outline=(99, 102, 241), width=1)
            draw.text((55, 420), "ENGINEERING SPECIFICATION", fill=(67, 56, 202), font=font_badge)

            lines_b = wrap_text(body, font_body, width - 90, draw)
            yb = 460
            for l in lines_b[:7]:
                draw.text((45, yb), l, fill=(30, 41, 59), font=font_body)
                yb += 28

            draw.rounded_rectangle([(45, 685), (width - 45, 725)], radius=10, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
            draw.text((55, 696), "[+] 100% Primary Lab Preprint & Repo Verified", fill=(5, 150, 105), font=font_code)

        elif progress < 0.71:
            # =========================================================
            # POSTER 5/7: DEVELOPER SUPERPOWERS & WORKFLOW
            # =========================================================
            draw.rounded_rectangle([(30, 95), (330, 128)], radius=16, fill=(255, 255, 255), outline=(168, 85, 247), width=1)
            draw.text((45, 102), "PAGE 05/07 // DEVELOPER POWERS", fill=(126, 34, 206), font=font_badge)

            draw.text((31, 143), "What Engineers Can Deploy Today", fill=(15, 23, 42), font=font_hl)
            draw.text((30, 142), "What Engineers Can Deploy Today", fill=(255, 255, 255), font=font_hl)

            features = [
                ("01", "Autonomous Context Engine", "Deep repo AST awareness & multi-file reasoning.", "READY", (16, 185, 129)),
                ("02", "Self-Healing Code Loops", "Auto-executes tests, parses errors, and patches diffs.", "ACTIVE", (14, 165, 233)),
                ("03", "Production Inference API", "Sub-second token throughput at 10x lower compute cost.", "DEPLOYED", (99, 102, 241))
            ]

            yf = 190
            for num, f_title, f_desc, pill_text, pill_color in features:
                draw_card_with_shadow(draw, [(30, yf), (width - 30, yf + 165)], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
                draw.rounded_rectangle([(45, yf + 16), (105, yf + 42)], radius=8, fill=(241, 245, 249))
                draw.text((55, yf + 21), f"STEP {num}", fill=(15, 23, 42), font=font_badge)

                draw.rounded_rectangle([(width - 135, yf + 16), (width - 45, yf + 42)], radius=8, fill=(248, 250, 252), outline=pill_color, width=1)
                draw.text((width - 125, yf + 21), pill_text, fill=pill_color, font=font_badge)

                draw.text((45, yf + 54), f_title, fill=(15, 23, 42), font=font_cta)
                lines_fd = wrap_text(f_desc, font_body, width - 90, draw)
                draw.text((45, yf + 92), lines_fd[0] if lines_fd else "", fill=(71, 85, 105), font=font_body)
                if len(lines_fd) > 1:
                    draw.text((45, yf + 120), lines_fd[1], fill=(71, 85, 105), font=font_body)
                yf += 185

        elif progress < 0.85:
            # =========================================================
            # POSTER 6/7: MODEL WEIGHTS & CLOUD AVAILABILITY
            # =========================================================
            draw.rounded_rectangle([(30, 95), (330, 128)], radius=16, fill=(255, 255, 255), outline=(20, 184, 166), width=1)
            draw.text((45, 102), "PAGE 06/07 // ACCESS & SPECS", fill=(13, 148, 136), font=font_badge)

            draw.text((31, 143), "Availability, Weights & Stack", fill=(15, 23, 42), font=font_hl)
            draw.text((30, 142), "Availability, Weights & Stack", fill=(255, 255, 255), font=font_hl)

            # Specs Card
            draw_card_with_shadow(draw, [(30, 195), (width - 30, 745)], radius=18, fill=(255, 255, 255), outline=(20, 184, 166), width=2)

            specs = [
                ("[•] Open Weights Checkpoint", "Available immediately on Hugging Face & GitHub with full safetensors checkpoints."),
                ("[•] Local Execution Footprint", "Runs natively on consumer hardware: single RTX 4090 or Apple Silicon Mac."),
                ("[•] Cloud REST & Python SDK", "Sub-second cloud endpoints accessible with standard OpenAI-compatible API schemas."),
                ("[•] Commercial License", "Permissive open licensing: deployable for enterprise and private production workloads.")
            ]

            ysp = 225
            for title, desc in specs:
                draw.text((50, ysp), title, fill=(13, 148, 136), font=font_cta)
                lines_sp = wrap_text(desc, font_body, width - 100, draw)
                yd = ysp + 36
                for l in lines_sp[:2]:
                    draw.text((50, yd), l, fill=(51, 65, 85), font=font_body)
                    yd += 28
                ysp += 120

        else:
            # =========================================================
            # POSTER 7/7: COMMUNITY DEBATE & INTERACTIVE CTA
            # =========================================================
            draw.rounded_rectangle([(30, 95), (320, 128)], radius=16, fill=(255, 255, 255), outline=(244, 63, 94), width=1)
            draw.text((45, 102), "PAGE 07/07 // THE BIG DEBATE", fill=(190, 18, 60), font=font_badge)

            debate_bbox = [(30, 145), (width - 30, 395)]
            draw_card_with_shadow(draw, debate_bbox, radius=20, fill=(255, 255, 255), outline=(244, 63, 94), width=2)
            draw.text((45, 165), "THE BIG TECHNICAL DEBATE:", fill=(244, 63, 94), font=font_badge)

            lines_cta = wrap_text(cta, font_hl, width - 90, draw)
            yc = 198
            for l in lines_cta[:5]:
                draw.text((45, yc), l, fill=(15, 23, 42), font=font_hl)
                yc += 36

            # Live Poll Simulation
            poll_y = 415
            poll_bbox = [(30, poll_y), (width - 30, poll_y + 125)]
            draw_card_with_shadow(draw, poll_bbox, radius=16, fill=(255, 255, 255), outline=(14, 165, 233), width=2)
            draw.text((45, poll_y + 14), "LIVE COMMUNITY POLL", fill=(14, 165, 233), font=font_badge)

            draw.rounded_rectangle([(45, poll_y + 38), (width - 45, poll_y + 70)], radius=8, fill=(241, 245, 249))
            draw.rounded_rectangle([(45, poll_y + 38), (int(45 + (width - 90) * 0.84), poll_y + 70)], radius=8, fill=(220, 252, 231))
            draw.text((55, poll_y + 44), "[A]  Game-Changer Paradigm (84%)", fill=(21, 128, 61), font=font_dock)

            draw.rounded_rectangle([(45, poll_y + 78), (width - 45, poll_y + 110)], radius=8, fill=(248, 250, 252))
            draw.rounded_rectangle([(45, poll_y + 78), (int(45 + (width - 90) * 0.16), poll_y + 110)], radius=8, fill=(241, 245, 249))
            draw.text((55, poll_y + 84), "[B]  Incremental Benchmark (16%)", fill=(100, 116, 139), font=font_dock)

            # Social Action Dock
            dock_y = 560
            dock_bbox = [(30, dock_y), (width - 30, 755)]
            draw_card_with_shadow(draw, dock_bbox, radius=18, fill=(255, 255, 255), outline=(226, 232, 240), width=2)

            actions = [
                ("[ + ]", "LIKE & SAVE REEL", (244, 63, 94)),
                ("[ > ]", "DROP YOUR COMMENT", (14, 165, 233)),
                ("[ ^ ]", "SHARE WITH ENGINEERS", (99, 102, 241)),
                ("[ * ]", "SUBSCRIBE TO @ERAOF_AI", (16, 185, 129))
            ]

            ya = dock_y + 20
            for icon, label, clr in actions:
                draw.rounded_rectangle([(45, ya), (width - 45, ya + 38)], radius=10, fill=(248, 250, 252), outline=(226, 232, 240), width=1)
                draw.text((58, ya + 8), f"{icon}  {label}", fill=clr, font=font_dock)
                ya += 46

        # -------------------------------------------------------------
        # 3. Clean Minimalist Frosted Footer (NO Audio Wave Bars)
        # -------------------------------------------------------------
        footer_box = [(20, height - 52), (width - 20, height - 16)]
        draw.rounded_rectangle([(footer_box[0][0] + 2, footer_box[0][1] + 3), (footer_box[1][0] + 2, footer_box[1][1] + 3)], radius=12, fill=(30, 20, 60))
        draw.rounded_rectangle(footer_box, radius=12, fill=(255, 255, 255), outline=(226, 232, 240), width=1)

        draw.text((32, height - 42), "ERA OF AI", fill=(15, 23, 42), font=font_brand_sub)
        draw.text((115, height - 42), "@Eraof_Ai  •  t.me/Eraof_Ai", fill=(71, 85, 105), font=font_small)
        curr_page = min(7, int(progress * 7) + 1)
        draw.text((width - 82, height - 43), f"0{curr_page} / 07", fill=(2, 132, 199), font=font_badge)

        # Send frame to FFmpeg writer
        writer.send(np.array(img))

    writer.close()

    # Mux video with synthesized audio using FFmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    if output_video_path.exists():
        output_video_path.unlink()

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(temp_raw_video),
        "-i", str(audio_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_video_path)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    if temp_raw_video.exists():
        temp_raw_video.unlink()

    return str(output_video_path)


async def synthesize_broadcast_video(directive: Dict[str, Any], output_filename: str) -> str:
    """End-to-end video synthesis pipeline: Script -> Neural Voiceover -> 7-Poster Motion Graphics -> MP4."""
    # Compose captivating, structured voiceover covering the 7-poster narrative
    hook_text = directive.get('hook_narration', '').strip()
    body_text = directive.get('body_narration', '').strip()
    cta_text = directive.get('call_to_action', '').strip()
    
    narration = f"{hook_text} Let's examine the technical architecture and verified benchmarks. {body_text} The official checkpoints and weights are live today. {cta_text}"
    
    audio_path = STAGING_DIR / f"voice_{output_filename}.mp3"
    video_path = STAGING_DIR / f"{output_filename}.mp4"

    # Step 1: Synthesize charismatic neural speech
    await synthesize_audio(narration, audio_path)

    # Step 2: Render 9:16 vertical motion video across 7 poster pages
    render_motion_video(directive, audio_path, video_path)

    return str(video_path)


if __name__ == "__main__":
    test_d = {
        "title": "Gemini 2.5 Flash: Autonomous SWE-bench Leap",
        "hook_narration": "Gemini 2.5 Flash just shattered SWE-bench coding benchmarks with a verified +14.2% gain!",
        "body_narration": "DeepMind confirmed real-time multimodal reasoning and native coding automation inside Gemini 2.5. Benchmark data shows significant gains across complex multi-file repo edits and automated tests.",
        "call_to_action": "Will multimodal test-time compute make all single-pass code models obsolete?"
    }
    out = asyncio.run(synthesize_broadcast_video(test_d, "test_7page_poster_reel"))
    print("7-Page Poster Video rendered successfully:", out, "Size:", os.path.getsize(out), "bytes")
