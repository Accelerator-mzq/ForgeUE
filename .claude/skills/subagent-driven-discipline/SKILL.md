---
name: subagent-driven-discipline
description: Subagent task type taxonomy + cheap-model reliability playbook + Trigger Type Matrix retrospect for subagent-driven-development workflows。**重场景轻业务**:按 subagent 任务类型(implementation 5 子类 / spec review 4 子类 / code quality review 5 子类 / test creation / doc / debug / verification)细分 model tier + WHY + 让 cheap model 高质量的具体 prompt patterns。**Design 任务(algorithmic / architectural / arch doc rewrite / complex root cause)绝对原则 Opus only,无 exception**。Cross-scenario discipline(cwd verify / cross-verify / cherry-pick recovery / cost framework)作为 supporting infrastructure。**Living catalog 增长由 §3.4 Trigger Type Matrix retrospect 强制**:5 trigger types(3-stage / parallel / standalone / ad-hoc / codex CLI)各自 retrospect intensity;Type 1+2 Opus mandatory full;Type 3 light;Type 4 skip retrospect 仅 cross-verify;任一 Yes 才加 case study;全 No 不加(避免噪声)。Companion to `superpowers:subagent-driven-development`。
license: MIT
compatibility: Claude Code Agent tool + python -m pytest;sister to superpowers:subagent-driven-development(generic 3-stage process)
metadata:
  author: forgeue (initial seed)
  version: "2.2"
  scenario_subtype_count: 28
  case_study_count: 1
  retrospect_protocol: trigger-type-matrix(5 types × per-type intensity)
---

Universal controller-side discipline for `superpowers:subagent-driven-development` workflows。

**核心立场**:**重场景轻业务**。
- **重**(§1 § 2 — 主体):subagent 任务类型 taxonomy(per task subtype:用什么 model + WHY + 怎么让 cheap model 高质量)
- **轻**(§3 § 4 — 支撑):cross-scenario discipline 基础设施(cwd verify / cross-verify / recovery / cost framework)
- **业务无关**:具体项目用法属于 case studies(§5)增量层,不染入 scenario taxonomy

**何时启用**:任何项目使用 `superpowers:subagent-driven-development` 派 subagent 时,controller 主 session dispatch 前 + return 后 + commit 前全流程参考。

---

## §1 Subagent Scenario Taxonomy(重 — task type 决定 model + 协议)

### §1.1 Implementation Tasks(写代码 / 改代码)

| 子类 | 特征 | model | WHY | 让 cheap model 高质量的必备 prompt 元素 |
|---|---|---|---|---|
| **§1.1.1 Mechanical(完整代码样例)** | Plan 含完整 code block + 全 fence test 名 + 完整测试模板 + commit message 模板 | `haiku` | implementer 只需 transcribe + 微调;无 design judgment | 1) Plan 内含 inline 完整代码(不让 implementer 自由 design)<br>2) 每个 fence test 给具体 name + assertion 描述<br>3) Commit message 模板 inline<br>4) Pre-condition / Pre-state(git status clean / pytest baseline N)<br>5) Self-review 7 项检查清单 |
| **§1.1.2 Pattern-matching(用既有模式)** | 改 / 新建文件,需照既有 sister files 风格;Plan 给 file:line 锚点但不全 inline | `haiku` 或 `sonnet`(borderline)| Pattern lookup + 套用是 pattern matching 任务;若需理解 pattern semantic 升 Sonnet | 1) **必给 sister file 路径**(让 implementer Read 参考)<br>2) Pattern 元素 enumerated(e.g. "沿 `tools/forgeue_skill_cascade_check.py` argparse + multi-mode CLI 风格")<br>3) Style constraint(stdlib only / 中文 docstring)<br>4) Anti-pattern 显式列(e.g. "不引入外部 dep") |
| **§1.1.3 Multi-file integration** | 改既有 module + cross-fence wiring + 多文件 coordinate | `sonnet` | 需保持 cross-file consistency;Haiku 易 miss interaction | 1) 列全部涉及 file paths<br>2) 显式 dependency graph(file A change 影响 file B 哪段)<br>3) Defense-in-depth dispatch logic 描述 |
| **§1.1.4 Algorithmic design** | Plan 描述需求但不给具体算法 / data structure | **`opus` MANDATORY**(不允许 Sonnet 替代) | **设计任务的判断错误下游修复成本极高** — 错算法 → 全 implementation 重写 + 全 test 重写 + 可能影响 contract;Opus 的 reasoning depth 对设计决策必要;Sonnet 在 design 任务下选 "first reasonable solution" 可能跳过更优 alternative | 1) 显式列**已考虑的方案 alternatives**(让 Opus evaluate)<br>2) Performance / memory / 可维护性约束<br>3) Trade-off priority<br>4) Cross-impact 范围(影响哪些 module / future 演进) |
| **§1.1.5 Architectural(跨子系统)** | 引入 new ABC / 新子系统 / cross-boundary refactor / new ADR drafting | **`opus` MANDATORY** | 需全局视角 + 长期演进考虑 + adversarial review;**任何 design 任务都不能降级 cheap model** | **首选 controller 自己做(若 controller 是 Opus)— 不外包给 subagent**;若 controller 非 Opus 必须 dispatch Opus subagent;subagent 只 implement 已 finalized design |

### §1.2 Spec / Compliance Review Tasks(检查 implementation 符合 spec)

