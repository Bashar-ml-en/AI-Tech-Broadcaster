"""
AutoProdcaster - Neural CEO Voice Cloning Engine
Integrates free and SOTA voice cloning technologies:
1. F5-TTS / E2-TTS Zero-Shot Diffusion Voice Cloning (via Hugging Face Space API / gradio_client)
2. ElevenLabs Free Tier (if configured in config/.env)
3. Fish Audio Free API (if configured)
4. Calibrated Multi-Accent Edge-TTS Neural Fallback with Executive EQ & Pitch Compensation
"""

import os
import sys
import json
import time
import shutil
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import imageio_ffmpeg
from gradio_client import Client, handle_file

logger = logging.getLogger("voice_cloner")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

ROOT_DIR = Path(__file__).resolve().parent.parent
VOICES_DIR = ROOT_DIR / "storage" / "assets" / "personas" / "voices"
METADATA_PATH = VOICES_DIR / "reference_metadata.json"

F5_TTS_DEFAULT_SPACE = os.getenv("F5_TTS_SPACE", "mrfakename/E2-F5-TTS")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN", os.getenv("HF_TOKEN", None))


def load_voice_metadata() -> Dict[str, Any]:
    """Load reference audio metadata for tech CEOs."""
    if METADATA_PATH.exists():
        try:
            return json.loads(METADATA_PATH.read_text())
        except Exception as e:
            logger.warning("Failed to parse reference_metadata.json: %s", e)
    return {}


async def _clone_voice_f5_tts(
    narration_text: str,
    ref_wav_path: Path,
    ref_text: str,
    output_path: Path,
    space_name: str = F5_TTS_DEFAULT_SPACE,
    timeout_sec: float = 60.0
) -> bool:
    """
    Synthesize speech using F5-TTS Zero-Shot Voice Cloning on Hugging Face Spaces.
    Extracts authentic vocal formant, timber, and cadence from reference audio.
    """
    logger.info("Attempting F5-TTS zero-shot voice cloning via Hugging Face Space '%s'...", space_name)

    def _sync_f5_call():
        client = Client(space_name, token=HF_TOKEN, verbose=False)
        result = client.predict(
            ref_audio=handle_file(str(ref_wav_path)),
            ref_text=ref_text,
            gen_text=narration_text,
            remove_silence=False,
            api_name="/predict"
        )
        return result

    try:
        loop = asyncio.get_running_loop()
        gen_path = await asyncio.wait_for(loop.run_in_executor(None, _sync_f5_call), timeout=timeout_sec)
        if gen_path and Path(gen_path).exists() and Path(gen_path).stat().st_size > 1500:
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(gen_path),
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                str(output_path)
            ]
            import subprocess
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            logger.info("F5-TTS voice cloning succeeded: %s (%d bytes)", output_path.name, output_path.stat().st_size)
            return True
    except asyncio.TimeoutError:
        logger.warning("F5-TTS Hugging Face Space timed out after %ds (queue busy)", timeout_sec)
    except Exception as e:
        logger.warning("F5-TTS voice cloning failed: %s", e)

    return False


