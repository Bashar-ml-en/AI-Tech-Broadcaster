# Deployment & Execution Guide: AI Tech Broadcaster
**Target Platform:** Google Antigravity 2.0 (Scheduled Sidecar & MCP Runtime)

---

## 1. Prerequisites & Environment Setup

### System Requirements
- Python 3.11+
- `uv` (recommended) or standard `pip`
- SQLite 3.35+ (with window functions and JSON support)
- Cloudflare R2 bucket with custom public CDN domain
- Telegram Bot Token & Editorial Channel
- Ayrshare API Key (with connected TikTok, Instagram, Facebook, Threads, X accounts)

### Virtual Environment Setup
```powershell
# Create dedicated virtual environment using uv
uv venv .venv

# Install production dependencies
uv pip install -r requirements.txt --python .venv\Scripts\python.exe
```

---

## 2. Configuration & Secrets (`config/.env`)

Copy and configure your secrets in `config/.env`:

```ini
# Runtime Settings
ENVIRONMENT=production
LOG_LEVEL=INFO
SCHEDULE_INTERVAL_HOURS=3

# Storage Paths
DATABASE_PATH=storage/published_history.db
STAGING_DIR=storage/staging
LOGS_DIR=storage/logs

# Cloudflare R2 Object Storage
CLOUDFLARE_R2_ACCOUNT_ID=your_cloudflare_account_id
CLOUDFLARE_R2_ACCESS_KEY_ID=your_r2_access_key_id
CLOUDFLARE_R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
CLOUDFLARE_R2_BUCKET_NAME=broadcaster-staging
CLOUDFLARE_R2_PUBLIC_URL=https://cdn.broadcaster.ai

# Telegram HITL Verification Gate
TELEGRAM_BOT_TOKEN=0000000000:AAExampleTelegramBotTokenHere
TELEGRAM_CHAT_ID=-1001234567890
TELEGRAM_WEBHOOK_SECRET=antigravity_hitl_cryptographic_hmac_secret_2026
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
WEBHOOK_PUBLIC_BASE_URL=https://your-domain-or-tunnel.ngrok.app

# Ayrshare Multi-Platform Social Dispatcher API
AYRSHARE_API_KEY=YOUR_AYRSHARE_API_KEY
AYRSHARE_PROFILE_KEY=

# Google GenAI Settings
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
DIRECTOR_MODEL=gemini-2.0-flash
VEO_MODEL=veo-3.1-fast
IMAGEN_MODEL=imagen-3.0
```

---

## 3. Webhook Tunneling & Telegram Setup

### Step 1: Create Telegram Bot & Channel
1. Open `@BotFather` in Telegram and run `/newbot`.
2. Save the generated `TELEGRAM_BOT_TOKEN`.
3. Create a private Telegram channel (e.g., `Tech Intelligence Editorial Board`) and add your bot as an Administrator with post permissions.
4. Retrieve the channel `TELEGRAM_CHAT_ID` (format `-100xxxxxxxxxx`).

### Step 2: Establish Webhook Tunnel
For public webhook receipt from Telegram:
```powershell
# Expose local port 8080 via ngrok or Cloudflare Tunnel
ngrok http 8080
# Set WEBHOOK_PUBLIC_BASE_URL in config/.env to your ngrok HTTPS URL
```

### Step 3: Register Telegram Webhook
```powershell
$BOT_TOKEN = "YOUR_BOT_TOKEN"
$WEBHOOK_URL = "https://your-domain.ngrok.app/telegram-webhook"
$SECRET_TOKEN = "antigravity_hitl_cryptographic_hmac_secret_2026"

Invoke-RestMethod -Uri "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" `
  -Method Post `
  -ContentType "application/json" `
  -Body (@{
      url = $WEBHOOK_URL
      secret_token = $SECRET_TOKEN
      allowed_updates = @("callback_query", "message")
  } | ConvertTo-Json)
```

---

## 4. Execution & Verification Runbook

### Step 1: MCP Server Diagnostic Self-Test
Verify all 6 tool operations (read_query, write_query, fetch, upload_media_to_r2, send_telegram_approval, publish_to_networks):
```powershell
.venv\Scripts\python.exe src/mcp_social_server.py --test
```
*Expected Output: `ALL MCP TOOLS PASSED SELF-TEST SUCCESSFULLY!`*

### Step 2: Start the HITL Webhook Server
```powershell
.venv\Scripts\python.exe src/webhook_server.py
```
*Liveness Probe:* Visit `http://localhost:8080/health` to confirm `{"status": "healthy"}`.

### Step 3: Execute a Single Broadcast Cycle (Run-Once)
```powershell
.venv\Scripts\python.exe src/pipeline.py --run-once
```
*Execution Flow:*
1. Scrapes Tier 1 AI lab feeds (DeepMind, OpenAI, Anthropic, Meta, HuggingFace) and Tier 2 ArXiv/GitHub.
2. Checks `storage/published_history.db` to guarantee 14-day deduplication.
3. Validates against qualification thresholds (>5% benchmark gain, public weights, developer tooling).
4. Routes format to Veo 3.1 Fast (`video`) or Imagen 3.0 (`text_image`).
5. Synthesizes strict JSON Director payload with 4-block narration.
6. Renders media and stages to Cloudflare R2 CDN.
7. Logs `pending` record in SQLite and sends interactive Telegram card with HMAC cryptographic nonce.
8. Provides local review fallback link: `http://localhost:8080/review/<post_id>`.

### Step 4: Test Human-in-the-Loop Approval
- **Via Telegram**: Click `[✅ Approve & Post Globally]` on the received message card.
- **Via Local Browser**: Open `http://localhost:8080/review/<post_id>` and click `Approve & Post Globally`.
- The webhook verifies HMAC authenticity, posts to TikTok, Instagram Reels, Facebook Reels, Threads, and X via Ayrshare with `"is_aigc": true`, and updates database status to `published`.

### Step 5: Continuous 3-Hour Antigravity Sidecar Mode
To run the automated autonomous background daemon:
```powershell
.venv\Scripts\python.exe src/pipeline.py --sidecar
```

---

## 5. Google Antigravity 2.0 Sidecar Scheduling

Within Antigravity 2.0, the broadcaster is managed either via:
1. **Antigravity Left-Hand Sidebar > Scheduled Tasks**: Add recurring cron task with schedule `0 */3 * * *` invoking `social-broadcaster`.
2. **Antigravity CLI**:
   ```bash
   agy task create --name "tech-broadcaster" --schedule "0 */3 * * *" --agent "social-broadcaster"
   ```
3. **Chat Directive**: Trigger ad-hoc runs or monitor status via `/schedule` or direct prompt.

---

## 6. Health Checks & Circuit Breakers

| Failure Mode | Detection | Automated Recovery Action |
| :--- | :--- | :--- |
| Primary Feed Timeout | HTTP 5xx / Timeout | Automatic fallback to next source in priority tier |
| Duplicate Story | SQLite 14-day lookback | Immediate drop before invoking Director model |
| Webhook Expiry / Inactivity | Unanswered card | Auto-marked as `discarded` after TTL; cleanly terminates |
| Ayrshare API Error | HTTP 4xx/5xx | Retries 3x with exponential backoff; notifies Telegram editor |
| Corrupt Media Render | Missing header bytes | Re-renders fallback high-resolution asset before staging |
