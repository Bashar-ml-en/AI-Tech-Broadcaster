"""
Master Autonomous Omnichannel Dispatcher for AI Tech Broadcaster
Directly broadcasts to Facebook, Instagram, Threads, and TikTok concurrently with zero human approval gating.

Conforms strictly to P6 specifications:
- Entry point: dispatch_autonomous_broadcast(post_id, post_record, media)
- Modes:
    * simulate: all platforms simulated with realistic previews
    * auto: live when configured, simulated when unconfigured
    * live: live everywhere; unconfigured platforms fail with NOT_CONFIGURED
- Idempotency: skips platforms already published (or simulated on rerun) for this post_id
- Concurrency: ThreadPoolExecutor(max_workers=4) with complete isolation between platforms
- Persistence: writes outcome via update_publish_outcome and emits structured JSON logs
- Passive Telegram mirror: if TELEGRAM_MIRROR=true, mirrors post outside critical path
"""

import os
import sys
import time
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

from src.publish_types import PlatformResult, DispatchResult, MediaRef, OverallStatus, PlatformName
from src.publisher_meta import publish_to_facebook, publish_to_instagram, is_meta_configured
from src.publisher_threads import publish_to_threads, is_threads_configured
from src.publisher_tiktok import publish_to_tiktok, is_tiktok_configured

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

env_path = ROOT_DIR / "config" / ".env"
load_dotenv(dotenv_path=env_path)

DATABASE_PATH = os.getenv("DATABASE_PATH", str(ROOT_DIR / "storage" / "published_history.db"))
logger = logging.getLogger("publisher_autonomous")


def get_prior_platform_results(post_id: int) -> Dict[str, PlatformResult]:
    """Retrieve existing platform results from SQLite to ensure strict idempotency."""
    prior: Dict[str, PlatformResult] = {}
    try:
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT publish_results_json FROM posts WHERE id = ?", (post_id,)).fetchone()
            if row and row["publish_results_json"]:
                items = json.loads(row["publish_results_json"])
                for item in items:
                    pname = item.get("platform")
                    if pname:
                        prior[pname] = item
    except Exception as e:
        logger.warning("[Dispatcher] Failed to read prior publish results for post %s: %s", post_id, e)
    return prior


def _run_platform_worker(
    platform: str,
    post_record: Dict[str, Any],
    media_refs: List[MediaRef],
    publish_mode: str
) -> PlatformResult:
    """Execute dispatch for a single platform with full error isolation."""
    start_ts = time.time()
    try:
        if platform == "facebook":
            if publish_mode == "live" and not is_meta_configured():
                return PlatformResult(
                    platform="facebook",
                    status="failed",
                    mode="live",
                    error_code="NOT_CONFIGURED",
                    error_message="Meta credentials missing in live mode.",
                    attempts=1,
                    latency_ms=0
                )
            return publish_to_facebook(post_record, media_refs=media_refs)

        elif platform == "instagram":
            if publish_mode == "live" and not is_meta_configured():
                return PlatformResult(
                    platform="instagram",
                    status="failed",
                    mode="live",
                    error_code="NOT_CONFIGURED",
                    error_message="Meta credentials missing in live mode.",
                    attempts=1,
                    latency_ms=0
                )
            return publish_to_instagram(post_record, media_refs=media_refs)

        elif platform == "threads":
            if publish_mode == "live" and not is_threads_configured():
                return PlatformResult(
                    platform="threads",
                    status="failed",
                    mode="live",
                    error_code="NOT_CONFIGURED",
                    error_message="Threads credentials missing in live mode.",
                    attempts=1,
                    latency_ms=0
                )
            return publish_to_threads(post_record, media=media_refs)

        elif platform == "tiktok":
            if publish_mode == "live" and not is_tiktok_configured():
                return PlatformResult(
                    platform="tiktok",
                    status="failed",
                    mode="live",
                    error_code="NOT_CONFIGURED",
                    error_message="TikTok credentials missing in live mode.",
                    attempts=1,
                    latency_ms=0
                )
            primary_media = media_refs[0] if media_refs else None
            return publish_to_tiktok(post_record, media=primary_media)

        else:
            return PlatformResult(
                platform=platform,  # type: ignore
                status="skipped",
                mode="live" if publish_mode == "live" else "simulated",
                error_code="UNKNOWN_PLATFORM",
                error_message=f"Platform '{platform}' is not recognized.",
                attempts=0,
                latency_ms=0
            )

    except Exception as e:
        latency = int((time.time() - start_ts) * 1000)
        logger.exception("[Dispatcher] Exception in worker for platform %s: %s", platform, e)
        return PlatformResult(
            platform=platform,  # type: ignore
            status="failed",
            mode="live" if publish_mode == "live" else "simulated",
            error_code="WORKER_EXCEPTION",
            error_message=str(e),
            attempts=1,
            latency_ms=latency
        )


def compute_overall_status(results: List[PlatformResult]) -> OverallStatus:
    """
    Compute aggregate broadcast outcome conforming to P6 specification:
    - all published -> published
    - some published -> partial
    - all simulated -> simulated
    - none published/simulated -> failed
    """
    if not results:
        return "failed"

    statuses = [r.get("status") for r in results]
    published_count = sum(1 for s in statuses if s == "published")
    simulated_count = sum(1 for s in statuses if s == "simulated")
    failed_count = sum(1 for s in statuses if s == "failed")
    skipped_count = sum(1 for s in statuses if s == "skipped")

    # If any were skipped due to already being published, count them as published
    for r in results:
        if r.get("status") == "skipped" and r.get("note") == "already_published":
            published_count += 1
            skipped_count -= 1
        elif r.get("status") == "skipped" and r.get("note") == "already_simulated":
            simulated_count += 1
            skipped_count -= 1

    active_count = len(results) - skipped_count

    if published_count > 0:
        if published_count == active_count:
            return "published"
        return "partial"

    if simulated_count > 0:
        if failed_count == 0:
            return "simulated"
        return "simulated" if simulated_count >= failed_count else "failed"

    return "failed"


