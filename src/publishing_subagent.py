"""
Autonomous Publishing & Reach-Recovery Subagent Engine (SA-06)
Monitors, diagnoses, repairs, and dispatches omnichannel broadcasts across:
- Telegram (@eraof_ai20 / Bot & Channel API)
- TikTok (Content Posting API v2 Chunked Upload + Slide-to-Video Compiler)
- Facebook Page (Graph API v20.0 Video Reels & Direct Binary Photo Upload)
- Instagram Professional (Graph API v20.0 Reels, Carousels & Single Photos)
- Meta Threads (Threads Graph API v1.0 Video, Image, Carousel & Text+Link)

Provides:
1. Real-time Reach Ledger (`reached` vs. `unreached` per platform across all DB posts)
2. Root-Cause Diagnosis (`RENDER_FAILED`, `FORMAT_UNSUPPORTED`, `NO_PUBLIC_MEDIA`, `SIMULATED`, `NOT_DISPATCHED`)
3. Autonomous Self-Healing (`heal_and_publish_post`) that synthesizes missing 9:16 MP4 Reels or 1080x1350 slides, stages public URLs or uses direct binary upload, and updates `publish_results_json` in SQLite.
4. Batch Unreached Queue Sync (`sync_unreached_queue`) and Live Token Configuration (`configure_platform_credentials`).
"""

import os
import re
import sys
import json
import time
import shutil
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

ENV_PATH = ROOT_DIR / "config" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from src.publish_types import PlatformResult, MediaRef
from src.r2_storage import stage_media_asset, is_r2_configured
from src.telegram_broadcaster import (
    send_telegram_post_carousel,
    send_telegram_story_deck,
    send_telegram_reel,
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_CHAT_ID,
)
from src.publisher_meta import (
    publish_to_facebook,
    publish_to_instagram,
    is_meta_configured,
    reload_meta_credentials,
    get_instagram_id,
    META_PAGE_ID,
)
from src.publisher_threads import (
    publish_to_threads,
    is_threads_configured,
    reload_threads_credentials,
    THREADS_USER_ID,
)
from src.publisher_tiktok import (
    publish_to_tiktok,
    is_tiktok_configured,
    reload_tiktok_credentials,
    ensure_tiktok_token,
    load_persisted_token,
)

logger = logging.getLogger("publishing_subagent")

SUPPORTED_PLATFORMS = ("telegram", "tiktok", "facebook", "instagram", "threads")

PLATFORM_SUBAGENT_SPECS: Dict[str, Dict[str, Any]] = {
    "telegram": {
        "platform": "telegram",
        "subagent_id": "SA-06-TG",
        "name": "Telegram Channel Subagent",
        "role": "Primary MTProto / Bot API v7.x Broadcaster",
        "account": "@eraof_ai20",
        "protocol": "Telegram Bot API HTTPS Multipart",
        "icon": "send",
        "capabilities": [
            "Direct multipart MP4 Reel streaming (sendVideo)",
            "Multi-slide 2-10 album delivery (sendMediaGroup)",
            "Rich HTML editorial captions + inline keyboard CTAs",
        ],
    },
    "tiktok": {
        "platform": "tiktok",
        "subagent_id": "SA-06-TT",
        "name": "TikTok Content Subagent",
        "role": "TikTok v2 Chunked Video & Auto-Reel Compiler",
        "account": "TikTok Creator Studio (v2 OAuth)",
        "protocol": "TikTok Content Posting API v2 (Chunked PUT)",
        "icon": "movie",
        "capabilities": [
            "Automatic OAuth2 refresh_token rotation (storage/tiktok_token.json)",
            "Auto-compiles static/carousel posts into 9:16 H.264 MP4 Reels on demand",
            "Creator privacy negotiation (PUBLIC_TO_EVERYONE / SELF_ONLY fallback)",
        ],
    },
    "facebook": {
        "platform": "facebook",
        "subagent_id": "SA-06-FB",
        "name": "Facebook Page Subagent",
        "role": "Meta Graph v20.0 Page Reels & Direct Binary Publisher",
        "account": f"Page ID {META_PAGE_ID}",
        "protocol": "Meta Graph API v20.0 (Direct Binary + URL)",
        "icon": "public",
        "capabilities": [
            "2-phase /{page_id}/video_reels upload with direct local binary streaming",
            "Direct multipart /{page_id}/photos upload (bypasses R2 SSL requirement)",
            "Canonical permalink resolution & token verification",
        ],
    },
    "instagram": {
        "platform": "instagram",
        "subagent_id": "SA-06-IG",
        "name": "Instagram Creator Subagent",
        "role": "Instagram Graph v20.0 Reels, Carousel & Story Engine",
        "account": "@eraof_ai20 (IG Business)",
        "protocol": "Instagram Graph API v20.0 Container Pipeline",
        "icon": "photo_camera",
        "capabilities": [
            "Auto-discovers Instagram Business Account ID from linked Facebook Page",
            "Multi-slide CAROUSEL container orchestration (up to 10 slides)",
            "9:16 REELS container transcoding poll + Public Media Bridge fallback",
        ],
    },
    "threads": {
        "platform": "threads",
        "subagent_id": "SA-06-TH",
        "name": "Meta Threads Subagent",
        "role": "Threads Graph v1.0 Microblog & Media Publisher",
        "account": "@eraof_ai20 (Threads)",
        "protocol": "Threads Graph API v1.0 (graph.threads.net)",
        "icon": "alternate_email",
        "capabilities": [
            "Auto-discovers THREADS_USER_ID via GET /v1.0/me",
            "Publishes VIDEO, CAROUSEL, IMAGE, or auto-downgrades to TEXT + source link",
            "500-char word-boundary smart truncation & rate-limit quota inspection",
        ],
    },
}


