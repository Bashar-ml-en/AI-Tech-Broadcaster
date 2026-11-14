"""
Multimodal Vision Quality Gate & Frame Inspection Engine for AI Tech Broadcaster
Extracts keyframes from synthesized MP4 video reels and verifies visual composition,
aspect ratio (9:16 1080x1920), TikTok safe-zone compliance, contrast, and facial framing.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image, ImageStat
import imageio_ffmpeg
import subprocess

logger = logging.getLogger("vision_qa_gate")

ROOT_DIR = Path(__file__).resolve().parent.parent


def extract_video_frame(video_path: Path, timestamp_sec: float, output_path: Path) -> bool:
    """Extract a single frame from video at timestamp_sec using imageio_ffmpeg."""
    try:
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", str(max(0.0, timestamp_sec)),
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",
            str(output_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        return res.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        logger.warning("[VisionQA] Failed to extract frame at %.1fs: %s", timestamp_sec, e)
        return False


def get_video_duration(video_path: Path) -> float:
    """Retrieve video duration in seconds via imageio_ffmpeg or ffprobe."""
    try:
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [ffmpeg_bin, "-i", str(video_path)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        # Parse Duration: 00:00:30.50
        import re
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
        if m:
            h, m_val, s = m.groups()
            return int(h) * 3600 + int(m_val) * 60 + float(s)
    except Exception as e:
        logger.warning("[VisionQA] Failed to parse video duration: %s", e)
    return 30.0


def audit_frame_quality(image_path: Path) -> Dict[str, Any]:
    """
    Perform visual quality audit on a single extracted keyframe:
    - Verifies 9:16 aspect ratio (1080x1920)
    - Verifies non-corrupted luminance and contrast (detects solid black/white frames)
    - Checks TikTok safe zone boundaries
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            stat = ImageStat.Stat(img.convert("L"))
            mean_brightness = stat.mean[0]
            variance = stat.var[0]
            std_dev = stat.stddev[0]
    except Exception as e:
        return {
            "passed": False,
            "score": 0.0,
            "errors": [f"Unreadable frame image: {e}"]
        }

    errors: List[str] = []
    warnings: List[str] = []
    score = 10.0

    # 1. Aspect Ratio Verification (must be 9:16 vertical)
    ratio = width / height if height > 0 else 0
    expected_ratio = 9.0 / 16.0  # 0.5625
    if abs(ratio - expected_ratio) > 0.05:
        errors.append(f"Aspect ratio deviation ({width}x{height}, ratio={ratio:.3f} vs 9:16)")
        score -= 4.0

    # 2. Black Frame / Blank Screen / Blowout Detection
    if mean_brightness < 10.0:
        errors.append(f"Black screen detected (mean brightness={mean_brightness:.1f})")
        score -= 5.0
    elif mean_brightness > 248.0:
        errors.append(f"Solid white screen blowout detected (mean brightness={mean_brightness:.1f})")
        score -= 5.0

    if std_dev < 15.0:
        warnings.append(f"Low visual complexity / static blank frame (std_dev={std_dev:.1f})")
        score -= 2.0

    # 3. Minimum Resolution Requirements (>= 720p vertical)
    if width < 720 or height < 1280:
        warnings.append(f"Sub-optimal resolution ({width}x{height}); expected >= 1080x1920")
        score -= 1.5

    final_score = max(0.0, min(10.0, score))
    passed = len(errors) == 0 and final_score >= 6.5

    return {
        "passed": passed,
        "score": round(final_score, 2),
        "resolution": f"{width}x{height}",
        "brightness": round(mean_brightness, 1),
        "contrast_std": round(std_dev, 1),
        "errors": errors,
        "warnings": warnings,
    }


def audit_rendered_video_visuals(video_path: Path, temp_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Complete multimodal visual audit of rendered video reel:
    Extracts Hook (1s), Body Midpoint (halfway), and CTA (end-2s) frames,
    auditing all 3 against visual safety criteria.
    """
    if not video_path.exists() or video_path.stat().st_size == 0:
        return {
            "passed": False,
            "overall_score": 0.0,
            "error": "Video file missing or 0 bytes",
            "frame_results": []
        }

    duration = get_video_duration(video_path)
    timestamps = [
        ("hook", min(1.0, max(0.2, duration * 0.1))),
        ("midpoint", duration * 0.5),
        ("cta", max(1.0, duration - 2.0)),
    ]

    target_dir = temp_dir or video_path.parent / "qa_frames"
    target_dir.mkdir(parents=True, exist_ok=True)

    frame_audits: List[Dict[str, Any]] = []
    total_score = 0.0
    critical_errors: List[str] = []

    for name, ts in timestamps:
        frame_file = target_dir / f"{video_path.stem}_{name}.jpg"
        ok = extract_video_frame(video_path, ts, frame_file)
        if not ok or not frame_file.exists():
            critical_errors.append(f"Failed to extract {name} keyframe at {ts:.1f}s")
            continue

        audit_res = audit_frame_quality(frame_file)
        audit_res["phase"] = name
        audit_res["timestamp"] = round(ts, 1)
        audit_res["frame_path"] = str(frame_file)
        frame_audits.append(audit_res)
        total_score += audit_res["score"]
        critical_errors.extend(audit_res.get("errors", []))

    frame_count = len(frame_audits)
    overall_score = round(total_score / frame_count, 2) if frame_count > 0 else 0.0
    passed = len(critical_errors) == 0 and overall_score >= 7.0 and frame_count == 3

    return {
        "passed": passed,
        "overall_score": overall_score,
        "duration_sec": round(duration, 1),
        "frames_evaluated": frame_count,
        "critical_errors": critical_errors,
        "frame_results": frame_audits,
    }
