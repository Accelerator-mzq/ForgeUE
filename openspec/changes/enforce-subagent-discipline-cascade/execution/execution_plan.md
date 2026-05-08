---
change_id: enforce-subagent-discipline-cascade
stage: S2
evidence_type: execution_plan
contract_refs:
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#1.1
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#1.2
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#1.3
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#2.1
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#2.2
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#2.3
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#2.4
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#3.1
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#3.2
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#3.3
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#3.4
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#4.1
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#4.2
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#4.3
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#4.4
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#4.5
  - openspec/changes/enforce-subagent-discipline-cascade/tasks.md#4.6
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-08T13:36:01Z
autonomy_decision: claude_codex_concurred
---

# enforce-subagent-discipline-cascade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **ForgeUE 路径**:本 change 走 `/forgeue:change-apply-subagent`(沿 design.md D6 inline writeback `2ac207f` 切到 subagent dispatch 路径;dogfood 自验证 cascade 协议)。

**Goal:** `/forgeue:change-apply-subagent` 命令模板 Preflight Skill Cascade declared dependency 协议化加入 `subagent-driven-discipline` companion skill,并在 dispatch Step 强制 controller 显式按 discipline §1 表选 model + 加 fence test 静态扫覆盖防回归。

**Architecture:** 命令模板层修订(3 处 markdown edit)+ fence test 静态扫(2 case 扩 `test_forgeue_command_markdown.py`)+ 文档同步(`forgeue_integrated_ai_workflow.md` §B + `CHANGELOG.md`)。**不**改 `forgeue_skill_cascade_check.py` 工具语义(generic accept `--invoked` 字符串)。**不**强制 `/forgeue:change-apply-direct` cascade(direct 路径无 subagent)。**不**动 backbone skill / discipline skill 自身。

**Tech Stack:** Python stdlib(pytest fence)+ markdown(命令模板 / 文档)+ ForgeUE-existing tooling(`forgeue_skill_cascade_check.py` / `forgeue_doc_sync_check.py` / `forgeue_finish_gate.py`)

---

## File Structure

修改文件清单(in-scope per design.md `## Migration Plan` Phase A/B/D):

| File | Operation | Responsibility |
|---|---|---|
| `.claude/commands/forgeue/change-apply-subagent.md` | Modify | Preflight Skill Cascade `--invoked` 参数加 `subagent-driven-discipline`;Steps 第 8 step 加 model tier sub-step + quick reference table;evidence frontmatter `skill_cascade_audit.invoked_skills` template 加 `subagent-driven-discipline` |
| `tests/unit/test_forgeue_command_markdown.py` | Modify(extend)| 扩 2 case:(a)cascade `--invoked` 行 + frontmatter template 都含 `subagent-driven-discipline` 字符串 ≥ 2 次;(b)Steps 第 8 sub-step 含 model tier quick reference table(implementer / spec_review / code_quality 3 row 同时存在)|
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md` | Modify | §B 命令矩阵 `change-apply-subagent` 行 sister skill list 加 `subagent-driven-discipline` |
| `CHANGELOG.md` | Modify | Unreleased Added 段顶部加 entry |

不动文件(NG1-NG7 显式排除):

- `tools/forgeue_skill_cascade_check.py`(NG1)
- `.claude/commands/forgeue/change-apply-direct.md`(NG2)
- `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`(NG3)
- `.claude/skills/subagent-driven-discipline/SKILL.md`(NG7,沿 D7)
- archived change evidence(D4)

---

## Bootstrap vs Acceptance Phase 协议(沿 design.md D6.1 + codex round 1 F2 [medium] accepted-codex)

每 Task 实施时 controller 必须按下表标 `bootstrap_phase` 状态,在 evidence body `## Dogfood Acceptance` section 记录:

| Task | bootstrap_phase | cascade_enforcement_source | controller manual override required? |
|---|---|---|---|
| Task 1(Phase A 命令模板修订)| `true` | controller_manual | YES — 命令模板尚未含 cascade,controller 主动 invoke discipline + 主动按 §1 表选 model |
| Task 2(Phase B fence test)| `false` | command_template_auto | NO — Task 1 commit 后命令模板已生效 |
| Task 3(Phase D doc-sync)| `false` | command_template_auto | NO |
| Task 4(Phase E 各 sub-step)| `false` | command_template_auto | NO — 但 Final reviewer subagent 必须验 Phase A bootstrap status 顺序合规(沿 D6.1 4 项验证责任)|

