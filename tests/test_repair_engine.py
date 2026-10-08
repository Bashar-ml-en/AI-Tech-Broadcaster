"""
Tests for Reach Analytics and Autonomous Repair Engine.
"""

from src.analytics_engine import diagnose_post_reach
from src.repair_engine import run_repair_cycle, get_active_learned_rules, load_learning_memory


def test_diagnose_post_reach():
    mock_post = {
        "id": 9999,
        "format_type": "reel",
        "headline": "Gemini 2.5 Flash Architecture",
        "hook_narration": "In this video today we are looking at Gemini models.",  # Weak opening
        "body_narration": "Performance was tested on benchmark.",  # Shallow
        "call_to_action": "Let us know.",  # Missing ?
        "captions_json": "{}"
    }
    diag = diagnose_post_reach(mock_post)
    assert diag["post_id"] == 9999
    assert diag["distribution_tier"] in ("underperforming", "suppressed")
    assert any("WEAK_HOOK_OPENING" in b for b in diag["diagnosed_bottlenecks"])
    assert any("CTA_ABSENT" in b for b in diag["diagnosed_bottlenecks"])
    assert len(diag["improvement_recommendations"]) > 0


def test_run_repair_cycle():
    cycle_res = run_repair_cycle()
    assert cycle_res["status"] == "success"
    assert cycle_res["total_active_rules"] >= 4

    rules = get_active_learned_rules()
    assert len(rules) >= 4
    assert any("[HOOK]" in r for r in rules)
    assert any("[CTA]" in r for r in rules)
