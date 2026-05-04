---
change_id: enhance-workflow-automation
stage: S4
evidence_type: subagent_code_quality_review
contract_refs:
  - openspec/changes/enhance-workflow-automation/tasks.md
  - openspec/changes/enhance-workflow-automation/design.md
  - openspec/changes/enhance-workflow-automation/proposal.md
  - openspec/changes/enhance-workflow-automation/specs/examples-and-acceptance/spec.md
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: direct_invocation
codex_plugin_available: true
triggered_by_command: change-apply-subagent
autonomy_decision: claude_autonomous
codex_review_ref: null
created_at: 2026-05-05T00:00:00Z
---

# Task P3 Code Quality Review — 11 处文档同步

## 审查对象

- Commit: `484f839`
- 审查范围: P3 文档同步 11 处(doc-only PR)
- 参考文档: `design.md`(D-AutonomyBoundary / D-FenceTaxonomy) + `specs/examples-and-acceptance/spec.md`

## 方法

对每份变更文件独立 `git show 484f839 -- <file>` 读取实际 diff,对照 design.md 权威源验证
一致性、cross-reference 完整性、内容质量与可操作性。不基于 spec reviewer 结论,独立核验。

---

## Strengths

- **§C 内部一致性强**: §C.1 → §C.6 六节形成完整闭环 — 自主路径描述(C.1)→ 6 类 fence 表(C.2)→
  Fence #3 Verdict Normalization 细化(C.3)→ D-DefaultBackground 轮询协议(C.4)→
  D-CodexContextBridge 注入语法(C.5)→ Edge cases 兜底(C.6)。每节确实有独立语义,无明显
  冗余节。
- **design.md 回指明确**: §C 开头 `> 本节描述 D-AutonomyBoundary 决议(enhance-workflow-automation
  change)。完整设计见 openspec/changes/enhance-workflow-automation/design.md。` —— 读者
  明确知道 design.md 是权威源,§C 是工作流视角精简描述。
- **Verdict Normalization 8-row 表完整正确**: 与 design.md D-FenceTaxonomy §Fence #3 逐行
  对照,判定列与决策列语义一致;per-finding 2 个额外触发维度也正确保留。
- **CHANGELOG SHA 全验证通过**: 8 个 SHA (`99540e2` / `1ea80b5` / `730de52` / `55d15d7` /
  `1e4dfb9` / `8e897c4` / `c6913ae` / `8b1f9cc`)均为真实可访问 commit,且对应 commit
  message 与 CHANGELOG 描述语义匹配。
- **测试计数处理正确**: CHANGELOG 写 "以 `python -m pytest -q` 实测为准" 而非硬编码数字 —
  符合项目 "不硬编码测试总数" 纪律。
- **README/AGENTS/CLAUDE 三份文档有意义区分**:
  - `README.md`: 工具链视角 (+1 行扩展现有工具链段 + 单独新行 ADR-010 导读),面向新用户
  - `AGENTS.md`: 外部 agent 视角,显式加入 `AGENTS.md` 自身为 fence #4 约束源(其他文档无此行)
  - `CLAUDE.md`: Claude 自身行为规则视角,格式沿用编号列表(与同文档其他禁令格式一致)
  三份文档的受众语境有差异,内容虽相近但不是无差别 copy-paste。
- **forgeue_quickstart.md S2/S5/S6 更新均可操作**:
  - S2: 新增 `(默认 background dispatch,D-DefaultBackground)` + `(round N+1 时 prompt 首段
    自动注入...)` — 用户/Claude 知道要做什么不同的事
  - S5: 新增 codex verification hook block,说明 job id 存哪、用什么命令轮询、`concurred` 的
    前提条件 — 具体可执行
  - S6: 新增 `autonomy_decision` 字段三种典型场景 + 新增"✓ /codex:status + /codex:result 拿完整
    output 后才写 concurred" 关键检查项 + 新增"✗ background job 未完成就写 concurred" 常见错误
    — 全部可操作,非纯描述性
