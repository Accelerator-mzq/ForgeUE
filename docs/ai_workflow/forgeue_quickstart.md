# ForgeUE Integrated AI Change Workflow — 上手指南

> 5 分钟读懂本工作流;按 **dev stage** 组织,每个 stage 给出"命令 + 做什么 + 产出什么 + 关键检查"。
> 本文是教程层;深度契约与协议见 [`forgeue_integrated_ai_workflow.md`](forgeue_integrated_ai_workflow.md)(4 section / 600+ 行)。

## 1. 第一步:决定要不要走 change

**走 change**(`/opsx:propose`)— 走完整 S0→S9:

- 新对象 / 新 workflow / 新 provider / 新 step type
- 架构边界变化 / 跨子系统重构
- 引入新规范行为(spec delta)
- 多人协作 / 需要 review 留痕的变更

**直接改代码**(不走 change):

- 小 bugfix / typo / logic 微调
- 必须补回归测试或说明验证方式(沿"每条 review 修复 = 一条新回归测试"纪律)
- 文档修订 / 配置增补 / 维护性 cleanup

判断标准:**改动是否引入新承诺?**引入 = 走 change;只是兑现已有承诺 = 直接改。

---

## 2. 9 个 stage 全景图

```
S0 (无 change)
  │ /opsx:propose <id> "<one-liner>"            ← 起 change
  ▼
S1 (scaffold)        proposal/design/tasks/specs 起草 + strict validate
  │ /forgeue:change-plan <id>                    ← S2→S3 关键 stage
  ▼
S2-S3 (plan ready)   codex design hook + cross-check + writing-plans 产 plan
  │ /forgeue:change-apply-subagent <id>          ← default;subagent-driven-development + 4 类 evidence
  │ /forgeue:change-apply-direct <id>            ← fallback;executing-plans + TDD(轻量 change / budget 紧张)
  │ /forgeue:change-debug <id>                   ← bug 时
  ▼
S4 (impl in progress)  TDD + subagent-driven-development / executing-plans + 越界检测
  │ /forgeue:change-verify <id>                  ← Level 0/1/2
  ▼
S5 (verify ready)    verify_report 落盘
  │ /forgeue:change-review <id>                  ← self-review + codex adversarial
  ▼
S6 (review ready)    blocker 全清 + 回写
  │ /forgeue:change-doc-sync <id>                ← 10 文档同步
  ▼
S7 (sync gate passed)  doc_sync_report 落盘
  │ /forgeue:change-finish <id>                  ← 中心化最后防线
  ▼
S8 (finish gate passed)  finish_gate_report 落盘
  │ openspec archive <id> -y                     ← 自动 sync-specs 合 delta
  ▼
S9 (archived)
```

**横切**:任何时候用 `/forgeue:change-status` 查 active changes 当前 state(只读)。

---

## 3. 各 stage 操作手册

### 3.1 S0→S1 起 change

**命令**:
```bash
/opsx:propose fix-payload-aid-stable-key "stabilize Artifact aid pairing in run-comparison"
# 等价于:/opsx:new + 一次性起 proposal/design/tasks
```

**做什么**:scaffold change 目录 `openspec/changes/<id>/` + 起草三件套 + 至少 1 个 spec delta

**产出**:`proposal.md` / `design.md` / `tasks.md` / `specs/<capability>/spec.md`

**关键检查**:
- ✓ `openspec validate <id> --strict` PASS(strict 强制 ≥ 1 delta)
- ✓ design.md 含 `## Reasoning Notes` 段(为后续 disputed-permanent-drift 留 anchor 槽)

**深读**:`forgeue_integrated_ai_workflow.md` §B.1 状态机表 S0/S1

---

### 3.2 S2→S3 Plan stage(关键 — codex hook + cross-check)

**命令**:
```bash
/forgeue:change-plan <id>
```

**做什么**(4 步串联):
1. **codex** `/codex:adversarial-review` design hook → `review/codex_design_review.md`(verbatim 完整保留)
2. **Superpowers** `writing-plans` → `execution/execution_plan.md` + `execution/micro_tasks.md`(引用 `tasks.md#X.Y` 锚点)
3. **Claude** 写 cross-check matrix → `review/design_cross_check.md`(`## A` 冻结于 codex 调用前;A/B/C/D 4 段齐 + `disputed_open: 0`)
4. **`forgeue_change_state.py --writeback-check`** → 4 类 named DRIFT 检测(锚点 / 决策越界 / 接口字段 / 异常段)

