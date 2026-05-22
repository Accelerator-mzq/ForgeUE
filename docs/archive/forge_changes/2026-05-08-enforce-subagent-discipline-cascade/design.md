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
| α | `tests/unit/test_forgeue_command_markdown.py`(已存在的命令模板 markdown 静态扫 file,直接扩 case)|
| β | `tests/unit/test_forgeue_skill_cascade_check.py`(已 cover skill cascade tool 行为;扩它加命令模板静态扫)|
| γ | 新 file `tests/unit/test_change_apply_subagent_template.py`(粒度细)|

**决定**:**α**

**理由**:
- α 是命令模板内容静态扫,scope 是 markdown file 而非 cascade tool 行为 → 与 `test_forgeue_skill_cascade_check.py` 职责正交
- ForgeUE 既有命令模板测试 file 实际名为 `test_forgeue_command_markdown.py`(不是早期命名假设的 `test_forgeue_command_templates.py`);沿"既有命令模板测试模式"原则直接扩
- γ 粒度过细,one file per command template 太细碎

**实施**(沿 codex round 2 F1 [high] accepted-codex writeback `[本 commit]`,前序 round 1 F1 同 accepted):

3 个 fence case 覆盖 specificity:

1. **正向 section-aware assertion 1**(`change-apply-subagent.md` Preflight cascade 接入 + frontmatter template 接入)— `test_change_apply_subagent_cascade_includes_subagent_driven_discipline`:**section-aware parse**(沿 round 2 F1 accepted-codex,替代全文件 count):
   - 解析 `### Preflight Skill Cascade` section,定位 shell block 内 `--invoked` 行,assert 含 `subagent-driven-discipline`
   - 解析 Evidence Frontmatter Template section,定位 `skill_cascade_audit.invoked_skills` YAML block-list,assert 该 block-list 含 `subagent-driven-discipline`
   - **不**用全文件 `text.count(...) >= N`(round 2 F1 暴露:quick reference table inline 后 string 自然出现 ≥ 1 次,即使 `--invoked` / frontmatter template 漏改也可能 fence 误通过)

2. **正向 assertion 2**(`change-apply-subagent.md` Steps 第 8 sub-step model tier 引用)— `test_change_apply_subagent_dispatch_step_references_discipline_section_1`:read_text 含 `discipline §1` 引用 + 含 model tier quick reference table 关键 row(`implementer` + `spec_reviewer` + `code_quality` 同时存在)

3. **负向 assertion**(`change-apply-direct.md` 不接入 — NG2 边界)— `test_change_apply_direct_does_not_reference_subagent_driven_discipline`:`Path(".claude/commands/forgeue/change-apply-direct.md").read_text()` **不含** `subagent-driven-discipline` 字符串(direct 路径无 subagent dispatch → discipline §1 model tier 协议无 dispatch 触发面;防协议反向漂移 — direct 误加 cascade 或 future change 整 retire subagent 但漏改 direct)

**Archived 路径不扫**(verbal note 不需 assertion):fence file `CMD_DIR = .claude/commands/forgeue/` 只扫 active 命令文件;archived 在 `openspec/changes/archive/` 不在该 path,fence 自动不扫(沿 ForgeUE archive policy "归档即冻结")。

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

### D6:本 change 走 subagent 还是 direct 路径?

**选项**:

| 选项 | 描述 |
|---|---|
| α | direct 路径(`/forgeue:change-apply-direct`)— 沿"轻量 change < 3 micro-task"argument |
| **β(选)** | subagent dispatch 路径(`/forgeue:change-apply-subagent`)— 修改 workflow 协议自身的 change 默认 subagent + 本 change 自验证新 cascade 协议 |

**决定**:**β**

**理由**(沿 ForgeUE memory `feedback_self_reference_overcaution`,2026-05-06 user push back trigger):

