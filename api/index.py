"""
Vercel Serverless Entrypoint for AI Tech Broadcaster Executive Studio
Routes all incoming web traffic on Vercel directly to the FastAPI Application.
Handles serverless SQLite /tmp mounting and environment loading.
"""

import os
import sys
import shutil
import sqlite3
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

def should_seed_database(dest_path: Path) -> bool:
    if not dest_path.exists():
        return True
    try:
        conn = sqlite3.connect(str(dest_path))
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='posts'")
        if cur.fetchone()[0] == 0:
            conn.close()
            return True
        cur.execute("SELECT count(*) FROM posts")
        count = cur.fetchone()[0]
        conn.close()
        return count == 0
    except Exception:
        return True

# Configure Vercel ephemeral database and staging paths
if os.getenv("VERCEL"):
    os.environ["DATABASE_PATH"] = "/tmp/published_history.db"
    dest_db = Path("/tmp/published_history.db")
    
    if should_seed_database(dest_db):
        src_seed = root_dir / "storage" / "seed_history.db"
        src_db = root_dir / "storage" / "published_history.db"
        src = src_seed if src_seed.exists() else src_db
        if src.exists():
            try:
                dest_db.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest_db)
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
