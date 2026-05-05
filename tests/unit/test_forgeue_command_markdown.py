"""tasks.md §5.4.4 fence: forgeue command md files have required
frontmatter + Steps + Output + Guardrails sections + active-change binding.

Active-command count:10(2026-05-05 起,enhance-workflow-automation-runtime-enforcement
P2.3 引入 ``change-apply-parallel`` 暴露并行 dispatch 路径,与 ``change-apply-subagent``
/ ``change-apply-direct`` 共同构成 D-ParallelDispatch 三选一路由)。
之前 9(自 2026-05-04 ``adopt-subagent-driven-development`` task 2 拆 subagent + direct);
``change-apply.md`` deprecation banner stub 仍标 ``tags: [forgeue, deprecated]``,fixture
通过 tags-aware skip 排除,见 design.md ``## Migration Plan``。

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
    # change-apply-direct + change-apply-parallel = 10。change-apply.md 走
    # deprecation banner 路径排除(自 2026-05-05 起,enhance-workflow-automation-runtime-enforcement
    # P2.3 加 change-apply-parallel,7 → 8 keep+direct+parallel,共 10)。
    files = sorted(p for p in CMD_DIR.glob("change-*.md") if not _is_deprecated(p))
    assert len(files) == 10, f"expected exactly 10 active command files, found {len(files)}"
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


# ---------------------------------------------------------------------------
# enhance-workflow-automation-runtime-enforcement P2 fence:Preflight section
# (D-PreflightProtocol + D-WorktreeEnforce + D-DirectWorktreeRefinement +
# D-SkillCascadeCheck + D-TaskGranularityDeclaration + D-ParallelDispatch)
# ---------------------------------------------------------------------------


_APPLY_CMD_NAMES = ("change-apply-subagent.md", "change-apply-direct.md", "change-apply-parallel.md")
# 沿 D-DirectWorktreeRefinement(2026-05-05 user 拍板):仅 subagent + parallel
# 强制 Preflight Worktree;direct 沿 archived 第 5 项不强制。
_APPLY_CMD_WITH_WORKTREE = ("change-apply-subagent.md", "change-apply-parallel.md")
# 5 个 SKILL-invoke 命令(plan / debug / verify / review / doc-sync)+ 3 个 apply
# 命令 = 8 个含 Preflight Skill Cascade 的命令。change-finish + change-status 不
# invoke SKILL,沿 P2.4 task 描述跳过。
_SKILL_INVOKE_CMDS = (
    "change-apply-subagent.md",
    "change-apply-direct.md",
    "change-apply-parallel.md",
    "change-plan.md",
    "change-debug.md",
    "change-verify.md",
    "change-review.md",
    "change-doc-sync.md",
)


def test_apply_cmds_have_preflight_skill_cascade_section(cmd_files):
    """P2.6 fence:3 个 apply 命令(subagent / direct / parallel)均含
    ## Preflight Skill Cascade section(D-SkillCascadeCheck)。"""
    bad: list[str] = []
    for f in cmd_files:
        if f.name not in _APPLY_CMD_NAMES:
            continue
        body = f.read_text(encoding="utf-8")
        if "## Preflight Skill Cascade" not in body:
            bad.append(f"{f.name}: missing '## Preflight Skill Cascade' section")
    assert not bad, (
        "apply cmd md missing Preflight Skill Cascade section:\n  " + "\n  ".join(bad)
    )


def test_apply_cmds_have_preflight_task_granularity_section(cmd_files):
    """P2.6 fence:3 个 apply 命令均含 ## Preflight Task Granularity section
    (D-TaskGranularityDeclaration)。"""
    bad: list[str] = []
    for f in cmd_files:
        if f.name not in _APPLY_CMD_NAMES:
            continue
        body = f.read_text(encoding="utf-8")
        if "## Preflight Task Granularity" not in body:
            bad.append(f"{f.name}: missing '## Preflight Task Granularity' section")
    assert not bad, (
        "apply cmd md missing Preflight Task Granularity section:\n  " + "\n  ".join(bad)
    )


def test_subagent_parallel_have_preflight_worktree_section(cmd_files):
    """P2.6 fence(D-WorktreeEnforce):仅 subagent + parallel 命令含
    ## Preflight Worktree section;direct 沿 D-DirectWorktreeRefinement
    不含。"""
    bad: list[str] = []
    for f in cmd_files:
        if f.name not in _APPLY_CMD_WITH_WORKTREE:
            continue
        body = f.read_text(encoding="utf-8")
        if "## Preflight Worktree" not in body:
            bad.append(f"{f.name}: missing '## Preflight Worktree' section")
        if "Skill(superpowers:using-git-worktrees)" not in body:
            bad.append(f"{f.name}: missing 'Skill(superpowers:using-git-worktrees)' invoke")
    assert not bad, (
        "subagent / parallel cmd md missing Preflight Worktree:\n  " + "\n  ".join(bad)
    )


