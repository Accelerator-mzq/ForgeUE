## 1. P0 — Pre-flight + Baseline

- [ ] 1.1 在 dev branch 起点(`git log --oneline -1` SHA backfill 进 evidence frontmatter)记录 baseline pytest 数:`python -m pytest -q --collect-only 2>&1 | tail -3`,记到 `verification/baseline.md`
- [ ] 1.2 验证 4 archived change 的当前 finish_gate replay 状态(本 change 后 D-ArchivedReplayCompat legacy pass-through 必须保 PASS;**沿 codex round 1 F2 inline writeback 修正:archived change id 不带 `archive/` 前缀,因 `tools/_common.py:484-496 change_path()` 仅匹配 `archive entry.name.endswith(change_id)`;且 runtime-enforcement 实际归档日期是 2026-05-05 非 2026-05-04**;**沿 P0 实施 writeback:必加 `--dry-run` flag 防止 tool 副作用写入 archived `finish_gate_report.md` 违 "归档即冻结"**):
  - `python tools/forgeue_finish_gate.py --change 2026-05-05-enhance-workflow-automation-runtime-enforcement --json --dry-run`
  - `python tools/forgeue_finish_gate.py --change 2026-05-05-enhance-workflow-automation-executable-enforcement --json --dry-run`
  - `python tools/forgeue_finish_gate.py --change 2026-05-06-restore-superpowers-worktree-consent-gate --json --dry-run`
  - `python tools/forgeue_finish_gate.py --change 2026-05-06-enhance-workflow-automation-ledger-binding --json --dry-run`
  - 前置校验 4 目录确实存在:`ls openspec/changes/archive/ | grep -E "runtime-enforcement|executable-enforcement|consent-gate|ledger-binding"`(应输出 4 行)
  - 4 个全 PASS 记到 `verification/baseline.md`(P5 完成后回归对比期望仍 PASS)

## 2. P1 — 测试 imports 清理 + fence 测试删除(test edit;reorder Option B step 1)

> **Reorder rationale**(P0 实施 writeback,2026-05-06):原 P1=file delete / P2=fence edit / P3=test edit 顺序会让 P1 commit 之后 `pytest --collect-only` fail(`tests/unit/test_forgeue_finish_gate.py:3411` 模块级 import `_forgeue_ledger_crypto` 在 crypto 文件被删后崩溃)。reorder 为 P1=test edit / P2=production edit / P3=file delete,每 commit 后 pytest collect 都过,git bisect 友好。

- [ ] 2.1 `tests/unit/test_forgeue_finish_gate.py` 部分删除:
  - [ ] 2.1.a 删除 module-level `_forgeue_ledger_crypto` import + sys.path 操作(line 3407-3411)
  - [ ] 2.1.b 删除 `test_check_dispatch_ledger_*` 测试组(v1/v2/v3 全分支)
  - [ ] 2.1.c 删除 `test_check_worktree_*` 测试组(`test_check_worktree_path` + `test_check_worktree_consent_outcome` + `test_check_worktree_mode_consistency`)
  - [ ] 2.1.d 删除 `test_check_ledger_*` 测试组(`test_check_ledger_terminal_proof` + `test_check_ledger_forgery_resistance_consistency`)
  - [ ] 2.1.e 删除 `test_check_archived_replay_path_*` 测试组
  - [ ] 2.1.f 删除 `test_check_runtime_enforcement_protocol_version_validity_*` 测试组
  - [ ] 2.1.g 删除 `v3_fence_evidence_setup` fixture(line 3414+ — 依赖 `_ledger_crypto_test` import,沿 P0 实施 writeback)
  - [ ] 2.1.h 保留 ADR-010 advisory 测试 + ADR-011 v1 advisory 测试(skill_cascade / round_fix_continuity / task_granularity / autonomy_boundary)
  - [ ] 2.1.i 验证文件仍可 collect:`python -m pytest tests/unit/test_forgeue_finish_gate.py --collect-only -q | tail -3`
- [ ] 2.2 `tests/integration/test_v2_e2e_synthetic_change.py` 整文件 vs 部分删除:
  - [ ] 2.2.a 实测 v2 path 占比:`grep -c "v2_protocol\|dispatch_ledger\|HMAC\|forgery_resistance\|protocol_version.*v2\|protocol_version.*v3" tests/integration/test_v2_e2e_synthetic_change.py` + `grep -c "^def test_" tests/integration/test_v2_e2e_synthetic_change.py`
  - [ ] 2.2.b 若 > 80% case 用 v2 path → P3 阶段 `git rm`(本 P1 阶段先 Edit 删除模块级 v2 import 防止 collect fail)
  - [ ] 2.2.c 若 ≤ 80% → 仅删除 v2 path case,保留 ADR-010 advisory baseline case