**关键检查**:
- ✓ codex 每条 finding **独立验证** `file:line`(沿 ForgeUE memory `feedback_verify_external_reviews`)
- ✓ `## A` 段冻结于 codex 调用前(防 anchoring bias;不允许回填)
- ✓ blocker 涉及 design choice → 回写 `design.md` 或标 `disputed-permanent-drift`(≥ 50 字 reason + Reasoning Notes anchor)
- ✓ `disputed_open == 0` 才能进 S3

**常见错误**:
- ✗ 看完 codex 才写 `## A`(anchoring bias)
- ✗ plan 引用 `tasks.md#99.1` 但 tasks 没 §99.1(`evidence_references_missing_anchor` DRIFT 阻断)
- ✗ plan / cross-check 内偷偷加新决策不回写 design.md(`evidence_introduces_decision_not_in_contract` DRIFT 阻断)

**深读**:`forgeue_integrated_ai_workflow.md` §B.4 codex stage hook + §D.3 4 类 DRIFT

---

### 3.3 S3→S4-S5 实施(自 `adopt-subagent-driven-development` change 起,拆为 default subagent + fallback direct)

**命令**(根据 change 复杂度显式选一,**不**走 env flag facade):

```bash
# default 路径:多 micro-task / 需要强 review checkpoint
/forgeue:change-apply-subagent <id>

# fallback 路径:小 change(< 3 micro-task)/ budget 紧张
/forgeue:change-apply-direct <id>

# bug 时显式调 systematic-debugging
/forgeue:change-debug <id>
```

**做什么(`change-apply-subagent` default 路径)**:
- codex plan review hook → `review/codex_plan_review.md`
- 主 session Claude 起 isolated worktree(REQUIRED `using-git-worktrees`;commit untracked artifacts → 起 worktree → cwd 切换;沿 design.md D-Worktree-Detail)
- invoke Superpowers `subagent-driven-development` skill;每 task 派:
  - implementer subagent(Task tool;prompt 含 task FULL TEXT + context;subagent **不**读 plan 文件)
  - spec compliance reviewer subagent(独立验证 implementer 是否按 spec 做 + 不过度建造)
  - code quality reviewer subagent(代码干净度 / 测试度 / 可维护度)
- 全 task 完成后派 final reviewer subagent(整体 review 跨 task 一致性)
- evidence 落盘:
  - `execution/task_<n>_implementer.md`(`evidence_type: subagent_implementer_report`)
  - `execution/task_<n>_spec_review.md`(`evidence_type: subagent_spec_review`)
  - `execution/task_<n>_code_quality_review.md`(`evidence_type: subagent_code_quality_review`)
  - `review/subagent_final_review.md`(`evidence_type: subagent_final_review`)
- evidence frontmatter 必含 audit 字段 `triggered_by_command: change-apply-subagent`(沿 D-EvidenceSchema;`forgeue_finish_gate.py` 从此字段判定 dispatch mode)
- token usage 写 evidence body `## Token usage` 段(`data_source: task_tool_return` / `manual_estimate`),由 `tools/forgeue_subagent_budget.py --record` 追踪
- 越界检测 + writeback-check + 全 task done + Level 0 全绿 + finish_gate exit 0 后 squash merge / cherry-pick 回主分支 + `git worktree remove`

**做什么(`change-apply-direct` fallback 路径)**:
- 沿原 `executing-plans + TDD` 编排
- Superpowers `executing-plans` 取 `execution/micro_tasks.md` 按部就班跑
- Superpowers `test-driven-development` → `execution/tdd_log.md`(增量)
- Superpowers `systematic-debugging`(bug 时)→ `execution/debug_log.md`
- 越界检测:git diff 模块 vs design.md 接口字段
- 不需要 worktree isolation;不派 subagent;不落 4 类 subagent evidence

**关键检查**:
- ✓ 每条 codex review / adversarial finding 修复 = **1 个新回归测试**(项目铁律)
- ✓ 实施暴露 contract 漏洞 = 必须**回写**(design / tasks / proposal),evidence 不能成新规范源
- ✓ 不调付费 provider 默认(env guard `{1,true,yes,on}`)
- ✓ subagent path 每个 task 必有 spec_review + code_quality_review evidence;通过的 task 允许"frontmatter + 一行 summary"轻量化,未通过的 task MUST 完整 issues 列表
- ✓ Token / cost 字段**不进** 12-key frontmatter,在 evidence body `## Token usage` 段记录
- ✓ ADR-008 budget tracker 仅 informational + soft WARNING(`exit 0` 始终,**不**做 hard gate;用户保留判断权)