| 子类 | 特征 | model | WHY | 让 cheap model 高质量的必备 prompt 元素 |
|---|---|---|---|---|
| **§1.2.1 String matching(检查 N specific strings 在 M files)** | "verify file X contains string Y, doesn't contain Z" 类机械字符串校验 | `haiku` | 纯 grep-style 任务;无 reasoning | 1) 给完整 verification list("Check these 4 specific things")<br>2) Pre-verified data(controller 已跑 grep,reviewer 不必重跑)<br>3) **不**让 reviewer 跑 pytest(避免 binary env mismatch)<br>4) 拒绝 open-ended task(永远不要 "is this spec compliant?",要 "verify these 4 strings") |
| **§1.2.2 Structural verification(模板 / file 含某 section)** | "template X has section Y at right position" | `haiku` | 静态 markdown / file 结构校验 | 同 §1.2.1 + 显式 file path + section header 准确字符串 |
| **§1.2.3 Cross-phase reasoning(scenario 跨 phase boundary)** | spec 写端到端 Requirement,但 plan 拆 P1 工具 / P2 fence — reviewer 需理解 phase decomposition | `sonnet`(`haiku` 会 scope-bleed) | 需理解 "本 phase 该做 vs 其他 phase 该做";Haiku 把 spec 全部 missing 当本 phase issue | 同 §1.2.1 + **Phase Scope Boundary 显式段**:"only review P{N} scope;P{N+1}/P{N-1} 的 missing 不算 issue;若看到 cross-phase 问题,note as observation 不 blocker" |
| **§1.2.4 Acceptance criteria(复杂 business rule)** | "feature meets these 5 acceptance scenarios with WHEN/THEN" | `sonnet` | 涉及 business semantic;Haiku 字面理解可能错 | 列全 acceptance scenarios + 给反例(false claims that should fail) |

### §1.3 Code Quality Review Tasks(代码质量 / 设计)

| 子类 | 特征 | model | WHY | 让 cheap model 高质量的必备 prompt 元素 |
|---|---|---|---|---|
| **§1.3.1 Style / Lint nits** | 命名 / 缩进 / 注释格式 / dead code 检测 | `haiku` | 静态 pattern recognition | 给 specific style rules + file:line targets |
| **§1.3.2 Pattern adherence(沿既有模式)** | "code follows existing project pattern X?" | `haiku`(简单)或 `sonnet`(模糊) | 比对模式 | 给 reference pattern file path + 具体 sub-pattern enumeration |
| **§1.3.3 Maintainability(hard-to-test / tight coupling / sync drift risk)** | 设计判断 — code 是否 future-proof | `sonnet`(必须) | **判断是否会 future bug** 是 reasoning task;Haiku 看不见 | 列具体维护 concern(coupling / drift risk / refactor friction)+ 项目 maintenance 历史 context |
| **§1.3.4 Runtime correctness(race conditions / silent failures / edge cases)** | 检查 implementation 是否会 silent fail at runtime | `sonnet`(**MANDATORY**;Haiku 不可替代) | **必须 reasoning code semantics** + envision execution flow;Haiku 只看 static structure | 描述 expected runtime behavior + 列已知 edge case + adversarial thinking 提示("how can this fail under concurrent / malformed / partial-state input?") |
| **§1.3.5 Security review** | 注入 / 敏感信息 / 权限 / 加密 / 边界 | `sonnet` 或 `opus` | 需要 adversarial thinking + 安全 domain 知识 | 显式 threat model + ASVS / OWASP class refs + 项目 security context |

**核心 takeaway**:**Code Quality 阶段 §1.3.4 Runtime correctness 不可 skip + 不可降级 Haiku**。Case 1 实证:Haiku implementer + Haiku spec_reviewer 漏的 2 个 runtime bug(f-string / IMPL_FILES_JSON silent fail)只有 Sonnet code_quality 抓到。

**任何 Design 任务必须 Opus**(§1.1.4 + §1.1.5 + §1.5.4 architecture doc 重写 + §1.6.3 root cause analysis 复杂场景):design 错误的下游 impact 远大于 dispatch cost differential;Opus reasoning depth 对 design 必要。Cheap model 在 design 任务下倾向"选 first reasonable solution"漏 alternative。这是**绝对原则,无 exception**。

### §1.4 Test Creation Tasks(写新 test)

| 子类 | 特征 | model | WHY | 让 cheap model 高质量的必备 prompt 元素 |
|---|---|---|---|---|
| **§1.4.1 Unit test from spec(spec 清晰)** | spec scenario 已明确 → 翻译为 pytest fence | `haiku` | 模板化;Plan 含 fence name + 期望行为 | 给 fence name list + each fence 一句 expected behavior + 测试 framework 模板 |
| **§1.4.2 Integration test(跨 module)** | 需协调多 module 状态 | `sonnet` | 跨 module setup / teardown 复杂 | 列涉及 module + 依赖 setup 顺序 + tmp_path / mock 策略 |
| **§1.4.3 Edge case generation(创造性)** | "find edge cases not in spec" | `sonnet` | 需要创造性 + adversarial | 给已知 edge case + 提示 "what corner cases NOT covered by these?" |
| **§1.4.4 Regression test(为 bug fix 写 test)** | bug 已识别,写 test 防回归 | `haiku` | 翻译已知 bug 为 test | 给 bug repro steps + expected vs actual + fixture 模板 |

### §1.5 Documentation Tasks

| 子类 | 特征 | model | WHY | 让 cheap model 高质量的必备 prompt 元素 |
|---|---|---|---|---|
| **§1.5.1 Doc sync(机械替换)** | "update version X to Y in N files" | `haiku` 或 direct(no subagent;沿 §3 skip) | 纯字符串替换 | 给 grep / sed 指令 + 影响 file list |
| **§1.5.2 Doc rewrite(semantic)** | 重写段落 for new audience | `sonnet` | 需理解原意 + 重表达 | 给 audience profile + 风格示例 |
| **§1.5.3 API doc(match implementation)** | 从 code generate doc | `haiku` | 模板化 | 给 code path + doc 模板 + cross-ref convention |
| **§1.5.4 Architecture doc(explain decisions)** | 解释 design choices + alternatives | `sonnet` 或 `opus` | 需要 design reasoning | 给 D-decision list + 选用 vs alternatives + WHY |

