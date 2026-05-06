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


# ---------------------------------------------------------------------------
# enhance-workflow-automation-executable-enforcement P3 fence:Wrapper + Ledger
# (F1 round 1/2 + F3 round 2 + F4 round 1 inline writeback)
# ---------------------------------------------------------------------------


def test_change_apply_subagent_invokes_preflight_wrapper(cmd_files):
    """P0.5 fence(ADR-013 codex round 1 F3 writeback):change-apply-subagent.md
    内仍含 `python tools/forgeue_preflight_wrapper.py` 字符串(留 OPT-IN reference
    for `worktree_mode: wrapper_worktree` 路径),但**不再 mandatory invoke**。

    沿 ADR-013 D-RestoreConsentGate:wrapper 留 deprecated 但 functional;
    user 显式选 `worktree_mode: wrapper_worktree` 时仍可调用,故 string 保留;
    但 default decline 路径(`worktree_mode: in_place`)不调用 wrapper。"""
    subagent_path = next(
        (f for f in cmd_files if f.name == "change-apply-subagent.md"), None
    )
    assert subagent_path is not None
    body = subagent_path.read_text(encoding="utf-8")
    # ADR-013 advisory:wrapper string 仍保留(opt-in tool reference for wrapper_worktree
    # mode);若被完全删除则 spec.md "opt-in W1 wrapper 仍 functional" Scenario 失效。
    assert "python tools/forgeue_preflight_wrapper.py" in body, (
        "change-apply-subagent.md MUST retain `python tools/forgeue_preflight_wrapper.py` "
        "string as OPT-IN reference (opt-in path for wrapper_worktree mode only — "
        "ADR-013 D-RestoreConsentGate; wrapper 留 deprecated 但 functional;"
        "P0 code_quality m-1 message clarification)"
    )


def test_change_apply_parallel_invokes_preflight_wrapper(cmd_files):
    """P0.5 fence(ADR-013 codex round 1 F3 writeback):change-apply-parallel.md
    内仍含 `python tools/forgeue_preflight_wrapper.py` 字符串(留 OPT-IN reference
    for `worktree_mode: wrapper_worktree` 路径),但**不再 mandatory invoke**。

    沿 ADR-013 D-RestoreConsentGate:wrapper 留 deprecated 但 functional。"""
    parallel_path = next(
        (f for f in cmd_files if f.name == "change-apply-parallel.md"), None
    )
    assert parallel_path is not None
    body = parallel_path.read_text(encoding="utf-8")
    assert "python tools/forgeue_preflight_wrapper.py" in body, (
        "change-apply-parallel.md MUST retain `python tools/forgeue_preflight_wrapper.py` "
        "string as OPT-IN reference (opt-in path for wrapper_worktree mode only — "
        "ADR-013 D-RestoreConsentGate;P0 code_quality m-1 message clarification)"
    )


def test_change_apply_subagent_invokes_dispatch_ledger_append(cmd_files):
    """P3.2 fence(F1 round 2):change-apply-subagent.md 内含
    `python tools/forgeue_dispatch_ledger.py append` 字符串(Step 10a post-dispatch)。"""
    subagent_path = next(
        (f for f in cmd_files if f.name == "change-apply-subagent.md"), None
    )
    assert subagent_path is not None
    body = subagent_path.read_text(encoding="utf-8")
    assert "python tools/forgeue_dispatch_ledger.py append" in body, (
        "change-apply-subagent.md MUST invoke dispatch ledger append in Step 10a"
    )


def test_change_apply_parallel_invokes_dispatch_ledger_append(cmd_files):
    """P3.3 fence(F1 round 2):change-apply-parallel.md 内含
    `python tools/forgeue_dispatch_ledger.py append` 字符串(Step 10a post-dispatch)。"""
    parallel_path = next(
        (f for f in cmd_files if f.name == "change-apply-parallel.md"), None
    )
    assert parallel_path is not None
    body = parallel_path.read_text(encoding="utf-8")
    assert "python tools/forgeue_dispatch_ledger.py append" in body, (
        "change-apply-parallel.md MUST invoke dispatch ledger append in Step 10a"
    )


