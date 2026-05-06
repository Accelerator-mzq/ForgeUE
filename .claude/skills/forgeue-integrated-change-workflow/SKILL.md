---
name: forgeue-integrated-change-workflow
description: ForgeUE 中心化编排器主 skill;每个 /forgeue:change-* command 引用本 skill 作 backbone。包含中心化架构图 + Superpowers/codex 集成边界 + S0-S9 状态机 + 4 类 DRIFT taxonomy + 12-key frontmatter + writeback 协议 + cross-check A/B/C/D 模板。
license: MIT
compatibility: Requires openspec CLI + Claude Code (Superpowers + codex-plugin-cc 可选,降级 OPTIONAL 不阻断 archive)
metadata:
  author: forgeue
  version: "1.0"
---

ForgeUE Integrated AI Change Workflow 的中心化编排器。本 skill 是 10 个 `/forgeue:change-*` command(`change-{status,plan,apply-subagent,apply-parallel,apply-direct,debug,verify,review,doc-sync,finish}`;自 `adopt-subagent-driven-development` change 起拆 subagent + direct;自 `enhance-workflow-automation-runtime-enforcement` change 起加 parallel,共 10)的共享 backbone:统一架构 + 状态机 + 协议,每个 command 只引用本 skill,不重复定义。

**真源**:`openspec/changes/fuse-openspec-superpowers-workflow/design.md` §1-§11 + Reasoning Notes;`docs/ai_workflow/forgeue_integrated_ai_workflow.md`(本 skill 的 user-facing 详表 + 阅读引导)。

## 中心化架构(design.md §1)

```
                    OpenSpec Contract Artifact (唯一锚点)
              proposal.md / design.md / tasks.md / specs/
                              ^
                              | writeback required
        ----------------------------------------------------------
        | Superpowers evidence | codex review evidence | tools DRIFT |
        ----------------------------------------------------------
                              |
              ForgeUE guard tools: state / verify / doc-sync / finish
```

OpenSpec contract artifact 是项目唯一规范锚点;Superpowers / codex / ForgeUE tool 产生的 evidence **服务于这个中心**,不并立。

**evidence 不能成新规范源**:实施暴露的 contract 漏洞**必须回写到 OpenSpec contract**,禁止在 evidence 里宣告"新决策"。

## Superpowers 集成边界(design.md §6 / §8 / forgeue_integrated_ai_workflow.md §B.3)

| Superpowers skill | trigger 时机 | ForgeUE 配置 / 边界 |
|---|---|---|
| `brainstorming` | S0 / S1 起草 proposal 前 | scope 变化是否回写 proposal |
| `writing-plans` | S2(`/forgeue:change-plan` 内) | 输出落 `execution/execution_plan.md` + `execution/micro_tasks.md` |
| `executing-plans` | S3-S4 | 实施时 Claude 主动调,不强制 |
| `test-driven-development` | S4 实施 | tdd_log 追加;**不**重复造 ForgeUE TDD skill |
| `systematic-debugging` | S4 bug 时(`/forgeue:change-debug`)| debug_log 追加 |
| `requesting-code-review` | S5-S6 | superpowers_review 增量 + finalize |
| `verification-before-completion` | S5 | verify_report 输入 |
| `finishing-a-development-branch` | S9 后 | git 层 merge / PR / discard;不进 evidence |
| `using-git-worktrees` | **consent-gated;default decline in implementation;opt-in for bug-fix iteration / explicit isolation**(ADR-013;archived `restore-superpowers-worktree-consent-gate` change)| Step 0 outcome × mode 状态机:`declined + in_place`(default,main repo cwd)/ `accepted + skill_worktree`(skill 自管 worktree)/ `accepted + wrapper_worktree`(opt-in W1 wrapper + receipt)/ `already_isolated + {skill,wrapper}_worktree`(session 已 isolated)/ `sandbox_fallback + in_place`;详 sister skill `subagent-driven-discipline` §3.5 Worktree Consent Policy |
| `subagent-driven-development` | **default sequential for `/forgeue:change-apply-subagent`**(ADR-009 token-budget tracker informational) | 4× LLM 调用;per-task 4 类 evidence + `subagent_budget.log`;ADR-009 与 ADR-007 vendor API 双扣边界**根本不同**;controller-side 40% scenario judgment 见 universal sister skill `subagent-driven-discipline`(8 patterns + growing case studies — model 矩阵 / cwd verify / cross-verify / strict reviewer prompts / cherry-pick recovery / inline fix vs round 2 / skip review boundary / cost-benefit) |
| `dispatching-parallel-agents` | **for `/forgeue:change-apply-parallel`**(自 `enhance-workflow-automation-runtime-enforcement` change 起;借用 pattern,debugging-focused → implementation 借用) | 并行 dispatch implementer subagents;controller 显式判定 task 独立后路由(`task_independence_assertion: true` + `task_files_disjoint`,命令前自动 verify file overlap)|

