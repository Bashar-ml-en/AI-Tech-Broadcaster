---
name: omnichannel-publisher
description: Diagnose, heal, and publish AI news broadcasts across Telegram, TikTok Content Posting API v2, Facebook Pages, Instagram Reels/Carousels, and Meta Threads using PublishingSubagentOrchestrator.
---

# Omnichannel Publisher & Reach-Recovery Skill

Use this skill whenever the user wants to inspect which posts reached or did not reach a social channel, repair failed broadcasts, configure platform tokens, or trigger live omnichannel publishing.

## Key Entry Points (`src/publishing_subagent.py`)

```python
from src.publishing_subagent import PublishingSubagentOrchestrator

orchestrator = PublishingSubagentOrchestrator()

# 1. Summary across all 5 channels (Telegram, TikTok, Facebook, Instagram, Threads)
summary = orchestrator.get_all_platforms_reach_summary()

# 2. Detailed Reach Ledger (reached_posts + unreached_posts + diagnosis) for one platform
ledger = orchestrator.get_platform_reach_ledger("tiktok")

# 3. Auto-heal & publish a specific unreached post
result = orchestrator.heal_and_publish_post(post_id=34, platform="telegram", force_live=True)

# 4. Batch sync unreached queue for a platform
batch = orchestrator.sync_unreached_queue(platform="facebook", limit=3)
```

## Web Console API Endpoints (`src/webhook_server.py`)
- `GET /api/platforms/reach`: Live Reached/Unreached summary across all 5 platforms.
- `GET /api/platforms/{platform}/ledger`: Full Reach Ledger for `telegram`, `tiktok`, `facebook`, `instagram`, or `threads`.
- `POST /api/platforms/{platform}/publish/{post_id}`: One-click Auto-Heal & Live Publish.
- `POST /api/platforms/{platform}/sync`: Batch heal & sync unreached posts.
- `POST /api/platforms/configure`: Hot-reload platform API tokens into `config/.env` and live process memory.
