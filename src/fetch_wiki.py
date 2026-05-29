"""Fetch Outer Wilds Fandom Wiki pages via MediaWiki API.

Why this script exists
----------------------
Baseline tests proved Qwen3-8B hallucinates 90% of OW-specific facts when
pressed for answers. Before any fine-tuning, we need a trustworthy facts
substrate. The fandom wiki is the most authoritative public source.

This script is a **one-shot initialization tool**: it pulls a curated
list of pages (P0/P1/P2 tiers) into ``docs/ow_facts/raw/`` as JSON files.
The raw dump is NOT what the model sees — you (AJ) audit it and distill
the curated SSOT manually. Re-run only when the wiki updates or you
discover missing pages.

Tiers
-----
* P0 (53): essential — full wikitext, indispensable for facts substrate.
* P1 (45): supplementary — full wikitext, mostly Nomai/Hearthian minor characters.
* P2 (20): DLC outline only — ``exintro=true`` fetches just the intro section.

Output layout
-------------
    docs/ow_facts/raw/
    ├── p0/<Page_Name>.json
    ├── p1/<Page_Name>.json
    └── p2/<Page_Name>.json   ← intro only

Each JSON has shape:
    {
      "page": "Hearthian",
      "pageid": 944,
      "tier": "p0",
      "fetched_at": "2026-05-28T12:00:00",
      "url": "https://outerwilds.fandom.com/wiki/Hearthian",
      "categories": ["Hearthians", "Races"],
      "wikitext": "..."
    }

Usage
-----
    python -m src.fetch_wiki                 # fetch all tiers
    python -m src.fetch_wiki --tier p0       # fetch only p0
    python -m src.fetch_wiki --dry-run       # list URLs, don't fetch
    python -m src.fetch_wiki --resume        # skip pages already on disk
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "docs" / "ow_facts" / "raw"
API_BASE = "https://outerwilds.fandom.com/api.php"
WIKI_BASE = "https://outerwilds.fandom.com/wiki"

# Be polite — the wiki is community-hosted.
SLEEP_BETWEEN_REQUESTS = 0.5  # seconds
USER_AGENT = "ow-socrates/0.1 (research project; https://github.com/ajyujunliu/ow-socrates)"

# --------------------------------------------------------------------------- #
# Page lists (audited 2026-05-28 against fandom category dumps)               #
# --------------------------------------------------------------------------- #

P0_PAGES: list[str] = [
    # Planets / moons / celestial bodies (13)
    "Timber Hearth", "Brittle Hollow", "Giant's Deep", "Dark Bramble",
    "Hourglass Twins", "Quantum Moon", "Sun", "Interloper",
    "Eye of the Universe", "Solar System", "Star System",
    "Attlerock", "Hollow's Lantern",
    # Key locations (19)
    "The Village", "Observatory",
    "Sun Station", "Ash Twin Project",
    "Tower of Quantum Knowledge", "Black Hole Forge",
    "Hanging City", "Crossroads", "High Energy Lab",
    "Bramble Island", "Construction Yard", "Gabbro's Island",
    "Statue Island", "Tower of Quantum Trials",
    "The Vessel",
    "Quantum Shrine",
    "White Hole Station", "Orbital Probe Cannon", "Gravity Cannon",
    # Lore cornerstones (3)
    "Nomai", "Hearthian", "Travelers",
    # Gameplay / mechanics / items (13)
    "Ghost Matter", "Supernova", "Endings", "Launch codes",
    "Quantum Shards", "Signalscope", "Scout Launcher",
    "Spaceship", "Spacesuit", "Translation tool", "Warp Core",
    "Black Hole", "White Hole",
    # Creatures (2)
    "Anglerfish", "Jellyfish",
    # Critical NPCs — Hearthian (8)
    "Feldspar", "Gabbro", "Riebeck", "Chert", "Esker",
    "Gossan", "Hornfels", "Slate",
    # Critical NPCs — Nomai (9)
    "Solanum", "Coleus", "Cycad", "Escall", "Idaea",
    "Phlox", "Privet", "Pye", "Poke",
]

P1_PAGES: list[str] = [
    # Remaining Hearthian villagers (13)
    "Arkose", "Galena", "Gneiss", "Hal", "Marl", "Mica", "Moraine",
    "Porphy", "Rutile", "Spinel", "Tektite", "Tephra", "Tuff",
    # Remaining Nomai supporting cast (32)
    "Annona", "Avens", "Bells", "Bromi", "Bur", "Canna", "Cassava",
    "Clary", "Clem", "Conoy", "Daz", "Din", "Filix", "Foli",
    "Hyssop", "Ilex", "Keek", "Kousa", "Laevi", "Lami",
    "Mallow", "Melorae", "Mitis", "Neem", "Oeno", "Plume",
    "Ramie", "Rhus", "Root", "Secca", "Spire", "Taget",
    "Thatch", "Yarrow",
]

# DLC — intro only.
P2_PAGES: list[str] = [
    "Echoes of the Eye", "Stranger", "Prisoner", "The Stranger's inhabitants",
    "Reservoir", "Cinder Isles", "River Lowlands", "Hidden Gorge",
    "Endless Canyon", "Shrouded Woodlands", "Starlit Cove",
    "Subterranean Lake", "Island Tower", "Abandoned Temple",
    "Forbidden Archives", "Submerged Structure",
    "Artifact", "Slide Reels", "Simulation", "Deep Space Satellite",
]

TIERS: dict[str, list[str]] = {"p0": P0_PAGES, "p1": P1_PAGES, "p2": P2_PAGES}


# --------------------------------------------------------------------------- #
# API helpers                                                                 #
# --------------------------------------------------------------------------- #
def _request(params: dict) -> dict:
    """GET ``API_BASE`` with given params; return parsed JSON."""
    params = {**params, "format": "json"}
    qs = urllib.parse.urlencode(params)
    url = f"{API_BASE}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_full_wikitext(title: str) -> dict | None:
    """Return ``{pageid, wikitext, categories}`` or ``None`` if page is missing."""
    data = _request(
        {
            "action": "parse",
            "page": title,
            "prop": "wikitext|categories",
            "redirects": "1",
        }
    )
    parse = data.get("parse")
    if not parse:
        return None
    return {
        "pageid": parse.get("pageid"),
        "wikitext": parse.get("wikitext", {}).get("*", ""),
        "categories": [c.get("*", "").replace("_", " ") for c in parse.get("categories", [])],
    }


def fetch_intro_extract(title: str) -> dict | None:
    """Return the page's *outline* — used for P2 (DLC) pages.

    Why this is not what its name suggests
    --------------------------------------
    Originally this used MediaWiki's ``action=query&prop=extracts`` API to
    pull only the intro paragraph as plain text. That endpoint silently
    returns an empty string for any page whose wikitext begins with a
    template like ``{{Spoiler}}`` — which every DLC page does. The result
    was 16/20 P2 pages coming back blank.

    Fix: use the same ``action=parse`` endpoint as full pages, then trim
    in Python. We keep the intro paragraph (before the first ``==``
    section heading) PLUS the first 1-2 substantive sections
    ("Description", "Overview", or whatever comes first). This is enough
    for a model to know the entity exists and roughly what it is, without
    pulling in the full DLC walkthrough.
    """
    full = fetch_full_wikitext(title)
    if full is None:
        return None
    full["wikitext"] = _trim_to_outline(full["wikitext"])
    return full


def _trim_to_outline(wikitext: str, max_sections: int = 2) -> str:
    """Keep the intro + first ``max_sections`` top-level ``== Section ==`` blocks."""
    if not wikitext:
        return ""

    # Split on top-level (==…==) headings only, not ===…=== sub-sections.
    # The pattern is anchored at line start and matches exactly two ='s on
    # each side so ``=== Sub ===`` stays inside its parent section.
    import re

    parts = re.split(r"(?m)^(==[^=].*?==)\s*$", wikitext)
    # parts looks like: [intro, "== Description ==", section1, "== Tactics ==", section2, ...]
    intro = parts[0].rstrip()
    kept_sections: list[str] = []
    i = 1
    skip_headings = {
        "references", "notes & trivia", "trivia", "see also",
        "gallery", "external links",
    }
    while i < len(parts) and len(kept_sections) < max_sections:
        heading = parts[i].strip("= ").strip().lower()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if heading not in skip_headings:
            kept_sections.append(f"{parts[i]}\n{body.rstrip()}")
        i += 2

    pieces = [intro] + kept_sections
    return "\n\n".join(p for p in pieces if p.strip())


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #
def fetch_tier(tier: str, *, dry_run: bool, resume: bool) -> tuple[int, int]:
    """Fetch all pages in ``tier``. Return ``(ok_count, fail_count)``."""
    pages = TIERS[tier]
    out_dir = RAW_DIR / tier
    out_dir.mkdir(parents=True, exist_ok=True)

    is_intro_only = tier == "p2"
    ok = 0
    fail = 0

    print(f"\n=== Tier {tier.upper()} — {len(pages)} pages ===")
    for i, title in enumerate(pages, 1):
        safe_name = title.replace(" ", "_").replace("/", "_")
        out_path = out_dir / f"{safe_name}.json"

        if resume and out_path.exists():
            print(f"  [{i:3d}/{len(pages)}] {title}  — skip (already on disk)")
            continue

        if dry_run:
            mode = "intro" if is_intro_only else "full"
            print(f"  [{i:3d}/{len(pages)}] {title}  → {mode}")
            continue

        try:
            payload = fetch_intro_extract(title) if is_intro_only else fetch_full_wikitext(title)
        except Exception as e:
            print(f"  [{i:3d}/{len(pages)}] {title}  ❌ {type(e).__name__}: {e}")
            fail += 1
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        if payload is None:
            print(f"  [{i:3d}/{len(pages)}] {title}  ❌ page not found")
            fail += 1
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        record = {
            "page": title,
            "pageid": payload["pageid"],
            "tier": tier,
            "intro_only": is_intro_only,
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "url": f"{WIKI_BASE}/{urllib.parse.quote(title.replace(' ', '_'))}",
            "categories": payload["categories"],
            "wikitext": payload["wikitext"],
        }
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        size_kb = len(record["wikitext"]) / 1024
        print(f"  [{i:3d}/{len(pages)}] {title:38s} ✓ {size_kb:6.1f} KB")
        ok += 1
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    return ok, fail


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch OW fandom pages → docs/ow_facts/raw/")
    parser.add_argument(
        "--tier",
        choices=["p0", "p1", "p2", "all"],
        default="all",
        help="Which tier to fetch.",
    )
    parser.add_argument("--dry-run", action="store_true", help="List pages, don't fetch.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip pages already saved on disk (useful when re-running after partial failure).",
    )
    args = parser.parse_args()

    tiers_to_run = ["p0", "p1", "p2"] if args.tier == "all" else [args.tier]
    total_ok = total_fail = 0
    t0 = time.time()
    for tier in tiers_to_run:
        ok, fail = fetch_tier(tier, dry_run=args.dry_run, resume=args.resume)
        total_ok += ok
        total_fail += fail

    elapsed = time.time() - t0
    print(f"\n{'=' * 60}")
    print(f"Done. ok={total_ok}  fail={total_fail}  elapsed={elapsed:.1f}s")
    if total_fail:
        print(f"⚠️  {total_fail} pages failed — check the log above. Re-run with --resume to retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
