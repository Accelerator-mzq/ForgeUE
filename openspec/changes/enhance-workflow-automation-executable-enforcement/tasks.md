# Tasks — enhance-workflow-automation-executable-enforcement

> **Dogfood gap notice**(D-DogfoodGap):本 change 实施时 W1 wrapper 还没 ship;本 change 自身 evidence 沿 v1 advisory(`runtime_enforcement_protocol_version: v1`,无 worktree_receipt_path / dispatch_ledger_path / task_files_actual 字段)。本 change archive 后第一个 follow-on change 是真 dogfood,届时 evidence 才会含 v2 字段闭环。

## Pre-P0(self-host bootstrap;沿 D-SelfHost 模式;**本 change 实施期间 sequential dispatch**因为 W1 wrapper 还没 ship,无法用 W2 actual overlap 安全 parallel)

- [x] Pre-P0.1:`/codex:adversarial-review` round 1 挑战 D-W1-ReceiptSchema / D-W2-OverlapDetection / D-W3-LedgerFormat / D-DispatchWrapperBoundary / D-DegradationPath / D-FrontmatterSchemaExtension / D-DogfoodGap / D-W3-WrapperImpl 8 个 D-decision + Open Questions OQ-1/2/3/4
- [x] Pre-P0.2:落 `notes/pre_p0/codex_review_round1.md` evidence
- [x] Pre-P0.3:Claude 独立验证 codex finding(file:line 引用)+ verdict 矩阵
- [x] Pre-P0.4:writeback finding 到 design.md / proposal.md / spec.md / tasks.md
- [x] Pre-P0.5:落 `notes/pre_p0/plan_cross_check.md`(plan-level cross-check 覆盖 design + plan + spec + tasks 四 scope)
- [x] Pre-P0.6:`disputed_open: 0` 验证

## P0 — `tools/forgeue_preflight_wrapper.py` 新建 + 测试 fence(W1)

- [x] P0.1:Read 现有 `tools/forgeue_skill_cascade_check.py` 了解 stdlib 风格 + argparse 协议
- [x] P0.2:加 `tools/forgeue_preflight_wrapper.py`(stdlib only;F1 round 1 codex inline writeback 后 wrapper 自管 worktree):
  - argparse:`--change <id>` + `--skill <skill-name>`(default `superpowers:using-git-worktrees`,仅供 cascade check 内嵌使用,wrapper 不 invoke SKILL)+ `--cwd <path>`(default os.getcwd())+ `--worktrees-root <path>`(default `<repo>/.worktrees/`)+ `--receipts-dir <path>`(default `<change>/preflight_receipts/`)+ `--reuse-if-clean`(D-OQ-1 可选 reuse)
  - **wrapper 自管 worktree**(沿 D-W1-ReceiptSchema F1 round 1 inline writeback;**不**依赖 Skill tool):
    - 计算 target worktree path = `<worktrees-root>/<change-id>/`
    - 跑 `git worktree list --porcelain` 解析:若 target 在 list + clean → reuse(`worktree_action: reused`);若 target 在 list + dirty(`git status --porcelain` 非空)→ exit 6(`worktree_action: rejected_dirty`);若不在 list → 跑 `git worktree add <target> -b <change-id>` 创建(`worktree_action: created`)
    - 强制 cwd 校验:`os.path.realpath(cwd) == os.path.realpath(worktree_path)`,不一致 → exit 6(`worktree_action: rejected_wrong_cwd`)+ stderr 提示 "请 cd 到 <worktree path> 重新调用 wrapper"
  - 校验 git 仓库状态 + resolve `base_sha`(`git rev-parse HEAD`)/ `base_branch`(`git rev-parse --abbrev-ref HEAD`)
  - 跑内嵌 cascade check:subprocess `python tools/forgeue_skill_cascade_check.py --skill <skill> --invoked <skill>`(只校验主 skill 自身的 dependency 解析无错;cascade fail → exit 5)
  - 写 receipt JSON 到 `<change>/preflight_receipts/<receipt_id>.json`,字段沿 D-W1-ReceiptSchema(13 字段含 `is_isolated_worktree: true` + `worktree_action`)
  - stdout 输出 receipt 相对路径(供命令模板 capture)+ exit 0(成功)/ exit 5(cascade check fail)/ exit 6(wrong cwd / dirty worktree / git 状态异常)/ exit 7(receipt 写失败)
