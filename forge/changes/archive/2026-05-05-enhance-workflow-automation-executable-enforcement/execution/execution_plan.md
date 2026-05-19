---
change_id: enhance-workflow-automation-executable-enforcement
stage: S2
evidence_type: execution_plan
contract_refs:
  - tasks.md#Pre-P0
  - tasks.md#P0
  - tasks.md#P1
  - tasks.md#P2
  - tasks.md#P3
  - tasks.md#P4
  - tasks.md#P5
  - tasks.md#P6
  - tasks.md#P7
  - tasks.md#P8
  - tasks.md#P9
  - tasks.md#P10
  - tasks.md#P11
  - tasks.md#P12
  - design.md#decisions
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v1
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-05T13:30:00+08:00
created_at: 2026-05-05T13:35:00+08:00
---

# Execution Plan — enhance-workflow-automation-executable-enforcement

> **For agentic workers**:本 plan 沿 ForgeUE Integrated AI Change Workflow S3→S4-S5 阶段执行。
> 推荐路径:`/forgeue:change-apply-subagent`(本 change 默认 sequential — W1 wrapper 还没 ship 无法用 W2 actual diff 安全 parallel)。
> 不推荐 `/forgeue:change-apply-parallel`(违反 D-DogfoodGap 立场,且 W2 协议未实施;沿本 change Pre-P0 sequential 模式)。
> 不推荐 `/forgeue:change-apply-direct`(P0/P1/P2 各 ≥ 5 sub-task,超过 < 3 micro-task direct 适用边界)。

**Goal**:把刚 ship `enhance-workflow-automation-runtime-enforcement` 的 markdown advisory enforcement(F1 worktree preflight / F2 parallel disjoint / F3 round 2 continuity)升级为可执行 deterministic enforcement layer:W1 preflight wrapper + receipt JSON / W2 主 session actual diff overlap detection + 自动降级 sequential / W3 dispatch ledger append-only + LLM context isolation + finish_gate cross-check。引入 protocol_version v2,v1 evidence 完全兼容,archived enhance-workflow-automation-runtime-enforcement evidence(v1)replay 不 false-block。

**Architecture**:三层防伪造 — (1) wrapper-only write(receipt + ledger 不让 LLM 直接 echo)/ (2) LLM context isolation(命令模板不暴露 ledger path 给 Read/Write/Edit tool)/ (3) fence cross-check(receipt JSON ≡ evidence frontmatter,ledger ⊇ evidence 声明的 agent_id 集合);失败时 fail-closed。

**Tech Stack**:Python 3.12+ stdlib(argparse / json / pathlib / subprocess / hashlib / datetime);git CLI(diff / status / rev-parse);ForgeUE 既有 `tools/forgeue_*.py` 工具集风格;OpenSpec change artifact + `openspec validate --strict`;pytest 单元测试矩阵(沿 archived runtime-enforcement P0/P1 同款 fence test 模式)。

---

## File Structure

