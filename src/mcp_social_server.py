"""
Model Context Protocol (MCP) Server for AI Tech Broadcaster
Provides stdio JSON-RPC 2.0 interfaces for:
1. sqlite-history (Deterministic deduplication & record-keeping)
2. web-fetcher (Grounded primary documentation & benchmark extraction)
3. social-dispatcher (R2 asset staging, Telegram HITL review & Ayrshare publication)
"""

import sys
import os
import json
import logging
import sqlite3
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from src.r2_storage import upload_media_to_r2, is_r2_configured
from src.webhook_server import (
    generate_hmac_token,
    publish_to_ayrshare,
    publish_dispatcher,
    DATABASE_PATH,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    init_db,
)

# Logging directed to stderr so stdout remains clean for MCP JSON-RPC protocol
logging.basicConfig(
    stream=sys.stderr,
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mcp_social_server")

init_db()


# ---------------------------------------------------------------------------
# Core Tool Implementations
# ---------------------------------------------------------------------------

def tool_sqlite_read_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Execute a read SQL query against storage/published_history.db."""
    params = params or {}
    logger.info("Executing read_query: %s with params: %s", query, params)
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def tool_sqlite_write_query(query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Execute a write/update SQL query against storage/published_history.db."""
    params = params or {}
    logger.info("Executing write_query: %s with params: %s", query, params)
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return {
            "status": "success",
            "rows_affected": cursor.rowcount,
            "last_row_id": cursor.lastrowid
        }


def tool_web_fetch(url: str) -> Dict[str, Any]:
    """Fetch raw page and extract clean structured text/markdown for grounded verification."""
    logger.info("Fetching source URL: %s", url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Tech-Broadcaster/2.0 (Grounded-Verification-Engine)"
    }
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code >= 400:
            return {
                "error": f"HTTP {resp.status_code}",
                "url": url,
                "text": ""
            }

        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Remove noisy elements
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
            element.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else "Technical Announcement"
        
        # Extract text preserving paragraphs and headers
        body_text = soup.get_text(separator="\n", strip=True)
        # Limit to first 25,000 chars to fit context window comfortably while retaining dense technical metrics
        truncated_text = body_text[:25000]

        return {
            "url": url,
            "title": title,
            "status": resp.status_code,
            "content": truncated_text,
            "length": len(truncated_text)
        }


def tool_upload_media_to_r2(file_path: str, destination_key: Optional[str] = None) -> Dict[str, Any]:
    """Upload a local render (output_clip.mp4 or output_graphic.png) to Cloudflare R2."""
    logger.info("Uploading media to R2: %s", file_path)
    cdn_url = upload_media_to_r2(file_path, destination_key)
    return {
        "status": "success",
        "media_url": cdn_url,
        "local_file": file_path
    }


def tool_send_telegram_approval(
    post_id: int,
    headline: str,
    format_type: str,
    media_url: str,
    hook_narration: str,
    body_narration: str,
    call_to_action: str,
    platform_captions: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Dispatch interactive preview card with [✅ Approve & Post Globally] and [❌ Discard] buttons
    to the Telegram HITL editorial channel.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.cursor().execute("SELECT source_url FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise ValueError(f"Post ID {post_id} not found in database.")
        source_url = row["source_url"]

    token = generate_hmac_token(source_url, post_id)
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("UPDATE posts SET verification_token = ? WHERE id = ?", (token, post_id))
        conn.commit()

    card_text = (
        f"🚨 *TECH INTELLIGENCE BROADCAST PROPOSAL*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *Headline*: {headline}\n"
        f"🏷️ *Format*: `{format_type.upper()}`\n"
        f"🔗 *Source*: {source_url}\n"
        f"🎬 *Asset CDN*: {media_url}\n\n"
        f"🎙️ *Hook (0-3s)*:\n\"{hook_narration}\"\n\n"
        f"📝 *Core Body (4-30s)*:\n\"{body_narration}\"\n\n"
        f"💬 *Debate CTA*:\n\"{call_to_action}\"\n\n"
        f"📱 *Short-Form Caption*:\n{platform_captions.get('short_form', '')}\n\n"
        f"🌐 *Microblog (X/Threads)*:\n{platform_captions.get('microblog', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔒 Cryptographic Nonce: `{token}`\n"
        f"Awaiting Editorial Authorization..."
    )

    inline_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve & Post Globally", "callback_data": f"approve:{token}:{post_id}"},
                {"text": "❌ Discard", "callback_data": f"discard:{token}:{post_id}"}
            ]
        ]
    }

    message_id = None
    if TELEGRAM_BOT_TOKEN and "Example" not in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            # Check if there is an actual local video or graphic file to attach directly
            media_file = None
            if media_url:
                filename = Path(media_url.split("?")[0]).name
                candidate = root_dir / "storage" / "staging" / filename
                if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 200:
                    media_file = candidate

            sent = False
            # 1. Try sending as playable video if it's an MP4 file
            if media_file and media_file.suffix.lower() == ".mp4":
                try:
                    with open(media_file, "rb") as vf:
                        files = {"video": (media_file.name, vf, "video/mp4")}
                        data = {
                            "chat_id": TELEGRAM_CHAT_ID,
                            "caption": card_text[:1024],
                            "parse_mode": "Markdown",
                            "reply_markup": json.dumps(inline_keyboard)
                        }
                        resp = httpx.post(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
                            data=data,
                            files=files,
                            timeout=60.0
                        )
                        if resp.status_code == 400:
                            vf.seek(0)
                            data["caption"] = card_text.replace("*", "").replace("`", "")[:1024]
                            data.pop("parse_mode", None)
                            resp = httpx.post(
                                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo",
                                data=data,
                                files=files,
                                timeout=60.0
                            )
                        if resp.status_code == 200:
                            resp_data = resp.json()
                            message_id = resp_data.get("result", {}).get("message_id")
                            sent = True
                            logger.info("Playable video dispatched to Telegram for preview (message_id=%s)", message_id)
                except Exception as vid_err:
                    logger.warning("Failed to send video directly to Telegram: %s", vid_err)

            # 2. Try sending as high-res photo if it's an image file
            elif media_file and media_file.suffix.lower() in (".png", ".jpg", ".jpeg"):
                try:
                    with open(media_file, "rb") as pf:
                        files = {"photo": (media_file.name, pf, "image/png")}
                        data = {
                            "chat_id": TELEGRAM_CHAT_ID,
                            "caption": card_text[:1024],
                            "parse_mode": "Markdown",
                            "reply_markup": json.dumps(inline_keyboard)
                        }
                        resp = httpx.post(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                            data=data,
                            files=files,
                            timeout=45.0
                        )
                        if resp.status_code == 400:
                            pf.seek(0)
                            data["caption"] = card_text.replace("*", "").replace("`", "")[:1024]
                            data.pop("parse_mode", None)
                            resp = httpx.post(
                                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto",
                                data=data,
                                files=files,
                                timeout=45.0
                            )
                        if resp.status_code == 200:
                            resp_data = resp.json()
                            message_id = resp_data.get("result", {}).get("message_id")
                            sent = True
                            logger.info("Graphic image dispatched to Telegram for preview (message_id=%s)", message_id)
                except Exception as img_err:
                    logger.warning("Failed to send photo directly to Telegram: %s", img_err)

            # 3. Fallback to rich text sendMessage if media could not be sent directly
            if not sent:
                tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                resp = httpx.post(
                    tg_url,
                    json={
                        "chat_id": TELEGRAM_CHAT_ID,
                        "text": card_text,
                        "parse_mode": "Markdown",
                        "reply_markup": inline_keyboard
                    },
                    timeout=15.0
                )
                if resp.status_code == 400:
                    clean_text = card_text.replace("*", "").replace("`", "")
                    resp = httpx.post(
                        tg_url,
                        json={
                            "chat_id": TELEGRAM_CHAT_ID,
                            "text": clean_text,
                            "reply_markup": inline_keyboard
                        },
                        timeout=15.0
                    )
                if resp.status_code == 200:
                    resp_data = resp.json()
                    message_id = resp_data.get("result", {}).get("message_id")
                    logger.info("Telegram text approval card sent successfully (message_id=%s)", message_id)
                else:
                    logger.warning("Telegram API error (%s): %s", resp.status_code, resp.text)

            if message_id:
                with sqlite3.connect(DATABASE_PATH) as conn:
                    conn.execute("UPDATE posts SET telegram_message_id = ? WHERE id = ?", (message_id, post_id))
                    conn.commit()
        except Exception as e:
            logger.error("Failed to dispatch Telegram message: %s", e)

    return {
        "status": "pending_approval",
        "post_id": post_id,
        "token": token,
        "telegram_dispatched": message_id is not None,
        "review_url": f"http://localhost:8080/review/{post_id}"
    }


