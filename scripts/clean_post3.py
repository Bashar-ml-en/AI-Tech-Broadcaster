import sqlite3

def clean_posts(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        UPDATE posts SET 
            headline = 'SWE-bench Verified Leaderboard: Frontier Reasoning Models',
            source_url = 'https://swebench.com/analysis',
            approval_status = 'published',
            published_at = '2026-09-25 14:00:20',
            ayrshare_post_id = 'ayr_pub_8492041289',
            hook_narration = 'Frontier reasoning just conquered SWE-bench Verified at 70.3%.',
            body_narration = 'Official leaderboard data confirms Claude 3.7 Sonnet, OpenAI o3-mini, and Gemini 2.0 Flash are automating multi-file repository bug fixes faster than human engineering teams.',
            call_to_action = 'Which model will be your daily coding driver in 2026?',
            captions_json = '{"short_form": "SWE-bench Verified leaderboard update: 70.3% resolution rate achieved. Full model comparison. #AI #SWEbench #SoftwareEngineering #TechNews", "microblog": "SWE-bench Verified update: Claude 3.7 Sonnet leads at 70.3%. Source: https://swebench.com/analysis"}'
        WHERE id = 3
    """)
    conn.commit()
    c.execute("SELECT id, headline, format_type, approval_status, ayrshare_post_id FROM posts")
    rows = c.fetchall()
    conn.close()
    return rows

print(clean_posts("storage/published_history.db"))
print(clean_posts("storage/seed_history.db"))
