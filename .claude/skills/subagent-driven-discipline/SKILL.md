---
name: subagent-driven-discipline
description: Universal controller-side discipline for subagent-driven-development workflows — model selection by task complexity / STRICT cwd verify / controller cross-verify / strict reviewer prompts / cherry-pick recovery / inline fix vs round 2 decision / skip review boundary / cost-benefit framework. Living catalog:patterns 上层稳定,case studies 下层随每个项目实证增长。Companion to `superpowers:subagent-driven-development`(generic process scaffold)— 本 skill 补 controller-side scenario judgment 40%。
license: MIT
compatibility: Claude Code Agent tool + python -m pytest;sister to superpowers:subagent-driven-development(generic 3-stage process)
metadata:
  author: forgeue (initial seed),subsequent contributors via case study additions
  version: "1.1"
  pattern_count: 8
  case_study_count: 1
---

Universal controller-side discipline for `superpowers:subagent-driven-development` workflows。Sister skill 补足 generic process scaffold 之外的 controller-side scenario judgment(model selection by task type / cwd 严格 verify / cross-verify subagent self-report / strict reviewer prompts / cherry-pick recovery / inline fix vs round 2 / skip review boundary / cost-benefit framework)。

**何时启用**:任何项目使用 `superpowers:subagent-driven-development` 派 implementer + reviewer subagents 时,controller 主 session 在 dispatch Agent tool 之前 + 收 return 之后 + commit 之前 — 全流程参考本 skill 决策。

**真源**:
- `superpowers:subagent-driven-development`(generic process scaffold;**不复制不引用** prompt 模板)
- 本 skill **patterns**(§1):跨项目通用模式
- 本 skill **case studies**(§2):具体项目实证(随每个新项目实施增长)

---

## §1 Universal Patterns(stable layer — 跨项目通用)

### Pattern 1: Model Selection by Task Complexity

**问题**:Agent tool dispatch 时 omit `model` parameter → subagent inherits 父 session model;往往 over-powered + over-cost。

**Pattern**:dispatch 时**显式传 `model:` 参数**,按任务复杂度选 tier。

| Task 特征 | model tier | 适用 subagent 角色 |
|---|---|---|
| Plan 含完整代码样例 + 1-3 stdlib 文件 + well-known pattern | `haiku` | implementer |
| Mechanical text edit / markdown lint / pattern matching | `haiku` | implementer + spec_reviewer |
| Multi-file integration / cross-module wiring / N fence test | `sonnet` | implementer |
| Code quality review(judgment-heavy + multi-file context) | `sonnet`(**不可省**) | code_quality_reviewer always |
| Architecture decision / new ABC / spec drafting | `opus` | implementer for design phases only |
| Final综合 review across all phases | `sonnet` 或 `opus`(stakes-dependent) | final_reviewer |

