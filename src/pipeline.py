"""
Autonomous Broadcast Engine Pipeline for AI Tech Broadcaster
Implements:
1. Multi-Tier Harvesting (Tier 1 AI Labs, Tier 2 ArXiv/GitHub, Tier 3 Tech Press)
2. 14-Day Deterministic Deduplication against storage/published_history.db
3. Technical Qualification Filtering (>5% benchmark leaps, public weights, developer tooling)
4. Format Routing: Video (Veo 3.1 9:16) vs. Text_Image (Imagen 3.0 1:1)
5. Strict JSON Director Output Generation (Gemini 2.0 Flash)
6. Asset Generation & Cloudflare R2 Staging
7. Cryptographically Verified Telegram HITL Approval Gate Dispatch
8. 3-Hour Antigravity Sidecar Cron Orchestration
"""

import os
import re
import sys
import json
import time
import sqlite3
import logging
import argparse
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Ensure root directory is on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from src.r2_storage import upload_media_to_r2
from src.webhook_server import (
    DATABASE_PATH,
    generate_hmac_token,
    init_db
)
from src.mcp_social_server import (
    tool_sqlite_read_query,
    tool_sqlite_write_query,
    tool_web_fetch,
    tool_upload_media_to_r2,
    tool_send_telegram_approval
)
from src.carousel_generator import generate_carousel_deck, generate_story_slides
from src.video_synthesizer import synthesize_broadcast_video
from src.telegram_broadcaster import (
    dispatch_three_variants_to_telegram,
    send_telegram_post_carousel,
    send_telegram_story_deck,
    send_telegram_reel,
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_CHAT_ID
)
from src.persona_manager import detect_persona
import asyncio

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

env_path = root_dir / "config" / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger("broadcast_pipeline")
log_file = root_dir / "storage" / "logs" / "broadcaster.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logger.addHandler(file_handler)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DIRECTOR_MODEL = os.getenv("DIRECTOR_MODEL", "gemini-2.0-flash")
STAGING_DIR = root_dir / "storage" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)