1. **Dispatch flow 主体未被改/删** — 本 change 仅在 `change-apply-subagent.md` 命令模板内加 3 处内容(Preflight cascade `--invoked` 列表 + Steps 第 8 sub-step + evidence frontmatter template);dispatch flow 主体(派 implementer + 2 reviewer + final reviewer + 4 类 per-task evidence)完全不动 → subagent 路径自身仍可用
2. **Commit-by-commit forward progress 成立** — Phase A commit 命令模板修订后,Phase B subagent 派 implementer 跑 fence test 时读的是改完的命令模板(已含 discipline cascade 强制),不存在同一 phase 内 subagent 同时改命令文件 + 调用该命令的循环 self-reference
3. **本 change 是 workflow 协议层修订** — destructive 操作 risk 面虽小,但修改协议契约本身(cascade declared dependency)需要 spec reviewer + code quality reviewer 守门,subagent 4 类 per-task evidence 完整 audit trail 比 direct 路径单 implementer evidence 更可靠
4. **self-reference dogfood 是本 change 唯一可行的协议自验证窗口** — 修订 cascade 协议的 change 自身走该 cascade 协议是最直接的 acceptance test;dispatch 时 controller 必须显式按 discipline §1 表选 model + cascade `--invoked` 列表必须含 `subagent-driven-discipline`,直接验证修订生效
5. **工程量评估**:Phase A(3 处 markdown edit)+ Phase B(1-2 fence test 新建)+ Phase D(2 文档同步)~3-4 micro-task,处于 direct 边界但不显著低于;subagent overhead vs cascade dogfood 验证价值 trade-off 偏向 subagent

**实施 model tier 选择**(沿 D2 + discipline §1):

| Phase × subagent role | discipline §1 subtype | model |
|---|---|---|
| Phase A implementer(markdown 命令模板 3 处 edit;mechanical replace)| §1.1.1 mechanical | `haiku` |
| Phase A spec_reviewer(对照 design.md G1-G3 + tasks 1.1-1.3)| §1.2.1 string match | `haiku` |
| Phase A code_quality reviewer(markdown 文件无 runtime;只是格式正确性)| §1.3.1 style | `haiku` |
| Phase B implementer(fence test 新建 / extend;pattern matching ForgeUE 既有命令模板测试)| §1.1.2 pattern | `haiku` 或 `sonnet` |
| Phase B spec_reviewer(对照 design D3 + tasks 2.1-2.3)| §1.2.1 string match | `haiku` |
| Phase B code_quality reviewer(pytest fence 真实跑 + assertions)| §1.3.4 runtime correctness MANDATORY | `sonnet` |
| Phase D doc-sync 实施者(2 处 markdown semantic edit)| §1.5.2 semantic rewrite | `sonnet` |
| Final reviewer(cross-phase consistency + cascade dogfood 协议自验证)| §1.3.3 + §1.3.4 | `sonnet` |

**Drift writeback**:

- `drift_decision: written-back-to-design`
- `drift_reason: design.md D6 当前选 α direct,与 ForgeUE memory feedback_self_reference_overcaution 协议(workflow 协议 change 默认 subagent + dispatch flow 主体未动 + commit-by-commit forward progress 成立 → 走 subagent)冲突;切到 β subagent 路径自验证 cascade 协议`
- `writeback_commit`(本次 inline writeback commit)

### D6.1:Bootstrap vs Acceptance phase 区分(沿 codex round 1 F2 [medium] accepted-codex)

**Codex finding**:Phase A dispatch 时新模板尚未生效 — Phase A bootstrap 期 controller 必须 manual-bootstrap(主动 invoke discipline + 在 cascade `--invoked` 中带 discipline,不依赖命令模板 enforce);真正 self-dogfood acceptance 必须从 Phase B 开始,因为 Phase A commit 之后 cascade 才自动 enforce。

**协议**:

| Phase | bootstrap_phase | cascade enforcement source | controller manual override required? |
|---|---|---|---|
| Phase A(改命令模板)| `true` | controller manual(命令模板尚未含 discipline cascade)| YES — controller 主动按 ForgeUE memory `feedback_self_reference_overcaution` 协议 invoke discipline |
| Phase B(fence test)| `false` | 命令模板 L29 自动 enforce(已含 `subagent-driven-discipline`)| NO — cascade 自动 enforce |
| Phase D(doc-sync)| `false` | 命令模板 L29 自动 enforce | NO |
| Final reviewer | `false` | 命令模板 L29 自动 enforce | NO — 但必须在 cross-phase consistency review 中 audit Phase A bootstrap status,确认 ordering 合规 |

**Evidence audit**:

每个 per-task / final reviewer evidence body 末尾必加 `## Dogfood Acceptance` section(不动 12-key frontmatter schema — 沿 NG6),含:

```markdown
## Dogfood Acceptance

- bootstrap_phase: true | false
- cascade_enforcement_source: controller_manual | command_template_auto
- justification: <reason if bootstrap_phase: true,e.g. "Phase A 修改命令模板,cascade enforce 路径尚未生效,controller 主动 invoke discipline">
```

