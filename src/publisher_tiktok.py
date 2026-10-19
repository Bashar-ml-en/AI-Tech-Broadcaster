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
    """Poll status of uploaded TikTok video until PUBLISH_COMPLETE, SEND_TO_USER_INBOX, or FAILED."""
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
                if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX", "SUCCESS"):
                    return {
                        "success": True,
                        "status": status,
                        "publically_available_post_id": data.get("publically_available_post_id", []),
                    }
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


def _notify_telegram_inbox_caption(
    client: httpx.Client,
    creator_username: Optional[str],
    publish_id: str,
    title: Optional[str]
) -> None:
    """Send a Telegram helper alert with the ready-to-paste caption when a video arrives in TikTok Inbox."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id or not title:
        return
    handle = (creator_username or "eraofai8").lstrip("@")
    msg = (
        f"📲 <b>TikTok Full HD (1080x1920) Ready in Inbox (@{handle})</b>\n\n"
        f"1️⃣ Open the <b>TikTok App</b> on your phone (@{handle}) → tap <b>Inbox (System Notifications)</b> → <i>'Your video is ready to post'</i>.\n"
        f"2️⃣ Paste this caption and tap <b>Post (Everyone)</b> for full For You Page reach:\n\n"
        f"<code>{title[:800]}</code>"
    )
    try:
        client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=10.0,
        )
    except Exception as e:
        logger.debug("[TikTok] Optional Telegram caption helper failed: %s", e)


def upload_video_to_tiktok_inbox(
    client: httpx.Client,
    local_file: Path,
    access_token: str,
    title: Optional[str] = None,
    creator_username: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload MP4 video to TikTok Creator Inbox (/v2/post/publish/inbox/video/init/).
    Allows unaudited apps to deliver a ready-to-post draft notification to the TikTok mobile app
    so the creator can publish with PUBLIC_TO_EVERYONE visibility and full FYP reach in 1 tap.
    """
    file_size = local_file.stat().st_size
    chunk_size, total_chunks = calculate_chunks(file_size)

    inbox_url = f"{TIKTOK_API_BASE}/post/publish/inbox/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    payload = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks
        }
    }

    resp = client.post(inbox_url, headers=headers, json=payload)
    if resp.status_code != 200:
        err_code = "INBOX_INIT_FAILED"
        err_msg = resp.text
        try:
            err_json = resp.json().get("error", {})
            err_code = err_json.get("code") or err_code
            err_msg = err_json.get("message") or err_msg
        except Exception:
            pass
        return {
            "success": False,
            "error_code": err_code,
            "error_message": f"TikTok inbox video init failed ({resp.status_code}): {err_msg}"
        }

    res_json = resp.json()
    data = res_json.get("data", {})
    publish_id = data.get("publish_id")
    upload_url = data.get("upload_url")

    if not publish_id or not upload_url:
        err = res_json.get("error", {})
        return {
            "success": False,
            "error_code": err.get("code", "INBOX_RESPONSE_INVALID"),
            "error_message": err.get("message", f"Missing publish_id/upload_url in inbox init: {resp.text}")
        }

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
            put_resp = client.put(upload_url, headers=put_headers, content=chunk_bytes)
            if put_resp.status_code not in (200, 201, 206):
                return {
                    "success": False,
                    "error_code": "INBOX_CHUNK_FAILED",
                    "error_message": f"Inbox chunk #{chunk_idx} failed ({put_resp.status_code}): {put_resp.text}"
                }

    poll_res = poll_publish_status(client, publish_id, access_token, max_wait_sec=600)
    if not poll_res.get("success"):
        return {
            "success": False,
            "error_code": poll_res.get("fail_reason", "INBOX_POLL_FAILED"),
            "error_message": f"Inbox video processing failed: {poll_res.get('fail_reason')}"
        }

    _notify_telegram_inbox_caption(client, creator_username, publish_id, title)

    return {
        "success": True,
        "publish_id": publish_id,
        "status": poll_res.get("status", "SEND_TO_USER_INBOX"),
        "publically_available_post_id": poll_res.get("publically_available_post_id", [])
    }


