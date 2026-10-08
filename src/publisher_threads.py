"""
Native Meta Threads API Publisher for AI Tech Broadcaster
Direct HTTPS calls to Threads Graph API (https://graph.threads.net/v1.0).

Conforms strictly to P4 specifications:
- Direct HTTPS calls for container creation, status polling, and publishing.
- Format mapping:
    * reel  -> media_type=VIDEO (video_url)
    * post  -> CAROUSEL (2-20 items) or IMAGE (1 item)
    * story -> TEXT post using microblog/short caption + link_attachment=source_url
- Two-step flow with backoff container polling up to 5 min.
- Text <= 500 chars (word-boundary truncate, preserve links).
- Check threads_publishing_limit before publishing.
- Fetch permalink after publish.
- If media is not hosted, safely downgrade to a TEXT post with link attachment
  (note="downgraded_to_text").
- Complete simulation mode with realistic request previews and tokens redacted.
"""

import os
import sys
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

from src.publish_types import PlatformResult, MediaRef

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

env_path = ROOT_DIR / "config" / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("publisher_threads")

THREADS_USER_ID = os.getenv("THREADS_USER_ID", "").strip()
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
THREADS_GRAPH_BASE = "https://graph.threads.net/v1.0"
THREADS_BASE = "https://graph.threads.net"


def is_threads_configured() -> bool:
    """Check if Threads User ID and Access Token are configured and valid."""
    tok = THREADS_ACCESS_TOKEN
    uid = THREADS_USER_ID
    return bool(
        tok and "YOUR_" not in tok and "THREADS" not in tok and len(tok) > 20 and
        uid and "YOUR_" not in uid
    )


