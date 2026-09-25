---
name: media-director
description: Synthesize qualified AI technical stories into high-retention short-form media directives, route formats (Veo 3.1 vs Imagen 3.0), and enforce the strict JSON Director schema.
---

# Media Director & Retention Engineering Skill

This skill guides the autonomous agent in transforming raw, verified technical breakthroughs into captivating, high-retention short-form broadcast media designed for TikTok, Instagram Reels, Facebook Reels, Threads, and X.

---

## 1. Format Assignment Matrix

Evaluate the qualified update and assign the format strictly according to technical subject matter:

| Subject Type | Assigned Format | Target Pipeline |
| :--- | :--- | :--- |
| Dynamic software demos, robotics, code execution screencasts, multimodal VLM capabilities | `video` | Google Veo 3.1 Fast (9:16 vertical MP4, 6s) + TTS Voiceover |
| Benchmark charts, system schematics, policy/safety papers, API pricing updates | `text_image` | Imagen 3.0 (1:1 square graphic) + Technical Copy |

---

## 2. Short-Form Narration Formula (Strict 30–45s Pacing)

All narration copy must adhere strictly to the 4-block psychological retention model:

```
[0s - 3s] Block 1: Disruption Hook
  - Goal: Stop scroll immediately.
  - Formula: Bold, high-contrast factual assertion.
  - Invariant: Zero greetings, zero channel introductions, zero filler.
  - Example: "Google DeepMind just made standard transformer fine-tuning obsolete."

[4s - 18s] Block 2: The Core Event
  - Goal: Deliver dense, verified technical information.
  - Formula: State the release name, the engineering team, and the definitive metric.
  - Example: "Their newly released Gemini 2.0 Flash architecture achieves a 14.2% jump on SWE-bench while cutting inference latency under 200 milliseconds."

[19s - 30s] Block 3: Practical Application
  - Goal: Demonstrate immediate developer utility.
  - Formula: Explain what engineers can build right now that was previously impossible.
  - Example: "Developers can now run real-time agentic reasoning loops over multi-million token codebases with zero throughput degradation."

[31s - 35s] Block 4: The Debate CTA
  - Goal: Drive high-velocity comment section engagement.
  - Formula: Ask a polarizing, non-trivial technical trade-off question.
  - Example: "Will open-weight alternatives ever catch up, or is proprietary infrastructure now unassailable?"
```

---

## 3. Generative Prompt Guidelines

### For Google Veo 3.1 Fast (`format = "video"`)
- **Aspect Ratio**: Must be explicitly `9:16 vertical aspect ratio`.
- **Cinematography**: Dynamic camera motion (`rapid macro tracking zoom`, `low-angle orbital sweep`, `fpv dive into silicon dies`).
- **Lighting**: Cinematic volumetric lighting, high-contrast atmospheric rays, neon accents over dark matte textures.
- **Rendering**: Ultra-photorealistic, 8k render, octane render style.
- **Typography Rule**: Strictly **ZERO baked-in typography, text, or floating subtitles** in the video prompt (captions are rendered natively by platforms).

### For Imagen 3.0 (`format = "text_image"`)
- **Aspect Ratio**: Must be explicitly `1:1 square aspect ratio`.
- **Style**: Clean vector or isometric schematic aesthetic.
- **Color Balance**: Dark-mode palette (obsidian, deep navy) with vibrant contrast (cyan, electric amber).

---

## 4. Strict JSON Director Output Schema

All synthesis outputs must match this JSON contract:

```json
{
  "title": "5-8 word punchy technical headline",
  "source_url": "https://official-source-link.com/announcement",
  "format": "video",
  "hook_narration": "First 3 seconds of spoken audio designed to stop scrolling.",
  "body_narration": "Remaining spoken audio covering the core release and practical developer implications (40-60 words).",
  "call_to_action": "High-velocity polarizing question to trigger comments.",
  "visual_prompt": "Cinematic visual prompt for Veo 3 (9:16 vertical, dynamic lighting) or Imagen 3 (1:1 clean tech graphic).",
  "platform_captions": {
    "short_form": "Hook-first caption optimized for TikTok, Instagram Reels, and Facebook Reels with 4-5 hashtags.",
    "microblog": "Dense, insight-rich summary optimized for X and Threads under 280 characters, including the source link."
  }
}
```

---

## 5. Dispatch & HITL Procedures

1. **Asset Staging**: Call `social-dispatcher/upload_media_to_r2` with local render.
2. **Database Logging**: Call `sqlite-history/write_query` to record post in `pending` state.
3. **HITL Review**: Call `social-dispatcher/send_telegram_approval` to present the interactive review card. Never publish directly to social networks without callback approval.