def resolve_tiktok_permalink(
    publish_id: str,
    creator_username: Optional[str] = None,
    public_ids: Optional[List[Any]] = None
) -> str:
    """Resolve canonical TikTok video permalink from publish_id, creator_username, and public_ids."""
    video_id = publish_id
    if public_ids and len(public_ids) > 0 and str(public_ids[0]).strip():
        video_id = str(public_ids[0]).strip()
    elif "." in publish_id:
        suffix = publish_id.rsplit(".", 1)[-1].strip()
        if suffix.isdigit():
            video_id = suffix

    clean_user = (creator_username or "").strip().lstrip("@")
    if clean_user:
        return f"https://www.tiktok.com/@{clean_user}/video/{video_id}"
    return f"https://www.tiktok.com/video/{video_id}"


def diagnose_tiktok_connection(
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    client: Optional[httpx.Client] = None
) -> Dict[str, Any]:
    """
    Comprehensive live diagnostic health-check for TikTok Content Posting API v2.
    Checks OAuth2 token validity/auto-refresh, queries creator_info, and checks Sandbox/Private Account reach status.
    """
    tok_data = load_persisted_token()
    if access_token and access_token.strip():
        os.environ["TIKTOK_ACCESS_TOKEN"] = access_token.strip()
        tok_data["access_token"] = access_token.strip()
    if refresh_token and refresh_token.strip():
        os.environ["TIKTOK_REFRESH_TOKEN"] = refresh_token.strip()
        tok_data["refresh_token"] = refresh_token.strip()
    if (access_token and access_token.strip()) or (refresh_token and refresh_token.strip()):
        save_persisted_token(tok_data)

    if not is_tiktok_configured():
        return {
            "configured": False,
            "status": "unconfigured",
            "status_badge": "OAUTH REQUIRED",
            "diagnostic": "TikTok OAuth2 credentials are missing. Provide TIKTOK_ACCESS_TOKEN and TIKTOK_REFRESH_TOKEN.",
        }

    c = client or httpx.Client(timeout=20.0)
    active_tok = ensure_tiktok_token(c)
    if not active_tok:
        return {
            "configured": False,
            "status": "token_expired",
            "status_badge": "TOKEN EXPIRED",
            "diagnostic": "Failed to obtain or refresh TikTok access token via /v2/oauth/token/.",
        }

    creator_res = query_creator_info(c, active_tok)
    tok_data = load_persisted_token()
    now = time.time()
    expires_at = tok_data.get("expires_at", 0)
    refresh_expires_at = tok_data.get("refresh_expires_at", 0)
    ttl_hours = max(0.0, round((expires_at - now) / 3600, 1)) if expires_at else 24.0
    refresh_days = max(0, int((refresh_expires_at - now) / 86400)) if refresh_expires_at else 365

    ck = os.getenv("TIKTOK_CLIENT_KEY", "").strip() or TIKTOK_CLIENT_KEY
    is_sandbox_key = ck.startswith("sb")
    publish_method = os.getenv("TIKTOK_PUBLISH_METHOD", "auto").strip().lower()

    if creator_res.get("success"):
        cdata = creator_res.get("data", {})
        username = cdata.get("creator_username") or tok_data.get("creator_username") or "eraofai8"
        nickname = cdata.get("creator_nickname") or tok_data.get("creator_nickname") or "Ai_updats"
        privacy_opts = cdata.get("privacy_level_options", [])
        max_dur = cdata.get("max_video_post_duration_sec", 3600)
        account_is_private = "PUBLIC_TO_EVERYONE" not in privacy_opts

        # Persist creator metadata for fast sidebar lookup
        if (
            tok_data.get("creator_username") != username
            or tok_data.get("creator_nickname") != nickname
            or tok_data.get("privacy_level_options") != privacy_opts
        ):
            tok_data["creator_username"] = username
            tok_data["creator_nickname"] = nickname
            tok_data["privacy_level_options"] = privacy_opts
            save_persisted_token(tok_data)

        warnings_list = []
        if account_is_private:
            warnings_list.append(
                f"Account @{username} has 'Private Account' enabled in TikTok app (PUBLIC_TO_EVERYONE missing). "
                "Go to TikTok App -> Profile -> Menu -> Settings and privacy -> Privacy -> turn 'Private account' OFF."
            )
        if is_sandbox_key:
            warnings_list.append(
                f"Client Key ({ck[:6]}...) is a TikTok Sandbox / Unaudited key. Direct Posts default to SELF_ONLY "
                "(Private Lock tab). Use Inbox Draft mode or flip privacy to 'Everyone' in the TikTok app Lock tab."
            )

        return {
            "configured": True,
            "status": "ready",
            "status_badge": f"ONLINE // READY (@{username})",
            "username": username,
            "nickname": nickname,
            "open_id": tok_data.get("open_id") or TIKTOK_OPEN_ID,
            "privacy_level_options": privacy_opts,
            "account_is_private": account_is_private,
            "is_sandbox_key": is_sandbox_key,
            "publish_method": publish_method,
            "max_video_post_duration_sec": max_dur,
            "token_ttl_hours": ttl_hours,
            "refresh_ttl_days": refresh_days,
            "is_permanent": True,
            "expiry_description": f"Auto-Rotating OAuth2 Refresh Token ({refresh_days}d remaining, Access TTL: {ttl_hours}h)",
            "scopes": ["video.publish", "video.upload", "user.info.basic"],
            "warnings": warnings_list,
            "diagnostic": (
                f"Connected live to TikTok @{username} ({nickname}) [mode={publish_method.upper()}]. "
                f"Privacy options: {', '.join(privacy_opts) or 'SELF_ONLY'}. "
                + (" | WARNING: " + " ".join(warnings_list) if warnings_list else f"Max video duration: {max_dur}s.")
            ),
        }

    err = creator_res.get("error", {})
    return {
        "configured": True,
        "status": "degraded",
        "status_badge": "API WARNING",
        "open_id": tok_data.get("open_id") or TIKTOK_OPEN_ID,
        "token_ttl_hours": ttl_hours,
        "expiry_description": f"Access Token TTL: {ttl_hours}h",
        "diagnostic": f"TikTok creator_info returned {err.get('code', 'ERROR')}: {err.get('message', '')}",
    }


