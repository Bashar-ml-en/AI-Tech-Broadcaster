import pytest
from pathlib import Path
from src.persona_manager import detect_persona, PERSONA_REGISTRY, get_persona_stage_background
from src.presenter_engine import FULLBODY_DIR

def test_persona_routing_accuracy():
    cases = [
        ("OpenAI Unveils GPT-5 Frontier Model", "https://openai.com/blog", "sam_altman"),
        ("NVIDIA Blackwell Ultra AI Clusters Ship Worldwide", "https://nvidianews.nvidia.com", "jensen_huang"),
        ("Meta Releases Llama 4 Open Source Weights", "https://about.fb.com", "mark_zuckerberg"),
        ("xAI Grok 3 Reasoning Engine Outperforms SOTA", "https://x.ai/news", "elon_musk"),
        ("Anthropic Claude 3.7 Sonnet Multi-Agent Reasoning", "https://anthropic.com/news", "dario_amodei"),
        ("Microsoft Copilot Studio Deep Azure Integration", "https://blogs.microsoft.com", "satya_nadella"),
        ("DeepSeek R1 Open Weights Reasoning Breakthrough", "https://deepseek.com", "liang_wenfeng"),
        ("Google DeepMind AlphaProof Solves Olympiad Geometry", "https://deepmind.google", "demis_hassabis"),
        ("Google I/O 2026 Keynote Sundar Pichai Announces Gemini 3.0", "https://blog.google", "sundar_pichai"),
    ]
    for headline, url, expected_ceo in cases:
        p = detect_persona(headline, url)
        assert p["id"] == expected_ceo, f"Failed for '{headline}': got {p['id']}, expected {expected_ceo}"

def test_general_ai_news_diversification():
    # Verify that general AI headlines without explicit brand mentions don't all default to sundar_pichai
    headlines = [
        "Autonomous AI Coding Agents Revolutionize Software Engineering",
        "Next-Generation Semiconductor Packaging Overcomes Thermal Scaling",
        "Open-Weights Multimodal Foundations Challenge Proprietary Paradigms",
        "Reinforcement Learning with Verifiable Rewards Breaks Reasoning Bottleneck",
        "Enterprise Multi-Agent Orchestration Slashes Workflow Latency by 70%",
        "Quantum-Classical Hybrid Computing Demonstrates Real-Time Error Mitigation",
    ]
    assigned_ceos = {detect_persona(h, "")["id"] for h in headlines}
    assert len(assigned_ceos) > 1, f"Expected diversified hosts, but all mapped to: {assigned_ceos}"

def test_all_ceos_have_dedicated_stage_plates():
    for ceo_id in PERSONA_REGISTRY:
        if ceo_id == "default_titan":
            continue
        center_plate = FULLBODY_DIR / f"{ceo_id}_stage_center.jpg"
        pointing_plate = FULLBODY_DIR / f"{ceo_id}_stage_pointing.jpg"
        assert center_plate.exists(), f"Missing center plate for {ceo_id}: {center_plate}"
        assert pointing_plate.exists(), f"Missing pointing plate for {ceo_id}: {pointing_plate}"
        assert center_plate.stat().st_size > 10000, f"Center plate for {ceo_id} is too small"
        assert pointing_plate.stat().st_size > 10000, f"Pointing plate for {ceo_id} is too small"
