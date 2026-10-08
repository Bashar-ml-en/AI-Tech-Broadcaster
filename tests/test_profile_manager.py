"""
Tests for Social Media Profile & Bio Optimization Engine.
"""

from src.profile_manager import generate_optimized_profiles, apply_profile_updates


def test_generate_optimized_profiles():
    profiles = generate_optimized_profiles(brand_name="Era of AI", niche="AI Architecture")
    assert "telegram" in profiles
    assert "instagram" in profiles
    assert "threads" in profiles
    assert "facebook" in profiles
    assert "tiktok" in profiles

    # Check Instagram constraints
    ig = profiles["instagram"]
    assert len(ig.get("bio", "")) <= 180
    assert "Era of AI" in ig.get("name_field", "") or "Era of AI" in str(profiles)

    # Check Telegram constraints
    tg = profiles["telegram"]
    assert len(tg.get("title", "")) <= 64
    assert len(tg.get("description", "")) <= 300


def test_apply_profile_updates_dry_run():
    res = apply_profile_updates(platform="all", dry_run=True)
    assert "telegram" in res
    assert "facebook" in res
    assert "instagram" in res
    assert res["telegram"]["status"] == "simulated"
    assert res["facebook"]["status"] == "simulated"
    assert res["instagram"]["status"] == "ready_for_copy_paste"
