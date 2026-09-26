"""
Postiz Social Media Publisher Module
Integrates with Postiz Public API (Cloud or Self-Hosted Docker instance)
Supports:
- Local & remote video uploads (MP4 vertical 9:16 reels)
- Multi-image carousel uploads
- Automated integration discovery (Instagram, Facebook, TikTok, YouTube, X, LinkedIn)
- Immediate publishing ("now") with rich media and hashtags
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

env_path = root_dir / "config" / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("publisher_postiz")

POSTIZ_API_KEY = os.getenv("POSTIZ_API_KEY", "")
# Default to Cloud API, or http://localhost:3000/api for self-hosted Postiz
POSTIZ_API_URL = os.getenv("POSTIZ_API_URL", "https://api.postiz.com").rstrip("/")


def get_postiz_headers() -> Dict[str, str]:
    """Return standard headers for Postiz Public API."""
    key = POSTIZ_API_KEY.strip()
    # Postiz supports 'Authorization: <api-key>' or 'Authorization: Bearer <api-key>'
    return {
        "Authorization": key if key.startswith("Bearer ") else f"Bearer {key}",
        "Accept": "application/json"
    }


def is_postiz_configured() -> bool:
    """Check if Postiz API key is set and not a placeholder."""
    return bool(POSTIZ_API_KEY and "POSTIZ" not in POSTIZ_API_KEY and len(POSTIZ_API_KEY) > 8)


def get_connected_integrations() -> List[Dict[str, Any]]:
    """
    Fetch all active social integrations connected in Postiz.
    Endpoint: GET /public/v1/integrations
    """
    if not is_postiz_configured():
        logger.warning("Postiz API key is not configured.")
        return []

    url = f"{POSTIZ_API_URL}/public/v1/integrations"
    try:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(url, headers=get_postiz_headers())
            if resp.status_code == 200:
                data = resp.json()
                logger.info("Retrieved %d active Postiz integrations.", len(data))
                return data
            else:
                logger.error("Failed to fetch Postiz integrations (%s): %s", resp.status_code, resp.text)
                return []
    except Exception as e:
        logger.exception("Error connecting to Postiz API at %s: %s", url, e)
        return []


def upload_media_to_postiz(media_path_or_url: str) -> Optional[Dict[str, str]]:
    """
    Upload a media asset (MP4 video or image) to Postiz.
    Supports:
    1. Local file path via multipart/form-data POST /public/v1/upload
    2. Public remote URL via POST /public/v1/upload-from-url
    Returns: {"id": "...", "path": "..."} or None
    """
    if not is_postiz_configured():
        logger.warning("Postiz API key not configured; skipping media upload.")
        return None

    # Check if this is a local file
    local_path = Path(media_path_or_url)
    if not local_path.is_absolute():
        local_path = root_dir / media_path_or_url

    headers = get_postiz_headers()

    # Case 1: Local file upload via multipart/form-data
    if local_path.exists() and local_path.is_file():
        upload_url = f"{POSTIZ_API_URL}/public/v1/upload"
        mime_type = "video/mp4" if local_path.suffix.lower() == ".mp4" else "image/png"
        try:
            with open(local_path, "rb") as f:
                files = {"file": (local_path.name, f, mime_type)}
                # httpx manages boundary automatically when headers do not set Content-Type
                upload_headers = {k: v for k, v in headers.items() if k.lower() != "content-type"}
                with httpx.Client(timeout=60.0) as client:
                    resp = client.post(upload_url, files=files, headers=upload_headers)
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        logger.info("Successfully uploaded local media to Postiz: %s -> %s", local_path.name, data.get("path"))
                        return {"id": data.get("id", ""), "path": data.get("path", "")}
                    else:
                        logger.warning("Postiz local upload returned %s: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.exception("Exception uploading local file to Postiz: %s", e)

    # Case 2: Remote URL upload via upload-from-url
    if media_path_or_url.startswith("http://") or media_path_or_url.startswith("https://"):
        upload_url = f"{POSTIZ_API_URL}/public/v1/upload-from-url"
        try:
            with httpx.Client(timeout=45.0) as client:
                json_headers = {**headers, "Content-Type": "application/json"}
                resp = client.post(upload_url, json={"url": media_path_or_url}, headers=json_headers)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    logger.info("Successfully uploaded remote media to Postiz: %s", data.get("path"))
                    return {"id": data.get("id", ""), "path": data.get("path", "")}
                else:
                    logger.warning("Postiz upload-from-url returned %s: %s", resp.status_code, resp.text)
        except Exception as e:
            logger.exception("Exception uploading from URL to Postiz: %s", e)

    return None


def publish_to_postiz(post_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Publish a post record to Postiz across all connected channels.
    Supports MP4 video reels, carousel graphics, and text updates.
    """
    if not is_postiz_configured():
        raise RuntimeError("POSTIZ_API_KEY is not configured in config/.env. Please configure your Postiz API key.")

    # 1. Fetch connected integrations
    integrations = get_connected_integrations()
    if not integrations:
        raise RuntimeError("No connected social integrations found in Postiz. Please connect at least one account (Instagram, Facebook, etc.) in your Postiz dashboard.")

    # 2. Extract captions
    captions = {}
    try:
        captions = json.loads(post_record.get("captions_json") or "{}")
    except Exception:
        pass

    headline = post_record.get("headline", "AI Breakthrough Update")
    caption_text = captions.get("short_form") or f"{headline}\n\n#AI #TechNews #Innovation #MachineLearning"
    source_url = post_record.get("source_url", "")
    if source_url and source_url not in caption_text:
        caption_text = f"{caption_text}\n\nSource: {source_url}"

    # 3. Handle media (video or graphic)
    media_url = post_record.get("media_url") or ""
    uploaded_media = None
    if media_url:
        uploaded_media = upload_media_to_postiz(media_url)

    # 4. Construct Postiz post items for each integration
    posts_payload = []
    for integ in integrations:
        integ_id = integ.get("id")
        integ_type = integ.get("identifier") or integ.get("type", "generic")
        
        post_item: Dict[str, Any] = {
            "integration": {"id": integ_id},
            "value": [
                {
                    "content": caption_text,
                    "image": [uploaded_media] if uploaded_media else []
                }
            ],
            "settings": {
                "__type": integ_type
            }
        }
        posts_payload.append(post_item)

    # 5. Dispatch to POST /public/v1/posts
    submit_url = f"{POSTIZ_API_URL}/public/v1/posts"
    body = {
        "type": "now",
        "shortLink": False,
        "tags": ["AI", "TechNews"],
        "posts": posts_payload
    }

    headers = {**get_postiz_headers(), "Content-Type": "application/json"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(submit_url, json=body, headers=headers)
        if resp.status_code not in (200, 201):
            logger.error("Postiz publish failed (%s): %s", resp.status_code, resp.text)
            raise RuntimeError(f"Postiz publish error {resp.status_code}: {resp.text}")

        data = resp.json()
        logger.info("Successfully published via Postiz: %s", data)
        return {
            "status": "success",
            "provider": "postiz",
            "id": data.get("id") or data.get("postId") or "postiz_ok",
            "details": data,
            "integrations_count": len(integrations)
        }
