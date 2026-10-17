"""
Native X (formerly Twitter) API v2 & Chunked Video Publisher for AI Tech Broadcaster
Conforms to official X Developer Platform standards:
- X API v2 Tweet Creation (`POST https://api.x.com/2/tweets`)
- Chunked Media Upload v1.1 (`POST https://upload.twitter.com/1.1/media/upload.json`)
  * INIT -> APPEND (2MB segments) -> FINALIZE -> STATUS asynchronous polling
- Dual Auth: OAuth 1.0a User Context (HMAC-SHA1) & OAuth 2.0 User Bearer
- Automatic thread bursting for insights exceeding 280 characters
- Full simulation mode with realistic request previews when keys are pending
"""

import os
import sys
import time
import json
import base64
import hmac
import hashlib
import urllib.parse
import secrets
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import httpx
from dotenv import load_dotenv

from src.publish_types import PlatformResult, MediaRef

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

env_path = ROOT_DIR / "config" / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("publisher_x")

X_API_BASE = "https://api.x.com/2"
X_UPLOAD_BASE = "https://upload.twitter.com/1.1"

# Environment configuration keys
X_API_KEY = os.getenv("X_API_KEY", "").strip()
X_API_SECRET = os.getenv("X_API_SECRET", "").strip()
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "").strip()
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "").strip()
X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "").strip()
X_USERNAME = os.getenv("X_USERNAME", "Eraof_Ai").strip().lstrip("@")


def reload_x_credentials() -> Dict[str, Any]:
    """Reload X credentials from config/.env and environment."""
    global X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET, X_BEARER_TOKEN, X_USERNAME
    load_dotenv(dotenv_path=env_path, override=True)
    X_API_KEY = os.getenv("X_API_KEY", "").strip()
    X_API_SECRET = os.getenv("X_API_SECRET", "").strip()
    X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "").strip()
    X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "").strip()
    X_BEARER_TOKEN = os.getenv("X_BEARER_TOKEN", "").strip()
    X_USERNAME = os.getenv("X_USERNAME", "Eraof_Ai").strip().lstrip("@")
    return {
        "configured": is_x_configured(),
        "has_oauth1": bool(X_API_KEY and X_API_SECRET and X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET),
        "has_bearer": bool(X_BEARER_TOKEN),
        "username": X_USERNAME or "Eraof_Ai",
    }


def is_x_configured() -> bool:
    """Check if valid X credentials (OAuth 1.0a or Bearer) are configured."""
    # Priority 1: OAuth 1.0a User Context (required for media uploads)
    has_oauth1 = bool(
        X_API_KEY and "YOUR_" not in X_API_KEY and len(X_API_KEY) >= 10 and
        X_API_SECRET and "YOUR_" not in X_API_SECRET and len(X_API_SECRET) >= 20 and
        X_ACCESS_TOKEN and "YOUR_" not in X_ACCESS_TOKEN and len(X_ACCESS_TOKEN) >= 20 and
        X_ACCESS_TOKEN_SECRET and "YOUR_" not in X_ACCESS_TOKEN_SECRET and len(X_ACCESS_TOKEN_SECRET) >= 20
    )
    # Priority 2: OAuth 2.0 User Bearer Token
    has_bearer = bool(
        X_BEARER_TOKEN and "YOUR_" not in X_BEARER_TOKEN and len(X_BEARER_TOKEN) >= 20
    )
    return has_oauth1 or has_bearer


def build_oauth1_header(
    method: str,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    token: Optional[str] = None,
    token_secret: Optional[str] = None
) -> str:
    """Generate an authentic RFC 5849 OAuth 1.0a Authorization header without external dependencies."""
    k = api_key or X_API_KEY
    ks = api_secret or X_API_SECRET
    tok = token or X_ACCESS_TOKEN
    ts = token_secret or X_ACCESS_TOKEN_SECRET

    oauth_params = {
        "oauth_consumer_key": k,
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": tok,
        "oauth_version": "1.0",
    }

    # Combine query/form params with oauth params for base string
    all_params = {}
    if params:
        for key, val in params.items():
            if isinstance(val, (str, int, float)):
                all_params[urllib.parse.quote(str(key), safe="")] = urllib.parse.quote(str(val), safe="")
    for key, val in oauth_params.items():
        all_params[urllib.parse.quote(str(key), safe="")] = urllib.parse.quote(str(val), safe="")

    sorted_encoded_params = "&".join(f"{k}={all_params[k]}" for k in sorted(all_params.keys()))
    base_url = url.split("?")[0]
    signature_base = f"{method.upper()}&{urllib.parse.quote(base_url, safe='')}&{urllib.parse.quote(sorted_encoded_params, safe='')}"

    signing_key = f"{urllib.parse.quote(ks, safe='')}&{urllib.parse.quote(ts, safe='')}".encode("utf-8")
    hashed = hmac.new(signing_key, signature_base.encode("utf-8"), hashlib.sha1)
    oauth_params["oauth_signature"] = base64.b64encode(hashed.digest()).decode("utf-8")

    header_parts = [
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    ]
    return f"OAuth {', '.join(header_parts)}"


