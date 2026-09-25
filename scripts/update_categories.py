import sqlite3

def update_db(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Update existing formats
    c.execute("UPDATE posts SET format_type = 'reel' WHERE id IN (1, 2)")
    c.execute("UPDATE posts SET format_type = 'post' WHERE id = 3")
    c.execute("UPDATE posts SET format_type = 'reel' WHERE id = 4")
    
    # Check if story exists
    c.execute("SELECT COUNT(*) FROM posts WHERE format_type = 'story'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO posts (
                source_url, headline, format_type, media_url, approval_status,
                hook_narration, body_narration, call_to_action, visual_prompt,
                captions_json, verification_token
            ) VALUES (
                'https://openai.com/index/introducing-operator',
                'OpenAI Operator: Autonomous Browser Control Enters Beta',
                'story',
                'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=1080&q=80',
                'pending',
                'Autonomous web browsing just went mainstream with OpenAI Operator.',
                'OpenAI has officially launched Operator in developer preview. The model runs continuous multi-step browser execution inside Chrome, completing complex enterprise research, form submissions, and data verification autonomously.',
                'Would you trust an autonomous agent to manage your travel bookings and credit card checkouts?',
                '9:16 vertical modern neon-lit glassmorphic tech card showing autonomous browser agent navigation steps',
                '{"short_form": "⚡ 24H TECH STORY: OpenAI Operator autonomous browser agent is in beta. Here is what it changes for RPA. #AI #Operator #OpenAI #TechStory #Reels", "microblog": "OpenAI Operator agent begins closed beta: autonomous web browser control and multi-step action execution."}',
                '7f8849201bdca281048892ca'
            )
        """)
    
    conn.commit()
    c.execute("SELECT id, headline, format_type, approval_status FROM posts")
    rows = c.fetchall()
    conn.close()
    return rows

print("Updating published_history.db:")
print(update_db("storage/published_history.db"))
print("\nUpdating seed_history.db:")
print(update_db("storage/seed_history.db"))