**关键边界**:
- Haiku implementer 适用边界 — Plan 必须含**完整代码样例 + 具体 fence 名 + 完整测试模板**;不能凭 spec 自由设计。
- Sonnet code_quality 不可省 — Haiku review 看不到 runtime correctness 问题(只看静态字符串匹配)。
- Opus 留给 controller-level work(design / cross-check ## A 立场冻结 / architectural drafting),不外包给 subagent。

### Pattern 2: STRICT cwd verify(防 worktree-scope leak)

**问题**:Agent tool subagent 继承父 session cwd,但**不严格遵循** dispatch prompt 内的 cwd 指令。subagent 可能在错误 directory(主 repo dev branch / 兄弟 worktree / 旧 cwd)工作 → commit 落错 branch。

**Pattern**:每次 implementer / reviewer dispatch prompt **必含 STRICT cwd verify 段**:

````markdown
## Working Directory(STRICT — verify before any work)

```bash
cd <worktree-path>
pwd  # MUST show <worktree-path>
git branch --show-current  # MUST be <expected-branch>
git rev-parse HEAD  # MUST be <expected-SHA>
git status --short  # SHOULD be clean
```

If `pwd` 不显示 expected path → **STOP report NEEDS_CONTEXT;不要在错误 directory 工作**。
````

**Recovery**(若 leak 发生):见 Pattern 5。

### Pattern 3: Controller Cross-Verify(防 subagent self-hallucination)

**问题**:subagent self-report 可能幻觉(测试 count 错 / 引用不存在 URL / 编自己没做的工作)。

**Pattern**:**永远不接受 subagent self-report 直接进 evidence**。Controller MUST 独立验证以下 5 类 claim:

| Subagent claim | Controller verify 命令 | 注意事项 |
|---|---|---|
| "X fence 全 PASS" | `python -m pytest <test-file> -v` | 用 `python -m pytest` 而非 `pytest`(后者 binary 可能走错 Python interpreter,缺 dep) |
| "全 regress N PASS" | `python -m pytest -q` | 同上 |
| "Commit SHA `X`" | `git show <X> --stat` | 验证存在 + 内容符合预期 |
| "Spec scenario 全覆盖" | `grep -c "<spec-required-string>" <file>` | 静态字符串匹配验证 |
| "改了 X 不改 Y" | `git diff <base>..HEAD --stat` | scope 验证 |
| "Commit 在 branch X" | `git branch --contains <commit-sha>` | 防 branch leak |
| "URL / 文件 path 引用" | 实际访问 / `ls` / `git log <path>` | 防幻觉 URL / 不存在 path |

### Pattern 4: Strict Reviewer Prompts(让 cheap model reviewer 可靠)

**问题**:cheap model(如 Haiku)reviewer 在 open-ended task 下易出问题(scope-bleed / 幻觉 URL / 工具方法错)。

**Pattern**:reviewer prompt 必含 4 元素(顺序固定)— **限制 scope + pre-verified data + specific list + phase boundary 显式**:

```markdown
## Working Directory(STRICT)
[Pattern 2 cwd verify section]

## Pre-verified Data(controller 已跑,你不必再跑)
- pytest tests/unit/test_X.py -v → N PASS
- python -m pytest -q → M PASS + K skipped
- grep "<key string>" <file> → 命中 / 不命中

## Your Job — Verify These Specific Points(NOT open-ended)
1. <Specific check 1>
2. <Specific check 2>
3. <Specific check 3>
4. <Specific check 4>

## Phase Scope Boundary
**Note**:only review P{N} scope。P{N+1} / P{N-1} are different phases — don't flag missing functionality from other phases。If you see something cross-phase,note it as observation not blocker。
```

**实证效果**:同 model(Haiku)在 open-ended prompt 下 scope-bleed + 幻觉,在严格 prompt 下表现可靠。**模型不变,prompt 变**。

### Pattern 5: Cherry-Pick Recovery(worktree-scope leak 救援)

**问题**:subagent 在错误 branch 落 commit(如 dev 而非 worktree branch)。

**Detection**:
```bash
git log <expected-branch> --oneline -3  # MUST 含刚 commit
git log <wrong-branch> --oneline -3  # 不应 含 该 commit
git branch --contains <commit-sha>  # 列哪些 branch 含此 commit
```

**Recovery**:
```bash
# Step 1: cherry-pick 到正确 branch
cd <expected-worktree>
git cherry-pick <leaked-commit-sha>
# 验证 cherry-pick 后 SHA(新 SHA)
git log --oneline -2

# Step 2: 撤销错误 branch 上的 leaked commit(否则 duplicate)
git update-ref refs/heads/<wrong-branch> <prior-base-sha>
git log <wrong-branch> --oneline -3  # 验证回到 prior-base
```

**Evidence 标注**:在该 phase 的 implementer evidence 加 `worktree_scope_leak: true` + `worktree_scope_leak_recovery: <description>` 字段(若项目有 evidence frontmatter 协议)。

**Future preventive**:dispatch prompt §2 STRICT cwd verify 必加(Pattern 2)。

### Pattern 6: Inline Fix vs Round 2 Fix Decision

**问题**:reviewer 出 Important / Minor 时,controller 决策——controller 自己直接 edit 还是 dispatch round 2 SendMessage 给原 implementer?

**Decision Table**:

| Issue 类型 | 决策 | Cost |
|---|---|---|
| Trivial 文本 fix(docstring 加段 / f-string prefix / 注释加行 / 字符串拼写) | **Controller inline edit** | ~free(controller token) |
| Spec-violating 字符串缺(forgot to add `git status --porcelain` to template) | **Controller inline edit** | ~free |
| Missing serialization step / glue code(简单 Bash dict→JSON 序列化) | **Controller inline edit** | ~free |
| Logic 错误(算法选错 / 数据流错 / 控制流缺) | **Round 2 fix dispatch**(SendMessage 同 implementer subagent) | ~$0.20-0.50 |
| Architectural 错误(违 design decision / 引入 new ADR) | **升级 user**(沿 autonomy boundary fence;controller-only) | controller-only,等用户拍板 |

**关键**:Round 2 fix 应**SendMessage 同 implementer subagent**(不 dispatch fresh subagent),沿 superpowers:subagent-driven-development 的 round-2 continuity 协议。

### Pattern 7: When to Skip Subagent Reviewer(节省 cost)

**Skip 可接受** 的场景(implementer + controller verify + commit;**不**派 spec_reviewer + code_quality_reviewer):
- Single-file doc edit + 无 logic(单 markdown 文件 1 段 update)
- Mechanical text 替换 across 多文件(grep/sed-like edit;e.g. doc sync 阶段)
- Documentation typo fix
- README / CHANGELOG entry 添加
- Trivial config 字段加(yaml / toml)

**仍要做的**(controller 自己):
- `python -m pytest -q` verify 0 regression(若改 source code)
- 项目级 contract validation(若改 contract artifact)
- evidence 完整性 check(若加 evidence)

**不能 skip** 的场景(必跑全 3-stage review):
- Source code 修改(implementer 写 .py / .ts / .rs / etc)
- Cross-file refactor
- 引入 new test fence / 改既有 test 行为
- 引入 new design decision implementation
- 跨子系统 integration

### Pattern 8: Cost-Benefit Framework

**Per-phase cost 估算**(参考价;实际依 token 用量):

| 路径 | cost range | 何时合适 |
|---|---|---|
| 全 Opus 3-stage(implementer + spec + code_quality)| $5-10 | architecture / spec drafting phase |
| 矩阵 3-stage(Haiku/Haiku/Sonnet)| $0.50-1.50 | mechanical implementation phases |
| 矩阵 3-stage(Sonnet/Haiku/Sonnet)| $1.00-3.00 | multi-file integration phases |
| Skip reviewer(implementer + controller verify)| $0.10-0.50 | doc / typo / mechanical 多文件 |
| Direct(controller in-session)| $0.05-0.20 | trivial step / 1-2 line change |

**Mid-phase 升级 trigger**(从 cheap → standard model):
- Subagent return BLOCKED / DONE_WITH_CONCERNS 带 substantive 问题
- spec_reviewer 找到 ≥3 真实 issues round 1(implementer over its head)
- code_quality_reviewer 标 Critical
- pytest 跑 fence test 失败 with 实现明显 misread plan

---

## §2 Case Studies(growing layer — 每项目实证增量补充)

每项目用本 skill 跑完一个 change / phase 后,加一个 case study 条目。沿模板:

```
### Case <NN>: <project> / <change-id> / <phase / scope>

**Date**:<YYYY-MM-DD>
**Project context**:<1 句项目类型 + 子系统>
**Subagent dispatch**:
- implementer: <model> ($cost) — <task summary>
- spec_reviewer: <model> ($cost) — <verdict>
- code_quality_reviewer: <model> ($cost) — <verdict>

**Real issues caught / failed**:
| Issue | Severity | Caught by | Pattern referenced |
|---|---|---|---|
| ... | ... | ... | Pattern N |

**Lesson** / Pattern reinforcement / new pattern surfaced:
- ...

**Cost vs all-Opus alternative**:实际 $X vs Opus 估 $Y → 节省 ratio
```

### Case 1: ForgeUE / enhance-workflow-automation-executable-enforcement / P0-P3

**Date**:2026-05-05
**Project context**:ForgeUE workflow tooling change — W1 preflight wrapper + W3 dispatch ledger + finish_gate v2 + 命令模板升级

**Subagent dispatch**(P0 全 Opus 误用 + P1/P2/P3 矩阵):

| Phase | implementer | spec_reviewer | code_quality | $ |
|---|---|---|---|---|
| P0(W1 wrapper 584 LOC + 18 fence) | Opus(误)| Opus(误)| Opus(误) | $5.90 |
| P1(W3 ledger 150 LOC + 12 fence) | Haiku ✅ | Haiku scope-bleed | Sonnet ✅ | $0.52 |
| P2(finish_gate +367 LOC + 16 fence) | Sonnet ✅ | Haiku 幻觉 URL + wrong test count | Sonnet ✅ | $1.30 |
| P3(2 命令模板 + 8 fence) | Haiku worktree leak + 自我幻觉 + 2 bug | Haiku ✅(strict prompt 后) | Sonnet ✅ caught 2 bug | $0.62 |

**Real issues caught / failed**:

| Issue | Severity | Caught by | Pattern referenced |
|---|---|---|---|
| P0 cost 6.7x over budget(全 Opus 默认继承) | High | Cost retrospect 实证 | Pattern 1 — 显式 model 选择 |
| P1 spec_reviewer scope-bleed(P2 fence 当 P1 missing 报错) | Important | Controller verdict override | Pattern 4 — strict reviewer prompt(phase boundary 段) |
| P2 spec_reviewer 幻觉 GitHub URL + 错测试 count | Important | Controller cross-verify pytest | Pattern 3 — cross-verify 5 类 claim |
| P3 implementer cwd leak(commit 落 dev 而非 worktree) | **Critical** | Controller `git log dev` cross-check | Pattern 2 — STRICT cwd verify + Pattern 5 — cherry-pick recovery |
| P3 implementer 自我幻觉("改了测试结构"实际没改) | High | Controller verify 实际 file 内容 | Pattern 3 — cross-verify "改了 X 不改 Y" |
| P3 f-string assert message bug | Important | Sonnet code_quality reviewer | Pattern 1 — Sonnet code_quality 不可省 |
| P3 `IMPL_FILES_JSON` Bash 序列化缺(runtime silent failure) | **Important** | Sonnet code_quality reviewer | Pattern 1 — Sonnet code_quality catches runtime correctness;Pattern 6 — controller inline fix |

**Lesson reinforcement**:
- Pattern 1 验证:Sonnet code_quality 抓的 2 bug(f-string + IMPL_FILES_JSON)Haiku 三人组都漏。**Sonnet 不可省**。
- Pattern 2 验证:dispatch prompt 写 "STOP report NEEDS_CONTEXT if pwd mismatch" 不够,subagent 仍可能跳过。**STRICT cwd verify section + Bash 命令样例必含**。
- Pattern 3 验证:subagent 自我汇报 hallucinate 的频率不低(P2 + P3 都出过)— controller cross-verify 必跑。
- Pattern 4 实证:同 Haiku 在 P1/P2 open-ended prompt 下 scope-bleed + 幻觉,P3 strict prompt 下表现可靠。**model 不变,prompt 变**。
- Pattern 5 实证:cherry-pick 流程在 worktree leak 时 work,~5 min 救援(无数据丢失)。
- Pattern 6 实证:f-string + IMPL_FILES_JSON inline fix(controller-side ~30s + free)远优 round 2 fix dispatch(~$0.30 + 几分钟)。
- Pattern 8 实证:全 Opus $5.90 vs 矩阵 $0.62 same deliverable quality(P0 vs P3 — both 1 phase code change)→ **9.5x cost reduction**。

**Cost vs all-Opus alternative**:P1+P2+P3 实际 $2.44 vs 全 Opus 估 $15-25 → 节省 ~$15-22 same quality deliverable。

**New pattern surfaced**:无(P0-P3 实证全部映射到 Pattern 1-8)。本 skill 8 patterns 在 P0-P3 验证够用。

---

## §3 Pattern Catalog(quick reference index)

| Subagent failure mode | Pattern that prevents | Case studies reproducing |
|---|---|---|
| over-cost(默认继承 Opus) | 1 | Case 1 P0 |
| spec_reviewer scope-bleed | 4 | Case 1 P1 |
| 幻觉 URL / 测试 count | 3 | Case 1 P2 |
| worktree-scope leak(错 branch commit) | 2 + 5 recovery | Case 1 P3 |
| 自我汇报幻觉(claimed work didn't do) | 3 | Case 1 P3 |
| 静态 review 漏 runtime correctness bug | 1(Sonnet code_quality 不可省) | Case 1 P3 |

---

## §4 How to Use This Skill

### 控制器(主 session Claude / Codex / 其他 LLM)启动 subagent dispatch 前:
1. 读 §1 Pattern 1 选 model tier(根据本次 task 复杂度)
2. 写 dispatch prompt 时**必含** Pattern 2 STRICT cwd verify section
3. 若 dispatch reviewer subagent → 用 Pattern 4 strict prompt 模板(限制 scope + pre-verified data + specific list + phase boundary)

### 收 subagent return 后:
1. 跑 §1 Pattern 3 cross-verify(测试 count / commit SHA / spec strings 等)
2. 检查 commit branch(`git log <expected-branch>` + `git branch --contains <SHA>`)— 若 leak,Pattern 5 recovery
3. 若 reviewer 出 issues → §1 Pattern 6 决策(inline / round 2 / 升级)

### Phase 完成 / change 完成后:
1. 加 §2 case study 条目(沿模板)— 把本项目实证沉淀
2. 若发现新 subagent failure mode 不在 §3 catalog → 加 catalog 行 + 若 8 patterns 不覆盖,提议新 pattern

---

## §5 How to Update This Skill(growing 协议)

本 skill 设计为**living document**:patterns 上层(§1)稳定,case studies(§2)+ catalog(§3)增量增长。

### 新 case study 添加(每个新项目 / change / phase 用本 skill 后)

1. Append to §2 用 Case <NN+1> 模板
2. Update frontmatter `case_study_count`(N → N+1)
3. 在 §3 catalog 加新 row(若发现新 failure mode)
4. **不**改 §1 patterns(除非是 major pattern revision)

### 新 pattern 添加(rare;只有当 §1 8 patterns 不覆盖 new failure mode 时)

1. Append to §1 用 Pattern <N+1> 格式
2. Update frontmatter `pattern_count`(8 → 9)
3. 在 §3 catalog 加新 row mapping new pattern → cases
4. 同步 §4 How to Use 段(若新 pattern 改变 workflow 顺序)

### Model tier 调整(当 model lineup 变化时)

例:Anthropic 出 Claude 5 / 不同 pricing → §1 Pattern 1 model tier table 调整。频率 ~1-2 年一次。

### Skill 演进 review

每 ~10 case studies 后(或当某 pattern 实证 ≥5 case 强化)— controller 应做 meta-review:
- 是否某 pattern 该提升优先级(如从 8 patterns 中标 top 3 必检)
- 是否 case studies 暴露 systemic gap(需要更新 superpowers 上游 skill)
- 是否本 skill scope 该扩(e.g. 加新 reviewer role / 加 batch dispatch pattern)

---

## §6 Relation to superpowers:subagent-driven-development

| superpowers:subagent-driven-development(60% generic scaffold) | 本 skill(40% scenario judgment) |
|---|---|
| per-task 3-stage process(implementer + spec_reviewer + code_quality_reviewer + final_reviewer) | Pattern 1 — model selection per stage by task complexity |
| Generic prompt templates(implementer-prompt.md / spec-reviewer-prompt.md / code-quality-reviewer-prompt.md) | Pattern 4 — strict reviewer prompt elements(cwd verify + pre-verified data + specific list + phase boundary)|
| Loose 3-tier model selection(cheap / standard / most-capable) | Pattern 1 — concrete task signals → model tier matrix |
| Status handling(DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT)| Pattern 6 — Controller decision when reviewer出 issues(inline / round 2 / 升级)|
| Red Flags(don't dispatch parallel implementers / subagent 不读 plan 文件) | Pattern 2 — STRICT cwd verify(防 worktree-scope leak;红 flag 之外的实证)|
| Continuous execution discipline | Pattern 3 — controller cross-verify(防 self-report hallucination)|
| (无 cost guidance) | Pattern 8 — cost-benefit framework + mid-phase upgrade trigger |
| (无 recovery flow)| Pattern 5 — cherry-pick recovery for branch leak |
| (无 skip 边界)| Pattern 7 — when to skip subagent reviewer |

**真源**:`superpowers:subagent-driven-development`。本 skill **不复制不重写** 上游 prompt 模板;只补 controller-side judgment。
