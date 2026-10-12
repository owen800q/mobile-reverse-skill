#!/usr/bin/env python3
"""Build the search index for the knowledge base.

Creates kb/index/index.pkl (BM25) and optionally kb/index/embeddings.npy
(semantic vectors, if sentence-transformers is installed).

Usage:
    python scripts/kb_build_index.py            # incremental (only if files changed)
    python scripts/kb_build_index.py --force    # full rebuild
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ARTICLES_DIR = SKILL_DIR / "kb" / "articles"
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


def extract_title(text: str, fallback: str) -> str:
    # YAML frontmatter title
    if text.startswith("---"):
        m = re.search(r"^title:\s*(.+)$", text[:2000], re.MULTILINE)
        if m:
            return m.group(1).strip().strip("\"'")
    # First markdown heading
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return fallback


def corpus_fingerprint(files: list[Path]) -> str:
    h = hashlib.sha256()
    for f in sorted(files):
        st = f.stat()
        h.update(f"{f.name}:{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force full rebuild")
    args = parser.parse_args()

    files = sorted(ARTICLES_DIR.rglob("*.md"))
    if not files:
        print(f"ERROR: no .md files found in {ARTICLES_DIR}", file=sys.stderr)
        sys.exit(1)

    CACHE_DIR.mkdir(exist_ok=True)
    fp_file = CACHE_DIR / "fingerprint.txt"
    fingerprint = corpus_fingerprint(files)

    index_file = CACHE_DIR / "index.pkl"
    if (not args.force and index_file.exists()
            and fp_file.exists() and fp_file.read_text().strip() == fingerprint):
        print("Index is up to date. Use --force to rebuild anyway.")
        return

    print(f"Indexing {len(files)} articles...")
    docs = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        rel = str(f.relative_to(SKILL_DIR))
        title = extract_title(text, f.stem)
        # Body with the YAML frontmatter removed, for the embedding input.  Sentence
        # transformers need natural language: feeding them tokenize() output (CJK
        # bigrams, stopwords stripped) embeds noise, not meaning.
        body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.DOTALL)
        docs.append(
            {
                "path": rel,
                "title": title,
                "tokens": tokenize(text),
                "preview": re.sub(r"\s+", " ", text)[:300],
                "embed_text": (title + "。 " + re.sub(r"\s+", " ", body))[:2000],
            }
        )

    # --- BM25 index ---
    from rank_bm25 import BM25Okapi

    bm25 = BM25Okapi([d["tokens"] for d in docs])
    with open(CACHE_DIR / "index.pkl", "wb") as fh:
        pickle.dump(
            {
                "bm25": bm25,
                "meta": [
                    {
                        "path": d["path"],
                        "title": d["title"],
                        "preview": d["preview"],
                        "token_set": frozenset(d["tokens"]),
                    }
                    for d in docs
                ],
            },
            fh,
        )
    print(f"BM25 index written: {CACHE_DIR / 'index.pkl'}")

    # --- Optional semantic embeddings ---
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMBED_MODEL)
        model.max_seq_length = EMBED_MAX_TOKENS
        texts = [d["embed_text"] for d in docs]
        emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
        np.save(CACHE_DIR / "embeddings.npy", emb.astype("float32"))
        print(f"Embeddings written: {CACHE_DIR / 'embeddings.npy'}")
    except ImportError:
        print("sentence-transformers not installed -> BM25-only mode (still works fine).")
        print("For semantic search: pip install sentence-transformers")

    fp_file.write_text(fingerprint)

    # --- Human/Claude-readable INDEX.md ---
    lines = ["# Knowledge Base Index", "", f"{len(docs)} articles.", ""]
    for d in docs:
        lines.append(f"- `{d['path']}` — **{d['title']}**")
    (SKILL_DIR / "kb" / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"INDEX.md written ({len(docs)} entries). Done.")


if __name__ == "__main__":
    main()
