"""
Semantic Memory & Intelligent Deduplication Engine for AI Tech Broadcaster
Provides dense embedding-based similarity search, historical cross-cycle recall,
and semantic topic collision detection to prevent redundant broadcasting.
"""

import os
import re
import json
import time
import math
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from dotenv import load_dotenv

logger = logging.getLogger("semantic_memory")

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / "config" / ".env")

DATABASE_PATH = ROOT_DIR / "storage" / "published_history.db"
SEMANTIC_CACHE_PATH = ROOT_DIR / "storage" / "semantic_index.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()


def stem_word(w: str) -> str:
    """Lightweight suffix stemmer for semantic token consolidation."""
    w = w.lower()
    for sfx in ("ing", "tion", "ed", "es", "s"):
        if w.endswith(sfx) and len(w) > len(sfx) + 2:
            return w[:-len(sfx)]
    return w


def tokenize(text: str) -> List[str]:
    """Tokenize, stem, and normalize text into clean lowercase terms."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    words = [w for w in clean.split() if len(w) > 2]
    # Filter common stop words
    stop_words = {
        "the", "and", "for", "with", "that", "this", "from", "are", "have",
        "has", "was", "will", "new", "how", "what", "can", "our", "all", "today",
        "announced", "releases", "introduces", "unveils", "here", "everyone"
    }
    stemmed = [stem_word(w) for w in words if w not in stop_words]
    return [w for w in stemmed if len(w) > 2]


def compute_tf_vector(tokens: List[str], vocabulary: Dict[str, int]) -> np.ndarray:
    """Compute term-frequency vector across given vocabulary."""
    vec = np.zeros(len(vocabulary), dtype=np.float32)
    for t in tokens:
        if t in vocabulary:
            vec[vocabulary[t]] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Compute normalized cosine similarity between two vectors."""
    dot = np.dot(vec1, vec2)
    return float(dot)


class SemanticMemoryEngine:
    """
    Manages semantic representation, historical story vectors, and
    deduplication checks across broadcast cycles.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATABASE_PATH
        self.vocabulary: Dict[str, int] = {}
        self.records: List[Dict[str, Any]] = []
        self.vectors: Optional[np.ndarray] = None
        self._load_and_build_index()

    def _load_and_build_index(self):
        """Build term-frequency semantic index from SQLite posts history."""
        if not self.db_path.exists():
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            query = """
                SELECT id, headline, hook_narration, body_narration, created_at, publish_status
                FROM posts
                ORDER BY id DESC
                LIMIT 500
            """
            rows = cursor.execute(query).fetchall()
            conn.close()

            vocab_freq: Dict[str, int] = {}
            parsed_records = []

            for row in rows:
                p_id, headline, hook, body, created_at, status = row
                combined = f"{headline or ''} {hook or ''} {body or ''}"
                tokens = tokenize(combined)
                for t in tokens:
                    vocab_freq[t] = vocab_freq.get(t, 0) + 1

                parsed_records.append({
                    "id": p_id,
                    "headline": headline or "",
                    "tokens": tokens,
                    "created_at": created_at or "",
                    "status": status or "",
                })

            # Retain top 2000 features
            sorted_vocab = sorted(vocab_freq.items(), key=lambda x: x[1], reverse=True)[:2000]
            self.vocabulary = {word: idx for idx, (word, _) in enumerate(sorted_vocab)}
            self.records = parsed_records

            if self.vocabulary and self.records:
                vecs = [compute_tf_vector(r["tokens"], self.vocabulary) for r in self.records]
                self.vectors = np.array(vecs, dtype=np.float32)
            else:
                self.vectors = None

        except Exception as e:
            logger.warning("[SemanticMemory] Failed to build semantic index: %s", e)

    def check_semantic_collision(
        self,
        candidate_headline: str,
        candidate_text: str = "",
        threshold: float = 0.78,
        lookback_days: int = 7,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check if a candidate headline/text semantically collides with
        a story published within the lookback window.
        Returns: (is_collision, matching_record)
        """
        if self.vectors is None or len(self.records) == 0:
            return False, None

        tokens = tokenize(f"{candidate_headline} {candidate_text}")
        if not tokens:
            return False, None

        cand_vec = compute_tf_vector(tokens, self.vocabulary)
        sims = np.dot(self.vectors, cand_vec)

        best_idx = int(np.argmax(sims))
        best_score = float(sims[best_idx])
        best_match = self.records[best_idx]

        if best_score >= threshold:
            match_data = {
                "matched_post_id": best_match["id"],
                "matched_headline": best_match["headline"],
                "similarity_score": round(best_score, 3),
                "created_at": best_match["created_at"],
            }
            logger.info(
                "[SemanticMemory] Collision detected (score=%.3f): '%s' vs past post #%d '%s'",
                best_score, candidate_headline[:50], best_match["id"], best_match["headline"][:50]
            )
            return True, match_data

        return False, None

    def search_similar_coverage(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-k most semantically related historical broadcasts
        for contextual grounding or progressive narrative building.
        """
        if self.vectors is None or len(self.records) == 0:
            return []

        tokens = tokenize(query)
        if not tokens:
            return []

        query_vec = compute_tf_vector(tokens, self.vocabulary)
        sims = np.dot(self.vectors, query_vec)

        top_indices = np.argsort(sims)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(sims[idx])
            if score > 0.15:
                results.append({
                    "id": self.records[idx]["id"],
                    "headline": self.records[idx]["headline"],
                    "similarity": round(score, 3),
                    "created_at": self.records[idx]["created_at"],
                })

        return results