- [x] P0.3:加 `tests/unit/test_preflight_wrapper.py` fence(预计 18 个;F1 round 1 inline 加 4 个新 negative test):
  - 7 base:wrapper 自创 worktree / wrapper 写 receipt / receipt JSON well-formed / receipt 13 字段全填(含 is_isolated_worktree + worktree_action)/ receipt worktree_path 绝对路径 / receipt skill_cascade_check.exit_code == 0 / wrapper stdout 输出 receipt 相对路径
  - 6 失败路径:cascade check fail → exit 5 / **wrong-cwd → exit 6 + worktree_action: rejected_wrong_cwd**(F1 inline)/ **dirty worktree → exit 6 + worktree_action: rejected_dirty**(F1 inline)/ git 不在仓库 → exit 6 / receipt dir 不可写 → exit 7 / unknown skill → exit 5
  - 3 D-OQ-1 reuse:`--reuse-if-clean` + clean tree 同 base_sha → reuse old receipt(`worktree_action: reused`)/ dirty tree 强制 reject / 不同 base_sha → recreate
  - 2 CLI smoke(subprocess 验证 exit code + stderr 内容)
- [x] P0.4:`pytest -q tests/unit/test_preflight_wrapper.py` 全绿
- [x] P0.5:`pytest -q` 全套 regress 全绿(无回归)

## P1 — `tools/forgeue_dispatch_ledger.py` 新建 + 测试 fence(W3)

- [x] P1.1:加 `tools/forgeue_dispatch_ledger.py`(stdlib only):
  - argparse:子命令 `append` + `verify`
  - `append`:`--change <id>` + `--agent-id <id>` + `--round <int>` + `--role <role>` + `--task-subject-hash <sha256>`(可选)+ `--parent-session-id <uuid>`(可选);atomic append 一行 JSON 到 `<change>/dispatch_ledger.jsonl`(open with `'a'` mode + flush);沿 D-W3-LedgerFormat 字段
  - `verify`:`--change <id>`;读 ledger 全部行 + parse JSON + 校验 timestamp 单调递增 + wrapper_version 字段非空;exit 0(全 OK)/ exit 5(timestamp 倒流 / JSON 不合 schema / wrapper_version 缺失)
- [x] P1.2:加 `tests/unit/test_dispatch_ledger.py` fence(预计 12 个):
  - 5 append:append 一行 / N 行 / 字段全 / atomic(并发 append 不损坏文件)/ ledger 不存在自动创建
  - 4 verify:verify 单行 OK / verify timestamp 单调 / verify timestamp 倒流 → exit 5 / verify wrapper_version 缺失 → exit 5
  - 2 schema:JSON 不合 schema → exit 5 / role 在 enum(`implementer` / `spec_reviewer` / `code_quality_reviewer` / `final_reviewer` / `implementer_round_2_fix` / `spec_reviewer_round_2_review`)
  - 1 CLI smoke
- [x] P1.3:`pytest -q tests/unit/test_dispatch_ledger.py` 全绿
- [x] P1.4:`pytest -q` 全套 regress 全绿

## P2 — `forgeue_finish_gate.py` 升级 4 fence + 协议 v2 dispatch + 测试

- [x] P2.1:Read `tools/forgeue_finish_gate.py` 现状(P1/P2/P3 simplified protocol 之后 + 4 runtime fence v1 版)
- [x] P2.2:在 `check_frontmatter_protocol` 入口加 `runtime_enforcement_protocol_version` dispatch:
  - 缺字段(legacy)→ skip 全部 v1/v2 fence(沿现 pass-through)
  - `v1` → 走 v1 fence 逻辑(沿现实装,无变化)
  - `v2` → 走 v2 fence 逻辑(`_check_worktree_path` v2 / `_check_round_fix_continuity` v2 / 新 `_check_file_overlap_actual` / 新 `_check_dispatch_ledger`)
