---
change_id: enhance-workflow-automation-executable-enforcement
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
disputed_open: 0
writeback_commit: 1fbe09b
resolved_at: 2026-05-05T13:50:00+08:00
created_at: 2026-05-05T13:30:00+08:00
---

# Design Cross-check — enhance-workflow-automation-executable-enforcement

## A. Decision Summary(Claude 立场,冻结于 codex review 之前)

> **协议自我保护**:本段在 `/codex:adversarial-review` 调用之前完成,锁定 Claude 对 8 D-decision 的立场。codex 输出之后只填 `## B/C/D`,不回填 `## A`。

### A.1 D-W1-ReceiptSchema(Preflight wrapper receipt JSON 11 字段)

**Claude 立场**:Receipt JSON 字段最小化但版本化。LLM 只需复制 2 个字段(`worktree_path` + `receipt_id`),其他 9 字段(`change_id` / `protocol_version` / `base_sha` / `base_branch` / `cwd_at_invocation` / `skill_cascade_check` / `created_at` / `wrapper_version`)是 finish_gate 内部 audit 用。

**Why**:
- LLM context 接触面越小,emulation drift 越小(沿 Layer 6 root cause)
- protocol_version + wrapper_version 双 version field 自描述,后续协议升级有 anchor
- skill_cascade_check 嵌入 receipt 避免 evidence 重复扫描

**Anticipated codex challenge**:
- (a) receipt 11 字段太多 → 不接受;裁剪后 finish_gate 失去 audit 锚点
- (b) base_sha + cwd 应该外置 / 走 git 自身 → 不接受;receipt 是物证,git 状态运行时可变,需要 freeze
- (c) wrapper_version 与 protocol_version 重复 → 接受讨论但建议保留(wrapper bug fix 不必 bump protocol)

### A.2 D-W2-OverlapDetection(Parallel actual diff + 自动降级 sequential)

**Claude 立场**:dispatch 后(implementer commit 完成后)主 session 跑 `git diff --name-only <base_sha>..HEAD` 在每个 implementer worktree 内收集 actual changed-files set;intersection 非空 → **自动降级** `/forgeue:change-apply-subagent` sequential,无 user prompt。

**Why**:
- "actual diff" 是物证,优于 controller declaration(import / shared fixture / global config 不在直接 file scope)
- 自动降级 vs ask user:user feedback `feedback_no_continue_prompts_between_phases.md` 明确连续推 phase 不要 prompt
- sequential 是已 ship 的稳定路径,降级后 user 自动获得正确结果

**Anticipated codex challenge**:
- (a) `git diff --name-only` 漏 untracked file → OQ-2 已显式提出;倾向用 `git status --short` 替代;接受
- (b) implementer subagent 失败 / 没 commit 时主 session 取不到 diff → 需补"implementer 必须 commit 才进入 overlap 检测"约束;接受
- (c) 自动降级丢失 implementer wall-clock → 接受 trade-off(R5);overlap 是 controller 误判,降级是修正

### A.3 D-W3-LedgerFormat(JSONL append-only + wrapper-only write)

**Claude 立场**:`<change>/dispatch_ledger.jsonl`,JSONL 格式,append-only;`forgeue_dispatch_ledger.py append` 子命令唯一写入 path;LLM context 不暴露 ledger 文件路径(命令模板里走 wrapper invocation,不 Read / Write / Edit ledger)。

**Why**:
- JSONL 比 markdown / SQLite 更可 reproducible parse + git diff 友好
- Append-only + LLM context isolation 双层防伪造
- task_subject_hash 而非明文,既能比对又不暴露任务文本

**Anticipated codex challenge**:
- (a) LLM 仍可 echo > 重写 ledger → fence `_check_dispatch_ledger` 校验 timestamp 单调性 + wrapper_version + 行数 ≥ evidence 声明;接受 mitigation 但不接受 cryptographic signing(过度工程,沿 D-DispatchWrapperBoundary)
- (b) ledger per-change vs 全局 → OQ-3 显式提出;倾向 per-change(隔离 + archive 一起带走);接受
- (c) wrapper Python 启动开销 N × 200ms → 接受 R6(相对 implementer 自身 wall-clock 忽略不计)

### A.4 D-DispatchWrapperBoundary(LLM 不能直接写 receipt / ledger 的实施边界)

**Claude 立场**:LLM 对 receipt 是**可读不可写**(复制 2 字段);对 ledger 是**不读不写**(完全 wrapper 间接);命令模板**显式禁止** Read/Write/Edit 操作 ledger path。

