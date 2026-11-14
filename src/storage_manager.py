"""
Automated Staging Storage & Cache Lifecycle Manager for AI Tech Broadcaster
Protects disk integrity by purging temporary video/audio/image assets older than TTL,
while preserving files referenced by recent active posts and system assets.
"""

import os
import time
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, Set, Optional, List

logger = logging.getLogger("storage_manager")

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT_DIR / "storage" / "staging"
DATABASE_PATH = ROOT_DIR / "storage" / "published_history.db"

PERMANENT_ASSET_PATTERNS = {
    ".gitkeep",
    "era_of_ai_logo.jpg",
    "avatar_",
    "default_bg",
    "brand_",
}


def get_protected_files(db_path: Optional[Path] = None, recent_posts: int = 50) -> Set[str]:
    """
    Extract file basenames referenced by the most recent active posts
    in SQLite published_history.db to prevent breaking live permalinks or retries.
    """
    protected: Set[str] = set()
    db = db_path or DATABASE_PATH
    if not db.exists():
        return protected

    try:
        conn = sqlite3.connect(str(db))
        cursor = conn.cursor()
        query = """
            SELECT media_url, post_payload
            FROM posts
            ORDER BY id DESC
            LIMIT ?
        """
        rows = cursor.execute(query, (recent_posts,)).fetchall()
        for media_url, payload in rows:
            if media_url:
                basename = Path(media_url).name
                if basename:
                    protected.add(basename)
            if payload and isinstance(payload, str):
                # Search for video_path or staging references inside payload
                for token in payload.split('"'):
                    if "storage/staging/" in token or token.endswith((".mp4", ".png", ".mp3", ".jpg")):
                        bname = Path(token).name
                        if bname:
                            protected.add(bname)
        conn.close()
    except Exception as e:
        logger.warning("[StorageManager] Error querying protected files from DB: %s", e)

    return protected


def get_staging_metrics(staging_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Calculate telemetry metrics for storage/staging directory.
    Returns total files, disk usage in bytes/MB, and extension breakdown.
    """
    st_dir = staging_dir or STAGING_DIR
    if not st_dir.exists():
        return {
            "total_files": 0,
            "total_bytes": 0,
            "total_mb": 0.0,
            "extensions": {},
            "oldest_age_hours": 0.0,
        }

    now = time.time()
    total_bytes = 0
    ext_counts: Dict[str, int] = {}
    oldest_ts = now
    total_files = 0

    for f in st_dir.iterdir():
        if f.is_file():
            total_files += 1
            st = f.stat()
            total_bytes += st.st_size
            ext = f.suffix.lower() or "none"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            if st.st_mtime < oldest_ts:
                oldest_ts = st.st_mtime

    oldest_age_hours = round(max(0.0, (now - oldest_ts) / 3600.0), 1) if total_files > 0 else 0.0

    return {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "extensions": ext_counts,
        "oldest_age_hours": oldest_age_hours,
    }


def purge_staging_directory(
    staging_dir: Optional[Path] = None,
    db_path: Optional[Path] = None,
    max_age_hours: int = 48,
    dry_run: bool = False,
    recent_protected_posts: int = 50,
) -> Dict[str, Any]:
    """
    Purge staging files older than max_age_hours, strictly protecting:
    - Files referenced by the latest recent_protected_posts
    - Files matching PERMANENT_ASSET_PATTERNS or .gitkeep
    - Files modified within max_age_hours
    """
    st_dir = staging_dir or STAGING_DIR
    if not st_dir.exists():
        return {"status": "skipped", "reason": "staging_dir_missing", "deleted_files": 0, "freed_mb": 0.0}

    now = time.time()
    cutoff_ts = now - (max_age_hours * 3600.0)
    protected_basenames = get_protected_files(db_path, recent_posts=recent_protected_posts)

    deleted_count = 0
    deleted_bytes = 0
    retained_count = 0

    for f in st_dir.iterdir():
        if not f.is_file():
            continue

        filename = f.name
        # 1. Protect special patterns
        if any(pat in filename for pat in PERMANENT_ASSET_PATTERNS):
            retained_count += 1
            continue

        # 2. Protect files referenced in active DB posts
        if filename in protected_basenames:
            retained_count += 1
            continue

        # 3. Check timestamp
        try:
            st = f.stat()
            if st.st_mtime < cutoff_ts:
                file_size = st.st_size
                if not dry_run:
                    f.unlink()
                deleted_count += 1
                deleted_bytes += file_size
            else:
                retained_count += 1
        except Exception as e:
            logger.debug("[StorageManager] Could not inspect/unlink %s: %s", filename, e)
            retained_count += 1

    freed_mb = round(deleted_bytes / (1024 * 1024), 2)
    logger.info(
        "[StorageManager] Purge complete (dry_run=%s): %d deleted (%.2f MB freed), %d retained (cutoff: %dh)",
        dry_run, deleted_count, freed_mb, retained_count, max_age_hours
    )

    return {
        "status": "success",
        "dry_run": dry_run,
        "max_age_hours": max_age_hours,
        "deleted_count": deleted_count,
        "freed_mb": freed_mb,
        "retained_count": retained_count,
    }