### §1.6 Debug / Investigation Tasks

| 子类 | 特征 | model | WHY | 让 cheap model 高质量的必备 prompt 元素 |
|---|---|---|---|---|
| **§1.6.1 Bisect(机械二分)** | "找出哪个 commit 引入 regression" | `haiku` 或 direct | 机械 git bisect | 给 known good + bad commit + reproduction script |
| **§1.6.2 Reproduce + identify(根因定位)** | "test failing,find root cause" | `sonnet` | 需 reasoning code + execution flow | 给 test name + failure trace + 涉及 module list |
| **§1.6.3 Root cause analysis(complex)** | 多 component interaction;非显式 | `sonnet` 或 `opus` | 需 system-level reasoning | 给 system architecture + observed symptoms + 已尝试的 hypotheses |

### §1.7 Verification / Acceptance Tasks

| 子类 | 特征 | model | WHY | 让 cheap model 高质量的必备 prompt 元素 |
|---|---|---|---|---|
| **§1.7.1 Run tests + report(机械)** | "run pytest, report pass/fail" | direct(controller;no subagent) | 不值得 subagent dispatch | controller 自己 `python -m pytest -q` |
| **§1.7.2 Cross-check evidence vs spec(reasoning)** | "verify evidence matches spec scenarios" | `sonnet` | 跨 evidence + spec 比对推理 | 列 spec scenarios + evidence file paths + match criteria |

---

## §2 Making Cheap Models Reliable(重 — playbook per scenario)

`haiku` 在合适场景 + 严格 prompt 下 production-quality。**模型不变,prompt 变,质量天差地别**。

### §2.1 Implementation Haiku Reliability Playbook

**Pre-condition**(若不满足 → 升级 Sonnet):
- ✅ Plan 含**完整 inline code sample**(implementer transcribe + 微调,不自由 design)
- ✅ 每 fence test 给**具体 name + 1 句 expected behavior**
- ✅ Commit message 模板 inline
- ✅ Pre-state 标准(git status clean / pytest baseline N + 1 skipped)
- ✅ Sister file 风格 reference path 给(implementer Read 参考)
- ✅ Anti-pattern 显式列(don't add 这个 / don't refactor 那个)

**Prompt 必含元素**(沿 §3.1 STRICT cwd + 7 项 self-review):
```markdown
## Working Directory(STRICT)
[Pattern §3.1 cwd verify section]

## Project Context
- Sister file path: <e.g. tools/forgeue_skill_cascade_check.py>(read for style reference)
- Pre-state: pytest baseline N + K skipped
- Anti-pattern list: ...

## Task Description(full plan text — DO NOT read plan files)
[Full code sample inline + fence list + commit template]

## Self-Review Checklist(before reporting DONE)
- [ ] All N fence tests pass
- [ ] python -m pytest -q shows no regression
- [ ] File header follows project style
- [ ] Stdlib only(no external deps)
- [ ] Commit created and visible in git log -1
- [ ] Self-review found issues fixed before reporting
- [ ] Report includes file paths + pytest count + commit SHA
```

**Failure mode if skipped**:implementer 自由 design / hallucinate self-report / 漏 commit / commit 错 branch(see Pattern §3.1 worktree leak)。

### §2.2 Spec / Compliance Reviewer Haiku Reliability Playbook

**Pre-condition**(若不满足 → 升级 Sonnet):
- ✅ Task 是 §1.2.1 string matching 或 §1.2.2 structural verification(纯静态 grep)
- ✅ Spec scenario 不跨 phase boundary(若跨 → §1.2.3 升 Sonnet)
- ✅ Controller 已 pre-run pytest + given results(reviewer 不必跑 pytest 自己)

**Prompt 必含 4 元素(顺序固定)**:
```markdown
## Working Directory(STRICT)
[Pattern §3.1 cwd verify section]

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
**Note**: only review P{N} scope。P{N+1} / P{N-1} are different phases — don't flag missing functionality from other phases。If you see something cross-phase,note as observation not blocker。
```

**Failure mode if skipped**:scope-bleed(报别 phase 的 missing)/ 幻觉 URL / 错 pytest count(走错 binary)/ open-ended task 输出无用 verdict。

### §2.3 Code Quality Reviewer Haiku Acceptable Subset

**Haiku 适合**:§1.3.1 style/lint + §1.3.2 simple pattern adherence + §1.3.3 partial(有 specific concern list 时)

**Haiku 不适合**:§1.3.3 deep maintainability / **§1.3.4 runtime correctness(MANDATORY Sonnet)** / §1.3.5 security

**Haiku-acceptable prompt 必含**:
- 具体 file:line targets(不要 "review the whole change")
- Specific style rules / pattern checklist(不要 "is this good code?")
- Severity 分类约束(Critical / Important / Minor)— 限制 Haiku 不报满 false positive

### §2.4 Test Creation Haiku Reliability Playbook

**Pre-condition**:Plan 含 fence name list + each fence expected behavior + 测试 framework 模板。
**Prompt**:fence list + assertion 描述 + tmp_path / fixture pattern + commit template。
**Failure mode if skipped**:implementer 编 test 名 / 漏 fence / fence 实现与 name 不符。

### §2.5 Doc Sync Haiku Reliability Playbook

**Pre-condition**:全 mechanical text replace(grep / sed-like)。
**Prompt**:具体 grep pattern + 影响 file list + before/after example。
**Failure mode if skipped**:doc drift(implementer 改 file A 不改 file B)。

### §2.6 跨场景共通 — Cheap Model "高质量" 的核心 3 条

无论何种 cheap model 任务,以下 3 条是 floor:

1. **任务必须是 enumerated 而非 open-ended**:不要 "is this OK?" 要 "verify these N specific things"
2. **Pre-condition 必须 controller 设好**:不要让 cheap model 探索 environment / 自己 run pytest;controller 跑后给 results
3. **Output 必须 enumerated**:不要 "share concerns" 要 "report issues with severity Critical/Important/Minor + file:line + fix suggestion"

