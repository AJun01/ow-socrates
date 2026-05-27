"""QLoRA fine-tuning entrypoint — skeleton.

We shell out to ``mlx_lm.lora`` rather than re-implementing training, because
MLX-LM's trainer already handles the 4-bit quantized weight path correctly
on Apple Silicon.

Run:
    python -m src.finetune --data-dir data/training --adapter-out models/adapters/v0

After training, the adapter can be loaded by ``SocratesEngine(adapter_path=...)``.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

DEFAULT_MODEL = "Qwen/Qwen3-8B-MLX-4bit"


def build_command(
    *,
    model: str,
    data_dir: Path,
    adapter_out: Path,
    iters: int,
    batch_size: int,
    lora_rank: int,
    learning_rate: float,
) -> list[str]:
    """Compose the mlx_lm.lora CLI command. Kept testable in isolation."""
    return [
        "python",
        "-m",
        "mlx_lm.lora",
        "--model",
        model,
        "--train",
        "--data",
        str(data_dir),
        "--adapter-path",
        str(adapter_out),
        "--iters",
        str(iters),
        "--batch-size",
        str(batch_size),
        "--lora-layers",
        "8",
        # mlx-lm exposes rank via --lora-parameters; surface it here for clarity:
        "--lora-parameters",
        f"rank={lora_rank}",
        "--learning-rate",
        str(learning_rate),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="QLoRA fine-tune OW-Socrates.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--data-dir", type=Path, default=Path("data/training"))
    parser.add_argument("--adapter-out", type=Path, default=Path("models/adapters/v0"))
    parser.add_argument("--iters", type=int, default=600)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--dry-run", action="store_true", help="Print the command and exit.")
    args = parser.parse_args()

    args.adapter_out.mkdir(parents=True, exist_ok=True)

    cmd = build_command(
        model=args.model,
        data_dir=args.data_dir,
        adapter_out=args.adapter_out,
        iters=args.iters,
        batch_size=args.batch_size,
        lora_rank=args.lora_rank,
        learning_rate=args.learning_rate,
    )

    print("$ " + " ".join(cmd))
    if args.dry_run:
        return
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