- **ADR-010 行格式正确**: 与 ADR-007/009 同款四列格式(ADR-id / 决策短句 / 理由详述 / 无单独
  status 列,status 内嵌理由);`88% rubber-stamp(22/25)` 数据来源于 design.md §Context,有
  实证支撑。
- **acceptance_report ADR-010 行内容完整**: 实装状态列包含具体实装清单(`autonomy_decision 字段 +
  forgeue_finish_gate _check_autonomy_boundary + 9 forgeue 命令模板 + 2 codex 命令模板`)。

---

## Issues

### Critical

无 critical 级别问题。

### Important

**I-1: 9 个 forgeue 命令模板未更新 §D 编号引用(11 个文件外的遗漏)**

`change-doc-sync.md`(line 92)和 `forgeue-doc-sync-gate/SKILL.md`(line 100)引用:
```
forgeue_integrated_ai_workflow.md §C(Documentation Sync Gate 应用流程)
```
此处 §C 在 484f839 之后实际上已变为 §D。commit 484f839 未修改这两个文件:
- `.claude/commands/forgeue/change-doc-sync.md` — NOT in commit
- `.claude/skills/forgeue-doc-sync-gate/SKILL.md` — NOT in commit

此外 `.claude/commands/forgeue/` 下多个命令文件引用 `§D.x`(State Machine),在 484f839 后
实际内容已变为 `§E.x`,但这些文件也未在 commit 内更新:
- `change-debug.md:75`: `§D.3(DRIFT type 4)` → 应为 `§E.3`
- `change-plan.md:82`: `§D.5/§D.6` → 应为 `§E.5/§E.6`
- `change-status.md:76`: `§D.1(evidence 子目录结构)` → 应为 `§E.1`
- `change-apply-direct.md:92`: `§D` → 应为 `§E`
- `change-finish.md:84`: `§D` → 应为 `§E`
- `change-review.md:89`: `§D` → 应为 `§E`
- `change-verify.md:84`: `§D` → 应为 `§E`

共计 9 个遗漏文件(含 2 个 §C→§D 错误 + 7 个 §D→§E 错误)。这些命令模板在 workflow 执行
时是 Claude 的操作指引;引用错误节号会导致导航失败,操作者找不到对应内容。

**建议修复**: 对以上 9 个文件在同一 commit 或后续 fix commit 中更新引用。注意 `change-doc-sync.md`
和 `forgeue-doc-sync-gate/SKILL.md` 是禁令文件范围(`不修改 OpenSpec 默认产物全集` 中的
`.claude/skills/openspec-*`),但 `forgeue-doc-sync-gate` 是 ForgeUE 自定义 skill 而非 OpenSpec
默认产物,应在可修改范围内。

**I-2: §C.2 fence 表 与 design.md D-FenceTaxonomy 表 schema 不同 — 未声明简化原因**

design.md D-FenceTaxonomy 表 3 列: `Fence # | Trigger keyword(命令意图层) | 触发示例`

§C.2 表 3 列: `Fence # | 类别 | 触发关键字 / 条件`

差异:
1. "Trigger keyword(命令意图层)" 标题改为 "触发关键字 / 条件" — 丢失了"命令意图层"的
   重要语义限定(这列值是供 Claude controller scan 自身计划描述时匹配的 keyword,不是
   任意条件描述)
2. "触发示例" 一列在 §C.2 完全省略 — design.md 中该列提供了有价值的具体示例(
   `"推到 origin"` / `"归档 change"` 等)供 Claude 理解 keyword 匹配意图

§C 开头有 design.md 回指,但没有说明"§C.2 是 design.md D-FenceTaxonomy 的简化版,省略了
触发示例列,以可操作触发字符串代替命令意图层标题"。读者可能混淆两表是否等价。

对于在命令模板里工作的 Claude controller 来说,"命令意图层"的语义很重要 — 因为 fence
匹配是 Claude 在 step 执行前 grep 自身计划描述时发生的,该列 title 明确了 scan 的是
"意图层字符串"而非任意 log text。