def test_change_apply_subagent_protocol_version_v2_in_evidence_template(cmd_files):
    """P3.2 fence(F1 round 1):change-apply-subagent.md evidence frontmatter 模板
    含 `runtime_enforcement_protocol_version: v2` 字符串。"""
    subagent_path = next(
        (f for f in cmd_files if f.name == "change-apply-subagent.md"), None
    )
    assert subagent_path is not None
    body = subagent_path.read_text(encoding="utf-8")
    assert "runtime_enforcement_protocol_version: v2" in body, (
        "change-apply-subagent.md evidence template MUST specify runtime_enforcement_protocol_version: v2"
    )


def test_change_apply_parallel_protocol_version_v2_in_evidence_template(cmd_files):
    """P3.3 fence(F1 round 1):change-apply-parallel.md evidence frontmatter 模板
    含 `runtime_enforcement_protocol_version: v2` 字符串。"""
    parallel_path = next(
        (f for f in cmd_files if f.name == "change-apply-parallel.md"), None
    )
    assert parallel_path is not None
    body = parallel_path.read_text(encoding="utf-8")
    assert "runtime_enforcement_protocol_version: v2" in body, (
        "change-apply-parallel.md evidence template MUST specify runtime_enforcement_protocol_version: v2"
    )


def test_change_apply_ledger_append_after_skill_task_dispatch(cmd_files):
    """P3.2 fence(F1 round 2 inline):change-apply-subagent.md 中
    dispatch_ledger.py append Bash 步骤必须出现在 Skill(Task) dispatch 之后
    (post-dispatch order validation)。"""
    subagent_path = next(
        (f for f in cmd_files if f.name == "change-apply-subagent.md"), None
    )
    assert subagent_path is not None
    body = subagent_path.read_text(encoding="utf-8")
    # 简单检查:find "Skill(Task)" index + find "dispatch_ledger.py append" index
    # ledger 下标应 > Skill(Task) 下标(same section Step 10)
    skill_task_idx = body.find("Skill(Task)")
    ledger_idx = body.find("forgeue_dispatch_ledger.py append")
    assert skill_task_idx >= 0, "change-apply-subagent.md missing 'Skill(Task)' reference"
    assert ledger_idx >= 0, "change-apply-subagent.md missing 'forgeue_dispatch_ledger.py append'"
    assert ledger_idx > skill_task_idx, (
        f"dispatch_ledger append MUST appear AFTER Skill(Task) dispatch "
        f"(post-dispatch order requirement; found ledger at {ledger_idx}, Skill at {skill_task_idx})"
    )


