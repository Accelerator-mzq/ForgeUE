"""Conversation auto-compact helper (F4).

Long-running multi-turn callers can accumulate message histories that push
total tokens past the model's context window. This helper trims them back
down without losing either the system prompt or the latest user turn.

Strategy (simple, deterministic, no LLM-assisted summarisation — that would
cost another round-trip and blur the pipeline's determinism guarantees):

  1. Estimate token count for each message. Default estimator uses a cheap
     ~4 chars/token heuristic; caller can inject a real tokenizer via the
     `token_counter` argument for accurate numbers.
  2. If total ≤ max_tokens → return messages unchanged.
  3. Otherwise: always keep the first system message + the last
     `keep_tail_turns` messages. Drop from the middle until we fit, then
     prepend a synthetic {"role":"user","content":"[<N messages compacted>]"}
     placeholder so any downstream accountant (or the user reading a trace)
     knows compaction happened.

Opt-in usage — nothing in the framework auto-compacts by default. Adapters
or custom callers wire this in where appropriate (e.g. a long-running agent
loop or the review engine's chief-judge panel).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


TokenCounter = Callable[[str], int]


def _default_token_counter(text: str) -> int:
    """Rough 4 chars/token estimate. Good enough for budgeting decisions."""
    return max(1, len(text) // 4)


def _message_text(msg: dict[str, Any]) -> str:
    """Pull plain text out of an OpenAI-style message (handles multimodal)."""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif "image_url" in block:
                    parts.append("[image]")
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return "" if content is None else str(content)


@dataclass
class CompactionReport:
    original_tokens: int
    final_tokens: int
    dropped_count: int
    triggered: bool


def estimate_tokens(
    messages: list[dict[str, Any]],
    *,
    token_counter: TokenCounter | None = None,
) -> int:
    counter = token_counter or _default_token_counter
    total = 0
    for msg in messages:
        total += counter(_message_text(msg))
        total += 4        # role / separator overhead
    return total


def compact_messages(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int,
    keep_tail_turns: int = 4,
    token_counter: TokenCounter | None = None,
) -> tuple[list[dict[str, Any]], CompactionReport]:
    """Return (compacted_messages, report).

    - Always keeps the first system message (if any) and the last
      *keep_tail_turns* messages.
    - Drops messages from the middle until total ≤ *max_tokens* or nothing
      remains to drop.
    - Inserts a placeholder marker so the compaction is visible in traces.
    """
    counter = token_counter or _default_token_counter
    original_tokens = estimate_tokens(messages, token_counter=counter)

    if original_tokens <= max_tokens or len(messages) <= keep_tail_turns + 1:
        return list(messages), CompactionReport(
            original_tokens=original_tokens,
            final_tokens=original_tokens,
            dropped_count=0,
            triggered=False,
        )

    head: list[dict[str, Any]] = []
    body_start = 0
    if messages and messages[0].get("role") == "system":
        head = [messages[0]]
        body_start = 1

    tail_start = max(body_start, len(messages) - keep_tail_turns)
    tail = messages[tail_start:]
    middle = messages[body_start:tail_start]

    # Drop from the oldest end of middle until under cap.
    dropped = 0
    while middle:
        candidate = head + middle + tail
        if estimate_tokens(candidate, token_counter=counter) <= max_tokens:
            break
        middle.pop(0)
        dropped += 1

    # If even head + tail is over cap, we can't shrink further without
    # rewriting the tail — accept and let the caller deal with overflow.
    if dropped > 0:
        placeholder = {
            "role": "user",
            "content": f"[auto-compact: {dropped} earlier message(s) omitted]",
        }
        compacted = head + [placeholder] + middle + tail
    else:
        compacted = head + middle + tail

    final_tokens = estimate_tokens(compacted, token_counter=counter)
    return compacted, CompactionReport(
        original_tokens=original_tokens,
        final_tokens=final_tokens,
        dropped_count=dropped,
        triggered=dropped > 0,
    )
