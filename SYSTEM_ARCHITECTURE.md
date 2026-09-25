# System Architecture: Autonomous AI Tech Broadcaster
**Target Runtime:** Google Antigravity 2.0 (Scheduled Sidecar & MCP Architecture)  
**Target Models:** Gemini 2.0 Flash (Director) | Google Veo 3.1 Fast / Imagen 3.0 (Media Generation)

---

## 1. Executive Summary & Architectural Overview

The **Autonomous AI Tech Broadcaster** is an enterprise-grade agentic broadcasting engine operating natively within Google Antigravity 2.0. Every 3 hours, a scheduled sidecar awakens the Director agent, which monitors primary technical research from tier-1 AI laboratories, academics, and code repositories. Qualified breakthroughs are verified against primary documentation, synthesized into high-retention short-form media directives, staged to Cloudflare R2, and held behind a cryptographically secured Human-in-the-Loop (HITL) Telegram authorization gate before global distribution across TikTok, Instagram Reels, Facebook Reels, Threads, and X via Ayrshare.

```mermaid
flowchart TD
    subgraph S1["Scheduled Ingestion & Qualification (Every 3 Hours)"]
        Cron["Antigravity Sidecar Cron (0 */3 * * *)"] --> Scraper["Tier 1/2/3 Feed Harvester"]
        Scraper --> Dedup["14-Day Deduplication Gate<br/>(storage/published_history.db)"]
        Dedup --> Fetcher["web-fetcher MCP<br/>(Primary Grounded Docs)"]
        Fetcher --> Qualify{"Qualification Filter<br/>>5% Leap | Weights | Tooling"}
    end

    subgraph S2["Director Synthesis & Asset Staging"]
        Qualify -- Qualified --> Director["Gemini 2.0 Flash Director<br/>(Strict JSON Schema)"]
        Director --> Routing{"Format Routing Matrix"}
        Routing -- "Dynamic Demo / Robotics" --> Veo["Google Veo 3.1 Fast (9:16 Video)"]
        Routing -- "Benchmark / Schematics" --> Imagen["Imagen 3.0 (1:1 Graphic)"]
        Veo --> Stager["R2 Object Storage & CDN"]
        Imagen --> Stager
    end

    subgraph S3["Human-in-the-Loop (HITL) Verification Gate"]
        Stager --> DBLog["sqlite-history MCP (Pending Post)"]
        DBLog --> HMAC["HMAC-SHA256 Token Generator"]
        HMAC --> TG["Telegram Interactive Card<br/>[✅ Approve] [❌ Discard]"]
        TG --> Webhook["FastAPI HITL Webhook Server"]
    end

    subgraph S4["Global Social Dispatch"]
        Webhook -- "HMAC Verified: Approve" --> Ayrshare["Ayrshare Social API<br/>('is_aigc': true)"]
        Ayrshare --> TT["TikTok"]
        Ayrshare --> IG["Instagram Reels"]
        Ayrshare --> FB["Facebook Reels"]
        Ayrshare --> TH["Threads"]
        Ayrshare --> X["X (Twitter)"]
        Webhook -- "HMAC Verified: Discard" --> Discard["Mark 'discarded' in SQLite<br/>Clean Session Termination"]
    end
```

---

## 2. Core Architectural Pillars

### Pillar 1: Constitutional Invariants & Zero Hallucination
- **Grounded Verification**: All claims, context window sizes, parameter counts, and benchmark percentages must be extracted directly from official primary announcements (DeepMind, OpenAI, Anthropic, Meta AI, ArXiv preprints). Secondary social rumors and financial speculation are strictly blocked.
- **Deterministic Deduplication**: A 14-day lookback window in `storage/published_history.db` guarantees that duplicate URLs or overlapping technical subjects are discarded prior to script generation.
- **HITL Authorization Lock**: Under no circumstances can assets be published without explicit cryptographic approval through Telegram callback queries.

### Pillar 2: Information Harvesting & Selection Hierarchy

```mermaid
graph TD
    T1["Tier 1: Primary AI Labs (Highest Priority)"] --> D1["DeepMind, OpenAI, Anthropic, Meta AI, Hugging Face"]
    T2["Tier 2: Academic & Code Releases"] --> D2["ArXiv (cs.AI, cs.CL, cs.CV), GitHub Trending AI"]
    T3["Tier 3: Tier-1 Tech Publications"] --> D3["TechCrunch AI, Ars Technica, VentureBeat, The Verge"]
```

A story is qualified if and only if it passes at least one qualification threshold:
1. **Quantifiable Capability Leap**: Statistically significant benchmark advancement (>5% gain on SWE-bench, MMLU, GSM8K, etc.).
2. **Public Weight / Endpoint Availability**: Open-weights release (Hugging Face / GitHub) or immediate API general availability.
3. **Breakthrough Developer Tooling**: A production-ready framework, compiler, or runtime that resolves active software engineering bottlenecks.