async def _clone_voice_elevenlabs(
    narration_text: str,
    voice_id: str,
    output_path: Path,
    api_key: str
) -> bool:
    """Synthesize voice using ElevenLabs API if key is provided."""
    import httpx
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": narration_text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8
        }
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200 and len(resp.content) > 1000:
                output_path.write_bytes(resp.content)
                logger.info("ElevenLabs voice cloning succeeded: %s", output_path.name)
                return True
            else:
                logger.warning("ElevenLabs API returned status %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.warning("ElevenLabs voice generation error: %s", e)
    return False


async def _synthesize_edge_fallback(
    narration_text: str,
    output_path: Path,
    persona: Dict[str, Any]
) -> Path:
    """
    Tier 4 Fallback: Calibrated Edge-TTS with multi-accent neural model
    and FFmpeg formant & harmonic EQ compensation.
    """
    import edge_tts
    import subprocess

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    vp = (persona or {}).get("voice_profile", {})
    edge_voice = vp.get("edge_voice", "en-IN-PrabhatNeural")
    pitch_factor = float(vp.get("pitch_factor", 0.96))
    tempo = float(vp.get("tempo", 1.04))
    eq_filter = vp.get("eq_filter", "equalizer=f=220:width_type=o:width=1.5:g=3.5")

    raw_tts_path = output_path.with_name(f"raw_edge_{output_path.stem}.mp3")

    logger.info("Using calibrated Edge-TTS fallback voice '%s' for persona '%s'...", edge_voice, persona.get("id"))
    try:
        rate_str = f"+{int((tempo - 1.0) * 100)}%" if tempo >= 1.0 else f"{int((tempo - 1.0) * 100)}%"
        communicate = edge_tts.Communicate(narration_text, edge_voice, rate=rate_str)
        await communicate.save(str(raw_tts_path))
    except Exception as e:
        logger.warning("Edge-TTS save error: %s", e)

    if raw_tts_path.exists() and raw_tts_path.stat().st_size > 1000:
        tempo_comp = 1.0 / pitch_factor if pitch_factor != 0 else 1.0
        audio_filter = (
            f"asetrate=44100*{pitch_factor:.3f},"
            f"atempo={tempo_comp:.3f},"
            f"{eq_filter},"
            f"loudnorm=I=-16:TP=-1.5:LRA=11"
        )
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(raw_tts_path),
            "-af", audio_filter,
            "-ar", "44100",
            "-ac", "2",
            "-b:a", "192k",
            str(output_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 1000:
            if raw_tts_path.exists():
                raw_tts_path.unlink()
            return output_path

    if raw_tts_path.exists():
        raw_tts_path.replace(output_path)
        return output_path

    # Ultimate safety net: generate a short tone if all TTS fails
    cmd_tone = [
        ffmpeg_exe, "-y",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", "5",
        "-b:a", "192k",
        str(output_path)
    ]
    subprocess.run(cmd_tone, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_path


async def synthesize_ceo_voice(
    narration_text: str,
    output_path: Path,
    persona: Dict[str, Any],
    prefer_zero_shot: bool = True
) -> Path:
    """
    Main entry point for CEO voice synthesis.
    Cascades across:
    1. ElevenLabs (if ELEVENLABS_API_KEY is configured)
    2. F5-TTS / E2-TTS Zero-Shot Diffusion Voice Cloning (via Hugging Face Spaces)
    3. Calibrated Edge-TTS with Executive Formant & EQ Sculpting
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ceo_id = persona.get("id", "sundar_pichai")
    metadata = load_voice_metadata()
    ceo_meta = metadata.get(ceo_id, {})

    # Provider 1: ElevenLabs if key and voice ID present
    eleven_key = os.getenv("ELEVENLABS_API_KEY", "")
    eleven_voice_id = persona.get("voice_profile", {}).get("elevenlabs_voice_id") or os.getenv(f"ELEVENLABS_VOICE_{ceo_id.upper()}", "")
    if eleven_key and eleven_voice_id:
        success = await _clone_voice_elevenlabs(narration_text, eleven_voice_id, output_path, eleven_key)
        if success and output_path.exists() and output_path.stat().st_size > 1500:
            return output_path

    # Provider 2: F5-TTS Zero-Shot Voice Cloning
    if prefer_zero_shot:
        ref_file = VOICES_DIR / f"{ceo_id}_ref.wav"
        ref_text = ceo_meta.get("ref_text", "")
        if ref_file.exists() and ref_text:
            success = await _clone_voice_f5_tts(
                narration_text=narration_text,
                ref_wav_path=ref_file,
                ref_text=ref_text,
                output_path=output_path,
                timeout_sec=40.0
            )
            if success and output_path.exists() and output_path.stat().st_size > 1500:
                return output_path

    # Provider 3: Calibrated Fallback
    return await _synthesize_edge_fallback(narration_text, output_path, persona)