## Autonomy Boundary Protocol(ADR-010,自 `enhance-workflow-automation` change 起)

Claude 默认拍板执行 + 同步 invoke codex 二次验证。**6 类 fence 无条件升级用户**:

| Fence | 类别 | 触发 |
|---|---|---|
| 1 | 不可逆操作 | `git push` / `archive change` / `git reset --hard` / `git branch -D` / `rm <非临时>` / `commit --amend` 已 push |
| 2 | 跨 change 决策 | 修改非本 change D-decision / 动其他 active change contract artifact |
| 3 | Claude+Codex 冲突 | verdict 不一致;Verdict Normalization 判定(非字符串 == 比较) |
| 4 | 用户先验约束 | CLAUDE.md / AGENTS.md / MEMORY.md explicit fence rule 触发 |
| 5 | 钱 | ADR-007 vendor API paid call |
| 6 | Secret / 安全 | .env 写入 / `*api_key*` / `*credential*` / `*secret*` 文件操作 |

**`autonomy_decision` 字段**(每条 implementation evidence 必填):
- `claude_autonomous` — 极小 step 无 codex 验证
- `claude_codex_concurred` — Claude+Codex 一致 → 自主执行;必配 `codex_review_ref`
- `user_required` — fence 触发 / Claude+Codex 冲突
- `user_overrode` — 用户主动否决

`forgeue_finish_gate.py` `_check_autonomy_boundary` fence 守门(缺字段 / 值非法 / `concurred` 缺 ref / ref 路径不存在 / ref 跨 change → exit 非 0)。

**Codex 默认 background dispatch(D-DefaultBackground)**:大 scope 默认 background;仅 ≤2 files / ≤50 lines / 非 adversarial / 下一步必须等结果时才前台 wait。Background 启动后 main session 轮询 `/codex:status --wait <job>` + `/codex:result <job>` 拿 result 后才能写 `claude_codex_concurred` evidence。

**Codex 多轮 context bridge(D-CodexContextBridge)**:同 change_id + 同 review_type round N→N+1 prompt 首段自动注入 round N evidence reference;round counter 落 `notes/codex_<review_type>_round_counter.txt`;跨 change / 跨 review_type 绝不共享。

完整协议见 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C Autonomy Boundary Protocol。

## Runtime Enforcement Protocol(ADR-011,自 `enhance-workflow-automation-runtime-enforcement` change 起)

