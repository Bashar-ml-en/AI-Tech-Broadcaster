"""
Persona Manager for AI Tech Broadcaster
Provides detection, avatar chips, and executive stances for AI Tech Titans:
- Demis Hassabis (Google DeepMind / Gemini)
- Sundar Pichai (Google)
- Dario Amodei (Anthropic / Claude)
- Sam Altman (OpenAI / ChatGPT / Sora)
- Mark Zuckerberg & Yann LeCun (Meta AI / LLaMA)
- Liang Wenfeng (DeepSeek)
- Jensen Huang (NVIDIA / Hardware)
- Mustafa Suleyman (Microsoft AI)
- Elon Musk (xAI / Grok)
"""

from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parent.parent
PERSONAS_DIR = ROOT_DIR / "storage" / "assets" / "personas"

PERSONA_REGISTRY: Dict[str, Dict[str, Any]] = {
    "demis_hassabis": {
        "id": "demis_hassabis",
        "name": "Demis Hassabis",
        "title": "DeepMind CEO & Nobel Laureate",
        "lab": "Google DeepMind",
        "keywords": ["deepmind", "gemini", "hassabis", "alphafold", "alphageometry", "google ai"],
        "default_quote": "This architecture marks our most significant leap in real-time multimodal reasoning.",
        "avatar_file": "demis_hassabis.png",
        "accent_color": (99, 102, 241),
        "tag_bg": (238, 242, 255)
    },
    "sam_altman": {
        "id": "sam_altman",
        "name": "Sam Altman",
        "title": "OpenAI CEO",
        "lab": "OpenAI",
        "keywords": ["openai", "chatgpt", "altman", "gpt-4", "gpt-5", "sora", "o1", "o3", "operator"],
        "default_quote": "We believe compute scaling and test-time verification will fundamentally reshape intelligence.",
        "avatar_file": "sam_altman.png",
        "accent_color": (16, 185, 129),
        "tag_bg": (236, 253, 245)
    },
    "dario_amodei": {
        "id": "dario_amodei",
        "name": "Dario Amodei",
        "title": "Anthropic CEO",
        "lab": "Anthropic",
        "keywords": ["anthropic", "claude", "amodei", "constitutional ai", "artifacts", "computer use"],
        "default_quote": "Frontier models with agentic tool use are moving from passive chat to active engineering partners.",
        "avatar_file": "dario_amodei.png",
        "accent_color": (217, 119, 6),
        "tag_bg": (254, 243, 199)
    },
    "jensen_huang": {
        "id": "jensen_huang",
        "name": "Jensen Huang",
        "title": "NVIDIA CEO",
        "lab": "NVIDIA",
        "keywords": ["nvidia", "jensen", "huang", "blackwell", "hopper", "cuda", "gpu", "tensorrt"],
        "default_quote": "The entire computing stack is being reinvented from silicon to software in real time.",
        "avatar_file": "jensen_huang.png",
        "accent_color": (22, 163, 74),
        "tag_bg": (240, 253, 244)
    },
    "mark_zuckerberg": {
        "id": "mark_zuckerberg",
        "name": "Mark Zuckerberg",
        "title": "Meta CEO",
        "lab": "Meta AI",
        "keywords": ["meta", "llama", "zuckerberg", "open source ai", "pytorch", "meta ai"],
        "default_quote": "Open source AI will ensure that frontier intelligence is accessible to every developer globally.",
        "avatar_file": "mark_zuckerberg.png",
        "accent_color": (2, 132, 199),
        "tag_bg": (224, 242, 254)
    },
    "liang_wenfeng": {
        "id": "liang_wenfeng",
        "name": "Liang Wenfeng",
        "title": "DeepSeek Founder",
        "lab": "DeepSeek",
        "keywords": ["deepseek", "wenfeng", "r1", "v3", "dualpipe", "multi-head latent attention"],
        "default_quote": "Extreme architectural efficiency proves that world-class intelligence can run at a fraction of compute cost.",
        "avatar_file": "liang_wenfeng.png",
        "accent_color": (37, 99, 235),
        "tag_bg": (239, 246, 255)
    },
    "sundar_pichai": {
        "id": "sundar_pichai",
        "name": "Sundar Pichai",
        "title": "Google & Alphabet CEO",
        "lab": "Google",
        "keywords": ["google", "pichai", "alphabet", "tpu", "vertex ai"],
        "default_quote": "We are organizing the world's information with real-time multimodal intelligence at planet scale.",
        "avatar_file": "sundar_pichai.png",
        "accent_color": (220, 38, 38),
        "tag_bg": (254, 242, 242)
    },
    "default_titan": {
        "id": "default_titan",
        "name": "Frontier AI Lab",
        "title": "Executive AI Lead",
        "lab": "Era of AI Research",
        "keywords": [],
        "default_quote": "Verified engineering benchmarks confirm significant capability advancements across real-world workloads.",
        "avatar_file": "default_titan.png",
        "accent_color": (79, 70, 229),
        "tag_bg": (238, 242, 255)
    }
}


def detect_persona(text: str, context: str = "") -> Dict[str, Any]:
    """Detect matching AI Tech Titan persona from headline, context, or source text."""
    combined = f"{text} {context}".lower()
    matched = PERSONA_REGISTRY["default_titan"]
    for pid, data in PERSONA_REGISTRY.items():
        if pid == "default_titan":
            continue
        if any(kw in combined for kw in data["keywords"]):
            matched = data
            break
    res = dict(matched)
    res["role"] = res.get("role", res.get("title", "Executive AI Lead"))
    res["quote"] = res.get("quote", res.get("default_quote", ""))
    return res


def get_circular_avatar(key_or_filename: str, size: int = 54) -> Optional[Image.Image]:
    """Load and return circular cropped avatar image for the persona."""
    avatar_path = None
    if key_or_filename in PERSONA_REGISTRY:
        avatar_path = PERSONAS_DIR / PERSONA_REGISTRY[key_or_filename]["avatar_file"]
    elif (PERSONAS_DIR / key_or_filename).exists():
        avatar_path = PERSONAS_DIR / key_or_filename
    else:
        # Check if matches any data["avatar_file"]
        for data in PERSONA_REGISTRY.values():
            if data["avatar_file"] == key_or_filename:
                avatar_path = PERSONAS_DIR / data["avatar_file"]
                break

    if not avatar_path or not avatar_path.exists():
        avatar_path = PERSONAS_DIR / "default_titan.png"

    if avatar_path and avatar_path.exists():
        try:
            im = Image.open(avatar_path).convert("RGBA")
            im = im.resize((size, size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            d = ImageDraw.Draw(mask)
            d.ellipse([(0, 0), (size, size)], fill=255)
            out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            out.paste(im, (0, 0), mask=mask)
            return out
        except Exception:
            return None
    return None
