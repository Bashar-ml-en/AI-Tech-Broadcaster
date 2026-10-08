"""
AI Tech Broadcaster - Command-Line Management Utility
Usage:
    python manage.py studio        # Start Executive Management Web Studio & open browser
    python manage.py scan          # Trigger an immediate broadcast scan cycle
    python manage.py status        # Display database records, pending stories, and service health
    python manage.py sidecar       # Run continuous 1-hour scheduled sidecar loop
    python manage.py review        # Terminal-based interactive HITL review queue
"""

import os
import sys
import json
import time
import sqlite3
import argparse
import webbrowser
from pathlib import Path
from typing import Optional

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from src.webhook_server import get_db_connection, init_db, publish_to_ayrshare, DATABASE_PATH
from src.pipeline import execute_broadcast_cycle, run_scheduled_sidecar


def cmd_status():
    """Print system status, database KPIs, and integration states."""
    init_db()
    with get_db_connection() as conn:
        pub_counts = {}
        for s in ["published", "partial", "simulated", "rendered", "blocked", "failed"]:
            row = conn.execute("SELECT COUNT(*) as c FROM posts WHERE publish_status = ?", (s,)).fetchone()
            pub_counts[s] = row["c"]
        total = conn.execute("SELECT COUNT(*) as c FROM posts").fetchone()["c"]

    publish_mode = os.getenv("PUBLISH_MODE", "simulate").upper()
    meta_ok = bool(os.getenv("META_PAGE_ACCESS_TOKEN") and len(os.getenv("META_PAGE_ACCESS_TOKEN", "")) > 20)
    threads_ok = bool(os.getenv("THREADS_ACCESS_TOKEN") and len(os.getenv("THREADS_ACCESS_TOKEN", "")) > 10)
    tiktok_ok = bool(os.getenv("TIKTOK_ACCESS_TOKEN") and len(os.getenv("TIKTOK_ACCESS_TOKEN", "")) > 10)
    r2_ok = bool(os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID") and len(os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID", "")) > 10)
    gemini_ok = bool(os.getenv("GEMINI_API_KEY") and "YOUR_GEMINI" not in os.getenv("GEMINI_API_KEY", ""))

    print("\n" + "=" * 65)
    print("  AI TECH BROADCASTER — AUTONOMOUS SYSTEM STATUS & METRICS")
    print("=" * 65)
    print(f"  - Database:             {DATABASE_PATH}")
    print(f"  - Total Candidates:     {total}")
    print(f"  - Published (Live):     {pub_counts.get('published', 0)}")
    print(f"  - Partial Published:    {pub_counts.get('partial', 0)}")
    print(f"  - Simulated Broadcasts: {pub_counts.get('simulated', 0)}")
    print(f"  - Rendered (Ready):     {pub_counts.get('rendered', 0)}")
    print(f"  - Blocked by Gate:      {pub_counts.get('blocked', 0)}")
    print(f"  - Failed / Retrying:    {pub_counts.get('failed', 0)}")
    print("-" * 65)
    print(f"  * Runtime Mode:         [{publish_mode}]")
    print(f"  * Director (Gemini):    {'[LIVE API]' if gemini_ok else '[HEURISTIC CURATOR]'}")
    print(f"  * Meta (FB & IG):       {'[CONFIGURED (LIVE)]' if meta_ok else '[SIMULATED AUTONOMOUS]'}")
    print(f"  * Threads API:          {'[CONFIGURED (LIVE)]' if threads_ok else '[SIMULATED AUTONOMOUS]'}")
    print(f"  * TikTok Posting v2:    {'[CONFIGURED (LIVE)]' if tiktok_ok else '[SIMULATED AUTONOMOUS]'}")
    print(f"  * Cloudflare R2 CDN:    {'[CONFIGURED (LIVE)]' if r2_ok else '[LOCAL STAGING]'}")
    print("=" * 65 + "\n")


