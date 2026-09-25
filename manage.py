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
import argparse
import webbrowser
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from src.webhook_server import get_db_connection, init_db, publish_to_ayrshare, DATABASE_PATH
from src.pipeline import execute_broadcast_cycle, run_scheduled_sidecar


def cmd_status():
    """Print system status, database KPIs, and integration states."""
    init_db()
    with get_db_connection() as conn:
        counts = {}
        for s in ["pending", "published", "discarded"]:
            row = conn.execute("SELECT COUNT(*) as c FROM posts WHERE approval_status = ?", (s,)).fetchone()
            counts[s] = row["c"]
        total = conn.execute("SELECT COUNT(*) as c FROM posts").fetchone()["c"]

    print("\n" + "=" * 65)
    print("  AI TECH BROADCASTER — SYSTEM STATUS & METRICS")
    print("=" * 65)
    print(f"  - SQLite Database:      {DATABASE_PATH}")
    print(f"  - Total Evaluated:      {total}")
    print(f"  - Pending HITL Review:  {counts.get('pending', 0)} (Awaiting your authorization)")
    print(f"  - Published Globally:   {counts.get('published', 0)}")
    print(f"  - Discarded / Filtered: {counts.get('discarded', 0)}")
    print("-" * 65)
    print(f"  * Gemini 2.0 Director:  {'[LIVE KEY]' if os.getenv('GEMINI_API_KEY') and 'YOUR_GEMINI' not in os.getenv('GEMINI_API_KEY') else '[SIMULATED / OFFLINE]'}")
    print(f"  * Telegram Bot HITL:    {'[CONFIGURED]' if os.getenv('TELEGRAM_BOT_TOKEN') and 'Example' not in os.getenv('TELEGRAM_BOT_TOKEN') else '[LOCAL WEB STUDIO]'}")
    print(f"  * Ayrshare Dispatcher:  {'[CONFIGURED]' if os.getenv('AYRSHARE_API_KEY') and 'AYRSHARE' not in os.getenv('AYRSHARE_API_KEY') else '[SIMULATED PUBLISHING]'}")
    print(f"  * Cloudflare R2 CDN:    {'[CONFIGURED]' if os.getenv('CLOUDFLARE_R2_ACCOUNT_ID') and 'your_' not in os.getenv('CLOUDFLARE_R2_ACCOUNT_ID') else '[LOCAL STAGING]'}")
    print("=" * 65 + "\n")


def cmd_scan():
    """Run an immediate broadcast cycle."""
    init_db()
    print("\n[Broadcaster] Launching immediate broadcast cycle...")
    res = execute_broadcast_cycle()
    if res:
        print("\n✅ Broadcast cycle completed successfully!")
        print(f"Post #{res['post_id']} staged for review: {res['approval']['review_url']}")
    else:
        print("\nℹ️ No new qualified stories in this cycle.")


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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Tech Broadcaster Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available management commands")

    subparsers.add_parser("status", help="Show system status and KPIs")
    subparsers.add_parser("scan", help="Run immediate broadcast cycle")
    subparsers.add_parser("review", help="Review pending stories in terminal")
    subparsers.add_parser("sidecar", help="Run continuous hourly background sidecar loop")
    subparsers.add_parser("telegram-id", help="Auto-detect Telegram Chat ID from incoming message")

    studio_parser = subparsers.add_parser("studio", help="Start Web Management Studio")
    studio_parser.add_argument("--port", type=int, default=8080, help="Port for Studio Web Server")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "scan":
        cmd_scan()
    elif args.command == "review":
        cmd_review()
    elif args.command == "sidecar":
        run_scheduled_sidecar(1)
    elif args.command == "studio":
        cmd_studio(args.port)
    elif args.command == "telegram-id":
        cmd_telegram_detect()
    else:
        cmd_status()
        print("Tip: Run 'python manage.py studio' to launch the web dashboard, or 'python manage.py --help'.")