> **⚠️ Superseded note(ADR-013;archived `restore-superpowers-worktree-consent-gate` change 2026-05-06)**:
> D-WorktreeEnforce mandatory worktree 部分由 ADR-013 D-RestoreConsentGate + D-ConsentOutcomeStateMachine **superseded** —
> `_check_worktree_path` v1 fence 改 mode-conditional advisory(legacy archived evidence pass-through;ADR-013 evidence 走 outcome × mode 状态机);
> 加 `_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 2 新 fence(沿 ADR-013 D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant);
> archived ADR-011 evidence replay 不被 false-block(沿 legacy pass-through 兼容意图);
> 详见本 skill 末尾 "ADR-013 Restore Superpowers Worktree Consent Gate" 段。

**4 fence**(`tools/forgeue_finish_gate.py`):

| Fence | D-decision | evidence frontmatter 检查 |
|---|---|---|
| `_check_skill_cascade` | D-SkillCascadeCheck | `skill_cascade_audit` dict(`invoked_skills` list + `cascade_check_pass_at` ISO timestamp)|
| `_check_round_fix_continuity` | D-RoundFixContinuity | `subagent_continuity` dict(round 1/2 implementer + reviewer ID 一致)|
| `_check_task_granularity` | D-TaskGranularityDeclaration | `task_granularity` ∈ {phase, per-file, sub-task} |
| `_check_worktree_path` | D-WorktreeEnforce(superseded by ADR-013)| **mode-conditional advisory**(沿 ADR-013):legacy(无 outcome)→ pass-through;mode in_place → 禁写 worktree_path;mode skill_worktree / wrapper_worktree → 必写 worktree_path |
| `_check_worktree_consent_outcome` **(新加 ADR-013)** | D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant | `worktree_consent_outcome` ∈ {declined, accepted, already_isolated, sandbox_fallback} + outcome × mode invariant + already_isolated path != main repo |
| `_check_worktree_mode_consistency` **(新加 ADR-013)** | D-ConsentOutcomeStateMachine | `worktree_mode` ∈ {in_place, skill_worktree, wrapper_worktree} + mode-conditional path/receipt 字段共存 invariant |

**Protocol gating**(D-ProtocolVersionMigration):4 fence 仅对含 `runtime_enforcement_protocol_version: v1` 的 evidence 生效;legacy archived evidence 全 pass-through。

**8 个 SKILL-invoke 命令 Preflight section**(D-PreflightProtocol):

| 命令 | Preflight Worktree | Preflight Skill Cascade | Preflight Task Granularity |
|---|---|---|---|
| `change-apply-subagent` / `change-apply-parallel` | ✓ | ✓ | ✓ |
| `change-apply-direct` | **N/A**(D-DirectWorktreeRefinement)| ✓ | ✓ |
| `change-plan` / `change-debug` / `change-verify` / `change-review` / `change-doc-sync` | — | ✓ | — |
| `change-finish` / `change-status` | — | **N/A**(纯工具 / 只读)| — |
| codex `/review` / `/adversarial-review` | — | **N/A**(纯 codex CLI dispatch,disclaimer)| — |

**新增 evidence frontmatter 字段**:`runtime_enforcement_protocol_version: v1`(协议版本标记)/ `worktree_path` / `skill_cascade_audit` / `subagent_continuity` / `task_granularity` / `task_independence_assertion` + `task_files_disjoint`(仅 parallel)。

**新增工具 `tools/forgeue_skill_cascade_check.py`**:静态扫 SKILL.md `## Integration` 段验证 dependency 全 invoke;8 root probe 链 fallback。

**真 deterministic enforcement** 留 follow-on `enhance-workflow-automation-executable-enforcement`(W1 executable preflight wrapper / W2 changed-files diff overlap detection / W3 dispatch ledger);本 change 实装是 advisory not deterministic(R6 limitation)。

完整规则见 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C.7 Runtime Enforcement Protocol。

## Runtime Enforcement Protocol v2(ADR-012,自 `enhance-workflow-automation-executable-enforcement` change 起)

> **⚠️ Superseded note(ADR-013;archived `restore-superpowers-worktree-consent-gate` change 2026-05-06)**:
> D-W1-ReceiptSchema mandatory invocation 部分由 ADR-013 D-RestoreConsentGate + D-WrapperDeprecate **superseded** —
> wrapper(`tools/forgeue_preflight_wrapper.py`)标 deprecated 但 functional;命令模板 default decline 路径不再 mandatory invoke wrapper;
> 仅 user 显式 opt-in `worktree_mode: wrapper_worktree` 时才调用 wrapper;
> `_check_worktree_path_v2` fence 改 mode-conditional(仅 wrapper_worktree mode 强制 receipt cross-check;其他 mode pass-through);
> archived ADR-012 evidence replay 不被 false-block(沿 legacy pass-through);
> wrapper W7-a bug fix(`_git_repo_root` 改用 `git rev-parse --git-common-dir`)在本 change scope 内;
> 详见本 skill 末尾 "ADR-013 Restore Superpowers Worktree Consent Gate" 段。

ADR-011 v1 是 advisory not deterministic(R6 限制)— controller 跳过 markdown step 时 subagent 已修改 / finish_gate 是 archive 时才扫,无法 abort dispatch。本 change 升级 v2 为 **executable enforcement layer**(W1 wrapper + W2 actual diff + W3 ledger),关闭 v1 F1/F2/F3 deferred gap。

