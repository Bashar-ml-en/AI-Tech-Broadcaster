"""
Unit tests for Automated Staging Storage & Cache Lifecycle Manager
"""

import time
import sqlite3
from pathlib import Path
from src.storage_manager import (
    get_protected_files,
    get_staging_metrics,
    purge_staging_directory,
)


def test_get_staging_metrics_empty(tmp_path):
    metrics = get_staging_metrics(tmp_path)
    assert metrics["total_files"] == 0
    assert metrics["total_bytes"] == 0
    assert metrics["total_mb"] == 0.0


def test_staging_purge_with_protected_and_aged_files(tmp_path):
    st_dir = tmp_path / "staging"
    st_dir.mkdir()
    db_file = tmp_path / "published_history.db"

    # Create dummy database
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "CREATE TABLE posts (id INTEGER PRIMARY KEY, media_url TEXT, post_payload TEXT)"
    )
    conn.execute(
        "INSERT INTO posts (id, media_url, post_payload) VALUES (1, 'https://cdn.example.com/protected_clip.mp4', '{\"video_path\": \"storage/staging/protected_clip.mp4\"}')"
    )
    conn.commit()
    conn.close()

    now = time.time()
    old_time = now - (72 * 3600)  # 3 days old

    # 1. Stale unreferenced file (should be deleted)
    stale_file = st_dir / "temp_raw_old.mp4"
    stale_file.write_bytes(b"0" * 1024)
    import os
    os.utime(str(stale_file), (old_time, old_time))

    # 2. Protected by database file (should be kept despite age)
    db_ref_file = st_dir / "protected_clip.mp4"
    db_ref_file.write_bytes(b"1" * 2048)
    os.utime(str(db_ref_file), (old_time, old_time))

    # 3. Fresh unreferenced file (should be kept due to age < 48h)
    fresh_file = st_dir / "fresh_clip.mp4"
    fresh_file.write_bytes(b"2" * 512)

    # 4. Permanent asset pattern
    perm_file = st_dir / "avatar_sundar.png"
    perm_file.write_bytes(b"3" * 256)
    os.utime(str(perm_file), (old_time, old_time))

    # Run dry-run
    dry_res = purge_staging_directory(
        staging_dir=st_dir,
        db_path=db_file,
        max_age_hours=48,
        dry_run=True,
    )
    assert dry_res["deleted_count"] == 1
    assert stale_file.exists()

    # Run actual purge
    real_res = purge_staging_directory(
        staging_dir=st_dir,
        db_path=db_file,
        max_age_hours=48,
        dry_run=False,
    )
    assert real_res["deleted_count"] == 1
    assert not stale_file.exists()
    assert db_ref_file.exists()
    assert fresh_file.exists()
    assert perm_file.exists()