- [ ] 2.3 `tests/unit/test_forgeue_change_state.py` 部分删除(仅删 5th DRIFT type 相关 case;保留 4 类 DRIFT 测试)
- [ ] 2.4 验证 pytest collect 仍 PASS:`python -m pytest --collect-only -q 2>&1 | tail -3`(本 commit 前后 collect 数应一致 - N,N = 删除 case 总数)
- [ ] 2.5 提交 commit `feat(forgeue): retire-parallel-worktree P1 — 测试 imports 清理 + fence 测试删除(pytest collect <N> → <M>)`

## 3. P2 — `forgeue_finish_gate.py` + `forgeue_change_state.py` 内部 fence / helper / 常量删除(production code edit;reorder Option B step 2)

- [ ] 3.1 `tools/forgeue_finish_gate.py` 删除 7 fence 函数:
  - [ ] 3.1.a `_check_dispatch_ledger`(v1/v2/v3 全分支 + 函数内 `from . import _forgeue_ledger_crypto` import line 2210/2216;沿 `Dispatch ledger append-only contract` REMOVED)
  - [ ] 3.1.b `_check_ledger_terminal_proof`(v3 fence;沿 `v3 ledger terminal proof` REMOVED)
  - [ ] 3.1.c `_check_ledger_forgery_resistance_consistency`(v3 fence;沿 `ledger_forgery_resistance frontmatter` REMOVED)
  - [ ] 3.1.d `_check_archived_replay_path_boundary`(v3 fence;沿 `Archived replay path boundary` REMOVED)
  - [ ] 3.1.e `_check_worktree_path`(ADR-011 fence;沿 `Preflight Worktree runtime enforcement` REMOVED)
  - [ ] 3.1.f `_check_worktree_consent_outcome`(ADR-013 fence;沿 `Preflight Worktree runtime enforcement` REMOVED)
  - [ ] 3.1.g `_check_worktree_mode_consistency`(ADR-013 fence;沿 `Preflight Worktree runtime enforcement` REMOVED)
  - [ ] 3.1.h `_check_runtime_enforcement_protocol_version_validity`(沿 `Runtime enforcement protocol_version validity gate` REMOVED)
- [ ] 3.2 `tools/forgeue_finish_gate.py` 删除 helper:
  - [ ] 3.2.a `_runtime_enforcement_v3_active`
  - [ ] 3.2.b `_runtime_enforcement_v2_active`(若存在;否则跳过)
- [ ] 3.3 `tools/forgeue_finish_gate.py` 简化常量:
  - [ ] 3.3.a `_VALID_PROTOCOL_VERSIONS` 改为 `frozenset({"v1"})`(原 `frozenset({"v1", "v2", "v3"})`)
  - [ ] 3.3.b 删除 `_AUDIT_CONSISTENCY_MAP`(整常量)
  - [ ] 3.3.c 删除 `_WORKTREE_REQUIRED_COMMANDS`(整常量,ADR-013 已 retire 为空 frozenset 但仍占行)
- [ ] 3.4 `tools/forgeue_finish_gate.py` 改写 dispatch matrix(`_runtime_enforcement_active` 主路由 + dispatch loop;沿 D-ActiveVsArchivedReplayBoundary 物理路径分支):
  - [ ] 3.4.a 加 helper `_is_archived_replay_path(evidence_path: Path) -> bool`(判断 evidence 是否物理在 `openspec/changes/archive/` 子树)
  - [ ] 3.4.b 改 `_runtime_enforcement_active` 仅 accept `v1`;active 路径 + v2/v3/unknown → BLOCKER `unknown_protocol_version`;archived 路径 + 任何 value → legacy pass-through(沿 D-ActiveVsArchivedReplayBoundary 7-row 表)
  - [ ] 3.4.c 删除 dispatch loop 中 v2 fence 路由分支
  - [ ] 3.4.d 删除 dispatch loop 中 v3 fence 路由分支