def cmd_scan(target_format: str = "all", force: bool = False):
    """Run an immediate broadcast cycle."""
    init_db()
    if force:
        lock_path = root_dir / "storage" / ".cycle.lock"
        if lock_path.exists():
            try:
                lock_path.unlink()
                print("⚡ Force-cleared cycle lock file.")
            except Exception:
                pass

    print(f"\n[Broadcaster] Launching immediate broadcast cycle (format: {target_format})...")
    res = execute_broadcast_cycle(target_format=target_format)
    if res:
        if res.get("status") == "locked":
            print("\n⚠️ Broadcast cycle already running in background (cycle locked).")
            print("💡 The background sidecar daemon is actively synthesizing and dispatching content right now.")
            print("   Please wait 30-60 seconds for the active cycle to complete, or run:")
            print("   'python manage.py watch' to monitor in real-time, or 'python manage.py feed' to view results.\n")
            return
        print("\n✅ Broadcast cycle completed successfully!")
        if "dispatch_result" in res:
            d = res["dispatch_result"]
            print(f"Post #{d.get('post_id')} Dispatch Outcome: {str(d.get('overall')).upper()}")
            for r in d.get("results", []):
                print(f"  * {r.get('platform', '').capitalize()}: {r.get('status')} ({r.get('mode')}) - ID: {r.get('remote_id') or r.get('error_code')}")
        elif "dispatch_results" in res:
            for d in res["dispatch_results"]:
                print(f"Post #{d.get('post_id')} Dispatch Outcome: {str(d.get('overall')).upper()}")
                for r in d.get("results", []):
                    print(f"  * {r.get('platform', '').capitalize()}: {r.get('status')} ({r.get('mode')}) - ID: {r.get('remote_id') or r.get('error_code')}")
    else:
        print("\nℹ️ No new qualified stories in this cycle.")


def cmd_doctor():
    """Run comprehensive system health, dependency, and platform configuration diagnostics."""
    print("\n" + "=" * 65)
    print("  AI TECH BROADCASTER — DIAGNOSTIC HEALTH CHECK (DOCTOR)")
    print("=" * 65)

    all_passed = True

    # 1. Python Version Check
    py_ver = sys.version_info
    if py_ver >= (3, 10):
        print(f"  [PASS] Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro}")
    else:
        print(f"  [FAIL] Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro} (Requires >= 3.10)")
        all_passed = False

    # 2. Dependency Imports
    deps = [
        ("httpx", "HTTP Client"),
        ("fastapi", "API Server"),
        ("PIL", "Pillow Imaging"),
        ("edge_tts", "Neural Audio Engine"),
        ("bs4", "BeautifulSoup4 Scraper"),
        ("dotenv", "Dotenv Config"),
        ("imageio_ffmpeg", "FFmpeg Binary Binding"),
    ]
    for mod, label in deps:
        try:
            __import__(mod)
            print(f"  [PASS] Dependency: {label} ({mod})")
        except ImportError:
            print(f"  [FAIL] Dependency: {label} ({mod}) is missing")
            all_passed = False

    # 3. Environment & Configuration Diagnostics
    pub_mode = os.getenv("PUBLISH_MODE", "simulate").lower()
    print(f"  [INFO] Active Publish Mode: {pub_mode.upper()}")

    configs = [
        ("META_PAGE_ID", "Meta Page ID", False),
        ("META_PAGE_ACCESS_TOKEN", "Meta Page Access Token", True),
        ("META_GRAPH_VERSION", "Meta Graph API Version", False),
        ("THREADS_USER_ID", "Threads User ID", False),
        ("THREADS_ACCESS_TOKEN", "Threads Access Token", True),
        ("TIKTOK_CLIENT_KEY", "TikTok Client Key", True),
        ("TIKTOK_ACCESS_TOKEN", "TikTok Access Token", True),
        ("CLOUDFLARE_R2_ACCOUNT_ID", "Cloudflare R2 Account ID", True),
        ("CLOUDFLARE_R2_ACCESS_KEY_ID", "Cloudflare R2 Access Key", True),
        ("GEMINI_API_KEY", "Google Gemini API Key", True),
        ("TELEGRAM_BOT_TOKEN", "Telegram Bot Token", True),
    ]

    for key, name, is_secret in configs:
        val = os.getenv(key, "").strip()
        has_val = bool(val and "YOUR_" not in val and f"Example" not in val)
        if has_val:
            print(f"  [PASS] Config: {name} ({key}) is SET")
        else:
            if pub_mode == "live":
                print(f"  [FAIL] Config: {name} ({key}) is MISSING (Required in LIVE mode)")
                all_passed = False
            else:
                print(f"  [WARN] Config: {name} ({key}) is EMPTY (Gracefully simulated in {pub_mode.upper()} mode)")

    # 4. Storage & DB Schema Check
    db_file = root_dir / "storage" / "published_history.db"
    if db_file.exists():
        try:
            with sqlite3.connect(db_file) as conn:
                cols = [r[1] for r in conn.execute("PRAGMA table_info(posts)").fetchall()]
                required_cols = ["publish_status", "publish_results_json", "publish_attempts", "last_error", "content_hash"]
                missing = [c for c in required_cols if c not in cols]
                if not missing:
                    row_cnt = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
                    print(f"  [PASS] Database Schema: Validated ({row_cnt} post rows in storage)")
                else:
                    print(f"  [FAIL] Database Schema: Missing columns: {missing}")
                    all_passed = False
        except Exception as dbe:
            print(f"  [FAIL] Database Access: {dbe}")
            all_passed = False
    else:
        print(f"  [WARN] Database File: Not initialized yet at {db_file}")

    # 5. Staging Directories
    staging_dir = root_dir / "storage" / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    print(f"  [PASS] Local Staging Directory: {staging_dir} ready")

    print("=" * 65)
    if all_passed:
        print("  DIAGNOSTIC SUMMARY: ALL CORE CHECKS PASSED SUCCESSFULLY")
    else:
        print("  DIAGNOSTIC SUMMARY: SYSTEM HAS WARNINGS/FAILURES (REVIEW ABOVE)")
    print("=" * 65 + "\n")



