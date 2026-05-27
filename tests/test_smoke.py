"""Smoke tests — no MLX / model loading required."""

from src.data_prep import SocraticSample
from src.finetune import build_command
from src.prompts import DEFAULT_SYSTEM_PROMPT


def test_sample_to_chat_roundtrip() -> None:
    s = SocraticSample(
        stuck_point="ember_twin_signalscope",
        strategy="widen",
        player_turn="余烬星山洞里我把字都读完了，还要做什么？",
        socrates_turn="读文字之外，还有什么方式可以获取信息呢？",
        source="author_playthrough",
        language="zh",
    )
    chat = s.to_chat(DEFAULT_SYSTEM_PROMPT)
    assert chat["messages"][0]["role"] == "system"
    assert chat["messages"][1]["role"] == "user"
    assert chat["messages"][2]["role"] == "assistant"
    assert "信号" not in chat["messages"][2]["content"]  # don't spoil


def test_finetune_command_shape() -> None:
    cmd = build_command(
        model="Qwen/Qwen3-8B-MLX-4bit",
        data_dir="data/training",  # type: ignore[arg-type]
        adapter_out="models/adapters/v0",  # type: ignore[arg-type]
        iters=10,
        batch_size=1,
        lora_rank=4,
        learning_rate=1e-4,
    )
    assert cmd[:3] == ["python", "-m", "mlx_lm.lora"]
    assert "--train" in cmd
    assert "--adapter-path" in cmd
