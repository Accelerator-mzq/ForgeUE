## Context

### 当前状态

`/forgeue:change-apply-subagent` 命令模板 Preflight Skill Cascade Step(`.claude/commands/forgeue/change-apply-subagent.md` L20-35):

```bash
python tools/forgeue_skill_cascade_check.py \
    --skill superpowers:subagent-driven-development \
    --invoked superpowers:test-driven-development,superpowers:requesting-code-review,superpowers:finishing-a-development-branch
```

declared dependency 列了 3 个 superpowers skill,**漏 `subagent-driven-discipline`**。但 discipline skill description 顶部明文:
> "**Companion to `superpowers:subagent-driven-development`**"

且 §9 整段 sister skills 关系表对照 `subagent-driven-development` 与 discipline 各自职责(generic process scaffold vs scenario-specific judgment)。

### 实证后果(cluster-2 change `fix-export-d12-and-skipped-evidence-filter`,2026-05-08)

11 次 subagent dispatch:

| Phase | Subagent | discipline §1 推荐 model | 实际 model | Cost 后果 |
|---|---|---|---|---|
| A | implementer | §1.1.1 mechanical → `haiku` | Opus 4.7(default inherit)| ~6x over |
| A | spec_review | §1.2.1 string match → `haiku` | Opus 4.7 | ~10x over |
| A | code_quality | §1.3.4 runtime correctness → `sonnet` MANDATORY | Opus 4.7 | ~3x over |
| B | implementer | §1.1.3 multi-file integration → `sonnet` | Opus 4.7 | ~2-3x over |
| B | spec_review | §1.2.1 string match → `haiku` | Opus 4.7 | ~10x over |
| B | code_quality | §1.3.4 runtime correctness → `sonnet` | Opus 4.7 | ~3x over |
| C.1 | implementer | §1.4.2 integration test → `sonnet` | Opus 4.7 | ~2-3x over |
| C.1 | spec_review | §1.2.1 string match → `haiku` | Opus 4.7 | ~10x over |
| C.1 | code_quality | §1.3.4 runtime correctness → `sonnet` | Opus 4.7 | ~3x over |
| D | doc-sync | §1.5.1/§1.5.2 hybrid → `sonnet` | Opus 4.7 | ~2-3x over |
| Final | reviewer | §1.3.3+§1.3.4 + cross-phase → `sonnet` | Opus 4.7 | ~2-3x over |

预估真实总 cost `$7-10` vs budget log 填的 `$3.21`(填错 model 字段)。

### Constraints

- 不改 `tools/forgeue_skill_cascade_check.py`(该工具是 generic checker;接受 `--invoked` list 参数即可,不需扩工具语义)
- 不改 `forgeue-integrated-change-workflow` backbone skill(cascade 描述在命令模板层,backbone 仅引用)
- 不改 `/forgeue:change-apply-direct` 命令模板(direct 路径 controller 自跑,无 subagent dispatch,discipline 不强制 cascade)
- 改动尽量 minimal scope(命令模板 3 处 + 1-2 fence test);不引入新工具 / 新 ADR

### Stakeholders

- **未来走 `/forgeue:change-apply-subagent` 的 change**:本修订后默认强制 invoke discipline + dispatch 时显式选 model
- **`forgeue_finish_gate.py::_check_skill_cascade` fence**:从 evidence frontmatter `skill_cascade_audit.invoked_skills` 读出 list,verify 含 `subagent-driven-discipline`(本 fence 已实装,只需 cascade declared dependency 更新)

## Goals / Non-Goals

### Goals

- **G1**:`/forgeue:change-apply-subagent.md` Preflight Cascade Step `--invoked` 列表加 `subagent-driven-discipline`,使 controller 在 Step 主流程跑 `forgeue_skill_cascade_check.py` 时强制传该 skill,exit 5 if 漏 invoke
- **G2**:`/forgeue:change-apply-subagent.md` Steps 第 8 step(invoke `superpowers:subagent-driven-development` skill)增加 sub-step 明示 dispatch 前必参考 discipline §1 表选 model + 显式传 Agent tool `model:` 参数(强 default 协议)
- **G3**:evidence frontmatter `skill_cascade_audit.invoked_skills` template 加 `subagent-driven-discipline`,确保后续 finish_gate `_check_skill_cascade` fence 守门
- **G4**:加 1-2 fence test 静态扫命令模板含 `subagent-driven-discipline` 字符串(防回归)
- **G5**:Phase D doc-sync 同步 `forgeue_integrated_ai_workflow.md` §B 命令矩阵 `change-apply-subagent` 行 sister skill list 加 discipline + `CHANGELOG.md`

### Non-Goals