### W1 — `tools/forgeue_preflight_wrapper.py`(F1 round 1 + F2 round 2 inline writeback)

**Wrapper 自管 isolated worktree**(不依赖 SKILL invoke):
- 算法:`git worktree list --porcelain` parse → 不存在则 `git worktree add <target> -b worktree-<change-id>`;dirty → exit 6;wrong-cwd → exit 6
- 强制 cwd 校验:`os.path.realpath(cwd) == os.path.realpath(worktree)`,不一致 fail-closed
- exit codes:0 OK / 5 cascade fail / 6 git fail(wrong-cwd / dirty / not-repo)/ 7 receipt fail
- **13-field receipt JSON**(含 `is_isolated_worktree: true` + `worktree_action ∈ {created, reused}`)写到 `<change>/preflight_receipts/<receipt_id>.json`
- LLM 只复制 2 字段(worktree_path + worktree_receipt_path)到 evidence frontmatter

**命令模板调用**:`/forgeue:change-apply-{subagent,parallel}` Preflight Worktree section invoke wrapper(沿命令模板 step 1)。

### W2 — Parallel actual diff overlap detection(F4 round 1 + F3 round 2 inline writeback)

`/forgeue:change-apply-parallel` 在 implementer commit 完成后主 session 跑:
- **Step 0 dirty precondition**:`git -C <impl-worktree> status --porcelain=v1` → 非空 → 自动降级 sequential + abort log `<change>/parallel_abort_dirty_<iso>.log`
- **Step 1 actual changed-files 收集**:`git diff --name-only -z <base>..HEAD` + `git ls-files --others --exclude-standard -z` 合集(含 untracked)+ NUL parse + Bash dict → JSON 序列化(`IMPL_FILES_JSON` env var)
- **Step 2 cross-implementer set intersection**:inline python3 → 非空 → abort + `<change>/parallel_abort_overlap_<iso>.log` + 自动降级 sequential
- **abort log 沿 ForgeUE 产物路径约定**(`<change>/parallel_abort_*` 不 `/tmp/`)
- evidence frontmatter `task_files_actual` / `degraded_to` / `degradation_reason`(`actual_file_overlap_detected` / `dirty_implementer_worktree`)

### W3 — `tools/forgeue_dispatch_ledger.py`(F2 round 1 + F1 round 2 inline writeback)

**Append-only JSONL ledger**(`<change>/dispatch_ledger.jsonl`):
- 子命令:`append`(写一行 JSON 到 ledger)+ `verify`(校验 timestamp 单调 + wrapper_version 字段 + JSON well-formed)
- 7 字段:agent_id / round / role / task_subject_hash / dispatched_at(ISO8601) / parent_session_id / wrapper_version
- VALID_ROLES enum 6 个:implementer / spec_reviewer / code_quality_reviewer / final_reviewer / implementer_round_2_fix / spec_reviewer_round_2_review

**命令模板 post-dispatch capture**(F1 round 2 inline writeback;关闭 round 1 synthetic UUID 漏洞):
- Skill(Task) dispatch **之后**从 return parse 真实 agent_id → Bash wrapper append ledger
- 不允许 dispatch **之前**用 `$AGENT_ID=$(uuid_v4)` synthetic ID(原 round 1 设计被 codex F2 揭穿)

### protocol_version dispatch matrix(`forgeue_finish_gate.py` v2 升级)

| evidence frontmatter 字段 | finish_gate 行为 |
|---|---|
| 缺 `runtime_enforcement_protocol_version`(legacy) | skip 全部 v1/v2 fence pass-through |
| `runtime_enforcement_protocol_version: v1` | 走 v1 fence(沿 ADR-011 既有 4 fence) |
| `runtime_enforcement_protocol_version: v2` | 走 v1 fence + v2 fence(v2 = v1 + additional checks,严格于 v1)|

**v2 新 / 升级 4 fence**:
- `_check_worktree_path_v2` — 校验 receipt JSON 文件存在 + receipt `worktree_path` == evidence frontmatter + `is_isolated_worktree: true`
- `_check_round_fix_continuity_v2` — 校验 evidence subagent_continuity agent_id 全部在 ledger 中有真实记录(防 LLM 伪造 agent_id)
- `_check_file_overlap_actual` — 新 fence:parallel only;`task_files_actual ⊆ task_files_disjoint declared` + actual 间 disjoint(若 `degraded_to: null`)
- `_check_dispatch_ledger` — 新 fence:inline ledger verify(JSON well-formed + wrapper_version 字段 + timestamp 单调递增)