**Why**:
- 第一层防伪造:context isolation(LLM 看不到就不会试图 explain / debug / 改)
- 第二层防伪造:fence 校验 timestamp 单调性 + wrapper_version + ledger ⊇ evidence
- 完整 GPG signing 留 follow-on(实证不够时再加;过度工程拒绝)

**Anticipated codex challenge**:
- (a) "LLM context 不暴露 path" 难强制(LLM 总能理解模板里 wrapper 命令含义)→ 接受局限;mitigation 是命令模板 markdown lint fence + reasonable controller behavior 假设
- (b) Wrapper exec 路径污染(LLM 修改 wrapper 自身)→ 不接受新规;wrapper 在 `tools/` 下走标准 git diff review(任何 commit 修改 wrapper 必经 codex review)
- (c) GPG signing 应该加 → 不接受;过度工程,沿 D-LedgerFormat (a) 拒绝

### A.5 D-DegradationPath(Overlap detected 自动降级 sequential)

**Claude 立场**:见 A.2;自动降级 + evidence 记录 `degraded_to: change-apply-subagent` + `degradation_reason: actual_file_overlap_detected`;finish_gate fence 在 `degraded_to` 非 null 时改走 sequential 路径校验逻辑。

**Why**:见 A.2;沿 user feedback 不 prompt + sequential 是稳定 fallback。

**Anticipated codex challenge**:
- (a) 自动降级 mask 真问题(controller 应该意识到 overlap 发生)→ 不接受;evidence frontmatter `degradation_reason` + `<change>/parallel_abort_<iso>.log` 明确记录,事后审计完整
- (b) 应该提供 `--no-degrade` flag 强制 abort → 不接受 default;若实证需要,follow-on 加 flag 不破坏现有行为

### A.6 D-FrontmatterSchemaExtension(protocol_version v2 + 5 new fields)

**Claude 立场**:沿 v1 同款 protocol_version migration 模式(D-ProtocolVersionMigration);v1 → v2 单调递增,新 fence 只严不松;v1 evidence 沿 v1 fence 完全兼容;archived enhance-workflow-automation-runtime-enforcement evidence(v1)在本 change ship 后 replay 不 false-block。

**Why**:沿 v1 ship 时已 user-accept 的 migration 模式;不引入 backfill 工作量(沿"归档即冻结"原则)。

**Anticipated codex challenge**:
- (a) 5 new fields 太多 → 接受讨论;但 worktree_receipt_path / dispatch_ledger_path / task_files_actual / degraded_to / degradation_reason 各对应一个独立 fence,无冗余
- (b) v2 应该 v1.1 / 不 bump major → 拒绝;protocol 是 deterministic vs advisory 的根本分界,bump major 合理
- (c) v1 evidence 应该 backfill 到 v2 → 拒绝;沿 D-DogfoodGap + 归档冻结原则

### A.7 D-DogfoodGap(本 change 自身仍走 v1 advisory)

**Claude 立场**:本 change 实施时 W1 wrapper 还没 ship,本 change 自身 evidence 沿 v1 advisory;**不**含 v2 字段;`runtime_enforcement_protocol_version: v1`。本 change archive 后第一个 follow-on change 是真 dogfood。

**Why**:bootstrap 期不可能用未 ship 的 wrapper(没法跑);本 change 自身 worktree 漏 preflight 风险与 advisory ship 时同 risk 等级(R6 在 v1 ship 时已被 user accept)。

**Anticipated codex challenge**:
- (a) DogfoodGap 是协议漏洞,本 change 应延期到能自 dogfood → 拒绝;bootstrap gap 在任何新 enforcement 协议都存在,user 已 accept R6 advisory ship
- (b) 应该手工模拟 wrapper(写 fake receipt 验证流程)→ 不接受 default;额外维护成本无价值;sequential dispatch + v1 advisory 已经是 production proven 路径
- (c) 应该在 evidence frontmatter 标注 `dogfood_gap_acknowledged: true` → 接受讨论(可能加 audit anchor)

### A.8 D-W3-WrapperImpl(Dispatch ledger wrapper 在命令模板里 invoke 模式)

**Claude 立场**:命令模板内每个 Skill(Task) / SendMessage 调用前后嵌入 Bash step 调用 `forgeue_dispatch_ledger.py append`;**不**用 ~/.claude/settings.json `PreToolUse` hook(跨 project 污染);**不**让 wrapper 替代 Skill(Task)调用本身。

**Why**:
- Bash step 自描述,可 unit-test 命令模板含 wrapper invoke step
- Hook 跨 project 污染 + 不易测试
- Wrapper spawn agent 绕过 Skill tool 失去 stream / monitor / cost tracking