- **NG1**:不改 `tools/forgeue_skill_cascade_check.py` 工具语义(该工具 generic accept `--invoked`,无 hardcoded skill list)
- **NG2**:不强制 `/forgeue:change-apply-direct` cascade discipline(direct 路径无 subagent → discipline scope 不适用)
- **NG3**:不改 backbone skill `forgeue-integrated-change-workflow`(cascade 描述命令模板层维护)
- **NG4**:不引入新 ADR / 新 D-decision 体系层(本是命令模板层 cascade declared dependency 修订,不是协议级新决策)
- **NG5**:不补 archived cluster-2 change 的 budget log(archived 不动;留 follow-on 仅做事实记录)
- **NG6**:不改 evidence frontmatter `skill_cascade_audit` schema(只加 example list 内容,不改字段定义)
- **NG7**:不在本 change scope 引入"自动 model tier 选取"工具(让 controller 手动按 §1 表选,沿 discipline skill 设计原则 — manual judgment is feature, not bug)

## Decisions

### D1:Preflight cascade list 加 `subagent-driven-discipline` 还是 `forgeue-side-subagent-driven-discipline`?

**选项**:

| 选项 | 描述 |
|---|---|
| α(选)| 用 `subagent-driven-discipline`(skill 自家声明的 name)|
| β | 用 `forgeue:subagent-driven-discipline`(plugin-namespaced)|

**决定**:**α**

**理由**:Skill list 实际显示的 name 就是 `subagent-driven-discipline`(无 plugin prefix;它是 ForgeUE 自家 skill 但不在 `forgeue:` plugin namespace 下,直接在 `.claude/skills/` 注册)。`forgeue_skill_cascade_check.py` 接受 skill name 字符串,与 skill list 实际 name 一致即可。

### D2:Step 8 model tier sub-step 写法 — 文字提醒 vs 强制 `model:` 参数模板?

**选项**:

| 选项 | 描述 |
|---|---|
| α | 文字提醒:"dispatch 前请参考 discipline §1 表选 model" — 不强制 |
| **β(选)** | 加显式 dispatch 模板示例 + Agent tool `model:` 参数 — 强 default 协议;但保 controller override 余地 |

**决定**:**β**

**理由**:
- 沿 ForgeUE memory `feedback_dont_punt_executable_tasks` — 协议要明确,不能光"提醒"
- discipline §1 表已是协议化决策,命令模板把表的关键映射 inline 既减查阅成本又强制 controller 显式选
- 但保 controller override 余地(若 task subtype 难判 / 跨多 subtype):最终仍 trust controller judgment,只是 default cheap

**实施**:在 Step 8 sub-step 加 quick reference table:
```markdown
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

详细见 `subagent-driven-discipline` skill §1。
```

### D3:Fence test 写在 unit / integration / 哪 file?

**选项**:

| 选项 | 描述 |
|---|---|
| α | `tests/unit/test_forgeue_command_templates.py`(若存在则扩;否则新建)|
| β | `tests/unit/test_forgeue_skill_cascade_check.py`(已 cover skill cascade tool 行为;扩它加命令模板静态扫)|
| γ | 新 file `tests/unit/test_change_apply_subagent_template.py`(粒度细)|

**决定**:**α**

**理由**:
- α 是命令模板内容静态扫,scope 是 markdown file 而非 cascade tool 行为 → 与 `test_forgeue_skill_cascade_check.py` 职责正交
- 若 unit 已有 `test_forgeue_command_templates.py` 直接扩;否则新建一个,沿 ForgeUE 既有命令模板测试模式
- γ 粒度过细,one file per command template 太细碎

**实施**:
- 先 `Glob tests/unit/test_forgeue_command_templates.py`,若存在 append 1-2 case;若不存在新建
- Case:`test_change_apply_subagent_cascade_includes_subagent_driven_discipline` — `Path(".claude/commands/forgeue/change-apply-subagent.md").read_text()` 含 `subagent-driven-discipline` 字符串(`--invoked` 行 + `invoked_skills:` template list 行 — 两处都需要含)
- Case:`test_change_apply_subagent_dispatch_step_references_discipline_section_1` — read_text 含 `discipline §1` 或类似引用(确保 model tier 协议指向 §1 表)

### D4:是否 retroactively cascade 加到既有 archived change evidence?

**选项**:

| 选项 | 描述 |
|---|---|
| α | 不动 archived(沿 ForgeUE memory `feedback_dont_reference_retired_functionality` 类比 + ADR-014 `D-ArchivedReplayCompat`)|
| β | retroactive 改 archived `skill_cascade_audit.invoked_skills` 加 discipline + 写 history note |

**决定**:**α**

**理由**:archived 即冻结(沿历史 archived 4 change replay 兼容;`forgeue_finish_gate.py::_check_skill_cascade` 对 archived 走 legacy pass-through),不改 archived evidence。only forward;新 change 走新 cascade。

### D5:`/forgeue:change-apply-direct` 命令模板是否同步加 discipline?

**选项**:

| 选项 | 描述 |
|---|---|
| **α(选)** | 不加。direct 路径 controller 自跑实施,无 subagent dispatch → discipline §1 model tier 协议不适用(controller 已是固定 model parent session)|
| β | 加。controller 手动 invoke discipline 仍可能用得到(如 controller 自己派临时 ad-hoc subagent for 单点查询)|

**决定**:**α**