### Pillar 3: Format Routing & Retention Engineering
The Director routes stories into two production pipelines based on content type:
- **`format = "video"`**: Dynamic software demonstrations, robotics, code execution screencasts, or multimodal model capabilities. Rendered as 9:16 vertical MP4 (6s) via Google Veo 3.1 Fast with TTS narration.
- **`format = "text_image"`**: Benchmark comparison matrices, system architecture schematics, safety/policy papers, or API pricing updates. Rendered as 1:1 square graphic via Imagen 3.0.

Narration pacing strictly follows the **4-Block Pacing Model (30–45s total)**:
- **Block 1 (0–3s)**: Disruption Hook (zero greetings, bold high-contrast claim).
- **Block 2 (4–18s)**: Core Event (release, team, primary metric).
- **Block 3 (19–30s)**: Practical Application (what developers can build today).
- **Block 4 (Final 5s)**: Debate Call to Action (polarizing technical question).

---

## 3. Cryptographic Security Model (Telegram HITL Gate)

To prevent spoofed approvals, accidental callbacks, or replay attacks, the HITL approval gate employs a tamper-proof HMAC-SHA256 signature scheme:

```mermaid
sequenceDiagram
    autonumber
    participant Pipeline as Broadcast Pipeline
    participant DB as SQLite History DB
    participant TG as Telegram Bot API
    participant Editor as Human Editor
    participant Webhook as HITL Webhook Server
    participant Ayrshare as Ayrshare API

    Pipeline->>DB: INSERT post (status='pending') -> returns post_id
    Pipeline->>Pipeline: Compute HMAC_SHA256(secret, source_url + ":" + post_id)
    Pipeline->>DB: Store token in posts table
    Pipeline->>TG: Send card with inline buttons (data: approve/discard:token:post_id)
    TG->>Editor: Render Interactive Message Card
    Editor->>TG: Clicks [✅ Approve & Post Globally]
    TG->>Webhook: POST /telegram-webhook (callback_query with data)
    Webhook->>DB: SELECT source_url, approval_status, token FROM posts WHERE id = post_id
    Webhook->>Webhook: Validate HMAC(token, secret) & Check status == 'pending'
    alt Valid & Pending
        Webhook->>Ayrshare: POST /api/post ("is_aigc": true, mediaUrls, platforms)
        Ayrshare-->>Webhook: 200 OK (postIds)
        Webhook->>DB: UPDATE posts SET approval_status='published', published_at=NOW()
        Webhook->>TG: Edit message: "✅ PUBLISHED GLOBALLY"
    else Invalid / Replay / Discarded
        Webhook->>TG: Answer callback: "Unauthorized / Discarded"
    end
```

---

## 4. State Transition Machine

```mermaid
stateDiagram-v2
    [*] --> Harvested : Scraper discovers candidate
    Harvested --> Deduplicated : 14-day DB check passes
    Harvested --> Discarded : Already covered in last 14 days
    Deduplicated --> Qualified : Meets benchmark/weights/tooling criteria
    Deduplicated --> Discarded : Below threshold
    Qualified --> Staged : Director synthesizes JSON & renders asset to R2
    Staged --> PendingReview : Telegram card dispatched with HMAC token
    PendingReview --> Published : Human approves via Telegram / Webhook (Ayrshare posted)
    PendingReview --> Discarded : Human clicks [❌ Discard] or webhook times out
    Published --> [*]
    Discarded --> [*]
```

---

## 5. Storage & Database Schema (`storage/published_history.db`)

The SQLite database acts as the single source of truth for deduplication and audit logging:

```sql
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url TEXT UNIQUE NOT NULL,
    headline TEXT NOT NULL,
    format_type TEXT NOT NULL,             -- 'video' | 'text_image'
    media_url TEXT,                         -- Cloudflare R2 Public CDN URL
    approval_status TEXT NOT NULL DEFAULT 'pending', -- 'pending' | 'approved' | 'discarded' | 'published'
    hook_narration TEXT,
    body_narration TEXT,
    call_to_action TEXT,
    visual_prompt TEXT,
    captions_json TEXT,                     -- Platform captions (short_form, microblog)
    post_payload TEXT,                      -- Complete JSON Director directive
    telegram_message_id INTEGER,
    verification_token TEXT,               -- HMAC cryptographic verification token
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    published_at DATETIME,
    ayrshare_post_id TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_source_url ON posts(source_url);
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts(created_at);
CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(approval_status);
```

---

## 6. Regulatory AI Disclosure Compliance

In accordance with international AI safety and transparency directives (EU AI Act, FTC synthetic media guidelines, platform terms of service), all dispatched posts include:
1. Native API flag: `"is_aigc": true` passed directly to Ayrshare.
2. Machine-readable watermarking: Veo 3.1 synthID metadata preservation.
3. Spoken and caption attribution: Clear disclosure of synthetic video and generative media assistance in social captions.