违任一 → cheap model 易 hallucinate / scope-bleed / 输出 useless verdict(实证见 §5 Case 1)。

---

## §3 Cross-Scenario Discipline(轻 — 支撑基础设施)

### §3.1 STRICT cwd verify(防 worktree-scope leak)

每次 dispatch prompt 必含:
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

### §3.2 Controller Cross-Verify(防 self-hallucination)

收 subagent return 后,controller 独立验证:

| Subagent claim | Controller verify 命令 |
|---|---|
| "X fence 全 PASS" | `python -m pytest <test-file> -v`(不用 `pytest`,用 `python -m pytest` — 防 binary env mismatch)|
| "全 regress N PASS" | `python -m pytest -q` |
| "Commit SHA `X`" | `git show <X> --stat` + `git branch --contains <X>`(防 branch leak) |
| "Spec scenario 全覆盖" | `grep -c "<spec-required-string>" <file>` |
| "改了 X 不改 Y" | `git diff <base>..HEAD --stat` |
| "URL / 文件 path 引用" | 实际访问 / `ls` / `git log <path>` |

### §3.3 Inline Fix vs Round 2 Fix Decision

| Issue 类型 | 决策 |
|---|---|
| Trivial 文本 fix(docstring / f-string / 注释)| Controller inline edit(~free) |
| Spec-violating 字符串缺 / Glue code 缺 | Controller inline edit(~free) |
| Logic 错误(算法 / 数据流 / 控制流)| Round 2 SendMessage 同 implementer subagent(~$0.20-0.50)|
| Architectural 错误(违 design decision) | 升级 user(controller-only) |

### §3.4 Post-Phase Quality Retrospect Protocol(Opus-only judgment;skill 增长触发)

**核心原则**:任何 subagent dispatch 完成都需 controller-side 质量分析 — 但 dispatch 类型不同,retrospect intensity 不同。本节定义 **5 Trigger Type × 不同 retrospect intensity**。

#### §3.4.0 Trigger Type Matrix(总览)

| Trigger Type | 何时 fires | Retrospect Intensity | Actor | Cost |
|---|---|---|---|---|
| **Type 1: 3-stage full**(canonical;§1.1 + §1.2 + §1.3)| per-task implementer + spec_reviewer + code_quality_reviewer 全 ✅/⚠️ + 3 evidence committed | **MANDATORY full Q1-Q6** | **Opus**(MANDATORY)| $0.30-1.00 |
| **Type 2: Parallel dispatch**(`superpowers:dispatching-parallel-agents`)| 多 implementer 并行全 commit + W2 actual diff 验证 + 后续 spec / code_quality reviewer 全 ✅ | **MANDATORY full Q1-Q6 + Q7**(parallel-specific) | **Opus**(MANDATORY)| $0.40-1.20 |
| **Type 3: Standalone Task**(§1.4/§1.5/§1.6/§1.7 单 subagent dispatch,无 3-stage review)| Single Task return DONE / DONE_WITH_CONCERNS | **Light:Q2 + Q3 + Q4**(skip Q1/Q5/Q6 — 单 task scope 不够 trigger broader pattern) | **Opus or Sonnet** | $0.10-0.30 |
| **Type 4: Ad-hoc research Task**(无 evidence committed;e.g. "summarize files" / "find X usage")| Task return | **Skip full retrospect;仅 §3.2 cross-verify** | Controller(any tier) | ~$0(cross-verify only) |
| **Type 5: Codex CLI subprocess**(`/codex:adversarial-review` / `/codex:review`)| Codex CLI return | **本 skill 不 cover**(Codex 自家 protocol — 沿 codex-plugin/codex-companion) | N/A | N/A |

**判定 trigger type**:看 dispatch 用哪 upstream skill / 哪 dispatch pattern,不看 task 内容本身。

#### §3.4.1 Type 1: 3-stage Full Retrospect(canonical)

**3-stage 定义**(沿 `superpowers:subagent-driven-development` upstream;per-task 串行):

| Stage | Subagent 角色 | 任务 | 进入下 stage 条件 |
|---|---|---|---|
| Stage 1 | implementer | 写实现 code / fence test / commit | return status DONE / DONE_WITH_CONCERNS;若 BLOCKED / NEEDS_CONTEXT → controller 处理后 retry |
| Stage 2 | spec_reviewer(spec compliance) | verify implementation 符合 spec(checklist 比对) | reviewer ✅ Spec compliant;若 ❌ Issues → SendMessage round 2 same implementer fix → re-review;直到 ✅ |
| Stage 3 | code_quality_reviewer | verify code quality(clean / tested / maintainable / runtime correctness) | reviewer ✅ Approved 或 ⚠️ Approved with concerns(non-blocker);若 ❌ Issues → round 2 fix → re-review;直到 ✅/⚠️ |

**Phase complete** = Stage 1 + Stage 2 + Stage 3 全 ✅(或 ⚠️ non-blocker)+ 3 类 evidence 文件落盘 + commit。**此时**触发 Type 1 retrospect。

(注:**final_reviewer** 是 **per-change 末尾**额外 stage — 全 phase 完成后跑一次综合 review,不属于 per-phase 3-stage。final_reviewer 完成后做 change-level retrospect,不是 phase-level。)

#### §3.4.2 Type 2: Parallel Dispatch Retrospect

**Trigger**:`superpowers:dispatching-parallel-agents`(或 `/forgeue:change-apply-parallel`)派多 implementer 并行 → 全 commit → W2 actual diff verified disjoint(若 overlap 检测自动降级 sequential → 改走 Type 1 retrospect)→ 后续 spec / code_quality reviewer 全 ✅。