每 evidence(per-task `task_<n>_*.md` + `subagent_final_review.md`)body 末尾必加:

```markdown
## Dogfood Acceptance

- bootstrap_phase: true | false
- cascade_enforcement_source: controller_manual | command_template_auto
- justification: <reason if bootstrap_phase: true>
```

---

## Task 1: Phase A — change-apply-subagent.md 命令模板 3 处修订

**Files:**
- Modify: `.claude/commands/forgeue/change-apply-subagent.md` (3 个 region)
  - Region 1: L29 Preflight Cascade `--invoked` 参数行
  - Region 2: Steps 第 8 step(L64-70 区域)
  - Region 3: evidence frontmatter `skill_cascade_audit.invoked_skills` template L144-148

**Anchors:** `tasks.md#1.1` / `tasks.md#1.2` / `tasks.md#1.3`

**Decisions:** D1 (cascade name `subagent-driven-discipline` 无 plugin prefix)、D2 (β 选 — 显式 dispatch 模板示例 + Agent tool `model:` 参数)

- [ ] **Step 1.1: 改 Preflight Cascade `--invoked` 参数行**

`tasks.md#1.1`:在 L29(`--invoked superpowers:test-driven-development,...`)末尾加 `,subagent-driven-discipline`,使变成:

```bash
python tools/forgeue_skill_cascade_check.py \
    --skill superpowers:subagent-driven-development \
    --invoked superpowers:test-driven-development,superpowers:requesting-code-review,superpowers:finishing-a-development-branch,subagent-driven-discipline
```

- [ ] **Step 1.2: 改 Steps 第 8 step 加 model tier sub-step**

`tasks.md#1.2`:在 Step 8(invoke `superpowers:subagent-driven-development` skill 段)整段后面加 sub-step,内含明示 controller dispatch 每个 subagent 前必参考 discipline §1 28-subtype × model tier 表选 model + 显式传 `Agent` tool `model:` 参数,inline quick reference table 5 类 subagent role 默认 model:

```markdown
**Sub-step 8.x: Model tier 显式选择(沿 `subagent-driven-discipline` §1 表)**

每个 dispatch 前 controller MUST 按 discipline §1 28-subtype × model tier 表选 model,且显式在 `Agent` tool 调用传 `model:` 参数(不依赖 parent session inherit default)。Quick reference:

| Subagent role | discipline §1 subtype | model 默认 |
|---|---|---|
| implementer(完整 plan inline)| §1.1.1 mechanical | `haiku` |
| implementer(pattern matching)| §1.1.2 | `haiku` 或 `sonnet` |
| implementer(multi-file integration)| §1.1.3 | `sonnet` |
| implementer(algorithmic / architectural design)| §1.1.4 / §1.1.5 | `opus` MANDATORY |
| spec_reviewer(string matching)| §1.2.1 / §1.2.2 | `haiku` |
| spec_reviewer(cross-phase reasoning)| §1.2.3 | `sonnet` |
| code_quality(style / lint)| §1.3.1 | `haiku` |
| code_quality(runtime correctness)| §1.3.4 | `sonnet` MANDATORY |
| final reviewer(cross-phase consistency)| §1.3.3 + §1.3.4 | `sonnet` |
| doc-sync(mechanical replace)| §1.5.1 | `haiku` 或 direct(no subagent)|
| doc-sync(semantic rewrite)| §1.5.2 | `sonnet` |

完整 28-subtype 决策见 `subagent-driven-discipline` skill §1。Override 路径:若 task subtype 难判 / 跨多 subtype,controller 可选 higher tier(如把 §1.1.2 default `haiku` 升 `sonnet`),但 evidence body Token usage 段必须显式记录决策理由。
```

- [ ] **Step 1.3: 改 evidence frontmatter template `skill_cascade_audit.invoked_skills`**

`tasks.md#1.3`:在 L144-148 frontmatter template 的 `invoked_skills` block-list 加 `- subagent-driven-discipline` 行:

```yaml
skill_cascade_audit:
  invoked_skills:
    - superpowers:subagent-driven-development
    - subagent-driven-discipline
    # ... add more as needed (block-list)
  cascade_check_pass_at: <ISO-8601-timestamp>
```

- [ ] **Step 1.4: Verify markdown 静态正确性**

Run: `python -m pytest tests/unit/test_forgeue_command_markdown.py -v`(本 step 测的是现有 fence;Step 2 的新 fence 之前 baseline 应仍 PASS)
Expected: PASS(frontmatter + Steps + Output + Guardrails section 检查仍在)

- [ ] **Step 1.5: Commit Phase A**

```bash
git add .claude/commands/forgeue/change-apply-subagent.md
git commit -m "feat(forgeue): cascade discipline + model tier protocol in change-apply-subagent"
```

---

## Task 2: Phase B — Fence test 静态扫 2 case 扩 test_forgeue_command_markdown.py

**Files:**
- Modify: `tests/unit/test_forgeue_command_markdown.py` (扩 2 test function 在文件末尾)

**Anchors:** `tasks.md#2.1` / `tasks.md#2.2` / `tasks.md#2.3`

**Decisions:** D3 (扩既有 `test_forgeue_command_markdown.py`;design.md D3 写的 `test_forgeue_command_templates.py` 不存在,minor doc drift candidate — 将在 cross-check `## D` 评估是否需要 inline writeback design.md D3)

- [ ] **Step 2.1: Glob 验证 file 存在 + 当前末尾**

Run: `python -c "from pathlib import Path; p = Path('tests/unit/test_forgeue_command_markdown.py'); print(p.exists(), p.stat().st_size)"`
Expected: `True <size>`

- [ ] **Step 2.2: Write failing test case `test_change_apply_subagent_cascade_includes_subagent_driven_discipline`**

在 `tests/unit/test_forgeue_command_markdown.py` 末尾 append:

```python
def test_change_apply_subagent_cascade_includes_subagent_driven_discipline():
    """tasks.md §2.2 fence (sections-aware assertion，沿 codex round 2 F1
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
    的退化:quick reference table inline 后字符串自然出现 ≥ 1 次,即使
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
    # 任一 --invoked 行后续应含 subagent-driven-discipline(可能在同行或紧邻续行)
    # 简化:检查 preflight_section 内 --invoked 行所在的 shell block 含 subagent-driven-discipline
    # 取 --invoked 行起到下一空白行止作为 shell command block
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
        # fallback:取 invoked_skills: 后 1000 字符
        next_field_idx = invoked_skills_idx + 1000
    block_list_section = template_section[invoked_skills_idx:next_field_idx]
    assert "subagent-driven-discipline" in block_list_section, (
        "skill_cascade_audit.invoked_skills YAML block-list must include "
        f"'subagent-driven-discipline'. Found block-list section:\n{block_list_section}"
    )
```

- [ ] **Step 2.3: Run new test → expect FAIL(Phase A commit 后应 PASS,但本 step run 在 Phase B 内,Phase A 已先 commit → expect PASS)**

Run: `python -m pytest tests/unit/test_forgeue_command_markdown.py::test_change_apply_subagent_cascade_includes_subagent_driven_discipline -v`
Expected: PASS(若 FAIL 表明 Phase A commit 1.1 / 1.3 未生效)

- [ ] **Step 2.4: Write failing test case `test_change_apply_subagent_dispatch_step_references_discipline_section_1`**

在 `tests/unit/test_forgeue_command_markdown.py` 末尾继续 append:

```python
def test_change_apply_subagent_dispatch_step_references_discipline_section_1():
    """tasks.md §2.3 fence: change-apply-subagent.md Steps 第 8 sub-step 必
    引用 discipline §1 + 含 model tier quick reference table 关键 row。

    防止 sub-step 退化为只 mention "参考 discipline" 不带 inline reference table
    导致 controller 不查 skill 文件就 default Opus(沿 D2 β 选,inline reference
    table 是协议核心 — 减查阅成本)。
    """
    text = (CMD_DIR / "change-apply-subagent.md").read_text(encoding="utf-8")
    # discipline §1 引用
    assert "discipline §1" in text or "subagent-driven-discipline` skill §1" in text, (
        "Steps 第 8 sub-step should reference discipline §1 (28-subtype model tier table)"
    )
    # quick reference table 关键 3 row 同时存在
    assert "implementer" in text, "Quick reference table missing 'implementer' row"
    assert "spec_reviewer" in text, "Quick reference table missing 'spec_reviewer' row"
    assert "code_quality" in text, "Quick reference table missing 'code_quality' row"