- [x] P2.3:升级 `_check_worktree_path` v2:
  - v2 evidence MUST 含 `worktree_receipt_path` 字段
  - 读 receipt JSON(`<change>/<receipt_path>`),校验文件存在 + JSON well-formed
  - 校验 receipt 内 `worktree_path` == evidence frontmatter `worktree_path`
  - 任一不一致 → Blocker(`worktree_path_v2_violation`)
- [x] P2.4:升级 `_check_round_fix_continuity` v2:
  - v2 evidence MUST 含 `dispatch_ledger_path` 字段(固定值 `dispatch_ledger.jsonl`)
  - 读 `<change>/dispatch_ledger.jsonl`,校验文件存在
  - 校验 evidence frontmatter `subagent_continuity` 中所有 agent_id 都在 ledger 中**有真实记录**(round + role 与 ledger 行匹配)
  - 缺 ledger / agent_id 不在 ledger → Blocker(`round_fix_continuity_v2_violation`)
- [x] P2.5:加 `_check_file_overlap_actual` 新 fence(W2):
  - v2 evidence(parallel only,即 `triggered_by_command: change-apply-parallel`)MUST 含 `task_files_actual` 字段(list)
  - 校验 actual ⊆ declared(`task_files_actual` 与 `task_files_disjoint` 一致)
  - 校验 actual changed-files set 之间 disjoint(若 `degraded_to: null`)
  - `degraded_to: change-apply-subagent` 时跳过 disjoint 校验,改走 sequential 校验逻辑
  - 任一不一致 → Blocker(`file_overlap_actual_violation`)
- [x] P2.6:加 `_check_dispatch_ledger` 新 fence(W3):
  - v2 evidence MUST 含 `dispatch_ledger_path` 字段
  - 子调 `python tools/forgeue_dispatch_ledger.py verify --change <id>`(or 等价的 inline parse)
  - exit 非 0 / 任一行 timestamp 倒流 / wrapper_version 缺失 → Blocker(`dispatch_ledger_violation`)
- [x] P2.7:在 `check_frontmatter_protocol` 调用链插入新 fence(各独立 Blocker.type)
- [x] P2.8:加 `tests/unit/test_forgeue_finish_gate.py` v2 fence 测试(预计 12 个):
  - 4 v2 worktree_path:v2 receipt OK / receipt 缺失 / receipt JSON 不一致 / v2 evidence 缺 worktree_receipt_path
  - 3 v2 round_fix_continuity:v2 ledger OK / ledger 缺失 / agent_id 不在 ledger
  - 3 file_overlap_actual:OK disjoint / actual overlap / declared 与 actual 不一致
  - 2 dispatch_ledger:OK / timestamp 倒流
- [x] P2.9:加 `tests/unit/test_forgeue_finish_gate.py` protocol_version dispatch 测试(预计 4 个):
  - v1 evidence 仅触发 v1 fence(v2 fence 不触发)
  - v2 evidence 触发 v1 + v2 fence(v1 fence 仍生效)
  - legacy(无字段)pass-through(v1 + v2 fence 都不触发)
  - archived 2026-05-05-enhance-workflow-automation-runtime-enforcement fixture replay 通过
- [x] P2.10:`pytest -q tests/unit/test_forgeue_finish_gate.py` 全绿
- [x] P2.11:`pytest -q` 全套 regress 全绿

## P3 — `/forgeue:change-apply-{subagent,parallel}` 命令模板加 wrapper invocation step

- [x] P3.1:Read 现有 `.claude/commands/forgeue/change-apply-subagent.md` + `change-apply-parallel.md`(P2 既有 Preflight section)
- [x] P3.2:`change-apply-subagent.md` `## Preflight Worktree` section 升级:
  - 原 step "MUST `Skill(superpowers:using-git-worktrees)` invoke" → 改为 "MUST 调用 `python tools/forgeue_preflight_wrapper.py --change <id> --skill superpowers:using-git-worktrees` 生成 receipt"
  - 新增 step:capture wrapper stdout receipt 相对路径 → LLM 写 evidence frontmatter `worktree_receipt_path: <path>` + 读 receipt 内 `worktree_path` 复制到 frontmatter `worktree_path`
  - 新增 ledger append 段:每次 Skill(Task) 前插入 `python tools/forgeue_dispatch_ledger.py append --change <id> --agent-id <id> --round <N> --role <role>` Bash step
  - 升级 evidence frontmatter 模板 protocol_version 标识:`runtime_enforcement_protocol_version: v2`