- [ ] 3.5 `tools/forgeue_change_state.py` 删除:
  - [ ] 3.5.a `detect_drift_archived_replay_path`(5th DRIFT type;回到 4 类 DRIFT taxonomy)
  - [ ] 3.5.b worktree-related drift detection(若存在 `detect_drift_worktree_*` 类函数)
  - [ ] 3.5.c DRIFT taxonomy enum 改回 4 类(`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`)
- [ ] 3.6 import smoke check:`python -c "from tools import forgeue_finish_gate, forgeue_change_state; print('ok')"` 必 `print ok`
- [ ] 3.7 完整 pytest 实测:`python -m pytest -q 2>&1 | tail -5`,验证 P1 删除 fence 测试后 pytest 仍全 pass(无新 fail)
- [ ] 3.8 提交 commit `feat(forgeue): retire-parallel-worktree P2 — finish_gate + change_state fence/helper/常量/dispatch matrix 删除`

## 4. P3 — 工具 / 命令 / sister skill 文件删除 + grep audit + pytest 对账(file delete;reorder Option B step 3)

- [ ] 4.1 工具文件删除:
  - [ ] 4.1.a `git rm tools/forgeue_preflight_wrapper.py`(W1 wrapper,615 LOC)
  - [ ] 4.1.b `git rm tools/forgeue_dispatch_ledger.py`(W3 ledger 工具,353 LOC)
  - [ ] 4.1.c `git rm tools/_forgeue_ledger_crypto.py`(ledger-binding internal helper,507 LOC)
- [ ] 4.2 命令模板 + skill 整文件 / 目录删除:
  - [ ] 4.2.a `git rm .claude/commands/forgeue/change-apply-parallel.md`(parallel 命令模板,433 LOC)
  - [ ] 4.2.b `git rm -r .claude/skills/subagent-driven-discipline/`(整 sister skill 目录;ADR-012 加的 Layer 2 wiring;747 LOC SKILL.md)
- [ ] 4.3 测试文件整删除:
  - [ ] 4.3.a `git rm tests/unit/test_dispatch_ledger.py`(W3 + ledger-binding v3 测试,1021 LOC)
  - [ ] 4.3.b `git rm tests/unit/test_preflight_wrapper.py`(W1 wrapper 测试,902 LOC)
  - [ ] 4.3.c 检查 `tests/unit/test_forgeue_ledger_crypto.py` 是否存在;**P0 实测确认不存在**,跳过(沿 codex round 1 F4 + P0 实施 writeback)
  - [ ] 4.3.d 若 P1 实测 `test_v2_e2e_synthetic_change.py` v2 path > 80% → 此处 `git rm tests/integration/test_v2_e2e_synthetic_change.py`(P1 已 Edit 删除模块级 import 防 collect fail)
- [ ] 4.4 grep audit `tests/`:`grep -rn 'dispatch_ledger\|_forgeue_ledger_crypto\|forgeue_preflight_wrapper\|change-apply-parallel\|ledger_forgery_resistance\|HMAC\|ledger_line_count\|ledger_final_hmac\|worktree_consent_outcome\|worktree_mode\|task_files_actual\|preflight.*receipt' tests/` 全清(允许残留:archived 历史 fixture / 注释中的 retire 描述)
- [ ] 4.5 完整 pytest 实测:`python -m pytest -q 2>&1 | tail -5`,记录新 baseline 数(P0 实测 1746;期望 1746 - <P1 删除 case 数> + <P3 删除 case 数>)落 `verification/p3_pytest_summary.md`
- [ ] 4.6 baseline 数对账:`P0 baseline 1746 - P1 删除 - P3 删除 = P3 实测`;不一致写 drift 进 `verification/p3_baseline_diff.md` 并修
- [ ] 4.7 提交 commit `feat(forgeue): retire-parallel-worktree P3 — 工具/命令/skill/测试文件删除 + pytest baseline 1746 → <M>(diff: -<deleted>)`

## 5. P4 — 命令模板编辑(change-apply-{subagent,direct}.md)