### v2 evidence frontmatter 7 v2 字段

| 字段 | 描述 | F# inline writeback origin |
|---|---|---|
| `runtime_enforcement_protocol_version: v2` | 触发 v2 fence(v1/v2 共存,v1 evidence 不被 v2 fence 误杀) | F5 round 1 |
| `worktree_receipt_path: preflight_receipts/<receipt_id>.json` | LLM 复制 wrapper stdout(不直接写) | F1 round 1 |
| `worktree_path: <wrapper-managed worktree absolute path>` | LLM 复制 receipt JSON 字段 | F1 round 1 |
| `dispatch_ledger_path: dispatch_ledger.jsonl` | 固定值(LLM 不需变量)| F3 round 1 |
| `task_files_actual: list of {implementer_agent_id, files: [...]}` | parallel only;含 untracked file | F4 round 1 + F3 round 2 |
| `degraded_to: null 或 change-apply-subagent` + `degradation_reason: null / actual_file_overlap_detected / dirty_implementer_worktree` | 自动降级标识 | F4 round 1 |
| `pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory` | F2/F3 round 1 inline writeback advisory 标注(诚实暴露当前 limitation;真 cryptographic enforcement 留 follow-on `enhance-workflow-automation-ledger-binding`)| F2 + F3 round 1 |

### DogfoodGap(本 change 自身仍 v1 advisory)

本 change 实施时 W1 wrapper 还没 ship → 本 change evidence 全部 `runtime_enforcement_protocol_version: v1`(沿 v1 advisory + finish_gate audit 安全 archive)。**第一个真 v2 dogfood 是下一个 follow-on change**(任何 change),届时命令模板自动跑 W1 wrapper + W3 ledger + finish_gate v2 fence cross-check。

**P5.5 v2 e2e fixture**(`tests/integration/test_v2_e2e_synthetic_change.py`)= archive 必过 gate(P10.0 二次确认):mock 完成 v2 协议端到端实跑(W1 + W2 + W3 + finish_gate full 6 fence + overlap 负例 + dirty 负例 + v1/legacy 回归)。

### F2/F3 deferred 到 follow-on `enhance-workflow-automation-ledger-binding`

本 change 不 cover 的 architectural 升级:
- **F2 deferred 部分**:wrapper / Hook 拦截 Skill(Task) 调用 + 写 ledger 前拒绝 dispatch 直到 ledger 写入(真 wrapper-bound dispatch);或申请 Claude Code Skill tool 协议扩展(允许 caller-supplied agent_id metadata)
- **F3 deferred 部分**:cryptographic ledger signing — wrapper 写 nonce/HMAC 到 ledger,key 在 LLM 不可见 env var 域;finish_gate 校验 HMAC 一致性

**触发条件**:本 change ship 后实测 advisory protocol 不足以挡 controller drift(若足够,可 cancel follow-on)。

### Subagent dispatch 配套

本 change 引入命令模板 invoke `Skill(subagent-driven-discipline)`(sister skill;Layer 2 wiring)— controller dispatch subagent 前必含 Subagent Discipline preflight(详见 `subagent-driven-discipline/SKILL.md` §3.4 Trigger Type Matrix:Type 1 = 3-stage / Type 2 = parallel / Type 3 = standalone Task / Type 4 = ad-hoc / Type 5 = codex CLI;各自 retrospect intensity)。

