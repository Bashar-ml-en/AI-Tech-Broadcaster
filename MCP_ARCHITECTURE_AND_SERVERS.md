# MCP Architecture & Server Specifications
**Target Runtime:** Google Antigravity 2.0  
**Protocol:** Model Context Protocol (MCP) over Stdio (JSON-RPC 2.0)

---

## 1. Overview & Protocol Lifecycle

In Google Antigravity 2.0, external tools and databases are exposed to agents via the **Model Context Protocol (MCP)**. This system runs 3 dedicated MCP services via `src/mcp_social_server.py`, configured in `.agents/mcp_config.json`:

```
+-------------------------------------------------------------+
|                Google Antigravity 2.0 Agent                 |
|             (Gemini 2.0 Flash Director Engine)              |
+-------------------------------------------------------------+
                               |
               Stdio JSON-RPC 2.0 (Stdin / Stdout)
                               |
       +-----------------------+-----------------------+
       |                       |                       |
       v                       v                       v
+---------------+      +---------------+      +-------------------+
| sqlite-history|      |  web-fetcher  |      | social-dispatcher |
|  MCP Server   |      |  MCP Server   |      |    MCP Server     |
+---------------+      +---------------+      +-------------------+
       |                       |                       |
       v                       v                       v
storage/published_    Primary Web Sources     Cloudflare R2, Telegram
    history.db         (DeepMind, ArXiv)       HITL Gate & Ayrshare
```

### Stdio Transport Protocol Lifecycle
1. **`initialize`**: Agent sends protocol version (`2024-11-05`) and client capabilities. The server responds with server metadata and tool capabilities.
2. **`notifications/initialized`**: Notification acknowledging handshake.
3. **`tools/list`**: Agent requests the list of registered tools and their JSON schemas.
4. **`tools/call`**: Agent invokes a tool by name with structured arguments; server executes the handler and returns a `content` array with text/json results.

---

## 2. Server 1: `sqlite-history`

The `sqlite-history` server maintains deterministic deduplication and audit records in `storage/published_history.db`.

### Tool: `sqlite-history/read_query`
Executes safe read-only SQL queries against the local history database.

- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string", "description": "SQL SELECT query to execute" },
    "params": { "type": "object", "description": "Named query parameters" }
  },
  "required": ["query"]
}
```

- **Canonical Queries**:
```sql
-- 1. Exact URL deduplication
SELECT id, headline, approval_status 
FROM posts 
WHERE source_url = :source_url 
LIMIT 1;

-- 2. 14-day sliding window subject deduplication
SELECT id, headline, created_at 
FROM posts 
WHERE (source_url = :source_url OR headline LIKE :subject_pattern) 
  AND created_at >= datetime('now', '-14 days');
```

- **Output Structure**:
```json
[
  {
    "id": 1,
    "headline": "Gemini 2.0 Flash Beats Benchmarks",
    "approval_status": "pending"
  }
]
```

---

### Tool: `sqlite-history/write_query`
Executes state-mutating SQL statements (`INSERT` or `UPDATE`).

- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string", "description": "SQL INSERT or UPDATE statement" },
    "params": { "type": "object", "description": "Named query parameters" }
  },
  "required": ["query"]
}
```

- **Canonical Queries**:
```sql
-- Staging insert:
INSERT INTO posts (source_url, headline, format_type, media_url, approval_status) 
VALUES (:source_url, :headline, :format_type, :media_url, 'pending');

-- Publication update:
UPDATE posts 
SET approval_status = :status, published_at = CURRENT_TIMESTAMP 
WHERE source_url = :source_url;
```

- **Output Structure**:
```json
{
  "status": "success",
  "rows_affected": 1,
  "last_row_id": 2
}
```

---

## 3. Server 2: `web-fetcher`

The `web-fetcher` server retrieves primary documentation directly from official AI lab announcements and ArXiv to prevent hallucinations.

