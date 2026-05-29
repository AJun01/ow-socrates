# OW-Socrates

> **Outer Wilds Socratic Hint Assistant** — A fine-tuned Qwen3-8B that helps stuck players *think*, not *spoil*.
> 一个用苏格拉底式提问帮《星际拓荒》玩家突破思维卡点、但不剧透答案的微调小模型。

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Base model: Qwen3-8B-MLX-4bit](https://img.shields.io/badge/base--model-Qwen3--8B--MLX--4bit-orange)](https://huggingface.co/Qwen/Qwen3-8B-MLX-4bit)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-yellow.svg)](#roadmap)

---

## English

### Why this exists

Outer Wilds is built around the joy of *self-driven discovery*. Traditional walkthroughs destroy that experience by handing players the answer. OW-Socrates is a hint assistant that does the opposite — it asks the player questions until they figure it out themselves.

```
Player   : "I've collected every clue. Where do I go next?"
Socrates : "Every clue? Then why are you still stuck?
            Are there any question marks left on your map?"

Player   : "There is one — I never understood what the Ash Twin Project was for."
Socrates : "You know the Nomai existed. Why did they come?
            Where did they all go? What were they trying to do?"
```

No locations. No answers. Just the right question at the right moment.

### What's in this repo

* A baseline harness for the **un-fine-tuned** Qwen3-8B on a fixed set of stuck-point prompts — so we can measure what fine-tuning actually buys us.
* A **QLoRA fine-tuning pipeline** built on MLX-LM, designed to run on a 16 GB M2 Pro.
* A small but explicit **product taxonomy** of the four Socratic strategies (counter-question / widen / challenge premise / decompose) used both as a system prompt and as training-data labels.

### Quickstart

```bash
# 1. Install deps (uv is recommended)
uv sync

# 2. Baseline — generate replies from the un-fine-tuned model
python -m src.baseline_test
# → writes data/processed/baseline_results.json

# 3. One-off query
python -m src.inference "我感觉线索都拿齐了，下一步去哪？"

# 4. After data prep + fine-tuning
python -m src.finetune --data-dir data/training --adapter-out models/adapters/v0
python -m src.inference "..." --adapter models/adapters/v0
```

### Project layout

```
ow-socrates/
├── src/
│   ├── prompts.py        # System prompts encoding the 4 Socratic strategies
│   ├── inference.py      # SocratesEngine — MLX model wrapper
│   ├── baseline_test.py  # control-group generation over 10 stuck points
│   ├── data_prep.py      # raw → normalize → augment → chat-jsonl
│   └── finetune.py       # mlx_lm.lora wrapper (QLoRA)
├── data/                 # raw / processed / training (git-ignored)
├── models/               # base / adapters (git-ignored)
├── tests/                # smoke tests, no MLX required
├── notebooks/            # exploratory analysis
└── docs/                 # design notes
```

### Roadmap

* [x] Environment + base model + working inference (≈39 tok/s on M2 Pro)
* [ ] Baseline measurement over 10 stuck-point scenarios
* [ ] Training data schema + 500–2 000 curated examples
* [ ] QLoRA fine-tuning with W&B tracking
* [ ] Held-out eval set (50 hand-labeled scenarios)
* [ ] Gradio demo on HuggingFace Spaces
* [ ] r/outerwilds community validation

See [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) for the full design rationale.

### Hardware

Developed and tested on Apple Silicon M2 Pro (16 GB). The 4-bit MLX build of Qwen3-8B uses ~4.4 GB of memory at inference and ~10 GB during LoRA fine-tuning.

---

## 中文

### 为什么做这个

《星际拓荒》的核心体验是"自己发现"。传统攻略网站直接给答案的方式会摧毁这个体验。OW-Socrates 反其道而行——它不告诉你答案，只问你问题，让你自己想通。

```
玩家       ："线索都拿齐了，现在要去哪？"
Socrates   ："都拿齐了？那怎么会还卡关呢？是不是还有大问号？"

玩家       ："确实还有，灰烬双星计划到底是干嘛的我没搞懂。"
Socrates   ："你知道 Nomai 存在过吧？他们为什么要来？
              他们都去哪了？他们在尝试做什么？"
```

不给地点，不给答案，只在对的时间问对的问题。

### 仓库内容

* **基线测试脚手架**：在固定的 10 个卡关场景上跑未微调的 Qwen3-8B，作为微调前后的对照。
* **QLoRA 微调流水线**：基于 MLX-LM，针对 16 GB M2 Pro 优化。
* **四种苏格拉底策略**（反问验证 / 拓宽维度 / 质疑前提 / 拆解问题）：既作为系统提示，也作为训练数据的标签。

### 快速开始

```bash
# 1. 安装依赖（推荐 uv）
uv sync

# 2. 基线测试
python -m src.baseline_test
# → 输出 data/processed/baseline_results.json

# 3. 单次提问
python -m src.inference "我感觉线索都拿齐了，下一步去哪？"

# 4. 数据准备 + 微调后
python -m src.finetune --data-dir data/training --adapter-out models/adapters/v0
python -m src.inference "..." --adapter models/adapters/v0
```

### 项目结构

见上方 English 部分的目录树。所有源码集中在 `src/`，命令行入口在 `scripts/`。

### Roadmap

详细路线图见 [PROJECT_CONTEXT.md §6](PROJECT_CONTEXT.md)。当前阶段：基线测试与训练数据 schema 设计。

---

## Citation

If this work is useful to you, please cite:

```bibtex
@software{liu2026owsocrates,
  author = {Liu, AJ Yujun},
  title  = {OW-Socrates: A Socratic Hint Assistant for Outer Wilds},
  year   = {2026},
  url    = {https://github.com/ajyujunliu/ow-socrates}
}
```

## Acknowledgements

* [Qwen3-8B-MLX-4bit](https://huggingface.co/Qwen/Qwen3-8B-MLX-4bit) — base model.
* [mlx-lm](https://github.com/ml-explore/mlx-lm) — fine-tuning + inference on Apple Silicon.
* The r/outerwilds community — for proving that *not* spoiling can be a culture.

## License

[MIT](LICENSE) © 2026 AJ Liu

> ⚠️ This project is **not** affiliated with Mobius Digital or the Outer Wilds team. "Outer Wilds" is a trademark of its respective owner.