**Inputs(controller 必读)**:
1. 全 N implementer evidence files
2. spec_reviewer + code_quality_reviewer evidence
3. W2 actual diff result(`task_files_actual` declared vs detected)
4. parallel-specific log(若有 abort log:`<change>/parallel_abort_*`)
5. Phase commit diff
6. 本 skill 当前版本

**Question Matrix Q1-Q6 + Type 2 加 Q7**(parallel-specific):

| Q | 问题 | Yes 后果 |
|---|---|---|
| Q1-Q6 | 沿 Type 1 同款 | 同 Type 1 |
| **Q7a** | Actual file overlap detected post-dispatch?(implementer 间 diff 实际有交) | 必加 §5 case 标 controller declaration vs reality drift |
| **Q7b** | Race condition / shared state 影响?(implementer 改 shared fixture / global config / import hub)| 必加 §5 case + §6 catalog "parallel race condition" |
| **Q7c** | IMPL_FILES_JSON 序列化缺 / W2 actual diff Bash glue 错?(silent overlap detection failure)| 必加 §5 case + §1.1.3 multi-file integration playbook 加 prompt 元素 |
| **Q7d** | parallel implementer 数 vs degradation 实际比例?(若 ≥30% 降级 → 该 phase 不该选 parallel)| 必加 §5 case + §1.1.x 加 "适合 parallel vs sequential" 判定准则 |

#### §3.4.3 Type 3: Standalone Task Retrospect(Light)

**Trigger**:任何 §1.4 / §1.5 / §1.6 / §1.7 单 subagent dispatch(非 3-stage 包装)return DONE / DONE_WITH_CONCERNS。

**例**:
- §1.4.1 unit test from spec — implementer 写一组 test
- §1.5.1 doc sync — implementer 跨 N file mechanical 替换
- §1.5.2 doc rewrite — implementer 重写一段 doc
- §1.6.1 bisect / §1.6.2 reproduce — debug subagent
- §1.7.2 cross-check evidence vs spec — verification subagent

**Inputs**:
1. Task return content(no committed evidence file unless writing one)
2. 涉及 file diff(若 implementer 写了 commit)
3. §1.X.Y 对应的 subtype 行(check 是否表现 within expected)

**Question Matrix Light(skip Q1 / Q5 / Q6 — 单 task scope 不够 trigger broader pattern)**:

| Q | 问题 | Yes 后果 |
|---|---|---|
| **Q2** | Subagent hallucinate / scope-bleed / 自我汇报错? | 加 §5 case |
| **Q3** | Controller 需 intervention(re-run / inline fix)? | 加 §5 case |
| **Q4** | NEW failure mode 不在 §6 catalog? | 加 §6 + §5 case |

**Decision**:
- 全 No → SKIP skill update
- 任一 Yes → MUST add §5 case(标记 Trigger Type 3 + scenario §1.X.Y)

#### §3.4.4 Type 4: Ad-hoc Research Task(Skip retrospect)

**Trigger**:Agent tool / Explore subagent / general-purpose research dispatch — **无 committed evidence**(纯 information gathering / one-off lookup)。

**例**:
- "Summarize these N files for me"
- "Find where function X is used"
- "Investigate why test Y fails"(without writing fix)
- Codebase navigation queries

**Inputs**:Task return(text only,no file changes)。

**Retrospect**:**SKIP full retrospect** — 仅跑 §3.2 cross-verify 关键 claim(若 subagent 引用了 file path / commit SHA / function 名 / URL → controller 验证存在)。

**WHY skip**:
- Ad-hoc 无 committed evidence — case study 无 anchor
- One-off 性质 — pattern 难提炼
- Cost too high vs value(retrospect $0.30+ for $0.05 task)

**Exception**:若 ad-hoc Task return 含明显 hallucination / 错信息 → controller spot-add 一个 light §5 case(Trigger Type 4),记录该 task 的失败模式 + 防后续重蹈。

#### §3.4.5 Type 5: Codex CLI Subprocess(out of scope)

**Trigger**:`/codex:adversarial-review` / `/codex:review` / `/codex:rescue` 等 codex-plugin 派的 CLI subprocess。

**为什么不 cover**:
- Codex CLI 不是 Claude Code subagent — 是外部 CLI subprocess(`codex-companion.mjs` broker)
- Codex 走自家 protocol(Round Counter + Polling Convention + verbatim-first output)
- Codex 自家有 review 协议(`codex_review_round1.md` / cross-check matrix)

**Controller 责任**(本 skill 不规约,但提醒):
- Codex return 后仍需 §3.2 cross-verify(测试 count / file path / commit SHA / URL)
- 若 codex hallucinate → 是 codex-plugin / codex-companion bug,不是本 skill 范围

#### §3.4.6 Trigger Type 共通约束(all types)

无论 Trigger Type N:
1. **§3.2 controller cross-verify 永远 mandatory**(Type 1-4 都要;Type 5 也建议)
2. **Opus actor 决定**:Type 1 + Type 2 MANDATORY Opus;Type 3 Opus 或 Sonnet 都可;Type 4 controller 任意 tier;Type 5 N/A
3. **Skill update 触发条件**:任一 trigger type retrospect 出 Yes → 加 §5 case + 视情况 §6 / §1
4. **Anti-pattern**:跳过任何 trigger type 的最低 retrospect(即使是 Type 4 的 cross-verify)→ 失去 controller-side 质量防线

**Actor**:**Opus(MANDATORY)**。
- 若 controller(主 session)是 Opus → controller 直接做
- 若 controller 是 Sonnet/Haiku → controller MUST dispatch Opus subagent for retrospect
- **不允许 Sonnet/Haiku 做 retrospect** — retrospect 是 meta-judgment 任务,需:
  - Adversarial perspective on subagent self-reports(critical thinking)
  - Pattern recognition across 多 evidence files(broad context)
  - Evaluate against §1 28 subtypes(scenario knowledge)
  - 决定是否扩 §1 / §5 / §6(meta-skill update judgment)
  - 这些都是 Opus-tier 任务

