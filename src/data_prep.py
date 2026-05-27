"""Training data preparation — skeleton.

Pipeline (to be implemented):

    raw sources  ─▶  normalize  ─▶  augment (Claude API)  ─▶  chat-format jsonl
       │                │                  │                       │
   data/raw/      data/processed/     data/processed/          data/training/
                                       *_augmented.jsonl       train.jsonl
                                                               valid.jsonl

Each final record is a ``{"messages": [...]}`` object in the format MLX-LM's
LoRA trainer expects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
TRAINING_DIR = ROOT / "data" / "training"


# --------------------------------------------------------------------------- #
# Schema                                                                      #
# --------------------------------------------------------------------------- #
@dataclass
class SocraticSample:
    """One training example.

    Attributes:
        stuck_point: A canonical label, e.g. "ember_twin_signalscope".
        strategy:    One of {"counter_question", "widen", "challenge_premise", "decompose"}.
        player_turn: What the (simulated) player said.
        socrates_turn: The ideal Socratic reply.
        source: Where this came from, e.g. "reddit:r/outerwilds:abc123" or "author_playthrough".
        language: "zh" | "en" | "mixed".
    """

    stuck_point: str
    strategy: str
    player_turn: str
    socrates_turn: str
    source: str
    language: str

    def to_chat(self, system_prompt: str) -> dict:
        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": self.player_turn},
                {"role": "assistant", "content": self.socrates_turn},
            ]
        }


# --------------------------------------------------------------------------- #
# Stages                                                                      #
# --------------------------------------------------------------------------- #
def collect_raw() -> list[dict]:
    """TODO: pull from Reddit / hand-written / author playthrough notes.

    For now, returns an empty list so the rest of the pipeline can run dry.
    """
    return []


def normalize(raw_records: list[dict]) -> list[SocraticSample]:
    """TODO: clean text, dedupe, tag stuck_point + strategy."""
    _ = raw_records
    return []


def augment(samples: list[SocraticSample]) -> list[SocraticSample]:
    """TODO: call Claude API to generate paraphrases / strategy variants.

    Target multiplier: 3–5x. Keep originals first so we can ablate later.
    """
    return list(samples)


def to_chat_jsonl(samples: list[SocraticSample], system_prompt: str, out_path: Path) -> int:
    """Serialize to MLX-LM's expected JSONL format. Returns number of rows."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s.to_chat(system_prompt), ensure_ascii=False) + "\n")
    return len(samples)


def main() -> None:
    raw = collect_raw()
    samples = normalize(raw)
    samples = augment(samples)

    from .prompts import DEFAULT_SYSTEM_PROMPT

    train_n = to_chat_jsonl(samples, DEFAULT_SYSTEM_PROMPT, TRAINING_DIR / "train.jsonl")
    print(f"Wrote {train_n} training rows → {TRAINING_DIR/'train.jsonl'}")


if __name__ == "__main__":
    main()
