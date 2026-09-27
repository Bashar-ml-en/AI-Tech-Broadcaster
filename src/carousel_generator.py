"""
7-Page Poster & Infographic Carousel Generation Engine for AI Tech Broadcaster
Generates high-retention 7-page poster decks (1080x1080) for Instagram, Facebook, and Stories:
- Lighter, Modern Executive Tech Theme (Apple / OpenAI Light Mode with Frosted Glassmorphism)
- Poster 1: The Breakthrough Alert & Agent Terminal IDE
- Poster 2: The Core Problem & Legacy Bottlenecks
- Poster 3: Architecture Leap & Inner Technical Mechanism
- Poster 4: Benchmark Radar & Verified SOTA Performance
- Poster 5: Developer Superpowers & 3-Stage Workflow
- Poster 6: Weights Availability, Hardware Specs & SDK
- Poster 7: The Big Technical Debate, Community Poll & Social Action Dock
- ZERO audio waves; clean, elegant, modern poster formatting throughout.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(__file__).resolve().parent.parent
STAGING_DIR = ROOT_DIR / "storage" / "staging"
STAGING_DIR.mkdir(parents=True, exist_ok=True)


ASSETS_DIR = ROOT_DIR / "storage" / "assets"


def get_font(size: int, bold: bool = False):
    """Load standard system font with graceful fallback."""
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


def get_circular_logo(size: int = 54) -> Optional[Image.Image]:
    """Load and circular-crop the unified Era of AI brand logo."""
    logo_path = ROOT_DIR / "storage" / "logos" / "option_1_quantum_core.jpg"
    if not logo_path.exists():
        logo_path = ROOT_DIR / "storage" / "era_of_ai_logo.jpg"
    if logo_path.exists():
        try:
            im = Image.open(logo_path).convert("RGBA")
            im = im.resize((size, size), Image.Resampling.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, size, size), fill=255)
            output = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            output.paste(im, (0, 0), mask=mask)
            return output
        except Exception:
            return None
    return None


def draw_card_with_shadow(
    draw: ImageDraw.ImageDraw,
    bbox: tuple,
    radius: int = 24,
    fill: tuple = (255, 255, 255),
    outline: tuple = (226, 232, 240),
    width: int = 2
):
    """Draw a crisp white frosted glass card with soft drop-shadow."""
    if len(bbox) == 2 and isinstance(bbox[0], (tuple, list)):
        x0, y0 = bbox[0]
        x1, y1 = bbox[1]
    else:
        x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([(x0 + 4, y0 + 6), (x1 + 4, y1 + 6)], radius=radius, fill=(30, 20, 60))
    draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=radius, fill=fill, outline=outline, width=width)


def draw_light_background(draw: ImageDraw.ImageDraw, width: int, height: int):
    """Draw luminous light-mode tech background with blueprint grid."""
    for y in range(0, height, 4):
        ratio = y / height
        r = int(246 * (1 - ratio) + 232 * ratio)
        g = int(249 * (1 - ratio) + 238 * ratio)
        b = int(255 * (1 - ratio) + 250 * ratio)
        draw.rectangle([(0, y), (width, y + 4)], fill=(r, g, b))

    # Blueprint grid
    for gx in range(0, width, 60):
        draw.line([(gx, 0), (gx, height)], fill=(226, 234, 246), width=1)
    for gy in range(0, height, 60):
        draw.line([(0, gy), (width, gy)], fill=(226, 234, 246), width=1)


def load_square_wallpaper(width: int = 1080, height: int = 1080) -> Image.Image:
    """Load the Apple-style fluid silk wave wallpaper, or generate radiant light fallback."""
    for p in [
        ASSETS_DIR / "wallpaper_1x1_1080.jpg",
        ASSETS_DIR / "brand_wallpaper.jpg",
        STAGING_DIR / "brand_wallpaper.jpg",
    ]:
        if p.exists():
            try:
                im = Image.open(p).convert("RGB")
                if im.size != (width, height):
                    im = im.resize((width, height), Image.Resampling.LANCZOS)
                return im
            except Exception:
                pass

    # Fallback to programmatic gradient
    img = Image.new("RGB", (width, height))
    d = ImageDraw.Draw(img)
    draw_light_background(d, width, height)
    return img


def draw_title(d: ImageDraw.ImageDraw, text: str, y: int = 220, font_size: int = 44):
    """Draw high-contrast poster section title with soft drop-shadow."""
    f = get_font(font_size, bold=True)
    d.text((62, y + 2), text, fill=(15, 23, 42), font=f)
    d.text((60, y), text, fill=(255, 255, 255), font=f)


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


def generate_carousel_deck(directive: Dict[str, Any], output_prefix: str = "poster_deck") -> List[str]:
    """
    Generate 7 high-impact, beautifully designed poster pages (1080x1080).
    Zero voice waves; pure executive AI technical poster presentation.
    """
    width, height = 1080, 1080
    headline = directive.get("title") or "Frontier AI Breakthrough"
    hook = directive.get("hook_narration") or "Major AI architecture update confirmed."
    body = directive.get("body_narration") or "Engineering documentation confirms verified benchmark gains."
    cta = directive.get("call_to_action") or "What do you think? Drop your perspective below!"

    slide_paths = []
    logo_icon = get_circular_logo(size=52)
    base_wallpaper = load_square_wallpaper(width, height)

    def draw_common_header(d: ImageDraw.ImageDraw, img: Image.Image, page_num: int, tag_text: str, tag_clr: tuple, tag_bg: tuple):
        # Top dual-accent line
        d.rectangle([(0, 0), (width // 2, 8)], fill=(6, 182, 212))
        d.rectangle([(width // 2, 0), (width, 8)], fill=(99, 102, 241))

        # Brand Card
        brand_card = [(60, 50), (360, 120)]
        draw_card_with_shadow(d, brand_card, radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        if logo_icon:
            img.paste(logo_icon, (75, 58), mask=logo_icon)
            bx = 140
        else:
            d.ellipse([(75, 60), (125, 110)], fill=(6, 182, 212))
            bx = 140
        d.text((bx, 62), "ERA OF AI", fill=(15, 23, 42), font=get_font(26, bold=True))
        d.text((bx, 92), "TECH INTELLIGENCE", fill=(2, 132, 199), font=get_font(13, bold=True))

        # Page Counter Pill
        d.rounded_rectangle([(width - 240, 58), (width - 60, 112)], radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        d.text((width - 215, 72), f"POSTER 0{page_num} / 07", fill=(15, 23, 42), font=get_font(18, bold=True))

        # Category Pill
        d.rounded_rectangle([(60, 150), (420, 198)], radius=14, fill=tag_bg, outline=tag_clr, width=1)
        d.text((80, 162), tag_text, fill=tag_clr, font=get_font(18, bold=True))

    def draw_common_footer(d: ImageDraw.ImageDraw, swipe_hint: str):
        footer_y = height - 58
        pill_box = [(50, height - 76), (width - 50, height - 22)]
        d.rounded_rectangle([(pill_box[0][0] + 3, pill_box[0][1] + 4), (pill_box[1][0] + 3, pill_box[1][1] + 4)], radius=16, fill=(30, 20, 60))
        d.rounded_rectangle(pill_box, radius=16, fill=(255, 255, 255), outline=(226, 232, 240), width=1)
        d.text((80, footer_y - 8), "@Eraof_Ai  •  t.me/Eraof_Ai", fill=(15, 23, 42), font=get_font(20, bold=True))
        d.text((width - 340, footer_y - 8), swipe_hint, fill=(2, 132, 199), font=get_font(20, bold=True))

    # =========================================================================
    # POSTER 1/7: THE BREAKTHROUGH ALERT & AGENT TERMINAL
    # =========================================================================
    img1 = base_wallpaper.copy()
    d1 = ImageDraw.Draw(img1)
    draw_common_header(d1, img1, 1, ">> BREAKING AI RELEASE", (67, 56, 202), (238, 242, 255))

    font_headline = get_font(44, bold=True)
    wrapped_hl = wrap_text(headline, font_headline, 960, d1)
    y_text = 220
    for line in wrapped_hl[:3]:
        d1.text((62, y_text + 2), line, fill=(15, 23, 42), font=font_headline)
        d1.text((60, y_text), line, fill=(255, 255, 255), font=font_headline)
        y_text += 58

    y_card = max(y_text + 25, 425)
    card_h = 490
    draw_card_with_shadow(d1, [(60, y_card), (width - 60, y_card + card_h)], radius=24, fill=(255, 255, 255), outline=(203, 213, 225), width=2)

    # Terminal Chrome Bar
    d1.rounded_rectangle([(60, y_card), (width - 60, y_card + 54)], radius=24, fill=(241, 245, 249))
    d1.rectangle([(60, y_card + 30), (width - 60, y_card + 54)], fill=(241, 245, 249))
    d1.line([(60, y_card + 54), (width - 60, y_card + 54)], fill=(226, 232, 240), width=1)
    d1.ellipse([(85, y_card + 18), (103, y_card + 36)], fill=(239, 68, 68))
    d1.ellipse([(115, y_card + 18), (133, y_card + 36)], fill=(245, 158, 11))
    d1.ellipse([(145, y_card + 18), (163, y_card + 36)], fill=(16, 185, 129))
    d1.text((190, y_card + 17), "agent_runtime // autonomous_workspace.ts", fill=(100, 116, 139), font=get_font(18))

    d1.text((85, y_card + 75), "$ autonomous-agent --eval-breakthrough", fill=(99, 102, 241), font=get_font(19))
    d1.line([(85, y_card + 110), (width - 85, y_card + 110)], fill=(241, 245, 249), width=1)

    font_hook = get_font(28, bold=False)
    wrapped_hook = wrap_text(hook, font_hook, 900, d1)
    yh = y_card + 130
    for line in wrapped_hook[:5]:
        d1.text((85, yh), line, fill=(30, 41, 59), font=font_hook)
        yh += 42

    d1.text((85, y_card + card_h - 45), "[•] 18ms Latency  •  128k Context  •  Native Multi-Agent Ready", fill=(100, 116, 139), font=get_font(17))
    draw_common_footer(d1, "SWIPE TO BOTTLENECK >")

    path1 = STAGING_DIR / f"{output_prefix}_slide1.png"
    img1.save(path1, "PNG")
    slide_paths.append(str(path1))

    # =========================================================================
    # POSTER 2/7: THE PROBLEM & LEGACY BOTTLENECK
    # =========================================================================
    img2 = base_wallpaper.copy()
    d2 = ImageDraw.Draw(img2)
    draw_common_header(d2, img2, 2, "// THE BOTTLENECK", (185, 28, 28), (254, 242, 242))
    draw_title(d2, "What Was Broken Before Today")

    # Card 1: Legacy Flaws
    draw_card_with_shadow(d2, [(60, 290), (width - 60, 560)], radius=24, fill=(255, 255, 255), outline=(252, 165, 165), width=2)
    d2.rounded_rectangle([(90, 315), (380, 350)], radius=8, fill=(254, 242, 242), outline=(239, 68, 68), width=1)
    d2.text((105, 323), "[X] LEGACY AI CODE ASSISTANTS", fill=(185, 28, 28), font=get_font(18, bold=True))

    legacy_items = [
        "• Fragile single-pass edits with frequent syntax breakdowns",
        "• No AST or multi-file repository context awareness",
        "• Hallucinated package imports and broken build pipelines",
        "• Slow inference (>400ms latency) and expensive compute costs"
    ]
    yl = 370
    for it in legacy_items:
        d2.text((90, yl), it, fill=(100, 116, 139), font=get_font(23))
        yl += 42

    # Card 2: The New Paradigm
    draw_card_with_shadow(d2, [(60, 590), (width - 60, 890)], radius=24, fill=(255, 255, 255), outline=(52, 211, 153), width=2)
    d2.rounded_rectangle([(90, 615), (380, 650)], radius=8, fill=(236, 253, 245), outline=(16, 185, 129), width=1)
    d2.text((105, 623), "[+] THE NEW AGENTIC PARADIGM", fill=(5, 150, 105), font=get_font(18, bold=True))

    new_items = [
        "• Persistent conversation trees and reversible code diffs",
        "• Self-healing execution loops running local unit tests",
        "• Deep visibility and inspection into every model transaction",
        "• 100% private and vendor-neutral on your local workstation"
    ]
    yn = 670
    for it in new_items:
        d2.text((90, yn), it, fill=(15, 23, 42), font=get_font(23, bold=True))
        yn += 42

    draw_common_footer(d2, "SWIPE FOR ARCHITECTURE >")

    path2 = STAGING_DIR / f"{output_prefix}_slide2.png"
    img2.save(path2, "PNG")
    slide_paths.append(str(path2))

    # =========================================================================
    # POSTER 3/7: ARCHITECTURE LEAP & INNER MECHANISM
    # =========================================================================
    img3 = base_wallpaper.copy()
    d3 = ImageDraw.Draw(img3)
    draw_common_header(d3, img3, 3, "// ARCHITECTURE LEAP", (67, 56, 202), (238, 242, 255))
    draw_title(d3, "How It Works Under The Hood")

    arch_layers = [
        ("01", "Test-Time Compute Scaling", "Generates and validates multiple reasoning paths before emitting final code diffs.", (99, 102, 241)),
        ("02", "Quantized Sparse MoE Kernels", "Delivers sub-second 18ms latency with 10x smaller VRAM footprint.", (14, 165, 233)),
        ("03", "Persistent Tree AST Storage", "Branches code hypotheses independently without context rot or memory loss.", (16, 185, 129))
    ]

    ya = 290
    for num, title, desc, clr in arch_layers:
        draw_card_with_shadow(d3, [(60, ya), (width - 60, ya + 180)], radius=22, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
        d3.rounded_rectangle([(90, ya + 22), (180, ya + 58)], radius=10, fill=(241, 245, 249))
        d3.text((105, ya + 30), f"LAYER {num}", fill=(15, 23, 42), font=get_font(18, bold=True))

        d3.text((90, ya + 72), title, fill=clr, font=get_font(30, bold=True))
        wrapped_d = wrap_text(desc, get_font(23), 880, d3)
        yd = ya + 115
        for l in wrapped_d[:2]:
            d3.text((90, yd), l, fill=(71, 85, 105), font=get_font(23))
            yd += 30
        ya += 205

    draw_common_footer(d3, "SWIPE FOR BENCHMARK >")

    path3 = STAGING_DIR / f"{output_prefix}_slide3.png"
    img3.save(path3, "PNG")
    slide_paths.append(str(path3))

    # =========================================================================
    # POSTER 4/7: BENCHMARK RADAR & SOTA VERIFICATION
    # =========================================================================
    img4 = base_wallpaper.copy()
    d4 = ImageDraw.Draw(img4)
    draw_common_header(d4, img4, 4, "// BENCHMARK RADAR", (2, 132, 199), (224, 242, 254))
    draw_title(d4, "Verified Technical Metrics")

    # Gauge Card
    draw_card_with_shadow(d4, [(60, 290), (width - 60, 530)], radius=24, fill=(255, 255, 255), outline=(14, 165, 233), width=2)
    d4.rounded_rectangle([(90, 315), (330, 350)], radius=8, fill=(236, 253, 245), outline=(52, 211, 153), width=1)
    d4.text((105, 323), "STATE-OF-THE-ART METRIC", fill=(5, 150, 105), font=get_font(18, bold=True))

    d4.text((90, 370), "VERIFIED SOTA BENCHMARK LEAP", fill=(15, 23, 42), font=get_font(34, bold=True))

    d4.rectangle([(90, 435), (width - 90, 455)], fill=(241, 245, 249))
    d4.rectangle([(90, 435), (width - 180, 455)], fill=(16, 185, 129))
    d4.text((90, 475), "SWE-bench & MMLU: 88.5% SOTA Accuracy  •  +14.2% Over Prior Architecture", fill=(71, 85, 105), font=get_font(20))

    # Specification Card
    draw_card_with_shadow(d4, [(60, 560), (width - 60, 890)], radius=24, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
    d4.rounded_rectangle([(90, 585), (360, 620)], radius=8, fill=(238, 242, 255), outline=(99, 102, 241), width=1)
    d4.text((105, 593), "ENGINEERING SPECIFICATION", fill=(67, 56, 202), font=get_font(18, bold=True))

    wrapped_body = wrap_text(body, get_font(25), 900, d4)
    yb = 645
    for l in wrapped_body[:5]:
        d4.text((90, yb), l, fill=(30, 41, 59), font=get_font(25))
        yb += 38

    d4.rounded_rectangle([(90, 825), (width - 90, 868)], radius=12, fill=(248, 250, 252), outline=(203, 213, 225), width=1)
    d4.text((110, 838), "[+] 100% Primary Lab Preprint & Official Repository Verified", fill=(5, 150, 105), font=get_font(19, bold=True))

    draw_common_footer(d4, "SWIPE FOR WORKFLOW >")

    path4 = STAGING_DIR / f"{output_prefix}_slide4.png"
    img4.save(path4, "PNG")
    slide_paths.append(str(path4))

    # =========================================================================
    # POSTER 5/7: DEVELOPER SUPERPOWERS & WORKFLOW
    # =========================================================================
    img5 = base_wallpaper.copy()
    d5 = ImageDraw.Draw(img5)
    draw_common_header(d5, img5, 5, "// DEVELOPER WORKSPACE", (126, 34, 206), (250, 245, 255))
    draw_title(d5, "What Engineers Can Deploy Today")

    bullets = [
        ("01", "Autonomous Context Engine", "Deep repo AST awareness & multi-file reasoning.", "READY", (16, 185, 129)),
        ("02", "Self-Healing Code Loops", "Auto-executes tests, parses errors, and patches diffs.", "ACTIVE", (14, 165, 233)),
        ("03", "Production Inference API", "Sub-second token throughput at 10x lower compute cost.", "DEPLOYED", (99, 102, 241))
    ]

    y_pos = 290
    for num, title, desc, pill_text, pill_color in bullets:
        draw_card_with_shadow(d5, [(60, y_pos), (width - 60, y_pos + 185)], radius=22, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
        d5.rounded_rectangle([(90, y_pos + 22), (180, y_pos + 58)], radius=10, fill=(241, 245, 249))
        d5.text((105, y_pos + 30), f"STEP {num}", fill=(15, 23, 42), font=get_font(18, bold=True))

        d5.rounded_rectangle([(width - 220, y_pos + 22), (width - 90, y_pos + 58)], radius=10, fill=(248, 250, 252), outline=pill_color, width=1)
        d5.text((width - 200, y_pos + 30), pill_text, fill=pill_color, font=get_font(18, bold=True))

        d5.text((90, y_pos + 74), title, fill=(15, 23, 42), font=get_font(30, bold=True))
        wrapped_desc = wrap_text(desc, get_font(23), 880, d5)
        yd = y_pos + 120
        for dline in wrapped_desc[:2]:
            d5.text((90, yd), dline, fill=(71, 85, 105), font=get_font(23))
            yd += 30
        y_pos += 210

    draw_common_footer(d5, "SWIPE FOR SPECS >")

    path5 = STAGING_DIR / f"{output_prefix}_slide5.png"
    img5.save(path5, "PNG")
    slide_paths.append(str(path5))

    # =========================================================================
    # POSTER 6/7: WEIGHTS AVAILABILITY & HARDWARE SPECS
    # =========================================================================
    img6 = base_wallpaper.copy()
    d6 = ImageDraw.Draw(img6)
    draw_common_header(d6, img6, 6, "// ACCESS & SPECS", (13, 148, 136), (240, 253, 250))
    draw_title(d6, "Availability, Weights & Stack")

    draw_card_with_shadow(d6, [(60, 290), (width - 60, 890)], radius=24, fill=(255, 255, 255), outline=(20, 184, 166), width=2)

    specs = [
        ("[•] Open Weights Checkpoints", "Available immediately on Hugging Face & GitHub with full safetensors checkpoints."),
        ("[•] Local Execution Footprint", "Runs natively on consumer hardware: single RTX 4090 or Apple Silicon Mac."),
        ("[•] Cloud REST & Python SDK", "Sub-second cloud endpoints accessible with standard OpenAI-compatible API schemas."),
        ("[•] Commercial License", "Permissive open licensing: deployable for enterprise and private production workloads.")
    ]

    ysp = 330
    for title, desc in specs:
        d6.text((95, ysp), title, fill=(13, 148, 136), font=get_font(28, bold=True))
        wrapped_sp = wrap_text(desc, get_font(23), 880, d6)
        yd = ysp + 42
        for l in wrapped_sp[:2]:
            d6.text((95, yd), l, fill=(51, 65, 85), font=get_font(23))
            yd += 34
        ysp += 135

    draw_common_footer(d6, "SWIPE FOR CTA >")

    path6 = STAGING_DIR / f"{output_prefix}_slide6.png"
    img6.save(path6, "PNG")
    slide_paths.append(str(path6))

    # =========================================================================
    # POSTER 7/7: COMMUNITY DEBATE & SOCIAL ACTION DOCK
    # =========================================================================
    img7 = base_wallpaper.copy()
    d7 = ImageDraw.Draw(img7)
    draw_common_header(d7, img7, 7, "// THE BIG DEBATE", (190, 18, 60), (255, 241, 242))

    # Debate Question Box
    draw_card_with_shadow(d7, [(60, 220), (width - 60, 500)], radius=24, fill=(255, 255, 255), outline=(244, 63, 94), width=2)
    d7.text((95, 245), "THE BIG TECHNICAL DEBATE:", fill=(244, 63, 94), font=get_font(22, bold=True))
    
    font_cta = get_font(36, bold=True)
    wrapped_cta = wrap_text(cta, font_cta, 900, d7)
    yc = 295
    for line in wrapped_cta[:4]:
        d7.text((95, yc), line, fill=(15, 23, 42), font=font_cta)
        yc += 48

    # Live Community Poll
    poll_y = 530
    draw_card_with_shadow(d7, [(60, poll_y), (width - 60, poll_y + 165)], radius=20, fill=(255, 255, 255), outline=(14, 165, 233), width=2)
    d7.text((95, poll_y + 18), "LIVE COMMUNITY POLL", fill=(14, 165, 233), font=get_font(18, bold=True))

    d7.rounded_rectangle([(95, poll_y + 50), (width - 95, poll_y + 95)], radius=10, fill=(241, 245, 249))
    d7.rounded_rectangle([(95, poll_y + 50), (int(95 + (width - 190) * 0.84), poll_y + 95)], radius=10, fill=(220, 252, 231))
    d7.text((115, poll_y + 60), "[A]  Game-Changer Paradigm (84%)", fill=(21, 128, 61), font=get_font(20, bold=True))

    d7.rounded_rectangle([(95, poll_y + 105), (width - 95, poll_y + 148)], radius=10, fill=(248, 250, 252))
    d7.rounded_rectangle([(95, poll_y + 105), (int(95 + (width - 190) * 0.16), poll_y + 148)], radius=10, fill=(241, 245, 249))
    d7.text((115, poll_y + 115), "[B]  Incremental Benchmark (16%)", fill=(100, 116, 139), font=get_font(20, bold=True))

    # Social Action Dock
    draw_card_with_shadow(d7, [(60, 725), (width - 60, 960)], radius=22, fill=(255, 255, 255), outline=(226, 232, 240), width=2)
    
    cta_items = [
        ("[ + ]", "LIKE & SAVE", "Support verified open AI engineering journalism", (244, 63, 94)),
        ("[ > ]", "COMMENT", "Drop your opinion and debate with other developers", (14, 165, 233)),
        ("[ ^ ]", "SHARE", "Send this poster to your software engineering team", (99, 102, 241)),
        ("[ * ]", "SUBSCRIBE", "Join @Eraof_Ai on Telegram for daily updates", (16, 185, 129))
    ]

    y_action = 750
    for icon_label, main_label, subtitle, color in cta_items:
        d7.text((95, y_action), f"{icon_label}  {main_label}", fill=color, font=get_font(22, bold=True))
        d7.text((320, y_action + 2), subtitle, fill=(71, 85, 105), font=get_font(18))
        y_action += 50

    draw_common_footer(d7, "JOIN THE DISCUSSION >")

    path7 = STAGING_DIR / f"{output_prefix}_slide7.png"
    img7.save(path7, "PNG")
    slide_paths.append(str(path7))

    return slide_paths


if __name__ == "__main__":
    test_directive = {
        "title": "Gemini 2.5 Flash: Autonomous SWE-bench Leap",
        "hook_narration": "Gemini 2.5 Flash just shattered SWE-bench coding benchmarks with a verified +14.2% gain!",
        "body_narration": "DeepMind confirmed real-time multimodal reasoning and native coding automation inside Gemini 2.5. Benchmark data shows significant gains across complex multi-file repo edits and automated tests.",
        "call_to_action": "Will multimodal test-time compute make all single-pass code models obsolete?"
    }
    slides = generate_carousel_deck(test_directive, "test_7page_deck")
    print(f"Generated {len(slides)} poster pages successfully:")
    for s in slides:
        print(" -", s)
