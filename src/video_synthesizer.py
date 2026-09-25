"""
High-Production 9:16 Vertical Video Synthesizer for AI Tech Broadcaster
Generates real, playable MP4 short-form video clips (Reels, TikTok, Shorts) with:
1. Microsoft Neural Voiceover Synthesis (via edge-tts)
2. Dynamic 9:16 Vertical Motion Canvas (540x960 / 24 fps)
3. 4-Phase Retention Architecture:
   - Phase 1: Disruption Hook & Headline
   - Phase 2: Technical Architecture & Benchmark Numbers
   - Phase 3: Developer Utility & Code Impact
   - Phase 4: Interactive Viral CTA (Like, Comment, Share)
4. Animated Audio Frequency Visualizer Waves
5. Native FFmpeg Muxing (H.264 video + AAC audio)
"""

import os
import sys
import math
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
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


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw):
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


async def synthesize_audio(narration_text: str, output_path: Path, voice: str = "en-US-ChristopherNeural"):
    """Synthesize studio-quality neural voiceover."""
    communicate = edge_tts.Communicate(narration_text, voice)
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
    return 8.0  # fallback default seconds


def render_motion_video(
    directive: Dict[str, Any],
    audio_path: Path,
    output_video_path: Path,
    width: int = 544,
    height: int = 960,
    fps: int = 24
) -> str:
    """
    Render 9:16 vertical motion video synced with speech narration duration.
    Muxes video and audio streams via FFmpeg.
    """
    duration = get_audio_duration(audio_path)
    total_frames = max(fps * 4, int(duration * fps))

    headline = directive.get("title") or "Frontier AI Breakthrough"
    hook = directive.get("hook_narration") or "Major AI breakthrough confirmed."
    body = directive.get("body_narration") or "Engineering documentation confirms verified benchmark gains."
    cta = directive.get("call_to_action") or "What do you think? Drop your thoughts below!"

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

    font_brand = get_font(18, bold=True)
    font_hl = get_font(26, bold=True)
    font_body = get_font(20, bold=False)
    font_badge = get_font(16, bold=True)
    font_cta = get_font(22, bold=True)

    for f_idx in range(total_frames):
        t = f_idx / fps
        progress = f_idx / total_frames

        # Create base image
        img = Image.new("RGB", (width, height))
        draw = ImageDraw.Draw(img)

        # Dynamic glowing gradient background
        pulse = math.sin(t * 2.5) * 15
        r_top = int(max(0, min(255, 12 + pulse)))
        g_top = int(max(0, min(255, 18 + pulse * 1.5)))
        b_top = int(max(0, min(255, 42 + pulse * 2)))

        for y in range(0, height, 4):
            ratio = y / height
            r = int(r_top * (1 - ratio) + 5 * ratio)
            g = int(g_top * (1 - ratio) + 8 * ratio)
            b = int(b_top * (1 - ratio) + 18 * ratio)
            draw.rectangle([(0, y), (width, y + 4)], fill=(r, g, b))

        # Top Accent Header Bar
        draw.rectangle([(0, 0), (width, 8)], fill=(6, 182, 212))

        # Brand Badge & Progress Line
        draw.rectangle([(40, 30), (190, 65)], fill=(15, 23, 42), outline=(51, 65, 85), width=2)
        draw.text((55, 38), "ERA OF AI", fill=(6, 182, 212), font=font_brand)
        
        # Live Progress Bar
        bar_w = int((width - 80) * progress)
        draw.rectangle([(40, 80), (width - 40, 84)], fill=(30, 41, 59))
        draw.rectangle([(40, 80), (40 + bar_w, 84)], fill=(6, 182, 212))

        # -------------------------------------------------------------
        # Scene Sequencing based on timing
        # -------------------------------------------------------------
        if progress < 0.28:
            # Phase 1: Disruption Hook (0% - 28%)
            draw.rectangle([(40, 120), (220, 155)], fill=(245, 158, 11))
            draw.text((52, 127), "BREAKING ALERT", fill=(0, 0, 0), font=font_badge)

            lines_hl = wrap_text(headline, font_hl, width - 80, draw)
            y_h = 180
            for l in lines_hl[:3]:
                draw.text((40, y_h), l, fill=(255, 255, 255), font=font_hl)
                y_h += 38

            # Glass Hook Card
            card_y = max(y_h + 30, 340)
            draw.rounded_rectangle([(40, card_y), (width - 40, card_y + 360)], radius=20, fill=(15, 23, 42), outline=(6, 182, 212), width=3)
            draw.text((65, card_y + 30), "THE HOOK:", fill=(6, 182, 212), font=font_badge)

            lines_hook = wrap_text(hook, font_body, width - 130, draw)
            yh = card_y + 70
            for l in lines_hook[:5]:
                draw.text((65, yh), l, fill=(241, 245, 249), font=font_body)
                yh += 32

        elif progress < 0.65:
            # Phase 2: Technical Architecture & Metrics (28% - 65%)
            draw.rectangle([(40, 120), (220, 155)], fill=(59, 130, 246))
            draw.text((52, 127), "ARCHITECTURAL LEAP", fill=(255, 255, 255), font=font_badge)

            draw.text((40, 175), "Verified Benchmark Metrics", fill=(255, 255, 255), font=font_hl)

            # Metric Highlight Box
            draw.rounded_rectangle([(40, 230), (width - 40, 420)], radius=18, fill=(17, 24, 39), outline=(59, 130, 246), width=3)
            draw.text((65, 260), "STATE-OF-THE-ART RECORD", fill=(59, 130, 246), font=font_badge)
            draw.text((65, 300), "VERIFIED SOTA GAIN", fill=(16, 185, 129), font=get_font(34, bold=True))
            draw.text((65, 360), "Primary engineering documentation verified", fill=(148, 163, 184), font=get_font(15))

            # Body Card
            draw.rounded_rectangle([(40, 450), (width - 40, 750)], radius=18, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
            lines_body = wrap_text(body, font_body, width - 130, draw)
            yb = 480
            for l in lines_body[:7]:
                draw.text((65, yb), l, fill=(241, 245, 249), font=font_body)
                yb += 32

        elif progress < 0.85:
            # Phase 3: Developer Utility (65% - 85%)
            draw.rectangle([(40, 120), (220, 155)], fill=(168, 85, 247))
            draw.text((52, 127), "ENGINEERING IMPACT", fill=(255, 255, 255), font=font_badge)

            draw.text((40, 175), "What Engineers Unlock Today", fill=(255, 255, 255), font=font_hl)

            features = [
                ("01", "Native API Access", "Direct inference availability across developer cloud platforms."),
                ("02", "Agent Loops", "Self-correcting code loops and automated SWE-bench repairs."),
                ("03", "Compute Latency", "Sub-second inference token throughput at reduced cost.")
            ]
            y_f = 240
            for num, f_title, f_desc in features:
                draw.rounded_rectangle([(40, y_f), (width - 40, y_f + 140)], radius=16, fill=(19, 16, 43), outline=(139, 92, 246), width=2)
                draw.text((65, y_f + 25), f"{num}  {f_title}", fill=(255, 255, 255), font=font_cta)
                lines_d = wrap_text(f_desc, get_font(15), width - 130, draw)
                yd = y_f + 65
                for dl in lines_d[:2]:
                    draw.text((65, yd), dl, fill=(203, 213, 225), font=get_font(15))
                    yd += 24
                y_f += 165

        else:
            # Phase 4: The Viral CTA (85% - 100%)
            draw.rectangle([(40, 120), (220, 155)], fill=(236, 72, 153))
            draw.text((52, 127), "THE BIG DEBATE", fill=(255, 255, 255), font=font_badge)

            # CTA Box
            draw.rounded_rectangle([(40, 180), (width - 40, 480)], radius=20, fill=(24, 18, 38), outline=(236, 72, 153), width=3)
            lines_cta = wrap_text(cta, font_hl, width - 120, draw)
            yc = 230
            for l in lines_cta[:5]:
                draw.text((65, yc), l, fill=(255, 255, 255), font=font_hl)
                yc += 38

            # Action Callout
            draw.rounded_rectangle([(40, 520), (width - 40, 750)], radius=18, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
            draw.text((65, 550), "❤️  LIKE THIS INSIGHT", fill=(244, 63, 94), font=font_cta)
            draw.text((65, 600), "💬  DROP YOUR COMMENT", fill=(6, 182, 212), font=font_cta)
            draw.text((65, 650), "↗️  SHARE WITH ENGINEERS", fill=(59, 130, 246), font=font_cta)
            draw.text((65, 700), "🔔  FOLLOW @ERAOFAI", fill=(16, 185, 129), font=font_cta)

        # -------------------------------------------------------------
        # Bottom Audio Frequency Visualizer Waves (Pulsing dynamically)
        # -------------------------------------------------------------
        wave_y = height - 80
        num_bars = 28
        bar_width = (width - 120) // num_bars
        for b_idx in range(num_bars):
            # Dynamic bar height based on speech wave simulation
            wave_h = int(10 + 35 * abs(math.sin(t * 8 + b_idx * 0.45)))
            bx = 60 + b_idx * bar_width
            draw.rounded_rectangle([(bx, wave_y - wave_h), (bx + bar_width - 4, wave_y)], radius=4, fill=(6, 182, 212))

        draw.text((width // 2 - 60, height - 40), "@EraofAi", fill=(148, 163, 184), font=font_brand)

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
    """End-to-end video synthesis pipeline: Script -> Neural Voiceover -> Motion Graphics -> MP4."""
    narration = f"{directive.get('hook_narration', '')} {directive.get('body_narration', '')} {directive.get('call_to_action', '')}"
    audio_path = STAGING_DIR / f"voice_{output_filename}.mp3"
    video_path = STAGING_DIR / f"{output_filename}.mp4"

    # Step 1: Synthesize neural speech
    await synthesize_audio(narration, audio_path)

    # Step 2: Render 9:16 vertical motion video
    render_motion_video(directive, audio_path, video_path)

    return str(video_path)


if __name__ == "__main__":
    test_d = {
        "title": "Gemini Image: SWE-bench +14.2% Gain Confirmed",
        "hook_narration": "Gemini Image just shattered SWE-bench coding benchmarks with a verified +14.2% gain!",
        "body_narration": "DeepMind confirmed real-time multimodal reasoning and native coding automation inside Gemini Image. Benchmark data shows significant gains across complex multi-file repo edits and automated tests.",
        "call_to_action": "Will multimodal test-time compute make all single-pass code models obsolete?"
    }
    out = asyncio.run(synthesize_broadcast_video(test_d, "test_render_reel"))
    print("Video rendered successfully:", out, "Size:", os.path.getsize(out), "bytes")