| 路径 | 类型 | 责任 |
|---|---|---|
| `tools/forgeue_preflight_wrapper.py` | 新建 | W1 preflight wrapper:**自管 isolated worktree**(`git worktree add/list` subprocess + cwd realpath 强制校验,沿 F1 round 1 inline writeback)+ 内嵌 cascade check + 写 13 字段 receipt JSON(含 `is_isolated_worktree` + `worktree_action`)到 `<change>/preflight_receipts/<id>.json` |
| `tools/forgeue_dispatch_ledger.py` | 新建 | W3 dispatch ledger:`append` / `verify` 子命令;append-only JSONL 到 `<change>/dispatch_ledger.jsonl` |
| `tools/forgeue_finish_gate.py` | 修改 | 加 protocol_version v2 dispatch + 升级 `_check_worktree_path` v2(receipt cross-check)+ 升级 `_check_round_fix_continuity` v2(ledger cross-check)+ 新 `_check_file_overlap_actual`(W2)+ 新 `_check_dispatch_ledger`(W3) |
| `tests/unit/test_preflight_wrapper.py` | 新建 | W1 fence **18 个测试**(F2 round 2 inline:7 base + 6 失败路径含 wrong-cwd / dirty / unknown-skill / cascade fail / git not repo / receipt dir not writable + 3 reuse + 2 CLI smoke) |
| `tests/unit/test_dispatch_ledger.py` | 新建 | W3 fence 12 个测试 |
| `tests/unit/test_forgeue_finish_gate.py` | 修改 | 加 v2 fence 12 个 + protocol_version dispatch 4 个测试 |
| `.claude/commands/forgeue/change-apply-subagent.md` | 修改 | Preflight Worktree 段升级为 wrapper invocation;每 Skill(Task) 前插 ledger append step;evidence frontmatter 模板 protocol_version: v2 |
| `.claude/commands/forgeue/change-apply-parallel.md` | 修改 | 同 subagent + dispatch 后 W2 actual diff 收集 + 自动降级 sequential |
| `.claude/commands/forgeue/change-apply-direct.md` | 不动 | 沿 D-DirectWorktreeRefinement |
| `tests/unit/test_forgeue_command_markdown.py` | 修改 | 加 v2 命令模板 6 fence(wrapper invoke + ledger append + actual diff + protocol v2) |
| `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` | 修改 | 加 "Runtime Enforcement Protocol v2" 段(沿 P5 doc sync) |
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md` | 修改 | §C.8 加 "Executable Enforcement Layer v2" |
| `docs/ai_workflow/README.md` | 修改 | §4.4-ter 加 "Executable Enforcement v2" |
| `docs/ai_workflow/forgeue_quickstart.md` | 修改 | S3→S4-S5 stage 加 wrapper 协议摘要 |
| `CLAUDE.md` | 修改 | 工具清单 7→9;runtime enforcement frontmatter 字段段加 v2 |
| `README.md` | 修改 | ForgeUE Workflow 表 7→9 工具;ADR-012 摘要 |
| `AGENTS.md` | 修改 | 加 4 条 v2 enforcement 摘要 |
| `CHANGELOG.md` | 修改 | [Unreleased] 加本 change entry |
| `docs/requirements/SRS.md` | 修改 | 加 ADR-012 行 |
| `docs/acceptance/acceptance_report.md` | 修改 | 加 ADR-012 status 行 |
| `docs/design/HLD.md` | 修改 | workflow tooling 段加 W1/W3 wrapper |
| `openspec/specs/examples-and-acceptance/spec.md` | archive 时 auto-merge | sync 4 ADDED + 3 MODIFIED Requirement |

---

## Phase Map(对应 tasks.md 锚点;F4 round 2 inline writeback 后:14 phase 独立 row,P5.5 显式 + P0 18 fence)

| Phase | tasks.md 锚点 | scope | 依赖 | 说明 |
|---|---|---|---|---|
| Pre-P0 | [Pre-P0](../tasks.md#pre-p0self-host-bootstrap沿-d-selfhost-模式本-change-实施期间-sequential-dispatch因为-w1-wrapper-还没-ship无法用-w2-actual-overlap-安全-parallel) | codex round 1 design challenge + writeback(F1+F4+F5 inline / F2+F3 deferred follow-on)+ codex round 2 plan challenge + writeback(全 4 inline) | 已 4 制品 valid | 本会话已完成 |
| P0 | [P0](../tasks.md#p0--toolsforgeue_preflight_wrapperpy-新建--测试-fencew1) | W1 wrapper(自管 worktree)+ **18 fence test**(F2 round 2 inline:18 含 4 negative;原 14 stale) | Pre-P0 closed | 见 micro_tasks.md §P0 |
| P1 | [P1](../tasks.md#p1--toolsforgeue_dispatch_ledgerpy-新建--测试-fencew3) | W3 ledger + 12 fence test | P0 done | 见 micro_tasks.md §P1 |
| P2 | [P2](../tasks.md#p2--forgeue_finish_gatepy-升级-4-fence--协议-v2-dispatch--测试) | finish_gate 4 fence v2 + protocol dispatch + 16 fence test | P0 + P1 done(读 receipt + ledger) | 见 micro_tasks.md §P2 |
| P3 | [P3](../tasks.md#p3--forgeuechange-apply-subagentparallel-命令模板加-wrapper-invocation-step) | 命令模板 wrapper invocation(P3.2)+ post-dispatch ledger capture(P3.2/P3.3,F1 round 2 inline)+ actual diff git status --porcelain + ls-files --others 合集(P3.3,F3 round 2 inline)+ 6 fence test | P0 + P1 + P2 done | 见 micro_tasks.md §P3 |
| P4 | [P4](../tasks.md#p4--backbone-skill-skillmd-同步-w1w2w3-wrapper-invocation-协议) | backbone SKILL.md 同步 | P3 done(命令模板已升级) | 见 micro_tasks.md §P4 |
| P5 | [P5](../tasks.md#p5--11-处文档同步沿-enhance-workflow-automation-runtime-enforcement-p4-模式) | 11 处文档同步 + ADR-012 | P0-P4 done | 见 micro_tasks.md §P5 |
| **P5.5** | [P5.5](../tasks.md#p55--v2-e2e-integration-test-fixturef5-round-1-codex-inline-writeback;archive-前必过-gate) | **v2 e2e integration test fixture**(`tests/integration/test_v2_e2e_synthetic_change.py`)— W1 + W2 + W3 + finish_gate full 6 fence + overlap 负例 + dirty 负例 + v1/legacy 回归;**archive 必过 gate(P10.0 二次确认)** | P0 + P1 + P2 + P3 + P4 + P5 done | 见 micro_tasks.md §P5.5(F4 round 2 inline writeback:F5 round 1 加的 gate phase 独立 owner) |
| P6 | [P6](../tasks.md#p6--verify) | verify L0 + L1 + verify_report.md | **P0-P5.5 done**(F4 round 2 inline:P6 依赖加 P5.5) | 沿 archived runtime-enforcement P5 |
| P7 | [P7](../tasks.md#p7--codex-s6-mixed-scope-review) | codex mixed-scope review + 6 reference stub | P6 done | 沿 archived P6 |
| P8 | [P8](../tasks.md#p8--跳过-superpowers-requesting-code-review沿-enhance-workflow-automation-runtime-enforcement-同款cover-by-pre-p0-round-1--p7-mixed-scope) | superpowers review SKIP rationale stub | P7 done | 沿 archived P7 |
| P9 | [P9](../tasks.md#p9--documentation-sync-gate) | doc_sync_report.md | P0-P8 done | 沿 archived P8 |
| P10 | [P10](../tasks.md#p10--finish-gate) | **P10.0 v2 e2e gate 二次确认 + finish_gate_report.md**(P10.0 archive 阻断与 P5.5 phase owner 互补) | P0-P9 done | 沿 archived P9 + 加 P10.0 |
| P11 | [P11](../tasks.md#p11--archive用户授权fence-1-不可逆) | archive(用户授权 fence #1) | P10 done | 沿 archived P10 |
| P12 | [P12](../tasks.md#p12--后置可选--follow-on-tracking) | MEMORY.md update + follow-on tracking(含 `enhance-workflow-automation-ledger-binding` for F2+F3 deferred) | P11 done | 沿 archived P11 |

---

## Test-Driven Development 节奏(每 micro task 子步骤)

每个 P0/P1/P2 fence test 加新工具 / 新逻辑 micro task 必跑:

1. 写 failing test(`pytest <test> -v` → FAIL)
2. 写最小实现 → `pytest <test> -v` PASS
3. 跑全套 regress(`pytest -q`)→ 全绿无回归
4. commit(`git add <files> && git commit -m "<phase>(executable-enforcement): <subject>"`)

P3/P4/P5 命令模板 / SKILL.md / docs 修改沿 markdown lint fence pattern(`tests/unit/test_forgeue_command_markdown.py` / `tests/unit/test_codex_command_markdown.py`):每命令 / SKILL 增删 → fence test 同步加 keyword check。

---

## Self-Host Bootstrap 限制(D-DogfoodGap)

**本 change 实施时**:
- W1 wrapper 还没 ship → 命令模板**不能**用 wrapper invocation;沿 v1 advisory `Skill(superpowers:using-git-worktrees)` 直接 invoke
- W3 ledger 还没 ship → 命令模板**不能**写 ledger;evidence frontmatter 不含 `dispatch_ledger_path` / `worktree_receipt_path` 字段
- 本 change evidence 全部 `runtime_enforcement_protocol_version: v1`(沿 archived runtime-enforcement P9.4 self-host bootstrap 模式)
- finish_gate v2 fence 在本 change 自身 evidence 上 pass-through(无 v2 字段 → fence skip)
- 第一个真 dogfood W1/W2/W3 是**下一个**任意 follow-on change(本 change archive 后)

**实施期间 dispatch 模式**:沿 archived runtime-enforcement Pre-P0 + P0-P9 同款 sequential — `/forgeue:change-apply-subagent` 默认路径,**不**用 parallel(W2 协议未 ship)。

---

## Key Risks(沿 design.md §"Risks / Trade-offs")

- **R1 W1 wrapper 路径漂移**(receipt vs evidence frontmatter)→ wrapper 内部 normalize 路径 + fence 比较 normalize 后字符串(P0.2 + P2.3 守门)
- **R2 W2 overlap 漏检**(`git diff` 不覆盖 untracked file)→ OQ-2 倾向用 `git status --short` 替代,P3.3 实装(待 codex round 1 verdict 确认)
- **R3 W3 ledger LLM 篡改**(echo > 重写)→ fence `_check_dispatch_ledger` 校验 timestamp 单调性 + wrapper_version + 行数 ≥ evidence(P2.6)
- **R4 v1/v2 fence 矩阵复杂**→ fence 入口统一 dispatch on `runtime_enforcement_protocol_version`(P2.2 + 测试矩阵 P2.9)
- **R5 W2 自动降级损失 implementer wall-clock**→ 接受;evidence 记录 overlap files 后 sequential 实施时可参考 hint(non-binding)
- **R6 wrapper Python 启动开销**→ 接受(N × ~200ms,相对 implementer wall-clock 忽略不计)
- **R7 自身 dogfood gap**→ proposal/design/execution_plan 显式标注;archive 后第一个 follow-on change 真 dogfood 闭环

---

## References

- 契约真源:`proposal.md` / `design.md` / `specs/examples-and-acceptance/spec.md` / `tasks.md`
- 父 change archive:`openspec/changes/archive/2026-05-05-enhance-workflow-automation-runtime-enforcement/`(F1/F2/F3 deferred 出处)
- 前 change archive:`openspec/changes/archive/2026-05-04-adopt-subagent-driven-development/`(D-Worktree-Detail 第 5 项 = 本 change D-DogfoodGap 关联决策)
- 工具集风格:`tools/forgeue_skill_cascade_check.py`(P0.1 read 参考)+ `tools/forgeue_finish_gate.py`(P2.1 read 参考)
- 测试矩阵:`tests/unit/test_skill_cascade_check.py`(P0.3 fence 模板)+ `tests/unit/test_forgeue_finish_gate.py`(P2.8/P2.9 fence 模板)
- ForgeUE auto memory:`feedback_autonomy_boundary_simplified.md`(默认自主)+ `feedback_no_continue_prompts_between_phases.md`(连续推 phase 不 prompt)+ `project_runtime_enforcement_change.md`(父 change ship 摘要)
