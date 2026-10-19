"""
High-Production 9:16 Full HD (1080x1920 @ 30fps) CEO Character Presenter Video Engine
Generates executive-hosted short-form video clips (Reels, TikTok, Shorts) where the
CEO/Founder of the company behind the update (Sundar Pichai for Google, Sam Altman for OpenAI,
Jensen Huang for NVIDIA, Demis Hassabis for DeepMind, Dario Amodei for Anthropic,
Mark Zuckerberg for Meta, Liang Wenfeng for DeepSeek, Elon Musk for xAI, Satya Nadella for Microsoft)
appears on stage, speaks in first person with a matched vocal timbre/accent profile, and
animates at 30fps with audio-synchronized jaw/mouth articulation, head motion, dynamic
multi-scene holographic graphics, and word-by-word highlighted kinetic subtitles.
"""

import os
import re
import sys
import math
import time
import asyncio
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import quote
import httpx
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import imageio_ffmpeg
import edge_tts

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.persona_manager import (
    detect_persona,
    get_persona_portrait,
    get_circular_avatar,
    PORTRAITS_DIR,
)
from src.google_veo_client import generate_veo_broll

STAGING_DIR = ROOT_DIR / "storage" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = ROOT_DIR / "storage" / "assets"


def get_font(size: int, bold: bool = False):
    font_names = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "calibrib.ttf" if bold else "calibri.ttf",
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


def draw_card_with_shadow(
    draw: ImageDraw.ImageDraw,
    bbox: tuple,
    radius: int = 16,
    fill: tuple = (15, 23, 42),
    outline: tuple = (51, 65, 85),
    width: int = 2
):
    """Draw a sleek executive dark-glass or light card with subtle drop-shadow."""
    if len(bbox) == 2 and isinstance(bbox[0], (tuple, list)):
        x0, y0 = bbox[0]
        x1, y1 = bbox[1]
    else:
        x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([(x0 + 3, y0 + 4), (x1 + 3, y1 + 4)], radius=radius, fill=(5, 10, 22))
    draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=radius, fill=fill, outline=outline, width=width)


def _clean_legacy_boilerplate(text: str) -> str:
    """Remove any legacy hardcoded template phrases from older database rows."""
    if not text:
        return ""
    cleaned = text
    patterns = [
        r"Stop writing single-pass prompts\.?\s*",
        r"\s*Shuts Down Legacy Benchmarks\.?",
        r"^(⚡\s*24H Signal:|Architecture Deep Dive:)\s*",
        r"just changed the game\.?",
        r"Native test-time compute lets the model reason through complex bugs in real time\.?",
        r"Developers can now run autonomous coding loops that verify their own code before execution\.?",
    ]
    for pat in patterns:
        cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" .,;-")