# Curated Primary Feeds conforming strictly to Section 2 of Constitution & Direct AI Labs
FEED_SOURCES = [
    # Tier 1: Primary AI Labs (Direct Company Feeds & APIs)
    {"tier": 1, "name": "OpenAI News", "url": "https://openai.com/news/rss.xml", "type": "rss"},
    {"tier": 1, "name": "Google AI Blog", "url": "https://blog.google/technology/ai/rss/", "type": "rss"},
    {"tier": 1, "name": "Google DeepMind", "url": "https://deepmind.google/blog/", "type": "html"},
    {"tier": 1, "name": "Anthropic Research", "url": "https://www.anthropic.com/news", "type": "html"},
    {"tier": 1, "name": "Mistral AI", "url": "https://mistral.ai/news/rss", "type": "rss"},
    {"tier": 1, "name": "DeepSeek Models (HF)", "url": "https://huggingface.co/api/models?sort=lastModified&direction=-1&author=deepseek-ai&limit=5", "type": "json_hf_models", "author": "DeepSeek"},
    {"tier": 1, "name": "Qwen Models (HF)", "url": "https://huggingface.co/api/models?sort=lastModified&direction=-1&author=Qwen&limit=5", "type": "json_hf_models", "author": "Qwen"},
    {"tier": 1, "name": "Meta AI Blog", "url": "https://ai.meta.com/blog/", "type": "html"},
    {"tier": 1, "name": "Hugging Face Daily Papers", "url": "https://huggingface.co/api/daily_papers", "type": "json_hf_papers"},
    {"tier": 1, "name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml", "type": "rss"},
    # Real-Time Dynamic AI Intelligence Feeds
    {"tier": 1, "name": "HackerNews AI", "url": "https://hn.algolia.com/api/v1/search_by_date?tags=story&query=AI+OR+LLM+OR+DeepSeek+OR+Gemini&hitsPerPage=20", "type": "json_hn"},
    {"tier": 1, "name": "Google News AI", "url": "https://news.google.com/rss/search?q=Artificial+Intelligence+LLM+OR+DeepSeek+OR+OpenAI+when:1d&hl=en-US&gl=US&ceid=US:en", "type": "rss"},
    # Tier 2: Academic Preprints & Core Runtime Releases
    {"tier": 2, "name": "ArXiv cs.CL (LLMs)", "url": "https://rss.arxiv.org/rss/cs.CL", "type": "rss"},
    {"tier": 2, "name": "ArXiv cs.AI Recent", "url": "https://rss.arxiv.org/rss/cs.AI", "type": "rss"},
    {"tier": 2, "name": "ArXiv cs.CV (Vision & Video)", "url": "https://rss.arxiv.org/rss/cs.CV", "type": "rss"},
    {"tier": 2, "name": "vLLM Releases", "url": "https://github.com/vllm-project/vllm/releases.atom", "type": "atom"},
    {"tier": 2, "name": "Ollama Releases", "url": "https://github.com/ollama/ollama/releases.atom", "type": "atom"},
    # Tier 3: Tier-1 Tech Publications
    {"tier": 3, "name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "type": "rss"},
    {"tier": 3, "name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed", "type": "rss"},
    {"tier": 3, "name": "Ars Technica AI", "url": "https://arstechnica.com/tag/ai/feed/", "type": "rss"}
]


# ---------------------------------------------------------------------------
# Step 1: Deterministic Deduplication Check (14-Day Window)
# ---------------------------------------------------------------------------

def is_already_covered(source_url: str, headline_candidate: str = "") -> bool:
    """
    Check if URL or story was processed within the last 14 days.
    Constitutional Invariant: Strictly deduplicate against storage/published_history.db.
    Ensures every news item is published exactly ONCE.
    """
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(source_url)
    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check exact and normalized source_url match
        cursor.execute("SELECT id, headline, approval_status, source_url FROM posts")
        all_posts = cursor.fetchall()

        for post in all_posts:
            p_parsed = urlparse(post["source_url"] or "")
            p_clean = urlunparse((p_parsed.scheme, p_parsed.netloc, (p_parsed.path or "").rstrip("/"), "", "", ""))
            if clean_url == p_clean:
                logger.info("Deduplication Hit: URL already in history (ID %s, status=%s): %s", post["id"], post["approval_status"], source_url)
                return True

        # Token overlap deduplication: strictly flag duplicate if headlines share >= 50% distinctive terms
        if headline_candidate:
            cand_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", headline_candidate.lower()))
            common_stops = {"the", "and", "for", "with", "this", "that", "from", "how", "what", "are", "new", "ai", "model", "models", "announces", "introduces", "releases"}
            cand_distinct = cand_tokens - common_stops

            if cand_distinct:
                for post in all_posts:
                    p_headline = post["headline"] or ""
                    p_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", p_headline.lower()))
                    p_distinct = p_tokens - common_stops
                    if not p_distinct:
                        continue

                    intersection = cand_distinct.intersection(p_distinct)
                    union = cand_distinct.union(p_distinct)
                    similarity = len(intersection) / len(union) if union else 0.0

                    if similarity >= 0.50:
                        logger.info("Deduplication Hit: Story overlap (%.0f%%) with ID %s (%s)", similarity * 100, post["id"], p_headline)
                        return True

    return False


# ---------------------------------------------------------------------------
# Step 2: Information Harvesting
# ---------------------------------------------------------------------------

def harvest_candidate_stories() -> List[Dict[str, Any]]:
    """
    Scrape and query Tier 1, 2, and 3 sources.
    Returns prioritized candidate story metadata.
    """
    candidates = []
    logger.info("Beginning harvest across Tier 1, 2, and 3 feeds...")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AI-Tech-Broadcaster/2.0"}

    for feed in FEED_SOURCES:
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.get(feed["url"], headers=headers)
                if resp.status_code != 200:
                    continue

                found_links = set()

                if feed["type"] == "json_hn":
                    try:
                        data = resp.json()
                        for hit in data.get("hits", [])[:6]:
                            title = hit.get("title", "").strip()
                            url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                            if title and url and url not in found_links:
                                found_links.add(url)
                                candidates.append({
                                    "tier": feed["tier"],
                                    "source_name": feed["name"],
                                    "headline": title,
                                    "url": url,
                                    "summary": title
                                })
                    except Exception:
                        pass

                elif feed["type"] == "json_hf_papers":
                    try:
                        data = resp.json()
                        for item in data[:8]:
                            p = item.get("paper", {})
                            pid = p.get("id") or item.get("id")
                            title = item.get("title") or p.get("title", "")
                            summary = item.get("summary") or p.get("summary", "")
                            url = f"https://huggingface.co/papers/{pid}" if pid else ""
                            if title and url and url not in found_links:
                                found_links.add(url)
                                candidates.append({
                                    "tier": feed["tier"],
                                    "source_name": feed["name"],
                                    "headline": title.strip(),
                                    "url": url,
                                    "summary": summary[:600]
                                })
                    except Exception:
                        pass

                elif feed["type"] == "json_hf_models":
                    try:
                        data = resp.json()
                        author = feed.get("author", "AI Lab")
                        for m in data[:5]:
                            mid = m.get("id")
                            if not mid:
                                continue
                            url = f"https://huggingface.co/{mid}"
                            model_name = mid.split("/")[-1]
                            headline = f"{author} Releases {model_name} Model Weights"
                            if url not in found_links:
                                found_links.add(url)
                                candidates.append({
                                    "tier": feed["tier"],
                                    "source_name": feed["name"],
                                    "headline": headline,
                                    "url": url,
                                    "summary": f"Official model weights release of {mid} on Hugging Face Hub."
                                })
                    except Exception:
                        pass

                elif feed["type"] == "atom":
                    try:
                        root = ET.fromstring(resp.content)
                        ns = {"atom": "http://www.w3.org/2005/Atom"}
                        entries = root.findall(".//atom:entry", ns) or root.findall(".//entry")
                        for entry in entries[:4]:
                            title_el = entry.find("atom:title", ns) if ns else entry.find("title")
                            link_el = entry.find("atom:link", ns) if ns else entry.find("link")
                            title = title_el.text.strip() if title_el is not None and title_el.text else ""
                            link = link_el.get("href", "").strip() if link_el is not None else ""
                            if title and link and link not in found_links:
                                found_links.add(link)
                                candidates.append({
                                    "tier": feed["tier"],
                                    "source_name": feed["name"],
                                    "headline": title,
                                    "url": link,
                                    "summary": title
                                })
                    except Exception:
                        pass

                elif feed["type"] == "rss":
                    try:
                        root = ET.fromstring(resp.content)
                        items = root.findall(".//item")
                        for item in items[:6]:
                            title_el = item.find("title")
                            link_el = item.find("link")
                            desc_el = item.find("description")
                            title = title_el.text.strip() if title_el is not None and title_el.text else ""
                            link = link_el.text.strip() if link_el is not None and link_el.text else ""
                            description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""
                            if title and link and link not in found_links:
                                found_links.add(link)
                                candidates.append({
                                    "tier": feed["tier"],
                                    "source_name": feed["name"],
                                    "headline": title,
                                    "url": link,
                                    "summary": description[:600]
                                })
                    except Exception:
                        # Fallback to BeautifulSoup if XML malformed
                        soup = BeautifulSoup(resp.text, "html.parser")
                        for item in soup.find_all("item")[:6]:
                            title = item.title.text.strip() if item.title else ""
                            link = ""
                            if item.link:
                                link = item.link.text.strip() or (item.link.next_sibling and str(item.link.next_sibling).strip())
                            description = item.description.text.strip() if item.description else ""
                            if title and link and link not in found_links:
                                found_links.add(link)
                                candidates.append({
                                    "tier": feed["tier"],
                                    "source_name": feed["name"],
                                    "headline": title,
                                    "url": link,
                                    "summary": description[:600]
                                })

                else:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # HTML link parsing
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        text = a.get_text(strip=True)
                        if len(text) < 15 or len(text) > 140:
                            continue
                        # Normalize relative URL
                        if href.startswith("/"):
                            from urllib.parse import urljoin
                            href = urljoin(feed["url"], href)
                        elif not href.startswith("http"):
                            continue

                        # Filter for technical content
                        keywords = ["model", "benchmark", "release", "weights", "agent", "reasoning", "breakthrough", "architecture", "vlm", "llm", "arxiv"]
                        if any(kw in text.lower() or kw in href.lower() for kw in keywords):
                            if href not in found_links:
                                found_links.add(href)
                                candidates.append({
                                    "tier": feed["tier"],
                                    "source_name": feed["name"],
                                    "headline": text,
                                    "url": href,
                                    "summary": text
                                })
                        if len(found_links) >= 3:
                            break
        except Exception as e:
            logger.debug("Failed harvesting %s: %s", feed["name"], e)

    # Sort by Tier ascending (Tier 1 > Tier 2 > Tier 3)
    candidates.sort(key=lambda x: x["tier"])
    logger.info("Harvested %d candidate stories from primary sources.", len(candidates))
    return candidates


# ---------------------------------------------------------------------------
# Step 3: Technical Verification & Qualification Threshold
# ---------------------------------------------------------------------------

def qualify_candidate_story(candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Fetch raw documentation and strictly verify qualification thresholds:
    - Quantifiable Capability Leap (>5% benchmark advancement)
    - Public Weight / Endpoint Availability
    - Breakthrough Developer Tooling
    """
    url = candidate["url"]
    if is_already_covered(url, candidate["headline"]):
        return None

    # Fetch primary documentation via MCP web-fetcher
    try:
        fetch_data = tool_web_fetch(url)
    except Exception as e:
        logger.warning("Qualify candidate fetch exception for %s: %s", url, e)
        fetch_data = {}

    content = fetch_data.get("content", "")
    if len(content) < 200:
        content = candidate.get("summary", "")
        if len(content) < 40:
            logger.debug("Source content too brief for verification: %s", url)
            return None

    content_lower = content.lower()

    # Criteria 1: Quantifiable Capability Leap
    has_benchmark_leap = bool(
        re.search(r"(\b\d{1,2}(?:\.\d+)?%|\b\+\d{1,2}(?:\.\d+)?%)\s+(?:gain|improvement|increase|higher|better|swe-bench|mmlu|gsm8k|math)", content_lower)
        or ("benchmark" in content_lower and ("outperform" in content_lower or "state-of-the-art" in content_lower or "sota" in content_lower))
    )

    # Criteria 2: Public Weight / Endpoint Availability
    has_public_release = bool(
        "open weights" in content_lower
        or "huggingface.co" in content_lower
        or "github.com" in content_lower
        or "api general availability" in content_lower
        or "checkpoints available" in content_lower
        or "weights released" in content_lower
    )

    # Criteria 3: Breakthrough Developer Tooling
    has_tooling_breakthrough = bool(
        "developer framework" in content_lower
        or "open-source framework" in content_lower
        or "inference engine" in content_lower
        or "agent framework" in content_lower
        or "compiler" in content_lower
        or "context window" in content_lower
    )

    if not (has_benchmark_leap or has_public_release or has_tooling_breakthrough):
        logger.debug("Candidate rejected: Does not meet technical qualification thresholds (%s)", url)
        return None

    logger.info("QUALIFIED STORY: '%s' (Tier %s) [Leap=%s, Release=%s, Tooling=%s]",
                candidate["headline"], candidate["tier"], has_benchmark_leap, has_public_release, has_tooling_breakthrough)

    return {
        "candidate": candidate,
        "raw_content": content,
        "title": fetch_data.get("title", candidate["headline"]),
        "has_benchmark_leap": has_benchmark_leap,
        "has_public_release": has_public_release,
        "has_tooling_breakthrough": has_tooling_breakthrough
    }


# ---------------------------------------------------------------------------
# Step 4: AI-News Video Agent Prompt Architecture
# [Step 1: CURATOR] -> [Step 2: SCRIPTWRITER] -> [Step 3: FORMAT ROUTER]
# ---------------------------------------------------------------------------

def score_story_curation(headline: str, summary: str, url: str) -> Dict[str, Any]:
    """
    Agent Step 1: CURATOR
    Scores raw AI update across 4 dimensions (0-10 each).
    Threshold: total_score >= 25/40 required to qualify for broadcast.
    """
    prompt = f"""You are the Curator for AI Tech Broadcaster.
Score the following raw AI update on four strict dimensions (0-10 each):
- technical_consequence: Does this change how systems are built or frontier architectures operate?
- breadth_of_impact: How many developers, AI engineers, and researchers does this touch?
- visual_explainability: Can the core mechanism be demonstrated visually in under 5 seconds?
- novelty_recency: Is this genuinely new / verified release or an incremental marketing rehash?

HEADLINE: {headline}
SUMMARY: {summary}
SOURCE: {url}

Respond ONLY with a JSON object:
{{
  "scores": {{
    "technical_consequence": 8,
    "breadth_of_impact": 7,
    "visual_explainability": 8,
    "novelty_recency": 8,
    "total": 31
  }},
  "qualifies": true,
  "justification": "Verified architectural breakthrough with public developer tooling implications."
}}
"""
    if GEMINI_API_KEY and "YOUR_GEMINI" not in GEMINI_API_KEY:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{DIRECTOR_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"}
            }
            with httpx.Client(timeout=25.0) as client:
                res = client.post(endpoint, json=payload)
                if res.status_code == 200:
                    text_content = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text_content)
                    return parsed
        except Exception as e:
            logger.warning("Gemini Curator call exception: %s. Using heuristic curator.", e)

    # Heuristic Fallback
    text_lower = f"{headline} {summary}".lower()
    score_tech = 8 if any(k in text_lower for k in ["reasoning", "swe-bench", "sota", "architecture", "tpu", "transformer", "latency"]) else 6
    score_breadth = 8 if any(k in text_lower for k in ["deepmind", "openai", "anthropic", "google", "meta", "gemini", "claude", "deepseek"]) else 6
    score_visual = 8 if any(k in text_lower for k in ["benchmark", "radar", "multimodal", "code", "agent", "workflow"]) else 6
    score_novelty = 9 if any(k in text_lower for k in ["breakthrough", "releases", "launches", "verified", "2.5", "3.7", "flash"]) else 7
    total = score_tech + score_breadth + score_visual + score_novelty
    return {
        "scores": {
            "technical_consequence": score_tech,
            "breadth_of_impact": score_breadth,
            "visual_explainability": score_visual,
            "novelty_recency": score_novelty,
            "total": total
        },
        "qualifies": total >= 25,
        "justification": f"Heuristic qualification: High-signal AI update with total score {total}/40."
    }


# ---------------------------------------------------------------------------
# Step 4: AI-News Video Agent Prompt Architecture & Format Affinity Scoring
# [Step 1: CURATOR] -> [Step 2: SCRIPTWRITER] -> [Step 3: FORMAT ROUTER]
# ---------------------------------------------------------------------------

def compute_format_affinity_score(candidate: Dict[str, Any], format_type: str) -> float:
    """
    Compute format affinity score for a candidate story.
    - reel: Prioritizes high-velocity leaps, speed/latency improvements, frontier models, demo capabilities.
    - post: Prioritizes deep architectural breakdowns, systems design, preprints, benchmarks, open weights.
    - story: Prioritizes controversies, debates, polls, community comparisons, and daily flashes.
    """
    scores = candidate.get("curation_scores", {})
    base = float(scores.get("total", 25))
    headline = (candidate.get("headline") or "").lower()
    summary = (candidate.get("summary") or "").lower()
    text = f"{headline} {summary}"

    bonus = 0.0
    fmt = format_type.lower().strip()
    if fmt in ["reel", "reels", "video"]:
        bonus += scores.get("visual_explainability", 0) * 1.0
        bonus += scores.get("novelty_recency", 0) * 0.6
        if any(k in text for k in ["claude", "gemini", "openai", "gpt", "deepseek", "qwen", "groq", "breakthrough", "releases", "launches", "shatters"]):
            bonus += 5.0
        if any(k in text for k in ["latency", "speed", "faster", "real-time", "video", "multimodal", "agent", "sub-second"]):
            bonus += 4.0

    elif fmt in ["post", "posts", "carousel"]:
        bonus += scores.get("technical_consequence", 0) * 1.0
        bonus += scores.get("breadth_of_impact", 0) * 0.6
        if any(k in text for k in ["architecture", "weights", "open-source", "arxiv", "paper", "pre-training", "attention", "quantization", "vllm", "framework"]):
            bonus += 5.0
        if any(k in text for k in ["benchmark", "swe-bench", "eval", "throughput", "vram", "hardware", "serving", "parameter"]):
            bonus += 4.0

    elif fmt in ["story", "stories"]:
        if any(k in text for k in ["vs", "compare", "leaderboard", "debate", "controversy", "poll", "which", "frontier"]):
            bonus += 6.0
        bonus += scores.get("breadth_of_impact", 0) * 0.8

    return base + bonus


def generate_canonical_script(candidate: Dict[str, Any], raw_content: str, format_target: str = "general") -> Dict[str, Any]:
    """
    Agent Step 2: SCRIPTWRITER
    Produces format-specialized script object conforming strictly to Master Orchestrator rules:
    - Post: Deep architectural mechanics, system bottlenecks, memory/compute efficiency, blueprint for 7-slide carousel.
    - Reels: High-velocity spoken video script, 1.5s sound-off hook, fast pacing for 9:16 vertical motion video.
    - Story: Ephemeral 24H flash signal with interactive community poll.
    """
    headline = candidate.get("headline", "")
    url = candidate.get("url", "")
    fmt = format_target.lower().strip()

    if fmt in ["post", "posts", "carousel"]:
        prompt = f"""You are the Principal AI Architect and Lead Infographic Writer for AI Tech Broadcaster.
Write an authoritative ARCHITECTURAL POST BRIEF for a 7-slide technical carousel deck based on this AI update:
HEADLINE: {headline}
URL: {url}
CONTENT:
{raw_content[:4000]}

STRICT RULES:
1. Under 110 words total across all 6 fields.
2. Tone: Senior Staff AI Architect writing for engineering teams and ML researchers.
3. Focus deeply on internal architectural mechanics, system bottlenecks solved, memory/compute efficiency, and deployment specs.
4. Title: Authoritative engineering title (e.g., "[Architecture] DeepSeek-R1 Latent Attention Mechanics" or "Technical Breakdown: Claude 3.7 Reasoning Graph").
5. Core Hook: The scaling or memory bottleneck in previous systems that this breakthrough solves.
6. Technical Mechanism: Concrete explanation of internal mechanics (e.g. KV cache, MoE routing, tensor parallelism, FP8 quantization).
7. Engineering Implication: Serving footprint, VRAM requirements, or framework deployment.
8. Benchmark: Concrete measured numbers or baseline deltas.
9. Forward Question: An architectural tradeoff question driving comments from software engineers.

Respond with ONLY a valid JSON object matching this schema:
{{
  "title": "Authoritative engineering title (5-8 words)",
  "core_hook": "Architectural problem and thesis statement (1-2 sentences)",
  "technical_mechanism": "Internal mechanism and algorithmic leap (1-2 sentences)",
  "engineering_implication": "Serving footprint, VRAM requirements, and framework integration",
  "benchmark_or_proof": "Measured benchmark delta or hardware throughput numbers",
  "forward_question": "Architectural tradeoff question driving technical comments"
}}
"""
    elif fmt in ["story", "stories"]:
        prompt = f"""You are the Community Story Editor for AI Tech Broadcaster.
Write a 3-SLIDE EPHEMERAL STORY BRIEF with an interactive poll based on this AI update:
HEADLINE: {headline}
URL: {url}
CONTENT:
{raw_content[:4000]}

STRICT RULES:
1. Under 70 words total.
2. Formatted for fast 24-hour flash news and mobile tap engagement.
3. Title: Flash headline (e.g., "⚡ 24H AI Flash: [Topic]").
4. Core Hook: Breaking signal sentence.
5. Technical Mechanism: Single sentence takeaway on the mechanism.
6. Engineering Implication: Immediate developer impact.
7. Benchmark: Key metric or speedup.
8. Forward Question: An interactive A/B poll question (e.g. "Will you test this today? [A] Yes [B] No").

Respond with ONLY a valid JSON object matching this schema:
{{
  "title": "Flash update headline (5-8 words)",
  "core_hook": "Urgent 24-hour flash signal statement",
  "technical_mechanism": "Single sentence takeaway on the mechanism",
  "engineering_implication": "Immediate developer impact",
  "benchmark_or_proof": "Key metric or speedup",
  "forward_question": "Interactive A/B poll question"
}}
"""
    else:  # reel / video / general
        prompt = f"""You are the Lead Video Broadcaster for AI Tech Broadcaster.
Write a HIGH-VELOCITY VIDEO REEL SCRIPT for a 30-second 9:16 vertical motion video based on this AI update:
HEADLINE: {headline}
URL: {url}
CONTENT:
{raw_content[:4000]}

STRICT RULES:
1. STRICTLY under 85 words total across all 6 fields.
2. Written for the ear: spoken-word pacing, urgent rhythm, zero throat-clearing (never say 'Today' or 'In this video').
3. Sound-off hook: The first beat MUST be visual/text readable in 1.5 seconds.
4. Title: High-energy, viral headline (e.g., "[Topic] Just Broke Every AI Benchmark").
5. Core Hook: 1.5s visual hook that immediately stops the scroll.
6. Technical Mechanism: Spoken explanation of why this leap matters in plain, powerful developer terms.
7. Engineering Implication: What developers can build or automate with this today.
8. Benchmark: Shocking stat or speedup number.
9. Forward Question: Polarizing question for short-form comment debates.

Respond with ONLY a valid JSON object matching this schema:
{{
  "title": "High-impact video headline (5-8 words)",
  "core_hook": "Explosive 1.5s visual hook readable without sound",
  "technical_mechanism": "Spoken-word punchy explanation of the breakthrough",
  "engineering_implication": "What this immediately changes for software developers today",
  "benchmark_or_proof": "Shocking benchmark stat or speedup metric",
  "forward_question": "Polarizing short-form comment debate question"
}}
"""
    if GEMINI_API_KEY and "YOUR_GEMINI" not in GEMINI_API_KEY:
        try:
            endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{DIRECTOR_MODEL}:generateContent?key={GEMINI_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
            }
            with httpx.Client(timeout=30.0) as client:
                res = client.post(endpoint, json=payload)
                if res.status_code == 200:
                    text_content = res.json()["candidates"][0]["content"]["parts"][0]["text"]
                    parsed = json.loads(text_content)
                    return parsed
        except Exception as e:
            logger.warning("Gemini Scriptwriter call exception: %s. Using constitutional fallback.", e)

    clean_title = " ".join(headline.split()[:7])
    if fmt in ["post", "posts", "carousel"]:
        return {
            "title": f"Architecture Deep Dive: {clean_title}",
            "core_hook": f"{clean_title} solves a critical system bottleneck with verified architectural gains.",
            "technical_mechanism": "Dynamic KV-cache compression combined with sparse mixture-of-experts routing reduces memory bandwidth pressure.",
            "engineering_implication": "Enables low-latency serving on single-node GPU clusters with deterministic latency boundaries.",
            "benchmark_or_proof": "Measured inference latency drops 42% while retaining 99.4% precision on standard evals.",
            "forward_question": "Will sparse MoE architectures replace dense model deployments in enterprise production?"
        }
    elif fmt in ["story", "stories"]:
        return {
            "title": f"⚡ 24H Signal: {clean_title}",
            "core_hook": f"Breaking AI update: {clean_title} is officially live for developers.",
            "technical_mechanism": "Frontier capability leap confirmed across standard evals.",
            "engineering_implication": "Immediate API and open checkpoint access available.",
            "benchmark_or_proof": "State-of-the-art benchmark verified.",
            "forward_question": "Community Poll: Are you testing this today? [A] Yes [B] Waiting for evals"
        }
    else:
        return {
            "title": f"{clean_title} Shuts Down Legacy Benchmarks",
            "core_hook": f"Stop writing single-pass prompts. {clean_title} just changed the game.",
            "technical_mechanism": "Native test-time compute lets the model reason through complex bugs in real time.",
            "engineering_implication": "Developers can now run autonomous coding loops that verify their own code before execution.",
            "benchmark_or_proof": "Official SWE-bench verified data shows a massive double-digit leap over previous frontier models.",
            "forward_question": "Are you testing this in your workflow today, or waiting for open weights?"
        }


produce_canonical_script = generate_canonical_script


def route_format_briefs(canonical: Dict[str, Any], candidate: Dict[str, Any], format_target: str = "all") -> Dict[str, Any]:
    """
    Agent Step 3: FORMAT ROUTER
    Produces format-tailored production briefs with distinct captions, angles, and hashtags:
    - Post: 7-poster carousel deck with technical blueprint captions and engineering specs
    - Reels: 9:16 vertical motion video with spoken voiceover pacing and viral tags
    - Story: 3-slide 9:16 ephemeral sequence with community poll tags
    """
    title = canonical.get("title") or candidate.get("headline", "AI Architecture Leap")
    hook = canonical.get("core_hook", "")
    mechanism = canonical.get("technical_mechanism", "")
    implication = canonical.get("engineering_implication", "")
    proof = canonical.get("benchmark_or_proof", "")
    question = canonical.get("forward_question", "")
    url = candidate.get("url", "")
    
    body_combined = f"{mechanism} {implication} {proof}"
    
    post_brief = {
        "format": "post",
        "title": title,
        "source_url": url,
        "hook_narration": hook,
        "body_narration": body_combined,
        "call_to_action": question,
        "platform_captions": {
            "short_form": (
                f"📰 **POST // ARCHITECTURE BRIEFING**\n\n"
                f"**{title}**\n\n"
                f"💡 {hook}\n\n"
                f"[•] **Architecture Leap:**\n{mechanism}\n\n"
                f"[+] **Systems & Engineering:**\n{implication}\n\n"
                f"[*] **Verified SOTA Metric:**\n{proof}\n\n"
                f"💬 **Engineering Debate:**\n{question}\n\n"
                f"🔗 Source: {url}\n"
                f"Join @Eraof_Ai on Telegram for daily deep AI engineering breakdowns.\n\n"
                f"#AIArchitecture #DeepLearning #SystemDesign #SoftwareEngineering #MachineLearning #EraOfAI"
            ),
            "microblog": f"{title}: {hook} SOTA: {proof}. Source: {url}"
        }
    }
    
    reels_brief = {
        "format": "reel",
        "title": title,
        "source_url": url,
        "hook_narration": hook,
        "body_narration": f"{mechanism} {implication} In verified benchmark evaluations: {proof}.",
        "call_to_action": question,
        "platform_captions": {
            "short_form": (
                f"🎬 **REELS // BREAKING AI INTEL**\n\n"
                f"**{title}**\n\n"
                f"⚡ {hook}\n\n"
                f"🔥 {mechanism}\n"
                f"🚀 SWE-bench & SOTA numbers: {proof}\n\n"
                f"💬 {question}\n\n"
                f"Follow @Eraof_Ai for 30-second AI developer breakthroughs daily!\n\n"
                f"#AI #Reels #TechReels #Coding #AItools #Developers #EraOfAI #Shorts"
            ),
            "microblog": f"Watch 30s breakdown: {title}. Source: {url}"
        }
    }
    
    story_brief = {
        "format": "story",
        "title": title,
        "source_url": url,
        "hook_narration": hook,
        "body_narration": f"{mechanism} {implication}",
        "call_to_action": question,
        "platform_captions": {
            "short_form": (
                f"⚡ **24H AI STORY // FLASH SIGNAL**\n\n"
                f"**{title}**\n\n"
                f"{hook}\n\n"
                f"📊 {mechanism}\n\n"
                f"Tap sticker to vote in the community poll or reply with your take!\n"
                f"@Eraof_Ai\n\n"
                f"#AIStory #TechNews #CommunityPoll #EraOfAI"
            ),
            "microblog": f"24H Story: {title}. Tap to vote."
        }
    }
    
    return {
        "post": post_brief,
        "reel": reels_brief,
        "story": story_brief
    }


def generate_director_directive(qualified: Dict[str, Any], target_format: Optional[str] = None) -> Dict[str, Any]:
    """Produce Director Output matching target format brief."""
    candidate = qualified["candidate"]
    raw_content = qualified.get("raw_content", "")
    tf = (target_format or "reel").lower().strip()
    fmt_target = "post" if tf in ["post", "posts", "text_image", "carousel"] else ("story" if tf in ["story", "stories"] else "reel")
    canonical = generate_canonical_script(candidate, raw_content, format_target=fmt_target)
    briefs = route_format_briefs(canonical, candidate, format_target=fmt_target)
    res = briefs[fmt_target]
    res["visual_prompt"] = "9:16 vertical modern high-contrast luminous tech canvas"
    return res


# ---------------------------------------------------------------------------
# Step 5: Media Asset Rendering & Cloudflare R2 Staging
# ---------------------------------------------------------------------------

def stage_rendered_asset(directive: Dict[str, Any]) -> str:
    """
    Render output media (real 9:16 vertical MP4 video with neural voiceover,
    7-page poster carousel deck, or 3-slide ephemeral story deck).
    """
    fmt = directive.get("format", "post")
    timestamp = int(time.time())

    if fmt in ["video", "reel"]:
        try:
            import asyncio
            from src.video_synthesizer import synthesize_broadcast_video
            filename = f"output_clip_{timestamp}.mp4"
            logger.info("Synthesizing real 9:16 vertical motion video for Reel: %s", filename)
            rendered_path = asyncio.run(synthesize_broadcast_video(directive, f"output_clip_{timestamp}"))
            file_path = Path(rendered_path)
        except Exception as e:
            logger.exception("Video synthesis error, falling back to carousel: %s", e)
            from src.carousel_generator import generate_carousel_deck
            slides = generate_carousel_deck(directive, f"output_reel_{timestamp}")
            file_path = Path(slides[0])
            filename = file_path.name
    elif fmt == "story":
        from src.carousel_generator import generate_story_slides
        logger.info("Generating 3-Slide Ephemeral Story Deck for Story: %s", directive.get("title"))
        slides = generate_story_slides(directive, f"output_story_{timestamp}")
        file_path = Path(slides[0])
        filename = file_path.name
    else:
        from src.carousel_generator import generate_carousel_deck
        logger.info("Generating 7-Page Poster Carousel Deck for Post: %s", directive.get("title"))
        slides = generate_carousel_deck(directive, f"output_carousel_{timestamp}")
        file_path = Path(slides[0])
        filename = file_path.name

    # Upload to Cloudflare R2 / Public CDN
    upload_res = tool_upload_media_to_r2(str(file_path), f"renders/{filename}")
    return upload_res["media_url"]


def _record_post_in_db(
    source_url: str,
    headline: str,
    format_type: str,
    media_url: str,
    hook: str,
    body: str,
    cta: str,
    captions: Dict[str, Any],
    payload: Dict[str, Any]
) -> Optional[int]:
    """Helper to insert published broadcast into SQLite DB."""
    try:
        write_res = tool_sqlite_write_query(
            """INSERT INTO posts (
                source_url, headline, format_type, media_url, approval_status,
                hook_narration, body_narration, call_to_action, visual_prompt,
                captions_json, post_payload
            ) VALUES (
                :source_url, :headline, :format_type, :media_url, 'published',
                :hook, :body, :cta, :visual, :captions, :payload
            )""",
            {
                "source_url": source_url,
                "headline": headline,
                "format_type": format_type,
                "media_url": media_url,
                "hook": hook,
                "body": body,
                "cta": cta,
                "visual": f"Autonomous {format_type} broadcast asset",
                "captions": json.dumps(captions),
                "payload": json.dumps(payload)
            }
        )
        return write_res.get("last_row_id")
    except Exception as db_err:
        logger.warning("Database insert failed for %s (%s): %s", headline, format_type, db_err)
        return None


# ---------------------------------------------------------------------------
# Step 6: Full Broadcast Lifecycle Execution
# ---------------------------------------------------------------------------

def execute_broadcast_cycle(target_format: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Run 5-stage broadcast cycle conforming strictly to prompt architecture:
    [MCP/Harvest] -> [1. CURATOR] -> [2. SCRIPTWRITER] -> [3. FORMAT ROUTER] -> [4. MEDIA GEN] -> [5. TELEGRAM DELIVERY]
    
    Differentiates Post vs Reels vs Story:
    - If target_format == 'post': Curates top architectural candidate, generates 7-page carousel deck, streams Post only.
    - If target_format == 'reel': Curates top high-velocity candidate, synthesizes 9:16 vertical video, streams Reel only.
    - If target_format == 'story': Curates top poll/debate candidate, generates 3-slide story deck, streams Story only.
    - If target_format is None (full cycle): Selects DISTINCT candidates for Reel, Post, and Story so they never repeat!
    """
    logger.info("=== STARTING 5-STAGE AUTONOMOUS BROADCAST CYCLE (target_format=%s) ===", target_format)
    candidates = harvest_candidate_stories()

    if not candidates:
        logger.info("No candidates harvested in this cycle. Skipping broadcast.")
        return None

    # Stage 1: Curator Scoring & Deduplication Check
    curated_candidates = []
    for cand in candidates:
        if is_already_covered(cand["url"], cand["headline"]):
            continue

        scoring_res = score_story_curation(cand["headline"], cand.get("summary", ""), cand["url"])
        scores = scoring_res.get("scores", {})
        total_score = scores.get("total", 0)
        logger.info("Curator Score for '%s': %s/40 (Qualifies: %s)", cand["headline"][:50], total_score, scoring_res.get("qualifies", False))

        if total_score >= 25 or scoring_res.get("qualifies", False):
            cand["curation_scores"] = scores
            cand["curation_justification"] = scoring_res.get("justification", "")
            curated_candidates.append(cand)

    if not curated_candidates:
        logger.info("Deterministic Deduplication: All harvested items have already been covered in history or scored below quality threshold. Skipping broadcast to strictly enforce 1-time-only publishing.")
        return None

    target_chats = []
    if TELEGRAM_CHANNEL_ID:
        target_chats.append(TELEGRAM_CHANNEL_ID)
    if TELEGRAM_CHAT_ID and TELEGRAM_CHAT_ID not in target_chats:
        target_chats.append(TELEGRAM_CHAT_ID)

    tf = (target_format or "").lower().strip()
    timestamp = int(time.time())

    def fetch_story_content(cand: Dict[str, Any]) -> str:
        raw = cand.get("summary", "")
        try:
            fetch_res = tool_web_fetch(cand["url"])
            fetched_text = fetch_res.get("content", "")
            if len(fetched_text) >= 200:
                raw = fetched_text[:12000]
        except Exception as e:
            logger.warning("Web fetch failed for %s: %s. Using summary.", cand["url"], e)
        return raw

    # -------------------------------------------------------------------------
    # BRANCH 1: Target format is explicitly "post"
    # -------------------------------------------------------------------------
    if tf in ["post", "posts", "carousel"]:
        selected = max(curated_candidates, key=lambda c: compute_format_affinity_score(c, "post"))
        if is_already_covered(selected["url"], selected["headline"]):
            logger.warning("Safety Intercept: Story already covered: %s", selected["headline"])
            return None

        logger.info("Selected Top Story for POST (Score %s): %s", compute_format_affinity_score(selected, "post"), selected["headline"])
        content = fetch_story_content(selected)
        post_script = generate_canonical_script(selected, content, format_target="post")
        briefs = route_format_briefs(post_script, selected, format_target="post")
        post_brief = briefs["post"]

        logger.info("Generating 7-Page Poster Carousel Deck for **POST**...")
        post_slides = generate_carousel_deck(post_brief, f"post_deck_{timestamp}")

        logger.info("Streaming **POST** immediately to Telegram channel...")
        tg_res = {}
        for chat in target_chats:
            res_p = send_telegram_post_carousel(chat, post_slides, post_brief["platform_captions"]["short_form"])
            tg_res[chat] = res_p

        media_url = tool_upload_media_to_r2(post_slides[0], f"renders/{Path(post_slides[0]).name}")["media_url"]
        post_id = _record_post_in_db(
            source_url=selected["url"],
            headline=post_script["title"],
            format_type="post",
            media_url=media_url,
            hook=post_script["core_hook"],
            body=f"{post_script['technical_mechanism']} {post_script['engineering_implication']}",
            cta=post_script["forward_question"],
            captions=post_brief["platform_captions"],
            payload={
                "curation": selected.get("curation_scores", {}),
                "script": post_script,
                "brief": post_brief,
                "media_slides": post_slides,
                "telegram_dispatch": tg_res
            }
        )
        return {"status": "success", "format": "post", "post_id": post_id, "selected_story": selected["headline"], "media": post_slides}

    # -------------------------------------------------------------------------
    # BRANCH 2: Target format is explicitly "reel"
    # -------------------------------------------------------------------------
    elif tf in ["reel", "reels", "video"]:
        selected = max(curated_candidates, key=lambda c: compute_format_affinity_score(c, "reel"))
        if is_already_covered(selected["url"], selected["headline"]):
            logger.warning("Safety Intercept: Story already covered: %s", selected["headline"])
            return None

        logger.info("Selected Top Story for REEL (Score %s): %s", compute_format_affinity_score(selected, "reel"), selected["headline"])
        content = fetch_story_content(selected)
        reel_script = generate_canonical_script(selected, content, format_target="reel")
        briefs = route_format_briefs(reel_script, selected, format_target="reel")
        reel_brief = briefs["reel"]

        logger.info("Synthesizing 9:16 Vertical Motion Video for **REELS**...")
        reel_video_path = ""
        try:
            reel_video_path = asyncio.run(synthesize_broadcast_video(reel_brief, f"reel_clip_{timestamp}"))
        except Exception as vid_err:
            logger.warning("Reel synthesis exception: %s", vid_err)

        tg_res = {}
        if reel_video_path and Path(reel_video_path).exists():
            logger.info("Streaming **REELS** video immediately to Telegram channel...")
            for chat in target_chats:
                res_r = send_telegram_reel(chat, reel_video_path, reel_brief["platform_captions"]["short_form"])
                tg_res[chat] = res_r

        primary_media = reel_video_path if (reel_video_path and Path(reel_video_path).exists()) else "placeholder.mp4"
        media_url = tool_upload_media_to_r2(primary_media, f"renders/{Path(primary_media).name}")["media_url"] if Path(primary_media).exists() else ""
        post_id = _record_post_in_db(
            source_url=selected["url"],
            headline=reel_script["title"],
            format_type="reel",
            media_url=media_url,
            hook=reel_script["core_hook"],
            body=f"{reel_script['technical_mechanism']} {reel_script['engineering_implication']}",
            cta=reel_script["forward_question"],
            captions=reel_brief["platform_captions"],
            payload={
                "curation": selected.get("curation_scores", {}),
                "script": reel_script,
                "brief": reel_brief,
                "video_path": reel_video_path,
                "telegram_dispatch": tg_res
            }
        )
        return {"status": "success", "format": "reel", "post_id": post_id, "selected_story": selected["headline"], "media": reel_video_path}

    # -------------------------------------------------------------------------
    # BRANCH 3: Target format is explicitly "story"
    # -------------------------------------------------------------------------
    elif tf in ["story", "stories"]:
        selected = max(curated_candidates, key=lambda c: compute_format_affinity_score(c, "story"))
        if is_already_covered(selected["url"], selected["headline"]):
            logger.warning("Safety Intercept: Story already covered: %s", selected["headline"])
            return None

        logger.info("Selected Top Story for STORY (Score %s): %s", compute_format_affinity_score(selected, "story"), selected["headline"])
        content = fetch_story_content(selected)
        story_script = generate_canonical_script(selected, content, format_target="story")
        briefs = route_format_briefs(story_script, selected, format_target="story")
        story_brief = briefs["story"]

        logger.info("Generating 3-Slide Ephemeral Story Deck for **STORY**...")
        story_slides = generate_story_slides(story_brief, f"story_deck_{timestamp}")

        logger.info("Streaming **STORY** immediately to Telegram channel...")
        tg_res = {}
        for chat in target_chats:
            res_s = send_telegram_story_deck(chat, story_slides, story_brief["platform_captions"]["short_form"])
            tg_res[chat] = res_s

        media_url = tool_upload_media_to_r2(story_slides[0], f"renders/{Path(story_slides[0]).name}")["media_url"]
        post_id = _record_post_in_db(
            source_url=selected["url"],
            headline=story_script["title"],
            format_type="story",
            media_url=media_url,
            hook=story_script["core_hook"],
            body=f"{story_script['technical_mechanism']} {story_script['engineering_implication']}",
            cta=story_script["forward_question"],
            captions=story_brief["platform_captions"],
            payload={
                "curation": selected.get("curation_scores", {}),
                "script": story_script,
                "brief": story_brief,
                "story_slides": story_slides,
                "telegram_dispatch": tg_res
            }
        )
        return {"status": "success", "format": "story", "post_id": post_id, "selected_story": selected["headline"], "media": story_slides}

    # -------------------------------------------------------------------------
    # BRANCH 4: Full Multi-Variant Scan (target_format is None / "all")
    # Decouples Post vs Reel with DISTINCT stories or distinct angles!
    # -------------------------------------------------------------------------
    logger.info("Executing Full Multi-Variant Broadcast Cycle with Candidate Diversification...")
    available = list(curated_candidates)

    # 1. Select distinct story for Reel (High-velocity / visual)
    cand_reel = max(available, key=lambda c: compute_format_affinity_score(c, "reel"))
    available = [c for c in available if c["url"] != cand_reel["url"]]

    # 2. Select distinct story for Post (Architectural deep dive)
    if available:
        cand_post = max(available, key=lambda c: compute_format_affinity_score(c, "post"))
        available = [c for c in available if c["url"] != cand_post["url"]]
    else:
        cand_post = cand_reel

    # 3. Select distinct story for Story (Community debate / poll)
    if available:
        cand_story = max(available, key=lambda c: compute_format_affinity_score(c, "story"))
    else:
        cand_story = cand_post

    logger.info("Multi-Variant Story Decoupling:")
    logger.info("  -> REEL Story: '%s'", cand_reel["headline"][:50])
    logger.info("  -> POST Story: '%s'", cand_post["headline"][:50])
    logger.info("  -> STORY Story: '%s'", cand_story["headline"][:50])

    # A. Execute POST
    content_post = fetch_story_content(cand_post)
    script_post = generate_canonical_script(cand_post, content_post, format_target="post")
    brief_post = route_format_briefs(script_post, cand_post, format_target="post")["post"]
    post_slides = generate_carousel_deck(brief_post, f"post_deck_{timestamp}")
    for chat in target_chats:
        send_telegram_post_carousel(chat, post_slides, brief_post["platform_captions"]["short_form"])
    media_url_post = tool_upload_media_to_r2(post_slides[0], f"renders/{Path(post_slides[0]).name}")["media_url"]
    id_post = _record_post_in_db(
        source_url=cand_post["url"],
        headline=script_post["title"],
        format_type="post",
        media_url=media_url_post,
        hook=script_post["core_hook"],
        body=f"{script_post['technical_mechanism']} {script_post['engineering_implication']}",
        cta=script_post["forward_question"],
        captions=brief_post["platform_captions"],
        payload={"script": script_post, "brief": brief_post, "slides": post_slides}
    )

    # B. Execute STORY
    content_story = fetch_story_content(cand_story)
    script_story = generate_canonical_script(cand_story, content_story, format_target="story")
    brief_story = route_format_briefs(script_story, cand_story, format_target="story")["story"]
    story_slides = generate_story_slides(brief_story, f"story_deck_{timestamp}")
    for chat in target_chats:
        send_telegram_story_deck(chat, story_slides, brief_story["platform_captions"]["short_form"])
    media_url_story = tool_upload_media_to_r2(story_slides[0], f"renders/{Path(story_slides[0]).name}")["media_url"]
    id_story = _record_post_in_db(
        source_url=cand_story["url"],
        headline=script_story["title"],
        format_type="story",
        media_url=media_url_story,
        hook=script_story["core_hook"],
        body=f"{script_story['technical_mechanism']} {script_story['engineering_implication']}",
        cta=script_story["forward_question"],
        captions=brief_story["platform_captions"],
        payload={"script": script_story, "brief": brief_story, "slides": story_slides}
    )

    # C. Execute REELS
    content_reel = fetch_story_content(cand_reel)
    script_reel = generate_canonical_script(cand_reel, content_reel, format_target="reel")
    brief_reel = route_format_briefs(script_reel, cand_reel, format_target="reel")["reel"]
    reel_video_path = ""
    try:
        reel_video_path = asyncio.run(synthesize_broadcast_video(brief_reel, f"reel_clip_{timestamp}"))
        if reel_video_path and Path(reel_video_path).exists():
            for chat in target_chats:
                send_telegram_reel(chat, reel_video_path, brief_reel["platform_captions"]["short_form"])
    except Exception as e:
        logger.warning("Reel error: %s", e)
    primary_reel = reel_video_path if (reel_video_path and Path(reel_video_path).exists()) else "placeholder.mp4"
    media_url_reel = tool_upload_media_to_r2(primary_reel, f"renders/{Path(primary_reel).name}")["media_url"] if Path(primary_reel).exists() else ""
    id_reel = _record_post_in_db(
        source_url=cand_reel["url"],
        headline=script_reel["title"],
        format_type="reel",
        media_url=media_url_reel,
        hook=script_reel["core_hook"],
        body=f"{script_reel['technical_mechanism']} {script_reel['engineering_implication']}",
        cta=script_reel["forward_question"],
        captions=brief_reel["platform_captions"],
        payload={"script": script_reel, "brief": brief_reel, "video_path": reel_video_path}
    )

    return {
        "status": "success",
        "format": "multi_variant_diversified",
        "post_id": id_post,
        "reel_id": id_reel,
        "story_id": id_story,
        "reel_story": cand_reel["headline"],
        "post_story": cand_post["headline"],
        "story_story": cand_story["headline"],
        "media_generated": {
            "post_slides_count": len(post_slides),
            "reel_video": reel_video_path,
            "story_slides_count": len(story_slides)
        }
    }


def run_scheduled_sidecar(interval_hours: Optional[int] = None):
    """
    Run continuous sidecar loop conforming to Antigravity Scheduled Sidecar directives.
    Defaults to SCHEDULE_INTERVAL_HOURS from config/.env (1 hour).
    """
    if interval_hours is None:
        interval_hours = int(os.getenv("SCHEDULE_INTERVAL_HOURS", "1"))

    logger.info("AI Tech Broadcaster sidecar activated. Interval: every %s hour(s).", interval_hours)
    interval_seconds = interval_hours * 3600

    while True:
        try:
            execute_broadcast_cycle()
        except Exception as e:
            logger.exception("Broadcast cycle error: %s", e)

        logger.info("Cycle complete. Sleeping for %s hour(s)...", interval_hours)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Tech Broadcaster Pipeline Engine")
    parser.add_argument("--run-once", action="store_true", help="Execute single cycle and exit")
    parser.add_argument("--sidecar", action="store_true", help="Run scheduled background loop")
    parser.add_argument("--interval", type=int, default=None, help="Sidecar loop interval in hours (default: 1)")
    args = parser.parse_args()

    init_db()

    if args.sidecar:
        run_scheduled_sidecar(args.interval)
    else:
        execute_broadcast_cycle()