**建议**: 在 §C.2 表内或表下加一行说明,如:`(表为 design.md D-FenceTaxonomy 简化视图,
省略触发示例列;完整 trigger keyword 语义及示例见 design.md 源表)`。

### Minor

**M-1: README.md §4.4 变为 §4.5 后,commands/SKILL.md 引用未更新**

`change-doc-sync.md:90` 和 `forgeue-doc-sync-gate/SKILL.md:11,97` 引用
`docs/ai_workflow/README.md §4.4(tasks.md 必含段模板)` — 该节在 484f839 中已移为 §4.5(因
新增 §4.4 "决策权下放")。但这些文件不在 484f839 的修改列表中。

影响: 找不到正确节号,但 §4.5 内容本身完整,人工搜索能定位;比 I-1 的 §C/§D/§E 节号问题
轻微。

`forgeue_integrated_ai_workflow.md:317` 也引用了 `§4.4 tasks.md 必含段模板`,该文件在 484f839
中有修改但此行未更新。

**建议**: 与 I-1 一并修复,更新为 §4.5。

**M-2: CHANGELOG entry 中"测试覆盖"描述信息密度低**

```
**测试覆盖**:以 `python -m pytest -q` 实测为准
(文档 + finish_gate fence + forgeue_command_markdown fence + codex_command_markdown fence)
```

- 未给出任何数字(1483 passed 信息只在 task_p3_implementer.md 中);
- 括号内的 fence 列表仅为 module 级,未指明哪些是 P3 新增的 fence 守门 vs P0/P1/P2 已有的

从 implementer evidence 知道实测结果是 1483 passed / 1 skipped,但 CHANGELOG 读者看不到这个
数字。不是严重缺陷(项目约定不硬编码),但"以实测为准"是空白信息,P3 本身是纯 doc change,
无新测试,不如注明"P3 doc-only,无新测试;1483/1483 pytest 回归全绿(详见 task_p3_implementer.md)"。

**M-3: §C.5 D-CodexContextBridge 省略了 Round counter 文件的 git-tracking 决策**

design.md D-CodexContextBridge 明确写:
```
Round counter 状态:落在 notes/codex_<review_type>_round_counter.txt
(每个 review subject 一份,sticky 跨 controller session)。
```
并在 OQ-1 讨论: "倾向:git-tracked(evidence 一部分,审计需要;.gitignore 不加)"

§C.5 中对应段落:
```
Round counter 状态落 notes/codex_<review_type>_round_counter.txt
(sticky 跨 controller session,git-tracked)
```

"git-tracked" 已注明(正确),但该决策的背景 — 为什么 git-tracked 而不是本地 state 文件 — 在
§C.5 中没有任何说明。OQ-1 是有价值的设计判断(审计可追踪 vs 本地状态)。对于 §C 作为操作
指引文档来说,仅写"git-tracked"而不写为什么,可能导致未来维护者误认为这是无关紧要的实现细节
而改为 .gitignore。

影响低(OQ-1 判断在 design.md 有记录),但 §C.5 作为 autonomy boundary 协议文档应该至少一行
说明原因。

**M-4: §C.6 "Self-host bootstrap 豁免" 内容对 P3 归档后读者已无操作意义**

§C.6 edge case 第 3 条:
```
Self-host bootstrap 豁免 — 本 change 实施期间 fence 命令模板还没落地时,controller 临时在
planning layer 自检 6 类 trigger(沿 D-SelfHost 模式);archive 后走命令模板
```

这是 enhance-workflow-automation change 自身实施期间的临时豁免说明。一旦本 change archive,
这条 edge case 对任何后续 change 的读者都无实际意义 — 因为命令模板(P1)已落地,bootstrap
豁免已结束。长期驻留在 §C.6 会让读者误以为有某些场景仍需要 planning layer 临时自检。

建议: 此条可在 archive 时移除,或加 `(本 change 实施期间临时豁免,archive 后可删)` 的
注释以便清理。

