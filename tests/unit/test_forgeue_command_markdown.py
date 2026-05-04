"""tasks.md §5.4.4 fence: forgeue command md files have required
frontmatter + Steps + Output + Guardrails sections + active-change binding.

Active-command count:9(2026-05-04 起,task 2 引入 ``change-apply-subagent`` /
``change-apply-direct`` 替代旧 ``change-apply``;后者保留 1 archive cycle 作
deprecation banner stub,frontmatter 标 ``tags: [forgeue, deprecated]``,fixture
通过 tags-aware skip 排除,见 design.md ``## Migration Plan``)。

fixture 选择 Option C(tags-aware skip),以避免:
- Option A:fixture magic string ``change-apply.md``(future deprecated 命令需
  再次更新 fixture)
- Option B:archive 物理移动(破坏 ``/forgeue:change-apply`` skill 发现 +
  违反 Migration Plan ``保留 1 archive cycle 让用户切换`` 精神)

Future deprecated 命令只需在 frontmatter ``tags`` 加 ``deprecated``,
fixture 自动 skip 无需改动。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import _common  # noqa: E402

CMD_DIR = _REPO / ".claude" / "commands" / "forgeue"


def _is_deprecated(path: Path) -> bool:
    """Return True iff command md frontmatter ``tags`` includes ``deprecated``.

    parse_frontmatter 不支持 flow-style list,``tags: [forgeue, deprecated]``
    被解析成 raw string ``'[forgeue, deprecated]'`` — 用 substring 检测即可
    覆盖 flow / block 两种风格(沿 test_each_cmd_tags_includes_forgeue 同款)。
    """
    fm, _ = _common.parse_frontmatter(path.read_text(encoding="utf-8"))
    tags = fm.get("tags") or []
    if isinstance(tags, str):
        tags_str = tags
    else:
        tags_str = ", ".join(str(t) for t in tags)
    return "deprecated" in tags_str


@pytest.fixture(scope="module")
def cmd_files() -> list[Path]:
    # Active(非 deprecated)命令文件:7 keep + change-apply-subagent +
    # change-apply-direct = 9。change-apply.md 走 deprecation banner 路径排除。
    files = sorted(p for p in CMD_DIR.glob("change-*.md") if not _is_deprecated(p))
    assert len(files) == 9, f"expected exactly 9 active command files, found {len(files)}"
    return files


def test_each_cmd_has_required_frontmatter_keys(cmd_files):
    required = {"name", "description", "category", "tags"}
    bad: list[str] = []
    for f in cmd_files:
        fm, _ = _common.parse_frontmatter(f.read_text(encoding="utf-8"))
        missing = required - set(fm.keys())
        if missing:
            bad.append(f"{f.name}: missing {sorted(missing)}")
    assert not bad, "cmd md missing required frontmatter keys:\n  " + "\n  ".join(bad)


def test_each_cmd_category_is_forgeue_workflow(cmd_files):
    for f in cmd_files:
        fm, _ = _common.parse_frontmatter(f.read_text(encoding="utf-8"))
        assert fm.get("category") == "ForgeUE Workflow", (
            f"{f.name} category={fm.get('category')!r}"
        )


def test_each_cmd_name_starts_with_forgeue_change(cmd_files):
    for f in cmd_files:
        fm, _ = _common.parse_frontmatter(f.read_text(encoding="utf-8"))
        name = fm.get("name", "")
        assert isinstance(name, str), f"{f.name} non-string name: {name!r}"
        assert "ForgeUE" in name and "Change" in name, (
            f"{f.name} name does not advertise ForgeUE / Change: {name!r}"
        )


def test_each_cmd_has_required_body_sections(cmd_files):
    """body must reference a Steps section, an Output Format section, and
    a Guardrails section."""
    required_sections = ("**Steps**", "**Output Format**", "**Guardrails**")
    bad: list[str] = []
    for f in cmd_files:
        body = f.read_text(encoding="utf-8")
        missing = [s for s in required_sections if s not in body]
        if missing:
            bad.append(f"{f.name}: missing sections {missing}")
    assert not bad, "cmd md missing body sections:\n  " + "\n  ".join(bad)


def test_each_cmd_states_active_change_binding(cmd_files):
    """Per design.md §4 Guardrails: every command MUST require active change
    binding (either via ``必绑 active change`` literal or by aborting on
    missing change). Heuristic: each file must contain the literal
    ``active change`` AND either ``绑`` or ``abort`` somewhere in body."""
    bad: list[str] = []
    for f in cmd_files:
        body = f.read_text(encoding="utf-8")
        if "active change" not in body and "active changes" not in body:
            bad.append(f"{f.name}: missing 'active change' wording")
            continue
        if "绑" not in body and "abort" not in body and "Abort" not in body:
            bad.append(f"{f.name}: missing binding/abort guidance")
    assert not bad, "cmd md missing active-change binding:\n  " + "\n  ".join(bad)


def test_each_cmd_tags_includes_forgeue(cmd_files):
    for f in cmd_files:
        fm, _ = _common.parse_frontmatter(f.read_text(encoding="utf-8"))
        tags = fm.get("tags") or []
        # tags can come back as either list (parser) or string (raw)
        if isinstance(tags, str):
            tags_str = tags
        else:
            tags_str = ", ".join(str(t) for t in tags)
        assert "forgeue" in tags_str, f"{f.name} tags={tags_str!r}"


def test_each_cmd_description_non_empty(cmd_files):
    for f in cmd_files:
        fm, _ = _common.parse_frontmatter(f.read_text(encoding="utf-8"))
        desc = fm.get("description") or ""
        assert isinstance(desc, str) and desc.strip(), (
            f"{f.name} has empty description"
        )


def test_each_cmd_references_design_md_or_skill(cmd_files):
    """Every cmd should hint at the contract source (design.md or skill backbone)."""
    bad: list[str] = []
    for f in cmd_files:
        body = f.read_text(encoding="utf-8")
        if "design.md" not in body and "SKILL.md" not in body:
            bad.append(f.name)
    assert not bad, f"cmd missing design.md / SKILL.md reference: {bad}"


def test_each_cmd_has_decision_delegation_section(cmd_files):
    """P1.10 fence:每个非 deprecated 命令必含 ## Decision Delegation section。

    design.md D-AutonomyBoundary 要求每个命令模板显式声明
    - 默认自主路径(autonomy_decision default)
    - 6 类 D-FenceTaxonomy boundary fence 触发条件
    - evidence frontmatter 必含 autonomy_decision 字段说明
    """
    bad: list[str] = []
    for f in cmd_files:
        body = f.read_text(encoding="utf-8")
        # 检查 ## Decision Delegation section 存在(允许多个空格)
        if "## Decision Delegation" not in body:
            bad.append(f"{f.name}: missing '## Decision Delegation' section")
    assert not bad, (
        "cmd md missing Decision Delegation section:\n  " + "\n  ".join(bad)
    )
