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
    # change-apply-direct = 9。change-apply.md 走 deprecation banner 路径排除。
    # retire-parallel-and-worktree-fully P3(2026-05-06):change-apply-parallel.md
    # 整删除(沿 D-PostRetireParallelStrategy),命令矩阵 10 → 9。
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


# ---------------------------------------------------------------------------
# enhance-workflow-automation-runtime-enforcement P2 fence:Preflight section
# (D-PreflightProtocol + D-WorktreeEnforce + D-DirectWorktreeRefinement +
# D-SkillCascadeCheck + D-TaskGranularityDeclaration + D-ParallelDispatch)
# ---------------------------------------------------------------------------


_APPLY_CMD_NAMES = ("change-apply-subagent.md", "change-apply-direct.md")
# 沿 D-DirectWorktreeRefinement(2026-05-05 user 拍板):仅 subagent + parallel
# 强制 Preflight Worktree;direct 沿 archived 第 5 项不强制。
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


# ---------------------------------------------------------------------------
# enhance-workflow-automation-executable-enforcement P3+ fence:Subagent Discipline
# (subagent-driven-discipline skill wiring;Layer 2 命令模板 invoke step)
# ---------------------------------------------------------------------------


def test_change_apply_subagent_cascade_includes_subagent_driven_discipline():
    """tasks.md §2.2 fence (section-aware assertion，沿 codex round 2 F1
    [high] accepted-codex):change-apply-subagent.md cascade declared
    dependency 必含 subagent-driven-discipline,逐 section 精确断言:
      1. ### Preflight Skill Cascade section 内 shell block 的 --invoked 行
         含 subagent-driven-discipline
      2. Evidence Frontmatter Template section 的 skill_cascade_audit.invoked_skills
         YAML block-list 含 subagent-driven-discipline

    根因:cluster-2 change `fix-export-d12-and-skipped-evidence-filter`
    暴露 11 dispatch 全 default Opus 4.7,因为 cascade 漏 invoke discipline
    skill;本 fence 防回归。

    Round 2 F1 暴露 round 1 全文件 count 实施(text.count(...) >= 2)
    的退化:quick reference table inline 后字符串自然出现 >= 1 次,即使
    --invoked / frontmatter template 漏改也可能误通过;改为 section-aware。
    """
    text = (CMD_DIR / "change-apply-subagent.md").read_text(encoding="utf-8")

    # 1. Preflight Skill Cascade section 的 --invoked 行
    preflight_idx = text.find("### Preflight Skill Cascade")
    assert preflight_idx != -1, (
        "change-apply-subagent.md must contain '### Preflight Skill Cascade' section"
    )
    # section 边界:下一个 "### " 同级 heading 或 "## " 上级 heading
    next_h3 = text.find("\n### ", preflight_idx + 1)
    next_h2 = text.find("\n## ", preflight_idx + 1)
    candidates = [i for i in (next_h3, next_h2) if i > 0]
    section_end = min(candidates) if candidates else len(text)
    preflight_section = text[preflight_idx:section_end]

    # 在 preflight_section 内找 --invoked 行(可能跨多行;shell line continuation \\)
    invoked_lines = [
        line for line in preflight_section.splitlines()
        if "--invoked" in line
    ]
    assert invoked_lines, (
        "Preflight Skill Cascade section must contain a '--invoked' line "
        "in its shell block"
    )
    # 简化:取 --invoked 行起到下一空白行止作为 shell command block
    cascade_block_lines = []
    in_block = False
    for line in preflight_section.splitlines():
        if "--invoked" in line:
            in_block = True
        if in_block:
            cascade_block_lines.append(line)
            if line.strip() == "" and cascade_block_lines[:-1]:
                break
    cascade_block = "\n".join(cascade_block_lines)
    assert "subagent-driven-discipline" in cascade_block, (
        "Preflight Skill Cascade section's `--invoked` shell block must include "
        f"'subagent-driven-discipline'. Found cascade block:\n{cascade_block}"
    )

    # 2. Evidence Frontmatter Template section 的 skill_cascade_audit.invoked_skills
    template_idx = text.find("Evidence Frontmatter Template")
    assert template_idx != -1, (
        "change-apply-subagent.md must contain 'Evidence Frontmatter Template' section"
    )
    template_section = text[template_idx:]

    audit_idx = template_section.find("skill_cascade_audit:")
    assert audit_idx != -1, (
        "Evidence Frontmatter Template section must contain 'skill_cascade_audit:' field"
    )
    invoked_skills_idx = template_section.find("invoked_skills:", audit_idx)
    assert invoked_skills_idx != -1, (
        "skill_cascade_audit must contain 'invoked_skills:' field"
    )
    # 取 invoked_skills: 后到 cascade_check_pass_at(下一字段)止 作为 block-list 范围
    next_field_idx = template_section.find("cascade_check_pass_at", invoked_skills_idx)
    if next_field_idx == -1:
        # fallback:1000 chars >> actual block (~140 chars);safe headroom for skill list growth
        next_field_idx = invoked_skills_idx + 1000
    block_list_section = template_section[invoked_skills_idx:next_field_idx]
    assert "subagent-driven-discipline" in block_list_section, (
        "skill_cascade_audit.invoked_skills YAML block-list must include "
        f"'subagent-driven-discipline'. Found block-list section:\n{block_list_section}"
    )


