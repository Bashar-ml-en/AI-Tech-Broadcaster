"""
Social Media Profile & Bio Optimization Engine for AI Tech Broadcaster
Manages, enhances, and synchronizes profile bios, authority taglines, and descriptions
across Telegram Channel, Instagram Professional, Threads, Facebook Page, and TikTok.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / "config" / ".env")

logger = logging.getLogger("profile_manager")

DIRECTOR_MODEL = os.getenv("DIRECTOR_MODEL", "gemini-3.8-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "").strip()
META_PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
META_PAGE_ID = os.getenv("META_PAGE_ID", "1399811016543093").strip()
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v20.0").strip()

DEFAULT_PROFILES = {
    "telegram": {
        "title": "Era of AI // Deep Tech Intelligence",
        "description": "⚡ Frontier AI Research & Autonomous Systems\n🔬 Daily 7-slide architecture deep dives, 9:16 reels, & paper breakdowns\n🌐 Models: Gemini • DeepSeek • Claude • OpenAI\n💬 Community & verified evals @Eraof_Ai",
        "pinned_message": "🚀 **Welcome to Era of AI**\n\nWe provide verified, no-hype technical briefings on frontier AI architectures, open-weights releases, and systems engineering.\n\n📌 **What we broadcast daily:**\n• 7-Page Architecture Carousel Decks\n• 30-Second SOTA Benchmark Reels\n• 24H Flash Signal Stories & Polls\n\n🔗 Follow us across Threads, Instagram, & Facebook @Eraof_Ai."
    },
    "instagram": {
        "name_field": "Era of AI | Models & Architecture",
        "bio": "⚡ Frontier AI Architecture & Systems\n🔬 SWE-bench • Open Weights • Hardware\n📊 7-Slide Deep Dives & 30s Reels\n👇 Daily Paper Intel & Telegram Deck",
        "link_text": "t.me/Eraof_Ai",
        "category": "Science & Technology"
    },
    "threads": {
        "bio": "Senior ML architecture & systems engineering breakdowns. Covering frontier models, MoE routing, KV-cache efficiency, and real SOTA benchmarks. Built for engineers.",
        "link": "t.me/Eraof_Ai"
    },
    "facebook": {
        "page_name": "Era of AI",
        "about": "The executive broadcast network for AI architecture, frontier foundation models, and autonomous software engineering. Verified benchmarks and technical breakdowns daily.",
        "category": "Artificial Intelligence Laboratory"
    },
    "tiktok": {
        "bio": "⚡ Frontier AI in 30s. Systems • Code • Models. Zero hype, pure engineering. 🔗",
        "category": "Tech & Education"
    }
}


def generate_optimized_profiles(
    brand_name: str = "Era of AI",
    niche: str = "Frontier AI Architecture, Foundation Models, & Systems Engineering"
) -> Dict[str, Any]:
    """
    Generate authoritative, high-conversion profiles and bios for all platforms.
    Uses Gemini 3.8 Flash High if GEMINI_API_KEY is configured, otherwise returns optimized defaults.
    """
    if GEMINI_API_KEY and "YOUR_" not in GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = f"""You are the Chief Brand Director for {brand_name}, an elite tech intelligence publication covering {niche}.
Generate optimized, high-status profile descriptions for 5 platforms adhering strictly to character limits:

1. TELEGRAM:
   - title: Under 64 chars
   - description: Under 255 chars, bullet points with ASCII/emojis
   - pinned_message: Welcoming, authoritative manifesto (~100 words)

2. INSTAGRAM:
   - name_field: Keyword-rich (<=30 chars, e.g. "{brand_name} | AI Architecture")
   - bio: Exactly under 150 chars, line breaks, high status, clear CTA
   - link_text: CTA link text

3. THREADS:
   - bio: Under 200 chars, engineer-focused, punchy

4. FACEBOOK:
   - about: Under 255 chars, authoritative company bio

5. TIKTOK:
   - bio: Under 80 chars, ultra-punchy

Respond strictly in JSON matching this exact structure:
{{
  "telegram": {{"title": "...", "description": "...", "pinned_message": "..."}},
  "instagram": {{"name_field": "...", "bio": "...", "link_text": "...", "category": "..."}},
  "threads": {{"bio": "...", "link": "..."}},
  "facebook": {{"page_name": "...", "about": "...", "category": "..."}},
  "tiktok": {{"bio": "...", "category": "..."}}
}}
"""
            gen_config = types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json"
            )
            try:
                gen_config.thinking_config = types.ThinkingConfig(thinking_budget=2048)
            except Exception:
                pass

            resp = client.models.generate_content(
                model=DIRECTOR_MODEL,
                contents=prompt,
                config=gen_config
            )
            if resp.text:
                data = json.loads(resp.text)
                return data
        except Exception as e:
            logger.warning("[Profile Optimizer] LLM generation failed, using defaults: %s", e)

    return DEFAULT_PROFILES


def apply_profile_updates(
    profiles_data: Optional[Dict[str, Any]] = None,
    platform: str = "all",
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Apply profile updates via live APIs where available (Telegram, Facebook)
    and output formatted instructions for app-only settings (Instagram, Threads, TikTok).
    """
    profiles = profiles_data or generate_optimized_profiles()
    results = {}

    # 1. Telegram Channel
    if platform in ("all", "telegram"):
        tg_data = profiles.get("telegram", {})
        if dry_run or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
            results["telegram"] = {
                "status": "simulated" if dry_run else "credentials_needed",
                "description": tg_data.get("description"),
                "title": tg_data.get("title"),
                "note": "Ready to apply. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in config/.env"
            }
        else:
            try:
                url_desc = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatDescription"
                url_title = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setChatTitle"
                with httpx.Client(timeout=15.0) as client:
                    r1 = client.post(url_desc, data={"chat_id": TELEGRAM_CHANNEL_ID, "description": tg_data.get("description", "")})
                    r2 = client.post(url_title, data={"chat_id": TELEGRAM_CHANNEL_ID, "title": tg_data.get("title", "")})
                results["telegram"] = {
                    "status": "applied" if r1.status_code == 200 else "error",
                    "desc_response": r1.json(),
                    "title_response": r2.json()
                }
            except Exception as e:
                results["telegram"] = {"status": "error", "error": str(e)}

    # 2. Facebook Page
    if platform in ("all", "facebook"):
        fb_data = profiles.get("facebook", {})
        if dry_run or not META_PAGE_ACCESS_TOKEN or len(META_PAGE_ACCESS_TOKEN) < 20:
            results["facebook"] = {
                "status": "simulated" if dry_run else "credentials_needed",
                "about": fb_data.get("about"),
                "note": "Ready to apply. Set META_PAGE_ACCESS_TOKEN in config/.env"
            }
        else:
            try:
                url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{META_PAGE_ID}"
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(url, data={
                        "about": fb_data.get("about", ""),
                        "access_token": META_PAGE_ACCESS_TOKEN
                    })
                results["facebook"] = {
                    "status": "applied" if resp.status_code == 200 else "error",
                    "response": resp.json()
                }
            except Exception as e:
                results["facebook"] = {"status": "error", "error": str(e)}

    # 3. Instagram, Threads, TikTok (Platform API guidelines)
    for p in ["instagram", "threads", "tiktok"]:
        if platform in ("all", p):
            results[p] = {
                "status": "ready_for_copy_paste",
                "profile_payload": profiles.get(p, {}),
                "guidance": f"Copy-paste the optimized bio directly into {p.capitalize()} profile settings."
            }

    return results
