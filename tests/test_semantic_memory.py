"""
Unit tests for Semantic Memory & Intelligent Deduplication Engine
"""

import sqlite3
import numpy as np
from src.semantic_memory import (
    tokenize,
    compute_tf_vector,
    cosine_similarity,
    SemanticMemoryEngine,
)


def test_tokenize():
    text = "OpenAI introduces ChatGPT's new Wallet feature for agents today!"
    tokens = tokenize(text)
    assert "openai" in tokens
    assert "chatgpt" in tokens
    assert "wallet" in tokens
    assert "agent" in tokens
    # Stop words filtered
    assert "today" not in tokens
    assert "for" not in tokens


def test_tf_vector_and_cosine():
    vocab = {"apple": 0, "banana": 1, "cherry": 2}
    v1 = compute_tf_vector(["apple", "banana"], vocab)
    v2 = compute_tf_vector(["apple", "banana"], vocab)
    v3 = compute_tf_vector(["cherry"], vocab)

    sim12 = cosine_similarity(v1, v2)
    sim13 = cosine_similarity(v1, v3)

    assert np.isclose(sim12, 1.0)
    assert np.isclose(sim13, 0.0)


def test_semantic_engine_collision_detection(tmp_path):
    db_file = tmp_path / "published_history.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "CREATE TABLE posts (id INTEGER PRIMARY KEY, headline TEXT, hook_narration TEXT, body_narration TEXT, created_at TEXT, publish_status TEXT)"
    )
    conn.execute(
        "INSERT INTO posts (id, headline, hook_narration, body_narration, created_at, publish_status) "
        "VALUES (101, 'ChatGPT Wallet feature allows agents to shop', 'Hey everyone Sam Altman here', 'Agents can buy products', '2026-11-14', 'published')"
    )
    conn.commit()
    conn.close()

    engine = SemanticMemoryEngine(db_path=db_file)

    # Similar story should collide
    collided, match = engine.check_semantic_collision(
        candidate_headline="ChatGPT Wallet enables autonomous agent checkout shopping",
        threshold=0.60
    )
    assert collided is True
    assert match is not None
    assert match["matched_post_id"] == 101

    # Completely different story should not collide
    unrelated_collided, unrelated_match = engine.check_semantic_collision(
        candidate_headline="Nvidia Blackwell B200 NVLink liquid cooling architecture",
        threshold=0.60
    )
    assert unrelated_collided is False
    assert unrelated_match is None


def test_semantic_search(tmp_path):
    db_file = tmp_path / "published_history.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute(
        "CREATE TABLE posts (id INTEGER PRIMARY KEY, headline TEXT, hook_narration TEXT, body_narration TEXT, created_at TEXT, publish_status TEXT)"
    )
    conn.execute(
        "INSERT INTO posts (id, headline, hook_narration, body_narration, created_at, publish_status) "
        "VALUES (201, 'Google DeepMind AlphaFold3 Biomolecular Predictions', 'Demis here', 'Predicts protein ligand complexes', '2026-11-10', 'published')"
    )
    conn.execute(
        "INSERT INTO posts (id, headline, hook_narration, body_narration, created_at, publish_status) "
        "VALUES (202, 'Meta Llama 3.3 70B Open Source Release', 'Mark Zuckerberg here', 'New open weights model', '2026-11-11', 'published')"
    )
    conn.commit()
    conn.close()

    engine = SemanticMemoryEngine(db_path=db_file)
    results = engine.search_similar_coverage("AlphaFold protein molecular structure", top_k=2)
    assert len(results) >= 1
    assert results[0]["id"] == 201