def cmd_review():
    """Terminal-based interactive review queue."""
    init_db()
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM posts WHERE approval_status = 'pending' ORDER BY id ASC").fetchall()

    if not rows:
        print("\n✨ Review Queue is empty! No stories currently awaiting authorization.\n")
        return

    print(f"\nFound {len(rows)} pending story(ies) in review queue:\n")
    for r in rows:
        post = dict(r)
        print("=" * 65)
        print(f"Post ID: #{post['id']} | Format: {post['format_type'].upper()}")
        print(f"Headline: {post['headline']}")
        print(f"Source:   {post['source_url']}")
        print(f"Asset:    {post.get('media_url', 'None')}")
        print("-" * 65)
        print(f"Hook (0-3s):   \"{post.get('hook_narration')}\"")
        print(f"Body (4-30s):  \"{post.get('body_narration')}\"")
        print(f"Debate CTA:    \"{post.get('call_to_action')}\"")
        print("=" * 65)

        choice = input("Authorize action: [A]pprove & Publish Globally | [D]iscard | [S]kip: ").strip().lower()
        if choice == "a":
            with get_db_connection() as conn:
                pub_res = publish_to_ayrshare(post)
                ayr_id = pub_res.get("id", str(int(time.time())))
                conn.execute(
                    "UPDATE posts SET approval_status = 'published', published_at = CURRENT_TIMESTAMP, ayrshare_post_id = ? WHERE id = ?",
                    (ayr_id, post["id"])
                )
                conn.commit()
            print(f"✅ Post #{post['id']} PUBLISHED GLOBALLY via Ayrshare!\n")
        elif choice == "d":
            with get_db_connection() as conn:
                conn.execute("UPDATE posts SET approval_status = 'discarded', notes = 'Discarded via manage.py' WHERE id = ?", (post["id"],))
                conn.commit()
            print(f"❌ Post #{post['id']} DISCARDED.\n")
        else:
            print("Skipped.\n")


