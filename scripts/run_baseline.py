"""Run the un-fine-tuned model on a fixed set of stuck-point prompts.

The output JSON is the control group we'll compare against post-fine-tuning.
We deliberately keep the prompt set small (10 cases) so a full run finishes
in a few minutes on M2 Pro.

Usage:
    python scripts/run_baseline.py
    python scripts/run_baseline.py --out data/processed/baseline_thinking.json --thinking
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.inference import GenerationConfig, SocratesEngine  # noqa: E402


# Ten stuck-point scenarios, two per category from PROJECT_CONTEXT §3 plus the
# author's own playthrough notes. Spoiler-free as the player would phrase them.
STUCK_POINTS: list[dict] = [
    {
        "id": "ember_twin_signalscope",
        "category": "info_missing",
        "prompt": "我在余烬双星的山洞里把所有 Nomai 文字都读完了，但提示我还有东西没探索，我不知道还能干嘛。",
    },
    {
        "id": "all_clues_collected",
        "category": "info_missing",
        "prompt": "我感觉线索都拿齐了，现在要去哪里？",
    },
    {
        "id": "quantum_tower_door",
        "category": "info_disconnected",
        "prompt": "量子试炼塔下层，那个门一看就动，我不知道怎么让它不动。",
    },
    {
        "id": "anglerfish_dark_bramble",
        "category": "info_disconnected",
        "prompt": "黑荆棘里有那种大鱼，我每次过都被吃，怎么办？",
    },
    {
        "id": "cactus_assumption",
        "category": "wrong_frame",
        "prompt": "脆骨深谷有一条路被仙人掌挡住了，我得绕路对吧？",
    },
    {
        "id": "sun_station_useless",
        "category": "wrong_frame",
        "prompt": "太阳站感觉没什么用，我是不是不该花时间去？",
    },
    {
        "id": "high_energy_lab_lock",
        "category": "physical_block",
        "prompt": "脆骨深谷那个高能实验室门口的电流我过不去，是不是必须找钥匙？",
    },
    {
        "id": "bramble_seed_navigation",
        "category": "physical_block",
        "prompt": "我进了黑荆棘的种子，里面全是岔路，我永远绕不出来。",
    },
    {
        "id": "ash_twin_project_lore",
        "category": "blindspot",
        "prompt": "我大问号都解完了，但还是不知道结局该做什么。",
    },
    {
        "id": "stranger_dlc_entry",
        "category": "blindspot",
        "prompt": "我在巨人深渊看到一个奇怪的飞船残骸，但找不到怎么进去。",
    },
]


def run(adapter: str | None, thinking: bool, out_path: Path) -> None:
    engine = SocratesEngine(
        adapter_path=adapter,
        gen=GenerationConfig(enable_thinking=thinking),
    )

    results = []
    for i, case in enumerate(STUCK_POINTS, 1):
        print(f"[{i}/{len(STUCK_POINTS)}] {case['id']} ({case['category']})")
        t0 = time.time()
        reply = engine.ask(case["prompt"])
        elapsed = time.time() - t0
        results.append(
            {
                "id": case["id"],
                "category": case["category"],
                "prompt": case["prompt"],
                "reply": reply,
                "elapsed_sec": round(elapsed, 2),
            }
        )
        # Echo the first reply for quick eyeball QA.
        print(f"  ↳ ({elapsed:.1f}s) {reply[:120]}{'…' if len(reply) > 120 else ''}\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(results)} baseline records → {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate baseline replies for stuck points.")
    parser.add_argument("--adapter", default=None, help="Optional LoRA adapter path.")
    parser.add_argument("--thinking", action="store_true", help="Enable Qwen3 thinking mode.")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "processed" / "baseline.json",
        help="Output JSON path.",
    )
    args = parser.parse_args()
    run(adapter=args.adapter, thinking=args.thinking, out_path=args.out)


if __name__ == "__main__":
    main()