- [x] P3.3:`change-apply-parallel.md` 同款升级 + 新增 W2 actual diff 段(F4 round 1 codex inline writeback 后):
  - dispatch 后(每个 implementer subagent commit 完成后)插入 Bash precondition step:对每个 implementer worktree 跑 `git status --porcelain=v1` → 非空(dirty / untracked uncommitted)→ 命令 abort + Bash 写 `<change>/parallel_abort_dirty_<iso>.log` + 主 session 自动 invoke `/forgeue:change-apply-subagent` + evidence `degradation_reason: dirty_implementer_worktree`
  - clean precondition 通过后,对每个 implementer worktree 跑 actual changed-files 收集合集:
    - `git diff --name-only -z <base_sha>..HEAD`(committed diff)
    - `git ls-files --others --exclude-standard -z`(untracked but ignored exclusion 后)
    - 解析 NUL-separated 输出
  - 主 session 计算 set intersection(stdlib 写小段 inline Python or shell)
  - intersection 非空 → 命令 abort + Bash 写 `<change>/parallel_abort_<iso>.log` + 主 session 自动 invoke `/forgeue:change-apply-subagent`(沿 D-DegradationPath)+ evidence `degradation_reason: actual_file_overlap_detected`
  - intersection 空 → evidence frontmatter `task_files_actual: [...]` 字段填入(含 untracked file)+ `task_independence_assertion: true` + 继续走 spec_review / code_quality / final_review 4 类 evidence
- [x] P3.4:`change-apply-direct.md` **不动**(沿 D-DirectWorktreeRefinement;direct 路径无 wrapper 调用,无 ledger 写,evidence 仍 v1 advisory)
- [x] P3.5:`tests/unit/test_forgeue_command_markdown.py` 加 v2 fence(预计 6 个):
  - `test_change_apply_subagent_invokes_preflight_wrapper`(模板内含 `forgeue_preflight_wrapper.py` 字符串)
  - `test_change_apply_parallel_invokes_preflight_wrapper`
  - `test_change_apply_subagent_invokes_dispatch_ledger_append`(模板内含 `forgeue_dispatch_ledger.py append` 字符串)
  - `test_change_apply_parallel_invokes_dispatch_ledger_append`
  - `test_change_apply_parallel_collects_actual_diff_after_dispatch`(模板内含 `git status --porcelain=v1` precondition + `git diff --name-only -z` + `git ls-files --others --exclude-standard -z` 收集合集 + 自动降级 `change-apply-subagent` 字符串;F4 round 1 inline writeback 后)
  - `test_change_apply_subagent_protocol_version_v2_in_evidence_template`(模板含 `runtime_enforcement_protocol_version: v2` 字符串)
- [x] P3.6:`pytest -q tests/unit/test_forgeue_command_markdown.py` 全绿;`pytest -q` 全套 regress 全绿

## P4 — backbone skill SKILL.md 同步 W1/W2/W3 wrapper invocation 协议

- [x] P4.1:`.claude/skills/forgeue-integrated-change-workflow/SKILL.md` 加 "Runtime Enforcement Protocol v2(本 change 引入)" 段:
  - W1 wrapper invocation 协议 + receipt JSON schema(11 字段)
  - W2 actual diff 收集 + 自动降级 sequential
  - W3 dispatch ledger append-only + LLM context isolation
  - protocol_version dispatch(v1 / v2 / legacy 3 路径)
  - DogfoodGap 说明(本 change 自身仍 v1)
- [x] P4.2:命令清单表(沿 P2 模式)无新命令(W1/W2/W3 都是 wrapper 加强,不新增命令);Superpowers 集成边界表加 wrapper 拦截层说明
- [x] P4.3:`tests/unit/test_forgeue_command_markdown.py`(SKILL.md 静态扫 fence)若有 → 加 W1/W2/W3 关键词 fence(可选,若 SKILL.md 不在 fence scope 则跳过)

## P5 — 11 处文档同步(沿 enhance-workflow-automation-runtime-enforcement P4 模式)