def reload_tiktok_credentials() -> Dict[str, Any]:
    """Reload TikTok credentials from config/.env and storage/tiktok_token.json."""
    global TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, TIKTOK_ACCESS_TOKEN, TIKTOK_REFRESH_TOKEN, TIKTOK_OPEN_ID
    load_dotenv(dotenv_path=env_path, override=True)
    TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
    TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
    TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN", "").strip()
    TIKTOK_REFRESH_TOKEN = os.getenv("TIKTOK_REFRESH_TOKEN", "").strip()
    TIKTOK_OPEN_ID = os.getenv("TIKTOK_OPEN_ID", "").strip()
    tok = ensure_tiktok_token()
    persisted = load_persisted_token()
    return {
        "configured": is_tiktok_configured(),
        "has_active_token": bool(tok),
        "open_id": persisted.get("open_id") or TIKTOK_OPEN_ID,
        "username": persisted.get("creator_username"),
    }


def publish_to_tiktok(
    post_record: dict,
    media: Optional[MediaRef] = None,
    client: Optional[httpx.Client] = None,
    allow_format_conversion: bool = False
) -> PlatformResult:
    """
    Publish a Reel to TikTok Content Posting API v2 using direct chunked FILE_UPLOAD.

    Conforms to P5 specifications:
    - Only 'reel' format is eligible unless allow_format_conversion=True (when video has been synthesized).
    - Gracefully selects privacy_level (prefers PUBLIC_TO_EVERYONE, falls back to SELF_ONLY).
    - Sets is_aigc: true on every post.
    - Chunked PUT upload with Content-Range headers.
    - Simulates flow when unconfigured or in simulate mode.
    """
    format_type = post_record.get("format_type", "post")
    publish_mode = os.getenv("PUBLISH_MODE", "simulate").lower()

    # Rule 1: Only 'reel' format supported by TikTok unless converted by PublishingSubagent
    if format_type != "reel" and not allow_format_conversion:
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
        creator_username: Optional[str] = load_persisted_token().get("creator_username")

        forced_privacy = os.getenv("TIKTOK_PRIVACY_LEVEL", "").strip().upper()
        if forced_privacy in ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY", "FOLLOWER_OF_CREATOR"):
            privacy_level = forced_privacy
            if forced_privacy != "PUBLIC_TO_EVERYONE":
                note = "private_unaudited_app"
            else:
                is_unaudited = False
            if creator_res["success"]:
                cdata = creator_res["data"]
                creator_username = cdata.get("creator_username") or creator_username
                disable_duet = cdata.get("duet_disabled", False)
                disable_comment = cdata.get("comment_disabled", False)
                disable_stitch = cdata.get("stitch_disabled", False)
        elif creator_res["success"]:
            cdata = creator_res["data"]
            creator_username = cdata.get("creator_username") or creator_username
            options = cdata.get("privacy_level_options", [])
            disable_duet = cdata.get("duet_disabled", False)
            disable_comment = cdata.get("comment_disabled", False)
            disable_stitch = cdata.get("stitch_disabled", False)

            if "PUBLIC_TO_EVERYONE" in options:
                privacy_level = "PUBLIC_TO_EVERYONE"
                is_unaudited = False
            elif "FOLLOWER_OF_CREATOR" in options:
                privacy_level = "FOLLOWER_OF_CREATOR"
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

        publish_method = os.getenv("TIKTOK_PUBLISH_METHOD", "auto").strip().lower()

        # If explicitly set to 'inbox', deliver directly to TikTok Creator Inbox for 1-tap PUBLIC_TO_EVERYONE posting
        if publish_method == "inbox":
            logger.info("[TikTok] Using INBOX draft upload (/v2/post/publish/inbox/video/init/) for public reach...")
            inbox_res = upload_video_to_tiktok_inbox(c, local_file, token, title=title, creator_username=creator_username)
            if not inbox_res.get("success"):
                return PlatformResult(
                    platform="tiktok",
                    status="failed",
                    mode="live",
                    error_code=inbox_res.get("error_code", "INBOX_UPLOAD_FAILED"),
                    error_message=inbox_res.get("error_message", "TikTok inbox upload failed"),
                    attempts=1,
                    latency_ms=int((time.time() - start_time) * 1000)
                )
            pub_id = inbox_res["publish_id"]
            permalink = resolve_tiktok_permalink(
                publish_id=pub_id,
                creator_username=creator_username,
                public_ids=inbox_res.get("publically_available_post_id"),
            )
            return PlatformResult(
                platform="tiktok",
                status="published",
                mode="live",
                remote_id=pub_id,
                permalink=permalink,
                attempts=1,
                latency_ms=int((time.time() - start_time) * 1000),
                note="inbox_draft_ready_for_public_post"
            )

        # Step 2: Direct Video Init (/v2/post/publish/video/init/)
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

        # When the target TikTok account is PUBLIC, TikTok blocks /video/init/ even with SELF_ONLY for unaudited apps.
        # Automatically fall back to Creator Inbox Upload (/v2/post/publish/inbox/video/init/) which works on Public Accounts!
        if init_resp.status_code != 200 and "unaudited_client_can_only_post_to_private_accounts" in init_resp.text:
            logger.info(
                "[TikTok] Target account @%s is PUBLIC and app is unaudited; routing to Creator Inbox (/v2/post/publish/inbox/video/init/) for public FYP reach...",
                creator_username or "eraofai8"
            )
            inbox_res = upload_video_to_tiktok_inbox(c, local_file, token, title=title, creator_username=creator_username)
            if inbox_res.get("success"):
                pub_id = inbox_res["publish_id"]
                permalink = resolve_tiktok_permalink(
                    publish_id=pub_id,
                    creator_username=creator_username,
                    public_ids=inbox_res.get("publically_available_post_id"),
                )
                return PlatformResult(
                    platform="tiktok",
                    status="published",
                    mode="live",
                    remote_id=pub_id,
                    permalink=permalink,
                    attempts=1,
                    latency_ms=int((time.time() - start_time) * 1000),
                    note="inbox_draft_public_account"
                )
            else:
                inbox_err = inbox_res.get("error_code")
                inbox_msg = inbox_res.get("error_message", "")
                user_hint = ""
                if inbox_err == "spam_risk_too_many_pending_share" or "spam_risk" in inbox_msg:
                    user_hint = (
                        " [ACTION REQUIRED: TikTok Inbox rate limit reached. "
                        "Open the TikTok app on your phone -> tap Inbox (System notifications) and Post or Discard pending drafts. "
                        "Alternatively, toggle your TikTok account to 'Private' in TikTok Settings -> Privacy to enable direct automatic posting.]"
                    )
                return PlatformResult(
                    platform="tiktok",
                    status="failed",
                    mode="live",
                    error_code="UNAUDITED_PUBLIC_ACCOUNT_RESTRICTION",
                    error_message=(
                        f"TikTok rejected direct post (unaudited_client_can_only_post_to_private_accounts) "
                        f"and Inbox draft fallback failed ({inbox_err}).{user_hint}"
                    ),
                    attempts=1,
                    latency_ms=int((time.time() - start_time) * 1000)
                )

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
                if "unaudited_client_can_only_post_to_private_accounts" in init_resp.text:
                    logger.info(
                        "[TikTok] Unaudited app on public account @%s: delivering draft to Creator Inbox (/v2/post/publish/inbox/video/init/)...",
                        creator_username or "eraofai8"
                    )
                    inbox_res = upload_video_to_tiktok_inbox(c, local_file, token, title=title, creator_username=creator_username)
                    if inbox_res.get("success"):
                        pub_id = inbox_res["publish_id"]
                        permalink = resolve_tiktok_permalink(
                            publish_id=pub_id,
                            creator_username=creator_username,
                            public_ids=inbox_res.get("publically_available_post_id"),
                        )
                        return PlatformResult(
                            platform="tiktok",
                            status="published",
                            mode="live",
                            remote_id=pub_id,
                            permalink=permalink,
                            attempts=1,
                            latency_ms=int((time.time() - start_time) * 1000),
                            note="inbox_draft_public_account"
                        )
                    else:
                        inbox_err = inbox_res.get("error_code")
                        inbox_msg = inbox_res.get("error_message", "")
                        user_hint = ""
                        if inbox_err == "spam_risk_too_many_pending_share" or "spam_risk" in inbox_msg:
                            user_hint = (
                                " [ACTION REQUIRED: TikTok Inbox rate limit reached. "
                                "Open the TikTok app on your phone -> tap Inbox (System notifications) and Post or Discard pending drafts. "
                                "Alternatively, toggle your TikTok account to 'Private' in TikTok Settings -> Privacy to enable direct automatic posting.]"
                            )
                        return PlatformResult(
                            platform="tiktok",
                            status="failed",
                            mode="live",
                            error_code="UNAUDITED_PUBLIC_ACCOUNT_RESTRICTION",
                            error_message=(
                                f"TikTok rejected direct post (unaudited_client_can_only_post_to_private_accounts) "
                                f"and Inbox draft fallback failed ({inbox_err}).{user_hint}"
                            ),
                            attempts=1,
                            latency_ms=int((time.time() - start_time) * 1000)
                        )

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

        # Optional Dual-Delivery to Inbox when unaudited SELF_ONLY was forced and publish_method == 'dual'
        if privacy_level == "SELF_ONLY" and publish_method == "dual":
            try:
                inbox_res = upload_video_to_tiktok_inbox(c, local_file, token, title=title, creator_username=creator_username)
                if inbox_res.get("success"):
                    note = f"private_unaudited_app+inbox_draft:{inbox_res.get('publish_id')}"
            except Exception as inbox_err:
                logger.warning("[TikTok] Dual-delivery inbox mirror failed: %s", inbox_err)

        permalink = resolve_tiktok_permalink(
            publish_id=publish_id,
            creator_username=creator_username,
            public_ids=poll_res.get("publically_available_post_id"),
        )

        return PlatformResult(
            platform="tiktok",
            status="published",
            mode="live",
            remote_id=publish_id,
            permalink=permalink,
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