**常见错误**:
- ✗ 边写代码边改 design.md decisions(应当先回写 contract,确认 + commit 后再实施)
- ✗ 修 codex finding 不补 fence test(下次回归没人守)
- ✗ subagent path 跳过 step 6.5 commit untracked artifacts(`git worktree add` 不带 untracked 文件,subagent 看不到 contract;sequence 必须 commit → worktree → dispatch)
- ✗ `change-apply-subagent` 命令文件复制 / 引用 Superpowers 内部 prompt 模板(沿 D-SkillInvoke;ForgeUE 仅做 evidence wrapper,不重写 skill 协议)
- ✗ 使用 `FORGEUE_APPLY_MODE` env flag 切换路径(沿 D-Default 拒绝 env flag facade;两条命令独立显式声明)

**深读**:`forgeue_integrated_ai_workflow.md` §B.3 Superpowers 集成边界 + §B.6 subagent-driven-development 集成边界

---

### 3.4 S5 Verification

**命令**:
```bash
/forgeue:change-verify <id>                                       # Level 0 默认
/forgeue:change-verify <id> --level 1                              # 要 LLM live
FORGEUE_VERIFY_LIVE_PROVIDER=1 /forgeue:change-verify --level 2    # 要 paid provider
```

**做什么**:Level 0 必跑(`pytest -q` + offline-bundle-smoke);Level 1/2 默认 SKIP,env guard truthy 才跑

**产出**:`verification/verify_report.md`(frontmatter `aligned_with_contract: true` + body summary `[OK]: N / [FAIL]: 0 / [SKIP]: M`)

**关键检查**:
- ✓ Level 1/2 SKIP 必有 reason 写入 verify_report
- ✓ body 不允出现真实 `[FAIL]` per-step marker(`[FAIL]: 0` 计数 summary 行例外)

**深读**:`docs/ai_workflow/validation_matrix.md`

---

### 3.5 S6 Review

**命令**:
```bash
/forgeue:change-review <id>
```

**做什么**:
1. **Superpowers** `requesting-code-review` + `code-reviewer` subagent finalize → `review/superpowers_review.md`
2. **codex** `/codex:adversarial-review` mixed scope(post-implementation)→ `review/codex_adversarial_review.md`

**关键检查**:
- ✓ 每条 blocker **独立验证** TRUE 后才接受(verdict per item;沿 memory `feedback_verify_external_reviews`)
- ✓ 用户裁决"全改"后,沿**双 commit 模式**(见 §5)落地

**常见错误**:
- ✗ 把 codex 的 claim 当结论不验证 file:line(项目用户明确要求)
- ✗ self-review 与 codex review 重合 finding 不分别记录(失去对照价值)

**深读**:`forgeue_integrated_ai_workflow.md` §B.4 codex stage hook S6 mixed scope

---

### 3.6 S7 Documentation Sync Gate

**命令**:
```bash
/forgeue:change-doc-sync <id>
```

**做什么**(3 步):
1. `forgeue_doc_sync_check.py --change <id> --json` 静态扫 10 文档,标 `[REQUIRED] / [OPTIONAL] / [SKIP] / [DRIFT]`
2. 调 `docs/ai_workflow/README.md` §4.3 提示词,以工具输出为 context,agent 输出 A/B/C/D 类
3. 用户确认 `[REQUIRED]` 项后**应用 patch**(不只标记)