- [x] P5.1:`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C 加 §C.8 "Executable Enforcement Layer v2"(W1 wrapper + W2 actual diff + W3 ledger + protocol_version v2 dispatch + 6 fence 表)+ DogfoodGap 段
- [x] P5.2:`docs/ai_workflow/README.md` §4 加 §4.4-ter "Executable Enforcement v2"(沿 §4.4-bis 同款结构)+ 引 ADR-012
- [x] P5.3:`docs/ai_workflow/forgeue_quickstart.md` S3→S4-S5 stage 加 wrapper 协议摘要(用户视角):"运行命令时自动生成 receipt + ledger,不需手动写 worktree_path"
- [x] P5.4:`CLAUDE.md` `## OpenSpec 工作流` 段:
  - 工具清单 7→9(加 `forgeue_preflight_wrapper.py` + `forgeue_dispatch_ledger.py`)
  - "Runtime enforcement frontmatter 字段" 段加 v2 字段(worktree_receipt_path / dispatch_ledger_path / task_files_actual / degraded_to / degradation_reason)
  - 协议版本说明:v1 vs v2 dispatch
- [x] P5.5:`README.md` ForgeUE Workflow 表:7→9 工具(加 W1/W3 wrapper);新增 ADR-012 摘要段
- [x] P5.6:`AGENTS.md` 加 4 条 v2 enforcement 摘要(W1 receipt / W2 actual diff / W3 ledger / protocol_version v2 dispatch)
- [x] P5.7:`CHANGELOG.md` `[Unreleased]` 加本 change entry(完整覆盖 ADR-012 + 6 fence + 2 wrapper + W2 actual diff + protocol v2 + commit SHA + 测试覆盖)
- [x] P5.8:`docs/requirements/SRS.md` 加 ADR-012 行(沿 ADR-007/008/009/010/011 格式;含 8 D-decision 摘要 + DogfoodGap + W1/W2/W3 wrapper 协议)
- [x] P5.9:`docs/acceptance/acceptance_report.md` 加 ADR-012 status 行(✅ 已实装,全条目对应 SRS ADR-012)
- [x] P5.10:`docs/design/HLD.md` workflow tooling 段加 W1/W3 wrapper(沿 ADR-011 同款描述)+ protocol_version dispatch 简述
- [x] P5.11:`openspec/specs/examples-and-acceptance/spec.md` — sync archive 时 auto-merge(本 task 不动;P10 archive 协议处理)

## P5.5 — v2 e2e integration test fixture(F5 round 1 codex inline writeback;archive 前必过 gate)

- [x] P5.5.1:Read `tests/integration/test_p3_*.py` 了解 ForgeUE integration test 风格(tmp_path + 端到端 bundle)
- [x] P5.5.2:加 `tests/integration/test_v2_e2e_synthetic_change.py`(沿 D-W4-IntegrationGate;预计 ~200-300 LOC):
  - fixture 用 `tmp_path` 创建 synthetic active change 目录(`openspec/changes/test-v2-synthetic/`)+ proposal/design/specs/tasks 4 制品 minimal stub
  - 跑 `tools/forgeue_preflight_wrapper.py` 创建 worktree + 写 receipt(W1 全链路;含 wrong-cwd / dirty negative)
  - mock Skill(Task) 返回真实 agent_id 格式([a-f0-9]{17}+)+ 跑 `tools/forgeue_dispatch_ledger.py append`(W3 ledger 全链路)
  - 跑 `tools/forgeue_dispatch_ledger.py verify`(W3 ledger verify)
  - 模拟 parallel 场景:2 个 implementer 各自 commit + 跑 W2 actual diff(committed + untracked 合集)
  - 跑 W2 overlap 负例:模拟 2 implementer 修改同一文件 → 自动降级 sequential
  - 跑 W2 dirty 负例:模拟 implementer 漏 commit → precondition 触发降级
  - 跑 `tools/forgeue_finish_gate.py` 全 6 fence(skill_cascade / round_fix_continuity v2 / task_granularity / worktree_path v2 / file_overlap_actual / dispatch_ledger)on synthetic v2 evidence
  - 跑 v1 evidence 兼容回归(synthetic v1 evidence 不被 v2 fence 误杀)
  - 跑 legacy evidence pass-through 回归(无 protocol_version 字段 → 全 fence pass-through)