def cmd_studio(port: int = 8080):
    """Start the Executive Management Studio web server and launch browser."""
    import uvicorn
    from src.webhook_server import app

    url = f"http://localhost:{port}/"
    print("\n" + "=" * 65)
    print(f"  LAUNCHING AI TECH BROADCASTER — EXECUTIVE MANAGEMENT STUDIO")
    print(f"  URL: {url}")
    print("=" * 65)

    # Open browser after short delay
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=port)


def cmd_telegram_detect():
    """Poll Telegram getUpdates to automatically capture CHAT_ID and save to config/.env."""
    import httpx, re
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or "Example" in token:
        print("[Error] Please configure TELEGRAM_BOT_TOKEN in config/.env first.")
        return

    print(f"\nListening for updates on bot @Gasprovbot (Token: {token[:12]}...)...")
    print("Action required: Open Telegram, search for your bot, and send /start or any message!")
    print("Waiting up to 45 seconds for your message...\n")

    for i in range(15):
        try:
            res = httpx.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10.0)
            if res.status_code == 200:
                data = res.json()
                updates = data.get("result", [])
                if updates:
                    last_msg = updates[-1].get("message") or updates[-1].get("channel_post")
                    if last_msg:
                        chat = last_msg.get("chat", {})
                        chat_id = str(chat.get("id"))
                        chat_title = chat.get("title") or chat.get("username") or chat.get("first_name", "Unknown")
                        print(f"[SUCCESS] Detected Telegram Chat ID: {chat_id} ({chat_title})")

                        # Update config/.env
                        env_file = root_dir / "config" / ".env"
                        if env_file.exists():
                            content = env_file.read_text(encoding="utf-8")
                            content = re.sub(r"TELEGRAM_CHAT_ID=.*", f"TELEGRAM_CHAT_ID={chat_id}", content)
                            env_file.write_text(content, encoding="utf-8")
                            print(f"[UPDATED] Saved TELEGRAM_CHAT_ID={chat_id} to config/.env!")

                        # Send a test confirmation message to Telegram
                        httpx.post(
                            f"https://api.telegram.org/bot{token}/sendMessage",
                            json={"chat_id": chat_id, "text": "🤖 AI Tech Broadcaster HITL Gate connected successfully!"},
                            timeout=10.0
                        )
                        print("[SENT] Sent test confirmation message to your Telegram!\n")
                        return
        except Exception as e:
            pass
        time.sleep(3)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("\n[TIMEOUT] No messages received yet. Please make sure to search for @Gasprovbot in Telegram and send a message, then run: python manage.py telegram-id")


