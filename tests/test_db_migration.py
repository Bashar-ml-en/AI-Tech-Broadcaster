"""
Tests for idempotent database migration and schema integrity.
"""

import sqlite3
from src.webhook_server import init_db, DATABASE_PATH


def test_init_db_is_idempotent():
    # Calling init_db twice should be completely safe
    init_db()
    init_db()

    with sqlite3.connect(DATABASE_PATH) as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(posts)").fetchall()]
        required = [
            "publish_status",
            "publish_results_json",
            "publish_attempts",
            "last_error",
            "content_hash"
        ]
        for col in required:
            assert col in cols, f"Column {col} missing in posts schema"

        count = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        assert count >= 1, "Database rows should be preserved"