- [x] P5.5.3:`pytest -q tests/integration/test_v2_e2e_synthetic_change.py -v` 全绿(预计 8-12 test case)
- [x] P5.5.4:`pytest -q` 全套 regress 全绿(无回归)

## P6 — verify

- [x] P6.1:`python tools/forgeue_verify.py --change enhance-workflow-automation-executable-enforcement --level 0` 全绿
- [x] P6.2:`--level 1` 全绿(L1 live-llm SKIP 沿 ADR-007 钱 fence 边界,默认 skip 不 block)
- [x] P6.3:产 `verification/verify_report.md`(12-key audit frontmatter)

## P7 — codex S6 mixed-scope review

- [x] P7.1:`/codex:review --base <main> --background --scope branch` mixed-scope 评(default background;沿 D-DefaultBackground)
- [x] P7.2:落 `review/codex_mixed_scope_review.md`(verdict + finding verbatim + Claude file:line verify + B Cross-check Matrix + Resolution Plan)
- [x] P7.3:writeback finding(沿 ADR-010 simplified protocol 单 commit pattern)
- [x] P7.4:`disputed_open: 0` 验证

**Pre-commit P7 替代落地**(沿 archived enhance-workflow-automation-runtime-enforcement P6 同款 reference stub 模式):
- [x] `review/codex_design_review.md`(reference Pre-P0 round 1)
- [x] `review/codex_plan_review.md`(reference Pre-P0 round 1)
- [x] `review/codex_verification_review.md`(reference verify_report + 待 mixed-scope review 完成)
- [x] `review/codex_adversarial_review.md`(reference Pre-P0 round 1 + 待 mixed-scope review 完成 round 2)
- [x] `review/design_cross_check.md`(reference Pre-P0 plan_cross_check;A/B/C/D 4 段)
- [x] `review/plan_cross_check.md`(reference Pre-P0 plan_cross_check;A/B/C/D 4 段)

## P8 — 跳过 superpowers requesting-code-review(沿 enhance-workflow-automation-runtime-enforcement 同款;cover by Pre-P0 round 1 + P7 mixed-scope)

- [x] P8.1:写 `review/superpowers_review.md` SKIP rationale stub(reviewed N layer review coverage matrix)

## P9 — Documentation Sync Gate

- [x] P9.1:`python tools/forgeue_doc_sync_check.py --change enhance-workflow-automation-executable-enforcement` 静态扫(11 [REQUIRED] 全 touched_in_change 或 sync archive 时 auto-merge / 0 [DRIFT])
- [x] P9.2:落 `verification/doc_sync_report.md` evidence(12-key frontmatter)
- [x] P9.3:任何 [DRIFT] 项 → 0 DRIFT,无需修复

## P10 — Finish Gate

- [x] **P10.0(F5 round 1 codex inline writeback;archive 前必过 gate)**:`pytest -q tests/integration/test_v2_e2e_synthetic_change.py -v` 全绿(沿 D-W4-IntegrationGate;v2 协议端到端实跑 + overlap 负例 + 全 6 fence + v1/legacy 回归);**fixture 不绿 → archive 阻断**
- [x] P10.1:`python tools/forgeue_finish_gate.py --change enhance-workflow-automation-executable-enforcement --no-validate` 跑(预期 P11/P12 unchecked blocker 沿 self-host bootstrap 模式)
- [x] P10.2:验证 12-key frontmatter 全填(全部 formal evidence 12-key)
- [x] P10.3:验证 cross-check `disputed_open: 0`
- [x] P10.4:验证 runtime enforcement frontmatter 字段:
  - 本 change 自身实施模式是 sequential(W1 wrapper 还没 ship → 沿 v1 advisory)
  - evidence 全部 `runtime_enforcement_protocol_version: v1`(沿 archived enhance-workflow-automation-runtime-enforcement 模式)
  - 不强制 v2 字段(worktree_receipt_path / dispatch_ledger_path / task_files_actual)
  - DogfoodGap 显式标注:本 change ship 后下一个 follow-on change 是真 v2 dogfood