def cmd_watch(once: bool = False):
    """Live Terminal Command Center: monitors daemon heartbeat, recent broadcasts, and live links."""
    init_db()
    c_green = "\033[92m"
    c_cyan = "\033[96m"
    c_yellow = "\033[93m"
    c_red = "\033[91m"
    c_bold = "\033[1m"
    c_reset = "\033[0m"

    while True:
        # Clear screen on ANSI terminals if running interactive loop
        if not once and sys.stdout.isatty():
            sys.stdout.write("\033[2J\033[H")

        brain_model = os.getenv("DIRECTOR_MODEL", "gemini-3.8-flash")
        thinking_level = os.getenv("GEMINI_THINKING_LEVEL", "high").upper()
        mode = os.getenv("PUBLISH_MODE", "simulate").upper()

        print(f"{c_bold}{c_cyan}========================================================================={c_reset}")
        print(f"{c_bold}  AI TECH BROADCASTER — LIVE TERMINAL OBSERVABILITY CENTER{c_reset}")
        print(f"  Brain: {c_green}[{brain_model} ({thinking_level} EFFORT)]{c_reset} | Mode: {c_yellow}[{mode}]{c_reset}")
        print(f"{c_bold}{c_cyan}========================================================================={c_reset}\n")

        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, format_type, headline, publish_status, last_error, publish_results_json, created_at "
                "FROM posts ORDER BY id DESC LIMIT 6"
            ).fetchall()

        if not rows:
            print("  No broadcast history yet. Run 'python manage.py broadcast --instant' to start!\n")
        else:
            for r in rows:
                p_id = r["id"]
                fmt = (r["format_type"] or "POST").upper()
                status = (r["publish_status"] or "UNKNOWN").upper()
                title = (r["headline"] or "Untitled")[:55]
                time_str = r["created_at"] or ""

                if status in ("PUBLISHED", "SIMULATED", "PASSED"):
                    status_badge = f"{c_green}[{status}]{c_reset}"
                elif status in ("BLOCKED", "FAILED"):
                    status_badge = f"{c_red}[{status}]{c_reset}"
                else:
                    status_badge = f"{c_yellow}[{status}]{c_reset}"

                print(f"{c_bold}#{p_id}{c_reset} [{fmt:5}] {status_badge} {c_bold}{title}{c_reset} ({time_str})")

                # Parse publish outcomes / URLs
                res_json = r["publish_results_json"]
                links = []
                if res_json:
                    try:
                        results = json.loads(res_json)
                        for res in results:
                            plat = res.get("platform", "").capitalize()
                            p_stat = res.get("status", "")
                            url = res.get("permalink") or ""
                            if url:
                                links.append(f"{plat}: {c_cyan}{url}{c_reset}")
                            elif p_stat == "simulated":
                                links.append(f"{plat}: {c_yellow}(simulated){c_reset}")
                            elif p_stat == "skipped":
                                links.append(f"{plat}: {c_reset}(skipped){c_reset}")
                    except Exception:
                        pass

                if links:
                    print(f"   ↳ Links: {' | '.join(links)}")
                elif r["last_error"]:
                    print(f"   ↳ Reason: {c_red}{r['last_error'][:80]}{c_reset}")
                print()

        print(f"{c_bold}-------------------------------------------------------------------------{c_reset}")
        print("Commands: 'python manage.py broadcast --instant' | 'python manage.py repair' | 'python manage.py optimize-profile'")
        if once:
            break
        print(f"\nAuto-refreshing in 5s... (Press Ctrl+C to exit)")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\nExiting monitor.")
            break


def cmd_feed(limit: int = 10):
    """Display a clean history table of recent posts with Judge outcomes and platform URLs."""
    init_db()
    c_green = "\033[92m"
    c_cyan = "\033[96m"
    c_red = "\033[91m"
    c_reset = "\033[0m"

    print(f"\n=== AI TECH BROADCASTER — RECENT POST FEED (LAST {limit}) ===")
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, format_type, headline, source_url, publish_status, last_error, publish_results_json, created_at "
            "FROM posts ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()

    for r in rows:
        st = (r["publish_status"] or "UNKNOWN").upper()
        color = c_green if st in ("PUBLISHED", "SIMULATED") else (c_red if st in ("BLOCKED", "FAILED") else c_reset)
        print(f"\n#{r['id']} [{r['format_type'].upper()}] {color}[{st}]{c_reset} {r['headline']}")
        print(f"  Source: {r['source_url']}")
        if r["publish_results_json"]:
            try:
                results = json.loads(r["publish_results_json"])
                for res in results:
                    url = res.get("permalink") or f"({res.get('status')})"
                    print(f"  • {res.get('platform', '').capitalize()}: {c_cyan}{url}{c_reset}")
            except Exception:
                pass
        if r["last_error"]:
            print(f"  • Blocked Reason: {r['last_error']}")
    print()


def cmd_optimize_profile(platform: str = "all", apply: bool = False):
    """Generate and apply optimized bios and descriptions for social accounts."""
    from src.profile_manager import generate_optimized_profiles, apply_profile_updates
    c_cyan = "\033[96m"
    c_green = "\033[92m"
    c_bold = "\033[1m"
    c_reset = "\033[0m"

    print(f"\n{c_bold}{c_cyan}=== SOCIAL MEDIA PROFILE & BIO OPTIMIZER ==={c_reset}")
    profiles = generate_optimized_profiles()

    for plat, data in profiles.items():
        if platform != "all" and platform != plat:
            continue
        print(f"\n{c_bold}📱 {plat.upper()} PROFILE SPECIFICATION:{c_reset}")
        for k, v in data.items():
            print(f"  {c_bold}{k}:{c_reset}\n{v}\n")

    if apply:
        print(f"{c_bold}Applying updates via live APIs...{c_reset}")
        res = apply_profile_updates(profiles_data=profiles, platform=platform, dry_run=False)
        print(f"Outcome: {json.dumps(res, indent=2)}")
    else:
        print(f"{c_green}Tip: Run 'python manage.py optimize-profile --apply' to update Telegram & Facebook live!{c_reset}\n")


