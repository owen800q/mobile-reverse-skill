#!/usr/bin/env python3
"""Search the knowledge base. Hybrid BM25 + semantic (if embeddings exist).

Usage:
    python scripts/kb_search.py "your question here" [--top 5] [--json]

Output includes a CONFIDENCE line:
    HIGH   -> results are trustworthy, read the files and answer from them
    LOW    -> weak match; read top files but verify relevance before using
    NONE   -> knowledge base has no relevant article; say so, do NOT guess
"""

from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = SKILL_DIR / "kb" / "index"

TOKEN_RE = re.compile(r"[a-z0-9]+")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
STOPWORDS = frozenset(
    "a an and are as at be by for from has have if in into is it its of on or "
    "that the this to was were will with which what when where who how why not "
    "can could should would do does did you your we our they their".split()
)
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_MAX_TOKENS = 512

# Cosine thresholds are model-specific and must be re-measured if EMBED_MODEL changes.
# Calibrated on this corpus (635 kanxue Android-security threads, CN prose + EN code):
#   relevant queries   min 0.305, median 0.361
#   irrelevant queries max 0.279, median 0.154
# The bge-small-en defaults (0.55/0.42) scored every real query as NONE here.
SEM_HIGH = 0.42
SEM_LOW = 0.30


def tokenize(text: str) -> list[str]:
    """ASCII words plus CJK character bigrams.

    Chinese is written without spaces, so a bare [a-z0-9]+ tokenizer drops it
    entirely.  Indexing every adjacent character pair is the standard dependency-free
    way to make BM25 work on CJK: a 3-char word yields 2 bigrams.  Index and query
    must use this same function or nothing matches.
    """
    low = text.lower()
    toks = [t for t in TOKEN_RE.findall(low) if t not in STOPWORDS and len(t) > 1]
    for run in CJK_RE.findall(low):
        if len(run) == 1:
            toks.append(run)
        else:
            toks.extend(run[i:i + 2] for i in range(len(run) - 1))
    return toks


def ensure_index() -> None:
    if not (CACHE_DIR / "index.pkl").exists():
        print("Index not found — building it first (one-time)...", file=sys.stderr)
        import subprocess

        subprocess.run(
            [sys.executable, str(SKILL_DIR / "scripts" / "kb_build_index.py")], check=True
        )


def rrf(rank_lists: list[list[int]], k: int = 60) -> dict[int, float]:
    """Reciprocal Rank Fusion across multiple ranked lists of doc ids."""
    scores: dict[int, float] = {}
    for ranks in rank_lists:
        for pos, doc_id in enumerate(ranks):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + pos + 1)
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    ensure_index()
    with open(CACHE_DIR / "index.pkl", "rb") as fh:
        idx = pickle.load(fh)
    bm25, meta = idx["bm25"], idx["meta"]
    n = len(meta)
    pool = min(max(args.top * 4, 20), n)

    # --- BM25 ranking ---
    q_tokens = tokenize(args.query)
    bm25_scores = bm25.get_scores(q_tokens) if q_tokens else [0.0] * n
    bm25_rank = sorted(range(n), key=lambda i: bm25_scores[i], reverse=True)[:pool]
    best_bm25 = bm25_scores[bm25_rank[0]] if bm25_rank else 0.0

    rank_lists = [bm25_rank]
    best_cos = None

    # --- Semantic ranking (optional) ---
    emb_file = CACHE_DIR / "embeddings.npy"
    if emb_file.exists():
        try:
            import numpy as np
            from sentence_transformers import SentenceTransformer

            emb = np.load(emb_file)
            model = SentenceTransformer(EMBED_MODEL)   # must match build_index.py
            model.max_seq_length = EMBED_MAX_TOKENS
            q = model.encode([args.query], normalize_embeddings=True)[0]
            cos = emb @ q
            sem_rank = list(np.argsort(-cos)[:pool])
            best_cos = float(cos[sem_rank[0]])
            rank_lists.append([int(i) for i in sem_rank])
        except Exception as e:  # noqa: BLE001
            print(f"(semantic search unavailable: {e})", file=sys.stderr)

    fused = rrf(rank_lists)
    top = sorted(fused, key=fused.get, reverse=True)[: args.top]

    # --- Confidence: is the best match actually relevant? ---
    if best_cos is not None:
        confidence = "HIGH" if best_cos >= SEM_HIGH else ("LOW" if best_cos >= SEM_LOW else "NONE")
    else:
        # BM25-only heuristic: what fraction of query terms appear in the best doc?
        q_set = set(q_tokens)
        coverage = 0.0
        if q_set and top:
            best_doc_tokens = meta[top[0]].get("token_set", frozenset())
            coverage = len(q_set & best_doc_tokens) / len(q_set)
        if best_bm25 <= 0 or not q_set:
            confidence = "NONE"
        elif coverage >= 0.6:
            confidence = "HIGH"
        elif coverage >= 0.3:
            confidence = "LOW"
        else:
            confidence = "NONE"

    results = [
        {
            "rank": r + 1,
            "path": meta[i]["path"],
            "title": meta[i]["title"],
            "bm25": round(float(bm25_scores[i]), 2),
            "preview": meta[i]["preview"][:160],
        }
        for r, i in enumerate(top)
    ]

    if args.json:
        print(json.dumps({"confidence": confidence, "results": results}, indent=2))
        return

    print(f"CONFIDENCE: {confidence}")
    if confidence == "NONE":
        print("No relevant article found in the knowledge base.")
    for r in results:
        print(f"{r['rank']}. [{r['bm25']}] {r['path']}  —  {r['title']}")
        print(f"   {r['preview']}")


if __name__ == "__main__":
    main()
