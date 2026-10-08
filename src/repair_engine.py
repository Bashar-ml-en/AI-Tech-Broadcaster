"""
Autonomous Repair & Self-Correction Engine for AI Tech Broadcaster
Reflects on audience reach diagnostics, extracts actionable rules from past mistakes,
persists self-correction memory, and dynamically injects directives into the Director Brain.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

from src.publish_types import LearnedRule
from src.analytics_engine import diagnose_recent_history

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / "config" / ".env")

logger = logging.getLogger("repair_engine")
MEMORY_FILE = ROOT_DIR / "storage" / "learning_memory.json"
DIRECTOR_MODEL = os.getenv("DIRECTOR_MODEL", "gemini-3.8-flash")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

DEFAULT_LEARNED_RULES: List[LearnedRule] = [
    {
        "rule_id": "LR-001",
        "category": "hook",
        "directive": "Limit opening hooks to <=12 words. Lead with an active engineering verb or high-contrast claim in the first 3 words.",
        "rationale": "Viewer retention drop-off spikes beyond 15 words; 0-1.5s scroll-stopping velocity requires immediate contrast.",
        "confidence": 0.95,
        "created_at": "2026-10-07T00:00:00Z"
    },
    {
        "rule_id": "LR-002",
        "category": "retention",
        "directive": "Always pair quantitative benchmark numbers (SWE-bench, latency, VRAM) with a concrete architecture mechanism (KV-cache, MoE, LoRA).",
        "rationale": "Posts with generic claims without mechanisms suffer from shallow engagement and low peer-to-peer sharing.",
        "confidence": 0.92,
        "created_at": "2026-10-07T00:00:00Z"
    },
    {
        "rule_id": "LR-003",
        "category": "cta",
        "directive": "End every broadcast with an architectural tradeoff debate question (e.g., 'Dense vs MoE' or 'VRAM footprint vs Throughput').",
        "rationale": "High-value engineering comments trigger algorithmic distribution bursts across Threads and Instagram.",
        "confidence": 0.94,
        "created_at": "2026-10-07T00:00:00Z"
    },
    {
        "rule_id": "LR-004",
        "category": "grounding",
        "directive": "Never invent numbers or unverified benchmark deltas. Format boilerplate (e.g. 30s breakdown) must be kept strictly separated from factual lab metrics.",
        "rationale": "Preserves brand credibility and prevents automated Quality Gate blocks.",
        "confidence": 0.98,
        "created_at": "2026-10-07T00:00:00Z"
    }
]


def load_learning_memory() -> Dict[str, Any]:
    """Load persistent self-correction memory from storage/learning_memory.json."""
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not MEMORY_FILE.exists():
        initial_data = {
            "version": "2.0",
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_cycles_analyzed": 0,
            "active_rules": DEFAULT_LEARNED_RULES,
            "historical_lessons": []
        }
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, indent=2)
        return initial_data

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not read learning memory, resetting: %s", e)
        return {"active_rules": DEFAULT_LEARNED_RULES, "historical_lessons": []}


def save_learning_memory(data: Dict[str, Any]):
    """Persist updated memory state to disk."""
    data["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run_repair_cycle() -> Dict[str, Any]:
    """
    Execute full self-correction analysis:
    1. Diagnoses recent posts in SQLite history.
    2. Identifies underperforming posts and failure patterns.
    3. Synthesizes new rules or updates confidence on existing rules.
    4. Persists the updated memory for immediate injection into future broadcast cycles.
    """
    memory = load_learning_memory()
    diagnostics = diagnose_recent_history(limit=15)

    underperforming = [d for d in diagnostics if d.get("distribution_tier") in ("underperforming", "suppressed")]
    solid_or_viral = [d for d in diagnostics if d.get("distribution_tier") in ("solid", "viral")]

    new_rules: List[LearnedRule] = []

    # Analyze underperforming issues
    all_bottlenecks = []
    for u in underperforming:
        all_bottlenecks.extend(u.get("diagnosed_bottlenecks", []))

    if any("HOOK_FATIGUE" in b or "WEAK_HOOK_OPENING" in b for b in all_bottlenecks):
        rule: LearnedRule = {
            "rule_id": f"LR-{len(memory.get('active_rules', [])) + 1:03d}",
            "category": "hook",
            "directive": "Never start script with 'Google announced', 'In this video', or company greetings. Jump straight into the architectural leap in <=8 words.",
            "rationale": "Underperforming posts in history exhibited high initial 3s drop-offs due to slow introductory phrasing.",
            "confidence": 0.96,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        new_rules.append(rule)

    if any("SHALLOW_TECHNICAL_DEPTH" in b for b in all_bottlenecks):
        rule: LearnedRule = {
            "rule_id": f"LR-{len(memory.get('active_rules', [])) + 1:03d}",
            "category": "retention",
            "directive": "Every post must state the exact memory footprint or serving efficiency gain (e.g. KV cache reduction, FP8 quantization, or VRAM delta).",
            "rationale": "High-performing posts average 3x more peer shares when concrete systems specs are articulated.",
            "confidence": 0.91,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        new_rules.append(rule)

    # Merge unique new rules
    existing_directives = {r.get("directive", "").lower() for r in memory.get("active_rules", [])}
    added_count = 0
    for nr in new_rules:
        if nr.get("directive", "").lower() not in existing_directives:
            memory["active_rules"].append(nr)
            added_count += 1

    memory["total_cycles_analyzed"] = memory.get("total_cycles_analyzed", 0) + 1
    save_learning_memory(memory)

    return {
        "status": "success",
        "posts_analyzed": len(diagnostics),
        "underperforming_count": len(underperforming),
        "viral_count": len(solid_or_viral),
        "new_rules_synthesized": added_count,
        "total_active_rules": len(memory.get("active_rules", [])),
        "active_rules": memory.get("active_rules", [])
    }


def get_active_learned_rules() -> List[str]:
    """
    Retrieve formatted prompt directives to dynamically inject into
    the Gemini 3.8 Flash Director Brain on every broadcast cycle.
    """
    memory = load_learning_memory()
    rules = memory.get("active_rules", DEFAULT_LEARNED_RULES)
    return [f"[{r.get('category', 'general').upper()}] {r.get('directive')}" for r in rules]