完整规则见 `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C.8 Executable Enforcement Layer v2(待 P5 doc sync 落)。

## ADR-013:Restore Superpowers Worktree Consent Gate(自 archived `restore-superpowers-worktree-consent-gate` change 起,2026-05-06)

ADR-011 D-WorktreeEnforce + ADR-012 D-W1-ReceiptSchema 累积引入 ForgeUE-level **MANDATORY worktree enforcement**(命令模板 mandatory invoke + finish_gate `worktree_path` 必填);但 Superpowers upstream `using-git-worktrees` SKILL.md Step 0 含 user-consent gate(用户可 decline → "work in place"),ForgeUE mandatory 实质 override upstream consent gate。**ADR-013 revert mandatory 部分,restore Superpowers upstream Step 0 user-consent gate 行为**。

**4 D-decision**(完整 7 个 + 3 codex round 1/2 writeback 加,详见 archived `restore-superpowers-worktree-consent-gate/design.md`):

- **D-RestoreConsentGate**:命令模板 `change-apply-subagent` + `change-apply-parallel` `## Preflight Worktree` section 改 OPT-IN narrative(MUST invoke `Skill(superpowers:using-git-worktrees)` 沿 upstream cascade,但 default decline → main repo cwd;opt-in for bug-fix iteration / explicit isolation)
- **D-ConsentOutcomeStateMachine**(codex round 1 F2 + F3 writeback):evidence frontmatter `worktree_consent_outcome` enum + `worktree_mode` enum 必填;outcome × mode 显式状态机替代原 field-presence-conditional 推断
- **D-AlreadyIsolatedInvariant**(codex round 2 F2 writeback):`already_isolated` 必须 mode ∈ {skill_worktree, wrapper_worktree} + `worktree_path != main_repo`(关闭"已隔离 + main repo cwd 假声 isolated → 重新打开 F1 attribution"漏洞)
- **D-ParallelDeclineFallback**(codex round 1 F1 writeback):`/forgeue:change-apply-parallel` `declined + in_place` → 自动降级 sequential(无 user prompt;沿 R-no-continue-prompts);关闭"main repo + multi-implementer + W2 attribution"漏洞
- **D-WrapperDeprecate**:`tools/forgeue_preflight_wrapper.py` 标 deprecated 但 functional;命令模板 default decline 路径不再 mandatory invoke;仅 user 显式 opt-in `wrapper_worktree` mode 时调用
- **D-WrapperBugFixInScope**(codex round 2 F3 writeback):W7-a wrapper bug fix(`_git_repo_root` 改用 `git rev-parse --git-common-dir` — 关闭从 worktree 内调用 wrapper 时 nested target → "Filename too long" 链锁失败漏洞)拨入本 change scope;加 2 unit fence test 守门 regression
- **D-CrossArchiveADRSupersede**:archived ADR-011/012 evidence 不动(沿"归档即冻结");SRS ADR-011 + ADR-012 加 cross-reference 标 superseded by ADR-013(worktree mandatory parts)

**Outcome × Mode 状态机**(`forgeue_finish_gate.py::_check_worktree_consent_outcome` + `_check_worktree_mode_consistency` 守门):

| `worktree_consent_outcome` | `worktree_mode` | 路径 | use case |
|---|---|---|---|
| `declined` | `in_place`(强制) | main repo cwd(default)| implementation phase / lightweight change |
| `accepted` | `skill_worktree` | upstream Superpowers 自管 | 多 implementer 并行 / 大型 feature |
| `accepted` | `wrapper_worktree` | OPT-IN W1 wrapper + 13-field receipt | 强 audit + provenance |
| `already_isolated` | `skill_worktree` 或 `wrapper_worktree` | session 已 isolated;`worktree_path != main repo` | cross-session resume / sandbox auto-activate |
| `sandbox_fallback` | `in_place` | upstream skill sandbox fallback | sandbox 不允许 worktree creation |

**Cross-field invariants**:
- `declined ↔ in_place`
- `accepted → mode ∈ {skill_worktree, wrapper_worktree}`
- `already_isolated → mode ∈ {skill_worktree, wrapper_worktree}`(**禁** `in_place`;W6 codex round 2 F2)+ `worktree_path` 必写且 `realpath != main_repo_root`
- `mode: in_place` → 禁写 `worktree_path` / `worktree_receipt_path`
- `mode: skill_worktree` → 必写 `worktree_path`,禁写 `worktree_receipt_path`
- `mode: wrapper_worktree` → 必写 `worktree_path` + `worktree_receipt_path`

**legacy 兼容**:archived ADR-011/012 evidence 不含 `worktree_consent_outcome` 字段 → 全 fence pass-through(`_runtime_enforcement_active` False 模式 + 新 fence outcome 字段 absent 时直接 return [])。