---

## Drift Risk Assessment

**D-FenceTaxonomy 表复制漂移风险**: 低-中(acknowledged + 可接受)

§C.2 表是 design.md D-FenceTaxonomy 的简化版,列 schema 不同:
- 丢失了"触发示例"列(具体示例信息)
- "命令意图层"语义标注从列标题中消失

§C 开头有 design.md 回指(`完整设计见 openspec/changes/enhance-workflow-automation/design.md`),
因此表格不是无来源的孤立复制。然而:
1. §C 文档是 permanent doc(不 archive);design.md 是 change-scoped artifact(随 change archive)
2. Change archive 后,读者只能在 `openspec/changes/archive/...` 里找到 design.md,而 §C 常驻
   `docs/ai_workflow/` 并是主要操作参考
3. 两表的列 schema 差异未在 §C 中声明,未来修改 design.md 时维护者可能不知道 §C.2 是派生表

建议在 §C.2 表下加一行: `(完整 trigger keyword 及触发示例见 design.md D-FenceTaxonomy,§C.2
为简化摘要版;design.md archive 后见 openspec/changes/archive/<date>-enhance-workflow-automation/)`

**Verdict Normalization 8-row 表复制漂移风险**: 低(可接受)

§C.3 与 design.md D-FenceTaxonomy Verdict Normalization 表 8 row 语义完全一致。差异仅在:
- design.md 有"推荐操作"第 4 列 + 每行括号内详细说明
- §C.3 表 3 列(省略"推荐操作"列 + 括号注释),以 `→ clause` 简化形式保留判定结果

§C.3 有 design.md 回指;8 row 判定逻辑不变;"推荐操作"在上下文中可推断。可接受。
两表核心 conflict/non-conflict 判定完全一致,不存在语义分歧风险。

---

## Assessment

**Overall: APPROVED_WITH_CONCERNS**

P3 文档同步的主体内容(§C 六节、CHANGELOG、README/AGENTS/CLAUDE 三表、quickstart 三 stage、
SKILL.md 表格、SRS/acceptance ADR 行)质量良好,与 design.md 设计决策语义一致,有实际可操
作性。关键 Critical 问题: 无。

主要遗留缺陷是 **I-1: 9 个 forgeue 命令模板文件未随 §C→§D / §D→§E 重编号更新**,包括
`change-doc-sync.md`、`forgeue-doc-sync-gate/SKILL.md` 及 7 个 `change-*.md` 命令文件。
这些是 workflow 执行期 Claude 的主要操作引用,错误节号会导致导航失败。该问题是
Important 级而非 Critical,因为这些文件在 484f839 中未被修改(不是引入新 bug,是遗漏更新),
且内容仍正确只是节号过期。应在 P4 或后续 fix commit 中补正。

**I-2(§C.2 表 schema 与 design.md 不同,未声明简化原因)** 是可操作性风险,
建议在 §C.2 表下加一行来源说明,防止后续维护者将两表误认为等价完整拷贝。

---

## Re-review (Round 2)

审查对象:commit `5207e1c`(在 484f839 之上,non-amend),implementer claim 修复 I-1 + I-2 + m-1。

### 验证方法

- `git show 5207e1c --stat` 确认 12 文件改动,新增 20 行删除 18 行
- `git log --oneline 484f839..5207e1c` 确认是 incremental commit non-amend
- `git grep "§C/§D/§E/§4.4/§4.5"` 全仓 scan,排除 archive 目录,逐条验真
- `python -m pytest -q` 实测回归

### per-fix verification

**I-1(broken navigation refs): ✅ APPROVED**

预期 11 处 → 实测 12 处全修复(implementer 比我列的 9 处多找出 3 处):

