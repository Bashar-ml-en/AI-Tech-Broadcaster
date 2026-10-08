"""
Cloudflare R2 Object Storage & Media Validation Module for AI Tech Broadcaster
Provides:
1. Public CDN asset staging with S3-compatible R2 client
2. MediaRef typed references guaranteeing hosted state
3. Real public URL verification (HEAD / ranged GET)
4. Platform-specific media validation (resolution, aspect ratio, duration, format)
"""

import os
import mimetypes
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
from dotenv import load_dotenv

from src.publish_types import MediaRef

# Load configuration from config/.env
env_path = Path(__file__).resolve().parent.parent / "config" / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("r2_storage")
if not logger.handlers:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

ACCOUNT_ID = os.getenv("CLOUDFLARE_R2_ACCOUNT_ID", "").strip()
ACCESS_KEY_ID = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID", "").strip()
SECRET_ACCESS_KEY = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY", "").strip()
BUCKET_NAME = os.getenv("CLOUDFLARE_R2_BUCKET_NAME", "broadcaster-staging").strip()
PUBLIC_URL = os.getenv("CLOUDFLARE_R2_PUBLIC_URL", "").rstrip("/")
STAGING_DIR = Path(__file__).resolve().parent.parent / "storage" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Platform Media Constraints (Single Source of Truth)
# Maintainers: Verify against current official developer documentation.
# ---------------------------------------------------------------------------
PLATFORM_MEDIA_LIMITS = {
    "instagram_reel": {
        "max_size_mb": 100,
        "max_duration_sec": 90.0,
        "min_duration_sec": 3.0,
        "aspect_ratio": "9:16",
        "allowed_formats": [".mp4"],
    },
    "instagram_carousel": {
        "max_size_mb": 8,
        "max_slides": 10,
        "min_slides": 2,
        "allowed_formats": [".jpg", ".jpeg", ".png"],
    },
    "facebook_reel": {
        "max_size_mb": 100,
        "max_duration_sec": 90.0,
        "min_duration_sec": 3.0,
        "allowed_formats": [".mp4"],
    },
    "threads_media": {
        "max_size_mb": 50,
        "max_duration_sec": 300.0,
        "allowed_formats": [".mp4", ".jpg", ".jpeg", ".png"],
    },
    "tiktok_video": {
        "max_size_mb": 500,
        "max_duration_sec": 600.0,
        "min_duration_sec": 3.0,
        "aspect_ratio": "9:16",
        "allowed_formats": [".mp4"],
    }
}


def is_r2_configured() -> bool:
    """Check if valid Cloudflare R2 credentials and public domain are configured."""
    dummy_markers = ["your_", "example", "000000", "placeholder", "xxx"]
    if not (ACCOUNT_ID and ACCESS_KEY_ID and SECRET_ACCESS_KEY and PUBLIC_URL):
        return False
    for marker in dummy_markers:
        if (
            marker in ACCOUNT_ID.lower()
            or marker in ACCESS_KEY_ID.lower()
            or marker in SECRET_ACCESS_KEY.lower()
            or marker in PUBLIC_URL.lower()
        ):
            return False
    return len(ACCESS_KEY_ID) > 10 and len(SECRET_ACCESS_KEY) > 10


def get_s3_client():
    """Build and return a boto3 S3 client configured for Cloudflare R2."""
    import boto3
    from botocore.config import Config

    endpoint_url = f"https://{ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        service_name="s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=ACCESS_KEY_ID,
        aws_secret_access_key=SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def stage_media_asset(
    file_path: str,
    destination_key: Optional[str] = None,
    content_type: Optional[str] = None
) -> MediaRef:
    """
    Primary asset stager.
    If R2 is configured, uploads the asset to Cloudflare R2 and returns a hosted MediaRef.
    If R2 is not configured, copies asset to local staging and returns hosted=False, public_url=None.
    Never invents unhosted public URLs.
    """
    src_path = Path(file_path).resolve()
    if not src_path.exists():
        raise FileNotFoundError(f"Media file not found at: {file_path}")

    filename = src_path.name
    if not destination_key:
        destination_key = f"media/{filename}"

    if not content_type:
        guessed_type, _ = mimetypes.guess_type(str(src_path))
        content_type = guessed_type or "application/octet-stream"

    # Ensure local copy in staging
    staged_copy = STAGING_DIR / filename
    if src_path != staged_copy:
        import shutil
        shutil.copy2(src_path, staged_copy)

    # Probe duration and dimensions if available
    duration_sec, width, height = probe_media_metadata(str(staged_copy))

    if is_r2_configured():
        try:
            logger.info("Uploading asset to Cloudflare R2: %s -> %s", filename, destination_key)
            client = get_s3_client()
            with open(src_path, "rb") as f:
                client.put_object(
                    Bucket=BUCKET_NAME,
                    Key=destination_key,
                    Body=f,
                    ContentType=content_type,
                )
            public_cdn_url = f"{PUBLIC_URL}/{destination_key}"
            logger.info("Asset hosted successfully on R2: %s", public_cdn_url)
            return MediaRef(
                local_path=str(staged_copy),
                public_url=public_cdn_url,
                hosted=True,
                content_type=content_type,
                duration_sec=duration_sec,
                width=width,
                height=height,
            )
        except Exception as e:
            logger.warning("R2 upload failed (%s). Asset kept locally.", e)

    # Not hosted on public CDN
    logger.info("Asset staged locally at %s (R2 not configured, hosted=False)", staged_copy)
    return MediaRef(
        local_path=str(staged_copy),
        public_url=None,
        hosted=False,
        content_type=content_type,
        duration_sec=duration_sec,
        width=width,
        height=height,
    )


