"""
AI Tech Broadcaster - Executive Management Studio & HITL Webhook Server
Provides:
1. Interactive Web Management Studio (Dashboard, Real-Time Controls, HITL Studio)
2. Live Post Review & Direct One-Click Approval/Discard Gate
3. Sidecar Daemon Management (Start/Stop 1-Hour Schedule)
4. Media Asset Streaming for Staged Videos & Graphics (/media/)
5. Telegram Webhook Callback Query Processing with HMAC-SHA256 Cryptographic Verification
6. Multi-Platform Ayrshare Social Dispatcher Integration
"""

import os
import sys
import hmac
import hashlib
import time
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Header, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

env_path = root_dir / "config" / ".env"
load_dotenv(dotenv_path=env_path)

LOGS_DIR = root_dir / "storage" / "logs"
STAGING_DIR = root_dir / "storage" / "staging"
DATABASE_PATH = root_dir / os.getenv("DATABASE_PATH", "storage/published_history.db")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
STAGING_DIR.mkdir(parents=True, exist_ok=True)

# Configure comprehensive logging to both file and stderr
log_file = LOGS_DIR / "broadcaster.log"
file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

stream_handler = logging.StreamHandler(sys.stderr)
stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

logger = logging.getLogger("studio_server")
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "default_secret_key_antigravity_2026")
AYRSHARE_API_KEY = os.getenv("AYRSHARE_API_KEY", "")
AYRSHARE_PROFILE_KEY = os.getenv("AYRSHARE_PROFILE_KEY", "")
SCHEDULE_INTERVAL_HOURS = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "1"))

# Global Sidecar Thread State
sidecar_running = False
sidecar_thread: Optional[threading.Thread] = None
last_scan_time: Optional[float] = None
last_scan_result: Optional[str] = None

app = FastAPI(title="AI Tech Broadcaster Executive Studio")

# Mount staging directory for media asset streaming (Reels, TikTok MP4s, Graphics)
app.mount("/media", StaticFiles(directory=str(STAGING_DIR)), name="media")


def get_db_connection() -> sqlite3.Connection:
    """Return a thread-safe connection to the history database."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Ensure posts schema is properly created."""
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_url TEXT UNIQUE NOT NULL,
                headline TEXT NOT NULL,
                format_type TEXT NOT NULL,
                media_url TEXT,
                approval_status TEXT NOT NULL DEFAULT 'pending',
                hook_narration TEXT,
                body_narration TEXT,
                call_to_action TEXT,
                visual_prompt TEXT,
                captions_json TEXT,
                post_payload TEXT,
                telegram_message_id INTEGER,
                verification_token TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                published_at DATETIME,
                ayrshare_post_id TEXT,
                notes TEXT
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_source_url ON posts(source_url);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(approval_status);")
        conn.commit()


init_db()


def generate_hmac_token(source_url: str, post_id: int) -> str:
    """Generate a tamper-proof HMAC verification token for HITL action links."""
    message = f"{source_url}:{post_id}".encode("utf-8")
    secret = TELEGRAM_WEBHOOK_SECRET.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:24]


def verify_hmac_token(source_url: str, post_id: int, provided_token: str) -> bool:
    """Verify cryptographic authenticity of callback query token."""
    expected = generate_hmac_token(source_url, post_id)
    return hmac.compare_digest(expected, provided_token)