**Inputs**(retrospect actor 必读):
1. 全 phase 3 类 subagent evidence files(implementer + spec_reviewer + code_quality_reviewer)
2. Phase commit diff(`git diff <phase-base>..HEAD`)
3. 任何 controller intervention 记录(inline fix / round 2 / cherry-pick recovery)
4. 本 skill 当前版本(对照 §1 / §5 / §6)

**Question Matrix**(retrospect actor 逐项问):

| Q | 问题 | Yes 后果 |
|---|---|---|
| Q1 | 任一 subagent fail in ways outside §1.X.Y expected behavior? | → 加 §5 case + §6 catalog |
| Q2 | 任一 subagent hallucinate / scope-bleed / 自我汇报错? | → 加 §5 case |
| Q3 | Controller 需 intervention(inline fix / round 2 / cherry-pick)? | → 加 §5 case |
| Q4 | NEW failure mode 不在 §6 catalog? | → 加 §6 catalog row + §5 case |
| Q5 | NEW scenario subtype 不在 §1 28 子类? | → 加 §1.X.Y row + §2 playbook + §5 case |
| Q6 | Cheap model 在某 scenario 表现远低于预期(应升 Sonnet)? | → 调 §1 model 列 + §5 case |

**Decision Tree**:
- **All Q1-Q6 答 No**(subagents 表现 within §1 expectation + 无 controller intervention)→ **SKIP skill update**;phase passes silently
- **任一 Yes** → **MUST update skill**:
  - 至少加 §5 Case <NN+1>(retrospect 沿模板;含 retrospect verdict 段)
  - 视具体 Yes 情况追加 §1 / §6(沿 §8 update 协议)
- **不允许"觉得没必要就 skip"** — Opus retrospect 找到任何 issue 都必须沉淀 skill 增长

**Cost**:Opus retrospect ~$0.30-1.00 per phase(读 evidence + diff;judgment-heavy reasoning)。看似贵 — 但**这是 skill 增长的唯一 dependable mechanism**。Skip retrospect = skill 不长 = 后续 change 重蹈覆辙。

**Why mandatory**:
- 若每 phase 不 retrospect → skill 只在 controller 主动 "想到要更新" 时长 → unreliable feedback loop
- Mandatory retrospect = skill 自动从实证增长(只在真有 issue 时更新,无问题不污染)
- Opus-only = retrospect verdict 可信(cheap model retrospect 自己就是 unreliable)

---

## §4 Failure Recovery

### §4.1 Cherry-Pick Recovery(worktree-scope leak)

```bash
# Detection
git log <expected-branch> --oneline -3  # MUST 含刚 commit
git branch --contains <commit-sha>  # 列哪些 branch 含

# Recovery
cd <expected-worktree>
git cherry-pick <leaked-commit-sha>
git update-ref refs/heads/<wrong-branch> <prior-base-sha>
```

### §4.2 Mid-Phase Model Upgrade Trigger

从 cheap → standard model **mid-phase** 触发:
- Subagent return BLOCKED / DONE_WITH_CONCERNS 带 substantive 问题
- spec_reviewer 找到 ≥3 真实 issues round 1
- code_quality_reviewer 标 Critical
- pytest 跑 fence test 失败 with 实现明显 misread plan

---

## §5 Case Studies(growing layer — 项目实证)

### Case <NN> 模板

```
### Case <NN>: <project> / <change> / <phase>

**Date**:<YYYY-MM-DD>
**Project context**:<1 句>
**Subagent dispatch**:
| Subagent | Scenario subtype(§1.X.Y)| Model | $cost | Verdict |
|---|---|---|---|---|

**Real issues caught / failed**:
| Issue | Severity | Caught by | Scenario subtype 验证 |
|---|---|---|---|

**Lesson**(reinforce / new pattern / scenario 边界 refinement):

**Cost vs all-Opus alternative**:实际 $X vs Opus 估 $Y → 节省 ratio
```

### Case 1: ForgeUE / enhance-workflow-automation-executable-enforcement / P0-P3

**Date**:2026-05-05
**Project context**:Workflow tooling change — 4 phases × 不同 task subtype

**Subagent dispatch**:

| Phase | Subagent | Scenario subtype | Model | $ | Verdict |
|---|---|---|---|---|---|
| P0 | implementer | §1.1.3 multi-file integration(584 LOC wrapper) | Opus(误)| ~$2.50 | ✅ |
| P0 | spec_reviewer | §1.2.1 string matching | Opus(误)| ~$2.10 | ✅ |
| P0 | code_quality | §1.3.4 runtime correctness | Opus(误)| ~$1.30 | ✅ |
| P1 | implementer | §1.1.1 mechanical(plan 含完整 code) | Haiku | $0.14 | ✅ |
| P1 | spec_reviewer | §1.2.3 cross-phase reasoning(误用 Haiku)| Haiku | $0.13 | ❌ scope-bleed → controller override |
| P1 | code_quality | §1.3.4 runtime correctness | Sonnet | $0.25 | ✅ |
| P2 | implementer | §1.1.3 multi-file integration | Sonnet | $0.83 | ✅ |
| P2 | spec_reviewer | §1.2.1 string matching | Haiku | $0.15 | ❌ 幻觉 URL + 错 pytest count → controller cross-verify override |
| P2 | code_quality | §1.3.3 maintainability + §1.3.4 runtime | Sonnet | $0.32 | ✅ caught sync drift risk |
| P3 | implementer | §1.1.2 pattern-matching(markdown lint) | Haiku | $0.22 | ❌ worktree leak + 自我幻觉 → cherry-pick + cross-verify recovery |
| P3 | spec_reviewer | §1.2.1 string matching(strict prompt) | Haiku | $0.13 | ✅ |
| P3 | code_quality | §1.3.4 runtime correctness | Sonnet | $0.27 | ✅ caught 2 bug(f-string + IMPL_FILES_JSON silent fail) |

