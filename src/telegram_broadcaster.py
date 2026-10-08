"""
Telegram Dispatcher for AI Tech Broadcaster
Delivers the 3 format-specific variants to Telegram Bot and Channel:
- **POST**: 7-page carousel album with deep technical breakdown
- **REELS**: 9:16 vertical motion video with neural voiceover
- **STORY**: 3-page ephemeral vertical story deck with interactive poll zone
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / "config" / ".env")

logger = logging.getLogger("telegram_broadcaster")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")


def send_telegram_media_group(
    chat_id: str,
    image_paths: List[str],
    caption: str,
    bot_token: Optional[str] = None
) -> Dict[str, Any]:
    """Upload multiple photos as a single media group album to Telegram."""
    token = bot_token or TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    target = chat_id or TELEGRAM_CHANNEL_ID or os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not target:
        return {"status": "skipped", "reason": "missing_credentials"}

    valid_paths = [p for p in image_paths if Path(p).exists()]
    if not valid_paths:
        return {"status": "error", "reason": "no_images_found"}

    # Telegram sendMediaGroup accepts max 10 items
    valid_paths = valid_paths[:10]

    media_payload = []
    files = {}
    opened_files = []

    try:
        for idx, p in enumerate(valid_paths):
            f_handle = open(p, "rb")
            opened_files.append(f_handle)
            attach_name = f"photo_{idx}"
            files[attach_name] = (Path(p).name, f_handle, "image/png")

            item = {"type": "photo", "media": f"attach://{attach_name}"}
            if idx == 0:
                item["caption"] = caption[:1024]
                item["parse_mode"] = "Markdown"
            media_payload.append(item)

        url = f"https://api.telegram.org/bot{token}/sendMediaGroup"
        data = {
            "chat_id": target,
            "media": json.dumps(media_payload)
        }

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, data=data, files=files)
            if resp.status_code == 400:
                # Markdown parse error fallback: strip formatting and unescaped underscores
                clean_cap = caption.replace("*", "").replace("`", "").replace("_", " ")[:1024]
                media_payload[0]["caption"] = clean_cap
                media_payload[0].pop("parse_mode", None)
                data["media"] = json.dumps(media_payload)
                for f in opened_files:
                    f.seek(0)
                resp = client.post(url, data=data, files=files)

            if resp.status_code == 200:
                result = resp.json()
                logger.info("Media group successfully sent to %s (%d photos)", target, len(valid_paths))
                return {"status": "success", "result": result}
            else:
                logger.warning("sendMediaGroup failed: %s %s", resp.status_code, resp.text)
                return {"status": "error", "code": resp.status_code, "text": resp.text}
    except Exception as e:
        logger.exception("Exception in send_telegram_media_group: %s", e)
        return {"status": "exception", "error": str(e)}
    finally:
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass


def send_telegram_reel(
    chat_id: str,
    video_path: str,
    caption: str,
    bot_token: Optional[str] = None
) -> Dict[str, Any]:
    """Upload 9:16 playable MP4 video to Telegram."""
    token = bot_token or TELEGRAM_BOT_TOKEN or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    target = chat_id or TELEGRAM_CHANNEL_ID or os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
    if not token or not target:
        return {"status": "skipped", "reason": "missing_credentials"}

    vp = Path(video_path)
    if not vp.exists():
        return {"status": "error", "reason": "video_not_found"}

    url = f"https://api.telegram.org/bot{token}/sendVideo"
    formatted_caption = caption if caption.startswith("**REELS**") else f"**REELS**\n\n{caption}"

    try:
        with open(vp, "rb") as vf:
            files = {"video": (vp.name, vf, "video/mp4")}
            data = {
                "chat_id": target,
                "caption": formatted_caption[:1024],
                "parse_mode": "Markdown"
            }
            with httpx.Client(timeout=90.0) as client:
                resp = client.post(url, data=data, files=files)
                if resp.status_code == 400:
                    vf.seek(0)
                    clean_cap = formatted_caption.replace("*", "").replace("`", "").replace("_", " ")[:1024]
                    data["caption"] = clean_cap
                    data.pop("parse_mode", None)
                    resp = client.post(url, data=data, files=files)

                if resp.status_code == 200:
                    result = resp.json()
                    logger.info("Video reel successfully sent to %s", chat_id)
                    return {"status": "success", "result": result}
                else:
                    logger.warning("sendVideo failed: %s %s", resp.status_code, resp.text)
                    return {"status": "error", "code": resp.status_code, "text": resp.text}
    except Exception as e:
        logger.exception("Exception in send_telegram_reel: %s", e)
        return {"status": "exception", "error": str(e)}


def send_telegram_post_carousel(
    chat_id: str,
    slide_paths: List[str],
    caption: str,
    bot_token: Optional[str] = None
) -> Dict[str, Any]:
    """Upload 7-page carousel deck as an album with **POST** tagging."""
    formatted_caption = caption if caption.startswith("**POST**") else f"**POST**\n\n{caption}"
    return send_telegram_media_group(chat_id, slide_paths, formatted_caption, bot_token)


def send_telegram_story_deck(
    chat_id: str,
    slide_paths: List[str],
    caption: str,
    bot_token: Optional[str] = None
) -> Dict[str, Any]:
    """Upload 3-slide vertical story sequence as an album with **STORY** tagging."""
    formatted_caption = caption if caption.startswith("**STORY**") else f"**STORY**\n\n{caption}"
    return send_telegram_media_group(chat_id, slide_paths, formatted_caption, bot_token)


def dispatch_three_variants_to_telegram(
    post_slides: List[str],
    reel_video_path: str,
    story_slides: List[str],
    post_caption: str,
    reel_caption: str,
    story_caption: str,
    target_chats: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Dispatch all three format-specific variants to Telegram, tagged separately:
    1. **POST** (7-page carousel album)
    2. **REELS** (9:16 playable MP4 video)
    3. **STORY** (3-page vertical story deck)
    """
    targets = target_chats or []
    if not targets:
        # Prioritize public channel first so audience sees updates immediately
        chan = TELEGRAM_CHANNEL_ID or os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
        chat = TELEGRAM_CHAT_ID or os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if chan:
            targets.append(chan)
        if chat and chat not in targets:
            targets.append(chat)

    dispatch_results = {}

    for chat in targets:
        logger.info("Dispatching 3 variants to Telegram chat: %s", chat)
        chat_results = {}

        # 1. Post Variant
        if post_slides:
            res_post = send_telegram_post_carousel(chat, post_slides, post_caption)
            chat_results["post"] = res_post

        # 2. Reels Variant
        if reel_video_path and Path(reel_video_path).exists():
            res_reel = send_telegram_reel(chat, reel_video_path, reel_caption)
            chat_results["reel"] = res_reel

        # 3. Story Variant
        if story_slides:
            res_story = send_telegram_story_deck(chat, story_slides, story_caption)
            chat_results["story"] = res_story

        dispatch_results[chat] = chat_results

    return dispatch_results