**Final reviewer 责任**(沿 codex round 1 F2 + round 2 F2 accepted-codex,**6 项验证**逐 evidence file 验真实性):

Final reviewer subagent 在 cross-phase consistency review 中 MUST 验证(任一 ✗ → BLOCKED + writeback design.md D6.1 标 disputed-permanent-drift):

1. **Phase A evidence body 标识**:`task_1_*.md` body 内 `## Dogfood Acceptance` 段含 `bootstrap_phase: true` + `cascade_enforcement_source: controller_manual`
2. **Phase B/D evidence body 标识**:`task_2_*.md` / `task_3_*.md` body 内 `## Dogfood Acceptance` 段含 `bootstrap_phase: false` + `cascade_enforcement_source: command_template_auto`
3. **Phase A commit 时序**:`git log --pretty='%H %cI' -- .claude/commands/forgeue/change-apply-subagent.md` 取 Phase A commit ISO 时间;Phase B/D evidence frontmatter `triggered_by` 时间戳(从 evidence 文件 mtime 或 stage timestamp 推断)晚于 Phase A commit 时间
4. **Phase A 命令模板 commit 内容**:`git show <Phase A commit>:.claude/commands/forgeue/change-apply-subagent.md | grep '\\-\\-invoked'` 验证 `--invoked` 行已含 `subagent-driven-discipline`(证 commit 内容已生效,但**不**单独证 Phase B/D 实际跑了该版本)
5. **Phase B/D evidence frontmatter cascade declared content**(沿 round 2 F2 accepted-codex):逐 Phase B/D evidence file 解析 frontmatter,assert `skill_cascade_audit.invoked_skills` block-list 含 `subagent-driven-discipline`(**实际 dispatch 时 cascade declared dependency 真的含 discipline 的硬证据**)
6. **Phase B/D cascade 时间窗口**(沿 round 2 F2 accepted-codex):逐 Phase B/D evidence file 取 `skill_cascade_audit.cascade_check_pass_at` ISO 时间,assert 大于 Phase A 命令模板 commit ISO 时间(沿第 3 项取的时间戳;证 Phase B/D cascade check 实际在 Phase A commit 之后跑,而非旧模板时期 backfill)

**实施**:Final reviewer subagent 在 review 输出 evidence body 必含 6 项 verdict 表,每项标 ✓ / ✗ + 证据(file path + 提取的字段值 + 时间戳)。任一 ✗ → return BLOCKED + Phase B/D evidence frontmatter `aligned_with_contract: false` + `drift_decision: disputed-permanent-drift`(本 change 实施失败信号)。

**Writeback**:

- `drift_decision: written-back-to-design`
- `drift_reason: codex round 1 F2 [medium] + round 2 F2 [high]: Final reviewer 验证 4 项扩为 6 项,加 Phase B/D evidence frontmatter cascade 真实性 + 时间窗口验证(防止 controller 自由文本伪证据)`
- `writeback_commit`(本次 + 后续 inline writeback commit)

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

4. **Phase D**:doc-sync(nominal scope:`forgeue_integrated_ai_workflow.md` §B 命令矩阵 `change-apply-subagent` 行 + `CHANGELOG.md`;实施时 `forgeue_doc_sync_check.py` 启发式 `ai_workflow_changed=True` 把 `README.md` / `CLAUDE.md` / `AGENTS.md` 标 REQUIRED → 实际 scope 扩为 5 file。沿 ForgeUE memory `feedback_doc_reader_usefulness_audit` audit 实际 reader usefulness:CLAUDE.md(主 reader,protocol 协议化 sync)+ README.md(用户面向 workflow ref)+ AGENTS.md(跨 agent runtime 一致)— controller inline 加 1 line minimal mention 到这 3 doc 让 doc-sync exit 0。Inline writeback 自 implementation 阶段暴露 contract gap [本 commit])

5. **Phase E**:verify + review + finish + archive(走 `/forgeue:change-apply-subagent` 整 dispatch flow;Phase A/B/D 各派 implementer + spec_reviewer + code_quality reviewer + Final reviewer 跨 phase consistency)

**Rollback**:git revert 命令模板 commit + fence test commit + doc 同步 commit;不影响其他 change 因为 archived path 走 legacy pass-through。

## Open Questions

无。所有 D-decision 均已选 + 评估;实施期暴露任何契约层 oversight 走标准 writeback 协议(`drift_decision: written-back-to-design`)回写本文件。