def diagnose_x_connection(client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    """Diagnose X API connection and permissions via GET /2/users/me."""
    reload_x_credentials()
    if not is_x_configured():
        return {
            "configured": False,
            "status_badge": "NEEDS X API KEYS",
            "mode": "simulated",
            "account": f"@{X_USERNAME} (unlinked)",
            "diagnostic": "Provide X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET in Configure Token to enable live X publishing.",
        }

    c = client or httpx.Client(timeout=10.0)
    headers = {}
    if X_API_KEY and X_ACCESS_TOKEN:
        url = f"{X_API_BASE}/users/me"
        headers["Authorization"] = build_oauth1_header("GET", url)
    else:
        url = f"{X_API_BASE}/users/me"
        headers["Authorization"] = f"Bearer {X_BEARER_TOKEN}"

    try:
        resp = c.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            user_handle = data.get("username", X_USERNAME)
            name = data.get("name", "Era of AI")
            return {
                "configured": True,
                "status_badge": "LIVE CONNECTED",
                "mode": "live",
                "account": f"@{user_handle} ({name})",
                "diagnostic": f"Verified live connection to X account @{user_handle}. API v2 & Chunked Video Ready.",
            }
        return {
            "configured": True,
            "status_badge": f"HTTP {resp.status_code}",
            "mode": "simulated",
            "account": f"@{X_USERNAME}",
            "diagnostic": f"X API returned {resp.status_code}: {resp.text[:120]}",
        }
    except Exception as e:
        return {
            "configured": True,
            "status_badge": "CONNECTION ERROR",
            "mode": "simulated",
            "account": f"@{X_USERNAME}",
            "diagnostic": f"Failed to reach X API: {e}",
        }


def upload_video_to_x(
    video_path: Path,
    client: Optional[httpx.Client] = None,
    timeout_sec: int = 180
) -> Optional[str]:
    """
    Upload an MP4 video using the 4-phase chunked upload sequence on upload.twitter.com/1.1/media/upload.json:
    Phase 1: INIT -> returns media_id
    Phase 2: APPEND -> chunks up to 2MB sequentially
    Phase 3: FINALIZE -> verifies processing status
    Phase 4: STATUS -> polls until state == 'succeeded'
    """
    if not video_path.exists():
        logger.error("[X] Video file missing: %s", video_path)
        return None

    total_bytes = video_path.stat().st_size
    media_type = "video/mp4"
    c = client or httpx.Client(timeout=30.0)
    upload_url = f"{X_UPLOAD_BASE}/media/upload.json"

    try:
        # Phase 1: INIT
        init_params = {
            "command": "INIT",
            "total_bytes": str(total_bytes),
            "media_type": media_type,
            "media_category": "tweet_video",
        }
        init_headers = {"Authorization": build_oauth1_header("POST", upload_url, params=init_params)}
        init_resp = c.post(upload_url, data=init_params, headers=init_headers)
        if init_resp.status_code not in (200, 201, 202):
            logger.error("[X] Video INIT failed (%s): %s", init_resp.status_code, init_resp.text)
            return None

        media_id = init_resp.json().get("media_id_string")
        if not media_id:
            logger.error("[X] Video INIT returned no media_id: %s", init_resp.text)
            return None
        logger.info("[X] Video INIT success. media_id=%s (size=%d bytes)", media_id, total_bytes)

        # Phase 2: APPEND in 2MB chunks
        chunk_size = 2 * 1024 * 1024
        segment_index = 0
        with open(video_path, "rb") as f:
            while True:
                chunk_data = f.read(chunk_size)
                if not chunk_data:
                    break
                append_params = {
                    "command": "APPEND",
                    "media_id": media_id,
                    "segment_index": str(segment_index),
                }
                append_headers = {"Authorization": build_oauth1_header("POST", upload_url, params=append_params)}
                files = {"media": ("chunk.mp4", chunk_data, media_type)}
                append_resp = c.post(upload_url, data=append_params, files=files, headers=append_headers)
                if append_resp.status_code not in (200, 201, 202, 204):
                    logger.error("[X] Video APPEND segment %d failed (%s): %s", segment_index, append_resp.status_code, append_resp.text)
                    return None
                segment_index += 1

        # Phase 3: FINALIZE
        finalize_params = {
            "command": "FINALIZE",
            "media_id": media_id,
        }
        finalize_headers = {"Authorization": build_oauth1_header("POST", upload_url, params=finalize_params)}
        fin_resp = c.post(upload_url, data=finalize_params, headers=finalize_headers)
        if fin_resp.status_code not in (200, 201, 202):
            logger.error("[X] Video FINALIZE failed (%s): %s", fin_resp.status_code, fin_resp.text)
            return None

        fin_data = fin_resp.json()
        proc_info = fin_data.get("processing_info")
        if not proc_info:
            logger.info("[X] Video finalized immediately without asynchronous transcoding.")
            return media_id

        # Phase 4: STATUS Polling loop
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            state = proc_info.get("state")
            if state == "succeeded":
                logger.info("[X] Video transcoding succeeded for media_id=%s", media_id)
                return media_id
            if state == "failed":
                err = proc_info.get("error", {})
                logger.error("[X] Video transcoding failed: %s", err)
                return None

            wait_sec = max(2, int(proc_info.get("check_after_secs", 4)))
            time.sleep(wait_sec)

            status_params = {
                "command": "STATUS",
                "media_id": media_id,
            }
            status_headers = {"Authorization": build_oauth1_header("GET", upload_url, params=status_params)}
            stat_resp = c.get(upload_url, params=status_params, headers=status_headers)
            if stat_resp.status_code in (200, 201, 202):
                proc_info = stat_resp.json().get("processing_info", {})
            else:
                logger.warning("[X] STATUS check returned %s; continuing poll...", stat_resp.status_code)

        logger.error("[X] Video transcoding timed out after %d seconds.", timeout_sec)
        return None

    except Exception as e:
        logger.exception("[X] Unexpected exception during video upload: %s", e)
        return None


def format_tweet_text(headline: str, hook: str, url: str, lab: str = "Google") -> Tuple[str, List[str]]:
    """
    Format headline + hook + URL into a punchy viral X post (<= 280 chars),
    and split any extended breakdown text into a follow-up thread list.
    """
    clean_hl = headline.strip()
    tag = f"#{lab.replace(' ', '')} #AI #EraOfAI"
    
    # Primary tweet structure: Headline + Clean Link + Tags
    first_tweet = f"{clean_hl}\n\n{url}\n\n{tag}".strip()
    if len(first_tweet) > 280:
        avail = 280 - len(f"\n\n{url}\n\n{tag}") - 3
        first_tweet = f"{clean_hl[:avail]}...\n\n{url}\n\n{tag}"

    # Thread replies for detailed technical narrative
    thread_parts: List[str] = []
    if hook and len(hook) > 20:
        words = hook.split()
        curr: List[str] = []
        for w in words:
            curr.append(w)
            if len(" ".join(curr)) > 260:
                curr.pop()
                thread_parts.append(" ".join(curr))
                curr = [w]
        if curr:
            thread_parts.append(" ".join(curr))

    return first_tweet, thread_parts


def publish_to_x(
    post_record: Dict[str, Any],
    media_refs: Optional[List[MediaRef]] = None,
    client: Optional[httpx.Client] = None
) -> PlatformResult:
    """
    Publish a broadcast to X:
    - If video media is present, executes 4-phase chunked upload to attach Full HD video
    - Calls X API v2 `POST https://api.x.com/2/tweets`
    - Creates follow-up thread tweets for long-form context
    - Falls back to simulation mode if credentials are unconfigured or PUBLISH_MODE=simulate
    """
    start_t = time.time()
    reload_x_credentials()
    publish_mode = os.getenv("PUBLISH_MODE", "live").lower()
    post_id = post_record.get("id", int(time.time()))
    headline = post_record.get("headline") or "Frontier AI Intelligence Briefing"
    source_url = post_record.get("source_url") or "https://x.com/Eraof_Ai"
    hook = post_record.get("hook_narration") or post_record.get("body_narration") or ""

    primary_text, thread_texts = format_tweet_text(headline, hook, source_url)

    # Simulation fallback
    if not is_x_configured() or publish_mode == "simulate":
        sim_id = f"1919{int(time.time())}"
        permalink = f"https://x.com/{X_USERNAME}/status/{sim_id}"
        logger.info("[X] SIMULATED publish for post #%s -> %s", post_id, permalink)
        return PlatformResult(
            platform="x",
            status="simulated",
            mode="simulated",
            remote_id=sim_id,
            permalink=permalink,
            attempts=1,
            latency_ms=18,
            note="simulated_x_v2_tweet"
        )

    # Identify local video file
    local_files = [
        m.get("local_path") for m in (media_refs or [])
        if m.get("local_path") and Path(m["local_path"]).exists() and str(m["local_path"]).endswith(".mp4")
    ]
    if not local_files and post_record.get("media_path") and Path(post_record["media_path"]).exists():
        local_files = [post_record["media_path"]]

    c = client or httpx.Client(timeout=45.0)

    try:
        # Step 1: Upload video if available
        media_id = None
        if local_files:
            video_p = Path(local_files[0])
            logger.info("[X] Initiating chunked video upload for %s (%d bytes)", video_p.name, video_p.stat().st_size)
            media_id = upload_video_to_x(video_p, client=c)

        # Step 2: Post primary tweet via API v2
        tweet_url = f"{X_API_BASE}/tweets"
        tweet_payload: Dict[str, Any] = {"text": primary_text}
        if media_id:
            tweet_payload["media"] = {"media_ids": [media_id]}

        headers = {"Content-Type": "application/json"}
        if X_API_KEY and X_ACCESS_TOKEN:
            headers["Authorization"] = build_oauth1_header("POST", tweet_url)
        else:
            headers["Authorization"] = f"Bearer {X_BEARER_TOKEN}"

        resp = c.post(tweet_url, json=tweet_payload, headers=headers)
        if resp.status_code not in (200, 201):
            err_msg = f"X API v2 error ({resp.status_code}): {resp.text}"
            logger.error("[X] %s", err_msg)
            return PlatformResult(
                platform="x",
                status="failed",
                mode="live",
                error_code="TWEET_CREATION_FAILED",
                error_message=err_msg,
                attempts=1,
                latency_ms=int((time.time() - start_t) * 1000),
            )

        resp_data = resp.json().get("data", {})
        tweet_id = resp_data.get("id")
        permalink = f"https://x.com/{X_USERNAME}/status/{tweet_id}"
        logger.info("[X] Primary tweet published successfully: %s", permalink)

        # Step 3: Publish follow-up thread tweets if text was split
        prev_id = tweet_id
        for t_idx, th_txt in enumerate(thread_parts):
            try:
                th_payload = {
                    "text": th_txt,
                    "reply": {"in_reply_to_tweet_id": prev_id}
                }
                th_headers = {"Content-Type": "application/json"}
                if X_API_KEY and X_ACCESS_TOKEN:
                    th_headers["Authorization"] = build_oauth1_header("POST", tweet_url)
                else:
                    th_headers["Authorization"] = f"Bearer {X_BEARER_TOKEN}"
                th_resp = c.post(tweet_url, json=th_payload, headers=th_headers)
                if th_resp.status_code in (200, 201):
                    prev_id = th_resp.json().get("data", {}).get("id")
            except Exception as th_err:
                logger.warning("[X] Thread reply %d skipped: %s", t_idx, th_err)

        return PlatformResult(
            platform="x",
            status="published",
            mode="live",
            remote_id=str(tweet_id),
            permalink=permalink,
            attempts=1,
            latency_ms=int((time.time() - start_t) * 1000),
            note="x_v2_video_tweet" if media_id else "x_v2_text_tweet"
        )

    except Exception as e:
        logger.exception("[X] Unexpected error during X publishing: %s", e)
        return PlatformResult(
            platform="x",
            status="failed",
            mode="live",
            error_code="UNEXPECTED_ERROR",
            error_message=str(e),
            attempts=1,
            latency_ms=int((time.time() - start_t) * 1000),
        )