**10 份必检文档**:`openspec/specs/*` / SRS / HLD / LLD / test_spec / acceptance_report / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`

**产出**:`verification/doc_sync_report.md`(unresolved DRIFT = 0)

**深读**:`docs/ai_workflow/README.md` §4 主规则 + `forgeue_integrated_ai_workflow.md` §C

---

### 3.7 S8 Finish Gate(中心化最后防线)

**命令**:
```bash
/forgeue:change-finish <id>
# 等价: python tools/forgeue_finish_gate.py --change <id> --json
```

**11 项检查**(任一不过 → exit 2 阻断 archive):
1. evidence 完整性(claude-code+plugin env 要 6 项 codex/cross-check evidence;其他 env 仅 3 项通用)
2. 12-key frontmatter 全检(8 always-required + 4 conditional)
3. helper(`notes/`)vs formal(`{execution,review,verification}/`)区分(`notes/` 不能冒充满足 REQUIRED)
4. cross-check `disputed_open == 0`
5. cross-check `## A. / ## B. / ## C. / ## D.` 4 段齐
6. `verify_report` self-consistency
7. `writeback_commit` 真实性(`git rev-parse` + `git show --stat` 触对应 artifact)
8. `disputed-permanent-drift` ≥ 50 字 reason + anchor 解析到 ≥ 20 词 / ≥ 60 非空白字符段落
9. tasks unchecked == 0(stage-aware:§≥9 self-stage 豁免;`(SKIP / SKIP:` inline 豁免)
10. `openspec validate <id> --strict` PASS
11. `~/.claude/settings.json` 不含 `--enable-review-gate`(WARN 不 FAIL)

**产出**:`verification/finish_gate_report.md`(0 blockers + 0 warnings)+ exit 0

---

### 3.8 S8→S9 Archive

**命令**:
```bash
openspec archive <id> -y
```

**做什么**(自动两步):
1. `mv openspec/changes/<id>/ → openspec/changes/archive/YYYY-MM-DD-<id>/`(整目录搬迁,4 evidence 子目录全保留)
2. sync-specs 把 `specs/<capability>/spec.md` ADDED Requirement 合并到 `openspec/specs/<capability>/spec.md` 主 spec

**收口**:
- 在归档后的 `tasks.md` 标 §10.x + §11.1 `[x]`
- 单 commit:`chore: archive <id> + sync <capability> ADDED requirement`

---

## 4. 工作流内禁令(整条流程必守)

| 禁忌 | 原因 |
|---|---|
| ❌ `/codex:rescue` 在工作流内 | 违反 review-only 原则;markdown lint fence 守门;Pre-P0 一次性豁免不适用未来 change |
| ❌ `--enable-review-gate` | plugin 自警告 long loop;finish_gate WARN |
| ❌ evidence 内引入新规范决策 | 必须回写 contract(design / tasks / proposal / spec) |
| ❌ 修改 OpenSpec 默认产物 | `.claude/commands/opsx/*` / `.claude/skills/openspec-*` / `.codex/commands/opsx/*` / `.codex/skills/openspec-*` |
| ❌ paid provider / UE / ComfyUI live 默认调用 | env guard 严格,opt-in 才跑 |
| ❌ 硬编码 pytest 总数 | 以实测 `python -m pytest -q` 输出为准 |

---

## 5. 双 commit 模式(每个 review 修复 close-out 必看)

每条 review finding 修复(P3 / P4 / P7 / P8 实战模式):

```bash
# Commit 1 — resolution-commit
git commit -m "chore: P<N> review + <M> finding resolution landed"
#   - 修代码 / 文档 / fixture
#   - 加新回归测试
#   - evidence frontmatter 落 drift_decision: pending

# Commit 2 — evidence-backfill commit
git commit -m "docs: backfill writeback_commit in P<N> review evidence"
#   - amend evidence frontmatter:
#       aligned_with_contract: true
#       drift_decision: written-back-to-<artifact>
#       writeback_commit: <Commit 1 sha>
```

**例外**:`disputed-permanent-drift` 不需要 `writeback_commit`(协议本身),单 commit 即可。

---

## 6. 速查卡

| 我现在要... | 命令 |
|---|---|
| 起新 change | `/opsx:propose <id> "<desc>"` |
| 看哪个 change 卡哪个 stage | `/forgeue:change-status` |
| 写完 design 想跑 codex review | `/forgeue:change-plan <id>` |
| 实施(default subagent path) | `/forgeue:change-apply-subagent <id>`(多 micro-task / 需要 review checkpoint) |
| 实施(fallback direct path) | `/forgeue:change-apply-direct <id>`(轻量 change / budget 紧张) |
| 测试挂了找不出原因 | `/forgeue:change-debug <id>` |
| 跑测试 + 产 verify_report | `/forgeue:change-verify <id>` |
| 全套 review(self + codex) | `/forgeue:change-review <id>` |
| 跑 10 文档同步 gate | `/forgeue:change-doc-sync <id>` |
| 跑最后 finish gate | `/forgeue:change-finish <id>` |
| 归档(finish 通过后) | `openspec archive <id> -y` |