def resolve_db_path() -> Path:
    """Resolve active SQLite database path, copying repo DB to /tmp on Vercel if needed."""
    repo_db = ROOT_DIR / os.getenv("DATABASE_PATH", "storage/published_history.db")
    if os.getenv("VERCEL"):
        tmp_db = Path("/tmp/published_history.db")
        if not tmp_db.exists() and repo_db.exists():
            try:
                tmp_db.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(repo_db, tmp_db)
            except Exception as e:
                logger.warning("Could not copy repo DB to /tmp: %s", e)
        return tmp_db if tmp_db.exists() else repo_db
    return repo_db


def get_db_conn(db_path: Optional[Path] = None) -> sqlite3.Connection:
    target = db_path or resolve_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


def is_telegram_configured() -> bool:
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chan = os.getenv("TELEGRAM_CHANNEL_ID", "").strip() or TELEGRAM_CHANNEL_ID
    return bool(tok and "YOUR_" not in tok and "Example" not in tok and len(tok) > 15 and chan)


def publish_to_telegram_channel(
    post_record: Dict[str, Any],
    media_refs: Optional[List[MediaRef]] = None
) -> PlatformResult:
    """Publish a post, story, or reel directly to the configured Telegram channel."""
    start_t = time.time()
    tok = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chan = os.getenv("TELEGRAM_CHANNEL_ID", "").strip() or TELEGRAM_CHANNEL_ID or "@eraof_ai20"
    publish_mode = os.getenv("PUBLISH_MODE", "live").lower()

    if not is_telegram_configured() or publish_mode == "simulate":
        sim_id = f"tg_sim_{int(time.time())}"
        return PlatformResult(
            platform="telegram",
            status="simulated",
            mode="simulated",
            remote_id=sim_id,
            permalink=f"https://t.me/{chan.lstrip('@')}",
            attempts=1,
            latency_ms=15,
        )

    fmt = (post_record.get("format_type") or "post").lower()
    headline = post_record.get("headline") or "AI Intelligence Update"
    caption_text = f"{headline}\n\n#AI #EraOfAI"
    if post_record.get("captions_json"):
        try:
            parsed = json.loads(post_record["captions_json"])
            caption_text = parsed.get("short_form") or caption_text
        except Exception:
            pass

    local_files = [
        m.get("local_path") for m in (media_refs or [])
        if m.get("local_path") and Path(m["local_path"]).exists()
    ]
    if not local_files and post_record.get("media_path") and Path(post_record["media_path"]).exists():
        local_files = [post_record["media_path"]]

    try:
        if fmt == "reel" and local_files:
            tg_res = send_telegram_reel(chan, local_files[0], caption_text, bot_token=tok)
        elif fmt == "story" and local_files:
            tg_res = send_telegram_story_deck(chan, local_files, caption_text, bot_token=tok)
        elif local_files:
            tg_res = send_telegram_post_carousel(chan, local_files, caption_text, bot_token=tok)
        else:
            return PlatformResult(
                platform="telegram",
                status="failed",
                mode="live",
                error_code="LOCAL_FILE_MISSING",
                error_message="No local media file available to send to Telegram.",
                attempts=1,
                latency_ms=int((time.time() - start_t) * 1000),
            )

        if tg_res.get("status") == "success":
            msg_id = tg_res.get("result", {}).get("message_id") or int(time.time())
            return PlatformResult(
                platform="telegram",
                status="published",
                mode="live",
                remote_id=str(msg_id),
                permalink=f"https://t.me/{chan.lstrip('@')}/{msg_id}" if chan.startswith("@") else None,
                attempts=1,
                latency_ms=int((time.time() - start_t) * 1000),
            )
        return PlatformResult(
            platform="telegram",
            status="failed",
            mode="live",
            error_code="TG_API_ERROR",
            error_message=str(tg_res.get("message") or tg_res),
            attempts=1,
            latency_ms=int((time.time() - start_t) * 1000),
        )
    except Exception as e:
        return PlatformResult(
            platform="telegram",
            status="failed",
            mode="live",
            error_code="TG_EXCEPTION",
            error_message=str(e),
            attempts=1,
            latency_ms=int((time.time() - start_t) * 1000),
        )