### Tool: `web-fetcher/fetch`
Fetches raw HTML/text, strips scripts/nav elements, and formats clean technical text preserving benchmark tables and architecture specs.

- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "url": { "type": "string", "description": "Primary documentation URL to fetch" }
  },
  "required": ["url"]
}
```

- **Output Structure**:
```json
{
  "url": "https://deepmind.google/models/gemini/",
  "title": "Gemini - Google DeepMind",
  "status": 200,
  "content": "Gemini 2.0 Flash delivers high throughput... Benchmark scores: SWE-bench +14.2%...",
  "length": 14205
}
```

---

## 4. Server 3: `social-dispatcher`

The `social-dispatcher` server handles asset staging, human review orchestration, and multi-network publishing.

### Tool: `social-dispatcher/upload_media_to_r2`
Uploads local renders (`output_clip.mp4` or `output_graphic.png`) to Cloudflare R2 and returns the public CDN URL.

- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "file_path": { "type": "string", "description": "Local path to rendered media asset" },
    "destination_key": { "type": "string", "description": "Optional custom S3 object key" }
  },
  "required": ["file_path"]
}
```

- **Output Structure**:
```json
{
  "status": "success",
  "media_url": "https://cdn.broadcaster.ai/renders/output_clip_1790331058.mp4",
  "local_file": "storage/staging/output_clip_1790331058.mp4"
}
```

---

### Tool: `social-dispatcher/send_telegram_approval`
Dispatches an interactive Telegram card to the editorial channel with cryptographic HMAC authentication and inline action buttons.

- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "post_id": { "type": "integer" },
    "headline": { "type": "string" },
    "format_type": { "type": "string", "enum": ["video", "text_image"] },
    "media_url": { "type": "string" },
    "hook_narration": { "type": "string" },
    "body_narration": { "type": "string" },
    "call_to_action": { "type": "string" },
    "platform_captions": { "type": "object" }
  },
  "required": ["post_id", "headline", "format_type", "media_url", "hook_narration", "body_narration", "call_to_action", "platform_captions"]
}
```

- **Output Structure**:
```json
{
  "status": "pending_approval",
  "post_id": 2,
  "token": "d6448c2cc15b0f93794aba4c",
  "telegram_dispatched": true,
  "review_url": "http://localhost:8080/review/2"
}
```

---

### Tool: `social-dispatcher/publish_to_networks`
Publishes approved content across TikTok, Instagram Reels, Facebook Reels, Threads, and X via Ayrshare with mandatory `"is_aigc": true`.

- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "post_id": { "type": "integer", "description": "Database record ID of approved post" }
  },
  "required": ["post_id"]
}
```

- **Output Structure**:
```json
{
  "status": "published",
  "post_id": 2,
  "ayrshare_id": "ayr_908123841",
  "details": {
    "status": "success",
    "postIds": {
      "tiktok": "mock_tiktok_98213",
      "instagram": "mock_ig_49182",
      "facebook": "mock_fb_71294",
      "threads": "mock_threads_88123",
      "twitter": "mock_x_109283"
    }
  }
}
```

---

## 5. Configuration Manifest (`.agents/mcp_config.json`)

```json
{
  "mcpServers": {
    "sqlite-history": {
      "command": "python",
      "args": ["src/mcp_social_server.py", "--service", "sqlite-history"],
      "env": { "PYTHONUNBUFFERED": "1" }
    },
    "web-fetcher": {
      "command": "python",
      "args": ["src/mcp_social_server.py", "--service", "web-fetcher"],
      "env": { "PYTHONUNBUFFERED": "1" }
    },
    "social-dispatcher": {
      "command": "python",
      "args": ["src/mcp_social_server.py", "--service", "social-dispatcher"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

---

## 6. Self-Test & Diagnostic Commands

Run internal unit verification of all registered MCP tools:
```powershell
.venv\Scripts\python.exe src/mcp_social_server.py --test
```