def mirror_to_telegram(post_record: Dict[str, Any], dispatch_result: DispatchResult) -> None:
    """Passive Telegram mirror executed outside the critical path."""
    try:
        results = dispatch_result.get("results", [])
        if any(r.get("platform") == "telegram" and r.get("status") == "published" for r in results):
            logger.info("[Telegram Mirror] Post #%s already published to Telegram channel directly. Skipping mirror.", dispatch_result.get("post_id"))
            return

        from src.webhook_server import publish_to_telegram_channel
        logger.info("[Telegram Mirror] Dispatching passive mirror for post #%s...", dispatch_result["post_id"])
        publish_to_telegram_channel(post_record)
    except Exception as e:
        logger.warning("[Telegram Mirror] Non-critical Telegram mirror failed: %s", e)


def dispatch_autonomous_broadcast(
    post_id: int,
    post_record: Dict[str, Any],
    media: Optional[List[MediaRef]] = None
) -> DispatchResult:
    """
    Master omnichannel entry point for publishing across Facebook, Instagram, Threads, and TikTok.

    Idempotent, concurrent, and isolated across platforms.
    """
    publish_mode = os.getenv("PUBLISH_MODE", "simulate").lower()
    enabled_str = os.getenv("ENABLED_PLATFORMS", "facebook,instagram,threads,tiktok")
    enabled_platforms = [p.strip().lower() for p in enabled_str.split(",") if p.strip()]

    media_list = media or []
    prior_results = get_prior_platform_results(post_id)

    final_results: List[PlatformResult] = []
    platforms_to_run: List[str] = []

    # 1. Idempotency Check per Platform
    for platform in enabled_platforms:
        if platform in prior_results:
            prior = prior_results[platform]
            prior_status = prior.get("status")

            # In live/auto mode: if already published, skip
            if prior_status == "published":
                logger.info("[Dispatcher] Post #%s already published to %s. Skipping.", post_id, platform)
                final_results.append(PlatformResult(
                    platform=platform,  # type: ignore
                    status="skipped",
                    mode=prior.get("mode", "live"),
                    remote_id=prior.get("remote_id"),
                    permalink=prior.get("permalink"),
                    attempts=prior.get("attempts", 1),
                    latency_ms=0,
                    note="already_published"
                ))
                continue

            # If already simulated in simulate or auto mode, skip
            if publish_mode in ("simulate", "auto") and prior_status == "simulated":
                logger.info("[Dispatcher] Post #%s already simulated for %s. Skipping.", post_id, platform)
                final_results.append(PlatformResult(
                    platform=platform,  # type: ignore
                    status="skipped",
                    mode="simulated",
                    remote_id=prior.get("remote_id"),
                    permalink=prior.get("permalink"),
                    attempts=prior.get("attempts", 1),
                    latency_ms=0,
                    note="already_simulated"
                ))
                continue

        platforms_to_run.append(platform)

    # 2. Concurrently execute remaining platforms
    if platforms_to_run:
        logger.info("[Dispatcher] Dispatching post #%s to platforms concurrently: %s", post_id, platforms_to_run)
        with ThreadPoolExecutor(max_workers=min(len(platforms_to_run), 4)) as executor:
            future_to_platform = {
                executor.submit(_run_platform_worker, p, post_record, media_list, publish_mode): p
                for p in platforms_to_run
            }
            for future in as_completed(future_to_platform):
                plat = future_to_platform[future]
                try:
                    res = future.result()
                    final_results.append(res)
                except Exception as exc:
                    logger.exception("[Dispatcher] Uncaught executor error for platform %s: %s", plat, exc)
                    final_results.append(PlatformResult(
                        platform=plat,  # type: ignore
                        status="failed",
                        mode="live" if publish_mode == "live" else "simulated",
                        error_code="EXECUTOR_FAILURE",
                        error_message=str(exc),
                        attempts=1,
                        latency_ms=0
                    ))

    # 3. Compute overall status
    overall = compute_overall_status(final_results)

    dispatch_result: DispatchResult = {
        "post_id": post_id,
        "overall": overall,
        "results": final_results,
        "timestamp": int(time.time())
    }

    # 4. Structured JSON Logging per platform
    for r in final_results:
        log_payload = {
            "event": "platform_dispatch",
            "post_id": post_id,
            "platform": r.get("platform"),
            "status": r.get("status"),
            "mode": r.get("mode"),
            "latency_ms": r.get("latency_ms", 0),
            "error_code": r.get("error_code"),
            "note": r.get("note")
        }
        logger.info(json.dumps(log_payload))

    # 5. Persist outcome to database
    try:
        from src.pipeline import update_publish_outcome
        update_publish_outcome(post_id, dispatch_result)
    except Exception as e:
        logger.error("[Dispatcher] Failed to persist outcome to DB for post %s: %s", post_id, e)

    # 6. Optional Telegram Mirror (passive, non-blocking)
    telegram_mirror = os.getenv("TELEGRAM_MIRROR", "false").lower() in ("true", "1", "yes")
    if telegram_mirror:
        mirror_to_telegram(post_record, dispatch_result)

    logger.info(
        "[Dispatcher] Broadcast completed for post #%s with overall status: '%s' (%d platforms)",
        post_id, overall, len(final_results)
    )
    return dispatch_result