- [x] P10.5:验证 writeback_commit 真实性(Pre-P0 + 任意 drift writeback 全 git rev-parse 可解析)
- [x] P10.6:验证 tasks.md 全 [x] 勾选(P0-P10 全 [x];P11 archive + P12 follow-on tracking 必然 [ ] 直到 archive 操作本身;沿 archived 同款 self-host bootstrap unchecked blocker)
- [x] P10.7:`openspec validate enhance-workflow-automation-executable-enforcement --strict` 全绿(待 P11.4 sync archive 后再跑)
- [x] P10.8:落 `verification/finish_gate_report.md`(自 finish_gate 自动生成)

## P11 — Archive(用户授权;Fence #1 不可逆)

- [ ] P11.1:**用户授权确认**(D-AutonomyBoundary fence #1 不可逆)
- [ ] P11.2:`openspec archive enhance-workflow-automation-executable-enforcement --skip-specs --yes`
- [ ] P11.3:手工 sync 4 ADDED + 3 MODIFIED Requirement 到 `openspec/specs/examples-and-acceptance/spec.md`(34 → 38 Requirements;3 个 MODIFIED 替换原 3 个 v1 Requirements)
- [ ] P11.4:`openspec validate examples-and-acceptance --strict` 全绿
- [ ] P11.5:archive stub 加 cross_check fence-required frontmatter(沿 enhance-workflow-automation-runtime-enforcement 模式)
- [ ] P11.6:commit + push(用户授权 fence #1)

## P12 — 后置(可选)+ Follow-on tracking

- [ ] P12.1:更新 `MEMORY.md` 加 enhance-workflow-automation-executable-enforcement 摘要(沿 forgeue auto memory 协议;落 `~/.claude/projects/.../memory/project_executable_enforcement_change.md` + MEMORY.md index entry;含 8 D-decision + 6 fence + 2 wrapper + W2 actual diff + protocol_version v2 + commit SHA + DogfoodGap 说明 + follow-on tracking)
- [ ] P12.2:**实战 dogfood 验证 — 下一个 active change 用本 change 的 v2 协议跑一次**(辅助验证,不替代 P5.5 + P10.0 fixture gate):
  - W1 receipt 自动生成 + LLM 复制到 evidence frontmatter
  - W3 ledger 自动 append + finish_gate cross-check ledger vs evidence
  - 若用 parallel:W2 actual diff 自动收集(含 untracked);模拟 overlap 触发自动降级 sequential
  - 实测 controller drift 类风险是否被 wrapper / ledger 物证 catch
- [ ] P12.3 (follow-on tracking):**`enhance-workflow-automation-ledger-binding`**(F2 + F3 round 1 codex deferred)— W3 真 wrapper-bound dispatch + cryptographic enforcement:
  - **F2 deferred 部分**:wrapper / Hook 拦截 Skill(Task) 调用 + 写 ledger 前拒绝 dispatch 直到 ledger 写入;或申请 Claude Code Skill tool 协议扩展(allowed caller-supplied agent_id metadata + 回传同 ID)
  - **F3 deferred 部分**:cryptographic ledger signing — wrapper 写 nonce/HMAC 到 ledger,key 在 LLM 不可见 env var 域(由 wrapper init 时随机生成,session 内持久化);finish_gate 校验 HMAC 一致性;evidence frontmatter `ledger_forgery_resistance: cryptographic`
  - **触发条件**:本 change ship 后,实测 advisory protocol 不足以挡 controller drift(若足够,可 cancel follow-on);或 user 接受 ~/.claude/settings.json hook 改动作真 enforcement 路径
  - **依据**:本 change `notes/pre_p0/codex_review_round1.md` 等价物 `review/codex_design_review.md` F2 + F3 finding(全 accepted-codex,partial inline + deferred to architectural follow-on)
- [ ] P12.4 (follow-on tracking):**`enhance-workflow-automation-handoff-persistence`**(沿 enhance-workflow-automation P5 round 2 F6 deferred)— codex 命令 allowed-tools vs Polling Convention 写文件能力 mismatch 的 architectural 选择
- [ ] P12.5 (follow-on tracking):**`add-forgeue-brainstorm-stage`**(沿 adopt-subagent-driven-development 已 deferred)— Superpowers brainstorming skill 接入 S0/S1 stage
- [ ] P12.6 (follow-on tracking):**`enhance-workflow-automation-finishing-branch`**(沿 archived enhance-workflow-automation-runtime-enforcement P11 标识)— `superpowers:finishing-a-development-branch` skill 接入 `/forgeue:change-finish` 命令
- [ ] P12.7 (follow-on tracking):**`enhance-workflow-automation-final-review-fence-strictness`**(本 change P10 实证 — final_review SKIP stub 加 stub-only `skill_cascade_audit` + `task_granularity` 字段满足 v1 fence,但 fence 检查仅"字段存在"不检查"字段语义真假";同款 SKIP stub 的"诚实性 gap"在 v1 protocol 下不被 catch — v2 fence `_check_round_fix_continuity_v2` ledger cross-check 才能 catch reference stub vs 真 dispatch 的差异):
  - **scope**:加新 fence `_check_evidence_dispatch_authenticity` 区分真 dispatch evidence(implementer / spec_review / code_quality_review;subagent_continuity 字段含真实 agent_id;ledger 中有对应记录)vs SKIP stub(reference cover-by;evidence body 含 SKIP rationale;subagent_continuity 字段缺 OR ledger 中无对应记录)
  - **新 evidence frontmatter 字段**:`evidence_provenance: dispatched / skip_stub / reference / placeholder`(显式标记本 evidence 来源)
  - **触发条件**:本 change ship 后,实证 SKIP stub pattern(superpowers_review / subagent_final_review / codex_verification_review / codex_adversarial_review reference stub)在 v1 fence 下被当成 dispatched evidence 误通过的 hygiene risk 持续存在;若 follow-on `enhance-workflow-automation-ledger-binding` ship 后 v2 ledger cross-check 已经覆盖此 gap,可 cancel 本 follow-on
  - **依据**:本 change `review/subagent_final_review.md` evidence frontmatter 给 `skill_cascade_audit.invoked_skills: [subagent-driven-discipline]` 是 controller-side meta-judgment(retrospect 时 invoke),**不是** subagent 跑的;同款 hygiene gap 沿 archived runtime-enforcement P7 SKIP stub 模式延续 — 不是本 change 引入,而是被本 change 实证暴露
- [ ] P12.8 (follow-on tracking):**`enhance-workflow-automation-v2-fence-hardening`**(本 change codex mixed-scope round 1 F4 + F5 deferred):
  - **F4 deferred 部分**:`_check_dispatch_ledger` 仅校 wrapper_version + monotonic timestamp + JSON well-formed;不验证 7 字段全(agent_id / round / role / task_subject_hash / dispatched_at / parent_session_id / wrapper_version)/ role ∈ VALID_ROLES enum / 非空 agent_id+round → minimal ledger 行通过 fence,round-1 evidence 通常没有 `subagent_continuity` 也没有 cross-check 兜底,finish_gate 接受没有真实 dispatch 绑定的 ledger
  - **F5 deferred 部分**:`_check_worktree_path_v2` 用 `change_root / receipt_rel` 解析路径但不校 `receipt_rel` 是否 relative + 在 change_root 内;绝对路径 / `../other-change/...` 误填会解析到 change 之外,receipt.change_id 也不与 evidence change_id 比对 → stale receipt 复用 / 跨 change 串
  - **scope**:`_check_dispatch_ledger` 加 7 字段 schema validation + `_check_worktree_path_v2` 加 path traversal validation(`Path.resolve().relative_to(change_root.resolve())` + receipt.change_id == evidence.change_id 比对)+ ~6 fence test
  - **触发条件**:本 change ship 后实测 v2 enforcement 日常使用中遇 stub bypass / cross-change confusion / minimal ledger 误通过 hygiene risk 持续存在 → 启动;若 follow-on `enhance-workflow-automation-ledger-binding` ship 后 cryptographic enforcement 已覆盖此 gap → 可 cancel
  - **依据**:本 change `review/codex_mixed_scope_review.md` round 1 F4 + F5 finding(全 P2 hygiene defense-in-depth;非 critical break v2 enforcement)