- [ ] 5.1 `.claude/commands/forgeue/change-apply-subagent.md` 删除:
  - [ ] 5.1.a 整 `## Preflight Worktree` section(沿 `Preflight Worktree runtime enforcement` REMOVED)
  - [ ] 5.1.b 整 `## Preflight Subagent Discipline` section(ADR-012 Layer 2 wiring;sister skill 已 P2 删除)
  - [ ] 5.1.c v2/v3 frontmatter 字段说明(`worktree_path` / `worktree_consent_outcome` / `worktree_mode` / `worktree_receipt_path` / `dispatch_ledger_path` / `task_files_actual` / `degraded_to` / `degradation_reason` / `pre_dispatch_metadata` / `ledger_forgery_resistance` / `ledger_line_count` / `ledger_final_hmac`)
  - [ ] 5.1.d Step 10a stdout 解析逻辑(`[LEDGER] line_count=<N> final_hmac=<hex>` 行解析)
  - [ ] 5.1.e ledger append step(每 dispatch 后 `python tools/forgeue_dispatch_ledger.py append ...`)
  - [ ] 5.1.f 改回 v1 frontmatter only(沿 ADR-011 advisory 同款)
  - [ ] 5.1.g 验证命令模板内 `frontmatter MUST` section 仅列 v1 字段 + ADR-010 baseline 字段
- [ ] 5.2 `.claude/commands/forgeue/change-apply-direct.md` 删除:
  - [ ] 5.2.a `Preflight Worktree` section(沿 D-DirectWorktreeRefinement 当时已不强制,但 doc 仍残留 mention)
- [ ] 5.3 `.claude/commands/forgeue/change-apply.md`(deprecated stub)检查是否含 worktree / ledger / parallel mention,若有删除
- [ ] 5.4 `.claude/commands/forgeue/change-finish.md` / `change-verify.md` / `change-doc-sync.md` / `change-status.md` / `change-plan.md` 检查是否含 v2/v3 frontmatter / ledger / worktree mention,若有删除
- [ ] 5.5 **改写 backbone skill `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`(沿 codex round 1 F1 inline writeback + design.md `D-BackboneSkillRewrite`)**:
  - 5.5.a 删除引用 `change-apply-parallel` 命令的所有行(line 47 / 102 / 142 等)
  - 5.5.b 删除引用 sister skill `subagent-driven-discipline` 的所有行(line 202 / 240 等)
  - 5.5.c 删除 W1 / W2 / W3 wrapper / dispatch ledger 段(line 120 / 129 / 142 / 149 / 171 / 184 等)
  - 5.5.d 删除 ADR-013 D-RestoreConsentGate + D-ConsentOutcomeStateMachine + D-AlreadyIsolatedInvariant + D-ParallelDeclineFallback + D-WrapperDeprecate 5 D-decision 整段(line 81-93 / 212-216 / 220-238 / 240)
  - 5.5.e 沿 ADR-010 baseline 简化:仅保留 12-key audit frontmatter + 4 类 DRIFT taxonomy + 6 advisory fence + Documentation Sync Gate + S0-S9 状态机
  - 5.5.f v1 advisory baseline:保留 `runtime_enforcement_protocol_version: v1` + `_check_skill_cascade` + `_check_round_fix_continuity` + `_check_task_granularity`(沿 D-V1ProtocolBoundary)
  - 5.5.g 实测 backbone SKILL.md 内 retire 关键字 hit 数 → 0:`grep -cE 'change-apply-parallel|subagent-driven-discipline|worktree_consent_outcome|worktree_mode|ledger_forgery_resistance|task_files_actual|forgeue_preflight_wrapper|forgeue_dispatch_ledger|_forgeue_ledger_crypto|HMAC|dispatching-parallel-agents|D-RestoreConsentGate|D-W[123]-|D-Parallel|D-Worktree|D-Consent|D-Already' .claude/skills/forgeue-integrated-change-workflow/SKILL.md`
- [ ] 5.6 提交 commit `feat(forgeue): retire-parallel-worktree P4 — 命令模板退回 v1 frontmatter only + backbone skill 整改`

## 6. P5 — Verify(Level 0 + 1 + 2 + archived replay 4 change finish_gate)

- [ ] 6.1 Level 0 — 静态校验:
  - [ ] 6.1.a `python tools/forgeue_finish_gate.py --change retire-parallel-and-worktree-fully --json` 当前(本 change 自身 not yet ready)预期 `evidence_complete: false`
  - [ ] 6.1.b 抽样 finish_gate 在历史 archived 4 change 上仍 PASS(沿 D-ArchivedReplayCompat;P0 baseline 对账)
  - [ ] 6.1.c 上 4 archived change 全 PASS 记到 `verification/p5_archived_replay.md`(`legacy_pass_through_validated: true`)
