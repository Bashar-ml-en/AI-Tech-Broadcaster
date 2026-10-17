"""
Executive Persona & CEO Character Manager for AI Tech Broadcaster
Maps every AI lab/company update to its CEO/Founder character, high-resolution studio portrait,
first-person keynote greeting, and custom vocal timbre/accent profile:
- Sundar Pichai (Google & Alphabet CEO)
- Demis Hassabis (Google DeepMind CEO & Nobel Laureate)
- Sam Altman (OpenAI CEO)
- Jensen Huang (NVIDIA President & CEO)
- Dario Amodei (Anthropic CEO)
- Mark Zuckerberg (Meta Founder & CEO)
- Liang Wenfeng (DeepSeek Founder & CEO)
- Elon Musk (xAI Founder & CEO)
- Satya Nadella (Microsoft Chairman & CEO)
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "storage" / "assets"
PERSONAS_DIR = ASSETS_DIR / "personas"
PORTRAITS_DIR = PERSONAS_DIR / "portraits"
STAGES_DIR = ASSETS_DIR / "stages"
PERSONAS_DIR.mkdir(parents=True, exist_ok=True)
PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
STAGES_DIR.mkdir(parents=True, exist_ok=True)

PERSONA_REGISTRY: Dict[str, Dict[str, Any]] = {
    "sundar_pichai": {
        "id": "sundar_pichai",
        "name": "Sundar Pichai",
        "title": "CEO, Google & Alphabet",
        "lab": "Google",
        "keywords": [
            "google", "gemini", "pichai", "alphabet", "tpu", "vertex ai",
            "android", "notebooklm", "google cloud", "gemma", "veo", "imagen",
            "antigravity", "workspace"
        ],
        "intro_greeting": "Hi everyone, Sundar Pichai here at Google.",
        "default_quote": "We are making Gemini and our AI infrastructure faster, more capable, and accessible to every developer globally.",
        "avatar_file": "sundar_pichai.png",
        "portrait_file": "sundar_pichai.jpg",
        "stage_bg_file": "google_stage.jpg",
        "accent_color": (66, 133, 244),       # Google Blue
        "secondary_color": (234, 67, 53),     # Google Red
        "glow_color": (52, 168, 83),          # Google Green
        "tag_bg": (232, 240, 254),
        "mouth_box_ratio": (0.37, 0.56, 0.63, 0.72),  # (x0, y0, x1, y1) relative to cropped portrait
        "voice_profile": {
            "accent_tld": "en-IN",
            "edge_voice": "en-IN-PrabhatNeural",
            "pitch_factor": 0.96,             # Warm measured Indian-American baritone
            "tempo": 1.04,
            "eq_filter": "equalizer=f=220:width_type=o:width=1.5:g=3.5,equalizer=f=3200:width_type=o:width=1.2:g=2.5",
            "gemini_voice_design": (
                "Calm, articulate, warm Indian-American male technology CEO voice in his early 50s, "
                "measured keynote cadence, thoughtful emphasis, studio lapel microphone clarity."
            ),
        },
    },
    "demis_hassabis": {
        "id": "demis_hassabis",
        "name": "Demis Hassabis",
        "title": "CEO, Google DeepMind",
        "lab": "Google DeepMind",
        "keywords": [
            "deepmind", "hassabis", "alphafold", "alphageometry", "alphagenome",
            "alphaproof", "alphadev", "sim-to-real", "nature paper"
        ],
        "intro_greeting": "Hello everyone, Demis Hassabis here from Google DeepMind.",
        "default_quote": "This architecture marks our most significant leap in scientific discovery and real-time multimodal reasoning.",
        "avatar_file": "demis_hassabis.png",
        "portrait_file": "demis_hassabis.jpg",
        "stage_bg_file": "google_stage.jpg",
        "accent_color": (99, 102, 241),       # DeepMind Indigo
        "secondary_color": (14, 165, 233),    # Cyan
        "glow_color": (129, 140, 248),
        "tag_bg": (238, 242, 255),
        "mouth_box_ratio": (0.36, 0.56, 0.64, 0.72),
        "voice_profile": {
            "accent_tld": "en-GB",
            "edge_voice": "en-GB-RyanNeural",
            "pitch_factor": 0.97,             # Articulate British baritone
            "tempo": 1.06,
            "eq_filter": "equalizer=f=240:width_type=o:width=1.4:g=3.0,equalizer=f=3800:width_type=o:width=1.2:g=3.0",
            "gemini_voice_design": (
                "Articulate British male AI scientist and CEO voice, brisk intellectual cadence, "
                "clear London accent, warm scientific authority."
            ),
        },
    },
    "sam_altman": {
        "id": "sam_altman",
        "name": "Sam Altman",
        "title": "CEO, OpenAI",
        "lab": "OpenAI",
        "keywords": [
            "openai", "chatgpt", "altman", "gpt-4", "gpt-5", "sora",
            "o1", "o3", "o4", "operator", "codex", "ironclad"
        ],
        "intro_greeting": "Hey everyone, Sam Altman here from OpenAI.",
        "default_quote": "We believe test-time compute scaling and autonomous reasoning agents will fundamentally reshape software engineering.",
        "avatar_file": "sam_altman.png",
        "portrait_file": "sam_altman.jpg",
        "stage_bg_file": "openai_stage.jpg",
        "accent_color": (16, 185, 129),       # OpenAI Emerald
        "secondary_color": (6, 182, 212),
        "glow_color": (52, 211, 153),
        "tag_bg": (236, 253, 245),
        "mouth_box_ratio": (0.37, 0.55, 0.63, 0.71),
        "voice_profile": {
            "accent_tld": "en-US",
            "edge_voice": "en-US-RogerNeural",
            "pitch_factor": 1.03,             # Silicon Valley tenor
            "tempo": 1.07,
            "eq_filter": "equalizer=f=280:width_type=o:width=1.3:g=2.0,equalizer=f=4200:width_type=o:width=1.2:g=3.5",
            "gemini_voice_design": (
                "Young Silicon Valley male tech founder voice in his late 30s, crisp tenor pitch, "
                "conversational, direct, fast-paced keynote delivery."
            ),
        },
    },
    "jensen_huang": {
        "id": "jensen_huang",
        "name": "Jensen Huang",
        "title": "Founder & CEO, NVIDIA",
        "lab": "NVIDIA",
        "keywords": [
            "nvidia", "jensen", "huang", "blackwell", "hopper", "rubin",
            "cuda", "gpu", "tensorrt", "nvlink", "dgx", "nemotron", "megatron"
        ],
        "intro_greeting": "Hello everyone, Jensen Huang here at NVIDIA.",
        "default_quote": "The entire computing stack is being reinvented from silicon to autonomous AI factories in real time.",
        "avatar_file": "jensen_huang.png",
        "portrait_file": "jensen_huang.jpg",
        "stage_bg_file": "nvidia_stage.jpg",
        "accent_color": (118, 185, 0),        # NVIDIA Green
        "secondary_color": (16, 185, 129),
        "glow_color": (163, 230, 53),
        "tag_bg": (240, 253, 244),
        "mouth_box_ratio": (0.37, 0.56, 0.63, 0.72),
        "voice_profile": {
            "accent_tld": "en-US",
            "edge_voice": "en-US-GuyNeural",
            "pitch_factor": 0.94,             # Energetic resonant keynote baritone
            "tempo": 1.05,
            "eq_filter": "equalizer=f=190:width_type=o:width=1.5:g=4.5,equalizer=f=3500:width_type=o:width=1.2:g=3.0",
            "gemini_voice_design": (
                "Charismatic, energetic Taiwanese-American male tech CEO voice in his 60s, "
                "warm resonant baritone, dramatic stadium keynote emphasis."
            ),
        },
    },
    "dario_amodei": {
        "id": "dario_amodei",
        "name": "Dario Amodei",
        "title": "CEO, Anthropic",
        "lab": "Anthropic",
        "keywords": [
            "anthropic", "claude", "amodei", "constitutional ai",
            "sonnet", "opus", "haiku", "mcp", "model context protocol"
        ],
        "intro_greeting": "Hi everyone, Dario Amodei here at Anthropic.",
        "default_quote": "Frontier models with verifiable alignment and agentic tool use are transforming how engineers build reliable systems.",
        "avatar_file": "dario_amodei.png",
        "portrait_file": "dario_amodei.jpg",
        "stage_bg_file": "anthropic_stage.jpg",
        "accent_color": (217, 119, 6),        # Anthropic Amber
        "secondary_color": (245, 158, 11),
        "glow_color": (251, 191, 36),
        "tag_bg": (254, 243, 199),
        "mouth_box_ratio": (0.37, 0.56, 0.63, 0.72),
        "voice_profile": {
            "accent_tld": "en-US",
            "edge_voice": "en-US-ChristopherNeural",
            "pitch_factor": 0.98,
            "tempo": 1.06,
            "eq_filter": "equalizer=f=230:width_type=o:width=1.4:g=3.0,equalizer=f=3400:width_type=o:width=1.2:g=2.5",
            "gemini_voice_design": (
                "Thoughtful, analytical American male AI research CEO voice, precise technical cadence, "
                "warm and trustworthy studio tone."
            ),
        },
    },
    "mark_zuckerberg": {
        "id": "mark_zuckerberg",
        "name": "Mark Zuckerberg",
        "title": "Founder & CEO, Meta",
        "lab": "Meta AI",
        "keywords": [
            "meta", "llama", "zuckerberg", "open source ai", "pytorch",
            "meta ai", "fair", "ray-ban", "orion"
        ],
        "intro_greeting": "Hey everyone, Mark Zuckerberg here at Meta.",
        "default_quote": "Open source frontier AI ensures that every developer and company can build and own their intelligence stack.",
        "avatar_file": "mark_zuckerberg.png",
        "portrait_file": "mark_zuckerberg.jpg",
        "stage_bg_file": "meta_stage.jpg",
        "accent_color": (2, 132, 199),        # Meta Blue
        "secondary_color": (56, 189, 248),
        "glow_color": (14, 165, 233),
        "tag_bg": (224, 242, 254),
        "mouth_box_ratio": (0.37, 0.55, 0.63, 0.71),
        "voice_profile": {
            "accent_tld": "en-US",
            "edge_voice": "en-US-EricNeural",
            "pitch_factor": 1.02,
            "tempo": 1.08,
            "eq_filter": "equalizer=f=260:width_type=o:width=1.4:g=2.5,equalizer=f=4000:width_type=o:width=1.2:g=3.0",
            "gemini_voice_design": (
                "Direct, fast-paced American male tech CEO voice in his early 40s, clear mid-tenor, "
                "product keynote energy."
            ),
        },
    },
    "liang_wenfeng": {
        "id": "liang_wenfeng",
        "name": "Liang Wenfeng",
        "title": "Founder & CEO, DeepSeek",
        "lab": "DeepSeek",
        "keywords": [
            "deepseek", "wenfeng", "r1", "v3", "v4", "dualpipe",
            "multi-head latent attention", "mla", "qwen", "open-weights"
        ],
        "intro_greeting": "Hello everyone, Liang Wenfeng here from DeepSeek.",
        "default_quote": "Extreme architectural efficiency proves that frontier reasoning models can run openly at a fraction of legacy compute cost.",
        "avatar_file": "liang_wenfeng.png",
        "portrait_file": "liang_wenfeng.jpg",
        "stage_bg_file": "deepseek_stage.jpg",
        "accent_color": (37, 99, 235),        # DeepSeek Royal Blue
        "secondary_color": (6, 182, 212),
        "glow_color": (96, 165, 250),
        "tag_bg": (239, 246, 255),
        "mouth_box_ratio": (0.37, 0.56, 0.63, 0.72),
        "voice_profile": {
            "accent_tld": "en-SG",
            "edge_voice": "en-SG-WayneNeural",
            "pitch_factor": 0.97,
            "tempo": 1.05,
            "eq_filter": "equalizer=f=220:width_type=o:width=1.4:g=3.0,equalizer=f=3600:width_type=o:width=1.2:g=2.8",
            "gemini_voice_design": (
                "Composed, sharp East-Asian international English male quantitative AI founder voice, "
                "clear technical articulation."
            ),
        },
    },
    "elon_musk": {
        "id": "elon_musk",
        "name": "Elon Musk",
        "title": "Founder & CEO, xAI",
        "lab": "xAI",
        "keywords": ["xai", "grok", "musk", "colossus", "tesla ai", "optimus"],
        "intro_greeting": "Hi everyone, Elon Musk here at xAI.",
        "default_quote": "We are scaling maximum truth-seeking intelligence on the world's largest coherent supercomputing cluster.",
        "avatar_file": "elon_musk.png",
        "portrait_file": "elon_musk.jpg",
        "stage_bg_file": "xai_stage.jpg",
        "accent_color": (148, 163, 184),
        "secondary_color": (56, 189, 248),
        "glow_color": (226, 232, 240),
        "tag_bg": (241, 245, 249),
        "mouth_box_ratio": (0.37, 0.56, 0.63, 0.72),
        "voice_profile": {
            "accent_tld": "en-ZA",
            "edge_voice": "en-ZA-LukeNeural",
            "pitch_factor": 0.92,
            "tempo": 1.02,
            "eq_filter": "equalizer=f=180:width_type=o:width=1.5:g=4.5,equalizer=f=3100:width_type=o:width=1.2:g=2.5",
            "gemini_voice_design": (
                "Deep baritone male engineering CEO voice with subtle South-African-American inflection, "
                "thoughtful pauses and bold emphasis."
            ),
        },
    },
    "satya_nadella": {
        "id": "satya_nadella",
        "name": "Satya Nadella",
        "title": "Chairman & CEO, Microsoft",
        "lab": "Microsoft AI",
        "keywords": ["microsoft", "nadella", "copilot", "azure ai", "phi-3", "phi-4", "suleyman"],
        "intro_greeting": "Hello everyone, Satya Nadella here at Microsoft.",
        "default_quote": "We are building the copilot and agentic runtime layer to empower every developer and organization on the planet.",
        "avatar_file": "satya_nadella.png",
        "portrait_file": "satya_nadella.jpg",
        "stage_bg_file": "microsoft_stage.jpg",
        "accent_color": (14, 165, 233),
        "secondary_color": (99, 102, 241),
        "glow_color": (56, 189, 248),
        "tag_bg": (224, 242, 254),
        "mouth_box_ratio": (0.37, 0.56, 0.63, 0.72),
        "voice_profile": {
            "accent_tld": "en-IN",
            "edge_voice": "en-IN-PrabhatNeural",
            "pitch_factor": 0.95,
            "tempo": 1.05,
            "eq_filter": "equalizer=f=210:width_type=o:width=1.5:g=3.8,equalizer=f=3300:width_type=o:width=1.2:g=2.5",
            "gemini_voice_design": (
                "Warm, authoritative Indian-American enterprise technology CEO voice, energetic and inspiring keynote tone."
            ),
        },
    },
    "default_titan": {
        "id": "default_titan",
        "name": "Sundar Pichai",
        "title": "CEO, Google & AI Keynote Host",
        "lab": "Frontier AI Lab",
        "keywords": [],
        "intro_greeting": "Hello everyone, welcome to our live Frontier AI Briefing.",
        "default_quote": "Verified engineering benchmarks confirm significant capability advancements across real-world developer workloads.",
        "avatar_file": "sundar_pichai.png",
        "portrait_file": "sundar_pichai.jpg",
        "accent_color": (66, 133, 244),
        "secondary_color": (99, 102, 241),
        "glow_color": (14, 165, 233),
        "tag_bg": (238, 242, 255),
        "mouth_box_ratio": (0.37, 0.56, 0.63, 0.72),
        "voice_profile": {
            "accent_tld": "en-IN",
            "edge_voice": "en-IN-PrabhatNeural",
            "pitch_factor": 0.96,
            "tempo": 1.04,
            "eq_filter": "equalizer=f=220:width_type=o:width=1.5:g=3.5,equalizer=f=3200:width_type=o:width=1.2:g=2.5",
            "gemini_voice_design": (
                "Calm, articulate executive technology CEO voice with studio keynote presence."
            ),
        },
    },
}


def detect_persona(text: str, context: str = "") -> Dict[str, Any]:
    """
    Detect the exact company CEO persona from headline, context, or source URL
    using strict word-boundary matching so boilerplate words never cause false matches.
    Prioritizes explicit company/model matches (e.g. Google -> Sundar Pichai, OpenAI -> Sam Altman).
    """
    import re

    primary = (text or "").lower()
    secondary = (context or "").lower()
    combined = f"{primary} {secondary}"
    matched = None

    def _has_word(haystack: str, kw: str) -> bool:
        return bool(re.search(r"\b" + re.escape(kw.lower()) + r"\b", haystack))

    # 1. Check primary headline first for explicit company/CEO/model keywords
    if any(_has_word(primary, k) for k in ["alphafold", "alphageometry", "alphagenome", "hassabis", "deepmind"]):
        matched = PERSONA_REGISTRY["demis_hassabis"]
    else:
        for pid, data in PERSONA_REGISTRY.items():
            if pid == "default_titan":
                continue
            if any(_has_word(primary, kw) for kw in data["keywords"]):
                matched = data
                break

    # 2. Check secondary context if headline didn't name a specific company
    if matched is None and secondary:
        for pid, data in PERSONA_REGISTRY.items():
            if pid == "default_titan":
                continue
            if any(_has_word(secondary, kw) for kw in data["keywords"]):
                matched = data
                break

    # 3. Topic-based executive host fallback
    if matched is None:
        if any(_has_word(combined, w) for w in ["gpu", "chip", "hardware", "cuda", "blackwell", "rubin", "npu"]):
            matched = PERSONA_REGISTRY["jensen_huang"]
        elif any(_has_word(combined, w) for w in ["claude", "anthropic", "constitutional"]):
            matched = PERSONA_REGISTRY["dario_amodei"]
        elif any(_has_word(combined, w) for w in ["deepseek", "open-weights", "moe"]):
            matched = PERSONA_REGISTRY["liang_wenfeng"]
        elif any(_has_word(combined, w) for w in ["llama", "meta", "pytorch"]):
            matched = PERSONA_REGISTRY["mark_zuckerberg"]
        elif any(_has_word(combined, w) for w in ["copilot", "github", "azure", "microsoft"]):
            matched = PERSONA_REGISTRY["satya_nadella"]
        elif any(_has_word(combined, w) for w in ["openai", "gpt", "chatgpt", "sora"]):
            matched = PERSONA_REGISTRY["sam_altman"]
        else:
            matched = PERSONA_REGISTRY["sundar_pichai"]

    res = dict(matched)
    res["company"] = res.get("lab", "Google")
    res["role"] = res.get("role", res.get("title", "Chief Executive Officer"))
    res["quote"] = res.get("quote", res.get("default_quote", ""))
    return res


get_persona = detect_persona
get_persona_for_lab = detect_persona


def get_persona_portrait(persona: Dict[str, Any], target_size: Tuple[int, int] = (520, 620)) -> Image.Image:
    """
    Load the high-resolution real photograph portrait of the CEO presenter,
    center-cropped and aspect-fitted to `target_size`.
    """
    p_file = persona.get("portrait_file") or f"{persona.get('id', 'sundar_pichai')}.jpg"
    candidates = [
        PORTRAITS_DIR / p_file,
        PERSONAS_DIR / persona.get("avatar_file", "sundar_pichai.png"),
        PORTRAITS_DIR / "sundar_pichai.jpg",
    ]
    for path in candidates:
        if path.exists():
            try:
                im = Image.open(path).convert("RGB")
                tw, th = target_size
                target_ratio = tw / th
                iw, ih = im.size
                curr_ratio = iw / ih
                if curr_ratio > target_ratio:
                    new_w = int(ih * target_ratio)
                    left = (iw - new_w) // 2
                    im = im.crop((left, 0, left + new_w, ih))
                else:
                    new_h = int(iw / target_ratio)
                    top = max(0, int((ih - new_h) * 0.12))
                    im = im.crop((0, top, iw, top + new_h))
                return im.resize((tw, th), Image.Resampling.LANCZOS)
            except Exception:
                continue

    # Fallback executive silhouette if file missing
    fallback = Image.new("RGB", target_size, (15, 23, 42))
    return fallback


def get_circular_avatar(key_or_filename: str, size: int = 54) -> Optional[Image.Image]:
    """Load and return circular cropped real photograph avatar for the CEO persona."""
    avatar_path = None
    if key_or_filename in PERSONA_REGISTRY:
        p_jpg = PORTRAITS_DIR / PERSONA_REGISTRY[key_or_filename].get("portrait_file", "")
        if p_jpg.exists():
            avatar_path = p_jpg
        else:
            avatar_path = PERSONAS_DIR / PERSONA_REGISTRY[key_or_filename]["avatar_file"]
    elif (PORTRAITS_DIR / Path(key_or_filename).with_suffix(".jpg").name).exists():
        avatar_path = PORTRAITS_DIR / Path(key_or_filename).with_suffix(".jpg").name
    elif (PERSONAS_DIR / key_or_filename).exists():
        avatar_path = PERSONAS_DIR / key_or_filename
    else:
        for data in PERSONA_REGISTRY.values():
            if data["avatar_file"] == key_or_filename:
                p_jpg = PORTRAITS_DIR / data.get("portrait_file", "")
                avatar_path = p_jpg if p_jpg.exists() else (PERSONAS_DIR / data["avatar_file"])
                break

    if not avatar_path or not avatar_path.exists():
        avatar_path = PORTRAITS_DIR / "sundar_pichai.jpg"
        if not avatar_path.exists():
            avatar_path = PERSONAS_DIR / "default_titan.png"

    if avatar_path and avatar_path.exists():
        try:
            im = Image.open(avatar_path).convert("RGBA")
            w, h = im.size
            side = min(w, h)
            left = (w - side) // 2
            top = max(0, int((h - side) * 0.12))
            im = im.crop((left, top, left + side, top + side)).resize((size, size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            d = ImageDraw.Draw(mask)
            d.ellipse([(0, 0), (size, size)], fill=255)
            out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            out.paste(im, (0, 0), mask=mask)
            return out
        except Exception:
            return None
    return None


def get_persona_stage_background(persona: Dict[str, Any], target_size: Tuple[int, int] = (544, 960)) -> Image.Image:
    """Load and return the authentic company keynote stage background for this persona."""
    stage_file = persona.get("stage_bg_file", "google_stage.jpg")
    candidates = [
        STAGES_DIR / (f"{stage_file.replace('.jpg', '_544.jpg')}" if target_size[0] <= 544 else stage_file),
        STAGES_DIR / stage_file,
        STAGES_DIR / "google_stage.jpg",
    ]
    for p in candidates:
        if p.exists():
            try:
                im = Image.open(p).convert("RGB")
                return im.resize(target_size, Image.Resampling.LANCZOS)
            except Exception:
                continue

    fallback = Image.new("RGB", target_size, (10, 16, 30))
    return fallback

