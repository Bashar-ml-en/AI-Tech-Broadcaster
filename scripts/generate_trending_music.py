"""
AutoProdcaster - Trending Background Music Synthesizer
Procedurally composes and exports 5 royalty-free, high-energy modern trending beat tracks:
1. trending_malaysia_tech_phonk.mp3 (132 BPM: Viral SEA/Malaysia TikTok Phonk, punchy 808 kick, sliding sub-bass, syncopated bells)
2. trending_cyber_keynote_energy.mp3 (128 BPM: Driving electro house beat, saw bass arpeggios, atmospheric risers)
3. trending_silicon_future_groove.mp3 (124 BPM: Modern tech house bounce, snappy clap, clean melodic stabs)
4. trending_synthwave_momentum.mp3 (115 BPM: Driving retro-futuristic synthwave pulse, analog chords)
5. trending_lofi_cyber_chill.mp3 (92 BPM: Mellow chillhop groove, warm Rhodes chords, vinyl warmth)
"""

import sys
import subprocess
from pathlib import Path
import numpy as np
import imageio_ffmpeg

ROOT_DIR = Path(__file__).resolve().parent.parent
MUSIC_DIR = ROOT_DIR / "storage" / "assets" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)


def _render_to_mp3(stereo_arr: np.ndarray, sr: int, out_path: Path):
    """Encode stereo float32 [-1.0, 1.0] array into 192k MP3 via FFmpeg."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    clipped = np.clip(stereo_arr, -0.98, 0.98)
    raw_pcm = (clipped * 32767).astype(np.int16).tobytes()
    cmd = [
        ffmpeg_exe, "-y",
        "-f", "s16le",
        "-ar", str(sr),
        "-ac", "2",
        "-i", "pipe:0",
        "-b:a", "192k",
        str(out_path)
    ]
    subprocess.run(cmd, input=raw_pcm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def generate_all_trending_tracks(duration_sec: float = 45.0, sr: int = 44100):
    """Generate all 5 master trending background tracks."""
    print(f"Synthesizing 5 trending music tracks in {MUSIC_DIR}...")
    total_samples = int(sr * duration_sec)
    t = np.linspace(0, duration_sec, total_samples, endpoint=False)

    # -------------------------------------------------------------------------
    # Track 1: trending_malaysia_tech_phonk (132 BPM)
    # Extremely viral in Malaysia, Indonesia & Southeast Asia TikTok Reels
    # -------------------------------------------------------------------------
    bpm1 = 132
    beat_len1 = 60.0 / bpm1
    track1 = np.zeros(total_samples)

    # Hard-hitting 808 Kick on beats 1, 2.5, 3
    for bar in np.arange(0, duration_sec, beat_len1 * 4):
        for offset in [0.0, beat_len1 * 1.5, beat_len1 * 2.0, beat_len1 * 3.25]:
            pos = bar + offset
            if pos < duration_sec:
                idx = int(pos * sr)
                k_len = int(0.28 * sr)
                if idx + k_len < total_samples:
                    kt = np.linspace(0, 0.28, k_len)
                    freq = 160 * np.exp(-22 * kt) + 42
                    env = np.exp(-10 * kt)
                    track1[idx:idx+k_len] += 0.8 * np.sin(2 * np.pi * freq * kt) * env

    # Snappy 808 Snare on beats 2 and 4
    for bar in np.arange(0, duration_sec, beat_len1 * 4):
        for offset in [beat_len1 * 1.0, beat_len1 * 3.0]:
            pos = bar + offset
            if pos < duration_sec:
                idx = int(pos * sr)
                s_len = int(0.18 * sr)
                if idx + s_len < total_samples:
                    st = np.linspace(0, 0.18, s_len)
                    noise = np.random.uniform(-1, 1, s_len) * np.exp(-25 * st)
                    tone = np.sin(2 * np.pi * 220 * st) * np.exp(-30 * st)
                    track1[idx:idx+s_len] += 0.5 * (noise + tone)

    # Fast 16th-note phonk trap hats
    for b in np.arange(0, duration_sec, beat_len1 / 4):
        idx = int(b * sr)
        h_len = int(0.04 * sr)
        if idx + h_len < total_samples:
            ht = np.linspace(0, 0.04, h_len)
            noise = np.random.uniform(-1, 1, h_len) * np.exp(-60 * ht)
            track1[idx:idx+h_len] += 0.25 * noise

    # Cowbell / Phonk melodic riff in G minor (G4, Bb4, D5, C5)
    phonk_notes = [392.0, 466.16, 587.33, 523.25, 466.16, 392.0, 349.23, 392.0]
    for b_idx, b in enumerate(np.arange(0, duration_sec, beat_len1 / 2)):
        idx = int(b * sr)
        m_len = int(0.18 * sr)
        freq = phonk_notes[b_idx % len(phonk_notes)]
        if idx + m_len < total_samples:
            mt = np.linspace(0, 0.18, m_len)
            bell = (np.sin(2 * np.pi * freq * mt) + 0.4 * np.sin(2 * np.pi * freq * 2.02 * mt)) * np.exp(-18 * mt)
            track1[idx:idx+m_len] += 0.35 * bell

    # Sliding 808 sub bass
    sub1 = 0.45 * np.sin(2 * np.pi * (46.25 + 6 * np.sin(2 * np.pi * 0.5 * t)) * t) * (0.8 + 0.2 * np.sin(2 * np.pi * (bpm1 / 60) * t))
    out1_stereo = np.column_stack([track1 + sub1, track1 + sub1 * 0.95])
    _render_to_mp3(out1_stereo, sr, MUSIC_DIR / "trending_malaysia_tech_phonk.mp3")
    print(f"  [OK] trending_malaysia_tech_phonk.mp3 ({MUSIC_DIR / 'trending_malaysia_tech_phonk.mp3'})")

    # -------------------------------------------------------------------------
    # Track 2: trending_cyber_keynote_energy (128 BPM)
    # Driving modern electro house / tech keynote energy
    # -------------------------------------------------------------------------
    bpm2 = 128
    beat_len2 = 60.0 / bpm2
    track2 = np.zeros(total_samples)

    # 4-on-the-floor kick
    for b in np.arange(0, duration_sec, beat_len2):
        idx = int(b * sr)
        k_len = int(0.22 * sr)
        if idx + k_len < total_samples:
            kt = np.linspace(0, 0.22, k_len)
            freq = 150 * np.exp(-24 * kt) + 50
            env = np.exp(-14 * kt)
            track2[idx:idx+k_len] += 0.75 * np.sin(2 * np.pi * freq * kt) * env

    # Off-beat open hi-hat
    for b in np.arange(beat_len2 / 2, duration_sec, beat_len2):
        idx = int(b * sr)
        h_len = int(0.12 * sr)
        if idx + h_len < total_samples:
            ht = np.linspace(0, 0.12, h_len)
            noise = np.random.uniform(-1, 1, h_len) * np.exp(-20 * ht)
            track2[idx:idx+h_len] += 0.35 * noise

    # Electro saw arpeggio in F minor
    f_arp = [174.61, 207.65, 261.63, 311.13, 349.23, 311.13, 261.63, 207.65]
    for b_idx, b in enumerate(np.arange(0, duration_sec, beat_len2 / 4)):
        idx = int(b * sr)
        a_len = int(0.10 * sr)
        freq = f_arp[b_idx % len(f_arp)]
        if idx + a_len < total_samples:
            at = np.linspace(0, 0.10, a_len)
            saw = (2 * (at * freq - np.floor(0.5 + at * freq))) * np.exp(-15 * at)
            track2[idx:idx+a_len] += 0.22 * saw

    sub2 = 0.35 * np.sin(2 * np.pi * 58.27 * t)
    out2_stereo = np.column_stack([track2 + sub2, track2 + sub2])
    _render_to_mp3(out2_stereo, sr, MUSIC_DIR / "trending_cyber_keynote_energy.mp3")
    print(f"  [OK] trending_cyber_keynote_energy.mp3")

    # -------------------------------------------------------------------------
    # Track 3: trending_silicon_future_groove (124 BPM)
    # Modern Silicon Valley tech house bounce
    # -------------------------------------------------------------------------
    bpm3 = 124
    beat_len3 = 60.0 / bpm3
    track3 = np.zeros(total_samples)

    for b in np.arange(0, duration_sec, beat_len3):
        idx = int(b * sr)
        k_len = int(0.20 * sr)
        if idx + k_len < total_samples:
            kt = np.linspace(0, 0.20, k_len)
            freq = 135 * np.exp(-20 * kt) + 48
            env = np.exp(-13 * kt)
            track3[idx:idx+k_len] += 0.7 * np.sin(2 * np.pi * freq * kt) * env

    for b in np.arange(beat_len3, duration_sec, beat_len3 * 2):
        idx = int(b * sr)
        c_len = int(0.14 * sr)
        if idx + c_len < total_samples:
            ct = np.linspace(0, 0.14, c_len)
            clap = np.random.uniform(-1, 1, c_len) * np.exp(-28 * ct)
            track3[idx:idx+c_len] += 0.45 * clap

    # Tech house bass bounce
    bounce_bass = 0.35 * np.sin(2 * np.pi * 65.41 * t) * (np.sin(2 * np.pi * (bpm3 / 120) * t) ** 2)
    out3_stereo = np.column_stack([track3 + bounce_bass, track3 + bounce_bass * 0.9])
    _render_to_mp3(out3_stereo, sr, MUSIC_DIR / "trending_silicon_future_groove.mp3")
    print(f"  [OK] trending_silicon_future_groove.mp3")

    # -------------------------------------------------------------------------
    # Track 4: trending_synthwave_momentum (115 BPM)
    # Driving retro-futuristic synthwave pulse
    # -------------------------------------------------------------------------
    bpm4 = 115
    beat_len4 = 60.0 / bpm4
    track4 = np.zeros(total_samples)

    for b in np.arange(0, duration_sec, beat_len4):
        idx = int(b * sr)
        k_len = int(0.25 * sr)
        if idx + k_len < total_samples:
            kt = np.linspace(0, 0.25, k_len)
            track4[idx:idx+k_len] += 0.65 * np.sin(2 * np.pi * (140 * np.exp(-15 * kt) + 45) * kt) * np.exp(-10 * kt)

    # 8th note rolling octave synth bass
    synthwave_bass = 0.3 * np.sin(2 * np.pi * (110 if int(t[0]*2)%2==0 else 55) * t) * (0.8 + 0.2 * np.sin(2 * np.pi * bpm4/60 * t))
    out4_stereo = np.column_stack([track4 + synthwave_bass, track4 + synthwave_bass])
    _render_to_mp3(out4_stereo, sr, MUSIC_DIR / "trending_synthwave_momentum.mp3")
    print(f"  [OK] trending_synthwave_momentum.mp3")

    # -------------------------------------------------------------------------
    # Track 5: trending_lofi_cyber_chill (92 BPM)
    # Relaxed tech lofi beat
    # -------------------------------------------------------------------------
    bpm5 = 92
    beat_len5 = 60.0 / bpm5
    track5 = np.zeros(total_samples)

    for b in np.arange(0, duration_sec, beat_len5 * 2):
        idx = int(b * sr)
        k_len = int(0.25 * sr)
        if idx + k_len < total_samples:
            kt = np.linspace(0, 0.25, k_len)
            track5[idx:idx+k_len] += 0.55 * np.sin(2 * np.pi * (110 * np.exp(-12 * kt) + 40) * kt) * np.exp(-8 * kt)

    # Soft snare on beat 2
    for b in np.arange(beat_len5, duration_sec, beat_len5 * 2):
        idx = int(b * sr)
        s_len = int(0.15 * sr)
        if idx + s_len < total_samples:
            st = np.linspace(0, 0.15, s_len)
            track5[idx:idx+s_len] += 0.3 * np.random.uniform(-1, 1, s_len) * np.exp(-22 * st)

    # Gentle Rhodes chord
    rhodes = 0.22 * (np.sin(2 * np.pi * 261.63 * t) + np.sin(2 * np.pi * 329.63 * t) + np.sin(2 * np.pi * 392.00 * t))
    vinyl_noise = 0.04 * np.random.uniform(-1, 1, total_samples)
    out5_stereo = np.column_stack([track5 + rhodes + vinyl_noise, track5 + rhodes + vinyl_noise])
    _render_to_mp3(out5_stereo, sr, MUSIC_DIR / "trending_lofi_cyber_chill.mp3")
    print(f"  [OK] trending_lofi_cyber_chill.mp3")
    print("\nAll 5 master trending tracks synthesized successfully!")


if __name__ == "__main__":
    generate_all_trending_tracks()