**Sister skill `subagent-driven-discipline` v2.3 update**:加新 §3.5 Worktree Consent Policy 段(完整 outcome × mode 决策表 + invariant + use case dispatch heuristic);Pattern 2 §3.1 STRICT cwd verify rewrite 为 "when worktree IS used";Case 3 P0+P1 retrospect(13 inline fix;2 new failure mode "sister-file fence test sync drift" + "fence design intent docstring gap")+ §6 catalog 加 2 row。

**完整协议见**:archived `openspec/changes/archive/2026-05-06-restore-superpowers-worktree-consent-gate/`(design.md G11 / G12 / G13 + spec.md state machine 表 + 9 spec scenario 全覆盖)。

## codex stage hook(design.md §3 / §4 / forgeue_integrated_ai_workflow.md §B.4)

| stage | hook 命令 | 评审范围 | cross-check 要求 |
|---|---|---|---|
| **S2 design** | `/codex:adversarial-review`(默认 background;大 scope)| 文档级 | 强制 cross-check(`review/design_cross_check.md`)|
| **S3 plan** | `/codex:adversarial-review`(默认 background)| 文档级 | 强制 cross-check(`review/plan_cross_check.md`)|
| **S5 verification** | `/codex:review --base <main>`(默认 background;仅极小 scope 才 wait)| 代码级 | 单向挑错,**无** cross-check |
| **S6 adversarial** | `/codex:adversarial-review`(adversarial 永远 background)| mixed scope | blocker 独立验证;**无** cross-check |

**env-conditional + plugin-conditional 双重 enforce**:
- claude-code env + plugin available → REQUIRED
- claude-code env + plugin not available → OPTIONAL,evidence 标 `_unavailable_reason: codex_plugin_unavailable`
- non-claude-code env → OPTIONAL(由 agent 自决)

## State Machine S0-S9(design.md §3)

完整表见 `forgeue_integrated_ai_workflow.md` §B.1。关键横切硬约束:

- 没 active change → `/forgeue:change-{plan,apply-subagent,apply-direct,...}` abort
- proposal/design/tasks 不齐 → 不能进 S3
- 测试未跑 / 未解释 SKIP → 不能进 S6
- review blocker 未清 → 不能进 S7
- doc sync DRIFT → 不能进 S8
- **evidence 含 `aligned_with_contract: false` 且未标 drift → 不能进 S9**(中心化最后防线)

## 12-key frontmatter(design.md §3)

每份 evidence 必含 1 wrapper(`change_id`)+ 11 audit fields:

```yaml
---
change_id: <change-id>
stage: S<N>
evidence_type: <enum>
contract_refs: [path#anchor, ...]
aligned_with_contract: <bool>
drift_decision: null | pending | written-back-to-<artifact> | disputed-permanent-drift
writeback_commit: <sha> | null
drift_reason: <string> | null
reasoning_notes_anchor: <anchor> | null
detected_env: claude-code | codex-cli | cursor | aider | unknown
triggered_by: auto | cli-flag | env-var | setting | forced
codex_plugin_available: <bool> | null
---
```

## 4 类 named DRIFT(design.md §3)

`tools/forgeue_change_state.py --writeback-check` 检测,exit 5 阻断:

1. `evidence_introduces_decision_not_in_contract` — evidence 含 contract 未记录决策
2. `evidence_references_missing_anchor` — plan/micro_tasks 引用 `tasks.md#X.Y` 不存在
3. `evidence_contradicts_contract` — implementation log 与 design.md 接口字段不一致
4. `evidence_exposes_contract_gap` — debug log 揭示 design.md 异常段缺失

附加 frontmatter 校验由 `forgeue_finish_gate.py` exit 2 阻断(spec.md ADDED Requirement Scenario 2-3 protocol)。

## writeback 协议三态(design.md §3)

- `null` — 当前 evidence 无 drift
- `pending` — drift 已识别,未决定;阻断下一阶段
- `written-back-to-<artifact>` — drift 已通过修改 contract artifact 消化;`writeback_commit` 必有真实 sha;finish gate 用 `git rev-parse <sha>` + `git show --stat <sha>` 二次校验
- `disputed-permanent-drift` — 经评估永久不回写;必有 ≥ 50 字 `drift_reason` + `reasoning_notes_anchor` 指向 design.md `## Reasoning Notes` 段实际存在的 anchor

