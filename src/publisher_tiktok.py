"""
Native TikTok Content Posting API v2 Publisher for AI Tech Broadcaster
Direct HTTPS calls to https://open.tiktokapis.com/v2 for autonomous Reel publishing.

Conforms strictly to P5 specifications:
- Format check: Only format_type == "reel" is eligible; others -> skipped("FORMAT_UNSUPPORTED").
- Token lifecycle: Manages access token and refresh token via /v2/oauth/token/
  persisting securely to storage/tiktok_token.json (chmod 600).
- Creator info query: POST /v2/post/publish/creator_info/query/ before posting.
  Selects privacy level (prefers PUBLIC_TO_EVERYONE; falls back to SELF_ONLY if unaudited).
- Video Init + Chunked Upload: POST /v2/post/publish/video/init/ with is_aigc=True,
  followed by chunked PUT upload (5-64 MB per chunk).
- Status Polling: POST /v2/post/publish/status/fetch/ until PUBLISH_COMPLETE or FAILED.
- Detailed error code mapping without retrying policy rejections.
- Complete simulation mode with realistic creator_info -> init -> upload -> status flow.
"""

import os
import sys
import time
import math
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import re
import urllib.parse
import httpx
from dotenv import load_dotenv

from src.publish_types import PlatformResult, MediaRef

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

env_path = ROOT_DIR / "config" / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("publisher_tiktok")

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"
TOKEN_STORAGE_PATH = ROOT_DIR / "storage" / "tiktok_token.json"

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN", "").strip()
TIKTOK_OPEN_ID = os.getenv("TIKTOK_OPEN_ID", "").strip()

# Minimum chunk size is 5MB, max is 64MB for TikTok v2
MIN_CHUNK_SIZE = 5 * 1024 * 1024
DEFAULT_CHUNK_SIZE = 10 * 1024 * 1024
MAX_CHUNK_SIZE = 64 * 1024 * 1024


def load_persisted_token() -> Dict[str, Any]:
    """Load token from storage/tiktok_token.json if available."""
    if TOKEN_STORAGE_PATH.exists():
        try:
            with open(TOKEN_STORAGE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("[TikTok] Failed to read token file: %s", e)
    return {}


def save_persisted_token(token_data: Dict[str, Any]) -> None:
    """Save token to storage/tiktok_token.json with strict permissions (0o600)."""
    try:
        TOKEN_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_STORAGE_PATH, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)
        os.chmod(TOKEN_STORAGE_PATH, 0o600)
        logger.info("[TikTok] Saved updated token to %s", TOKEN_STORAGE_PATH)
    except Exception as e:
        logger.error("[TikTok] Failed to save token file: %s", e)


def is_tiktok_configured() -> bool:
    """Check if TikTok client key and active tokens are configured."""
    ck = os.getenv("TIKTOK_CLIENT_KEY", "").strip() or TIKTOK_CLIENT_KEY
    if not ck or "YOUR_" in ck or len(ck) < 5:
        return False

    tok_data = load_persisted_token()
    access_tok = tok_data.get("access_token") or os.getenv("TIKTOK_ACCESS_TOKEN", "").strip() or TIKTOK_ACCESS_TOKEN
    refresh_tok = tok_data.get("refresh_token") or os.getenv("TIKTOK_REFRESH_TOKEN", "").strip() or TIKTOK_REFRESH_TOKEN

    return bool(access_tok or refresh_tok)


