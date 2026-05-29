"""Inference wrapper around an MLX Qwen3-8B model.

Usable both with the base model (for baseline measurement) and with a LoRA
adapter applied (after fine-tuning).

Example:
    >>> from src.inference import SocratesEngine
    >>> engine = SocratesEngine()
    >>> engine.ask("我线索都拿齐了，现在要去哪里？")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .prompts import DEFAULT_SYSTEM_PROMPT

DEFAULT_MODEL = "Qwen/Qwen3-8B-MLX-4bit"


@dataclass
class GenerationConfig:
    """Generation hyper-parameters. Tuned conservatively for chat use."""

    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    repetition_penalty: float = 1.05
    # Qwen3 supports a "thinking" mode — exposed here so we can A/B it later.
    enable_thinking: bool = False


@dataclass
class SocratesEngine:
    """Thin wrapper that lazy-loads an MLX model + tokenizer."""

    model_id: str = DEFAULT_MODEL
    adapter_path: str | Path | None = None
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    gen: GenerationConfig = field(default_factory=GenerationConfig)

    # Internals — populated by ``_ensure_loaded``.
    _model: object | None = field(default=None, init=False, repr=False)
    _tokenizer: object | None = field(default=None, init=False, repr=False)

    # ------------------------------------------------------------------ #
    # Loading                                                            #
    # ------------------------------------------------------------------ #
    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        # Imported lazily so unit tests don't have to pull in MLX.
        from mlx_lm import load  # type: ignore

        adapter_path = str(self.adapter_path) if self.adapter_path else None
        self._model, self._tokenizer = load(self.model_id, adapter_path=adapter_path)

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #
    def ask(self, user_message: str, history: Iterable[dict] | None = None) -> str:
        """Single-turn (or short multi-turn) reply.

        ``history`` is a sequence of ``{"role": "user"|"assistant", "content": str}``
        messages — pass the prior turns to keep the conversation coherent.
        """
        self._ensure_loaded()
        from mlx_lm import generate  # type: ignore
        from mlx_lm.sample_utils import (  # type: ignore
            make_logits_processors,
            make_sampler,
        )

        # Build messages. Skip the system slot entirely if `system_prompt` is "",
        # so baseline runs see the same chat template as a user-only request.
        messages: list[dict] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        prompt = self._tokenizer.apply_chat_template(  # type: ignore[union-attr]
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=self.gen.enable_thinking,
        )

        # mlx-lm 0.31 dropped the `temp=` shortcut in favor of an explicit
        # sampler. Build one from our GenerationConfig so the temperature /
        # top_p values stored in the baseline JSON actually take effect.
        sampler = make_sampler(temp=self.gen.temperature, top_p=self.gen.top_p)
        logits_processors = make_logits_processors(
            repetition_penalty=self.gen.repetition_penalty,
        )

        text = generate(
            self._model,
            self._tokenizer,
            prompt=prompt,
            max_tokens=self.gen.max_tokens,
            sampler=sampler,
            logits_processors=logits_processors,
            verbose=False,
        )
        return text.strip()


# Convenience for `python -m src.inference "..."`.
def _cli() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="One-shot OW-Socrates query.")
    parser.add_argument("message", help="User question.")
    parser.add_argument("--adapter", default=None, help="Optional LoRA adapter path.")
    args = parser.parse_args()

    engine = SocratesEngine(adapter_path=args.adapter)
    print(engine.ask(args.message))


if __name__ == "__main__":
    _cli()