def test_change_apply_subagent_dispatch_step_references_discipline_section_1():
    """tasks.md §2.3 fence: change-apply-subagent.md Steps 第 8 sub-step 必
    引用 discipline §1 + 含 model tier quick reference table 关键 row。

    防止 sub-step 退化为只 mention "参考 discipline" 不带 inline reference table
    导致 controller 不查 skill 文件就 default Opus(沿 D2 beta 选,inline reference
    table 是协议核心 — 减查阅成本)。
    """
    text = (CMD_DIR / "change-apply-subagent.md").read_text(encoding="utf-8")
    # discipline §1 引用
    assert "discipline §1" in text or "subagent-driven-discipline` skill §1" in text, (
        "Steps 第 8 sub-step should reference discipline §1 (28-subtype model tier table)"
    )
    # quick reference table 关键 3 row 同时存在(沿 codex round 2 code_quality
    # Important fix:用 "| <name>" pipe-delimited 格式 strict assert 表格 row,
    # 防止 narrative 文本中的 "implementer" / "spec_reviewer" / "code_quality"
    # 单词出现导致 vacuous PASS — implementer 在文件 narrative 22 处出现)
    assert "| implementer" in text, "Quick reference table missing 'implementer' row(pipe-delimited)"
    assert "| spec_reviewer" in text, "Quick reference table missing 'spec_reviewer' row(pipe-delimited)"
    assert "| code_quality" in text, "Quick reference table missing 'code_quality' row(pipe-delimited)"


def test_change_apply_direct_does_not_reference_subagent_driven_discipline():
    """tasks.md §2.4 fence: change-apply-direct.md 不含 subagent-driven-discipline。

    根因(沿 codex round 1 F1 [high] accepted-codex):direct 路径无 subagent
    dispatch -> discipline §1 model tier 协议无 dispatch 触发面(NG2 显式排除);
    本 fence 防协议反向漂移 — direct 误加 cascade 或 future change 整 retire
    subagent 但漏改 direct 时 catch。

    Archived 路径不扫:CMD_DIR = .claude/commands/forgeue/ 只扫 active 命令文件;
    archived 在 openspec/changes/archive/ 不在该 path,fence 自动不扫(沿 ForgeUE
    archive policy 归档即冻结)— 无需额外 assertion。
    """
    text = (CMD_DIR / "change-apply-direct.md").read_text(encoding="utf-8")
    assert "subagent-driven-discipline" not in text, (
        "change-apply-direct.md should NOT reference 'subagent-driven-discipline' "
        "(direct path has no subagent dispatch; NG2 boundary). If this fence "
        "fails, it means cascade discipline leaked to direct path or someone "
        "is using subagent dispatch under direct path."
    )
