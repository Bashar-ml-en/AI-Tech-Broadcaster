"""
Vercel Serverless Entrypoint for AI Tech Broadcaster Executive Studio
Routes all incoming web traffic on Vercel directly to the FastAPI Application.
Handles serverless SQLite /tmp mounting, Cloudflare R2 live state pulling, and environment loading.
"""

import os
import sys
import shutil
import sqlite3
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))


def get_row_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='posts'")
        if cur.fetchone()[0] == 0:
            conn.close()
            return 0
        cur.execute("SELECT count(*) FROM posts")
        count = cur.fetchone()[0]
        conn.close()
        return int(count)
    except Exception:
        return 0


# Configure Vercel ephemeral database and staging paths
if os.getenv("VERCEL"):
    os.environ["DATABASE_PATH"] = "/tmp/published_history.db"
    dest_db = Path("/tmp/published_history.db")
    dest_snap = Path("/tmp/platform_state_snapshot.json")

    # 1. Try pulling latest live database & platform state from Cloudflare R2 first
    try:
        from src.r2_storage import pull_state_from_cloud
        pull_state_from_cloud(dest_db, dest_snap)
    except Exception:
        pass

    # 2. If /tmp/published_history.db is missing or has fewer rows than repo seed_history.db, copy repo DB
    src_seed = root_dir / "storage" / "seed_history.db"
    src_db = root_dir / "storage" / "published_history.db"
    best_repo_db = src_db if get_row_count(src_db) >= get_row_count(src_seed) else src_seed
    if best_repo_db.exists() and get_row_count(dest_db) < get_row_count(best_repo_db):
        try:
            dest_db.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(best_repo_db, dest_db)
        except Exception:
            pass

    repo_snap = root_dir / "storage" / "platform_state_snapshot.json"
    if not dest_snap.exists() and repo_snap.exists():
        try:
            shutil.copy2(repo_snap, dest_snap)
        except Exception:
            pass

    tmp_staging = Path("/tmp/staging")
    tmp_staging.mkdir(parents=True, exist_ok=True)
    for media_dir in [root_dir / "public" / "media", root_dir / "storage" / "staging"]:
        if media_dir.exists():
            for f in media_dir.glob("*"):
                if f.is_file() and not (tmp_staging / f.name).exists():
                    try:
                        shutil.copy2(f, tmp_staging / f.name)
                    except Exception:
                        pass

from src.webhook_server import app

# Export ASGI application for Vercel
__all__ = ["app"]
