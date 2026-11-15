"""
Swarm Coordinator & Specialized Agents for AI Tech Broadcaster
Implements decoupled agent roles for harvesting, editorial scripting, synthesis, QA, and dispatch.
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from src.agents.base_agent import BaseAgent

logger = logging.getLogger("swarm_coordinator")


class IngestionAgent(BaseAgent):
    """Responsible for monitoring feeds and scraping fresh AI announcements."""

    def __init__(self):
        super().__init__(name="IngestionAgent", role="AI Intelligence Harvester")

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from src.pipeline import harvest_candidate_stories
        candidates = harvest_candidate_stories()
        return {
            "candidate_count": len(candidates),
            "candidates": candidates,
        }


class EditorialAgent(BaseAgent):
    """Responsible for CEO persona matching, narrative structuring, and semantic deduplication."""

    def __init__(self):
        super().__init__(name="EditorialAgent", role="Executive Scriptwriter & Deduplicator")

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from src.pipeline import (
            curate_and_rank_stories,
            generate_canonical_script,
            route_format_briefs,
            fetch_story_content,
        )
        from src.semantic_memory import SemanticMemoryEngine

        candidates = payload.get("candidates", [])
        target_format = payload.get("target_format", "reel")
        curated = curate_and_rank_stories(candidates)

        if not curated:
            return {"selected_story": None, "reason": "No qualified stories after curation"}

        sem_engine = SemanticMemoryEngine()
        selected = None

        for cand in curated:
            headline = cand.get("headline", "")
            collided, match = sem_engine.check_semantic_collision(headline)
            if not collided:
                selected = cand
                break
            else:
                logger.info("[EditorialAgent] Skipping duplicate candidate '%s' (collided with #%s)", headline[:40], match.get("matched_post_id"))

        if not selected:
            selected = curated[0]  # Fallback to top story if all had soft collisions

        content = fetch_story_content(selected)
        script = generate_canonical_script(selected, content, format_target=target_format)
        briefs = route_format_briefs(script, selected, format_target=target_format)
        brief = briefs.get(target_format) or briefs.get("reel")

        # Assign rotating aesthetic theme style
        hl_lower = (selected.get("headline") or "").lower()
        if any(k in hl_lower for k in ("weights", "open source", "github", "release", "model", "llama", "deepseek", "qwen", "code")):
            style = "cyberpunk"
        elif any(k in hl_lower for k in ("benchmark", "paper", "arxiv", "evaluation", "score", "reasoning", "swe-bench")):
            style = "minimalist"
        elif any(k in hl_lower for k in ("antitrust", "lawsuit", "regulation", "acquisition", "billion", "revenue", "policy", "scandal")):
            style = "news_desk"
        else:
            style = "keynote"

        if brief and isinstance(brief, dict):
            brief["style"] = style

        return {
            "selected_story": selected,
            "script": script,
            "brief": brief,
            "content": content,
            "style": style,
        }


class QualityAuditorAgent(BaseAgent):
    """Responsible for 8-point pre-flight quality gate and multimodal visual frame inspection."""

    def __init__(self):
        super().__init__(name="QualityAuditorAgent", role="Pre-Flight & Visual Gate Auditor")

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from src.quality_gate import evaluate
        from src.publish_types import MediaRef

        post_record = payload.get("post_record", {})
        source_text = payload.get("source_text", "")
        media_refs = payload.get("media_refs", [])
        format_type = payload.get("format_type", "reel")

        eval_result = evaluate(
            post_record=post_record,
            source_text=source_text,
            media_refs=media_refs,
            format_type=format_type,
        )

        return {
            "passed": eval_result.get("passed", False),
            "composite_score": eval_result.get("composite_score", 0.0),
            "failed_checks": eval_result.get("failed_checks", []),
            "eval_result": eval_result,
        }


class DistributionAgent(BaseAgent):
    """Responsible for omnichannel publishing, rate limits, and delivery receipts."""

    def __init__(self):
        super().__init__(name="DistributionAgent", role="Omnichannel Dispatcher")

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from src.dispatcher import dispatch_broadcast
        post_record = payload.get("post_record", {})
        media_refs = payload.get("media_refs", [])
        target_chats = payload.get("target_chats")

        dispatch_res = dispatch_broadcast(
            post_record=post_record,
            media_refs=media_refs,
            target_chats=target_chats,
        )

        return {
            "dispatch_result": dispatch_res,
        }


class SwarmCoordinator:
    """Orchestrates multi-agent execution pipeline across specialized agents."""

    def __init__(self):
        self.ingestion_agent = IngestionAgent()
        self.editorial_agent = EditorialAgent()
        self.quality_agent = QualityAuditorAgent()
        self.distribution_agent = DistributionAgent()

    def get_swarm_status(self) -> Dict[str, Any]:
        """Collect status telemetry across all swarm agents."""
        return {
            "ingestion": self.ingestion_agent.get_status(),
            "editorial": self.editorial_agent.get_status(),
            "quality": self.quality_agent.get_status(),
            "distribution": self.distribution_agent.get_status(),
        }