```

- [ ] **Step 2.5: Run new test → expect PASS**

Run: `python -m pytest tests/unit/test_forgeue_command_markdown.py::test_change_apply_subagent_dispatch_step_references_discipline_section_1 -v`
Expected: PASS

- [ ] **Step 2.6: Write negative assertion test `test_change_apply_direct_does_not_reference_subagent_driven_discipline`**(沿 codex round 1 F1 [high] accepted-codex)

在 `tests/unit/test_forgeue_command_markdown.py` 末尾继续 append:

```python
def test_change_apply_direct_does_not_reference_subagent_driven_discipline():
    """tasks.md §2.4 fence: change-apply-direct.md 不含 subagent-driven-discipline。

    根因(沿 codex round 1 F1 [high] accepted-codex):direct 路径无 subagent
    dispatch → discipline §1 model tier 协议无 dispatch 触发面(NG2 显式排除);
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
```

- [ ] **Step 2.7: Run negative assertion test → expect PASS**

Run: `python -m pytest tests/unit/test_forgeue_command_markdown.py::test_change_apply_direct_does_not_reference_subagent_driven_discipline -v`
Expected: PASS(`change-apply-direct.md` 不应被 Phase A 误改)

- [ ] **Step 2.8: Run full test_forgeue_command_markdown.py to ensure no regression**

Run: `python -m pytest tests/unit/test_forgeue_command_markdown.py -v`
Expected: 全 PASS(既有 case + 3 新 case)

- [ ] **Step 2.9: Commit Phase B**

```bash
git add tests/unit/test_forgeue_command_markdown.py
git commit -m "test(forgeue): fence cascade discipline + model tier + direct path negative assertion"
```

---

## Task 3: Phase D — Doc-sync gate(轻量;3 文档)

**Files:**
- Modify: `docs/ai_workflow/forgeue_integrated_ai_workflow.md` (§B 命令矩阵 `change-apply-subagent` 行 sister skill list)
- Modify: `CHANGELOG.md` (Unreleased Added 段顶部加 entry)

**Anchors:** `tasks.md#3.1` / `tasks.md#3.2` / `tasks.md#3.3` / `tasks.md#3.4`

**Decisions:** G5 (doc-sync 同步 §B 命令矩阵 + CHANGELOG)

- [ ] **Step 3.1: 检查 §B 命令矩阵 `change-apply-subagent` 行 sister skill list 现状**

Run: `python -c "import re; t = open('docs/ai_workflow/forgeue_integrated_ai_workflow.md', encoding='utf-8').read(); m = re.search(r'\\| /forgeue:change-apply-subagent .*?\\n', t); print(m.group(0) if m else 'NOT FOUND')"`
Expected: 找到行 + 检查是否含 `subagent-driven-discipline`

- [ ] **Step 3.2: 修改 §B 命令矩阵行(若现 list 不含 discipline)**

在 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B 命令矩阵 `/forgeue:change-apply-subagent` 行的 sister skill list cell 加 `subagent-driven-discipline`(若现有不含;若已含跳过)。

- [ ] **Step 3.3: 加 CHANGELOG.md Unreleased Added entry**

在 `CHANGELOG.md` Unreleased Added 段顶部加:

```markdown
- ForgeUE: `/forgeue:change-apply-subagent` Preflight Skill Cascade 列表加 `subagent-driven-discipline` companion skill;Steps 第 8 step 加 model tier sub-step(沿 discipline §1 表)+ quick reference table;evidence frontmatter `skill_cascade_audit.invoked_skills` template 加 `subagent-driven-discipline`。Fence test 2 case(`test_forgeue_command_markdown.py`)防回归。
```

- [ ] **Step 3.4: Run doc-sync check + enum cross-ref check**

Run: `python tools/forgeue_doc_sync_check.py --change enforce-subagent-discipline-cascade`
Expected: exit 0(本 change scope 不触 src/ → 不需修 LLD/HLD/test_spec)

Run: `python -m tools.forgeue_enum_cross_ref_check`
Expected: exit 0(本 change 不动 enum;baseline 应不变)

- [ ] **Step 3.5: Commit Phase D**

```bash
git add docs/ai_workflow/forgeue_integrated_ai_workflow.md CHANGELOG.md
git commit -m "docs(forgeue): sync cascade discipline addition to workflow.md + CHANGELOG"
```

---

## Task 4: Phase E — Verify + Review + Finish + Archive

**Files:** 无新代码改动;只跑工具 + evidence 收口。

**Anchors:** `tasks.md#4.1` / `tasks.md#4.2` / `tasks.md#4.3` / `tasks.md#4.4` / `tasks.md#4.5` / `tasks.md#4.6`

- [ ] **Step 4.1: Run full test suite**

Run: `python -m pytest -q`
Expected: baseline + ~2 fence(2.2 + 2.3 加的 `test_change_apply_subagent_*`)无回归

- [ ] **Step 4.2: `/forgeue:change-verify --level 0`**

Run: `/forgeue:change-verify enforce-subagent-discipline-cascade --level 0` + codex `/codex:review --base main` verification hook
Expected: Level 0 PASS;codex review verdict consume

- [ ] **Step 4.3: `/forgeue:change-review` finalize**

(Note: 沿 tasks.md 4.3 inline writeback — Final reviewer subagent 已在 change-apply-subagent 内跑;此 step 仅 controller-side wrap-up)。

**Final reviewer 6 项验证责任**(沿 design.md D6.1 + codex round 1 F2 + round 2 F2 accepted-codex,任一 ✗ → BLOCKED):

1. Phase A evidence body `## Dogfood Acceptance` 段含 `bootstrap_phase: true` + `cascade_enforcement_source: controller_manual`(`task_1_*.md`)
2. Phase B/D evidence body `## Dogfood Acceptance` 段含 `bootstrap_phase: false` + `cascade_enforcement_source: command_template_auto`(`task_2_*.md` / `task_3_*.md`)
3. Phase A commit 时间戳:`git log --pretty='%H %cI' -- .claude/commands/forgeue/change-apply-subagent.md`,取 Phase A commit ISO 时间;Phase B/D evidence 文件 mtime 或 stage timestamp 晚于此
4. Phase A 命令模板 commit 内容:`git show <Phase A commit>:.claude/commands/forgeue/change-apply-subagent.md | grep '\\-\\-invoked'` 验证 `--invoked` 行已含 `subagent-driven-discipline`
5. **Phase B/D evidence frontmatter cascade declared content**(沿 round 2 F2)— 逐 Phase B/D evidence file 解析 frontmatter,assert `skill_cascade_audit.invoked_skills` block-list 含 `subagent-driven-discipline`(实际 dispatch 时硬证据)
6. **Phase B/D cascade 时间窗口**(沿 round 2 F2)— 逐 Phase B/D evidence file 取 `skill_cascade_audit.cascade_check_pass_at` ISO 时间,assert 大于 Phase A 命令模板 commit ISO 时间(沿第 3 项时间戳;证 Phase B/D cascade check 实际跑在 Phase A commit 之后)

Run: `/forgeue:change-review enforce-subagent-discipline-cascade` + codex `/codex:adversarial-review --background` mixed scope
Expected: cross-check disputed_open=0;Final reviewer evidence body 含 6 项验证表(✓ / ✗ + 证据 file path + 提取字段值 + 时间戳)

- [ ] **Step 4.4: `/forgeue:change-doc-sync`**

Run: `/forgeue:change-doc-sync enforce-subagent-discipline-cascade`
Expected: 10 文档 sync gate PASS(本 change 多数 SKIP;只 §B 命令矩阵 + CHANGELOG REQUIRED)

- [ ] **Step 4.5: `/forgeue:change-finish`**

Run: `/forgeue:change-finish enforce-subagent-discipline-cascade`
Expected: finish_gate 12-key frontmatter 完整性 + writeback 真实性 + cross-check disputed_open=0 + tasks unchecked=0 + `openspec validate --strict` PASS

- [ ] **Step 4.6: Archive change(用户授权后)+ followon update**

(Fence #1 不可逆 → MUST 用户授权)

Run: 用户授权后 `openspec archive enforce-subagent-discipline-cascade`
Expected: archive 落 `openspec/changes/archive/2026-05-08-enforce-subagent-discipline-cascade/`

- [ ] **Step 4.7: 更新 followon backlog active.md**

加 1 follow-on candidate `audit-archived-subagent-budget-true-cost-vs-discipline-tier`(low priority,仅做事实记录,不 fix archived budget log)。

```bash
# 在 openspec/backlog/active.md 加 entry,然后 commit
git add openspec/backlog/active.md
git commit -m "docs(forgeue): add followon audit-archived-subagent-budget-true-cost"
```

---

## Self-Review Checklist

**1. Spec coverage:** 

| design.md / tasks.md 要求 | 对应 Task |
|---|---|
| G1 cascade `--invoked` 加 discipline | Task 1.1 |
| G2 Steps 第 8 model tier sub-step + table | Task 1.2 |
| G3 evidence frontmatter template 加 discipline | Task 1.3 |
| G4 1-2 fence test(实际 3 fence — Step 2.2 section-aware 沿 round 2 F1 accepted-codex;Step 2.4 model tier reference;Step 2.6 negative assertion 沿 round 1 F1)| Task 2.2 + 2.4 + 2.6 |
| G5 doc-sync §B 命令矩阵 + CHANGELOG | Task 3.2 + 3.3 |
| D6 走 subagent dispatch 路径(self-reference dogfood)| 整 plan via `/forgeue:change-apply-subagent` |
| D6.1 bootstrap vs acceptance phase 区分(沿 F2 accepted-codex)| Bootstrap Phase 协议段 + 每 Task 必加 `## Dogfood Acceptance` body section + Task 4 Final reviewer 4 项验证责任 |
| Fence #1 archive 升级用户 | Task 4.6 |
| Followon `audit-archived-subagent-budget-true-cost` | Task 4.7 |

无 gap。

**2. Placeholder scan:** 无 TBD / TODO / "implement later" / "Add appropriate error handling" / "fill in details"。Step 内含完整 markdown / python / bash 代码。

**3. Type consistency:** 

- `test_change_apply_subagent_cascade_includes_subagent_driven_discipline`(Step 2.2)+ `test_change_apply_subagent_dispatch_step_references_discipline_section_1`(Step 2.4)— 两 test function name 与 design.md D3 描述一致。
- `subagent-driven-discipline` skill name 字符串在所有 task 一致(Task 1.1 / 1.3 / 2.2 / 3.2)。
- evidence frontmatter `skill_cascade_audit.invoked_skills` block-list 风格沿 change-apply-subagent.md L144-148 现有 template,新加行用 `- subagent-driven-discipline`(YAML block-list 风格,不用 flow `[..., subagent-driven-discipline]` — `_common.parse_frontmatter` 不支持 flow)。

**4. Potential drift candidates(交 cross-check `## D` 评估):**

- D-DriftCandidate-1: design.md D3 提到的 `test_forgeue_command_templates.py` 实际不存在;现存 `test_forgeue_command_markdown.py` 是 functional equivalent。本 plan 选择扩既有 file(沿 D3 phrasing "若 unit 已有 X 直接扩;否则新建" 的 fallback "新建" 反而违反"沿 ForgeUE 既有命令模板测试模式"原则)。inline writeback design.md D3 文件名 → `test_forgeue_command_markdown.py` 是 minor doc-sync drift,不阻断 S3。
- PlanNote-SubStepNumbering: Step 1.2 sub-step 编号占位 `Sub-step 8.x:` — 实施时 controller 看 change-apply-subagent.md L64 区域 Step 8 现有 sub-step 编号决定下一编号(例如已是 `Step 8.1` 则新加 `Step 8.2`)。本 plan 不强制具体编号(实施时 minor 自由度)。
