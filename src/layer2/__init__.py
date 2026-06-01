"""Layer 2: Grounded factual retrieval over the SSOT.

Architecture: SSOT (114 curated JSON files, ~2800 facts) is expanded into
fact-level chunks, embedded via sentence-transformers, and stored as a flat
NumPy index. At query time we retrieve top-K facts and inject them into a
Qwen3-8B prompt for grounded answer generation.

See docs/ow_facts/layer2/ for the built index and eval set.
"""
