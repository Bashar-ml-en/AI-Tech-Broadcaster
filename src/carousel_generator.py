"""
Multi-Slide Carousel & Infographic Generation Engine for AI Tech Broadcaster
Generates high-retention 4-slide carousel decks (1080x1080) for Instagram & Facebook:
- Slide 1: The Disruption Hook & Identity
- Slide 2: Core Engineering Architecture & Benchmark Leaps
- Slide 3: Practical Developer Utility & Real-World Unlocks
- Slide 4: High-Conversion Interactive Viral CTA (Like, Comment, Share, Follow)
"""

import os
from pathlib import Path
from typing import Dict, Any, List
from PIL import Image, ImageDraw, ImageFont

# Root directory and staging
ROOT_DIR = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT_DIR / "storage" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


def get_font(size: int, bold: bool = False):
    """Load standard Windows/system font with graceful fallback."""
    font_names = [
        "segoeuib.ttf" if bold else "segoeui.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "calibrib.ttf" if bold else "calibri.ttf"
    ]
    for fn in font_names:
        try:
            return ImageFont.truetype(fn, size)
        except Exception:
            continue
    return ImageFont.load_default()


def draw_gradient_background(draw: ImageDraw.ImageDraw, width: int, height: int, color_top=(10, 15, 30), color_bottom=(5, 8, 18)):
    """Draw smooth deep futuristic gradient background."""
    for y in range(height):
        ratio = y / height
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def wrap_text(text: str, font: ImageFont.ImageFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wrap text to fit within specified pixel width."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w > max_width and len(current_line) > 1:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def generate_carousel_deck(directive: Dict[str, Any], output_prefix: str = "carousel") -> List[str]:
    """
    Generate 4 sequentially detailed carousel slides (1080x1080) for a given broadcast directive.
    Returns list of local file paths.
    """
    width, height = 1080, 1080
    headline = directive.get("title") or "Frontier AI Breakthrough"
    hook = directive.get("hook_narration") or "Major AI architecture update confirmed."
    body = directive.get("body_narration") or "Engineering documentation confirms verified benchmark gains."
    cta = directive.get("call_to_action") or "What do you think? Drop your perspective below!"

    slide_paths = []

    # -------------------------------------------------------------------------
    # SLIDE 1: DISRUPTION HOOK & HEADLINE
    # -------------------------------------------------------------------------
    img1 = Image.new("RGB", (width, height))
    d1 = ImageDraw.Draw(img1)
    draw_gradient_background(d1, width, height, (12, 18, 38), (5, 7, 16))

    # Glowing top accent bar
    d1.rectangle([(0, 0), (width, 12)], fill=(6, 182, 212))

    # Header Brand Tag
    d1.rectangle([(80, 70), (260, 115)], fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    font_brand = get_font(22, bold=True)
    d1.text((95, 80), "ERA OF AI", fill=(6, 182, 212), font=font_brand)

    # Slide Counter
    font_counter = get_font(22, bold=True)
    d1.text((width - 160, 80), "SLIDE 1/4", fill=(148, 163, 184), font=font_counter)

    # Breaking Badge
    d1.rectangle([(80, 170), (330, 220)], fill=(245, 158, 11), outline=(217, 119, 6))
    font_badge = get_font(24, bold=True)
    d1.text((100, 180), "BREAKTHROUGH", fill=(0, 0, 0), font=font_badge)

    # Main Headline
    font_headline = get_font(52, bold=True)
    wrapped_hl = wrap_text(headline, font_headline, 920, d1)
    y_text = 270
    for line in wrapped_hl[:4]:
        d1.text((80, y_text), line, fill=(255, 255, 255), font=font_headline)
        y_text += 70

    # Glass Card for Hook
    y_card = max(y_text + 40, 560)
    d1.rounded_rectangle([(80, y_card), (width - 80, y_card + 320)], radius=24, fill=(15, 23, 42), outline=(6, 182, 212), width=3)
    
    font_hook_label = get_font(24, bold=True)
    d1.text((120, y_card + 35), "THE CORE CLAIM:", fill=(6, 182, 212), font=font_hook_label)

    font_hook = get_font(34, bold=False)
    wrapped_hook = wrap_text(hook, font_hook, 840, d1)
    yh = y_card + 85
    for line in wrapped_hook[:4]:
        d1.text((120, yh), line, fill=(241, 245, 249), font=font_hook)
        yh += 48

    # Swipe Prompt Footer
    font_swipe = get_font(26, bold=True)
    d1.text((width // 2 - 120, height - 70), "SWIPE FOR DATA >", fill=(6, 182, 212), font=font_swipe)

    path1 = STAGING_DIR / f"{output_prefix}_slide1.png"
    img1.save(path1, "PNG")
    slide_paths.append(str(path1))

    # -------------------------------------------------------------------------
    # SLIDE 2: CORE ARCHITECTURE & BENCHMARK NUMBERS
    # -------------------------------------------------------------------------
    img2 = Image.new("RGB", (width, height))
    d2 = ImageDraw.Draw(img2)
    draw_gradient_background(d2, width, height, (10, 16, 32), (4, 6, 14))

    d2.rectangle([(0, 0), (width, 12)], fill=(59, 130, 246))
    d2.text((80, 80), "ERA OF AI  •  ARCHITECTURE & DATA", fill=(148, 163, 184), font=get_font(22, bold=True))
    d2.text((width - 160, 80), "SLIDE 2/4", fill=(148, 163, 184), font=get_font(22, bold=True))

    font_sec = get_font(44, bold=True)
    d2.text((80, 160), "Verified Technical Metrics", fill=(255, 255, 255), font=font_sec)

    # Key Metric Box
    d2.rounded_rectangle([(80, 250), (width - 80, 480)], radius=24, fill=(17, 24, 39), outline=(59, 130, 246), width=3)
    d2.text((120, 290), "STATE-OF-THE-ART METRIC", fill=(59, 130, 246), font=get_font(22, bold=True))
    d2.text((120, 340), "SOTA BENCHMARK GAIN", fill=(16, 185, 129), font=get_font(56, bold=True))
    d2.text((120, 420), "Verified on official repository & primary preprint documentation", fill=(148, 163, 184), font=get_font(24))

    # Technical Deep-Dive Card
    d2.rounded_rectangle([(80, 520), (width - 80, 920)], radius=24, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    d2.text((120, 560), "TECHNICAL ARCHITECTURE:", fill=(148, 163, 184), font=get_font(24, bold=True))

    font_body = get_font(32)
    wrapped_body = wrap_text(body, font_body, 840, d2)
    yb = 620
    for line in wrapped_body[:6]:
        d2.text((120, yb), line, fill=(241, 245, 249), font=font_body)
        yb += 46

    d2.text((width // 2 - 140, height - 70), "SWIPE FOR IMPACT >", fill=(59, 130, 246), font=get_font(26, bold=True))

    path2 = STAGING_DIR / f"{output_prefix}_slide2.png"
    img2.save(path2, "PNG")
    slide_paths.append(str(path2))

    # -------------------------------------------------------------------------
    # SLIDE 3: DEVELOPER IMPLICATION & PRACTICAL APPLICATION
    # -------------------------------------------------------------------------
    img3 = Image.new("RGB", (width, height))
    d3 = ImageDraw.Draw(img3)
    draw_gradient_background(d3, width, height, (14, 12, 36), (6, 5, 18))

    d3.rectangle([(0, 0), (width, 12)], fill=(168, 85, 247))
    d3.text((80, 80), "ERA OF AI  •  DEVELOPER TOOLING", fill=(148, 163, 184), font=get_font(22, bold=True))
    d3.text((width - 160, 80), "SLIDE 3/4", fill=(148, 163, 184), font=get_font(22, bold=True))

    d3.text((80, 160), "What Engineers Can Deploy Today", fill=(255, 255, 255), font=get_font(44, bold=True))

    # 3 Bullet Feature Cards
    bullets = [
        ("01", "Native API Access & Model Weights", "Direct developer inference access enabled immediately across cloud and API providers."),
        ("02", "Autonomous Agent Integration", "Compatible with multi-file coding loops, self-correction scaffolds, and tool execution."),
        ("03", "Compute Cost Efficiency", "Reduces inference latency and test-time token spend for production workflows.")
    ]

    y_pos = 260
    for num, title, desc in bullets:
        d3.rounded_rectangle([(80, y_pos), (width - 80, y_pos + 180)], radius=20, fill=(19, 16, 43), outline=(139, 92, 246), width=2)
        d3.rectangle([(110, y_pos + 35), (170, y_pos + 85)], fill=(139, 92, 246))
        d3.text((120, y_pos + 42), num, fill=(255, 255, 255), font=get_font(28, bold=True))
        d3.text((195, y_pos + 35), title, fill=(255, 255, 255), font=get_font(28, bold=True))
        
        wrapped_desc = wrap_text(desc, get_font(22), 760, d3)
        yd = y_pos + 85
        for dline in wrapped_desc[:2]:
            d3.text((195, yd), dline, fill=(203, 213, 225), font=get_font(22))
            yd += 32
        y_pos += 215

    d3.text((width // 2 - 130, height - 70), "SWIPE FOR CTA >", fill=(168, 85, 247), font=get_font(26, bold=True))

    path3 = STAGING_DIR / f"{output_prefix}_slide3.png"
    img3.save(path3, "PNG")
    slide_paths.append(str(path3))

    # -------------------------------------------------------------------------
    # SLIDE 4: HIGH-CONVERSION INTERACTIVE VIRAL CTA
    # -------------------------------------------------------------------------
    img4 = Image.new("RGB", (width, height))
    d4 = ImageDraw.Draw(img4)
    draw_gradient_background(d4, width, height, (18, 14, 28), (8, 6, 16))

    d4.rectangle([(0, 0), (width, 12)], fill=(236, 72, 153))
    d4.text((80, 80), "ERA OF AI  •  COMMUNITY DEBATE", fill=(148, 163, 184), font=get_font(22, bold=True))
    d4.text((width - 160, 80), "SLIDE 4/4", fill=(148, 163, 184), font=get_font(22, bold=True))

    d4.text((80, 160), "The Big Question", fill=(236, 72, 153), font=get_font(34, bold=True))

    # Polarizing Debate CTA Box
    d4.rounded_rectangle([(80, 230), (width - 80, 560)], radius=24, fill=(24, 18, 38), outline=(236, 72, 153), width=3)
    
    font_cta = get_font(42, bold=True)
    wrapped_cta = wrap_text(cta, font_cta, 820, d4)
    yc = 280
    for line in wrapped_cta[:4]:
        d4.text((120, yc), line, fill=(255, 255, 255), font=font_cta)
        yc += 60

    # 4 Interactive Buttons Card
    d4.rounded_rectangle([(80, 600), (width - 80, 920)], radius=24, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    
    cta_items = [
        ("❤️  LIKE", "Support verified open AI engineering journalism", (244, 63, 94)),
        ("💬  COMMENT", "Drop your opinion and debate with other developers", (6, 182, 212)),
        ("↗️  SHARE", "Send this carousel to your software engineering team", (59, 130, 246)),
        ("🔔  FOLLOW", "Follow @EraofAi for daily technical AI updates", (16, 185, 129))
    ]

    y_action = 630
    for icon_label, subtitle, color in cta_items:
        d4.text((120, y_action), icon_label, fill=color, font=get_font(26, bold=True))
        d4.text((320, y_action + 4), subtitle, fill=(203, 213, 225), font=get_font(20))
        y_action += 68

    d4.text((width // 2 - 140, height - 70), "@EraofAi  •  2026", fill=(148, 163, 184), font=get_font(24, bold=True))

    path4 = STAGING_DIR / f"{output_prefix}_slide4.png"
    img4.save(path4, "PNG")
    slide_paths.append(str(path4))

    return slide_paths


if __name__ == "__main__":
    test_directive = {
        "title": "Gemini Image: SWE-bench +14.2% Gain Confirmed",
        "hook_narration": "Gemini Image just shattered SWE-bench coding benchmarks with a verified +14.2% gain!",
        "body_narration": "DeepMind confirmed real-time multimodal reasoning and native coding automation inside Gemini Image. Benchmark data shows significant gains across complex multi-file repo edits and automated tests.",
        "call_to_action": "Will multimodal test-time compute make all single-pass code models obsolete?"
    }
    slides = generate_carousel_deck(test_directive, "test_deck")
    print(f"Generated {len(slides)} slides successfully:")
    for s in slides:
        print(" -", s)