| 文件 | 旧 ref | 新 ref | 状态 |
|---|---|---|---|
| `.claude/commands/forgeue/change-doc-sync.md:92` | `§C` | `§D(...原 §C 顺延)` | ✅ |
| `.claude/commands/forgeue/change-debug.md:75` | `§D.3` | `§E.3(...原 §D.3 顺延)` | ✅ |
| `.claude/commands/forgeue/change-status.md:76` | `§D.1` | `§E.1(...原 §D.1 顺延)` | ✅ |
| `.claude/commands/forgeue/change-plan.md:82` | `§D.5/§D.6` | `§E.5/§E.6(...原 §D.5/§D.6 顺延)` | ✅ |
| `.claude/commands/forgeue/change-apply-direct.md:92` | `§D` | `§E(...原 §D 顺延)` | ✅ |
| `.claude/commands/forgeue/change-finish.md:84` | `§D` | `§E(...原 §D 顺延)` | ✅ |
| `.claude/commands/forgeue/change-review.md:89` | `§D` | `§E(...原 §D 顺延)` | ✅ |
| `.claude/commands/forgeue/change-verify.md:84` | `§D` | `§E(...原 §D 顺延)` | ✅ |
| `.claude/skills/forgeue-doc-sync-gate/SKILL.md:100` | `§C` | `§D(...原 §C 顺延)` | ✅ |
| `docs/ai_workflow/forgeue_quickstart.md:107` | `§D.3` | `§E.3(...原 §D.3 顺延)` | ✅ |
| `docs/ai_workflow/forgeue_quickstart.md:346` | `§D.1` | `§E.1(...原 §D.1 顺延)` | ✅ |
| `docs/ai_workflow/forgeue_quickstart.md:353` | `§D.2` | `§E.2(...原 §D.2 顺延)` | ✅ |
| `docs/ai_workflow/forgeue_quickstart.md:242` | `§C` | `§D(...原 §C 顺延)` | ✅ |
| `docs/ai_workflow/README.md:229` | `§D.4` | `§E.4(...原 §D.4 顺延)` | ✅ |

每处都加 "原 §X 在 enhance-workflow-automation change 后顺延" breadcrumb,符合 review 原始建议
"在 §C.2 表下加一行声明" 同款 navigability 改进思路。

**I-2(schema clarity):✅ APPROVED**

`docs/ai_workflow/forgeue_integrated_ai_workflow.md:240-241` §C.2 表前已加声明:

```
> 注:本表是 [openspec/changes/enhance-workflow-automation/design.md D-FenceTaxonomy](...)
> 完整 6 fence trigger 表的简化派生(省略 design.md 表里的"触发示例"列,本节聚焦关键字/条件
> 维度);**design.md D-FenceTaxonomy 是 source of truth**,触发示例与 implementation-layer
> keyword grep 协议见原表。
```

声明含 4 个关键要素:
1. ✅ relative-path link 到 design.md(可点击导航)
2. ✅ 简化原因(省略"触发示例"列)
3. ✅ 显式 source of truth 声明
4. ✅ 指引读者去原表找 implementation-layer keyword grep 协议

完全满足 round 1 I-2 建议范围。

**m-1(§4.4 → §4.5):✅ APPROVED**

3 处 active 引用全修:

