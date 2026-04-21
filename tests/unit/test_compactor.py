"""Auto-compact helper tests (F4)."""
from __future__ import annotations

from framework.observability.compactor import (
    compact_messages,
    estimate_tokens,
)


def test_no_compaction_when_under_limit():
    msgs = [
        {"role": "system", "content": "you are a helpful assistant"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    out, report = compact_messages(msgs, max_tokens=10_000)
    assert report.triggered is False
    assert report.dropped_count == 0
    assert out == msgs


def test_compaction_drops_middle_preserves_system_and_tail():
    system = {"role": "system", "content": "S" * 40}                  # ~10 toks
    middle = [
        {"role": "user", "content": "X" * 400} for _ in range(6)      # ~100 each
    ]
    tail = [
        {"role": "user", "content": "latest question"},
        {"role": "assistant", "content": "pending answer"},
    ]
    msgs = [system, *middle, *tail]
    before = estimate_tokens(msgs)

    out, report = compact_messages(msgs, max_tokens=before // 2, keep_tail_turns=2)

    assert report.triggered is True
    assert report.dropped_count > 0
    assert out[0] == system                # system message preserved
    assert out[-2:] == tail                # last two turns preserved
    assert any(
        isinstance(m.get("content"), str) and "auto-compact" in m["content"]
        for m in out
    )


def test_compaction_handles_multimodal_content():
    msgs = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": [
            {"type": "text", "text": "describe"},
            {"type": "image_url", "image_url": {"url": "data:..."}},
        ]},
        {"role": "assistant", "content": "it's a cat"},
    ]
    # Should not raise and should leave short conversation alone.
    out, report = compact_messages(msgs, max_tokens=10_000)
    assert report.triggered is False
    assert out == msgs


def test_compaction_with_short_history_is_noop():
    msgs = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "u"},
    ]
    out, report = compact_messages(msgs, max_tokens=1, keep_tail_turns=4)
    assert report.triggered is False
    assert out == msgs


def test_custom_token_counter_used():
    msgs = [{"role": "user", "content": "abcde"}] * 10
    calls = {"n": 0}

    def fake_counter(text: str) -> int:
        calls["n"] += 1
        return 100            # every message costs 100

    total = estimate_tokens(msgs, token_counter=fake_counter)
    assert total == 10 * 100 + 10 * 4
    assert calls["n"] >= 10