def publish_to_ayrshare(post_record: Dict[str, Any]) -> Dict[str, Any]:
    """Publish approved assets to TikTok, Instagram Reels, Facebook Reels, Threads, and X via Ayrshare."""
    if not AYRSHARE_API_KEY or "AYRSHARE_API_KEY" in AYRSHARE_API_KEY:
        logger.warning("Ayrshare API key not set or placeholder. Simulating successful broadcast.")
        return {
            "status": "success",
            "simulated": True,
            "id": f"ayr_sim_{int(time.time())}",
            "postIds": {
                "tiktok": f"mock_tiktok_{int(time.time())}",
                "instagram": f"mock_ig_{int(time.time())}",
                "facebook": f"mock_fb_{int(time.time())}",
                "threads": f"mock_threads_{int(time.time())}",
                "twitter": f"mock_x_{int(time.time())}"
            }
        }

    captions = {}
    try:
        captions = json.loads(post_record.get("captions_json") or "{}")
    except Exception:
        pass

    short_caption = captions.get("short_form") or f"{post_record['headline']} #AI #TechNews #Innovation"
    microblog_caption = captions.get("microblog") or f"{post_record['headline']} - {post_record['source_url']}"

    payload = {
        "post": short_caption,
        "platforms": ["tiktok", "instagram", "facebook", "threads", "twitter"],
        "mediaUrls": [post_record["media_url"]] if post_record.get("media_url") else [],
        "is_aigc": True,
        "shortenLinks": True,
        "platformSpecific": {
            "twitter": microblog_caption,
            "threads": microblog_caption,
            "instagram": {"caption": short_caption},
            "tiktok": {"caption": short_caption}
        }
    }

    if AYRSHARE_PROFILE_KEY:
        payload["profileKey"] = AYRSHARE_PROFILE_KEY

    headers = {
        "Authorization": f"Bearer {AYRSHARE_API_KEY}",
        "Content-Type": "application/json"
    }

    with httpx.Client(timeout=45.0) as client:
        resp = client.post("https://app.ayrshare.com/api/post", json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("Ayrshare publication error (%s): %s", resp.status_code, resp.text)
            raise RuntimeError(f"Ayrshare API returned error {resp.status_code}: {resp.text}")
        return resp.json()


# ---------------------------------------------------------------------------
# Background Sidecar Worker Management
# ---------------------------------------------------------------------------

def sidecar_worker():
    """Background sidecar thread that triggers broadcast cycles every SCHEDULE_INTERVAL_HOURS."""
    global sidecar_running, last_scan_time, last_scan_result
    from src.pipeline import execute_broadcast_cycle

    logger.info("Background sidecar worker thread started. Interval: %s hour(s)", SCHEDULE_INTERVAL_HOURS)
    while sidecar_running:
        try:
            last_scan_time = time.time()
            logger.info("Executing scheduled broadcast cycle...")
            res = execute_broadcast_cycle()
            last_scan_result = "New Story Staged" if res else "No New Qualified Stories"
        except Exception as e:
            logger.exception("Scheduled broadcast cycle error: %s", e)
            last_scan_result = f"Error: {str(e)[:50]}"

        # Sleep in 5-second intervals to allow fast interruption
        interval_seconds = SCHEDULE_INTERVAL_HOURS * 3600
        for _ in range(int(interval_seconds / 5)):
            if not sidecar_running:
                break
            time.sleep(5)

    logger.info("Background sidecar worker thread stopped.")


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI Tech Broadcaster Executive Studio",
        "timestamp": time.time(),
        "sidecar_running": sidecar_running
    }


@app.get("/api/status")
def get_system_status():
    """Return live system KPIs, worker state, and configuration status."""
    with get_db_connection() as conn:
        counts = {}
        for status in ["pending", "published", "discarded"]:
            row = conn.execute("SELECT COUNT(*) as count FROM posts WHERE approval_status = ?", (status,)).fetchone()
            counts[status] = row["count"] if row else 0
        total_row = conn.execute("SELECT COUNT(*) as count FROM posts").fetchone()
        counts["total"] = total_row["count"] if total_row else 0

    gemini_ready = bool(os.getenv("GEMINI_API_KEY") and "YOUR_GEMINI" not in os.getenv("GEMINI_API_KEY", ""))
    telegram_ready = bool(os.getenv("TELEGRAM_BOT_TOKEN") and "Example" not in os.getenv("TELEGRAM_BOT_TOKEN", ""))
    ayrshare_ready = bool(os.getenv("AYRSHARE_API_KEY") and "AYRSHARE" not in os.getenv("AYRSHARE_API_KEY", ""))
    r2_ready = bool(os.getenv("CLOUDFLARE_R2_ACCOUNT_ID") and "your_" not in os.getenv("CLOUDFLARE_R2_ACCOUNT_ID", ""))

    return {
        "metrics": counts,
        "sidecar": {
            "running": sidecar_running,
            "interval_hours": SCHEDULE_INTERVAL_HOURS,
            "last_scan_time": last_scan_time,
            "last_scan_result": last_scan_result
        },
        "integrations": {
            "gemini_director": "live" if gemini_ready else "simulated",
            "telegram_gate": "live" if telegram_ready else "local_web",
            "ayrshare_publisher": "live" if ayrshare_ready else "simulated",
            "cloudflare_r2": "live" if r2_ready else "local_staging"
        }
    }