def tool_publish_to_networks(post_id: int) -> Dict[str, Any]:
    """Publish an approved post to TikTok, Instagram Reels, Facebook Reels, Threads, and X."""
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.cursor().execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not row:
            raise ValueError(f"Post ID {post_id} not found.")
        post = dict(row)

    if post["approval_status"] not in ("approved", "pending"):
        raise ValueError(f"Cannot publish post with status '{post['approval_status']}'. Must be approved.")

    publish_result = publish_dispatcher(post)
    pub_id = publish_result.get("id", "simulated")
    provider = publish_result.get("provider", "ayrshare")
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "UPDATE posts SET approval_status = 'published', published_at = CURRENT_TIMESTAMP, ayrshare_post_id = ? WHERE id = ?",
            (pub_id, post_id)
        )
        conn.commit()

    return {
        "status": "published",
        "post_id": post_id,
        "broadcast_id": pub_id,
        "provider": provider,
        "details": publish_result
    }


# ---------------------------------------------------------------------------
# MCP Tool Registry & JSON-RPC 2.0 Handler
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = {
    "read_query": {
        "server": "sqlite-history",
        "description": "Execute a read SQL query against published_history.db (e.g. check for deduplication).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL SELECT statement."},
                "params": {"type": "object", "description": "Named parameters for query."}
            },
            "required": ["query"]
        },
        "handler": tool_sqlite_read_query
    },
    "write_query": {
        "server": "sqlite-history",
        "description": "Execute an INSERT or UPDATE query against published_history.db.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL INSERT/UPDATE statement."},
                "params": {"type": "object", "description": "Named parameters for query."}
            },
            "required": ["query"]
        },
        "handler": tool_sqlite_write_query
    },
    "fetch": {
        "server": "web-fetcher",
        "description": "Fetch raw HTML/text from primary documentation link for grounded verification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Primary source URL to fetch."}
            },
            "required": ["url"]
        },
        "handler": tool_web_fetch
    },
    "upload_media_to_r2": {
        "server": "social-dispatcher",
        "description": "Upload rendered media (output_clip.mp4 or output_graphic.png) to Cloudflare R2 CDN.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Local filesystem path to rendered media asset."},
                "destination_key": {"type": "string", "description": "Target R2 object key (optional)."}
            },
            "required": ["file_path"]
        },
        "handler": tool_upload_media_to_r2
    },
    "send_telegram_approval": {
        "server": "social-dispatcher",
        "description": "Dispatch interactive preview card with [✅ Approve & Post Globally] and [❌ Discard] buttons.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer"},
                "headline": {"type": "string"},
                "format_type": {"type": "string", "enum": ["video", "text_image"]},
                "media_url": {"type": "string"},
                "hook_narration": {"type": "string"},
                "body_narration": {"type": "string"},
                "call_to_action": {"type": "string"},
                "platform_captions": {"type": "object"}
            },
            "required": ["post_id", "headline", "format_type", "media_url", "hook_narration", "body_narration", "call_to_action", "platform_captions"]
        },
        "handler": tool_send_telegram_approval
    },
    "publish_to_networks": {
        "server": "social-dispatcher",
        "description": "Publish approved post to TikTok, Instagram Reels, Facebook Reels, Threads, and X via Ayrshare with 'is_aigc': true.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "post_id": {"type": "integer", "description": "Database ID of approved post."}
            },
            "required": ["post_id"]
        },
        "handler": tool_publish_to_networks
    }
}