def refresh_threads_token(client: Optional[httpx.Client] = None) -> Optional[str]:
    """
    Refresh long-lived Threads User Access Token using th_refresh_token grant.
    Long-lived tokens are valid for 60 days and can be refreshed after 24 hours.
    """
    global THREADS_ACCESS_TOKEN
    if not is_threads_configured():
        logger.info("[Threads] Not configured with valid token; skipping token refresh.")
        return None

    url = f"{THREADS_BASE}/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": THREADS_ACCESS_TOKEN
    }

    try:
        c = client or httpx.Client(timeout=15.0)
        resp = c.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            new_token = data.get("access_token")
            if new_token:
                THREADS_ACCESS_TOKEN = new_token
                logger.info("[Threads] Successfully refreshed Threads access token. Expires in: %s s", data.get("expires_in"))
                return new_token
        logger.warning("[Threads] Token refresh failed with status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.error("[Threads] Error refreshing Threads access token: %s", e)

    return None


def build_threads_text(post_record: dict, max_len: int = 500) -> str:
    """
    Build Threads text content adhering to the 500-character limit with
    safe word-boundary truncation.
    """
    headline = post_record.get("headline", "")
    captions_json = post_record.get("captions_json")
    format_type = post_record.get("format_type", "post")

    base_text = ""
    if captions_json:
        try:
            parsed = json.loads(captions_json)
            # Preference order: microblog > threads > short_form
            if format_type == "story" and parsed.get("microblog"):
                base_text = parsed["microblog"]
            elif parsed.get("threads"):
                base_text = parsed["threads"]
            elif parsed.get("microblog"):
                base_text = parsed["microblog"]
            elif parsed.get("short_form"):
                base_text = parsed["short_form"]
        except Exception:
            pass

    if not base_text:
        summary = post_record.get("summary_text") or headline
        base_text = f"{headline}\n\n{summary}\n\n#AI #TechNews #Innovation"

    if len(base_text) <= max_len:
        return base_text

    # Truncate on word boundary
    truncated = base_text[:max_len - 3]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return f"{truncated}..."


def check_threads_rate_limit(client: httpx.Client, user_id: str, access_token: str) -> bool:
    """
    Check Threads publishing limit. Returns True if publishing is allowed, False if exhausted.
    """
    url = f"{THREADS_GRAPH_BASE}/{user_id}/threads_publishing_limit"
    params = {
        "fields": "quota_usage,config",
        "access_token": access_token
    }
    try:
        resp = client.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json().get("data", [{}])[0]
            usage = data.get("quota_usage", 0)
            config = data.get("config", {})
            quota_total = config.get("quota_total", 250)
            if usage >= quota_total:
                logger.warning("[Threads] Publishing quota exhausted: %d/%d used", usage, quota_total)
                return False
            logger.info("[Threads] Quota status: %d/%d used", usage, quota_total)
            return True
        logger.warning("[Threads] Could not check publishing limit (%d): %s", resp.status_code, resp.text)
        return True  # If endpoint fails or scope missing, don't fail immediately
    except Exception as e:
        logger.warning("[Threads] Error checking publishing limit: %s", e)
        return True


def poll_container_status(
    client: httpx.Client,
    container_id: str,
    access_token: str,
    max_wait_sec: int = 300,
    poll_interval: int = 4
) -> Dict[str, Any]:
    """
    Poll /{container_id}?fields=status,error_message until FINISHED, ERROR, or timeout.
    """
    url = f"{THREADS_GRAPH_BASE}/{container_id}"
    params = {
        "fields": "status,error_message",
        "access_token": access_token
    }
    start = time.time()
    backoff = poll_interval

    while time.time() - start < max_wait_sec:
        try:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                logger.info("[Threads] Container %s status: %s (elapsed %.1fs)", container_id, status, time.time() - start)
                if status == "FINISHED":
                    return {"success": True, "status": "FINISHED"}
                if status in ("ERROR", "EXPIRED"):
                    return {
                        "success": False,
                        "status": status,
                        "error_message": data.get("error_message", f"Container {status}")
                    }
            elif resp.status_code == 400:
                return {"success": False, "status": "ERROR", "error_message": resp.text}
        except Exception as e:
            logger.warning("[Threads] Polling error for container %s: %s", container_id, e)

        time.sleep(backoff)
        backoff = min(backoff + 2, 15)

    return {"success": False, "status": "TIMEOUT", "error_message": f"Container did not finish within {max_wait_sec}s"}


def fetch_permalink(client: httpx.Client, media_id: str, access_token: str) -> Optional[str]:
    """Fetch the real permalink for a published Threads media object."""
    url = f"{THREADS_GRAPH_BASE}/{media_id}"
    params = {
        "fields": "permalink,id",
        "access_token": access_token
    }
    try:
        resp = client.get(url, params=params)
        if resp.status_code == 200:
            return resp.json().get("permalink")
    except Exception as e:
        logger.warning("[Threads] Failed to resolve permalink for %s: %s", media_id, e)
    return None


def publish_to_threads(
    post_record: dict,
    media: Optional[List[MediaRef]] = None,
    client: Optional[httpx.Client] = None
) -> PlatformResult:
    """
    Publish a post to Meta Threads adhering to the Threads API contract.

    Handles:
    - reel  -> VIDEO
    - post  -> CAROUSEL (2-20 items) or IMAGE (1 item)
    - story -> TEXT with link attachment
    - Downgrade to TEXT when media is unhosted
    - Dual mode: simulate vs live
    """
    media_list = media or []
    format_type = post_record.get("format_type", "post")
    headline = post_record.get("headline", "Tech Update")
    source_url = post_record.get("source_url")
    publish_mode = os.getenv("PUBLISH_MODE", "simulate").lower()

    text_content = build_threads_text(post_record, max_len=500)

    # Check media hosting status
    has_hosted_media = any(m.get("hosted") and m.get("public_url") for m in media_list)
    downgrade_to_text = False
    effective_media_type = "TEXT"

    if format_type == "story":
        effective_media_type = "TEXT"
    elif format_type == "reel":
        if has_hosted_media:
            effective_media_type = "VIDEO"
        else:
            downgrade_to_text = True
            effective_media_type = "TEXT"
    elif format_type == "post":
        hosted_items = [m for m in media_list if m.get("hosted") and m.get("public_url")]
        if len(hosted_items) > 1:
            effective_media_type = "CAROUSEL"
        elif len(hosted_items) == 1:
            effective_media_type = "IMAGE"
        else:
            downgrade_to_text = True
            effective_media_type = "TEXT"

    # --- SIMULATION MODE ---
    if publish_mode == "simulate" or not is_threads_configured():
        if publish_mode == "live" and not is_threads_configured():
            return PlatformResult(
                platform="threads",
                status="failed",
                mode="live",
                error_code="NOT_CONFIGURED",
                error_message="THREADS_USER_ID or THREADS_ACCESS_TOKEN is missing or placeholder in live mode.",
                attempts=1,
                latency_ms=0
            )

        sim_id = f"th_sim_{int(time.time())}"
        request_preview: Dict[str, Any] = {
            "endpoint": f"{THREADS_GRAPH_BASE}/{{user_id}}/threads",
            "media_type": effective_media_type,
            "text": text_content,
            "link_attachment": source_url if (effective_media_type == "TEXT" and source_url) else None,
            "media_count": len(media_list),
            "downgraded_to_text": downgrade_to_text
        }
        if effective_media_type == "VIDEO" and has_hosted_media:
            request_preview["video_url"] = media_list[0].get("public_url")
        elif effective_media_type == "IMAGE" and has_hosted_media:
            request_preview["image_url"] = media_list[0].get("public_url")
        elif effective_media_type == "CAROUSEL":
            request_preview["carousel_items"] = [
                m.get("public_url") for m in media_list if m.get("hosted") and m.get("public_url")
            ]

        logger.info("[Threads SIMULATE] %s -> %s (downgraded=%s)", format_type, effective_media_type, downgrade_to_text)
        return PlatformResult(
            platform="threads",
            status="simulated",
            mode="simulated",
            remote_id=sim_id,
            permalink=f"https://www.threads.net/@user/post/{sim_id}",
            attempts=1,
            latency_ms=10,
            note="downgraded_to_text" if downgrade_to_text else None,
            request_preview=request_preview
        )

    # --- LIVE MODE ---
    start_time = time.time()
    c = client or httpx.Client(timeout=30.0)
    user_id = THREADS_USER_ID
    token = THREADS_ACCESS_TOKEN

    try:
        # 1. Rate Limit Check
        if not check_threads_rate_limit(c, user_id, token):
            return PlatformResult(
                platform="threads",
                status="skipped",
                mode="live",
                error_code="THREADS_RATE_LIMIT",
                error_message="Threads publishing quota is currently exhausted.",
                attempts=1,
                latency_ms=int((time.time() - start_time) * 1000)
            )

        # 2. Container Creation Flow
        container_url = f"{THREADS_GRAPH_BASE}/{user_id}/threads"

        if effective_media_type == "TEXT":
            payload = {
                "media_type": "TEXT",
                "text": text_content,
                "access_token": token
            }
            if source_url:
                payload["link_attachment"] = source_url

            resp = c.post(container_url, data=payload)
            if resp.status_code != 200:
                return PlatformResult(
                    platform="threads",
                    status="failed",
                    mode="live",
                    error_code="CONTAINER_CREATE_FAILED",
                    error_message=f"Text container creation failed: {resp.text}",
                    attempts=1,
                    latency_ms=int((time.time() - start_time) * 1000)
                )
            container_id = resp.json().get("id")

        elif effective_media_type == "IMAGE":
            hosted_media = next((m for m in media_list if m.get("hosted") and m.get("public_url")), None)
            payload = {
                "media_type": "IMAGE",
                "image_url": hosted_media["public_url"],
                "text": text_content,
                "access_token": token
            }
            resp = c.post(container_url, data=payload)
            if resp.status_code != 200:
                return PlatformResult(
                    platform="threads",
                    status="failed",
                    mode="live",
                    error_code="CONTAINER_CREATE_FAILED",
                    error_message=f"Image container creation failed: {resp.text}",
                    attempts=1,
                    latency_ms=int((time.time() - start_time) * 1000)
                )
            container_id = resp.json().get("id")

        elif effective_media_type == "VIDEO":
            hosted_media = next((m for m in media_list if m.get("hosted") and m.get("public_url")), None)
            payload = {
                "media_type": "VIDEO",
                "video_url": hosted_media["public_url"],
                "text": text_content,
                "access_token": token
            }
            resp = c.post(container_url, data=payload)
            if resp.status_code != 200:
                return PlatformResult(
                    platform="threads",
                    status="failed",
                    mode="live",
                    error_code="CONTAINER_CREATE_FAILED",
                    error_message=f"Video container creation failed: {resp.text}",
                    attempts=1,
                    latency_ms=int((time.time() - start_time) * 1000)
                )
            container_id = resp.json().get("id")

        elif effective_media_type == "CAROUSEL":
            hosted_items = [m for m in media_list if m.get("hosted") and m.get("public_url")][:20]
            child_ids = []

            for idx, item in enumerate(hosted_items):
                is_vid = item.get("content_type", "").startswith("video") or item.get("local_path", "").endswith(".mp4")
                child_payload = {
                    "media_type": "VIDEO" if is_vid else "IMAGE",
                    "is_carousel_item": "true",
                    "access_token": token
                }
                if is_vid:
                    child_payload["video_url"] = item["public_url"]
                else:
                    child_payload["image_url"] = item["public_url"]

                child_resp = c.post(container_url, data=child_payload)
                if child_resp.status_code != 200:
                    return PlatformResult(
                        platform="threads",
                        status="failed",
                        mode="live",
                        error_code="CAROUSEL_ITEM_CREATE_FAILED",
                        error_message=f"Failed to create carousel item #{idx}: {child_resp.text}",
                        attempts=1,
                        latency_ms=int((time.time() - start_time) * 1000)
                    )
                child_id = child_resp.json().get("id")
                # Wait for child item to finish processing
                poll_res = poll_container_status(c, child_id, token, max_wait_sec=120)
                if not poll_res["success"]:
                    return PlatformResult(
                        platform="threads",
                        status="failed",
                        mode="live",
                        error_code="CAROUSEL_ITEM_PROCESSING_FAILED",
                        error_message=f"Carousel item #{idx} failed processing: {poll_res.get('error_message')}",
                        attempts=1,
                        latency_ms=int((time.time() - start_time) * 1000)
                    )
                child_ids.append(child_id)

            carousel_payload = {
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "text": text_content,
                "access_token": token
            }
            resp = c.post(container_url, data=carousel_payload)
            if resp.status_code != 200:
                return PlatformResult(
                    platform="threads",
                    status="failed",
                    mode="live",
                    error_code="CAROUSEL_CONTAINER_CREATE_FAILED",
                    error_message=f"Carousel container creation failed: {resp.text}",
                    attempts=1,
                    latency_ms=int((time.time() - start_time) * 1000)
                )
            container_id = resp.json().get("id")

        else:
            return PlatformResult(
                platform="threads",
                status="failed",
                mode="live",
                error_code="UNSUPPORTED_MEDIA_TYPE",
                error_message=f"Unsupported effective media type: {effective_media_type}",
                attempts=1,
                latency_ms=int((time.time() - start_time) * 1000)
            )

        # 3. Poll container until ready
        poll_res = poll_container_status(c, container_id, token, max_wait_sec=300)
        if not poll_res["success"]:
            return PlatformResult(
                platform="threads",
                status="failed",
                mode="live",
                error_code=poll_res.get("status", "PROCESSING_FAILED"),
                error_message=poll_res.get("error_message", "Container processing failed"),
                attempts=1,
                latency_ms=int((time.time() - start_time) * 1000)
            )

        # 4. Publish Container
        publish_url = f"{THREADS_GRAPH_BASE}/{user_id}/threads_publish"
        publish_payload = {
            "creation_id": container_id,
            "access_token": token
        }
        pub_resp = c.post(publish_url, data=publish_payload)
        if pub_resp.status_code != 200:
            return PlatformResult(
                platform="threads",
                status="failed",
                mode="live",
                error_code="PUBLISH_FAILED",
                error_message=f"Publishing container failed: {pub_resp.text}",
                attempts=1,
                latency_ms=int((time.time() - start_time) * 1000)
            )

        media_id = pub_resp.json().get("id")
        permalink = fetch_permalink(c, media_id, token) or f"https://www.threads.net/post/{media_id}"

        return PlatformResult(
            platform="threads",
            status="published",
            mode="live",
            remote_id=media_id,
            permalink=permalink,
            attempts=1,
            latency_ms=int((time.time() - start_time) * 1000),
            note="downgraded_to_text" if downgrade_to_text else None
        )

    except Exception as e:
        logger.exception("[Threads] Unexpected exception during publish: %s", e)
        return PlatformResult(
            platform="threads",
            status="failed",
            mode="live",
            error_code="UNEXPECTED_ERROR",
            error_message=str(e),
            attempts=1,
            latency_ms=int((time.time() - start_time) * 1000)
        )