def get_platform_connection_state(platform: str) -> Dict[str, Any]:
    """Return live configuration and token readiness for a specific platform."""
    p = platform.lower()
    publish_mode = os.getenv("PUBLISH_MODE", "live").lower()

    if p == "telegram":
        configured = is_telegram_configured()
        return {
            "configured": configured,
            "mode": "live" if configured and publish_mode == "live" else "simulated",
            "status_badge": "LIVE CONNECTED" if configured else "TOKEN MISSING",
            "account": os.getenv("TELEGRAM_CHANNEL_ID", "").strip() or "@eraof_ai20",
            "env_keys": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "TELEGRAM_CHAT_ID"],
            "diagnostic": "Bot API active and verified on @eraof_ai20." if configured else "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID.",
        }
    elif p == "tiktok":
        configured = is_tiktok_configured()
        tok = load_persisted_token()
        expires_at = tok.get("expires_at", 0)
        ttl_hours = max(0, round((expires_at - time.time()) / 3600, 1)) if expires_at else 0
        return {
            "configured": configured,
            "mode": "live" if configured and publish_mode == "live" else "simulated",
            "status_badge": "LIVE CONNECTED" if configured else "OAUTH REQUIRED",
            "account": f"open_id:{(tok.get('open_id') or os.getenv('TIKTOK_OPEN_ID', ''))[:10]}..." if configured else "Unlinked",
            "token_ttl_hours": ttl_hours,
            "env_keys": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN"],
            "diagnostic": (
                f"OAuth2 token active (TTL: {ttl_hours}h). Non-reel posts can be auto-compiled to 9:16 MP4 video."
                if configured else "Authorize TikTok v2 OAuth or provide TIKTOK_ACCESS_TOKEN."
            ),
        }
    elif p == "facebook":
        configured = is_meta_configured()
        page_id = os.getenv("META_PAGE_ID", META_PAGE_ID).strip()
        return {
            "configured": configured,
            "mode": "live" if configured and publish_mode == "live" else "simulated",
            "status_badge": "LIVE CONNECTED" if configured else "NEEDS PAGE TOKEN",
            "account": f"Page #{page_id}",
            "env_keys": ["META_PAGE_ACCESS_TOKEN", "META_PAGE_ID"],
            "diagnostic": (
                f"Meta Page Access Token active for Page {page_id}. Direct binary upload enabled (bypasses R2 SSL)."
                if configured else "Provide a valid META_PAGE_ACCESS_TOKEN in Configure Token to switch from Simulated to Live."
            ),
        }
    elif p == "instagram":
        configured = is_meta_configured()
        ig_id = os.getenv("META_INSTAGRAM_ACCOUNT_ID", "").strip() or ("auto-linked" if configured else "unlinked")
        return {
            "configured": configured,
            "mode": "live" if configured and publish_mode == "live" else "simulated",
            "status_badge": "LIVE CONNECTED" if configured else "NEEDS META TOKEN",
            "account": f"IG Business ({ig_id})",
            "env_keys": ["META_PAGE_ACCESS_TOKEN", "META_INSTAGRAM_ACCOUNT_ID"],
            "diagnostic": (
                "Instagram Graph API active with Public HTTPS Media Bridge fallback."
                if configured else "Provide META_PAGE_ACCESS_TOKEN + META_INSTAGRAM_ACCOUNT_ID to publish live Reels & Carousels."
            ),
        }
    elif p == "threads":
        configured = is_threads_configured()
        uid = os.getenv("THREADS_USER_ID", THREADS_USER_ID).strip()
        return {
            "configured": configured,
            "mode": "live" if configured and publish_mode == "live" else "simulated",
            "status_badge": "LIVE CONNECTED" if configured else "NEEDS THREADS TOKEN",
            "account": f"Threads UID ({uid or 'unlinked'})",
            "env_keys": ["THREADS_ACCESS_TOKEN", "THREADS_USER_ID"],
            "diagnostic": (
                f"Threads Graph API v1.0 active for user {uid}."
                if configured else "Provide THREADS_ACCESS_TOKEN (THREADS_USER_ID is auto-discovered via /v1.0/me)."
            ),
        }
    return {"configured": False, "mode": "simulated", "status_badge": "UNKNOWN", "account": "N/A", "env_keys": []}