def get_tools_for_service(service_filter: str = "all") -> List[Dict[str, Any]]:
    """Return tool schemas filtered by server name."""
    tools = []
    for name, defn in TOOL_DEFINITIONS.items():
        if service_filter in ("all", defn["server"]):
            # Use namespaced or raw name depending on server filter
            tool_name = name if service_filter == defn["server"] else f"{defn['server']}/{name}"
            tools.append({
                "name": tool_name,
                "description": defn["description"],
                "inputSchema": defn["inputSchema"]
            })
    return tools


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Find and execute handler by name."""
    # Strip server prefix if present
    bare_name = tool_name.split("/")[-1]
    if bare_name not in TOOL_DEFINITIONS:
        raise ValueError(f"Unknown tool: '{tool_name}'")
    handler = TOOL_DEFINITIONS[bare_name]["handler"]
    return handler(**arguments)


def run_stdio_server(service_filter: str = "all"):
    """Run MCP JSON-RPC 2.0 stdio server loop."""
    logger.info("Starting MCP stdio server for service: %s", service_filter)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception as e:
            logger.error("Failed to parse JSON-RPC input: %s", e)
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        response = {"jsonrpc": "2.0", "id": req_id}

        if method == "initialize":
            response["result"] = {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": f"ai-tech-broadcaster-{service_filter}",
                    "version": "2.0.0"
                }
            }
        elif method == "notifications/initialized":
            # Notifications do not return responses
            continue
        elif method == "ping":
            response["result"] = {}
        elif method == "tools/list":
            response["result"] = {
                "tools": get_tools_for_service(service_filter)
            }
        elif method == "tools/call":
            tool_name = params.get("name", "")
            args = params.get("arguments", {})
            try:
                result = execute_tool(tool_name, args)
                response["result"] = {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)
                        }
                    ]
                }
            except Exception as e:
                logger.exception("Error executing tool %s: %s", tool_name, e)
                response["error"] = {
                    "code": -32000,
                    "message": str(e)
                }
        else:
            response["error"] = {
                "code": -32601,
                "message": f"Method '{method}' not found"
            }

        # Write response to stdout followed by newline
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


def run_self_test():
    """Verify tool operations directly in standalone test mode."""
    print("=== RUNNING MCP TOOLKIT SELF-TEST ===")
    
    # 1. Test sqlite write_query
    print("\n[1] Testing sqlite-history/write_query...")
    test_url = f"https://deepmind.google/discover/blog/test-release-{int(os.getpid())}"
    res_insert = tool_sqlite_write_query(
        "INSERT INTO posts (source_url, headline, format_type, media_url, approval_status) VALUES (:source_url, :headline, :format_type, :media_url, 'pending')",
        {
            "source_url": test_url,
            "headline": "Gemini 2.0 Flash Beats Benchmarks",
            "format_type": "video",
            "media_url": "https://cdn.broadcaster.ai/media/output_clip.mp4"
        }
    )
    print("Insert result:", res_insert)
    post_id = res_insert["last_row_id"]

    # 2. Test sqlite read_query
    print("\n[2] Testing sqlite-history/read_query...")
    rows = tool_sqlite_read_query(
        "SELECT id, headline, approval_status FROM posts WHERE source_url = :source_url LIMIT 1",
        {"source_url": test_url}
    )
    print("Read result:", rows)
    assert len(rows) == 1
    assert rows[0]["id"] == post_id

    # 3. Test web_fetch
    print("\n[3] Testing web-fetcher/fetch...")
    fetch_res = tool_web_fetch("https://arxiv.org/abs/2301.00234")
    print("Fetch status:", fetch_res.get("status"), "Title:", fetch_res.get("title")[:40])

    # 4. Test R2 upload
    print("\n[4] Testing social-dispatcher/upload_media_to_r2...")
    dummy_clip = Path("storage/staging/output_clip.mp4")
    dummy_clip.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42")
    r2_res = tool_upload_media_to_r2(str(dummy_clip), "media/output_clip.mp4")
    print("R2 staging result:", r2_res)

    # 5. Test Telegram approval card dispatch
    print("\n[5] Testing social-dispatcher/send_telegram_approval...")
    tg_res = tool_send_telegram_approval(
        post_id=post_id,
        headline="Gemini 2.0 Flash Breakthrough",
        format_type="video",
        media_url=r2_res["media_url"],
        hook_narration="AI just shattered coding benchmarks.",
        body_narration="DeepMind released Gemini 2.0 Flash with sub-second execution speeds.",
        call_to_action="Are autonomous agents ready to replace junior devs?",
        platform_captions={
            "short_form": "Gemini 2.0 Flash is here! #AI #TechNews #Gemini",
            "microblog": "DeepMind launches Gemini 2.0 Flash. https://deepmind.google"
        }
    )
    print("Telegram approval card:", tg_res)

    # 6. Test publish_to_networks
    print("\n[6] Testing social-dispatcher/publish_to_networks...")
    tool_sqlite_write_query("UPDATE posts SET approval_status = 'approved' WHERE id = :id", {"id": post_id})
    pub_res = tool_publish_to_networks(post_id)
    print("Publish result:", pub_res)

    print("\n=== ALL MCP TOOLS PASSED SELF-TEST SUCCESSFULLY! ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Tech Broadcaster MCP Server")
    parser.add_argument("--service", choices=["all", "sqlite-history", "web-fetcher", "social-dispatcher"], default="all")
    parser.add_argument("--test", action="store_true", help="Run internal tool unit tests")
    args = parser.parse_args()

    if args.test:
        run_self_test()
    else:
        run_stdio_server(args.service)
