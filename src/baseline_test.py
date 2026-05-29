"""OW-Socrates Baseline Test
============================

跑未微调的 Qwen3-8B，在 10 个真实卡关场景上拿回答，作为微调前的对照组。

设计要点
--------
1. **不带 system prompt**。我们故意让基模"裸跑"，看它在用户硬要答案时会不会
   直接剧透。微调完成后再跑同一组 prompt（这时模型本身已学会苏格拉底风格，
   不需要 system prompt 提示），两次结果对比就是真实的 delta。

2. **用户语气强硬**。每条 prompt 都以"Just tell me / Give me the answer"收尾——
   这是测基模会不会被这种压力击穿，给出含剧透的回答。

3. **10 个场景 = 5 类 × ~2 个**，对应 PROJECT_CONTEXT §3 的卡点分类。
   未来的训练集和评估集都用这套 id 体系。

4. **走 chat template**。Qwen3 是 chat 模型，不套 chat template 直接喂裸 prompt
   会显著降低输出质量、扭曲 baseline。

Usage
-----
    python -m src.baseline_test
    python -m src.baseline_test --out data/processed/baseline_v0.json
    python -m src.baseline_test --adapter models/adapters/v0  # 微调后对照
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from .inference import GenerationConfig, SocratesEngine
from .prompts import DEFAULT_SYSTEM_PROMPT

# ── 路径 ─────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "processed" / "baseline_results.json"
DEFAULT_MODEL = "Qwen/Qwen3-8B-MLX-4bit"

# ── 测试场景 ────────────────────────────────────────────────────
# id 命名：typeN_<短描述>，N 对应 PROJECT_CONTEXT §3 五种卡点。
TEST_CASES: list[dict] = [
    # ── 类型1：信息缺失 ────────────────────────────────────────
    {
        "id": "type1_ember_twin_signalscope",
        "type": "信息缺失",
        "description": "余烬星山洞 - 文字读完但还有未探索提示",
        "prompt": (
            "I'm playing Outer Wilds and I'm stuck in Ember Twin caves. "
            "I've read every single Nomai text I can find, but the game "
            "still shows there's something unexplored. "
            "What am I missing? Just tell me."
        ),
    },
    {
        "id": "type1_all_clues_collected",
        "type": "信息缺失",
        "description": "自认为线索都拿齐了",
        "prompt": (
            "I've collected what I think are all the clues in Outer Wilds, "
            "but the game won't progress. Where exactly do I need to go next? "
            "Don't be cryptic, just tell me the location."
        ),
    },
    # ── 类型2：信息有了但没连起来 ───────────────────────────
    {
        "id": "type2_quantum_tower_door",
        "type": "信息有了但没连起来",
        "description": "量子试炼塔下层 - 门一直在移动",
        "prompt": (
            "I'm at the Quantum Tower lower section in Outer Wilds. "
            "There's a door that keeps moving whenever I look away. "
            "I've been stuck here for an hour. "
            "How do I stop it from moving? Give me the answer."
        ),
    },
    {
        "id": "type2_anglerfish_dark_bramble",
        "type": "信息有了但没连起来",
        "description": "黑荆棘 - 被鮟鱇鱼吃",
        "prompt": (
            "There are these giant anglerfish in Dark Bramble in Outer Wilds. "
            "Every time I try to fly past them they eat me. "
            "What's the trick to getting past them? Just tell me."
        ),
    },
    # ── 类型3：思维框架错误 ─────────────────────────────────
    {
        "id": "type3_cactus_blocking",
        "type": "思维框架错误",
        "description": "太阳站 - 以为仙人掌不能通过",
        "prompt": (
            "How do I get past the cacti to reach the Sun Station "
            "in Outer Wilds? They seem to be blocking the path completely. "
            "Is there a way around them?"
        ),
    },
    {
        "id": "type3_sun_station_useless",
        "type": "思维框架错误",
        "description": "太阳站 - 怀疑去了没意义",
        "prompt": (
            "Is the Sun Station in Outer Wilds even worth visiting? "
            "It feels like a dead end. Just tell me if I can skip it."
        ),
    },
    # ── 类型4：物理/操作障碍 ───────────────────────────────
    {
        "id": "type4_cactus_damage",
        "type": "物理/操作障碍",
        "description": "太阳站 - 不知道可以扛伤害",
        "prompt": (
            "I know I need to fly through the cacti to get to the "
            "Sun Station in Outer Wilds, but every time I touch them "
            "I die immediately. Is there a way to survive passing through?"
        ),
    },
    {
        "id": "type4_high_energy_lab",
        "type": "物理/操作障碍",
        "description": "高能实验室 - 电流挡住门口",
        "prompt": (
            "The High Energy Lab in Brittle Hollow has some electric "
            "currents blocking the entrance. I keep dying. "
            "Do I need a key item to disable them? Just tell me."
        ),
    },
    # ── 类型5：意识不到自己的盲点 ─────────────────────────
    {
        "id": "type5_dont_know_ending",
        "type": "意识不到盲点",
        "description": "线索齐了但不知道怎么通关",
        "prompt": (
            "I think I have all the clues in Outer Wilds but I still "
            "don't know where to go next or how to finish the game. "
            "Just tell me what I need to do to complete it."
        ),
    },
    {
        "id": "type5_ash_twin_project_lore",
        "type": "意识不到盲点",
        "description": "有线索但没理解 Ash Twin Project",
        "prompt": (
            "In Outer Wilds, I've explored almost everywhere and "
            "collected all the coordinates, but I still feel completely "
            "lost about what the Ash Twin Project is and why it matters. "
            "Can you explain it to me?"
        ),
    },
]


def run_baseline(
    *,
    model_id: str,
    adapter: str | None,
    out_path: Path,
    max_tokens: int,
    temperature: float,
    use_system_prompt: bool,
) -> None:
    print("=" * 60)
    print("OW-Socrates Baseline Test")
    print(f"Model       : {model_id}")
    print(f"Adapter     : {adapter or '(none — base model)'}")
    print(f"System prmt : {'ON' if use_system_prompt else 'OFF (raw baseline)'}")
    print(f"Time        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # baseline 默认 system_prompt="" — chat template 不会注入 system slot，
    # 模型完全裸跑、看用户压力下会不会剧透。微调后或对照实验时再开 --with-system-prompt。
    engine = SocratesEngine(
        model_id=model_id,
        adapter_path=adapter,
        system_prompt=DEFAULT_SYSTEM_PROMPT if use_system_prompt else "",
        gen=GenerationConfig(max_tokens=max_tokens, temperature=temperature),
    )

    print("\n模型加载中...")
    engine._ensure_loaded()  # 提前加载，避免第一条 case 把加载耗时算进去
    print("模型加载完成\n")

    results: list[dict] = []
    for i, case in enumerate(TEST_CASES, 1):
        print(f"[{i}/{len(TEST_CASES)}] {case['description']}")
        print(f"  类型：{case['type']}")
        print(f"  Prompt：{case['prompt'][:80]}...")

        t0 = time.time()
        response = engine.ask(case["prompt"])
        elapsed = time.time() - t0

        preview = response[:200].replace("\n", " ")
        print(f"  回答：{preview}{'...' if len(response) > 200 else ''}")
        print(f"  耗时：{elapsed:.1f}秒")
        print("-" * 40)

        results.append(
            {
                "id": case["id"],
                "type": case["type"],
                "description": case["description"],
                "prompt": case["prompt"],
                "response": response,
                "elapsed_seconds": round(elapsed, 2),
                "model": model_id,
                "adapter": adapter,
                "system_prompt_enabled": use_system_prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    total_time = sum(r["elapsed_seconds"] for r in results)
    print(f"\n✅ 完成！结果保存到：{out_path}")
    print(f"   总场景：{len(results)} 个，累计耗时：{total_time:.1f} 秒")
    print("\n下一步：")
    print("   1. 人工标注每条 response 是否剧透（开一列 is_spoiler）")
    print("   2. 标注是否包含具体地点/物品名（leakage 程度）")
    print("   3. 这份文件就是微调对照组，留住别覆盖")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Baseline 测试：未微调的 Qwen3-8B 在 10 个卡关场景上的回答。",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="HF model id 或本地路径")
    parser.add_argument("--adapter", default=None, help="可选 LoRA adapter 路径（微调后对比用）")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出 JSON 路径")
    parser.add_argument("--max-tokens", type=int, default=500)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument(
        "--with-system-prompt",
        action="store_true",
        help="启用苏格拉底 system prompt（baseline 默认关闭）",
    )
    args = parser.parse_args()

    run_baseline(
        model_id=args.model,
        adapter=args.adapter,
        out_path=args.out,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        use_system_prompt=args.with_system_prompt,
    )


if __name__ == "__main__":
    main()