- [ ] 6.2 Level 1 — pytest 全跑:`python -m pytest -q 2>&1 | tail -5`,与 P3 实测数一致
- [ ] 6.3 Level 2 — `/codex:review --base main`(automated review hook;沿 `change-verify.md`):
  - [ ] 6.3.a invoke `/codex:review --base main` background
  - [ ] 6.3.b BashOutput 拉 codex result + 解析 finding
  - [ ] 6.3.c 落 `verification/codex_verification_review_round1.md`(沿 12-key audit frontmatter)
- [ ] 6.4 grep audit retire scope 全清(verify 阶段二次扫,沿 D-DocResidueSweep):
  - [ ] 6.4.a `grep -rni 'forgeue_preflight_wrapper\|forgeue_dispatch_ledger\|_forgeue_ledger_crypto' src/ tools/ tests/` 全空
  - [ ] 6.4.b `grep -rni 'change-apply-parallel\|subagent-driven-discipline' .claude/` 全空
  - [ ] 6.4.c `grep -rni 'worktree_consent_outcome\|worktree_mode\|task_files_actual\|ledger_forgery_resistance\|ledger_line_count\|ledger_final_hmac' tools/ .claude/` 全空(允许 archived 4 change 内残留)
- [ ] 6.5 落 `verification/verify_report.md`(12-key audit frontmatter)+ commit

## 7. P6 — Doc Sync Gate(10 文档 stale residue 清理)