**Anticipated codex challenge**:
- (a) Bash step 与 Skill(Task) 时序无原子性(implementer 已派但 ledger 没 append)→ 接受;mitigation:wrapper 在 dispatch **之前** append(不是之后),implementer 即使失败也保留 dispatch 记录
- (b) 应该用 PostToolUse hook 自动 append → 拒绝;违 D-W3-WrapperImpl alternative (a)
- (c) agent_id capture 不可靠(Skill tool 不返回 stable id)→ 真问题;需补 P0/P1 测试覆盖 capture pattern

### A.9 Open Questions 立场

- **OQ-1**(W1 wrapper 在 worktree 已存在时 reuse?):**reuse if base_sha 一致 + clean tree**;否则 fail-closed
- **OQ-2**(W2 actual diff 是否包含 untracked?):**包含**(用 `git status --short` 替代 `git diff --name-only`)
- **OQ-3**(W3 ledger per-change vs 全局?):**per-change**(沿 design statement;隔离 + archive 一起带走)
- **OQ-4**(Receipt 是否含 cleanup 信息?):**否**(receipt 是 dispatch 时刻物证,cleanup 是 finish 时刻事件,需要时另写 `<id>.cleanup.json`)

## B. Codex Findings — Resolution Matrix

| ID | Severity | Codex 推荐 | Claude 独立 verify(file:line) | Verdict | Resolution |
|---|---|---|---|---|---|
| F1 | high | wrapper 自创 / 校验 isolated worktree + skipped-skill / wrong-cwd 负例 | tasks.md:19 显式说 wrapper "**不直接 invoke Skill tool**(wrapper 是命令模板调用前置 step;命令模板内 wrapper 后才 invoke `Skill(superpowers:using-git-worktrees)`)";controller 跳过命令模板 worktree step 后,wrapper 仅校验当前 git 状态,无法证明 cwd 在 isolated worktree 内 → **真漏洞** | **accepted-codex,inline writeback** | tasks.md P0.2 改:wrapper 自己用 `git worktree add / verify` subprocess 创建 / 验证 worktree(不依赖 Skill tool);receipt 加 `is_isolated_worktree: bool` 字段;P0.4 加 negative test "wrong-cwd-fail-closed" + "skipped-skill-receipt-rejected"(receipt 不在 worktree cwd 内 → exit 6) |
| F2 | high | wrapper/hook 包 dispatch 并 capture 真实 agent_id,或测试 caller-supplied agent_id;P0/P1 加 Skill 输出 capture 集成测试 + synthetic agent_id 被拒绝负例 | design.md:241-244 显式 `$AGENT_ID=$(uuid_v4)  # 或从 Skill tool 后处理 capture`;Claude Code Skill tool **不支持** caller-supplied agent_id(实测 Skill(Task) 返回的 ID 由 Claude Code 自动生成,无 metadata 注入);ledger 写的是 wrapper 生成的 uuid_v4 synthetic ID,与真实 subagent agent_id 无关 → **真漏洞** | **accepted-codex,partial inline + deferred** | (a) **Inline**:design.md D-W3-WrapperImpl Statement 改为 **post-dispatch ledger capture** — Skill(Task) 返回后立即从 Skill 输出 capture 真实 agent_id,然后 Bash wrapper append ledger;evidence frontmatter 标注 `pre_dispatch_metadata: advisory`(放弃 pre-dispatch 物证);P0/P1 加 Skill 输出 capture pattern 集成测试。(b) **Deferred** 真 wrapper-bound dispatch 到 follow-on `enhance-workflow-automation-ledger-binding`(需 Hook system 或 Claude Code Skill tool 协议扩展) |
| F3 | high | ledger 写入移出 LLM 可写面(wrapper/hook 包 dispatch),或加对 LLM 不可见 nonce/HMAC + finish_gate 校验;新增 well-formed forged ledger 仍失败的负例 | design.md:144 + 162 — `wrapper_version` 是 const("1.0")+ `dispatch_ledger_path` 是 fixed string + timestamp 是 LLM 可写域;同一能伪造 frontmatter 的 controller 写出 monotonic timestamp + wrapper_version: "1.0" 即通过 fence → **真漏洞**;Claude 立场 A.4 已自承 "context isolation 难强制" | **accepted-codex,降级标注 + deferred** | (a) **Inline**:design.md D-DispatchWrapperBoundary + Risk R3 改为显式标注 "fence 仅 catch crude forge,well-formed forge 不阻断 — 沿 v1 advisory 同款限制";evidence frontmatter 加 `ledger_forgery_resistance: advisory`(诚实标注 advisory not deterministic for adversarial controller)。(b) **Deferred** cryptographic enforcement(Hook + nonce/HMAC + key 不在 LLM 可见域)到同一 follow-on `enhance-workflow-automation-ledger-binding` |
| F4 | high | normative contract 改 `git status --porcelain=v1 -z`(含 untracked/staged/dirty)+ committed diff;require implementer worktree clean 或 fail-closed;更新 tasks 静态测试 | spec.md:82 写 `git diff --name-only <base_sha>..HEAD` 是 SHALL;design.md OQ-2 自承 "`git diff --name-only` 不覆盖 untracked file";真实失败:implementer 漏 `git add` 新文件 → actual overlap 检测得空集 → parallel 通过 → merge 才发现冲突 → **真漏洞** | **accepted-codex,inline writeback** | spec.md "Parallel dispatch actual file overlap detection" Requirement 改 SHALL `git status --porcelain=v1 -z` 收集(含 untracked);design.md D-W2-OverlapDetection step 1 同款改 + 加 step 0 "implementer worktree MUST clean(no dirty files)before overlap detection,否则 fail-closed";tasks.md P3.3 + P3.5 fence test 字符串同步;OQ-2 status 标 "resolved-inline" |
| F5 | high | P12.2 提前为 P6/P10 必过 gate;创建 synthetic active change / fixture 跑 v2 全链路;archive 前必须有 v2 evidence 通过 + 一个 overlap 负例失败 | tasks.md P10.4 显式 "evidence 全部 v1 + 不强制 v2 字段";P12.2 在 "后置(可选)" 段;archive 前 v2 协议无任何端到端实跑;若 v2 协议有 bug 本 change archive 后才被下一 change 暴露 → **真漏洞**;原 D-DogfoodGap rationale 是 "wrapper 还没 ship 无法自 dogfood",但可创建 fixture(synthetic change in tmp_path)模拟 v2 evidence 跑全链路 | **accepted-codex,inline writeback** | tasks.md 加新 phase **P5.5 v2 e2e integration test**(在 P5 文档同步前):`tests/integration/test_v2_e2e_synthetic_change.py` 创建 tmp synthetic change → 跑 W1 wrapper → 跑 Skill(Task) capture pattern → 跑 W3 ledger append → 跑 W2 actual diff(含 overlap 负例)→ 跑 finish_gate 全 6 fence;P10 加 "P10.0 v2 e2e gate must pass" 必过项;P12.2 改为 "实战 dogfood(下一个真 change)"(辅助验证,不替代 P5.5 fixture gate) |