| 文件 | 修复 |
|---|---|
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md:319` | `§4.5` + 加 "(原 §4.4 在 enhance-workflow-automation change 后顺延为 §4.5,因 §4.4 改为 决策权下放与 Autonomy Boundary)" |
| `.claude/skills/forgeue-doc-sync-gate/SKILL.md:11+97` | 显式列出 §4.4 决策权下放[新增] + §4.5 tasks.md 必含段[原 §4.4 顺延],信息密度更高 |
| `.claude/commands/forgeue/change-doc-sync.md:90` | 同上,§4.4 + §4.5 显式列出 |

修复方案选择正确:不仅是更新节号,还显式注明 "原 §4.4 顺延为 §4.5",读者可理解节号变迁
而不仅是看到新节号就疑惑"怎么节号跳了"。

`SRS.md:48` 的 §4.4 / §4.5 是 SRS 自身章节(不在 README §4 范围),正确不动。

### 测试回归

`python -m pytest -q` 实测:`1483 passed, 1 skipped in 49.27s` —— 与 484f839 实测一致(0 regression)。
跳过的 1 项是 `test_comfy_subprocess_video.py:523 symlink Windows 需要 admin 权限` 既有 expected
skip,与 5207e1c 无关。

### Archive 完整性

`git diff 484f839..5207e1c --stat` 检查 12 文件全在 active path:
- `.claude/commands/forgeue/` 8 文件
- `.claude/skills/forgeue-doc-sync-gate/SKILL.md`
- `docs/ai_workflow/{README,forgeue_integrated_ai_workflow,forgeue_quickstart}.md` 3 文件

`openspec/changes/archive/` 0 改动 — archive 完整保护。

### Round 1 backlog 状态

未修(implementer 明示留 backlog):

- **M-2** CHANGELOG 测试覆盖描述信息密度低 — 仍存在,但属 Minor + 项目"以实测为准"纪律,
  接受 backlog
- **M-3** §C.5 git-tracked 决策无背景说明 — 仍存在,Minor
- **M-4** §C.6 self-host bootstrap 豁免 archive 后无意义 — 仍存在,Minor + archive 时清理

这些 Minor 都不阻断 P3 finalize,留 follow-up 处理合理。

### Round 2 New Issues

**审查 5207e1c 后,在 forgeue_integrated_ai_workflow.md 自身发现 2 处 5207e1c 漏修的内部 §D 引用**:

- **N-1**(Minor):line 30 `(详 §A.4 + §D)`
  - 上下文:讨论 evidence 不能成为新规范源,"中心化的物理表达 = 回写不可绕过"
  - "回写" / "aligned_with_contract" / "drift_decision" 协议在新 §E.4(writeback 协议三态)
    + §E.2(12-key frontmatter),已不在 §D(现 §D 是 Documentation Sync Gate)
  - 应改为 `(详 §A.4 + §E)` 或更精准的 `§E.2 + §E.4`
- **N-2**(Minor):line 69 `回写不可绕过(详细机制见 §D)`
  - 同上,writeback "详细机制"在新 §E
  - 应改为 `详细机制见 §E`

这两处是 §C 插入导致原 §D State Machine + Writeback Protocol 顺延为 §E 时,文档自身内部对该
段的指代未跟着改。implementer 修了所有外部引用(其他 .md 文件)和 quickstart 的引用,但漏了
forgeue_integrated_ai_workflow.md 自己 §A 段(line 30)+ §A.4 段(line 69)对 §D 的内部
back-reference。

影响:Minor 级 — 文档读者读到 line 30/69 看到 "详 §D" 后到 §D Documentation Sync Gate 找不到
writeback 协议描述,需要再翻到 §E。不阻断 finalize,可在后续 fix commit 一并修。

注意 line 14(`本文档 §D 引用其规则`)是关于 Documentation Sync Gate 主规则衔接,新 §D 就是
Documentation Sync Gate,该 ref **正确不动** ✅(已逐字对照确认)。

### Final Verdict

**Round 2 Overall: ✅ APPROVED(with 2 minor follow-ups N-1 / N-2)**

I-1 + I-2 + m-1 三项 fix 全部高质量完成,5207e1c implementer 在 I-1 范围内主动扩展找到 round 1
未列的 3 处遗漏(`README.md:229` + 2 处 `forgeue_quickstart.md` 同源刷新),态度严谨。修复方式
不止是改节号,还加 breadcrumb 让节号变迁可追溯,可维护性提升明显。

新发现的 N-1 / N-2 是 5207e1c implementer 自己漏的 forgeue_integrated_ai_workflow.md 内部
back-reference,Minor 级,不阻断 P3 finalize;建议在后续小 fix commit 一并修,或纳入 doc-sync
gate 时统一处理。

测试 1483 pass/1 skipped 与基线持平,0 regression;archive 0 改动,无 OpenSpec 默认产物
被触动。P3 quality gate 通过。