**Real issues caught / failed**:

| Issue | Severity | Caught by | Scenario subtype 验证 |
|---|---|---|---|
| P0 cost 6.7x over budget | High | Cost retrospect | §1.1.3 应是 Sonnet 而非 Opus(over-tier) |
| P1 spec_reviewer scope-bleed | Important | Controller override | §1.2.3 cross-phase 必须 Sonnet,§1.2.1 strict prompt 不够时 Haiku 失败 |
| P2 spec_reviewer 幻觉 URL + 错 count | Important | Controller cross-verify(§3.2)| §1.2.1 即使 string matching 也需 §2.6 三条(enumerated / pre-condition / enumerated output) |
| P3 implementer cwd leak | **Critical** | Controller `git log dev`(§3.2)| §3.1 STRICT cwd verify 即使写在 prompt 也可能被 subagent 跳过 — 无 prevention,只有 detection + §4.1 recovery |
| P3 implementer 自我幻觉 | High | Controller verify 实际 file 内容(§3.2)| §2.6 三条之外 + §3.2 cross-verify 必跑 |
| P3 f-string assert message bug | Important | Sonnet code_quality(§1.3.4)| §1.3.4 runtime correctness 不可降级 Haiku |
| P3 IMPL_FILES_JSON silent fail | **Important** | Sonnet code_quality(§1.3.4)| 同上;Haiku reviewer 看不出 silent failure |

**Lesson**:
- **§1.3.4 runtime correctness 不可省 + 不可降级**:P3 实证 — Sonnet 抓 2 个 silent fail bug,Haiku implementer + Haiku spec_reviewer 都漏。
- **§1.2.3 cross-phase reasoning 必 Sonnet**:P1 教训 — 不能用 Haiku 做跨 phase 判断。
- **§2.6 三条 + §3.2 cross-verify 是 cheap model 高质量的 floor**:P2 教训 — 即使 §1.2.1 string matching 任务,无 §2.6 enumerated 元素 + 无 §3.2 controller 兜底,Haiku 仍幻觉。
- **§3.1 STRICT cwd verify 是 detection 不是 prevention**:P3 教训 — prompt 写 STOP NEEDS_CONTEXT 不够,subagent 仍可能跳过;controller 必须 §3.2 cross-verify branch + §4.1 cherry-pick 兜底。
- **Cost framework 验证**:P0 全 Opus $5.90 vs P3 矩阵 $0.62(same task type complexity)→ **9.5x cost reduction**。

**Cost vs all-Opus**:P1+P2+P3 实际 $2.44 vs 全 Opus 估 $15-25 → 节省 ~$15-22 same quality。

**New scenario subtype surfaced**:无 — 28 子类(§1)在 P0-P3 实证全覆盖。

**§3.4 Retrospect verdict per phase**(retroactively applied;若当时跑 retrospect 会触发 skill update 哪些):