def cmd_repair():
    """Run Reach Diagnostic and Autonomous Repair Engine to extract learned rules."""
    from src.repair_engine import run_repair_cycle
    c_cyan = "\033[96m"
    c_green = "\033[92m"
    c_bold = "\033[1m"
    c_reset = "\033[0m"

    print(f"\n{c_bold}{c_cyan}=== AUTONOMOUS REPAIR & AUDIENCE REACH DIAGNOSTIC ENGINE ==={c_reset}")
    res = run_repair_cycle()
    print(f"  - Posts Analyzed:        {res.get('posts_analyzed')}")
    print(f"  - Underperforming Posts: {res.get('underperforming_count')}")
    print(f"  - Viral/Solid Posts:     {res.get('viral_count')}")
    print(f"  - Total Active Rules:    {res.get('total_active_rules')}")
    print(f"\n{c_bold}ACTIVE SELF-CORRECTION KNOWLEDGE BASE (storage/learning_memory.json):{c_reset}")
    for r in res.get("active_rules", []):
        cat = r.get("category", "").upper()
        print(f"  {c_green}[{r.get('rule_id')}][{cat}]{c_reset} {r.get('directive')}")
        print(f"     ↳ {c_cyan}Rationale:{c_reset} {r.get('rationale')} (Confidence: {r.get('confidence')})\n")