---

## 7. 卡住了往哪查

| 症状 | 优先看 |
|---|---|
| `evidence_missing` blocker(finish gate) | `forgeue_integrated_ai_workflow.md` §D.1 evidence 子目录 + §3.1 / §3.2 evidence 类型表 |
| `evidence_references_missing_anchor` exit 5 | 检查 `execution/execution_plan.md` 引用的 `tasks.md#X.Y` 是否真存在;不存在则回写 tasks.md 加锚或删除引用 |
| `aligned_false_no_drift` blocker | evidence frontmatter `aligned_with_contract: false` 必须配 `drift_decision`(写回 / disputed-permanent-drift)三选一 |
| `writeback_commit_unrelated` blocker | `git show --stat <sha>` 看该 commit 是否真改了 frontmatter 声明的 artifact;不是则补 commit 或换 sha |
| `disputed_drift_anchor_unresolved` blocker | `design.md` `## Reasoning Notes` 段加 `> Anchor: <slug>` + ≥ 20 词 / ≥ 60 非空白字符段落 |
| `tasks_unchecked` blocker | 早期 §1-§8 task 真未做完;§9-§11 self-stage 自动豁免(stage-aware filter) |
| `openspec_cli_missing` blocker | npm install -g @fastify/openspec;Windows 上 finish_gate 已用 `shutil.which` 解析 `.cmd` shim |
| 不知道某 evidence frontmatter 该写啥 | `forgeue_integrated_ai_workflow.md` §D.2 12-key schema + 已 archived change `openspec/changes/archive/2026-04-27-fuse-openspec-superpowers-workflow/review/` 里取模板 |
| Documentation Sync Gate `[DRIFT]` 不知怎么解 | `docs/ai_workflow/README.md` §4.3 提示词 → 输出 A/B/C/D 类裁决 |
| Codex review claim 看不出真假 | 沿 ForgeUE memory `feedback_verify_external_reviews`:**逐条** `file:line` 独立对照代码,verdict per item;**不**把 claim 当结论 |

---

## 8. 工具与文档结构速查

**8 个 `/forgeue:change-*` 命令** — `.claude/commands/forgeue/<name>.md` 各自有完整 Steps + Output + Guardrails。

**5 个 stdlib-only 工具** — `python tools/<name>.py --help`:
- `forgeue_env_detect.py` — 5 层 env 检测 + plugin 可用性启发式
- `forgeue_change_state.py` — state 推断 + 4 类 DRIFT 检测主力(`--writeback-check`)
- `forgeue_verify.py` — Level 0/1/2 编排 + verify_report 生成
- `forgeue_doc_sync_check.py` — 10 文档静态扫 + 标签
- `forgeue_finish_gate.py` — 中心化最后防线 + 11 项检查

**2 个 ForgeUE Skills**:
- `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` — 中心化编排器 backbone
- `.claude/skills/forgeue-doc-sync-gate/SKILL.md` — Sync Gate 子 skill

**Evidence 子目录**(`openspec/changes/<id>/`):
- `notes/` — helper bucket(brainstorming / onboarding;不强制 12-key,**不**满足 REQUIRED slot)
- `execution/` — formal(execution_plan / micro_tasks / tdd_log / debug_log)
- `review/` — formal(superpowers_review / codex_*_review / *_cross_check)
- `verification/` — formal(verify_report / doc_sync_report / finish_gate_report)

---

## 9. 深度参考

- 本文档是教程层;契约层 / 协议细节看 [`forgeue_integrated_ai_workflow.md`](forgeue_integrated_ai_workflow.md)
- 主流程主规则 / Documentation Sync Gate 主规则:[`README.md`](README.md)
- Level 0/1/2 验证矩阵:[`validation_matrix.md`](validation_matrix.md)
- Claude Code 视角速查:`CLAUDE.md` §"OpenSpec 工作流" / "ForgeUE Integrated AI Change Workflow"
- 其他 agent(Codex / Cursor / Aider)视角速查:`AGENTS.md` 同段
- 完整 evidence 模板参考:`openspec/changes/archive/2026-04-27-fuse-openspec-superpowers-workflow/`(self-host bootstrap)
