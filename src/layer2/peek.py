"""
Eyeball the Layer 2 retrieval index.

Loads the saved embeddings + metadata, encodes a query (or a list of canned
test queries), and prints the top-K most similar fact chunks.

Used for fast iteration on chunk format and embedding model choice — before
wiring up the LLM in Phase 2.

Usage
-----
  uv run python -m src.layer2.peek                    # run canned probe set
  uv run python -m src.layer2.peek "your query here"  # one-off query
  uv run python -m src.layer2.peek -k 20 "query"      # custom top-K

Look for:
- Are the top-3 chunks actually about the query's entity?
- Do facts within a top hit come from the right bucket (location vs lore)?
- Do anaphoric short facts ("she is female") still bubble up via the entity
  header in embed_text?
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    sys.exit(
        "sentence-transformers is not installed.\n"
        "Run:  uv pip install sentence-transformers"
    )


ROOT = Path(__file__).resolve().parents[2]
INDEX_DIR = ROOT / "docs" / "ow_facts" / "layer2" / "index"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


# Canned probes spanning early-game / lore / mechanics / multi-hop /
# refusal-style queries. If retrieval looks bad on these, fix chunks before
# moving on.
CANNED_QUERIES = [
    "How long is the time loop?",
    "Who created warp core technology?",
    "Why does the Orbital Probe Cannon break apart every loop?",
    "Where can I find Solanum?",
    "What is Ghost Matter and how do I detect it?",
    "How do I land on the Quantum Moon?",
    "Who is Riebeck and what are they afraid of?",
    "What's inside the Sun Station?",
    "Where did the Nomai come from originally?",
    "How do I reach the Vessel in Dark Bramble?",
    "Who played the Anglerfish game in the Sunless City?",
    "What killed all the Nomai?",
]


def load_index() -> tuple[np.ndarray, list[dict]]:
    if not (INDEX_DIR / "embeddings.npy").exists():
        sys.exit(
            f"No index at {INDEX_DIR}.\n"
            "Run first: uv run python -m src.layer2.build_index"
        )
    embeddings = np.load(INDEX_DIR / "embeddings.npy")
    metadata = [
        json.loads(line)
        for line in (INDEX_DIR / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(metadata) == embeddings.shape[0], (
        f"index mismatch: {len(metadata)} meta vs {embeddings.shape[0]} emb"
    )
    return embeddings, metadata


def search(
    query: str,
    model: SentenceTransformer,
    embeddings: np.ndarray,
    metadata: list[dict],
    k: int = 10,
) -> list[tuple[float, dict]]:
    """Encode query, return top-k chunks by cosine similarity."""
    q = model.encode([query], normalize_embeddings=True, convert_to_numpy=True)[0]
    # Both q and embeddings are L2-normalized → dot product == cosine.
    scores = embeddings @ q
    top_idx = np.argsort(-scores)[:k]
    return [(float(scores[i]), metadata[i]) for i in top_idx]


def print_results(query: str, results: list[tuple[float, dict]]) -> None:
    print(f"\n{'=' * 78}")
    print(f"Q: {query}")
    print(f"{'=' * 78}")
    for rank, (score, m) in enumerate(results, 1):
        head = f"[{rank:2d}] {score:.3f}  {m['entity']} ({m['entity_type']}, {m['bucket']})"
        print(head)
        # 4-space indent on the fact line so the head stands out
        print(f"     {m['fact']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Eyeball Layer 2 retrieval.")
    ap.add_argument("query", nargs="?", help="Query string (default: run canned set)")
    ap.add_argument("-k", "--top-k", type=int, default=10, help="top-K to show (default 10)")
    args = ap.parse_args()

    print(f"Loading index from {INDEX_DIR.relative_to(ROOT)}/...")
    embeddings, metadata = load_index()
    print(f"  {len(metadata)} chunks, embeddings shape={embeddings.shape}")

    print(f"\nLoading {MODEL_NAME}...")
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    print(f"  ready in {time.time() - t0:.1f}s")

    queries = [args.query] if args.query else CANNED_QUERIES
    for q in queries:
        results = search(q, model, embeddings, metadata, k=args.top_k)
        print_results(q, results)

    if not args.query:
        print(
            "\n" + "-" * 78
            + "\nDone. Eyeball each Q above: top-3 should be on-topic. "
            "Pass query string as arg to probe more."
        )


if __name__ == "__main__":
    main()