def cmd_tiktok_auth(code: Optional[str] = None, redirect_uri: Optional[str] = None, generate_url: bool = False):
    """Generate TikTok OAuth URL or exchange authorization code for permanent tokens."""
    from src.publisher_tiktok import generate_tiktok_auth_url, exchange_tiktok_code

    ck = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
    cs = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
    default_redirect = "https://ai-tech-broadcaster.vercel.app/api/auth/tiktok/callback"
    target_redirect = redirect_uri or default_redirect

    print("\n" + "=" * 65)
    print("  TIKTOK CONTENT POSTING API v2 — OAUTH AUTHENTICATOR")
    print("=" * 65)
    print(f"  • Client Key:    {ck if ck else '[NOT SET]'}")
    print(f"  • Client Secret: {'[CONFIGURED]' if cs else '[NOT SET]'}")
    print(f"  • Redirect URI:  {target_redirect}")
    print("=" * 65 + "\n")

    if not ck or not cs:
        print("❌ Error: TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET must be configured in config/.env first.")
        return

    if code:
        print("🔄 Exchanging authorization code for access and refresh tokens...")
        res = exchange_tiktok_code(code, target_redirect)
        if res.get("status") == "success":
            print("✅ TikTok OAuth Authorization Succeeded!")
            print(f"  • Open ID:           {res.get('open_id')}")
            print(f"  • Scopes Granted:    {res.get('scope')}")
            print(f"  • Access Token TTL:  {res.get('expires_in')}s (auto-refreshed daily)")
            print(f"  • Refresh Token TTL: {res.get('refresh_expires_in')}s (valid 365 days)")
            print("\n🎉 Token persisted to storage/tiktok_token.json and config/.env!")
            print("Autonomous TikTok Reel broadcasting is now LIVE and fully enabled.\n")
        else:
            print(f"❌ Token Exchange Failed: {res.get('message') or res}")
            if "response" in res:
                print(f"Response: {res.get('response')}\n")
        return

    # Generate authorization URL
    auth_url = generate_tiktok_auth_url(target_redirect)
    print("📋 STEP 1: Verify this Redirect URI is added in your TikTok Developer App settings:")
    print(f"   {target_redirect}\n")
    print("🔗 STEP 2: Open this URL in your browser to authorize your TikTok account:")
    print(f"   {auth_url}\n")
    print("📥 STEP 3: After authorizing, copy the 'code' parameter from the redirected URL, and run:")
    print(f"   python manage.py tiktok-auth --code <YOUR_CODE> --redirect \"{target_redirect}\"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Tech Broadcaster Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available management commands")

    subparsers.add_parser("status", help="Show system status and KPIs")
    subparsers.add_parser("doctor", help="Run comprehensive diagnostic health check")

    scan_parser = subparsers.add_parser("scan", help="Run immediate broadcast cycle")
    scan_parser.add_argument("--format", choices=["post", "reel", "story", "all"], default="all", help="Target broadcast format")
    scan_parser.add_argument("--force", action="store_true", help="Force run by clearing any stale cycle locks")

    bcast_parser = subparsers.add_parser("broadcast", help="Trigger instant broadcast and watch in real time")
    bcast_parser.add_argument("--format", choices=["post", "reel", "story", "all"], default="all", help="Target format")
    bcast_parser.add_argument("--instant", action="store_true", default=True, help="Run immediately")
    bcast_parser.add_argument("--force", action="store_true", help="Force run by clearing any stale cycle locks")

    watch_parser = subparsers.add_parser("watch", help="Live terminal dashboard monitor")
    watch_parser.add_argument("--once", action="store_true", help="Print single snapshot without looping")

    feed_parser = subparsers.add_parser("feed", help="View recent broadcast history and clickable URLs")
    feed_parser.add_argument("--limit", type=int, default=10, help="Number of records to show")

    prof_parser = subparsers.add_parser("optimize-profile", help="Generate and apply optimized social bios")
    prof_parser.add_argument("--platform", choices=["all", "telegram", "facebook", "instagram", "threads", "tiktok"], default="all")
    prof_parser.add_argument("--apply", action="store_true", help="Apply updates via live APIs")

    subparsers.add_parser("repair", help="Analyze reach drop-offs and update learning memory")
    subparsers.add_parser("review", help="Review pending stories in terminal")
    subparsers.add_parser("sidecar", help="Run continuous hourly background sidecar loop")
    subparsers.add_parser("telegram-id", help="Auto-detect Telegram Chat ID from incoming message")

    tk_parser = subparsers.add_parser("tiktok-auth", help="TikTok OAuth v2 authorization & token exchange")
    tk_parser.add_argument("--code", type=str, help="Authorization code returned by TikTok redirect")
    tk_parser.add_argument("--redirect", type=str, default="https://ai-tech-broadcaster.vercel.app/api/auth/tiktok/callback", help="Redirect URI")
    tk_parser.add_argument("--generate-url", action="store_true", help="Generate authorization URL")

    studio_parser = subparsers.add_parser("studio", help="Start Web Management Studio")
    studio_parser.add_argument("--port", type=int, default=8080, help="Port for Studio Web Server")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "doctor":
        cmd_doctor()
    elif args.command in ("scan", "broadcast"):
        cmd_scan(args.format, force=getattr(args, "force", False))
    elif args.command == "watch":
        cmd_watch(once=getattr(args, "once", False))
    elif args.command == "feed":
        cmd_feed(args.limit)
    elif args.command == "optimize-profile":
        cmd_optimize_profile(args.platform, apply=args.apply)
    elif args.command == "repair":
        cmd_repair()
    elif args.command == "review":
        cmd_review()
    elif args.command == "sidecar":
        run_scheduled_sidecar(1)
    elif args.command == "tiktok-auth":
        cmd_tiktok_auth(code=getattr(args, "code", None), redirect_uri=getattr(args, "redirect", None), generate_url=getattr(args, "generate_url", False))
    elif args.command == "studio":
        cmd_studio(args.port)
    elif args.command == "telegram-id":
        cmd_telegram_detect()
    else:
        cmd_status()
        print("Tip: Run 'python manage.py watch' to monitor live broadcasts, or 'python manage.py --help'.")



