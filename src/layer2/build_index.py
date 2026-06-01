"""
Build the Layer 2 fact-level vector index over the curated SSOT.

What it does
------------
1. Walks docs/ow_facts/curated/*.json (all 114 audited entity files).
2. Expands each fact in each bucket (biology/behavior/location/lore/mechanics)
   into one chunk, prepending the entity name + entity_type + bucket as a
   header so short facts like "Annona is male." retrieve correctly.
3. Skips redirect-stub files (they only contain pointer text, no real facts).
4. Loads sentence-transformers/all-MiniLM-L6-v2 (~100 MB), encodes all chunks
   with normalize_embeddings=True so cosine similarity = dot product.
5. Saves:
   - embeddings.npy      float32 array of shape (N_chunks, 384)
   - metadata.jsonl      one chunk-record per line, in the same order as the
                         rows of embeddings.npy
   - stats.json          build statistics (counts per bucket, model name, dim)

Usage
-----
   uv run python -m src.layer2.build_index

First run downloads the model (~100 MB). Subsequent runs use the cached copy
in ~/.cache/huggingface/. Total runtime on M2 Pro: ~30 seconds for 2800
chunks.
"""

from __future__ import annotations

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


# -- paths and constants ----------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
CURATED_DIR = ROOT / "docs" / "ow_facts" / "curated"
INDEX_DIR = ROOT / "docs" / "ow_facts" / "layer2" / "index"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BUCKETS = ("biology", "behavior", "location", "lore", "mechanics")


# -- chunk expansion --------------------------------------------------------
def expand_to_chunks(curated_dir: Path) -> list[dict]:
    """One chunk per fact, with entity context baked into embed_text."""
    chunks: list[dict] = []
    files = sorted(curated_dir.glob("*.json"))
    n_skipped_stubs = 0

    for fp in files:
        d = json.loads(fp.read_text(encoding="utf-8"))

        # Redirect stubs (Crossroads/Hanging City/Star System/etc) contain
        # only a pointer to another file, no real facts — skip them.
        if d.get("source", {}).get("is_redirect_stub"):
            n_skipped_stubs += 1
            continue

        entity = d["entity"]
        entity_type = d.get("entity_type", "unknown")
        aliases = d.get("aliases", [])
        tags = d.get("tags", [])

        for bucket in BUCKETS:
            facts = d.get("facts", {}).get(bucket, [])
            for i, fact in enumerate(facts):
                # The header lets the embedding model use entity context when
                # resolving short anaphoric facts ("He is male", "It lives in
                # caves", etc).
                header = f"[{entity} | {entity_type} | {bucket}]"
                embed_text = f"{header} {fact}"
                chunks.append({
                    "chunk_id": f"{fp.stem}__{bucket}__{i:02d}",
                    "entity": entity,
                    "entity_type": entity_type,
                    "aliases": aliases,
                    "tags": tags,
                    "bucket": bucket,
                    "fact": fact,
                    "embed_text": embed_text,
                    "source_file": fp.name,
                })

    print(f"  {len(files)} files seen, {n_skipped_stubs} redirect stubs skipped")
    return chunks


# -- main -------------------------------------------------------------------
def main() -> None:
    if not CURATED_DIR.exists():
        sys.exit(f"Curated dir not found: {CURATED_DIR}")

    print(f"\n[1/4] Walking {CURATED_DIR.relative_to(ROOT)}...")
    chunks = expand_to_chunks(CURATED_DIR)
    print(f"  → {len(chunks)} fact chunks expanded\n")

    print(f"[2/4] Loading {MODEL_NAME}...")
    t0 = time.time()
    model = SentenceTransformer(MODEL_NAME)
    dim = model.get_sentence_embedding_dimension()
    print(f"  loaded in {time.time() - t0:.1f}s, embedding dim={dim}\n")

    print(f"[3/4] Encoding {len(chunks)} chunks...")
    t0 = time.time()
    texts = [c["embed_text"] for c in chunks]
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,  # so retrieval can use dot product as cosine
    ).astype(np.float32)
    print(f"  encoded in {time.time() - t0:.1f}s, shape={embeddings.shape}\n")

    print(f"[4/4] Writing index to {INDEX_DIR.relative_to(ROOT)}/")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    np.save(INDEX_DIR / "embeddings.npy", embeddings)

    with (INDEX_DIR / "metadata.jsonl").open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    stats = {
        "n_chunks": len(chunks),
        "n_entities": len({c["entity"] for c in chunks}),
        "model": MODEL_NAME,
        "dim": int(embeddings.shape[1]),
        "buckets": {b: sum(1 for c in chunks if c["bucket"] == b) for b in BUCKETS},
        "embeddings_path": str(INDEX_DIR.relative_to(ROOT) / "embeddings.npy"),
        "metadata_path": str(INDEX_DIR.relative_to(ROOT) / "metadata.jsonl"),
    }
    (INDEX_DIR / "stats.json").write_text(json.dumps(stats, indent=2))

    print("\n✅ Build complete.\n")
    print(json.dumps(stats, indent=2))
    print("\nIndex files:")
    for f in sorted(INDEX_DIR.iterdir()):
        size_kb = f.stat().st_size / 1024
        print(f"  {f.relative_to(ROOT)}  ({size_kb:.1f} KB)")
    print(
        "\nNext: run  uv run python -m src.layer2.peek  "
        "to eyeball retrieval quality."
    )


if __name__ == "__main__":
    main()