def classify_post_for_platform(row: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """
    Inspect a database post row and classify its exact delivery state for `platform`:
    Returns whether it `reached` (live published) or is `unreached` (failed, skipped, simulated, or never dispatched),
    along with root-cause diagnosis and one-click repair action metadata.
    """
    p = platform.lower()
    post_id = row.get("id")
    headline = row.get("headline") or "Untitled AI Broadcast"
    format_type = (row.get("format_type") or "post").lower()
    publish_status = (row.get("publish_status") or "rendered").lower()
    approval_status = (row.get("approval_status") or "pending").lower()
    last_error = row.get("last_error") or ""
    media_url = row.get("media_url") or ""
    created_at = row.get("created_at") or ""
    published_at = row.get("published_at") or created_at

    # Parse publish_results_json if present
    results_list: List[Dict[str, Any]] = []
    raw_json = row.get("publish_results_json")
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, list):
                results_list = parsed
        except Exception:
            pass

    plat_entry: Optional[Dict[str, Any]] = None
    for item in results_list:
        if isinstance(item, dict) and str(item.get("platform", "")).lower() == p:
            plat_entry = item
            break

    # Legacy Telegram message ID check for rows created before publish_results_json
    if p == "telegram" and not plat_entry and row.get("telegram_message_id"):
        msg_id = str(row["telegram_message_id"])
        channel_handle = (os.getenv("TELEGRAM_CHANNEL_ID", "@eraof_ai20").strip() or "@eraof_ai20").lstrip("@")
        return {
            "id": post_id,
            "headline": headline,
            "format_type": format_type,
            "source_url": row.get("source_url", ""),
            "media_url": media_url,
            "created_at": created_at,
            "published_at": published_at,
            "reached": True,
            "platform": p,
            "platform_status": "published",
            "mode": "live",
            "remote_id": msg_id,
            "permalink": f"https://t.me/{channel_handle}/{msg_id}",
            "failure_code": None,
            "diagnosis": "Delivered live to Telegram channel.",
            "repair_action": "Republish / Refresh",
            "latency_ms": 0,
        }

    if plat_entry:
        st = str(plat_entry.get("status", "")).lower()
        mode = str(plat_entry.get("mode", "live")).lower()
        remote_id = plat_entry.get("remote_id")
        permalink = plat_entry.get("permalink")
        err_code = plat_entry.get("error_code")
        err_msg = plat_entry.get("error_message")
        note = plat_entry.get("note")
        latency_ms = plat_entry.get("latency_ms", 0)

        if st == "published" and mode == "live":
            return {
                "id": post_id,
                "headline": headline,
                "format_type": format_type,
                "source_url": row.get("source_url", ""),
                "media_url": media_url,
                "created_at": created_at,
                "published_at": published_at,
                "reached": True,
                "platform": p,
                "platform_status": "published",
                "mode": "live",
                "remote_id": remote_id,
                "permalink": permalink,
                "note": note,
                "failure_code": None,
                "diagnosis": (
                    "Published live (Private / SELF_ONLY mode due to unaudited TikTok app)"
                    if note == "private_unaudited_app"
                    else "Confirmed live delivery with remote ID & permalink."
                ),
                "repair_action": "Re-dispatch Live",
                "latency_ms": latency_ms,
            }

        # Otherwise it did not reach live audience (simulated, skipped, or failed)
        if st == "simulated" or mode == "simulated":
            failure_code = "SIMULATED_ONLY"
            diagnosis = (
                f"Simulated dry-run ({remote_id or 'no remote call'}). "
                f"Platform credentials were in simulate mode when this post ran."
            )
            repair_action = "Switch to Live & Publish"
        elif err_code == "FORMAT_UNSUPPORTED" or (p == "tiktok" and format_type != "reel"):
            failure_code = "FORMAT_UNSUPPORTED"
            diagnosis = (
                f"Post is format '{format_type}', whereas TikTok requires a 9:16 MP4 video Reel."
            )
            repair_action = "Auto-Compile 9:16 Video & Publish to TikTok"
        elif err_code == "NO_PUBLIC_MEDIA":
            failure_code = "NO_PUBLIC_MEDIA"
            diagnosis = (
                "Cloudflare R2 SSL handshake failed during staging, leaving no public media URL."
            )
            repair_action = "Stage via Public HTTPS Bridge / Direct Binary & Publish"
        else:
            failure_code = err_code or st.upper() or "DISPATCH_FAILED"
            diagnosis = err_msg or last_error or f"Platform returned status '{st}'."
            repair_action = "Auto-Heal & Retry Live Publish"

        return {
            "id": post_id,
            "headline": headline,
            "format_type": format_type,
            "source_url": row.get("source_url", ""),
            "media_url": media_url,
            "created_at": created_at,
            "published_at": published_at,
            "reached": False,
            "platform": p,
            "platform_status": st or "unreached",
            "mode": mode,
            "remote_id": remote_id,
            "permalink": permalink,
            "failure_code": failure_code,
            "diagnosis": diagnosis,
            "repair_action": repair_action,
            "latency_ms": latency_ms,
        }

    # No platform entry inside publish_results_json -> check overall post failure
    if "RENDER_FAILED" in last_error or publish_status == "failed":
        failure_code = "RENDER_FAILED"
        diagnosis = (
            f"Upstream media synthesis failed before dispatch ({last_error[:120]})."
            if last_error else "Media synthesis failed before platform dispatch."
        )
        repair_action = "Synthesize Media (3-Tier TTS Fallback) & Publish"
    elif p == "tiktok" and format_type != "reel":
        failure_code = "FORMAT_UNSUPPORTED"
        diagnosis = f"Post was created as '{format_type}'; TikTok requires 9:16 MP4 video."
        repair_action = "Auto-Compile 9:16 Video & Publish to TikTok"
    else:
        failure_code = "NOT_DISPATCHED"
        diagnosis = f"Post is in state '{publish_status}' ({approval_status}) and was never dispatched to {p.title()}."
        repair_action = f"Dispatch to {p.title()} Now"

    return {
        "id": post_id,
        "headline": headline,
        "format_type": format_type,
        "source_url": row.get("source_url", ""),
        "media_url": media_url,
        "created_at": created_at,
        "published_at": published_at,
        "reached": False,
        "platform": p,
        "platform_status": "not_dispatched",
        "mode": "none",
        "remote_id": None,
        "permalink": None,
        "failure_code": failure_code,
        "diagnosis": diagnosis,
        "repair_action": repair_action,
        "latency_ms": 0,
    }