def upload_media_to_r2(
    file_path: str,
    destination_key: Optional[str] = None,
    content_type: Optional[str] = None
) -> str:
    """
    Backwards-compatible wrapper returning string URL or local reference.
    Used by legacy tool callers.
    """
    ref = stage_media_asset(file_path, destination_key, content_type)
    return ref.get("public_url") or f"/media/{Path(file_path).name}"


def verify_public_url(url: Optional[str], timeout_sec: float = 10.0) -> bool:
    """
    Verify that a public URL is reachable and returns an actual media stream.
    Uses HEAD request, with fallback to ranged GET (bytes=0-1024).
    """
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return False

    try:
        with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
            resp = client.head(url)
            if resp.status_code in (200, 206):
                return True
            # Fallback to ranged GET if server rejects HEAD
            if resp.status_code in (403, 405):
                get_resp = client.get(url, headers={"Range": "bytes=0-1024"})
                return get_resp.status_code in (200, 206) and len(get_resp.content) > 0
    except Exception as e:
        logger.debug("URL verification check failed for %s: %s", url, e)
        return False
    return False


def probe_media_metadata(file_path: str) -> tuple[Optional[float], Optional[int], Optional[int]]:
    """Probe duration and dimensions of video or image file."""
    path = Path(file_path)
    if not path.exists():
        return None, None, None

    suffix = path.suffix.lower()
    if suffix in (".png", ".jpg", ".jpeg", ".webp"):
        try:
            from PIL import Image
            with Image.open(path) as img:
                return None, img.width, img.height
        except Exception:
            return None, None, None

    elif suffix in (".mp4", ".mov", ".m4v"):
        try:
            import imageio_ffmpeg
            # Use ffprobe if available via imageio_ffmpeg or python
            import subprocess
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            res = subprocess.run(
                [ffmpeg_exe, "-i", str(path)],
                stderr=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                text=True,
                check=False,
            )
            output = res.stderr
            # Extract duration (Duration: 00:00:10.50)
            import re
            dur_match = re.search(r"Duration:\s*(\d+):(\d+):([\d\.]+)", output)
            duration = None
            if dur_match:
                h, m, s = dur_match.groups()
                duration = int(h) * 3600 + int(m) * 60 + float(s)

            # Extract resolution (Stream #...: Video: ... 1080x1920)
            res_match = re.search(r",\s*(\d{3,4})x(\d{3,4})", output)
            width, height = None, None
            if res_match:
                width = int(res_match.group(1))
                height = int(res_match.group(2))

            return duration, width, height
        except Exception:
            return None, None, None

    return None, None, None


def validate_media_for_platform(
    local_path: str,
    platform: str,
    kind: str = "reel"
) -> Dict[str, Any]:
    """
    Validate local media file against platform constraints.
    Returns: {"valid": bool, "violations": List[str], "probed": Dict[str, Any]}
    """
    path = Path(local_path)
    violations = []
    if not path.exists():
        return {"valid": False, "violations": [f"File does not exist: {local_path}"], "probed": {}}

    size_mb = path.stat().st_size / (1024 * 1024)
    duration_sec, width, height = probe_media_metadata(str(path))
    probed = {
        "file_path": str(path),
        "size_mb": round(size_mb, 2),
        "duration_sec": duration_sec,
        "width": width,
        "height": height,
        "format": path.suffix.lower()
    }

    rule_key = f"{platform}_{kind}".lower()
    limits = PLATFORM_MEDIA_LIMITS.get(rule_key) or PLATFORM_MEDIA_LIMITS.get(f"{platform}_video".lower())
    if not limits:
        return {"valid": True, "violations": [], "probed": probed}

    if "allowed_formats" in limits and path.suffix.lower() not in limits["allowed_formats"]:
        violations.append(f"Format {path.suffix} not in allowed: {limits['allowed_formats']}")

    if "max_size_mb" in limits and size_mb > limits["max_size_mb"]:
        violations.append(f"Size {size_mb:.1f}MB exceeds limit of {limits['max_size_mb']}MB")

    if duration_sec is not None:
        if "max_duration_sec" in limits and duration_sec > limits["max_duration_sec"]:
            violations.append(f"Duration {duration_sec:.1f}s exceeds max {limits['max_duration_sec']}s")
        if "min_duration_sec" in limits and duration_sec < limits["min_duration_sec"]:
            violations.append(f"Duration {duration_sec:.1f}s below min {limits['min_duration_sec']}s")

    if width and height and limits.get("aspect_ratio") == "9:16":
        ratio = width / height
        expected = 9 / 16  # 0.5625
        if abs(ratio - expected) > 0.05:
            violations.append(f"Aspect ratio {width}x{height} ({ratio:.2f}) does not match 9:16 (~0.56)")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "probed": probed
    }