| Phase | Q1 outside §1.X.Y? | Q2 hallucinate? | Q3 controller intervention? | Q4 new failure mode? | Q5 new subtype? | Q6 model misconfig? | Decision |
|---|---|---|---|---|---|---|---|
| P0 | No | No | No | No | No | **Yes**(全 Opus 应 Sonnet)| **Add case** — Q6 触发 |
| P1 | No | No(implementer 干净)| **Yes**(spec_reviewer override)| No | No | **Yes**(spec_reviewer §1.2.3 误用 Haiku)| **Add case** — Q3 + Q6 |
| P2 | No | **Yes**(spec_reviewer 幻觉 URL)| **Yes**(controller cross-verify override)| No | No | **Yes**(spec_reviewer §1.2.1 缺 §2.6 floor 元素)| **Add case** — Q2 + Q3 + Q6 |
| P3 | No | **Yes**(implementer 自我汇报错)| **Yes**(cherry-pick + 2 inline fix)| **Yes**(worktree leak first time observed in this skill's history)| No | **Yes**(implementer §1.1.2 cwd discipline 不够)| **Add case** — Q2 + Q3 + Q4 + Q6 |

**结论**:**4/4 phase 全 trigger skill update**(P0-P3 都有 issue) — 这就是 Case 1 存在的原因。若任一 phase 全干净,该 phase 不需要单独 case 段(只在 lessons 段一笔带过)。

**反例**(若 retrospect 全 No 会怎样):
- 假设 P3 spec_reviewer 表现完全 within §1.2.1 expectation + 无 hallucination + 无 controller intervention → §3.4 Q1-Q6 全 No → **不加这一行 case study**;只在 lesson 段写 "P3 spec_reviewer 验证 §2.2 strict prompt 有效,无新观察"。这避免 skill 被无 issue 的 phase 噪声充斥。

---

## §6 Pattern Catalog(failure mode → scenario subtype + recovery)

| Subagent failure mode | Root cause(scenario subtype 误配)| Prevention | Recovery |
|---|---|---|---|
| over-cost(默认继承 Opus) | §1 model 选择缺 / 全 Opus 默认 | §1 显式 model + dispatch 时传 `model:` 参数 | 无(commit 已发生 cost) |
| spec_reviewer scope-bleed | §1.2.3 cross-phase 任务用 Haiku | §1.2.3 升 Sonnet OR §2.2 phase boundary 段 | controller override verdict |
| 幻觉 URL / pytest count | §1.2.x reviewer 任务无 §2.6 三条 | §2.2 pre-verified data + enumerated list | §3.2 cross-verify 命令 |
| worktree-scope leak | §3.1 STRICT cwd 写 prompt 但被跳过 | §3.1 + §3.2 branch verify | §4.1 cherry-pick recovery |
| 自我汇报幻觉 | subagent 输出 trust 过度 | §3.2 cross-verify 必跑 | §3.2 5 类 verify 命令 |
| 静态 review 漏 runtime correctness | §1.3.4 误用 Haiku 替代 Sonnet | §1.3.4 MANDATORY Sonnet | controller catches downstream / Sonnet code_quality 必跑 |

---

## §7 How to Use This Skill

### Controller dispatch 前(每次):
1. **判定 task subtype**:read §1 找 §1.X.Y 行
2. **选 model**:用 §1 表的 model 列(若 cheap-model row,read §2 playbook 验证 pre-condition 满足)
3. **写 dispatch prompt**:用 §2 X playbook 的 prompt 模板 + §3.1 STRICT cwd
4. **显式传 `model:` 参数**(否则 inherit 父 session model — Pattern catalog 第 1 行 failure mode)

### Controller 收 return 后:
1. **跑 §3.2 cross-verify**(测试 count / commit SHA / branch / spec strings)
2. **若 reviewer 出 issues** → §3.3 inline fix vs round 2 决策
3. **若 worktree leak detected** → §4.1 cherry-pick recovery

### Subagent dispatch 完成后(MANDATORY by Trigger Type):
1. **判定 Trigger Type**(§3.4.0 matrix:1 = 3-stage / 2 = parallel / 3 = standalone Task / 4 = ad-hoc research / 5 = codex CLI)
2. **跑对应 retrospect**:
   - Type 1 / 2 → MANDATORY full Q1-Q6(Type 2 加 Q7);Opus actor
   - Type 3 → Light Q2 + Q3 + Q4;Opus 或 Sonnet
   - Type 4 → Skip retrospect;仅 §3.2 cross-verify
   - Type 5 → 不在本 skill scope;沿 codex 自家 protocol + §3.2 cross-verify
3. **若 retrospect 全 No** → SKIP skill update,silent pass
4. **若 retrospect 任一 Yes** → §3.4 Decision Tree 触发 skill update:
   - 加 §5 Case <NN+1>(MANDATORY;标 Trigger Type + scenario §1.X.Y)
   - 视情况追加 §6 catalog row(若 new failure mode)
   - 视情况追加 §1.X.Y row + §2 playbook(若 new scenario subtype)
   - Update frontmatter `case_study_count` / `scenario_subtype_count`

---

## §8 How to Update This Skill(growing 协议)

本 skill 设计为**living document**:§1 scenario taxonomy + §2 playbook 是 stable 上层;§5 case studies + §6 catalog 是 growing 下层。**增长触发由 §3.4 Post-Phase Quality Retrospect 强制**(Opus retrospect 找到 issue 才加;无 issue 不加,避免噪声)。

### 新 case study 添加(MANDATORY 当 §3.4 retrospect 任一 Yes)
1. Append §5 用 Case <NN+1> 模板
2. Update frontmatter `case_study_count`(N → N+1)
3. 若新 failure mode → §6 catalog 加 row

### Case study 不加(SKIP — §3.4 retrospect 全 No)
1. **不**加 §5 — phase 表现 within §1 expectation,加 case 是噪声
2. **不**改 frontmatter
3. Phase silent pass — skill 不变

**Anti-pattern**:看到 phase 完成就反射式加 case study(无论质量)→ 信号噪声 ratio 降低;case studies 失去 "real failure 沉淀" 价值

### 新 scenario subtype 添加(rare;只在 §1 28 子类不覆盖 new task type 时)
1. 决定加在 §1.X 哪类下(implementation / spec review / code quality / test / doc / debug / verification / 新类)
2. 加 §1.X.Y row(特征 + model + WHY + 必备 prompt 元素)
3. 加 §2.X playbook 段(若 cheap-model 适用)
4. Update frontmatter `scenario_subtype_count`(28 → 29)

### Model tier 调整(model lineup 变化时,~1-2 年一次)
- §1 表 model 列调整(e.g. Anthropic 出 Claude 5 / 不同 pricing)

### Skill meta-review(每 ~10 case studies 或某 scenario 实证 ≥5 case 强化)
- 是否某 scenario subtype 提升优先级 / 加边界
- 是否 case studies 暴露 systemic gap(超出 controller-side 范围;需更新 superpowers 上游 skill)
- 是否 §1 taxonomy 该重新分组

---

## §9 Relation to superpowers:subagent-driven-development

本 skill 与 `superpowers:subagent-driven-development` 是 **sister skills**:

| superpowers:subagent-driven-development | 本 skill |
|---|---|
| **Generic process scaffold**(per-task 3-stage:implementer + spec_reviewer + code_quality_reviewer + final_reviewer)| **Scenario-specific judgment**(§1 taxonomy:每 task subtype → model + WHY + cheap-model playbook) |
| Generic prompt templates(implementer-prompt.md / spec-reviewer-prompt.md / code-quality-reviewer-prompt.md)| §2 strict prompt elements(per scenario:必含元素 + pre-condition + failure mode if skipped) |
| Loose 3-tier model selection(cheap / standard / most-capable + "files touched" signal)| §1 28-subtype × model tier matrix(细分 task subtype → 具体 model + WHY) |
| Status handling(DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT)| §3.3 controller decision(inline / round 2 / 升级 user)|
| Red Flags(don't dispatch parallel implementers / subagent 不读 plan 文件) | §3.1 STRICT cwd verify(防 worktree leak — 红 flag 之外的实证)+ §3.2 cross-verify |
| Continuous execution discipline | §3.2 cross-verify 5 类 claim(防 self-hallucination)|
| (无 cost guidance)| §1 model 列每 row 含 cost tier;§4.2 mid-phase upgrade trigger |
| (无 recovery flow)| §4.1 cherry-pick recovery |
| (无 skip 边界)| §1.5.1 + §1.7.1 显式列 direct/no-subagent 场景 |

**真源**:`superpowers:subagent-driven-development`。本 skill **不复制不重写** 上游 prompt 模板;只补 controller-side scenario judgment。