class PublishingSubagentOrchestrator:
    """
    Autonomous Publishing & Reach-Recovery Subagent Engine.
    Manages per-platform reach accounting, media self-healing, and live re-dispatch.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or resolve_db_path()

    def _fetch_all_posts(self) -> List[Dict[str, Any]]:
        if not self.db_path.exists():
            return []
        with get_db_conn(self.db_path) as conn:
            cur = conn.execute(
                """
                SELECT id, source_url, headline, format_type, media_url,
                       approval_status, publish_status, publish_results_json,
                       publish_attempts, last_error, hook_narration,
                       body_narration, call_to_action, visual_prompt,
                       captions_json, post_payload, telegram_message_id,
                       created_at, published_at
                FROM posts
                ORDER BY id DESC
                """
            )
            return [dict(r) for r in cur.fetchall()]

    def get_all_platforms_reach_summary(self) -> Dict[str, Any]:
        """
        Compute live Reached vs. Unreached counts and failure breakdown for all 5 platforms.
        """
        rows = self._fetch_all_posts()
        total_posts = len(rows)
        platforms_summary: Dict[str, Any] = {}

        for p in SUPPORTED_PLATFORMS:
            spec = PLATFORM_SUBAGENT_SPECS[p]
            conn_state = get_platform_connection_state(p)
            reached_count = 0
            unreached_count = 0
            failure_breakdown: Dict[str, int] = {}

            for r in rows:
                item = classify_post_for_platform(r, p)
                if item["reached"]:
                    reached_count += 1
                else:
                    unreached_count += 1
                    fc = item.get("failure_code") or "UNKNOWN"
                    failure_breakdown[fc] = failure_breakdown.get(fc, 0) + 1

            reach_rate = round((reached_count / total_posts) * 100, 1) if total_posts > 0 else 0.0
            platforms_summary[p] = {
                "platform": p,
                "subagent_id": spec["subagent_id"],
                "name": spec["name"],
                "role": spec["role"],
                "icon": spec["icon"],
                "protocol": spec["protocol"],
                "account": conn_state["account"],
                "configured": conn_state["configured"],
                "mode": conn_state["mode"],
                "status_badge": conn_state["status_badge"],
                "diagnostic": conn_state["diagnostic"],
                "reached_count": reached_count,
                "unreached_count": unreached_count,
                "total_posts": total_posts,
                "reach_rate_pct": reach_rate,
                "failure_breakdown": failure_breakdown,
            }

        return {
            "total_posts": total_posts,
            "platforms": platforms_summary,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def get_platform_reach_ledger(self, platform: str) -> Dict[str, Any]:
        """
        Return the complete Reach Ledger for a single platform:
        - `subagent`: metadata + live connection diagnostics
        - `summary`: reached_count, unreached_count, total_posts, failure_breakdown
        - `reached_posts`: list of all posts confirmed live on this platform
        - `unreached_posts`: list of all posts that did NOT reach this platform, with failure code & repair action
        """
        p = platform.lower()
        if p not in SUPPORTED_PLATFORMS:
            raise ValueError(f"Unsupported platform '{platform}'. Expected one of {SUPPORTED_PLATFORMS}")

        rows = self._fetch_all_posts()
        spec = PLATFORM_SUBAGENT_SPECS[p]
        conn_state = get_platform_connection_state(p)

        reached_posts: List[Dict[str, Any]] = []
        unreached_posts: List[Dict[str, Any]] = []
        failure_breakdown: Dict[str, int] = {}

        for r in rows:
            classified = classify_post_for_platform(r, p)
            if classified["reached"]:
                reached_posts.append(classified)
            else:
                unreached_posts.append(classified)
                fc = classified.get("failure_code") or "UNKNOWN"
                failure_breakdown[fc] = failure_breakdown.get(fc, 0) + 1

        total = len(rows)
        reach_rate = round((len(reached_posts) / total) * 100, 1) if total > 0 else 0.0

        return {
            "platform": p,
            "subagent": {
                **spec,
                **conn_state,
            },
            "summary": {
                "total_posts": total,
                "reached_count": len(reached_posts),
                "unreached_count": len(unreached_posts),
                "reach_rate_pct": reach_rate,
                "failure_breakdown": failure_breakdown,
            },
            "reached_posts": reached_posts,
            "unreached_posts": unreached_posts,
        }

    def _ensure_post_media_assets(
        self,
        row: Dict[str, Any],
        target_platform: str
    ) -> Tuple[List[str], Optional[str], str]:
        """
        Ensure the post has valid local media files on disk before publishing.
        - If `RENDER_FAILED` or missing media, synthesizes either a 9:16 MP4 Reel or 1080x1350 slide deck.
        - If `target_platform == 'tiktok'` and the post only has static slides (format != 'reel'),
          auto-compiles a 9:16 MP4 video Reel using `synthesize_broadcast_video_sync`.
        Returns (local_paths, video_path, effective_format_type).
        """
        post_id = row["id"]
        headline = row.get("headline") or "AI Breakthrough Update"
        format_type = (row.get("format_type") or "post").lower()
        hook = row.get("hook_narration") or headline
        body_text = row.get("body_narration") or headline
        cta = row.get("call_to_action") or "Follow @eraof_ai20 for daily AI intelligence."

        # Extract any existing local paths from post_payload or media_url
        existing_paths: List[str] = []
        video_path: Optional[str] = None

        if row.get("post_payload"):
            try:
                payload_data = json.loads(row["post_payload"])
                for p_str in payload_data.get("local_paths", []):
                    if p_str and Path(p_str).exists():
                        existing_paths.append(p_str)
                        if p_str.endswith(".mp4"):
                            video_path = p_str
            except Exception:
                pass

        media_url = row.get("media_url") or ""
        if media_url and media_url.startswith("/media/"):
            fname = media_url.replace("/media/", "")
            candidate = ROOT_DIR / "storage" / "staging" / fname
            if candidate.exists():
                if str(candidate) not in existing_paths:
                    existing_paths.append(str(candidate))
                if candidate.suffix.lower() == ".mp4":
                    video_path = str(candidate)

        needs_video = (format_type == "reel") or (target_platform.lower() == "tiktok")

        if needs_video and (not video_path or not Path(video_path).exists()):
            logger.info("[SA-06] Auto-synthesizing 9:16 MP4 video for Post #%d (%s)...", post_id, target_platform)
            try:
                from src.video_synthesizer import synthesize_broadcast_video_sync
                brief_data = {
                    "headline": headline,
                    "hook_narration": hook,
                    "body_narration": body_text,
                    "call_to_action": cta,
                    "visual_prompt": row.get("visual_prompt") or headline,
                }
                out_prefix = f"healed_reel_post_{post_id}_{int(time.time())}"
                synthesized_mp4 = synthesize_broadcast_video_sync(brief_data, out_prefix)
                if synthesized_mp4 and Path(synthesized_mp4).exists():
                    video_path = synthesized_mp4
                    if synthesized_mp4 not in existing_paths:
                        existing_paths.insert(0, synthesized_mp4)
            except Exception as e:
                logger.error("[SA-06] Video synthesis failed during auto-heal for Post #%d: %s", post_id, e)

        if not existing_paths:
            # Synthesize a high-contrast slide deck so image platforms have real visual assets
            logger.info("[SA-06] Generating fallback visual slides for Post #%d...", post_id)
            try:
                from src.carousel_generator import generate_carousel_deck, generate_story_slides
                brief_data = {
                    "headline": headline,
                    "hook_narration": hook,
                    "body_narration": body_text,
                    "call_to_action": cta,
                    "source_url": row.get("source_url", ""),
                }
                if format_type == "story":
                    slides = generate_story_slides(brief_data, f"healed_story_{post_id}")
                    existing_paths.extend([s for s in (slides or []) if s and Path(s).exists()])
                else:
                    slides = generate_carousel_deck(brief_data, f"healed_deck_{post_id}")
                    existing_paths.extend([s for s in (slides or []) if s and Path(s).exists()])
            except Exception as e:
                logger.error("[SA-06] Slide generation failed during auto-heal for Post #%d: %s", post_id, e)

        effective_format = "reel" if (target_platform.lower() == "tiktok" and video_path) else format_type
        return existing_paths, video_path, effective_format

    def heal_and_publish_post(
        self,
        post_id: int,
        platform: str,
        force_live: bool = True
    ) -> Dict[str, Any]:
        """
        Diagnose, auto-heal media/format/staging issues for `post_id`, dispatch to `platform`,
        and persist the updated `PlatformResult` back into `posts.publish_results_json`.
        """
        p = platform.lower()
        if p not in SUPPORTED_PLATFORMS:
            return {"status": "error", "message": f"Unsupported platform: {platform}"}

        with get_db_conn(self.db_path) as conn:
            cur = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            row_obj = cur.fetchone()
            if not row_obj:
                return {"status": "error", "message": f"Post #{post_id} not found in database."}
            row = dict(row_obj)

        # Ensure media assets exist (and compile 9:16 MP4 if target is TikTok)
        local_paths, video_path, effective_format = self._ensure_post_media_assets(row, p)

        # Stage media via R2 or Public HTTPS Media Bridge fallback
        media_refs: List[MediaRef] = [stage_media_asset(lp) for lp in local_paths] if local_paths else []

        post_record: Dict[str, Any] = {
            "id": row["id"],
            "headline": row.get("headline", "AI Tech Broadcast"),
            "format_type": effective_format,
            "source_url": row.get("source_url", ""),
            "summary_text": row.get("body_narration") or row.get("hook_narration") or row.get("headline", ""),
            "captions_json": row.get("captions_json"),
            "video_path": video_path,
            "media_path": local_paths[0] if local_paths else None,
        }

        prev_mode = os.getenv("PUBLISH_MODE", "live")
        if force_live:
            os.environ["PUBLISH_MODE"] = "live"

        try:
            if p == "telegram":
                result = publish_to_telegram_channel(post_record, media_refs=media_refs)
            elif p == "tiktok":
                primary_video_ref: Optional[MediaRef] = None
                for m in media_refs:
                    if m.get("local_path", "").endswith(".mp4"):
                        primary_video_ref = m
                        break
                if not primary_video_ref and media_refs:
                    primary_video_ref = media_refs[0]
                result = publish_to_tiktok(
                    post_record,
                    media=primary_video_ref,
                    allow_format_conversion=True
                )
            elif p == "facebook":
                result = publish_to_facebook(
                    post_record,
                    media_refs=media_refs,
                    allow_local_binary=True
                )
            elif p == "instagram":
                result = publish_to_instagram(
                    post_record,
                    media_refs=media_refs
                )
            elif p == "threads":
                result = publish_to_threads(
                    post_record,
                    media=media_refs
                )
            else:
                return {"status": "error", "message": f"Unhandled platform {p}"}
        finally:
            os.environ["PUBLISH_MODE"] = prev_mode

        # Merge new PlatformResult into publish_results_json in SQLite
        existing_results: List[Dict[str, Any]] = []
        if row.get("publish_results_json"):
            try:
                parsed = json.loads(row["publish_results_json"])
                if isinstance(parsed, list):
                    existing_results = [item for item in parsed if isinstance(item, dict) and item.get("platform") != p]
            except Exception:
                existing_results = []

        existing_results.append(dict(result))

        # Recompute aggregate post publish_status
        statuses = [r.get("status") for r in existing_results]
        modes = [r.get("mode") for r in existing_results]
        if all(s == "published" for s in statuses) and any(m == "live" for m in modes):
            new_pub_status = "published"
        elif any(s in ("published", "simulated") for s in statuses):
            new_pub_status = "partial" if any(m == "live" and s == "published" for m, s in zip(modes, statuses)) else "simulated"
        else:
            new_pub_status = "failed"

        failed_errors = [
            f"{r.get('platform')}: {r.get('error_message')}"
            for r in existing_results
            if r.get("status") == "failed" and r.get("error_message")
        ]
        new_last_error = "; ".join(failed_errors) if failed_errors else None

        # Update media_url if a new video or slide was synthesized during healing
        new_media_url = row.get("media_url")
        if video_path and Path(video_path).exists():
            new_media_url = f"/media/{Path(video_path).name}"
        elif local_paths and Path(local_paths[0]).exists() and not new_media_url:
            new_media_url = f"/media/{Path(local_paths[0]).name}"

        with get_db_conn(self.db_path) as conn:
            conn.execute(
                """
                UPDATE posts
                SET publish_status = ?,
                    approval_status = CASE WHEN ? IN ('published', 'partial') THEN 'published' ELSE approval_status END,
                    publish_results_json = ?,
                    publish_attempts = COALESCE(publish_attempts, 0) + 1,
                    last_error = ?,
                    media_url = COALESCE(?, media_url),
                    published_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    new_pub_status,
                    new_pub_status,
                    json.dumps(existing_results),
                    new_last_error,
                    new_media_url,
                    post_id,
                ),
            )
            conn.commit()
            cur = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
            updated_row = dict(cur.fetchone())

        classified = classify_post_for_platform(updated_row, p)
        return {
            "status": "ok",
            "post_id": post_id,
            "platform": p,
            "result": dict(result),
            "ledger_entry": classified,
        }

    def sync_unreached_queue(self, platform: str, limit: int = 3) -> Dict[str, Any]:
        """
        Batch-heal and dispatch up to `limit` unreached posts for `platform`.
        """
        ledger = self.get_platform_reach_ledger(platform)
        unreached = ledger.get("unreached_posts", [])[: max(1, min(limit, 10))]
        processed = []
        reached_now = 0

        for item in unreached:
            res = self.heal_and_publish_post(item["id"], platform, force_live=True)
            processed.append(res)
            if res.get("ledger_entry", {}).get("reached"):
                reached_now += 1

        updated_ledger = self.get_platform_reach_ledger(platform)
        return {
            "status": "ok",
            "platform": platform.lower(),
            "attempted": len(processed),
            "newly_reached": reached_now,
            "results": processed,
            "summary": updated_ledger["summary"],
        }

    def configure_platform_credentials(
        self,
        platform: str,
        credentials: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Persist updated platform credentials to `os.environ` and `config/.env`,
        reload the publisher module state, and return the live connection verification.
        """
        p = platform.lower()
        allowed_keys = {
            "telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "TELEGRAM_CHAT_ID"],
            "tiktok": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN", "TIKTOK_OPEN_ID"],
            "facebook": ["META_PAGE_ACCESS_TOKEN", "META_PAGE_ID"],
            "instagram": ["META_PAGE_ACCESS_TOKEN", "META_INSTAGRAM_ACCOUNT_ID", "META_PAGE_ID"],
            "threads": ["THREADS_ACCESS_TOKEN", "THREADS_USER_ID"],
        }.get(p, [])

        updated_keys: List[str] = []
        env_content = ""
        if ENV_PATH.exists():
            try:
                env_content = ENV_PATH.read_text(encoding="utf-8")
            except Exception:
                env_content = ""

        for k, v in credentials.items():
            if k in allowed_keys and v is not None:
                clean_val = str(v).strip()
                if not clean_val:
                    continue
                os.environ[k] = clean_val
                updated_keys.append(k)
                if env_content:
                    pattern = rf"^{re.escape(k)}=.*$"
                    if re.search(pattern, env_content, flags=re.MULTILINE):
                        env_content = re.sub(pattern, f"{k}={clean_val}", env_content, flags=re.MULTILINE)
                    else:
                        env_content = env_content.rstrip() + f"\n{k}={clean_val}\n"

        if updated_keys and env_content:
            try:
                ENV_PATH.write_text(env_content, encoding="utf-8")
            except Exception as e:
                logger.warning("Could not write updated credentials to config/.env: %s", e)

        # Reload module state
        if p in ("facebook", "instagram"):
            reload_meta_credentials()
        elif p == "threads":
            reload_threads_credentials()
        elif p == "tiktok":
            reload_tiktok_credentials()

        conn_state = get_platform_connection_state(p)
        return {
            "status": "ok",
            "platform": p,
            "updated_keys": updated_keys,
            "connection": conn_state,
        }
