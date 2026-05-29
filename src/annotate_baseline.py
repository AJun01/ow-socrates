"""Annotate baseline_results.json with quality labels.

Why this exists
---------------
``baseline_results.json`` is the *raw* model output — we keep it frozen as the
control group. This script is the one place where human/Claude judgments live,
so re-annotating later only means editing ``ANNOTATIONS`` below and re-running.

The annotation schema is intentionally small. Three booleans + two term lists:

* ``is_spoiler``         — does the reply state the answer / a location / an
                           item name the player should discover themselves?
* ``is_factually_correct`` — among the substantive claims, are they true?
                             ``None`` if no substantive claims.
* ``is_socratic``        — is the reply primarily asking questions to guide
                           the player, rather than telling?
* ``spoiled_terms``      — list of real OW terms the reply leaks.
* ``hallucinated_terms`` — list of OW-ish names the reply *invents* (these
                           are arguably worse than spoilers because they
                           actively misinform).
* ``notes``              — free-form short note for the human reviewer.

Usage
-----
    python -m src.annotate_baseline
    # → writes data/processed/baseline_annotated.json
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "processed" / "baseline_results.json"
OUT = ROOT / "data" / "processed" / "baseline_annotated.json"


# Keyed by case id. Edit freely — this is the single source of truth for
# the v0 baseline annotation. Treat as a structured changelog.
ANNOTATIONS: dict[str, dict] = {
    "type1_ember_twin_signalscope": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "laser array",
            "central chamber door",
            "control room",
            "databank reset",
        ],
        "notes": (
            "Confidently fabricates mechanics that don't exist in the game. "
            "Doesn't even mention Signalscope, which is the actual answer."
        ),
    },
    "type1_all_clues_collected": {
        "is_spoiler": True,
        "is_factually_correct": True,  # broadly correct about the ending direction
        "is_socratic": False,
        "spoiled_terms": ["Sun's core", "core collapse"],
        "hallucinated_terms": [],
        "notes": (
            "Caves immediately under user pressure. Names the endgame destination "
            "in two sentences. Worst-case spoiler behavior."
        ),
    },
    "type2_quantum_tower_door": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "time distortion",
            "glowing orb at the top of the Quantum Tower",
        ],
        "notes": (
            "Quantum mechanics in OW work via observation, not 'time distortion'. "
            "The real answer (Scout / photograph) is never mentioned."
        ),
    },
    "type2_anglerfish_dark_bramble": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "spawn every 14 Earth days",
            "glowing/shifting when about to spawn",
            "fly up or down to avoid",
        ],
        "notes": (
            "The real mechanic is sound-based: anglerfish are blind and react to "
            "engine thrust. Model misses this entirely and fabricates a spawn timer."
        ),
    },
    "type3_cactus_blocking": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "blue cacti on the Sun's surface",
            "Path of the Sun",
            "Sun's Orbit floating planet",
            "compass",
            "northern side of the Sun",
        ],
        "notes": (
            "Most fabricated reply in the set. The Sun Station is reached via the "
            "Ash Twin warp tower, not by walking on the Sun. Model invents an "
            "entire location."
        ),
    },
    "type3_sun_station_useless": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "Sundial Piece",
            "the Loop terminology framed as game mechanic",
        ],
        "notes": (
            "Stance is correct ('don't skip') but every concrete detail is invented. "
            "There is no 'Sundial' in Outer Wilds."
        ),
    },
    "type4_cactus_damage": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "30 damage value",
            "Stellar Cartographer",
            "Stranded timeline",
            "Space Station as safe zone",
        ],
        "notes": (
            "Real answer: cacti damage is survivable — push through and heal at the "
            "ship. Model never says this; instead fabricates timelines and items."
        ),
    },
    "type4_high_energy_lab": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "Insulated Wrench",
            "Pip's Workshop",
            "Mansion District",
        ],
        "notes": (
            "Top-of-class fabrication: invents an item, a location to find it, and "
            "a district that doesn't exist. Most dangerous failure mode — sounds "
            "authoritative, would actively waste hours of player time."
        ),
    },
    "type5_dont_know_ending": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "Celestial Monument",
            "planet called The Monument",
            "Temporal Anchor",
            "Moon of the End",
            "the Hollows",
        ],
        "notes": (
            "Wholesale invention of an alternate game. The actual endgame "
            "(Eye of the Universe, warp core swap) is never mentioned."
        ),
    },
    "type5_ash_twin_project_lore": {
        "is_spoiler": True,
        "is_factually_correct": False,
        "is_socratic": False,
        "spoiled_terms": [],
        "hallucinated_terms": [
            "Kurogane civilization",
            "Hesperia",
            "Kurogane Prime",
            "Ash Twin Catastrophe",
        ],
        "notes": (
            "Replaces Nomai with a fabricated 'Kurogane' Japanese-flavored "
            "civilization. Looks like contamination from another game or anime in "
            "the pretraining corpus. Confident, fluent, completely wrong."
        ),
    },
}


def _summarize(annotated: list[dict]) -> dict:
    total = len(annotated)
    n_spoiler = sum(1 for r in annotated if r["annotation"]["is_spoiler"])
    n_factual = sum(1 for r in annotated if r["annotation"]["is_factually_correct"] is True)
    n_socratic = sum(1 for r in annotated if r["annotation"]["is_socratic"])
    n_halluc = sum(1 for r in annotated if r["annotation"]["hallucinated_terms"])
    return {
        "total_cases": total,
        "is_spoiler_count": n_spoiler,
        "is_factually_correct_count": n_factual,
        "is_socratic_count": n_socratic,
        "cases_with_hallucinations": n_halluc,
        "spoiler_rate": round(n_spoiler / total, 2),
        "hallucination_rate": round(n_halluc / total, 2),
    }


def main() -> None:
    if not RAW.exists():
        raise SystemExit(
            f"baseline_results.json not found at {RAW}. Run `python -m src.baseline_test` first."
        )

    raw_records = json.loads(RAW.read_text(encoding="utf-8"))

    missing_ids = [r["id"] for r in raw_records if r["id"] not in ANNOTATIONS]
    if missing_ids:
        raise SystemExit(f"Missing annotations for ids: {missing_ids}")

    annotated = []
    for r in raw_records:
        annotated.append({**r, "annotation": ANNOTATIONS[r["id"]]})

    summary = _summarize(annotated)
    output = {
        "schema_version": "v0",
        "source_file": RAW.name,
        "summary": summary,
        "records": annotated,
    }

    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Wrote {len(annotated)} annotated records → {OUT}")
    print()
    print("Baseline summary (v0, un-fine-tuned Qwen3-8B, no system prompt):")
    for k, v in summary.items():
        print(f"  {k:35s} {v}")
    print()
    print("Next: open the file and sanity-check any case you disagree with.")
    print("All judgments live in src/annotate_baseline.py::ANNOTATIONS — edit + rerun.")


if __name__ == "__main__":
    main()