**Resolution enum**:`aligned`(claim 与 Claude 立场一致)/ `accepted-codex,inline writeback`(claim 真,本 change scope 内 inline 修)/ `accepted-codex,partial inline + deferred`(claim 真,部分 inline,部分 follow-on)/ `accepted-claude`(claim 假,Claude 立场对)/ `disputed-pending`(待裁决)/ `disputed-permanent-drift`(协议接受永久 drift)。

## C. Disputed Open Tally

`disputed_open: 0`

- 5 finding 全部 `accepted-codex`(独立 file:line verify 全 TRUE)
- 2 partial deferred(F2 + F3)→ 同一 follow-on `enhance-workflow-automation-ledger-binding`(独立 architectural change,需 Claude Code Skill tool 协议扩展或 Hook system 接入)
- 3 inline writeback(F1 + F4 + F5)→ 本 change scope 内修

**触发 fence**:本次 cross-check 揭示 5 个 framework / design.md 内部不一致(F1/F2/F3/F4/F5 各自 file:line 显示 design 与 tasks / spec 不匹配 / 内部矛盾),按 `feedback_autonomy_boundary_simplified.md` 升级 user 拍板:
- (A) 全 5 inline writeback(本 change scope 翻倍 — 加 P0.2 wrapper 自创 worktree / D-W3 改 post-dispatch / D-DispatchWrapperBoundary 降级 advisory / D-W2 改 git status / 加 P5.5 v2 e2e fixture)
- (B) 推荐方案:**3 inline + 2 deferred**(F1 + F4 + F5 inline;F2 + F3 deferred 到 `enhance-workflow-automation-ledger-binding` follow-on);本 change scope 增加 ~30%(可控)
- (C) 全 5 deferred → 本 change 几乎空(违背 close F1/F2/F3 的初衷)
- (D) Cancel 本 change → 与 user 起本 change 的初衷相悖

## D. Independent Verification(Claude 不把 codex claim 当结论)

沿 ForgeUE memory `feedback_verify_external_reviews`:Codex review 意见要独立对照代码验证,不把 claim 当结论。

**verify 命令矩阵**:

| Finding | verify 命令 | verify 结果 |
|---|---|---|
| F1 | `grep -n "不直接 invoke Skill tool" tasks.md` | tasks.md:19 命中,文字 "**不直接 invoke Skill tool**(wrapper 是命令模板调用前置 step;命令模板内 wrapper 后才 invoke `Skill(...)`)" → claim TRUE |
| F2 | `sed -n '236,260p' design.md` | design.md:241-244 命中 `$AGENT_ID=$(uuid_v4)  # 或从 Skill tool 后处理 capture` + `Skill(Task): dispatch implementer subagent(传 $AGENT_ID 作为 metadata)`;Claude Code Skill tool 实测**不**支持 caller-supplied agent_id(查 Skill tool schema:无 metadata 注入字段)→ claim TRUE |
| F3 | `sed -n '140,180p' design.md` | design.md:144 + 162 命中 `wrapper_version: "1.0"`(常量)+ `timestamp 单调性 + wrapper_version 字段 + JSON well-formed` 是 fence 全部内容;controller 写出 monotonic ts + ver=1.0 即通过 → claim TRUE |
| F4 | `sed -n '82,100p' specs/.../spec.md` + `grep -n "OQ-2" design.md` | spec.md:82 命中 `git diff --name-only <base_sha>..HEAD`(SHALL);design.md OQ-2 命中 "`git diff --name-only` 不覆盖 untracked file" + 倾向 "包含"(用 `git status --short`);spec 与 design 不一致 + design 自承漏洞 → claim TRUE |
| F5 | `sed -n '174,200p' tasks.md` + `grep -n "P12.2\|P10.4" tasks.md` | tasks.md P10.4 显式 "evidence 全部 `runtime_enforcement_protocol_version: v1`";P12.2 在 "## P12 — 后置(可选) + Follow-on tracking" 段(必非过 gate);archive 前 v2 协议无端到端实跑 → claim TRUE |

5/5 codex claim 真存在,无 disputed。

## Recommended Resolution Path(Claude 推荐 (B))

**(B) 3 inline + 2 deferred**:

**Inline writeback**(本 change scope 内修,F1 + F4 + F5):
1. **F1 inline**:design.md D-W1-ReceiptSchema + tasks.md P0.2 改 wrapper 自己 `git worktree add / verify` subprocess 创建 / 验证 worktree(不依赖 Skill tool);receipt 加 `is_isolated_worktree: bool` 字段;P0.4 加 2 negative test;estimate 工程量 +2 hour
2. **F4 inline**:spec.md / design.md / tasks.md P3.3 + P3.5 fence test 改 `git status --porcelain=v1 -z`(含 untracked)+ implementer worktree clean precondition;OQ-2 status 标 resolved;estimate 工程量 +1 hour
3. **F5 inline**:tasks.md 新加 phase P5.5 v2 e2e integration test fixture(`tests/integration/test_v2_e2e_synthetic_change.py`)+ P10 加 P10.0 必过 gate;estimate 工程量 +4 hour(synthetic active change fixture + 6 fence e2e + overlap 负例)

**Deferred follow-on**(独立 architectural change,F2 + F3):
- **`enhance-workflow-automation-ledger-binding`**(新 follow-on)— W3 真 wrapper-bound dispatch:
  - 路径 (a):接入 Claude Code Hook system(`PreToolUse` hook 拦截 Task / SendMessage 自动写 ledger)
  - 路径 (b):申请 Claude Code Skill tool 协议扩展(允许 caller-supplied agent_id metadata)
  - 路径 (c):cryptographic enforcement(wrapper 写 nonce/HMAC,key 在 LLM 不可见 env var 域)
  - 触发条件:本 change ship 后,实测 advisory protocol 不足以挡 controller drift(若足够,可 cancel follow-on)

**Updated change scope**:
- 工程量:原 estimate ~8 hour → 新 estimate ~15 hour(+~88%)
- 增加 1 phase(P5.5)+ 升级 P10 + P12.2 角色重定义
- 新加 1 follow-on tracking 行(P12.5 → P12.6 移位)
- design.md 加 R8 risk(F3 advisory 限制)+ updated D-W3-WrapperImpl Statement(post-dispatch capture)+ updated D-W1-ReceiptSchema Statement(wrapper 自创 worktree)+ 新 D-W4-IntegrationGate(F5 e2e fixture)
- spec.md 改 SHALL git status(F4)
- tasks.md 加 P0.2 wrapper 自创 worktree subprocess + P0.4 wrong-cwd negative + P5.5 e2e + P10.0 必过 gate

**Pending user verdict**:Resolution path (A) / (B) / (C) / (D)?推荐 **(B)**。