def test_change_apply_parallel_actual_diff_uses_git_status_porcelain_and_ls_files_others(cmd_files):
    """P3.3 fence(F3 round 2 inline):change-apply-parallel.md Step 0/1/2 W2 actual diff
    包含:
    1. Step 0 dirty precondition check(git status --porcelain=v1)
    2. Step 1 changed-files collection(git status + git ls-files)
    3. Step 2 intersection detection(Python set operation)
    4. abort log 落 <change>/ 目录(不落 /tmp/)
    """
    parallel_path = next(
        (f for f in cmd_files if f.name == "change-apply-parallel.md"), None
    )
    assert parallel_path is not None
    # Use binary mode and decode to UTF-8 to avoid locale issues on Windows
    with open(parallel_path, "rb") as f:
        content_bytes = f.read()
    body = content_bytes.decode("utf-8")

    # Check for W2 section 10b
    assert "10b. **并行 implementer 实施完成后 W2 actual diff 收集**" in body or "W2 actual diff" in body, (
        "change-apply-parallel.md MUST contain W2 actual diff section (Step 0/1/2)"
    )

    # Check for Step 0, Step 1, Step 2 substeps
    assert "**Step 0:" in body and "implementer worktree clean" in body, (
        "change-apply-parallel.md Step 0 must check dirty implementer worktree precondition"
    )
    assert "**Step 1:" in body and "actual changed-files 收集" in body, (
        "change-apply-parallel.md Step 1 must collect actual changed files"
    )
    assert "**Step 2:" in body and "cross-implementer set intersection" in body, (
        "change-apply-parallel.md Step 2 must detect file overlap"
    )

    # Critical constraints:abort log location
    assert "/tmp/" not in body, (
        "change-apply-parallel.md MUST NOT use /tmp/ paths for abort log "
        "(沿 ForgeUE 产物路径约定:abort log 落 <change>/ 目录,不落 /tmp)"
    )
    assert "parallel_abort" in body, (
        "change-apply-parallel.md abort log MUST use parallel_abort_* naming"
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


def test_apply_subagent_parallel_invoke_subagent_discipline_skill(cmd_files):
    """P3+ fence:change-apply-subagent + change-apply-parallel 必含 Preflight
    Subagent Discipline section;invoke Skill(subagent-driven-discipline)
    在 dispatch 第一个 subagent 之前(Layer 2 wiring;沿 §3.4 Trigger Type Matrix)。"""
    apply_cmds = ("change-apply-subagent.md", "change-apply-parallel.md")
    for cmd_name in apply_cmds:
        path = next((f for f in cmd_files if f.name == cmd_name), None)
        assert path is not None, f"{cmd_name} must exist"
        body = path.read_text(encoding="utf-8")
        # 必含 Preflight Subagent Discipline section
        assert "### Preflight Subagent Discipline" in body, (
            f"{cmd_name} MUST contain '### Preflight Subagent Discipline' section "
            "(沿 subagent-driven-discipline skill Layer 2 wiring)"
        )
        # 必含 Skill(subagent-driven-discipline) invoke 引用
        assert "Skill(subagent-driven-discipline)" in body, (
            f"{cmd_name} MUST reference 'Skill(subagent-driven-discipline)' invoke "
            "(controller 必须 invoke 加载 skill 内容到 working context)"
        )
        # 必含 Trigger Type 引用(Type 1 for subagent / Type 2 for parallel)
        assert "Type 1" in body or "Type 2" in body, (
            f"{cmd_name} MUST reference §3.4.0 Trigger Type(Type 1 3-stage 或 Type 2 Parallel)"
        )


# ---------------------------------------------------------------------------
# restore-superpowers-worktree-consent-gate P0.5 fence:ADR-013 OPT-IN narrative
# (D-RestoreConsentGate + D-ConsentOutcomeStateMachine + D-ParallelDeclineFallback;
# codex round 1 F3 + round 2 F1+F2 writeback)
# ---------------------------------------------------------------------------


def test_apply_subagent_parallel_must_invoke_skill_using_git_worktrees(cmd_files):
    """P0.5 fence(ADR-013 codex round 1 F3 writeback):subagent + parallel 命令
    `## Preflight Worktree` section 必含 `MUST invoke Skill(superpowers:using-git-worktrees)`
    字符串(不再允许 `MAY invoke` 或字符串占位 — codex F3 揭示 MAY invoke 让 Option B'
    consent gate 滑成 Option C 撤 cascade 等价物)。"""
    bad: list[str] = []
    for f in cmd_files:
        if f.name not in _APPLY_CMD_WITH_WORKTREE:
            continue
        body = f.read_text(encoding="utf-8")
        if "MUST invoke `Skill(superpowers:using-git-worktrees)`" not in body:
            bad.append(
                f"{f.name}: missing 'MUST invoke `Skill(superpowers:using-git-worktrees)`' "
                f"(ADR-013 codex round 1 F3 — MAY invoke 不再允许)"
            )
    assert not bad, (
        "subagent / parallel cmd md missing MUST invoke narrative:\n  " + "\n  ".join(bad)
    )


def test_apply_subagent_parallel_preflight_outcome_capture_field(cmd_files):
    """P0.5 fence(ADR-013 D-ConsentOutcomeStateMachine;codex round 1 F2 writeback):
    subagent + parallel 命令 `## Preflight Worktree` section 必含
    `worktree_consent_outcome` 字段提示(显式 outcome capture 到 evidence frontmatter)。"""
    bad: list[str] = []
    for f in cmd_files:
        if f.name not in _APPLY_CMD_WITH_WORKTREE:
            continue
        body = f.read_text(encoding="utf-8")
        if "worktree_consent_outcome" not in body:
            bad.append(
                f"{f.name}: missing 'worktree_consent_outcome' field reference "
                f"(ADR-013 D-ConsentOutcomeStateMachine — outcome capture mandatory)"
            )
    assert not bad, (
        "subagent / parallel cmd md missing outcome capture field:\n  " + "\n  ".join(bad)
    )


def test_apply_parallel_decline_auto_fallback_sequential_narrative(cmd_files):
    """P0.5 fence(ADR-013 D-ParallelDeclineFallback;codex round 1 F1 writeback):
    change-apply-parallel.md 必含 parallel decline → 自动降级 sequential narrative
    (关闭 main repo + multi-implementer + W2 attribution 漏洞)。

    P0 code_quality I-2 inline fix(2026-05-06):narrative 检查改 section-scoped,
    防止未来 maintainer 删 section 内 narrative content 但保留 heading 即 PASS 漏洞。
    """
    parallel_path = next(
        (f for f in cmd_files if f.name == "change-apply-parallel.md"), None
    )
    assert parallel_path is not None
    body = parallel_path.read_text(encoding="utf-8")
    # parallel decline auto-fallback section 应该存在(沿 P0.3 sub-task B.2)
    assert "Preflight Parallel Decline Auto-Fallback" in body, (
        "change-apply-parallel.md MUST contain '## Preflight Parallel Decline Auto-Fallback' "
        "section (ADR-013 D-ParallelDeclineFallback)"
    )
    # P0 code_quality I-2 fix:narrative check 限定在 section 内(从本 section heading
    # 起,到下一个同级或更高级 heading 止);防止 narrative 被删但 heading 保留时 PASS
    section_start = body.index("Preflight Parallel Decline Auto-Fallback")
    section_after = body[section_start:]
    # 找下一个 ###/## section heading(本 section 结束位置)
    next_heading_idx = len(section_after)
    for marker in ("\n### ", "\n## "):
        idx = section_after.find(marker, len("Preflight Parallel Decline Auto-Fallback"))
        if 0 < idx < next_heading_idx:
            next_heading_idx = idx
    section_body = section_after[:next_heading_idx]
    # 至少含一条 decline → fallback narrative IN SECTION;允许 "自动降级" / "auto-fallback" / "降级 sequential"
    has_fallback_narrative_in_section = (
        "自动降级" in section_body
        or "auto-fallback" in section_body.lower()
        or "降级 sequential" in section_body
    )
    assert has_fallback_narrative_in_section, (
        "change-apply-parallel.md `## Preflight Parallel Decline Auto-Fallback` section "
        "MUST contain decline → auto-fallback sequential narrative IN SECTION BODY "
        "(ADR-013 D-ParallelDeclineFallback; codex round 1 F1 — "
        "main repo + multi-implementer + W2 attribution 漏洞;P0 code_quality I-2 fix)"
    )


def test_preflight_worktree_section_bodies_identical(cmd_files):
    """P0 code_quality I-1 inline fix(2026-05-06):防 sync drift —
    change-apply-subagent.md 与 change-apply-parallel.md 的 `## Preflight Worktree`
    section body 必须完全一致(沿 D-RestoreConsentGate 协议:两命令共用同款 OPT-IN
    narrative)。

    Without this fence:future maintainer 可能更新一个 file 不更新另一个 → 决策表
    drift / invariant 描述不一致 / 字段引用差异 → silent 协议分裂(沿 P0 code_quality
    I-1 sync drift risk)。
    """
    subagent_path = next(
        (f for f in cmd_files if f.name == "change-apply-subagent.md"), None
    )
    parallel_path = next(
        (f for f in cmd_files if f.name == "change-apply-parallel.md"), None
    )
    assert subagent_path is not None and parallel_path is not None

    def _extract_preflight_worktree_section(body: str) -> str:
        """提取 ### Preflight Worktree heading 起到下一个同级 ### / ## heading 止的 body。"""
        idx = body.find("### Preflight Worktree")
        assert idx >= 0, "Preflight Worktree section not found"
        section = body[idx:]
        next_heading_idx = len(section)
        for marker in ("\n### ", "\n## "):
            i = section.find(marker, len("### Preflight Worktree"))
            if 0 < i < next_heading_idx:
                next_heading_idx = i
        return section[:next_heading_idx].rstrip()

    sub_section = _extract_preflight_worktree_section(
        subagent_path.read_text(encoding="utf-8")
    )
    par_section = _extract_preflight_worktree_section(
        parallel_path.read_text(encoding="utf-8")
    )

    assert sub_section == par_section, (
        "## Preflight Worktree section body MUST be character-identical between "
        "change-apply-subagent.md and change-apply-parallel.md "
        "(ADR-013 D-RestoreConsentGate sync drift防御;P0 code_quality I-1 fix)。\n"
        "Diff first divergence:\n"
        f"  subagent length={len(sub_section)} chars\n"
        f"  parallel length={len(par_section)} chars\n"
        "(use `diff` tool on extracted sections to debug)"
    )


def test_apply_subagent_parallel_steps_branch_by_outcome_mode(cmd_files):
    """ADR-013 P7 codex round 3 F1 writeback fence(2026-05-06):subagent + parallel
    命令的 Steps 7-9 + Step 16 必须按 `worktree_consent_outcome` × `worktree_mode`
    分支(Branch A: declined/sandbox_fallback + in_place 走 main repo cwd /
    Branch B: accepted/already_isolated + worktree mode 走 isolated worktree)。

    防回归:原 Steps 8-9 mandatory create worktree + cwd 切换,与 Preflight Worktree
    section OPT-IN narrative 矛盾(P7 codex F1 揭示 controller 拿 declined 后仍 force
    建 worktree 的 narrative-vs-implementation gap)。
    """
    bad: list[str] = []
    for f in cmd_files:
        if f.name not in _APPLY_CMD_WITH_WORKTREE:
            continue
        body = f.read_text(encoding="utf-8")
        # 必含 Branch A / Branch B 分支 narrative
        if "Branch A" not in body or "Branch B" not in body:
            bad.append(
                f"{f.name}: missing 'Branch A' / 'Branch B' Steps narrative "
                f"(P7 codex F1 — outcome × mode branching required)"
            )
            continue
        # Branch A 必须明确 main repo cwd 不创建 worktree
        if "Branch A" in body and "main repo cwd" not in body:
            bad.append(
                f"{f.name}: Branch A narrative MUST mention 'main repo cwd' "
                f"(declined / sandbox_fallback path)"
            )
        # Branch A 必须 SKIP worktree 创建
        if "Branch A" in body and "SKIP" not in body:
            bad.append(
                f"{f.name}: Branch A narrative MUST contain 'SKIP' to indicate "
                f"worktree creation/cleanup is skipped under declined path"
            )
    assert not bad, (
        "subagent / parallel cmd md missing outcome × mode Steps branching:\n  "
        + "\n  ".join(bad)
    )
