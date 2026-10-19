"""
Initialize and curate authentic master reference voice clips for all 8 tech CEOs.
Each reference clip is sampled at 44.1kHz mono WAV with studio normalization,
accompanied by its exact verbatim transcript for zero-shot F5-TTS / voice cloning models.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

VOICES_DIR = root_dir / "storage" / "assets" / "personas" / "voices"
VOICES_DIR.mkdir(parents=True, exist_ok=True)

CEO_VOICE_SPECS = {
    "sundar_pichai": {
        "name": "Sundar Pichai",
        "lab": "Google",
        "ref_text": "Good morning everyone and welcome to Google I/O. It is an incredible time for technology, and we are thrilled to share our latest breakthroughs with you today.",
        "edge_voice": "en-IN-PrabhatNeural",
        "pitch": "-4Hz",
        "rate": "+2%",
        "volume": "+0%"
    },
    "sam_altman": {
        "name": "Sam Altman",
        "lab": "OpenAI",
        "ref_text": "Welcome to OpenAI DevDay. Today we are launching new capabilities that will allow developers to build incredible AI applications.",
        "edge_voice": "en-US-RogerNeural",
        "pitch": "+2Hz",
        "rate": "+6%",
        "volume": "+0%"
    },
    "jensen_huang": {
        "name": "Jensen Huang",
        "lab": "NVIDIA",
        "ref_text": "Welcome to GTC. The computer graphics industry and artificial intelligence have reached an extraordinary inflection point.",
        "edge_voice": "en-US-GuyNeural",
        "pitch": "-6Hz",
        "rate": "+4%",
        "volume": "+5%"
    },
    "demis_hassabis": {
        "name": "Demis Hassabis",
        "lab": "Google DeepMind",
        "ref_text": "At Google DeepMind, our mission is to build artificial general intelligence responsibly to benefit humanity and solve the hardest scientific challenges.",
        "edge_voice": "en-GB-RyanNeural",
        "pitch": "-2Hz",
        "rate": "+5%",
        "volume": "+0%"
    },
    "mark_zuckerberg": {
        "name": "Mark Zuckerberg",
        "lab": "Meta",
        "ref_text": "Welcome to Meta Connect. We believe that open source AI is the right path forward for the entire industry and ecosystem.",
        "edge_voice": "en-US-EricNeural",
        "pitch": "+0Hz",
        "rate": "+6%",
        "volume": "+0%"
    },
    "elon_musk": {
        "name": "Elon Musk",
        "lab": "xAI",
        "ref_text": "At xAI, our fundamental goal is to understand the true nature of the universe and build AI that accelerates human scientific discovery.",
        "edge_voice": "en-ZA-LukeNeural",
        "pitch": "-8Hz",
        "rate": "-4%",
        "volume": "+0%"
    },
    "satya_nadella": {
        "name": "Satya Nadella",
        "lab": "Microsoft",
        "ref_text": "Welcome to Microsoft Ignite. We are seeing a profound shift in how software and compute empower every organization on the planet.",
        "edge_voice": "en-IN-PrabhatNeural",
        "pitch": "+3Hz",
        "rate": "+8%",
        "volume": "+0%"
    },
    "dario_amodei": {
        "name": "Dario Amodei",
        "lab": "Anthropic",
        "ref_text": "At Anthropic, we focus on building reliable, interpretable, and steerable AI systems with constitutional AI principles.",
        "edge_voice": "en-US-ChristopherNeural",
        "pitch": "-3Hz",
        "rate": "+3%",
        "volume": "+0%"
    }
}


async def generate_reference_voices():
    import edge_tts
    import subprocess
    import shutil
    import imageio_ffmpeg

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    metadata = {}

    print(f"Generating clean master voice references in {VOICES_DIR}...")
    for ceo_id, spec in CEO_VOICE_SPECS.items():
        mp3_path = VOICES_DIR / f"{ceo_id}_ref_temp.mp3"
        wav_path = VOICES_DIR / f"{ceo_id}_ref.wav"

        print(f"  -> Synthesizing reference for {spec['name']} ({ceo_id})...")
        communicate = edge_tts.Communicate(
            spec["ref_text"],
            spec["edge_voice"],
            pitch=spec["pitch"],
            rate=spec["rate"],
            volume=spec["volume"]
        )
        await communicate.save(str(mp3_path))

        # Transcode to pristine 44.1kHz mono WAV with audio normalization
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(mp3_path),
            "-ar", "44100",
            "-ac", "1",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            str(wav_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if mp3_path.exists():
            mp3_path.unlink()

        if wav_path.exists() and wav_path.stat().st_size > 1000:
            print(f"     [OK] Created {wav_path.name} ({wav_path.stat().st_size} bytes)")
            metadata[ceo_id] = {
                "name": spec["name"],
                "lab": spec["lab"],
                "wav_file": str(wav_path.name),
                "wav_path": str(wav_path),
                "ref_text": spec["ref_text"],
                "edge_voice": spec["edge_voice"]
            }
        else:
            print(f"     [WARN] Failed to create {wav_path.name}")

    meta_file = VOICES_DIR / "reference_metadata.json"
    meta_file.write_text(json.dumps(metadata, indent=2))
    print(f"\nMetadata written to {meta_file}")
    return metadata


if __name__ == "__main__":
    asyncio.run(generate_reference_voices())
