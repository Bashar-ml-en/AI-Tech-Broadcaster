---
name: news-scraper
description: Harvest breakthrough updates across AI and computing, execute 14-day deterministic deduplication via sqlite-history, and verify qualification thresholds.
---

# News Scraper & Grounded Technical Filter Skill

This skill guides the autonomous agent in monitoring, harvesting, deduplicating, and qualifying high-impact technical releases across artificial intelligence, computing, and robotics.

## Priority Source Tiers

Evaluate candidate announcements in strict descending order of authority:
1. **Tier 1 (Primary AI Labs)**:
   - Google DeepMind Blog (`https://deepmind.google/discover/blog/`)
   - OpenAI Newsroom (`https://openai.com/news/`)
   - Anthropic Research Updates (`https://www.anthropic.com/research`)
   - Meta AI Research (`https://ai.meta.com/blog/`)
   - Hugging Face Model Releases (`https://huggingface.co/blog`)
2. **Tier 2 (Academic & Code Releases)**:
   - ArXiv preprints in `cs.AI`, `cs.CL`, `cs.CV` (`https://rss.arxiv.org/rss/cs.AI`)
   - GitHub Trending AI/ML Repositories (`https://github.com/trending?since=daily`)
3. **Tier 3 (Tier-1 Tech Publications)**:
   - TechCrunch AI (`https://techcrunch.com/category/artificial-intelligence/`)
   - Ars Technica AI (`https://arstechnica.com/tag/ai/`)
   - VentureBeat AI & The Verge

---

## Operating Procedure

### Step 1: 14-Day Deterministic Deduplication
Before spending tokens or drafting copy, check the local database via `sqlite-history/read_query`:
```sql
SELECT id, headline, approval_status, created_at 
FROM posts 
WHERE source_url = :source_url 
   OR (headline LIKE :headline_pattern AND created_at >= datetime('now', '-14 days'))
LIMIT 1;
```
If a record exists, immediately skip to the next candidate.

### Step 2: Primary Documentation Context Extraction
Invoke `web-fetcher/fetch` on the candidate source URL:
```json
{
  "url": "https://official-lab-domain.com/announcement"
}
```
Examine raw text, tables, and metrics. Discard any secondary aggregator claims or blog rumors.

### Step 3: Technical Qualification Threshold Verification
The story must satisfy at least one of the three non-negotiable criteria:
1. **Quantifiable Capability Leap**: Statistically significant benchmark advancement (>5% gain on SWE-bench, MMLU, GSM8K, HumanEval, etc.).
2. **Public Weight / Endpoint Availability**: Immediate API general availability (GA), public open-weights repository (e.g. HuggingFace link), or model checkpoints.
3. **Breakthrough Developer Tooling**: A production-ready utility, compiler, inference runtime, or agent framework solving a critical developer bottleneck.

### Step 4: Hand-off to Media Director
Once verified and qualified, pass the verified primary source text, URL, and quantitative metrics to the `media-director` skill.