- [ ] 7.1 `python tools/forgeue_doc_sync_check.py --change retire-parallel-and-worktree-fully` 静态扫,生成 `verification/doc_sync_check.md`
- [ ] 7.2 应用 §4.3 提示词(沿 `docs/ai_workflow/README.md` §4),逐文档 audit:
  - [ ] 7.2.a `docs/requirements/SRS.md` ADR table 更新(ADR-011 / ADR-012 / ADR-013 / ledger-binding 全标 `[Retired]` + `Superseded by retire-parallel-and-worktree-fully`;若需新加 ADR-014 entry 描述本 change)
  - [ ] 7.2.b `docs/acceptance/acceptance_report.md` ADR table 同步(沿 SRS)
  - [ ] 7.2.c `docs/testing/test_spec.md` 删除 ledger / worktree fence 测试索引(P3 删除的测试 case index 同步删)
  - [ ] 7.2.d `docs/ai_workflow/README.md`(§4 doc sync rules + §6 命令矩阵 — `change-apply-parallel` retire)
  - [ ] 7.2.e `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.6(parallel) + §C.7-C.10(worktree REQUIRED + dispatch ledger + ledger-binding v3)整段删除
  - [ ] 7.2.f `docs/ai_workflow/forgeue_quickstart.md` 残留 Preflight 提及清理
  - [ ] 7.2.g `README.md` v3 cryptographic ledger binding section 删除(沿 `4b2e366`)
  - [ ] 7.2.h `CHANGELOG.md` 加 retire entry(沿 ledger-binding 同款 entry 风格)
  - [ ] 7.2.i `CLAUDE.md` 本文件编辑(§ForgeUE Integrated AI Change Workflow 内 12 字段表 + ADR-013 update + v3 字段段 全删除;退回 ADR-010 baseline 描述)
  - [ ] 7.2.j `AGENTS.md` 同步 `CLAUDE.md`
- [ ] 7.3 grep audit 二次扫(沿 D-DocResidueSweep):
  ```bash
  # 沿 codex round 1 F1 inline writeback 扩展 grep audit 关键字(加 backbone skill scope + 新关键字)
  grep -rniE 'worktree|dispatch_ledger|forgeue_finish_gate|forgeue_preflight_wrapper|change-apply-parallel|ledger_forgery_resistance|HMAC.*chain|HMAC|ledger_line_count|ledger_final_hmac|cryptographic.*ledger|ADR-011|ADR-012|ADR-013|ledger-binding|runtime_enforcement_protocol_version.*v[23]|worktree_consent_outcome|worktree_mode|task_files_actual|preflight.*receipt|subagent-driven-discipline|dispatching-parallel-agents|_forgeue_ledger_crypto|D-RestoreConsentGate|D-W[123]-|D-Parallel|D-Worktree|D-Consent|D-Already' \
    .claude/skills/ .claude/commands/ docs/ README.md CLAUDE.md AGENTS.md CHANGELOG.md
  ```
  分类每个 hit:active stale residue(必须删) / archived 4 change 引用(allowed) / 本 change retrospective entry(allowed) / historical narrative(SRS `[Retired]` 标记,allowed)
- [ ] 7.4 落 `verification/doc_sync_report.md`(12-key audit frontmatter + grep audit 分类清单)+ commit
- [ ] 7.5 提交 commit `docs(forgeue): retire-parallel-worktree P6 — doc-sync(10 文档 stale residue 清理 + ADR table retire 标记)`

## 8. P7 — Retrospective + Cross-check(blocker writeback)

- [ ] 8.1 落 `notes/retrospective.md`(沿 ledger-binding 同款 retrospective 节奏):
  - [ ] 8.1.a 实施过程 lessons learned
  - [ ] 8.1.b retire 漏物清单(若有 P5/P6 grep audit 漏的项目,本 round writeback)
  - [ ] 8.1.c 工程量实测对账(预估 ~3000-4000 LOC 实测多少;~30-50 测试 case 实测多少;~12-15 文档 stale residue 实测多少)
  - [ ] 8.1.d 4-round codex review 实测 round 数(预估 2-3 round;若 codex 找出 critical / high finding 自动加 round)
- [ ] 8.2 `notes/review_cross_check.md`(沿 ForgeUE cross-check A/B/C/D 模板):
  - [ ] 8.2.a Claude self-review verdict
  - [ ] 8.2.b Codex review verdict(自 P5 codex_verification_review)
  - [ ] 8.2.c disputed_open count(必须 == 0 沿 `change-finish` finish_gate fence)
  - [ ] 8.2.d 任一 blocker → writeback 到 design.md / proposal.md / tasks.md(沿 4 类 DRIFT taxonomy)
- [ ] 8.3 落 `verification/finish_gate_report.md`(12-key audit frontmatter + 4 runtime enforcement v1 fence 分支输出)
- [ ] 8.4 提交 commit `feat(forgeue): retire-parallel-worktree P7 — retrospective + cross-check(disputed_open=0;ready-to-ship)`

## 9. P8 — Finish Gate + Archive

- [ ] 9.1 `python tools/forgeue_finish_gate.py --change retire-parallel-and-worktree-fully --json` 全 PASS:
  - [ ] 9.1.a `evidence_complete: true`
  - [ ] 9.1.b `frontmatter_aligned: true`
  - [ ] 9.1.c `cross_check_disputed_open: 0`
  - [ ] 9.1.d `writeback_truth: true`(每个 evidence frontmatter 内 `writeback_commit` SHA 真实存在)
  - [ ] 9.1.e `tasks_unchecked: 0`
  - [ ] 9.1.f `openspec validate --strict` PASS
- [ ] 9.2 user explicit auth(沿 fence #1 不可逆操作 + memory `Push requires explicit per-commit auth`):
  - [ ] 9.2.a `AskUserQuestion`:archive change + push origin dev?
  - [ ] 9.2.b 等用户确认后才走下面 step
- [ ] 9.3 archive change:
  - [ ] 9.3.a `mv openspec/changes/retire-parallel-and-worktree-fully openspec/changes/archive/2026-05-XX-retire-parallel-and-worktree-fully`(具体日期归档时填)
  - [ ] 9.3.b commit `feat(forgeue): ship retire-parallel-and-worktree-fully (squash merge)`
- [ ] 9.4 dev → main merge(若 ForgeUE 走 PR / merge protocol,user 决定):
  - [ ] 9.4.a 沿 `git merge dev` 或 `gh pr create` 路径
  - [ ] 9.4.b user explicit auth(fence #1)
- [ ] 9.5 MEMORY.md update:
  - [ ] 9.5.a 删除 entry `[retire-parallel-and-worktree-fully change planned (B option)]`(planning entry,本 change 完成后已实现)
  - [ ] 9.5.b 加新 entry `[retire-parallel-and-worktree-fully shipped 2026-05-XX]`(描述完成状态 + 实际 LOC 删除数 + 测试 case 删除数)
  - [ ] 9.5.c entry `[ADR-013 Restore Superpowers Worktree Consent Gate shipped 2026-05-06]` 标 `[Superseded by retire-parallel-and-worktree-fully]`(保留 traceability)
  - [ ] 9.5.d entry `[v3 Cryptographic Ledger Binding shipped 2026-05-06]` 标 `[Superseded by retire-parallel-and-worktree-fully]`
  - [ ] 9.5.e entry `[Runtime enforcement change shipped 2026-05-05]` 标 `[Superseded]`
- [ ] 9.6 提交 commit `chore(memory): retire-parallel-worktree shipped — MEMORY.md superseded chain update`