@app.get("/api/posts")
def get_posts(status: Optional[str] = Query(None)):
    """Retrieve posts with optional status filter."""
    with get_db_connection() as conn:
        if status and status != "all":
            rows = conn.execute("SELECT * FROM posts WHERE approval_status = ? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


@app.post("/api/scan")
def trigger_scan(background_tasks: BackgroundTasks):
    """Trigger an immediate broadcast scan cycle in background."""
    global last_scan_time, last_scan_result
    from src.pipeline import execute_broadcast_cycle

    def run_cycle():
        global last_scan_time, last_scan_result
        last_scan_time = time.time()
        try:
            res = execute_broadcast_cycle()
            last_scan_result = "New Story Staged" if res else "No New Qualified Stories"
        except Exception as e:
            logger.exception("Manual scan error: %s", e)
            last_scan_result = f"Error: {str(e)[:50]}"

    background_tasks.add_task(run_cycle)
    return {"status": "scan_started", "message": "Broadcast cycle launched in background"}


@app.post("/api/sidecar/toggle")
def toggle_sidecar():
    """Start or stop the background hourly sidecar loop."""
    global sidecar_running, sidecar_thread
    if sidecar_running:
        sidecar_running = False
        return {"status": "stopped", "message": "Hourly sidecar stopped"}
    else:
        sidecar_running = True
        sidecar_thread = threading.Thread(target=sidecar_worker, daemon=True)
        sidecar_thread.start()
        return {"status": "started", "message": f"Hourly sidecar started (Interval: {SCHEDULE_INTERVAL_HOURS}h)"}


@app.post("/api/posts/{post_id}/approve")
def api_approve_post(post_id: int):
    """Approve a post and publish to all platforms."""
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")
        post = dict(row)

        if post["approval_status"] not in ("pending", "approved"):
            raise HTTPException(status_code=400, detail=f"Post status is already '{post['approval_status']}'")

        try:
            pub_res = publish_to_ayrshare(post)
            ayr_id = pub_res.get("id", str(int(time.time())))
            conn.execute(
                "UPDATE posts SET approval_status = 'published', published_at = CURRENT_TIMESTAMP, ayrshare_post_id = ? WHERE id = ?",
                (ayr_id, post_id)
            )
            conn.commit()
            logger.info("Post %s approved and published successfully.", post_id)
            return {"status": "published", "post_id": post_id, "ayrshare_id": ayr_id, "details": pub_res}
        except Exception as e:
            logger.exception("Failed to publish post %s: %s", post_id, e)
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/posts/{post_id}/discard")
def api_discard_post(post_id: int, reason: str = "Discarded via Executive Studio"):
    """Mark a pending post as discarded."""
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Post not found")

        conn.execute(
            "UPDATE posts SET approval_status = 'discarded', notes = ? WHERE id = ?",
            (reason, post_id)
        )
        conn.commit()
        logger.info("Post %s marked as discarded.", post_id)
        return {"status": "discarded", "post_id": post_id}


@app.get("/api/logs")
def get_logs(lines: int = 50):
    """Retrieve recent log lines."""
    if not log_file.exists():
        return {"logs": ["No logs recorded yet."]}
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return {"logs": all_lines[-lines:]}
    except Exception as e:
        return {"logs": [f"Error reading logs: {e}"]}


# ---------------------------------------------------------------------------
# Telegram Webhook & Legacy Review Endpoints
# ---------------------------------------------------------------------------

@app.post("/telegram-webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None)
):
    body = await request.json()
    callback_query = body.get("callback_query")
    if not callback_query:
        return {"status": "ignored"}

    query_id = callback_query.get("id")
    data = callback_query.get("data", "")
    from_user = callback_query.get("from", {}).get("username", "Unknown")

    parts = data.split(":")
    if len(parts) != 3:
        return {"status": "invalid_format"}

    action, token, post_id_str = parts[0], parts[1], parts[2]
    try:
        post_id = int(post_id_str)
    except ValueError:
        return {"status": "invalid_id"}

    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            return {"status": "not_found"}
        post_record = dict(row)

        if not verify_hmac_token(post_record["source_url"], post_id, token):
            return {"status": "unauthorized"}

        if post_record["approval_status"] != "pending":
            return {"status": f"already_{post_record['approval_status']}"}

        if action == "approve":
            pub_res = publish_to_ayrshare(post_record)
            ayr_id = pub_res.get("id", str(int(time.time())))
            conn.execute(
                "UPDATE posts SET approval_status = 'published', published_at = CURRENT_TIMESTAMP, ayrshare_post_id = ? WHERE id = ?",
                (ayr_id, post_id)
            )
            conn.commit()
            return {"status": "published", "post_id": post_id}
        elif action == "discard":
            conn.execute("UPDATE posts SET approval_status = 'discarded', notes = 'Discarded in Telegram' WHERE id = ?", (post_id,))
            conn.commit()
            return {"status": "discarded", "post_id": post_id}

    return {"status": "ok"}


@app.get("/review/{post_id}", response_class=HTMLResponse)
def review_redirect(post_id: int):
    """Redirect single post review directly into the Executive Studio focused view."""
    return HTMLResponse(content=f"<script>window.location.href='/?focus={post_id}';</script>")


# ---------------------------------------------------------------------------
# Executive Management Studio UI (Single-Page App)
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def executive_studio_dashboard():
    """
    Renders the modern Executive Management Studio Dashboard.
    Provides complete control over the AI Tech Broadcaster.
    """
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Tech Broadcaster — Executive Management Studio</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        body { font-family: 'Plus Jakarta Sans', sans-serif; background: #090d16; color: #f1f5f9; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        .glow-cyan { box-shadow: 0 0 20px rgba(6, 182, 212, 0.25); }
        .glow-emerald { box-shadow: 0 0 20px rgba(16, 185, 129, 0.25); }
        .custom-scroll::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scroll::-webkit-scrollbar-track { background: #0f172a; }
        .custom-scroll::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    </style>
</head>
<body class="min-h-screen flex flex-col">

    <!-- Top Navigation Header -->
    <header class="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div class="flex items-center space-x-4">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-cyan-500/30">
                <i class="fa-solid fa-broadcast-tower"></i>
            </div>
            <div>
                <h1 class="font-extrabold text-lg tracking-tight text-white flex items-center gap-2">
                    AI Tech Broadcaster <span class="text-xs font-mono font-medium px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">Antigravity 2.0 Studio</span>
                </h1>
                <p class="text-xs text-slate-400">Autonomous Broadcast Engine & Human-in-the-Loop Management</p>
            </div>
        </div>

        <div class="flex items-center space-x-3">
            <!-- Scan Trigger Button -->
            <button onclick="triggerScan()" id="btnScan" class="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold text-sm flex items-center gap-2 transition shadow-md hover:shadow-cyan-500/20 active:scale-95">
                <i class="fa-solid fa-bolt"></i> Scan & Direct Now
            </button>

            <!-- Hourly Sidecar Toggle Button -->
            <button onclick="toggleSidecar()" id="btnSidecar" class="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-sm border border-slate-700 flex items-center gap-2 transition active:scale-95">
                <i class="fa-solid fa-clock"></i> <span id="sidecarText">Sidecar: Idle</span>
            </button>
        </div>
    </header>

    <!-- Main Studio Body -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">

        <!-- KPI Metric Cards -->
        <div class="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition">
                <div class="flex justify-between items-start text-slate-400 text-xs font-semibold uppercase tracking-wider">
                    <span>Pending HITL</span>
                    <i class="fa-solid fa-hourglass-half text-amber-400"></i>
                </div>
                <div id="statPending" class="text-3xl font-extrabold text-amber-400 mt-2">0</div>
                <div class="text-xs text-slate-500 mt-1">Requires your authorization</div>
            </div>

            <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition">
                <div class="flex justify-between items-start text-slate-400 text-xs font-semibold uppercase tracking-wider">
                    <span>Published</span>
                    <i class="fa-solid fa-circle-check text-emerald-400"></i>
                </div>
                <div id="statPublished" class="text-3xl font-extrabold text-emerald-400 mt-2">0</div>
                <div class="text-xs text-slate-500 mt-1">Live on 5 social networks</div>
            </div>

            <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition">
                <div class="flex justify-between items-start text-slate-400 text-xs font-semibold uppercase tracking-wider">
                    <span>Discarded</span>
                    <i class="fa-solid fa-ban text-rose-400"></i>
                </div>
                <div id="statDiscarded" class="text-3xl font-extrabold text-rose-400 mt-2">0</div>
                <div class="text-xs text-slate-500 mt-1">Filtered or rejected</div>
            </div>

            <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition">
                <div class="flex justify-between items-start text-slate-400 text-xs font-semibold uppercase tracking-wider">
                    <span>Total Evaluated</span>
                    <i class="fa-solid fa-database text-cyan-400"></i>
                </div>
                <div id="statTotal" class="text-3xl font-extrabold text-cyan-400 mt-2">0</div>
                <div class="text-xs text-slate-500 mt-1">Deterministic deduplicated</div>
            </div>

            <div class="p-4 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 transition">
                <div class="flex justify-between items-start text-slate-400 text-xs font-semibold uppercase tracking-wider">
                    <span>Broadcast Cadence</span>
                    <i class="fa-solid fa-stopwatch text-purple-400"></i>
                </div>
                <div class="text-2xl font-extrabold text-purple-400 mt-2">Every 1 Hour</div>
                <div id="statNextScan" class="text-xs text-slate-500 mt-1">Autonomous sidecar ready</div>
            </div>
        </div>

        <!-- Integration Status Bar -->
        <div class="p-4 rounded-xl bg-slate-900/40 border border-slate-800 flex flex-wrap items-center justify-between gap-4 text-xs">
            <div class="flex items-center gap-6">
                <span class="text-slate-400 font-semibold uppercase tracking-wider">Services:</span>
                <div class="flex items-center gap-2">
                    <span id="badgeGemini" class="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse"></span>
                    <span class="text-slate-300">Gemini 2.0 Flash Director</span>
                </div>
                <div class="flex items-center gap-2">
                    <span id="badgeTelegram" class="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
                    <span class="text-slate-300">Telegram HITL Gate</span>
                </div>
                <div class="flex items-center gap-2">
                    <span id="badgeAyrshare" class="w-2.5 h-2.5 rounded-full bg-blue-400"></span>
                    <span class="text-slate-300">Ayrshare Multi-Poster (TikTok/IG/FB/X/Threads)</span>
                </div>
                <div class="flex items-center gap-2">
                    <span id="badgeR2" class="w-2.5 h-2.5 rounded-full bg-orange-400"></span>
                    <span class="text-slate-300">Cloudflare R2 Staging CDN</span>
                </div>
            </div>
            <div id="liveAlert" class="text-cyan-400 font-mono text-xs hidden">
                <i class="fa-solid fa-spinner fa-spin"></i> Processing...
            </div>
        </div>

        <!-- Filter Tabs -->
        <div class="flex items-center justify-between border-b border-slate-800 pb-3">
            <div class="flex items-center space-x-2">
                <button onclick="setFilter('pending')" id="tabPending" class="px-4 py-2 rounded-lg text-sm font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                    <i class="fa-solid fa-bell"></i> Pending Review (<span id="countPendingTab">0</span>)
                </button>
                <button onclick="setFilter('published')" id="tabPublished" class="px-4 py-2 rounded-lg text-sm font-semibold text-slate-400 hover:text-slate-200">
                    <i class="fa-solid fa-check-double"></i> Published
                </button>
                <button onclick="setFilter('discarded')" id="tabDiscarded" class="px-4 py-2 rounded-lg text-sm font-semibold text-slate-400 hover:text-slate-200">
                    <i class="fa-solid fa-trash"></i> Discarded
                </button>
                <button onclick="setFilter('all')" id="tabAll" class="px-4 py-2 rounded-lg text-sm font-semibold text-slate-400 hover:text-slate-200">
                    All History
                </button>
            </div>
            <button onclick="loadPosts()" class="text-slate-400 hover:text-slate-200 text-xs flex items-center gap-1.5 transition">
                <i class="fa-solid fa-arrows-rotate"></i> Refresh
            </button>
        </div>

        <!-- Main Cards Feed Area -->
        <div id="postsContainer" class="space-y-6">
            <!-- Dynamic Post Cards will render here -->
        </div>

        <!-- Terminal Logs Drawer (Collapsible) -->
        <div class="rounded-xl border border-slate-800 bg-slate-950 overflow-hidden">
            <div class="px-4 py-3 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs font-semibold text-slate-300">
                    <i class="fa-solid fa-terminal text-cyan-400"></i> Live Broadcaster Activity Logs
                </div>
                <button onclick="loadLogs()" class="text-xs text-slate-400 hover:text-cyan-400 transition">
                    <i class="fa-solid fa-arrows-rotate"></i> Refresh Logs
                </button>
            </div>
            <div id="logsOutput" class="p-4 font-mono text-xs text-slate-300 h-44 overflow-y-auto custom-scroll space-y-1 bg-black/40">
                Loading logs...
            </div>
        </div>

    </main>

    <footer class="border-t border-slate-800 py-4 px-6 text-center text-xs text-slate-500">
        AI Tech Broadcaster • Antigravity 2.0 Scheduled Sidecar • Gemini 2.0 Flash Director & Veo 3.1 Media
    </footer>

    <!-- JavaScript Controller -->
    <script>
        let currentFilter = 'pending';

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('statPending').innerText = data.metrics.pending;
                document.getElementById('statPublished').innerText = data.metrics.published;
                document.getElementById('statDiscarded').innerText = data.metrics.discarded;
                document.getElementById('statTotal').innerText = data.metrics.total;
                document.getElementById('countPendingTab').innerText = data.metrics.pending;

                const sidecarBtn = document.getElementById('btnSidecar');
                const sidecarText = document.getElementById('sidecarText');
                if (data.sidecar.running) {
                    sidecarBtn.className = "px-4 py-2 rounded-lg bg-emerald-600/20 text-emerald-400 border border-emerald-500/40 font-semibold text-sm flex items-center gap-2 transition";
                    sidecarText.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block"></span> Sidecar: Active (1h)';
                } else {
                    sidecarBtn.className = "px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-sm border border-slate-700 flex items-center gap-2 transition";
                    sidecarText.innerText = "Sidecar: Idle";
                }
            } catch (err) {
                console.error("Error loading status:", err);
            }
        }

        async function loadPosts() {
            const container = document.getElementById('postsContainer');
            container.innerHTML = '<div class="text-center py-12 text-slate-500"><i class="fa-solid fa-spinner fa-spin text-2xl"></i><p class="mt-2 text-sm">Loading broadcasts...</p></div>';

            try {
                const res = await fetch(`/api/posts?status=${currentFilter}`);
                const posts = await res.json();

                if (posts.length === 0) {
                    container.innerHTML = `
                        <div class="text-center py-16 bg-slate-900/30 rounded-2xl border border-slate-800/80">
                            <i class="fa-solid fa-inbox text-4xl text-slate-600"></i>
                            <h3 class="text-base font-bold text-slate-300 mt-3">No ${currentFilter} broadcasts</h3>
                            <p class="text-xs text-slate-500 mt-1 max-w-sm mx-auto">Click "Scan & Direct Now" above to scrape Tier 1/2/3 feeds and direct a new broadcast story.</p>
                        </div>
                    `;
                    return;
                }

                container.innerHTML = posts.map(post => {
                    let captions = { short_form: '', microblog: '' };
                    try { captions = JSON.parse(post.captions_json || '{}'); } catch(e) {}

                    const isPending = post.approval_status === 'pending';
                    const isPublished = post.approval_status === 'published';
                    const isVideo = post.format_type === 'video';

                    const statusBadge = isPending 
                        ? '<span class="px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/40"><i class="fa-solid fa-clock"></i> Pending Review</span>'
                        : isPublished
                        ? '<span class="px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"><i class="fa-solid fa-check"></i> Published Globally</span>'
                        : '<span class="px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-rose-500/20 text-rose-300 border border-rose-500/40"><i class="fa-solid fa-ban"></i> Discarded</span>';

                    const formatBadge = isVideo
                        ? '<span class="px-2.5 py-1 rounded-md text-xs font-bold bg-blue-500/20 text-blue-300 border border-blue-500/40"><i class="fa-solid fa-video"></i> Veo 3.1 Fast (9:16 Reels/TikTok)</span>'
                        : '<span class="px-2.5 py-1 rounded-md text-xs font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40"><i class="fa-solid fa-image"></i> Imagen 3.0 (1:1 Schematic)</span>';

                    // Parse local preview URL if file is in staging
                    let mediaPreviewHtml = '';
                    if (post.media_url) {
                        const filename = post.media_url.split('/').pop();
                        const localStreamUrl = `/media/${filename}`;
                        if (isVideo) {
                            mediaPreviewHtml = `
                                <div class="bg-black/60 rounded-xl p-3 border border-slate-800 text-center">
                                    <div class="aspect-[9/16] max-h-80 mx-auto bg-slate-950 rounded-lg flex items-center justify-center border border-slate-800 text-slate-500 relative overflow-hidden">
                                        <video src="${localStreamUrl}" controls class="w-full h-full object-cover rounded-lg" poster=""></video>
                                    </div>
                                    <div class="mt-2 text-xs font-mono text-cyan-400 truncate">
                                        <a href="${post.media_url}" target="_blank" class="hover:underline"><i class="fa-solid fa-link"></i> CDN Asset Link</a>
                                    </div>
                                </div>
                            `;
                        } else {
                            mediaPreviewHtml = `
                                <div class="bg-black/60 rounded-xl p-3 border border-slate-800 text-center">
                                    <div class="aspect-square max-h-64 mx-auto bg-slate-950 rounded-lg flex items-center justify-center border border-slate-800 overflow-hidden">
                                        <img src="${localStreamUrl}" alt="Graphic" class="w-full h-full object-contain">
                                    </div>
                                    <div class="mt-2 text-xs font-mono text-cyan-400 truncate">
                                        <a href="${post.media_url}" target="_blank" class="hover:underline"><i class="fa-solid fa-link"></i> CDN Asset Link</a>
                                    </div>
                                </div>
                            `;
                        }
                    }

                    return `
                        <div class="rounded-2xl border ${isPending ? 'border-amber-500/40 glow-cyan' : 'border-slate-800'} bg-slate-900/80 p-6 space-y-5 transition">
                            <!-- Card Header -->
                            <div class="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-4">
                                <div class="flex items-center gap-3">
                                    <span class="text-xs font-mono font-bold text-slate-500">ID #${post.id}</span>
                                    ${formatBadge}
                                    ${statusBadge}
                                </div>
                                <div class="text-xs text-slate-400 font-mono">
                                    <i class="fa-regular fa-calendar"></i> ${post.created_at || 'Just now'}
                                </div>
                            </div>

                            <!-- Title & Source -->
                            <div>
                                <h2 class="text-xl font-extrabold text-white tracking-tight">${post.headline}</h2>
                                <a href="${post.source_url}" target="_blank" class="text-xs font-mono text-cyan-400 hover:text-cyan-300 mt-1 inline-flex items-center gap-1.5 break-all">
                                    <i class="fa-solid fa-arrow-up-right-from-square"></i> Primary Source: ${post.source_url}
                                </a>
                            </div>

                            <!-- Grid Content: Media Preview & Script Breakdown -->
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <!-- Left Column: Media Preview -->
                                <div class="md:col-span-1">
                                    <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Rendered Asset</h4>
                                    ${mediaPreviewHtml || '<div class="p-6 bg-slate-950 rounded-xl text-center text-xs text-slate-500">No media preview</div>'}
                                </div>

                                <!-- Right Column: 4-Block Narration Architecture -->
                                <div class="md:col-span-2 space-y-4">
                                    <div>
                                        <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Retention Narration Architecture (30–45s)</h4>
                                        <div class="space-y-2 text-sm bg-slate-950/70 p-4 rounded-xl border border-slate-800/80">
                                            <div class="border-l-2 border-cyan-400 pl-3">
                                                <span class="text-xs font-bold text-cyan-400 uppercase">Block 1: Disruption Hook (0–3s)</span>
                                                <p class="text-slate-200 mt-0.5">"${post.hook_narration || 'N/A'}"</p>
                                            </div>
                                            <div class="border-l-2 border-blue-400 pl-3">
                                                <span class="text-xs font-bold text-blue-400 uppercase">Block 2 & 3: Core Event & Utility (4–30s)</span>
                                                <p class="text-slate-200 mt-0.5">${post.body_narration || 'N/A'}</p>
                                            </div>
                                            <div class="border-l-2 border-amber-400 pl-3">
                                                <span class="text-xs font-bold text-amber-400 uppercase">Block 4: Debate CTA (Final 5s)</span>
                                                <p class="text-slate-200 mt-0.5 font-medium">"${post.call_to_action || 'N/A'}"</p>
                                            </div>
                                        </div>
                                    </div>

                                    <!-- Platform Captions -->
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                                        <div class="bg-slate-950/50 p-3 rounded-lg border border-slate-800">
                                            <div class="flex justify-between items-center text-slate-400 font-bold mb-1">
                                                <span><i class="fa-brands fa-tiktok"></i> TikTok & Reels Caption</span>
                                                <button onclick="navigator.clipboard.writeText('${escapeQuotes(captions.short_form)}')" class="hover:text-cyan-400"><i class="fa-regular fa-copy"></i></button>
                                            </div>
                                            <p class="text-slate-300 line-clamp-3">${captions.short_form || 'N/A'}</p>
                                        </div>

                                        <div class="bg-slate-950/50 p-3 rounded-lg border border-slate-800">
                                            <div class="flex justify-between items-center text-slate-400 font-bold mb-1">
                                                <span><i class="fa-brands fa-x-twitter"></i> X & Threads Microblog</span>
                                                <button onclick="navigator.clipboard.writeText('${escapeQuotes(captions.microblog)}')" class="hover:text-cyan-400"><i class="fa-regular fa-copy"></i></button>
                                            </div>
                                            <p class="text-slate-300 line-clamp-3">${captions.microblog || 'N/A'}</p>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <!-- Actions Footer (HITL Authorization Gate) -->
                            ${isPending ? `
                                <div class="border-t border-slate-800 pt-4 flex items-center justify-end space-x-3">
                                    <button onclick="discardPost(${post.id})" class="px-5 py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-bold text-sm border border-rose-500/30 transition active:scale-95 flex items-center gap-2">
                                        <i class="fa-solid fa-xmark"></i> Discard Story
                                    </button>
                                    <button onclick="approvePost(${post.id})" class="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-sm transition shadow-lg shadow-emerald-500/20 active:scale-95 flex items-center gap-2">
                                        <i class="fa-solid fa-check-circle"></i> Approve & Publish Globally
                                    </button>
                                </div>
                            ` : isPublished ? `
                                <div class="border-t border-slate-800 pt-4 flex items-center justify-between text-xs text-slate-400">
                                    <span><i class="fa-solid fa-circle-check text-emerald-400"></i> Dispatched to TikTok, Instagram Reels, Facebook Reels, Threads & X</span>
                                    <span class="font-mono text-cyan-400">Ayrshare ID: ${post.ayrshare_post_id || 'Active'}</span>
                                </div>
                            ` : `
                                <div class="border-t border-slate-800 pt-4 text-xs text-slate-500 italic">
                                    Marked as discarded. Cleanly terminated.
                                </div>
                            `}
                        </div>
                    `;
                }).join('');

            } catch (err) {
                container.innerHTML = `<div class="p-6 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-300 text-sm">Error loading broadcasts: ${err.message}</div>`;
            }
        }

        function escapeQuotes(str) {
            if (!str) return '';
            return str.replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\\n/g, ' ');
        }

        async function triggerScan() {
            const alert = document.getElementById('liveAlert');
            const btn = document.getElementById('btnScan');
            alert.classList.remove('hidden');
            btn.disabled = true;
            btn.classList.add('opacity-50');

            try {
                await fetch('/api/scan', { method: 'POST' });
                alert.innerText = '⚡ Scan running across Tier 1, 2, 3 AI feeds...';
                setTimeout(() => {
                    fetchStatus();
                    loadPosts();
                    loadLogs();
                    alert.classList.add('hidden');
                    btn.disabled = false;
                    btn.classList.remove('opacity-50');
                }, 4000);
            } catch (err) {
                alert.innerText = 'Scan launch error';
                btn.disabled = false;
                btn.classList.remove('opacity-50');
            }
        }

        async function toggleSidecar() {
            try {
                const res = await fetch('/api/sidecar/toggle', { method: 'POST' });
                const data = await res.json();
                fetchStatus();
            } catch (err) {
                console.error("Error toggling sidecar:", err);
            }
        }

        async function approvePost(id) {
            if (!confirm(`Are you sure you want to approve and publish Broadcast #${id} globally to TikTok, Instagram, Facebook, Threads, and X?`)) return;

            try {
                const res = await fetch(`/api/posts/${id}/approve`, { method: 'POST' });
                const data = await res.json();
                if (res.ok) {
                    alert('✅ Post successfully approved and published globally!');
                    fetchStatus();
                    loadPosts();
                    loadLogs();
                } else {
                    alert('Error publishing post: ' + data.detail);
                }
            } catch (err) {
                alert('Publish request error: ' + err.message);
            }
        }

        async function discardPost(id) {
            if (!confirm(`Discard Broadcast #${id}? It will be removed from review.`)) return;

            try {
                const res = await fetch(`/api/posts/${id}/discard`, { method: 'POST' });
                if (res.ok) {
                    fetchStatus();
                    loadPosts();
                    loadLogs();
                }
            } catch (err) {
                alert('Discard error: ' + err.message);
            }
        }

        function setFilter(status) {
            currentFilter = status;
            ['pending', 'published', 'discarded', 'all'].forEach(tab => {
                const el = document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1));
                if (tab === status) {
                    el.className = "px-4 py-2 rounded-lg text-sm font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40";
                } else {
                    el.className = "px-4 py-2 rounded-lg text-sm font-semibold text-slate-400 hover:text-slate-200";
                }
            });
            loadPosts();
        }

        async function loadLogs() {
            try {
                const res = await fetch('/api/logs?lines=30');
                const data = await res.json();
                const logBox = document.getElementById('logsOutput');
                logBox.innerHTML = data.logs.map(l => `<div>${l}</div>`).join('');
                logBox.scrollTop = logBox.scrollHeight;
            } catch (err) {
                console.error("Error fetching logs:", err);
            }
        }

        // Initialize dashboard
        fetchStatus();
        loadPosts();
        loadLogs();
        setInterval(fetchStatus, 10000);
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("WEBHOOK_PORT", 8080))
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    print(f"==================================================================")
    print(f"  AI TECH BROADCASTER — EXECUTIVE MANAGEMENT STUDIO")
    print(f"  Access Dashboard at: http://localhost:{port}/")
    print(f"==================================================================")
    uvicorn.run(app, host=host, port=port)