def ensure_tiktok_token(client: Optional[httpx.Client] = None) -> Optional[str]:
    """
    Ensure a valid TikTok access token is available. If the token is within 1 hour
    of expiry, refreshes it using the refresh_token grant and persists the new token.
    """
    if not is_tiktok_configured():
        return None

    tok_data = load_persisted_token()
    now = time.time()
    access_token = tok_data.get("access_token") or os.getenv("TIKTOK_ACCESS_TOKEN", "").strip() or TIKTOK_ACCESS_TOKEN
    expires_at = tok_data.get("expires_at", 0)
    refresh_token = tok_data.get("refresh_token") or os.getenv("TIKTOK_REFRESH_TOKEN", "").strip() or TIKTOK_REFRESH_TOKEN

    # If active access token is valid for more than 1 hour, return it
    if access_token and (expires_at - now > 3600):
        return access_token

    # Need refresh
    ck = os.getenv("TIKTOK_CLIENT_KEY", "").strip() or TIKTOK_CLIENT_KEY
    cs = os.getenv("TIKTOK_CLIENT_SECRET", "").strip() or TIKTOK_CLIENT_SECRET
    if not refresh_token or not ck or not cs:
        if access_token:
            return access_token
        return None

    url = f"{TIKTOK_API_BASE}/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_key": ck,
        "client_secret": cs,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    try:
        c = client or httpx.Client(timeout=15.0)
        resp = c.post(url, headers=headers, data=data)
        if resp.status_code == 200:
            res_json = resp.json()
            d = res_json.get("data") if ("data" in res_json and isinstance(res_json["data"], dict) and "access_token" in res_json["data"]) else res_json
            if "access_token" in d:
                new_access = d.get("access_token")
                new_refresh = d.get("refresh_token", refresh_token)
                expires_in = d.get("expires_in", 86400)
                refresh_expires_in = d.get("refresh_expires_in", 31536000)

                persisted = {
                    "access_token": new_access,
                    "refresh_token": new_refresh,
                    "open_id": d.get("open_id") or os.getenv("TIKTOK_OPEN_ID", "").strip() or TIKTOK_OPEN_ID,
                    "expires_at": int(now + expires_in),
                    "refresh_expires_at": int(now + refresh_expires_in)
                }
                save_persisted_token(persisted)
                logger.info("[TikTok] Successfully refreshed token. Expires in %ds", expires_in)
                return new_access
        logger.warning("[TikTok] Token refresh returned %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.error("[TikTok] Failed to refresh token: %s", e)

    return access_token if access_token else None


def generate_tiktok_auth_url(
    redirect_uri: str = "https://ai-tech-broadcaster.vercel.app/api/auth/tiktok/callback",
    state: str = "eraof_ai_broadcaster"
) -> str:
    """Generate TikTok OAuth v2 authorization URL for user consent."""
    ck = os.getenv("TIKTOK_CLIENT_KEY", "").strip() or TIKTOK_CLIENT_KEY
    params = {
        "client_key": ck,
        "scope": "video.publish,video.upload,user.info.basic",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": state
    }
    return f"https://www.tiktok.com/v2/auth/authorize/?{urllib.parse.urlencode(params)}"


def exchange_tiktok_code(
    code: str,
    redirect_uri: str = "https://ai-tech-broadcaster.vercel.app/api/auth/tiktok/callback"
) -> Dict[str, Any]:
    """
    Exchange authorization code for access_token and refresh_token,
    persisting tokens to storage/tiktok_token.json and updating config/.env.
    """
    ck = os.getenv("TIKTOK_CLIENT_KEY", "").strip() or TIKTOK_CLIENT_KEY
    cs = os.getenv("TIKTOK_CLIENT_SECRET", "").strip() or TIKTOK_CLIENT_SECRET
    if not ck or not cs:
        return {"status": "error", "message": "Missing TIKTOK_CLIENT_KEY or TIKTOK_CLIENT_SECRET"}

    url = f"{TIKTOK_API_BASE}/oauth/token/"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_key": ck,
        "client_secret": cs,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, data=data)
            res_json = resp.json()
            d = res_json.get("data") if ("data" in res_json and isinstance(res_json["data"], dict) and "access_token" in res_json["data"]) else res_json
            if resp.status_code == 200 and "access_token" in d:
                now = time.time()
                persisted = {
                    "access_token": d.get("access_token"),
                    "refresh_token": d.get("refresh_token"),
                    "open_id": d.get("open_id"),
                    "scope": d.get("scope"),
                    "expires_at": int(now + d.get("expires_in", 86400)),
                    "refresh_expires_at": int(now + d.get("refresh_expires_in", 31536000))
                }
                save_persisted_token(persisted)

                try:
                    env_file = ROOT_DIR / "config" / ".env"
                    if env_file.exists():
                        content = env_file.read_text(encoding="utf-8")
                        content = re.sub(r"TIKTOK_ACCESS_TOKEN=.*", f"TIKTOK_ACCESS_TOKEN={d.get('access_token', '')}", content)
                        content = re.sub(r"TIKTOK_REFRESH_TOKEN=.*", f"TIKTOK_REFRESH_TOKEN={d.get('refresh_token', '')}", content)
                        content = re.sub(r"TIKTOK_OPEN_ID=.*", f"TIKTOK_OPEN_ID={d.get('open_id', '')}", content)
                        env_file.write_text(content, encoding="utf-8")
                except Exception as env_err:
                    logger.warning("[TikTok] Could not update config/.env: %s", env_err)

                return {
                    "status": "success",
                    "open_id": d.get("open_id"),
                    "scope": d.get("scope"),
                    "expires_in": d.get("expires_in"),
                    "refresh_expires_in": d.get("refresh_expires_in")
                }
            else:
                return {
                    "status": "error",
                    "http_code": resp.status_code,
                    "response": res_json
                }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def build_tiktok_title(post_record: dict, max_len: int = 2200) -> str:
    """Build caption/title for TikTok Reel with safe word boundary truncation."""
    headline = post_record.get("headline", "AI Tech Update")
    captions_json = post_record.get("captions_json")

    title_text = f"{headline}\n\n#AI #Technology #TechNews #EraOfAI #Innovation"
    if captions_json:
        try:
            parsed = json.loads(captions_json)
            short = parsed.get("short_form") or parsed.get("tiktok")
            if short:
                title_text = short
        except Exception:
            pass

    if len(title_text) <= max_len:
        return title_text

    truncated = title_text[:max_len - 3]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return f"{truncated}..."