**理由**:
- direct 命令模板已注 "不派 subagent"(`/forgeue:change-apply-direct` description:"S3→S4-S5 fallback;executing-plans + TDD;不派 subagent");无 subagent → discipline §1 model tier 协议无 dispatch 触发面
- controller 主 session 自身的 model 由 user 选(Opus 4.7 / Sonnet 4.6 / 等),不在 cascade 范围
- 若 controller direct 路径偶有派 ad-hoc 单点 subagent(如 codex review),codex 自家命令(`/codex:adversarial-review`)不在 ForgeUE-side cascade 范围(沿 codex command N/A disclaimer)

### D6:本 change subagent dispatch 用什么 model(self-reference dogfood)?

**选项**:

| 选项 | 描述 |
|---|---|
| **α(选)** | direct 路径(`/forgeue:change-apply-direct`)— 本 change scope 极小(命令模板 3 处 edit + 1-2 fence test + doc-sync),< 3 micro-task → direct 协议适用 |
| β | subagent dispatch 路径,本 change 自验证新 cascade(implementer + reviewer + final review)|

**决定**:**α**

**理由**:
- 沿 `/forgeue:change-apply-subagent` 命令描述自家约定 "**轻量 change(< 3 micro-task)/ budget 紧张时改走 `/forgeue:change-apply-direct`**"
- 本 change 实施核心是 markdown 命令模板修订(3 处 edit)+ 1-2 fence test;不到 3 真正 micro-task,subagent dispatch overhead 远大于 controller 自跑
- self-reference dogfood 不必强 — discipline cascade 协议在后续 non-trivial change 自然验证(沿 ADR-013 dogfood `worktree_consent_outcome` 同款 - 后续 change 自然验证 not self-reference)

### D7:Doc-sync scope — 是否需更新 `subagent-driven-discipline` skill 自身?

**选项**:

| 选项 | 描述 |
|---|---|
| **α(选)** | 不动 discipline skill — skill 本身设计为 living document(§5 case studies + §6 catalog growing layer),由 §3.4 retrospect 自动增长;本 change 是 cascade 协议化层修订,不动 skill 内容 |
| β | 在 discipline skill 头部加 "本 skill 已被 `/forgeue:change-apply-subagent` cascade enforced" note |

**决定**:**α**

**理由**:
- discipline skill 已是 living document,有 §3.4 retrospect 自动增长协议
- "cascade enforced" 是命令模板层 fact,不是 skill 自身内容(写在 skill 反而模糊职责)
- 若需要 cross-ref,在 `forgeue_integrated_ai_workflow.md` §B 命令矩阵的 sister skill 列加 discipline 即可

## Risks / Trade-offs

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Fence test 静态扫 string match 过松 / 误报 | Low | Low | 用 specific string `subagent-driven-discipline`(skill 唯一 name),不 regex pattern |
| Controller dispatch 时手动选 model 仍可能 default Opus(协议化但不机械化)| Medium | Medium | Step 8 sub-step quick reference table inline + Agent tool `model:` 参数显式(若 controller 仍 default,后续 retrospect Q6 触发 case study 沉淀)|
| `--invoked` list 加新 skill 让 cascade fail 卡 archived change replay | Low | High | archived path 走 legacy pass-through(沿 D-ArchivedReplayCompat;archived evidence `skill_cascade_audit.invoked_skills` 不含新 skill 也不阻断)|
| Discipline skill rename / retire | Very low | Medium | 命令模板 + fence test 含 hard string;若 discipline skill rename,本 change 实施 + finish_gate fence 也得同步改;留 follow-on `subagent-driven-discipline-name-stability-tracking` |
| `forgeue_skill_cascade_check.py` 工具行为不识别新 skill name | Very low | Low | 工具 generic accept `--invoked` 字符串;不需改工具(D1 决策)|

## Migration Plan

简单 forward-only,无 breaking change:

1. **Phase A**:Edit `.claude/commands/forgeue/change-apply-subagent.md` 3 处:
   - Preflight Cascade `--invoked` list 加 `subagent-driven-discipline`
   - Steps 第 8 加 sub-step + model tier quick reference table
   - evidence frontmatter `skill_cascade_audit.invoked_skills` template list 加 `subagent-driven-discipline`

2. **Phase B**:加 1-2 fence test(`tests/unit/test_forgeue_command_templates.py`,若存在则扩;否则新建)。

3. **Phase C**(无 — 本 change 无 L2 / 无 P4 真机)

4. **Phase D**:doc-sync(`forgeue_integrated_ai_workflow.md` §B 命令矩阵 `change-apply-subagent` 行 + `CHANGELOG.md`)

5. **Phase E**:verify + review + finish + archive(direct 路径 controller 自跑;无 subagent dispatch)

**Rollback**:git revert 命令模板 commit + fence test commit + doc 同步 commit;不影响其他 change 因为 archived path 走 legacy pass-through。

## Open Questions

无。所有 D-decision 均已选 + 评估;实施期暴露任何契约层 oversight 走标准 writeback 协议(`drift_decision: written-back-to-design`)回写本文件。
