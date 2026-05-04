"""P2.7 fence:codex 命令模板（review.md + adversarial-review.md）的
default background / 5 类 review_type counter / Round Counter & Context Bridge /
Polling Convention 静态契约测试。

P2.8 验收条件:pytest -q tests/unit/test_codex_command_markdown.py 全绿。

Codex round 1 F1 + F4 findings (accepted-codex) 的回归防线:
- F1:review_type 独立 counter（5 类枚举，per-type counter 路径互不干扰）
- F4:background 后必须 capture job id + polling convention，移除矛盾性
  "Do not call BashOutput or wait for completion in this turn."
"""
from __future__ import annotations

from pathlib import Path

import pytest

# 定位仓库根
_REPO = Path(__file__).resolve().parents[2]

# 命令模板文件路径
REVIEW_MD = _REPO / ".claude" / "commands" / "codex" / "review.md"
ADVERSARIAL_MD = _REPO / ".claude" / "commands" / "codex" / "adversarial-review.md"

# 5 类 review_type 枚举（F1 finding — 独立 counter 路径）
_REVIEW_TYPES = [
    "codex_design_review",
    "codex_plan_review",
    "codex_verification_review",
    "codex_adversarial_review",
    "codex_mixed_scope_review",
]


def _read(path: Path) -> str:
    """读取模板文件，UTF-8 编码。"""
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# P2.2:size estimation 默认 background（不弹 AskUserQuestion）
# ---------------------------------------------------------------------------


def test_review_default_background():
    """review.md 必须含精确的 markdown bold 形式 default background 声明，
    且不再含旧的 AskUserQuestion 二选一逻辑调用。

    P2.2 spec:OLD "use AskUserQuestion exactly once" 替换为 size-based 3-AND gate，
    仅当全部 3 条满足才前台 wait，其余默认 background 不弹问。

    m1 精化（review F-CodeQuality）：正向断言改为精确匹配 markdown bold
    `**Default: background.**` 而非宽松 substring 检查；负向断言精确匹配旧
    upstream "use AskUserQuestion exactly once with two options" 字面量。
    """
    body = _read(REVIEW_MD)
    # 新逻辑：精确匹配 markdown bold 形式的 default background 声明
    assert "**Default: background.**" in body, (
        "review.md 缺少精确文本 '**Default: background.**'（markdown bold）"
    )
    # 旧的 AskUserQuestion 强制二选一调用文本必须移除（精确匹配旧 upstream 字符串）
    old_ask_text = "use `AskUserQuestion` exactly once with two options"
    assert old_ask_text not in body, (
        f"review.md 仍含旧二选一弹框文本：{old_ask_text!r} — 须改为 3-AND gate 默认 background"
    )


def test_adversarial_always_background():
    """adversarial-review.md 对 adversarial 走"永远 background"的精确约束断言。

    P2.2 spec：adversarial 永远 background（涉及挑战式深度分析），
    不需要 size estimation 逻辑，也不含旧的 AskUserQuestion 二选一调用文本。

    m2 精化（review F-CodeQuality）：旧版 4-way OR 中 "always run in background"
    会通过 HTML comment 中的 ``always runs in background`` 字面量匹配（虽相近
    但措辞不严）。改为对正文规范段直接精确匹配 "Adversarial always runs in background."
    （首字母大写 + 句号 + 出现在 Execution Mode Rules 段）。
    """
    body = _read(ADVERSARIAL_MD)
    # 精确匹配规范正文（adversarial 永远 background 的 normative claim）
    assert "Adversarial always runs in background." in body, (
        "adversarial-review.md 缺少精确文本 'Adversarial always runs in background.'"
    )
    # adversarial 同样不含旧的 AskUserQuestion 二选一调用文本（精确匹配旧 upstream 字符串）
    old_ask_text = "use `AskUserQuestion` exactly once with two options"
    assert old_ask_text not in body, (
        f"adversarial-review.md 仍含旧二选一弹框文本：{old_ask_text!r} — adversarial 永远 background"
    )


# ---------------------------------------------------------------------------
# P2.4:## Round Counter & Context Bridge 段
# ---------------------------------------------------------------------------


def test_round_counter_reference_section_exists():
    """两个模板都必须含 ## Round Counter & Context Bridge 段。

    P2.4 spec：命令启动时读 review_type counter → 若 N≥1 则 prompt 注入 round 继承 fence。
    """
    for path in (REVIEW_MD, ADVERSARIAL_MD):
        body = _read(path)
        assert "## Round Counter & Context Bridge" in body, (
            f"{path.name} 缺少 '## Round Counter & Context Bridge' 段"
        )


# ---------------------------------------------------------------------------
# P2.3:5 类 review_type 枚举出现在模板（W1 writeback codex round 1 F1 finding）
# ---------------------------------------------------------------------------