def calculate_chunks(file_size: int) -> Tuple[int, int]:
    """Calculate (chunk_size, total_chunks) conforming to TikTok specs."""
    if file_size <= MAX_CHUNK_SIZE:
        return file_size, 1

    chunk_size = DEFAULT_CHUNK_SIZE
    total_chunks = math.ceil(file_size / chunk_size)
    return chunk_size, total_chunks


def query_creator_info(client: httpx.Client, access_token: str) -> Dict[str, Any]:
    """Query TikTok creator info to determine privacy options and duration bounds."""
    url = f"{TIKTOK_API_BASE}/post/publish/creator_info/query/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    try:
        resp = client.post(url, headers=headers, json={})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("error", {}).get("code") == "ok":
                return {"success": True, "data": data.get("data", {})}
            return {"success": False, "error": data.get("error", {})}
        return {"success": False, "error": {"code": str(resp.status_code), "message": resp.text}}
    except Exception as e:
        return {"success": False, "error": {"code": "CLIENT_EXCEPTION", "message": str(e)}}


def poll_publish_status(
    client: httpx.Client,
    publish_id: str,
    access_token: str,
    max_wait_sec: int = 600,
    poll_interval: int = 5
) -> Dict[str, Any]:
    """Poll status of uploaded TikTok video until PUBLISH_COMPLETE or FAILED."""
    url = f"{TIKTOK_API_BASE}/post/publish/status/fetch/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    body = {"publish_id": publish_id}
    start = time.time()
    backoff = poll_interval

    while time.time() - start < max_wait_sec:
        try:
            resp = client.post(url, headers=headers, json=body)
            if resp.status_code == 200:
                res_json = resp.json()
                data = res_json.get("data", {})
                status = data.get("status")
                logger.info("[TikTok] Publish %s status: %s (elapsed %.1fs)", publish_id, status, time.time() - start)
                if status in ("PUBLISH_COMPLETE", "SUCCESS"):
                    return {"success": True, "status": status}
                if status == "FAILED":
                    return {
                        "success": False,
                        "status": "FAILED",
                        "fail_reason": data.get("fail_reason", "PUBLISH_FAILED")
                    }
            elif resp.status_code in (400, 401, 403):
                return {"success": False, "status": "ERROR", "fail_reason": resp.text}
        except Exception as e:
            logger.warning("[TikTok] Status polling error for %s: %s", publish_id, e)

        time.sleep(backoff)
        backoff = min(backoff + 2, 20)

    return {"success": False, "status": "TIMEOUT", "fail_reason": f"Publish timed out after {max_wait_sec}s"}