## cross-check A/B/C/D 模板(design.md §3 Cross-check Protocol)

`design_cross_check.md` / `plan_cross_check.md` 必含:

- `## A. Decision Summary` — 冻结于 codex 调用之前;Claude **不**得在写 ## B/C/D 时回填 ## A
- `## B. Cross-check Matrix` — 逐条 codex finding + Resolution
- `## C. Disputed Items Pending Resolution` — `disputed_open: <count>`;> 0 阻断
- `## D. Verification Note` — 独立验证 file:line(沿 `feedback_verify_external_reviews`)

frontmatter 必含:`disputed_open: <int>` / `codex_review_ref: <path>` / `created_at` / `resolved_at`。

**Resolution 6 取值**:`aligned` / `accepted-codex` / `accepted-claude`(reason ≥ 20 字)/ `disputed-blocker`(临时态)/ `disputed-pending`(必含在 ## C)/ `disputed-permanent-drift`(reason ≥ 50 字 + Reasoning Notes anchor)。

**不走 cross-check**(carve-out):S5 verification single-direction review;S6 adversarial mixed scope review。

## 命令边界(design.md §11.1)

- **OpenSpec 默认命令**(强调 contract 中心地位,**不**包 facade):`/opsx:new` / `/opsx:propose` / `/opsx:archive` 等
- **ForgeUE 命令**(`/forgeue:change-*`,8 个):编排 S2-S8 实施 / cross-review / Sync Gate / Finish Gate;**不**做 contract create/archive

## 反模式 fence(design.md §6)

- **不**创建 `.claude/skills/forgeue-superpowers-tdd-execution/`(重复 Superpowers `test-driven-development`;P4 fence `test_forgeue_no_duplicated_tdd_skill.py` 守门)
- **不**新增 `.codex/skills/forgeue-*-review/`(走 codex-plugin-cc `/codex:*`;P4 fence `test_forgeue_codex_review_no_skill_files.py` 守门)

## 禁用项(design.md §4)

- `/codex:rescue` 在 ForgeUE workflow 内(违 review-only 原则;Pre-P0 是本 fusion change 一次性附录例外,未来其他 change 不豁免;markdown lint fence 守门)
- `/codex:setup --enable-review-gate`(plugin 自警告 long loop;`forgeue_finish_gate.py` 检查 `~/.claude/settings.json` 含 review-gate hook → WARN)

## ASCII 标记(design.md §5 / ForgeUE memory `feedback_ascii_only_in_adhoc_scripts`)

stdout / evidence markdown:用 7 种 ASCII 标记 `[OK]` / `[FAIL]` / `[SKIP]` / `[WARN]` / `[DRIFT]` / `[REQUIRED]` / `[OPTIONAL]`;**不**用 emoji(Windows GBK stdout / fence 测试 / lint 都会出问题)。

## Input / Output

**Input**: skill 自身不直接被用户调用;由 `/forgeue:change-*` command 引用作 backbone。

**Output**: skill 提供共享 mental model;实际 evidence 文件由各 command 写入,frontmatter 12-key + 协议遵循本 skill 的描述。

## Guardrails

- **必绑 active change**(所有引用本 skill 的 command 共享此约束)。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(全局禁令)。
- **不引入 paid provider / live UE / live ComfyUI 默认调用**(env guard 严格;Level 1/2 opt-in)。
- **不让 evidence 成新规范源**(中心化协议物理表达)。
- **不重复造轮子**:Superpowers 已有的 skill 不再做同名 ForgeUE skill。
- **数字以实测为准**:`pytest` 总数等不硬编码,以 `python -m pytest -q` 实际输出为准。

## References

- `openspec/changes/fuse-openspec-superpowers-workflow/design.md` §1-§11 + Reasoning Notes(权威源)
- `openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md`(ADDED Requirement + 3 Scenarios + Validation + Non-Goals)
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(user-facing 详表 + 阅读引导)
- `docs/ai_workflow/README.md` §4(Documentation Sync Gate 主规则)
- ForgeUE memory:`feedback_verify_external_reviews` / `feedback_no_silent_retry_on_billable_api` / `feedback_decisive_approval` / `feedback_ascii_only_in_adhoc_scripts`