def test_review_type_5_enumeration_present():
    """两个模板都必须含 5 类 codex_*_review 枚举字符串。

    F1 finding writeback:review_type 枚举写进命令模板，
    防止不同 review subject 串用同一 round counter 路径。
    """
    for path in (REVIEW_MD, ADVERSARIAL_MD):
        body = _read(path)
        missing = [rt for rt in _REVIEW_TYPES if rt not in body]
        assert not missing, (
            f"{path.name} 缺少以下 review_type 枚举：{missing}"
        )


def test_review_type_counter_isolation():
    """两个模板都必须显式列出 5 个独立 counter 文件路径（含 review_type 前缀）。

    F1 finding writeback:5 个文件互不读写（per-type counter 路径含 review_type 前缀）。
    路径格式：notes/<review_type>_round_counter.txt
    """
    for path in (REVIEW_MD, ADVERSARIAL_MD):
        body = _read(path)
        missing_paths = []
        for rt in _REVIEW_TYPES:
            counter_path = f"notes/{rt}_round_counter.txt"
            if counter_path not in body:
                missing_paths.append(counter_path)
        assert not missing_paths, (
            f"{path.name} 缺少以下独立 counter 路径（串线防止）：{missing_paths}"
        )


# ---------------------------------------------------------------------------
# P2.5:## Polling Convention 段（W4 writeback codex round 1 F4 finding）
# ---------------------------------------------------------------------------


def test_polling_convention_section_exists():
    """两个模板都必须含 ## Polling Convention 段。

    F4 finding writeback:background launch 后 main session 必须 polling，
    先 /codex:status --wait <job> 再 /codex:result <job> 拿完整输出。
    """
    for path in (REVIEW_MD, ADVERSARIAL_MD):
        body = _read(path)
        assert "## Polling Convention" in body, (
            f"{path.name} 缺少 '## Polling Convention' 段"
        )


def test_no_do_not_call_bashoutput_text():
    """两个模板都不得含旧的矛盾性文本 "Do not call BashOutput or wait for completion in this turn."

    F4 finding writeback:原 plugin upstream text 与 default background 协议冲突，
    替换为 "Main session MUST poll job before consuming verdict" 指令。
    """
    old_text = "Do not call BashOutput or wait for completion in this turn."
    for path in (REVIEW_MD, ADVERSARIAL_MD):
        body = _read(path)
        assert old_text not in body, (
            f"{path.name} 仍含旧矛盾文本：{old_text!r} — 须替换为 polling 指令"
        )


def test_polling_must_directive_present():
    """两个模板都必须含 "Main session MUST poll job before consuming verdict" 类字符串。

    spec W4 writeback 指定替换文本：
    "Main session MUST poll job before consuming verdict via /codex:status --wait + /codex:result."
    """
    directive = "Main session MUST poll job before consuming verdict"
    for path in (REVIEW_MD, ADVERSARIAL_MD):
        body = _read(path)
        assert directive in body, (
            f"{path.name} 缺少 polling 指令文本：{directive!r}"
        )


# ---------------------------------------------------------------------------
# m4 (review F-CodeQuality):review.md 必须文档化 --stage <hint> strip 指令
# ---------------------------------------------------------------------------


def test_review_strips_stage_hint_documented():
    """review.md 必须显式文档化 `--stage <hint>` 是 ForgeUE local extension，
    并且在调用 codex-companion.mjs 前 strip 掉该 flag。

    m4 fence：argument-hint frontmatter 已含 --stage，但 Argument Handling 段
    必须显式说明该 flag 不传给 upstream broker（否则 broker 报 unknown flag）。
    """
    body = _read(REVIEW_MD)
    # 必须含 `--stage` 字面量
    assert "--stage" in body, (
        "review.md 缺少 `--stage` flag 文档（用于 review_type 推导 hint）"
    )
    # 必须含 strip 指令（避免传给 codex-companion.mjs 上游 broker）
    has_strip_directive = (
        "strip it before" in body
        or "strip it from" in body
        or "not passed to codex-companion" in body
    )
    assert has_strip_directive, (
        "review.md 缺少 `--stage <hint>` strip 指令文档（须明示不传给 upstream broker）"
    )


# ---------------------------------------------------------------------------
# m7 (review F-CodeQuality):两模板必须文档化 _active_jobs.txt capture 指令
# ---------------------------------------------------------------------------


def test_active_jobs_capture_documented():
    """两个模板都必须文档化 `_active_jobs.txt` 文件作为 background job id capture 落点。

    m7 fence：Polling Convention 段第 1 步要求 capture job id 写入
    `notes/<review_type>_active_jobs.txt`（review.md 用变量 review_type，
    adversarial-review.md 写死为 codex_adversarial_review_active_jobs.txt）。
    """
    for path in (REVIEW_MD, ADVERSARIAL_MD):
        body = _read(path)
        assert "_active_jobs.txt" in body, (
            f"{path.name} 缺少 `_active_jobs.txt` capture 指令"
            f"（background job id 必须 sticky 落到该文件）"
        )
