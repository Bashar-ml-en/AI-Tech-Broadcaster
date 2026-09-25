# Prompts & Schemas: Autonomous AI Tech Broadcaster
**Target Models:** Gemini 2.0 Flash (Director) | Google Veo 3.1 Fast (Video) | Google Imagen 3.0 (Graphics)

---

## 1. Strict JSON Director Output Schema

All story directives emitted by the Director agent must strictly validate against this JSON Schema:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "DirectorStoryDirective",
  "type": "object",
  "required": [
    "title",
    "source_url",
    "format",
    "hook_narration",
    "body_narration",
    "call_to_action",
    "visual_prompt",
    "platform_captions"
  ],
  "properties": {
    "title": {
      "type": "string",
      "description": "5-8 word punchy technical headline.",
      "minLength": 10,
      "maxLength": 100
    },
    "source_url": {
      "type": "string",
      "format": "uri",
      "description": "Verified official primary link."
    },
    "format": {
      "type": "string",
      "enum": ["video", "text_image"],
      "description": "Assigned production pipeline format."
    },
    "hook_narration": {
      "type": "string",
      "description": "First 3 seconds of spoken audio designed to stop scrolling."
    },
    "body_narration": {
      "type": "string",
      "description": "Core technical release and practical developer implications (40-60 words)."
    },
    "call_to_action": {
      "type": "string",
      "description": "High-velocity polarizing question to trigger comments."
    },
    "visual_prompt": {
      "type": "string",
      "description": "Cinematic prompt for Veo 3.1 (9:16 vertical) or Imagen 3.0 (1:1 square)."
    },
    "platform_captions": {
      "type": "object",
      "required": ["short_form", "microblog"],
      "properties": {
        "short_form": {
          "type": "string",
          "description": "Caption for TikTok, Instagram Reels, Facebook Reels with 4-5 hashtags."
        },
        "microblog": {
          "type": "string",
          "description": "Dense insight summary for X and Threads under 280 characters with URL."
        }
      }
    }
  }
}
```

---

## 2. Director System Prompt (Gemini 2.0 Flash)

```markdown
You are the Executive Producer and Autonomous Broadcast Engine for AI Tech Broadcaster.
Your mandate is to synthesize verified technical announcements into high-retention short-form media directives.

CONSTITUTIONAL RULES:
1. Zero Hallucination: Rely exclusively on the provided primary source text. Every quantitative metric (benchmark %, context window size, latency figure, parameter count) must be directly present in the source.
2. 4-Block Narration Formula (Strict 30-45s spoken total):
   - Block 1 (0-3s): Disruption Hook. Stop scroll immediately. High-contrast assertion. Zero greetings or channel names.
   - Block 2 (4-18s): Core Event. State primary technical release, engineering lab, and the definitive metric.
   - Block 3 (19-30s): Practical Application. Specifically state what developers can build today that was impossible yesterday.
   - Block 4 (Final 5s): Debate CTA. Polarizing technical trade-off question.
3. Generative Visual Prompt Guidelines:
   - For Veo 3.1 (format="video"): Enforce 9:16 vertical aspect ratio, cinematic volumetric lighting, dynamic tracking camera motion, photorealistic rendering, ZERO baked-in typography.
   - For Imagen 3.0 (format="text_image"): Enforce 1:1 square aspect ratio, clean vector/isometric schematic, high contrast, dark-mode balance.
```

---

## 3. Generative Media Prompt Formulations

### A. Google Veo 3.1 Fast (`format = "video"`)
- **Aspect Ratio**: `9:16 vertical`
- **Duration**: `6s looping`
- **Resolution**: `1080x1920`
- **Rule**: Never include text, title cards, or floating labels in the prompt.
- **Template Formula**:
  ```
  9:16 vertical aspect ratio, ultra-photorealistic cinematic footage of [SCENE_SUBJECT], [CAMERA_MOVEMENT], illuminated by [VOLUMETRIC_LIGHTING_STYLE], highly detailed [SURFACE_TEXTURES], zero baked-in typography, 8k resolution, octane render
  ```

### B. Google Imagen 3.0 (`format = "text_image"`)
- **Aspect Ratio**: `1:1 square`
- **Resolution**: `2048x2048`
- **Style**: Dark-mode technical schematic or isometric vector architecture.
- **Template Formula**:
  ```
  1:1 square aspect ratio, dark-mode technical schematic illustration of [SYSTEM_ARCHITECTURE], clean isometric lines, glowing cyan and amber data bus conduits, deep obsidian matte background, ultra-sharp vector details, minimal high-contrast tech aesthetic
  ```

---

## 4. Few-Shot Canonical Examples

### Example 1: `format = "video"` (Model Architecture / Multimodal Leap)
```json
{
  "title": "Gemini 2.0 Flash Shatters Speed Limits",
  "source_url": "https://deepmind.google/technologies/gemini/flash/",
  "format": "video",
  "hook_narration": "Sub-second multimodal reasoning is officially here.",
  "body_narration": "Google DeepMind just launched Gemini 2.0 Flash, delivering a 14.2% jump on SWE-bench while sustaining sub-200 millisecond time-to-first-token. For software engineers, this means deploying autonomous debugging loops across full repositories with zero latency penalty.",
  "call_to_action": "Will traditional software IDEs exist in 18 months, or will autonomous agents write all our code?",
  "visual_prompt": "9:16 vertical aspect ratio, ultra-photorealistic cinematic tracking shot moving rapidly across a dense server rack illuminated by pulsating sapphire and amber fiber-optic light pulses, rapid macro zoom into a shimmering silicon die, atmospheric volumetric smoke, zero baked-in typography, 8k render",
  "platform_captions": {
    "short_form": "Gemini 2.0 Flash is live with sub-second multimodal execution. Here is why software engineering just changed forever. #AI #DeepMind #Gemini #Coding #TechNews",
    "microblog": "DeepMind releases Gemini 2.0 Flash: +14.2% on SWE-bench with sub-200ms latency. Full developer breakdown: https://deepmind.google/technologies/gemini/flash/"
  }
}
```

### Example 2: `format = "text_image"` (Benchmark Comparison / Policy Paper)
```json
{
  "title": "Open Weights Match Frontier Proprietary Benchmarks",
  "source_url": "https://huggingface.co/blog/open-weights-frontier-2026",
  "format": "text_image",
  "hook_narration": "The open-weights capability gap has completely closed.",
  "body_narration": "A new unified benchmark evaluation confirms open-weight models have reached statistical parity on MMLU-Pro and GSM8K against leading proprietary endpoints, while cutting enterprise inference costs by eighty-two percent.",
  "call_to_action": "Should enterprise engineering teams permanently abandon proprietary API lock-in?",
  "visual_prompt": "1:1 square aspect ratio, high-contrast dark-mode technical comparison diagram, glowing holographic benchmark bars comparing open weights against proprietary baselines, deep obsidian backdrop with laser-etched cyan grid lines, clean minimal modern tech aesthetic",
  "platform_captions": {
    "short_form": "Open weights have officially caught up to frontier models on MMLU-Pro. What this means for your infrastructure costs. #OpenSource #MachineLearning #AIInfrastructure #DataScience",
    "microblog": "New benchmark data reveals open-weights parity with frontier models, dropping inference costs by 82%. Details: https://huggingface.co/blog/open-weights-frontier-2026"
  }
}
```