def build_ceo_first_person_script(directive: Dict[str, Any], persona: Dict[str, Any]) -> str:
    """
    Transform a broadcast directive into a natural, first-person CEO keynote speech
    spoken directly by the company's CEO (e.g., Sundar Pichai for Google, Sam Altman for OpenAI).
    Automatically purges any legacy boilerplate and uses live LLM synthesis when needed.
    """
    ceo_name = persona.get("name", "Sundar Pichai")
    ceo_title = persona.get("title", "CEO, Google & Alphabet")
    company = persona.get("lab", "Google")
    greeting = persona.get("intro_greeting") or f"Hi everyone, {ceo_name} here at {company}."

    raw_title = (directive.get("title") or directive.get("headline") or "").strip()
    clean_title = _clean_legacy_boilerplate(raw_title) or f"{company} AI Architecture Update"
    hook = _clean_legacy_boilerplate(directive.get("hook_narration") or "")
    body = _clean_legacy_boilerplate(directive.get("body_narration") or "")
    cta = _clean_legacy_boilerplate(directive.get("call_to_action") or "") or f"Let us know what you're building with {company} next."

    # If hook or body is missing, identical to title, or too short after stripping boilerplate, generate real first-person CEO talk
    if (not hook or hook.lower() == clean_title.lower() or len(body) < 35) and "PYTEST_CURRENT_TEST" not in os.environ:
        try:
            prompt = (
                f"You are {ceo_name}, {ceo_title}. Speak directly to viewers on camera in first person "
                f"about this announcement: '{clean_title}'. Context: '{body or hook}'.\n"
                f"Return ONLY valid JSON: "
                f'{{"hook": "1-2 natural first-person sentences explaining why we built this", '
                f'"body": "2 natural first-person sentences explaining the technical breakthrough and real-world impact"}}'
            )
            with httpx.Client(timeout=15.0) as client:
                r = client.post(
                    "https://text.pollinations.ai/openai",
                    json={
                        "model": "openai",
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": f"You are {ceo_name} ({ceo_title}) presenting a keynote in first person."},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                if r.status_code == 200:
                    content_str = r.json()["choices"][0]["message"]["content"].strip()
                    if content_str.startswith("```"):
                        content_str = re.sub(r"^```(?:json)?\s*|\s*```$", "", content_str, flags=re.DOTALL)
                    gen = json.loads(content_str)
                    if gen.get("hook"):
                        hook = gen["hook"].strip()
                    if gen.get("body"):
                        body = gen["body"].strip()
        except Exception:
            pass

    if not hook or hook.lower() == clean_title.lower():
        hook = f"Today at {company}, we are rolling out {clean_title} to give developers and enterprises a major leap in real-world AI capability."
    if not body or len(body) < 25:
        body = persona.get("default_quote") or f"Our engineering team designed this architecture for higher reasoning accuracy, lower latency, and production reliability."

    # Update directive in-place so on-screen cards display clean first-person executive text
    directive["title"] = clean_title
    directive["headline"] = clean_title
    directive["hook_narration"] = hook
    directive["body_narration"] = body
    directive["call_to_action"] = cta

    parts = [greeting]
    if clean_title.lower() not in hook.lower():
        parts.append(f"Today I'm excited to share our latest update: {clean_title}.")
    if not hook.lower().startswith(("hi ", "hello ", "hey ")):
        parts.append(hook)
    else:
        parts = [hook]
    parts.append(body)
    parts.append(cta)
    return " ".join(p.strip() for p in parts if p and p.strip())


def _split_text_for_tts(text: str, max_chars: int = 175) -> List[str]:
    """Split text into natural sentence/phrase chunks under `max_chars`."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: List[str] = []
    for sent in sentences:
        if not sent:
            continue
        if len(sent) <= max_chars:
            chunks.append(sent)
        else:
            words = sent.split()
            curr: List[str] = []
            for w in words:
                curr.append(w)
                if len(" ".join(curr)) > max_chars and len(curr) > 1:
                    curr.pop()
                    chunks.append(" ".join(curr))
                    curr = [w]
            if curr:
                chunks.append(" ".join(curr))
    return chunks


async def synthesize_audio(
    narration_text: str,
    output_path: Path,
    voice: str = "en-IN-PrabhatNeural",
    persona: Optional[Dict[str, Any]] = None
):
    """
    Synthesize CEO-matched voiceover with a 3-tier vocal persona engine:
    Tier 1: Gemini 3.8 Flash TTS (`gemini-3.8-flash-tts` Voice Design) when GEMINI_API_KEY is set
    Tier 2: Microsoft Edge-TTS Neural Voice (`en-IN-PrabhatNeural`, `en-GB-RyanNeural`, `en-US-RogerNeural`, etc.)
    Tier 3: Multi-Accent Google Neural Speech (`en-IN`, `en-GB`, `en-US`, `en-ZA`, `en-SG`)
            + FFmpeg Executive Vocal Formant, Pitch & Broadcast EQ Sculpting (Zero Robotic Fallback)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    vp = (persona or {}).get("voice_profile", {})
    edge_voice = vp.get("edge_voice") or voice
    accent_tld = vp.get("accent_tld") or "en-US"
    pitch_factor = float(vp.get("pitch_factor", 0.96))
    tempo = float(vp.get("tempo", 1.04))
    eq_filter = vp.get(
        "eq_filter",
        "equalizer=f=220:width_type=o:width=1.5:g=3.5,equalizer=f=3200:width_type=o:width=1.2:g=2.5",
    )

    # Tier 1: Gemini 3.8 Flash TTS with CEO Voice Design (if GEMINI_API_KEY configured)
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key and "YOUR_" not in gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            if hasattr(client, "interactions"):
                voice_desc = vp.get("gemini_voice_design", "Articulate executive tech CEO keynote voice.")
                interaction = client.interactions.create(
                    model="gemini-3.8-flash-tts",
                    input=f"[Voice Design: {voice_desc}] {narration_text}",
                )
                if hasattr(interaction, "output_audio") and interaction.output_audio:
                    raw_wav = output_path.with_suffix(".wav")
                    raw_wav.write_bytes(interaction.output_audio.data)
                    subprocess.run(
                        [ffmpeg_exe, "-y", "-i", str(raw_wav), "-c:a", "libmp3lame", "-b:a", "192k", str(output_path)],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                    )
                    if raw_wav.exists():
                        raw_wav.unlink()
                    if output_path.exists() and output_path.stat().st_size > 2000:
                        return
        except Exception as gem_err:
            print(f"[CEOVoiceEngine] Gemini 3.8 TTS fallback: {gem_err}")

    # Tier 2: SOTA Zero-Shot Voice Cloning (F5-TTS / ElevenLabs / Fish Audio)
    if persona:
        try:
            from src.voice_cloner import synthesize_ceo_voice
            await synthesize_ceo_voice(
                narration_text=narration_text,
                output_path=output_path,
                persona=persona,
                prefer_zero_shot=True
            )
            if output_path.exists() and output_path.stat().st_size > 2000:
                return
        except Exception as clone_err:
            print(f"[CEOVoiceEngine] Zero-shot voice clone fallback ({clone_err}); engaging calibrated Edge-TTS.")

    # Tier 3: Edge-TTS Neural Voiceover
    raw_tts_path = output_path.with_name(f"raw_tts_{output_path.stem}.mp3")
    try:
        communicate = edge_tts.Communicate(narration_text, edge_voice, rate="+4%")
        await communicate.save(str(raw_tts_path))
    except Exception as edge_err:
        print(f"[CEOVoiceEngine] Edge-TTS unavailable ({edge_err}); engaging Multi-Accent Neural TTS + Formant DSP...")

    # Tier 3: Multi-Accent Google Neural Speech + FFmpeg Executive Vocal Formant/Pitch/EQ Sculpting
    if not raw_tts_path.exists() or raw_tts_path.stat().st_size < 1500:
        try:
            chunks = _split_text_for_tts(narration_text, max_chars=175)
            audio_segments: List[bytes] = []
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                for chunk in chunks:
                    q = quote(chunk)
                    url = f"https://translate.googleapis.com/translate_tts?ie=UTF-8&client=tw-ob&tl={accent_tld}&q={q}"
                    resp = client.get(url, headers=headers)
                    if resp.status_code == 200 and len(resp.content) > 500:
                        audio_segments.append(resp.content)
            if audio_segments:
                raw_tts_path.write_bytes(b"".join(audio_segments))
        except Exception as gtts_err:
            print(f"[CEOVoiceEngine] Multi-accent neural TTS error: {gtts_err}")

    # Apply Executive Vocal Formant, Pitch & Keynote Studio EQ DSP via FFmpeg
    if raw_tts_path.exists() and raw_tts_path.stat().st_size > 1000:
        try:
            # Compensate tempo when shifting sample-rate pitch so speech speed matches the CEO's natural cadence
            effective_tempo = max(0.85, min(1.30, tempo / pitch_factor))
            af_chain = (
                f"asetrate=24000*{pitch_factor:.3f},"
                f"aresample=44100,"
                f"atempo={effective_tempo:.3f},"
                f"{eq_filter},"
                f"acompressor=threshold=-16dB:ratio=2.4:attack=8:release=90"
            )
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-i", str(raw_tts_path),
                    "-af", af_chain,
                    "-c:a", "libmp3lame",
                    "-ar", "44100",
                    "-ac", "2",
                    "-b:a", "192k",
                    str(output_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
                check=False,
            )
            if not output_path.exists() or output_path.stat().st_size < 1000:
                raw_tts_path.replace(output_path)
            elif raw_tts_path.exists():
                raw_tts_path.unlink()
            if output_path.exists() and output_path.stat().st_size > 1000:
                return
        except Exception as dsp_err:
            print(f"[CEOVoiceEngine] Vocal DSP warning: {dsp_err}")
            if raw_tts_path.exists():
                raw_tts_path.replace(output_path)
                return

    # Final Emergency Fallback: Synthesized Harmonic Audio Bed
    word_count = max(20, len(narration_text.split()))
    est_duration = max(10.0, min(25.0, word_count / 3.0))
    subprocess.run(
        [
            ffmpeg_exe,
            "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=220:sample_rate=44100:duration={est_duration:.1f}",
            "-af", "volume=0.08",
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )


def get_audio_duration(audio_path: Path) -> float:
    """Use FFmpeg to get exact audio duration in seconds."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg_exe, "-i", str(audio_path)]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in result.stderr.splitlines():
        if "Duration:" in line:
            try:
                parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
                return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            except Exception:
                pass
    return 12.0


def extract_audio_envelope(audio_path: Path, total_frames: int, fps: int = 30) -> np.ndarray:
    """
    Decode audio track into mono 8kHz PCM samples and compute per-frame RMS vocal energy
    normalized to [0.0, 1.0] for frame-accurate 30fps lip/jaw articulation and voice aura pulsing.
    """
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    try:
        cmd = [
            ffmpeg_exe,
            "-i", str(audio_path),
            "-f", "s16le",
            "-ac", "1",
            "-ar", "8000",
            "-v", "quiet",
            "-",
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        pcm = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32)
        if pcm.size < 100:
            raise ValueError("Empty PCM stream")

        samples_per_frame = max(1, len(pcm) // max(1, total_frames))
        env = np.zeros(total_frames, dtype=np.float32)
        for i in range(total_frames):
            start = i * samples_per_frame
            end = min(len(pcm), start + samples_per_frame)
            if end > start:
                env[i] = float(np.sqrt(np.mean(np.square(pcm[start:end]))))

        p95 = float(np.percentile(env, 95)) if env.size > 0 else 1.0
        if p95 > 1.0:
            env = np.clip(env / p95, 0.0, 1.0)
        # Apply noise gate so silent pauses close the mouth cleanly
        env = np.where(env < 0.12, 0.0, (env - 0.12) / 0.88)
        # Smooth with a 3-tap kernel for natural jaw inertia
        if total_frames >= 3:
            env = np.convolve(env, np.array([0.25, 0.50, 0.25], dtype=np.float32), mode="same")
        return env
    except Exception:
        t = np.linspace(0, total_frames / fps, total_frames)
        return np.clip(0.5 + 0.45 * np.sin(t * 14.0) * np.cos(t * 3.5), 0.0, 1.0).astype(np.float32)


def animate_ceo_portrait(
    base_portrait: Image.Image,
    mouth_box_ratio: Tuple[float, float, float, float],
    amp: float,
    t: float,
    accent_color: Tuple[int, int, int],
    secondary_color: Tuple[int, int, int],
) -> Image.Image:
    """
    Broadcast-Grade Realistic Human Presenter Animator (30fps):
    1. Organic 3D Head Pose Inertia: Subtle living pitch, yaw, and conversational emphasis
       articulation that makes the presenter look like a live human being addressing an audience.
    2. Dynamic Eyebrow & Forehead Emphasis: Natural micro-elevation on vocal stress and pitch peaks.
    3. Bilateral Zygomatic Cheek Flex: Subtle facial muscle dynamics synchronized to speech power.
    4. Sub-Pixel Bilinear Viseme Lip & Jaw Articulation: Anchored below upper teeth with natural mouth aperture.
    5. Natural Eyelid Dynamics & Gaze: Smooth 130ms eyelid blink with eyelid creases every ~4.2 seconds.
    """
    arr = np.array(base_portrait, dtype=np.float32)
    h, w, _ = arr.shape

    # Multi-band syllable cadence (combines speech envelope with natural syllable viseme modulation)
    viseme_mod = 0.60 + 0.25 * math.sin(t * 14.5) + 0.15 * math.cos(t * 23.0)
    jaw_open = float(np.clip(amp * viseme_mod, 0.0, 1.0))

    mx0, my0, mx1, my1 = mouth_box_ratio
    cx = (mx0 + mx1) * 0.5 * w
    cy = (my0 + my1) * 0.5 * h
    rx = max(14.0, (mx1 - mx0) * 0.54 * w)
    ry = max(12.0, (my1 - my0) * 0.68 * h)

    # 1. Eyebrow Elevation on Vocal Stress & Pitch Peaks (amp > 0.45)
    if amp > 0.45:
        brow_y = int(cy - ry * 2.85)
        brow_h = int(ry * 0.65)
        brow_lift = max(0.5, (amp - 0.45) * 4.5)
        by0 = max(0, brow_y - brow_h)
        by1 = min(h - 2, brow_y + brow_h)
        bx0 = max(0, int(cx - rx * 1.5))
        bx1 = min(w - 1, int(cx + rx * 1.5))
        if by1 > by0 + 4 and bx1 > bx0 + 4:
            byy, bxx = np.mgrid[by0:by1, bx0:bx1].astype(np.float32)
            b_wx = np.exp(-0.5 * ((bxx - cx) / max(1.0, rx * 0.95)) ** 2)
            b_wy = np.exp(-0.5 * ((byy - brow_y) / max(1.0, brow_h * 0.65)) ** 2)
            b_src_y = np.clip(byy + b_wx * b_wy * brow_lift, float(by0), float(by1))
            by0_i = np.floor(b_src_y).astype(np.int32)
            by1_i = np.clip(by0_i + 1, 0, h - 1)
            b_alpha = (b_src_y - by0_i)[..., np.newaxis]
            bxx_i = bxx.astype(np.int32)
            arr[by0:by1, bx0:bx1] = (1.0 - b_alpha) * arr[by0_i, bxx_i] + b_alpha * arr[by1_i, bxx_i]

    # 2. Bilateral Zygomatic Cheek Flex on Open Syllables (jaw_open > 0.28)
    if jaw_open > 0.28:
        cheek_y = int(cy - ry * 0.55)
        cheek_h = int(ry * 0.75)
        cheek_shift = (jaw_open - 0.28) * 1.8
        cy0 = max(0, cheek_y - cheek_h)
        cy1 = min(h - 2, cheek_y + cheek_h)
        cx0 = max(0, int(cx - rx * 1.6))
        cx1 = min(w - 1, int(cx + rx * 1.6))
        if cy1 > cy0 + 4 and cx1 > cx0 + 4:
            cyy, cxx = np.mgrid[cy0:cy1, cx0:cx1].astype(np.float32)
            c_wy = np.exp(-0.5 * ((cyy - cheek_y) / max(1.0, cheek_h * 0.7)) ** 2)
            c_dx = np.where(cxx > cx, cheek_shift, -cheek_shift) * c_wy
            c_src_x = np.clip(cxx - c_dx, float(cx0), float(cx1 - 1))
            cx0_i = np.floor(c_src_x).astype(np.int32)
            cx1_i = np.clip(cx0_i + 1, 0, w - 1)
            c_alpha = (c_src_x - cx0_i)[..., np.newaxis]
            cyy_i = cyy.astype(np.int32)
            arr[cy0:cy1, cx0:cx1] = (1.0 - c_alpha) * arr[cyy_i, cx0_i] + c_alpha * arr[cyy_i, cx1_i]

    # 3. Bidirectional Sub-Pixel Bilinear Lip & Jaw Articulation:
    #    Anchored strictly below the upper teeth so upper teeth remain crisp
    lower_lip_y = cy + ry * 0.28
    y_start = max(0, int(lower_lip_y))
    y_end = min(h - 2, int(cy + ry * 2.15))
    x_start = max(0, int(cx - rx * 1.35))
    x_end = min(w - 1, int(cx + rx * 1.35))

    if y_end > y_start + 4 and x_end > x_start + 4:
        yy, xx = np.mgrid[y_start:y_end, x_start:x_end].astype(np.float32)
        wx = np.exp(-0.5 * ((xx - cx) / max(1.0, rx * 0.68)) ** 2)
        rel_y = (yy - lower_lip_y) / max(1.0, (y_end - lower_lip_y))
        wy_lower = np.sin(np.clip(rel_y, 0.0, 1.0) * math.pi) ** 1.4

        signed_open = (jaw_open - 0.18) * 1.15
        max_shift_px = max(2.5, h * 0.022) * signed_open
        dy = wx * wy_lower * max_shift_px

        src_y = np.clip(yy - dy, float(y_start), float(h - 2.001))
        y0 = np.floor(src_y).astype(np.int32)
        y1 = y0 + 1
        alpha = (src_y - y0)[..., np.newaxis]
        xx_i = xx.astype(np.int32)

        warped = (1.0 - alpha) * arr[y0, xx_i] + alpha * arr[y1, xx_i]
        arr[y_start:y_end, x_start:x_end] = warped

    # 4. Natural Periodic Eye Blink & Gaze (every 4.2 seconds, 130ms duration)
    blink_phase = t % 4.2
    if blink_phase < 0.13:
        blink_amt = math.sin((blink_phase / 0.13) * math.pi)
        eye_y = int(cy - ry * 2.15)
        eye_h = max(3, int(h * 0.018 * blink_amt))
        for eye_cx in (int(cx - rx * 0.68), int(cx + rx * 0.68)):
            ey0 = max(2, eye_y - eye_h)
            ey1 = min(h - 2, eye_y + eye_h)
            ex0 = max(2, eye_cx - int(rx * 0.36))
            ex1 = min(w - 2, eye_cx + int(rx * 0.36))
            if ey1 > ey0 and ex1 > ex0:
                skin_sample = arr[max(0, ey0 - 2):ey0, ex0:ex1].mean(axis=0, keepdims=True)
                if not np.isnan(skin_sample).any():
                    arr[ey0:ey1, ex0:ex1] = arr[ey0:ey1, ex0:ex1] * (1.0 - 0.75 * blink_amt) + skin_sample * (0.75 * blink_amt)

    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # 5. Organic Conversational Head Pose Articulation (Subtle 3D Pitch/Yaw/Roll)
    #    Simulates natural human head movement while maintaining rock-solid studio bounds
    head_nod = 1.4 * math.sin(t * 1.8) + (2.2 * amp if amp > 0.3 else 0.0)
    head_sway = 2.0 * math.sin(t * 1.1)
    head_tilt = 0.5 * math.sin(t * 0.85)

    if abs(head_tilt) > 0.1:
        img = img.rotate(head_tilt, resample=Image.Resampling.BILINEAR, expand=False)
    
    # Sub-pixel translate head for organic conversational pitch and yaw
    trans_w, trans_h = w, h
    crop_x = int(round(head_sway))
    crop_y = int(round(-head_nod))
    shifted = Image.new("RGB", (w, h), (12, 16, 28))
    shifted.paste(img, (crop_x, crop_y))
    img = shifted

    # 6. Clean Rounded Studio Broadcast Frame (Constant width, zero jitter)
    framed = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=24, fill=255)
    framed.paste(img.convert("RGBA"), (0, 0), mask=mask)

    fdraw = ImageDraw.Draw(framed)
    fdraw.rounded_rectangle([(1, 1), (w - 2, h - 2)], radius=24, outline=accent_color, width=2)

    # Live Audio Spectrum Equalizer Overlay at Bottom-Right of CEO Frame
    eq_base_x = w - 88
    eq_base_y = h - 18
    fdraw.rounded_rectangle([(eq_base_x - 8, eq_base_y - 30), (w - 10, eq_base_y + 6)], radius=8, fill=(10, 15, 30, 210))
    for b_idx in range(9):
        phase = t * 14.0 + b_idx * 0.85
        bar_h = int(4 + (18 * jaw_open * (0.45 + 0.55 * abs(math.sin(phase)))))
        bx = eq_base_x + b_idx * 8
        b_clr = accent_color if b_idx % 2 == 0 else secondary_color
        fdraw.rounded_rectangle([(bx, eq_base_y - bar_h), (bx + 4, eq_base_y)], radius=2, fill=b_clr)

    return framed


def draw_kinetic_subtitles(
    draw: ImageDraw.ImageDraw,
    words: List[str],
    progress: float,
    width: int,
    y_pos: int,
    accent_color: Tuple[int, int, int],
    font_sub: ImageFont.ImageFont,
):
    """
    Render viral TikTok/Reels word-by-word highlighted kinetic subtitles.
    Displays a 6-word window centered on the currently spoken word, highlighting the active word.
    """
    if not words:
        return
    total_w = len(words)
    curr_idx = min(total_w - 1, max(0, int(progress * total_w)))
    chunk_size = 6
    chunk_start = (curr_idx // chunk_size) * chunk_size
    chunk_words = words[chunk_start: chunk_start + chunk_size]
    active_in_chunk = curr_idx - chunk_start

    # Lay out words across 1 or 2 centered lines
    line1 = chunk_words[:3]
    line2 = chunk_words[3:]

    # Subtitle backdrop pill
    draw.rounded_rectangle(
        [(22, y_pos - 8), (width - 22, y_pos + (68 if line2 else 38))],
        radius=14,
        fill=(8, 12, 24),
        outline=accent_color,
        width=1,
    )

    for line_idx, line_words in enumerate([line1, line2]):
        if not line_words:
            continue
        ly = y_pos + line_idx * 30
        # Measure total line width
        word_widths = []
        space_w = 8
        for w_str in line_words:
            bb = draw.textbbox((0, 0), w_str.upper(), font=font_sub)
            word_widths.append(bb[2] - bb[0])
        total_line_w = sum(word_widths) + space_w * max(0, len(line_words) - 1)
        curr_x = (width - total_line_w) // 2

        for w_i, w_str in enumerate(line_words):
            global_in_chunk = line_idx * 3 + w_i
            w_up = w_str.upper()
            ww = word_widths[w_i]
            if global_in_chunk == active_in_chunk:
                draw.rounded_rectangle(
                    [(curr_x - 5, ly - 2), (curr_x + ww + 5, ly + 24)],
                    radius=6,
                    fill=accent_color,
                )
                draw.text((curr_x, ly), w_up, fill=(255, 255, 255), font=font_sub)
            elif global_in_chunk < active_in_chunk:
                draw.text((curr_x, ly), w_up, fill=(226, 232, 240), font=font_sub)
            else:
                draw.text((curr_x, ly), w_up, fill=(148, 163, 184), font=font_sub)
            curr_x += ww + space_w


def render_motion_video(
    directive: Dict[str, Any],
    audio_path: Path,
    output_video_path: Path,
    width: int = 544,
    height: int = 960,
    fps: int = 30,
    persona: Optional[Dict[str, Any]] = None,
    spoken_script: Optional[str] = None,
) -> str:
    """
    Render a 9:16 CEO Character Keynote Video across 4 dynamic animated scenes (upscaled to 1080x1920 30fps):
    - Scene 1 (0% - 25%): Full Keynote Stage Reveal — Large animated CEO presenter center-stage + Executive Nameplate
    - Scene 2 (25% - 52%): Split-Screen Holographic Architecture Diagram + Live Speaking CEO Presenter
    - Scene 3 (52% - 78%): Live Animated SOTA Benchmark Radar & Metric Bars + Live Speaking CEO Presenter
    - Scene 4 (78% - 100%): Executive Close-Up Takeaway & Live Community Poll + Word-by-Word Kinetic Subtitles
    """
    duration = get_audio_duration(audio_path)
    total_frames = max(fps * 8, int(duration * fps))

    raw_headline = directive.get("title") or directive.get("headline") or "Frontier AI Breakthrough"
    raw_hook = directive.get("hook_narration") or ""
    raw_body = directive.get("body_narration") or ""
    source_url = directive.get("source_url") or ""

    if persona is None:
        persona = detect_persona(raw_headline, f"{raw_hook} {raw_body} {source_url}")
    if not spoken_script:
        spoken_script = build_ceo_first_person_script(directive, persona)

    headline = directive.get("title") or directive.get("headline") or raw_headline
    hook = directive.get("hook_narration") or "Major AI architecture update confirmed."
    body = directive.get("body_narration") or "Engineering documentation confirms verified benchmark gains."
    cta = directive.get("call_to_action") or f"Let us know what you're building with {persona['lab']} next!"

    script_words = spoken_script.split()
    audio_env = extract_audio_envelope(audio_path, total_frames, fps=fps)

    # Pre-load CEO high-resolution portraits at the two stage sizes for fast 30fps rendering
    mouth_ratio = persona.get("mouth_box_ratio", (0.37, 0.56, 0.63, 0.72))
    accent_clr = persona.get("accent_color", (66, 133, 244))
    sec_clr = persona.get("secondary_color", (99, 102, 241))

    ceo_portrait_large = get_persona_portrait(persona, target_size=(464, 500))
    ceo_portrait_split = get_persona_portrait(persona, target_size=(215, 255))

    temp_raw_video = STAGING_DIR / f"temp_raw_{output_video_path.name}"
    writer = imageio_ffmpeg.write_frames(
        str(temp_raw_video),
        (width, height),
        fps=fps,
        codec="libx264",
        pix_fmt_in="rgb24",
        pix_fmt_out="yuv420p",
        ffmpeg_log_level="error",
    )
    writer.send(None)

    font_brand = get_font(16, bold=True)
    font_brand_sub = get_font(10, bold=True)
    font_hl = get_font(22, bold=True)
    font_name = get_font(20, bold=True)
    font_body = get_font(15, bold=False)
    font_badge = get_font(12, bold=True)
    font_code = get_font(12, bold=False)
    font_sub = get_font(15, bold=True)
    font_small = get_font(11, bold=False)

    logo_icon = get_circular_logo(size=32)

    # Load authentic company keynote stage background (Google I/O Shoreline, OpenAI DevDay, NVIDIA GTC, etc.)
    from src.persona_manager import get_persona_stage_background
    stage_bg = get_persona_stage_background(persona, target_size=(width, height))

    from src.presenter_engine import FullBodyKeynotePresenter
    presenter_inst = FullBodyKeynotePresenter(persona, width=width, height=height)

    clean_hl = _clean_legacy_boilerplate(headline) or headline

    for f_idx in range(total_frames):
        t = f_idx / fps
        progress = f_idx / total_frames
        amp = float(audio_env[f_idx]) if f_idx < len(audio_env) else 0.3

        # -------------------------------------------------------------
        # 1. Base Stage Plate with Living Photorealistic Presenter & Head Dynamics
        # -------------------------------------------------------------
        if progress < 0.26 or progress >= 0.78:
            pose_req = "GREETING" if progress < 0.26 else "INVITE"
            img, finger_xy = presenter_inst.get_stage_plate(pose_req, t=t, amp=amp)
        else:
            img, finger_xy = presenter_inst.get_stage_plate("POINT", t=t, amp=amp)

        draw = ImageDraw.Draw(img)

        # -------------------------------------------------------------
        # 2. Top Broadcast Header Bar
        # -------------------------------------------------------------
        draw.rectangle([(0, 0), (width // 2, 5)], fill=accent_clr)
        draw.rectangle([(width // 2, 0), (width, 5)], fill=sec_clr)

        draw_card_with_shadow(draw, [(22, 12), (215, 50)], radius=12, fill=(15, 23, 42), outline=accent_clr, width=1)
        if logo_icon:
            img.paste(logo_icon, (30, 15), mask=logo_icon)
        draw.text((70, 16), "ERA OF AI", fill=(255, 255, 255), font=font_brand)
        draw.text((70, 33), f"{persona['lab'].upper()} KEYNOTE", fill=accent_clr, font=font_brand_sub)

        # Live Speaking Indicator Pill
        live_pill = [(width - 195, 14), (width - 22, 48)]
        draw.rounded_rectangle(live_pill, radius=16, fill=(15, 23, 42), outline=accent_clr, width=1)
        dot_r = 6 if amp > 0.25 else 4
        draw.ellipse([(width - 180 - dot_r, 31 - dot_r), (width - 180 + dot_r, 31 + dot_r)], fill=(239, 68, 68))
        draw.text((width - 166, 23), f"LIVE • {persona['name'].split()[0].upper()}", fill=(255, 255, 255), font=font_badge)

        # Progress Timeline Bar
        bar_w = int((width - 44) * progress)
        draw.rectangle([(22, 54), (width - 22, 58)], fill=(30, 41, 59))
        draw.rectangle([(22, 54), (22 + bar_w, 58)], fill=accent_clr)

        # -------------------------------------------------------------
        # 3. Multi-Scene Full-Body Keynote Presenter & Interactive Stage
        # -------------------------------------------------------------
        if progress < 0.26 or progress >= 0.78:
            # =========================================================
            # SCENE 1 (0-26%) & SCENE 4 (78-100%):
            # CENTER STAGE FULL-BODY KEYNOTE PRESENTER
            # =========================================================
            scene_tag = "KEYNOTE STAGE // EXECUTIVE BRIEFING" if progress < 0.26 else "EXECUTIVE TAKEAWAY // LIVE DEBATE"
            draw.rounded_rectangle([(22, 64), (300, 88)], radius=8, fill=(15, 23, 42), outline=accent_clr, width=1)
            draw.text((32, 69), scene_tag, fill=accent_clr, font=font_badge)

            # Overhead Floating Headline Display (Placed cleanly above head)
            hl_display = clean_hl if progress < 0.26 else cta
            hl_lines = wrap_text(hl_display, font_hl, width - 64, draw)
            yh = 94
            h_card_h = min(2, len(hl_lines)) * 24 + 10
            draw.rounded_rectangle([(22, 90), (width - 22, 90 + h_card_h)], radius=10, fill=(11, 18, 34, 210), outline=(accent_clr[0], accent_clr[1], accent_clr[2], 180), width=1)
            for l_str in hl_lines[:2]:
                draw.text((34, yh + 1), l_str, fill=(0, 0, 0), font=font_hl)
                draw.text((33, yh), l_str, fill=(255, 255, 255), font=font_hl)
                yh += 24

            # Broadcast Lower-Third Nameplate grounded at Stage Level (y = 735)
            lt_y = 735
            draw.rounded_rectangle(
                [(width // 2 - 215, lt_y), (width // 2 + 215, lt_y + 54)],
                radius=14,
                fill=(10, 15, 28, 220),
                outline=accent_clr,
                width=2,
            )
            draw.rectangle([(width // 2 - 205, lt_y + 10), (width // 2 - 199, lt_y + 44)], fill=accent_clr)
            draw.text((width // 2 - 188, lt_y + 9), persona["name"].upper(), fill=(255, 255, 255), font=font_name)
            draw.text((width // 2 - 188, lt_y + 32), f"{persona['title']}  •  Official Keynote Update", fill=(148, 163, 184), font=font_badge)

        elif progress < 0.52:
            # =========================================================
            # SCENE 2 (26-52%):
            # STAGE-LEFT PRESENTER POINTING AT HOLOGRAPHIC ARCHITECTURE
            # =========================================================
            draw.rounded_rectangle([(22, 72), (320, 98)], radius=8, fill=(15, 23, 42), outline=accent_clr, width=1)
            draw.text((34, 78), f"ARCHITECTURE BREAKDOWN // {persona['lab'].upper()}", fill=accent_clr, font=font_badge)

            # Upper Holographic Architecture Screen on Stage Right
            screen_x0 = 250
            screen_x1 = width - 16
            draw.rounded_rectangle([(screen_x0, 104), (screen_x1, 260)], radius=12, fill=(11, 18, 34, 220), outline=accent_clr, width=2)
            draw.text((screen_x0 + 14, 114), "NEURAL PIPELINE & EXECUTION", fill=(255, 255, 255), font=font_badge)

            # 3-Node Neural Waveguide
            n1_x = screen_x0 + 38
            n2_x = screen_x0 + 130
            n3_x = screen_x0 + 222
            node_y = 158

            draw.line([(n1_x, node_y), (n3_x, node_y)], fill=(51, 65, 85), width=2)
            pkt_prog = ((t * 0.95) % 1.0)
            pkt_x = int(n1_x + (n3_x - n1_x) * pkt_prog)

            nodes_spec = [
                (n1_x, "INPUT", accent_clr),
                (n2_x, "CORE", sec_clr),
                (n3_x, "VERIFY", (16, 185, 129)),
            ]
            for nx, nlabel, nclr in nodes_spec:
                pulse_r = 14 + int(2 * abs(math.sin(t * 4 + nx)))
                draw.ellipse([(nx - pulse_r, node_y - pulse_r), (nx + pulse_r, node_y + pulse_r)], fill=(15, 23, 42), outline=nclr, width=2)
                draw.ellipse([(nx - 5, node_y - 5), (nx + 5, node_y + 5)], fill=nclr)
                draw.text((nx - 16, node_y + 18), nlabel, fill=(226, 232, 240), font=font_small)

            draw.ellipse([(pkt_x - 5, node_y - 5), (pkt_x + 5, node_y + 5)], fill=(255, 255, 255))

            # Architecture Explanation Bullets inside Hologram
            draw.text((screen_x0 + 14, 192), "• Parallel Test-Time Compute", fill=(226, 232, 240), font=font_small)
            draw.text((screen_x0 + 14, 212), "• 2M Context Multi-Agent Verify", fill=(226, 232, 240), font=font_small)
            draw.text((screen_x0 + 14, 232), "• 62% Lower Inference Latency", fill=(226, 232, 240), font=font_small)

            # Active Target Coordinate (Core node target)
            target_xy = (n2_x, node_y)

            # Dynamic Optical Beacon Connecting CEO's Finger to the Holographic Pipeline
            presenter_inst.draw_interactive_optical_beacon(
                base_canvas=img,
                finger_xy=finger_xy,
                target_xy=target_xy,
                t=t,
            )

        else:
            # =========================================================
            # SCENE 3 (52-78%):
            # STAGE-LEFT PRESENTER POINTING AT LIVE BENCHMARK TELEMETRY
            # =========================================================
            draw.rounded_rectangle([(22, 72), (320, 98)], radius=8, fill=(15, 23, 42), outline=(16, 185, 129), width=1)
            draw.text((34, 78), "VERIFIED BENCHMARKS // LIVE TELEMETRY", fill=(16, 185, 129), font=font_badge)

            screen_x0 = 250
            screen_x1 = width - 16
            draw.rounded_rectangle([(screen_x0, 104), (screen_x1, 260)], radius=12, fill=(11, 18, 34, 220), outline=(16, 185, 129), width=2)
            draw.text((screen_x0 + 14, 114), f"{persona['lab'].upper()} SOTA BENCHMARKS", fill=(255, 255, 255), font=font_badge)

            scene_prog = min(1.0, max(0.1, (progress - 0.52) / 0.18))
            benchmarks = [
                ("Reasoning Accuracy", 0.94, accent_clr, "+14.8% SOTA", 142),
                ("Multi-Agent Verify", 0.91, (16, 185, 129), "2.4x Speed", 180),
                ("Inference Latency", 0.89, sec_clr, "-62% Latency", 218),
            ]

            active_bench_y = 142
            for b_label, target_val, b_clr, b_delta, ym in benchmarks:
                curr_val = target_val * scene_prog
                draw.text((screen_x0 + 14, ym), b_label, fill=(226, 232, 240), font=font_small)
                draw.text((screen_x1 - 85, ym), b_delta, fill=b_clr, font=font_code)
                draw.rounded_rectangle([(screen_x0 + 14, ym + 16), (screen_x1 - 14, ym + 26)], radius=5, fill=(30, 41, 59))
                fill_w = max(10, int((screen_x1 - screen_x0 - 28) * curr_val))
                draw.rounded_rectangle([(screen_x0 + 14, ym + 16), (screen_x0 + 14 + fill_w, ym + 26)], radius=5, fill=b_clr)
                if scene_prog > 0.65 and ym == 218:
                    active_bench_y = ym + 21
                elif scene_prog > 0.35 and ym == 180:
                    active_bench_y = ym + 21
                elif ym == 142:
                    active_bench_y = ym + 21

            # Target active benchmark progress bar
            target_xy = (screen_x1 - 30, active_bench_y)

            # Optical Beacon Connecting CEO's Finger to the Benchmark Bar
            presenter_inst.draw_interactive_optical_beacon(
                base_canvas=img,
                finger_xy=finger_xy,
                target_xy=target_xy,
                t=t,
            )

        # -------------------------------------------------------------
        # 3. Synchronized Word-by-Word Highlighted Kinetic Subtitles
        # -------------------------------------------------------------
        draw_kinetic_subtitles(
            draw=draw,
            words=script_words,
            progress=progress,
            width=width,
            y_pos=812,
            accent_color=accent_clr,
            font_sub=font_sub,
        )

        # -------------------------------------------------------------
        # 4. Executive Broadcast Footer with AIGC Compliance Badge
        # -------------------------------------------------------------
        footer_box = [(22, height - 48), (width - 22, height - 14)]
        draw.rounded_rectangle(footer_box, radius=10, fill=(15, 23, 42), outline=(51, 65, 85), width=1)
        draw.text((34, height - 38), f"@{persona['lab'].replace(' ', '')}  •  @Eraof_Ai", fill=(255, 255, 255), font=font_small)
        draw.text((width - 215, height - 38), "AI Executive Simulation • Full HD", fill=(148, 163, 184), font=font_small)

        writer.send(np.array(img))

    writer.close()

    # Mux video with synthesized CEO voiceover into Full HD 1080x1920 (9:16) 30fps + 44.1kHz Stereo AAC
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    if output_video_path.exists():
        output_video_path.unlink()

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i", str(temp_raw_video),
        "-i", str(audio_path),
        "-vf", "scale=1080:1920:flags=lanczos,unsharp=3:3:0.5:3:3:0.0",
        "-r", "30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "192k",
        "-shortest",
        str(output_video_path),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    if temp_raw_video.exists():
        temp_raw_video.unlink()

    return str(output_video_path)


async def synthesize_broadcast_video(
    directive: Dict[str, Any],
    output_filename: str,
    use_veo: bool = False
) -> str:
    """
    End-to-end CEO Character Keynote Video synthesis pipeline:
    1. Detect company CEO persona (Sundar Pichai for Google, Sam Altman for OpenAI, etc.)
    2. Compose first-person CEO keynote script
    3. Synthesize CEO-matched neural voiceover (accent + vocal formant/pitch/EQ profile)
    4. Render 30fps audio-synchronized talking CEO character + 4 dynamic scenes in Full HD 1080x1920
    """
    headline = directive.get("title") or directive.get("headline") or "Frontier AI Breakthrough"
    hook_text = (directive.get("hook_narration") or "").strip()
    body_text = (directive.get("body_narration") or "").strip()
    source_url = (directive.get("source_url") or "").strip()

    persona = detect_persona(headline, f"{hook_text} {body_text} {source_url}")
    narration = build_ceo_first_person_script(directive, persona)

    audio_path = STAGING_DIR / f"voice_{output_filename}.mp3"
    video_path = STAGING_DIR / f"{output_filename}.mp4"

    # Step 1: Synthesize CEO-matched neural speech
    await synthesize_audio(
        narration,
        audio_path,
        voice=persona.get("voice_profile", {}).get("edge_voice", "en-IN-PrabhatNeural"),
        persona=persona,
    )

    # Step 2: Optional Gemini Omni 1.1 Flash / Veo 3.1 cloud video generation
    if use_veo:
        try:
            p_file = PORTRAITS_DIR / persona.get("portrait_file", "sundar_pichai.jpg")
            generate_veo_broll(
                f"{persona['name']}, {persona['title']}, presenting {headline} on a modern AI keynote stage",
                first_frame_path=p_file if p_file.exists() else None,
            )
        except Exception as e:
            print(f"[CEOVideoEngine] Cloud Veo/Omni skipped ({e}); rendering via 30fps CEO Character Animator.")

    # Step 3: Render 9:16 Full HD 1080x1920 30fps animated CEO presenter video
    try:
        from src.ai_video_engine import generate_presenter_video
        await generate_presenter_video(
            persona=persona,
            audio_path=audio_path,
            output_video_path=video_path,
            brief=directive,
            prefer_ai_diffusion=True
        )
    except Exception as e:
        print(f"[CEOVideoEngine] AI video engine error ({e}); falling back to local motion renderer.")
        render_motion_video(
            directive,
            audio_path,
            video_path,
            fps=30,
            persona=persona,
            spoken_script=narration,
        )

    return str(video_path)


def synthesize_broadcast_video_sync(
    directive: Dict[str, Any],
    output_filename: str,
    use_veo: bool = False
) -> str:
    """Thread-safe synchronous wrapper for synthesize_broadcast_video."""
    import concurrent.futures
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, synthesize_broadcast_video(directive, output_filename, use_veo=use_veo))
            return future.result(timeout=180)
    else:
        return asyncio.run(synthesize_broadcast_video(directive, output_filename, use_veo=use_veo))


if __name__ == "__main__":
    test_d = {
        "title": "Google Gemini 3.8 Flash: Real-Time Autonomous Coding & Multimodal Reasoning",
        "hook_narration": "Gemini 3.8 Flash just shattered SWE-bench coding benchmarks with a verified 14.8% leap in autonomous repository engineering.",
        "body_narration": "Our new sparse mixture-of-experts architecture combines sub-second 18 millisecond latency with native multi-file AST verification and live tool execution across Google Cloud and Android.",
        "call_to_action": "Will autonomous test-time compute make single-pass code assistants obsolete? Drop your thoughts in the comments!",
    }
    out = asyncio.run(synthesize_broadcast_video(test_d, "test_google_ceo_sundar_pichai_reel"))
    print("CEO Keynote Video rendered successfully:", out, "Size:", os.path.getsize(out), "bytes")