def publish_to_tiktok(
    post_record: dict,
    media: Optional[MediaRef] = None,
    client: Optional[httpx.Client] = None
) -> PlatformResult:
    """
    Publish a Reel to TikTok Content Posting API v2 using direct chunked FILE_UPLOAD.

    Conforms to P5 specifications:
    - Only 'reel' format is eligible.
    - Gracefully selects privacy_level (prefers PUBLIC_TO_EVERYONE, falls back to SELF_ONLY).
    - Sets is_aigc: true on every post.
    - Chunked PUT upload with Content-Range headers.
    - Simulates flow when unconfigured or in simulate mode.
    """
    format_type = post_record.get("format_type", "post")
    publish_mode = os.getenv("PUBLISH_MODE", "simulate").lower()

    # Rule 1: Only 'reel' format supported by TikTok
    if format_type != "reel":
        return PlatformResult(
            platform="tiktok",
            status="skipped",
            mode="simulated" if publish_mode == "simulate" else "live",
            error_code="FORMAT_UNSUPPORTED",
            error_message=f"TikTok publisher only supports format_type='reel' (got '{format_type}')",
            attempts=0,
            latency_ms=0
        )

    # Resolve local media path
    local_file: Optional[Path] = None
    if media and media.get("local_path"):
        p = Path(media["local_path"])
        if p.exists() and p.is_file():
            local_file = p

    # If no media provided or missing file, check post_record
    if not local_file:
        raw_path = post_record.get("video_path") or post_record.get("media_path")
        if raw_path:
            p = Path(raw_path)
            if p.exists() and p.is_file():
                local_file = p

    title = build_tiktok_title(post_record, max_len=2200)

    # --- SIMULATION MODE ---
    if publish_mode == "simulate" or not is_tiktok_configured():
        if publish_mode == "live" and not is_tiktok_configured():
            return PlatformResult(
                platform="tiktok",
                status="failed",
                mode="live",
                error_code="NOT_CONFIGURED",
                error_message="TikTok client credentials or tokens are missing in live mode.",
                attempts=1,
                latency_ms=0
            )

        sim_id = f"tt_sim_{int(time.time())}"
        file_size = local_file.stat().st_size if local_file else 15 * 1024 * 1024
        chunk_size, total_chunks = calculate_chunks(file_size)

        request_preview: Dict[str, Any] = {
            "creator_info_query": f"{TIKTOK_API_BASE}/post/publish/creator_info/query/",
            "video_init": {
                "endpoint": f"{TIKTOK_API_BASE}/post/publish/video/init/",
                "post_info": {
                    "title": title,
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "is_aigc": True
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": chunk_size,
                    "total_chunk_count": total_chunks
                }
            },
            "upload_plan": {
                "method": "PUT",
                "chunks": total_chunks,
                "chunk_size_bytes": chunk_size
            },
            "status_fetch": f"{TIKTOK_API_BASE}/post/publish/status/fetch/"
        }

        logger.info("[TikTok SIMULATE] Prepared simulated Reel publish: %d bytes, %d chunks", file_size, total_chunks)
        return PlatformResult(
            platform="tiktok",
            status="simulated",
            mode="simulated",
            remote_id=sim_id,
            permalink=f"https://www.tiktok.com/@creator/video/{sim_id}",
            attempts=1,
            latency_ms=10,
            note=None,
            request_preview=request_preview
        )

    # --- LIVE MODE ---
    if not local_file:
        return PlatformResult(
            platform="tiktok",
            status="failed",
            mode="live",
            error_code="LOCAL_FILE_MISSING",
            error_message="Video file not found on disk for TikTok FILE_UPLOAD.",
            attempts=1,
            latency_ms=0
        )

    start_time = time.time()
    c = client or httpx.Client(timeout=60.0)

    token = ensure_tiktok_token(c)
    if not token:
        return PlatformResult(
            platform="tiktok",
            status="failed",
            mode="live",
            error_code="TOKEN_REFRESH_FAILED",
            error_message="Failed to obtain a valid TikTok access token.",
            attempts=1,
            latency_ms=int((time.time() - start_time) * 1000)
        )

    try:
        # Step 1: Query Creator Info
        creator_res = query_creator_info(c, token)
        privacy_level = "SELF_ONLY"
        is_unaudited = True
        note = None
        disable_duet = False
        disable_comment = False
        disable_stitch = False

        forced_privacy = os.getenv("TIKTOK_PRIVACY_LEVEL", "").strip().upper()
        if forced_privacy in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY", "FOLLOWER_OF_CREATOR"):
            privacy_level = forced_privacy
            if forced_privacy != "PUBLIC_TO_EVERYONE":
                note = "private_unaudited_app"
            else:
                is_unaudited = False
            if creator_res["success"]:
                cdata = creator_res["data"]
                disable_duet = cdata.get("duet_disabled", False)
                disable_comment = cdata.get("comment_disabled", False)
                disable_stitch = cdata.get("stitch_disabled", False)
        elif creator_res["success"]:
            cdata = creator_res["data"]
            options = cdata.get("privacy_level_options", [])
            disable_duet = cdata.get("duet_disabled", False)
            disable_comment = cdata.get("comment_disabled", False)
            disable_stitch = cdata.get("stitch_disabled", False)

            if "PUBLIC_TO_EVERYONE" in options:
                privacy_level = "PUBLIC_TO_EVERYONE"
                is_unaudited = False
            elif "MUTUAL_FOLLOW_FRIENDS" in options:
                privacy_level = "MUTUAL_FOLLOW_FRIENDS"
                note = "private_unaudited_app"
            else:
                privacy_level = "SELF_ONLY"
                note = "private_unaudited_app"
        else:
            note = "private_unaudited_app"
            logger.warning("[TikTok] Creator query returned error; defaulting to SELF_ONLY: %s", creator_res.get("error"))

        # Step 2: Video Init
        file_size = local_file.stat().st_size
        chunk_size, total_chunks = calculate_chunks(file_size)

        init_url = f"{TIKTOK_API_BASE}/post/publish/video/init/"
        init_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8"
        }
        init_payload = {
            "post_info": {
                "title": title,
                "privacy_level": privacy_level,
                "disable_duet": disable_duet,
                "disable_comment": disable_comment,
                "disable_stitch": disable_stitch,
                "video_cover_timestamp_ms": 1000,
                "is_aigc": True
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks
            }
        }

        init_resp = c.post(init_url, headers=init_headers, json=init_payload)

        # Fallback if unaudited app error returned (applies to HTTP != 200 or HTTP 200 with error)
        if "unaudited_client_can_only_post_to_private_accounts" in init_resp.text and privacy_level != "SELF_ONLY":
            logger.warning("[TikTok] Unaudited app restriction encountered. Retrying video init with privacy_level='SELF_ONLY'...")
            privacy_level = "SELF_ONLY"
            note = "private_unaudited_app"
            init_payload["post_info"]["privacy_level"] = "SELF_ONLY"
            init_resp = c.post(init_url, headers=init_headers, json=init_payload)

        if init_resp.status_code != 200:
            return PlatformResult(
                platform="tiktok",
                status="failed",
                mode="live",
                error_code="VIDEO_INIT_FAILED",
                error_message=f"TikTok video init failed: {init_resp.text}",
                attempts=1,
                latency_ms=int((time.time() - start_time) * 1000)
            )

        init_json = init_resp.json()
        init_data = init_json.get("data", {})
        publish_id = init_data.get("publish_id")
        upload_url = init_data.get("upload_url")

        if not publish_id or not upload_url:
            err_info = init_json.get("error", {})
            err_code = err_info.get("code")
            if err_code == "unaudited_client_can_only_post_to_private_accounts" and privacy_level != "SELF_ONLY":
                logger.warning("[TikTok] Unaudited app restriction in 200 response. Retrying video init with privacy_level='SELF_ONLY'...")
                privacy_level = "SELF_ONLY"
                note = "private_unaudited_app"
                init_payload["post_info"]["privacy_level"] = "SELF_ONLY"
                init_resp = c.post(init_url, headers=init_headers, json=init_payload)
                if init_resp.status_code == 200:
                    init_json = init_resp.json()
                    init_data = init_json.get("data", {})
                    publish_id = init_data.get("publish_id")
                    upload_url = init_data.get("upload_url")
                    err_info = init_json.get("error", {})

            if not publish_id or not upload_url:
                return PlatformResult(
                    platform="tiktok",
                    status="failed",
                    mode="live",
                    error_code=err_info.get("code", "INIT_RESPONSE_INVALID"),
                    error_message=err_info.get("message", "publish_id or upload_url missing in init response"),
                    attempts=1,
                    latency_ms=int((time.time() - start_time) * 1000)
                )

        # Step 3: Chunked PUT Upload
        with open(local_file, "rb") as f:
            for chunk_idx in range(total_chunks):
                chunk_bytes = f.read(chunk_size)
                start_byte = chunk_idx * chunk_size
                end_byte = start_byte + len(chunk_bytes) - 1

                put_headers = {
                    "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(chunk_bytes))
                }
                put_resp = c.put(upload_url, headers=put_headers, content=chunk_bytes)
                if put_resp.status_code not in (200, 201, 206):
                    return PlatformResult(
                        platform="tiktok",
                        status="failed",
                        mode="live",
                        error_code="CHUNK_UPLOAD_FAILED",
                        error_message=f"Chunk #{chunk_idx} failed with {put_resp.status_code}: {put_resp.text}",
                        attempts=1,
                        latency_ms=int((time.time() - start_time) * 1000)
                    )

        # Step 4: Poll Status
        poll_res = poll_publish_status(c, publish_id, token, max_wait_sec=600)
        if not poll_res["success"]:
            return PlatformResult(
                platform="tiktok",
                status="failed",
                mode="live",
                error_code=poll_res.get("fail_reason", "PUBLISH_POLL_FAILED"),
                error_message=f"TikTok video processing failed: {poll_res.get('fail_reason')}",
                attempts=1,
                latency_ms=int((time.time() - start_time) * 1000)
            )

        return PlatformResult(
            platform="tiktok",
            status="published",
            mode="live",
            remote_id=publish_id,
            permalink=f"https://www.tiktok.com/video/{publish_id}",
            attempts=1,
            latency_ms=int((time.time() - start_time) * 1000),
            note=note
        )

    except Exception as e:
        logger.exception("[TikTok] Unexpected exception during publish: %s", e)
        return PlatformResult(
            platform="tiktok",
            status="failed",
            mode="live",
            error_code="UNEXPECTED_ERROR",
            error_message=str(e),
            attempts=1,
            latency_ms=int((time.time() - start_time) * 1000)
        )