def test_change_apply_direct_does_not_have_preflight_worktree_section(cmd_files):
    """P2.6 negative fence(D-DirectWorktreeRefinement,2026-05-05 user 拍板):
    change-apply-direct 沿 archived 2026-05-04-adopt-subagent-driven-development
    D-Worktree-Detail 第 5 项**不强制** Preflight Worktree;锁住此 negative
    行为防止后续 change 误加 Preflight Worktree 破坏 archived 决策语义。"""
    direct_path = next(
        (f for f in cmd_files if f.name == "change-apply-direct.md"), None
    )
    assert direct_path is not None, "change-apply-direct.md must exist as active command"
    body = direct_path.read_text(encoding="utf-8")
    # 注意:body 内可以提及 "Preflight Worktree" 字符串(如 disclaimer 段引用),
    # 但**不应**有独立的 "## Preflight Worktree" section heading
    assert "## Preflight Worktree" not in body, (
        "change-apply-direct.md MUST NOT contain '## Preflight Worktree' section "
        "(D-DirectWorktreeRefinement: direct 沿 archived 第 5 项不强制 worktree)"
    )


def test_change_apply_parallel_command_exists(cmd_files):
    """P2.6 fence(D-ParallelDispatch):新建 change-apply-parallel.md 文件存在
    + 含 superpowers:dispatching-parallel-agents SKILL 引用 + 借用 disclaimer。"""
    parallel_path = next(
        (f for f in cmd_files if f.name == "change-apply-parallel.md"), None
    )
    assert parallel_path is not None, (
        "change-apply-parallel.md must exist as active command "
        "(enhance-workflow-automation-runtime-enforcement P2.3)"
    )
    body = parallel_path.read_text(encoding="utf-8")
    assert "superpowers:dispatching-parallel-agents" in body, (
        "change-apply-parallel.md MUST reference superpowers:dispatching-parallel-agents skill"
    )
    # 借用 disclaimer:debugging-focused SKILL 借用为 implementation parallel
    assert "借用" in body or "borrow" in body.lower(), (
        "change-apply-parallel.md MUST contain 借用 pattern disclaimer "
        "(D-ParallelDispatch R5: SKILL 描述 debugging-focused,implementation 借用)"
    )
    # task_independence_assertion 字段引用
    assert "task_independence_assertion" in body, (
        "change-apply-parallel.md MUST reference task_independence_assertion frontmatter field"
    )


def test_skill_invoking_cmds_have_preflight_skill_cascade(cmd_files):
    """P2.6 fence:8 个 SKILL-invoke 命令(3 apply + plan / debug / verify /
    review / doc-sync)均含 ## Preflight Skill Cascade section + 引用
    `forgeue_skill_cascade_check.py` 工具。"""
    bad: list[str] = []
    for f in cmd_files:
        if f.name not in _SKILL_INVOKE_CMDS:
            continue
        body = f.read_text(encoding="utf-8")
        if "## Preflight Skill Cascade" not in body:
            bad.append(f"{f.name}: missing '## Preflight Skill Cascade' section")
            continue
        if "forgeue_skill_cascade_check" not in body:
            bad.append(
                f"{f.name}: Preflight Skill Cascade section missing tool reference "
                "to tools/forgeue_skill_cascade_check.py"
            )
    assert not bad, (
        "SKILL-invoke cmd md missing Preflight Skill Cascade:\n  " + "\n  ".join(bad)
    )


def test_change_finish_status_skip_preflight_skill_cascade(cmd_files):
    """P2.6 negative fence:change-finish + change-status 不 invoke SKILL
    (前者纯工具调用,后者只读),沿 P2.4 task 描述不强制 Preflight Skill
    Cascade;锁住此 skip 行为防止后续 change 误加 Preflight Skill Cascade。"""
    skip_cmds = ("change-finish.md", "change-status.md")
    for cmd_name in skip_cmds:
        path = next((f for f in cmd_files if f.name == cmd_name), None)
        assert path is not None, f"{cmd_name} must exist"
        body = path.read_text(encoding="utf-8")
        # change-finish + change-status 不应有 Preflight Skill Cascade section
        # (它们不 invoke Superpowers SKILL,纯工具调用 / 只读)
        assert "## Preflight Skill Cascade" not in body, (
            f"{cmd_name} MUST NOT contain '## Preflight Skill Cascade' section "
            "(本命令不 invoke SKILL,沿 P2.4 task 描述跳过)"
        )
