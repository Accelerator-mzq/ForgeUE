---
change_id: enhance-workflow-automation-ledger-binding
stage: S2
evidence_type: execution_plan
contract_refs:
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
  - design.md#decisions
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: cli-flag
codex_plugin_available: true
triggered_by_command: change-plan
runtime_enforcement_protocol_version: v2
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
task_granularity: phase
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
    - superpowers:brainstorming
  cascade_check_pass_at: 2026-05-06T13:53:29+08:00
created_at: 2026-05-06T15:00:00+08:00
---

# Execution Plan — enhance-workflow-automation-ledger-binding

> **For agentic workers**:本 plan 沿 ForgeUE Integrated AI Change Workflow S3→S4-S5 阶段执行。
> 推荐路径:`/forgeue:change-apply-direct`(沿 D-DispatchPath;scope 聚焦 + 工程量 6-9h + 3 个核心改动文件互相依赖,subagent overhead 不划算)。
> 不推荐 `/forgeue:change-apply-subagent`(subagent overhead 不划算 + 本 change 自身 evidence 沿 v2 self-dogfood 协议,subagent 路径需要 W3 ledger 写入 + dispatch overhead)。
> 不推荐 `/forgeue:change-apply-parallel`(tasks 不独立 — crypto helper / dispatch_ledger / finish_gate 互相依赖,无 parallel 边界)。
> ADR-013 worktree consent gate 在 direct 路径下生效:framework 层修改默认 `worktree_mode: in_place`(`worktree_consent_outcome: declined / already_isolated`)。

**Goal**:把 archived `enhance-workflow-automation-executable-enforcement` 的 ledger advisory 协议(`pre_dispatch_metadata: advisory` + `ledger_forgery_resistance: advisory`)升级为 cryptographic enforcement v3 协议 — HMAC-SHA256 hash chain + key-rotation fail-closed + tail truncation 守门 + audit consistency 强 enum + strict 11-field schema validation + unknown protocol value 守门 + archived replay 路径限定。F2 wrapper-bound dispatch out-of-scope(留独立 follow-on `enhance-workflow-automation-skill-tool-binding`);本 change scope F3-only 而 round 1+2 codex inline writeback 后 scope expansion 合并 P12.8 schema validation。

**Architecture**:三层防御 — (1) cryptographic chain(`prev_hmac` 串联行 + 单行 HMAC 重算抓中间删行 / hand-edit / reorder)/ (2) terminal proof anchor(evidence frontmatter `ledger_line_count` + `ledger_final_hmac` 抓 tail truncation 漏洞)/ (3) protocol-version + path + audit triple gate(unknown protocol BLOCKER + archived_replay 路径限定 + frontmatter audit consistency v3↔cryptographic / v2↔advisory);失败时 fail-closed BLOCKER。

**Tech Stack**:Python 3.12+ stdlib only(`hashlib` / `hmac` / `secrets` / `json` / `pathlib` / `os.chmod` / `argparse` / `datetime`);ForgeUE 既有 `tools/forgeue_*.py` 工具集风格(沿 `forgeue_preflight_wrapper.py` / `forgeue_dispatch_ledger.py` / `forgeue_finish_gate.py` 同款 stdlib subprocess pattern);pytest 单元测试矩阵(沿 archived `executable-enforcement` test_dispatch_ledger.py / test_forgeue_finish_gate.py 同款);OpenSpec change artifact + `openspec validate --strict`。

---

## File Structure

| 路径 | 类型 | 责任 |
|---|---|---|
| `tools/_forgeue_ledger_crypto.py` | 新建 | stdlib-only crypto helper:`load_or_init_key()` lifecycle(6 状态)/ `canonical_payload()` 排除 hmac + 包含 prev_hmac + sort_keys + UTF-8 / `compute_hmac()` HMAC-SHA256 / `compute_key_id()` SHA256[:16] fingerprint / `verify_chain_v3(key_bytes, lines, evidence_frontmatter)` 整链 verify 含 D-KeyRotationHandling 双路径 / `verify_terminal_proof()` D-LedgerTerminalProof / `verify_strict_schema_v3()` D-Scope-F3-MergeWithP12.8。下划线前缀 internal,无 CLI 入口,模块顶层零副作用 |
| `tools/forgeue_dispatch_ledger.py` | 修改 | `WRAPPER_VERSION` "1.0" → "2.0";`cmd_append` 升级:加载 key + 读 prev_hmac + 算 hmac + 写 11 字段 + stdout 打印 `[LEDGER] line_count=<N> final_hmac=<hex>`;`cmd_verify` 升级:沿 `protocol_version` 字段 dispatch + 加 `--allow-archived-replay` flag(D-ArchivedReplayPathBoundary)+ exit code 5/6/7 |
| `tools/forgeue_finish_gate.py` | 修改 | 新 helper `_runtime_enforcement_v3_active(frontmatter)` + `_VALID_PROTOCOL_VERSIONS = frozenset({"v1", "v2", "v3"})` 模块常量;新 fence 4 个:`_check_runtime_enforcement_protocol_version_validity`(D-RuntimeEnforcementProtocolVersionValidity)/ `_check_archived_replay_path_boundary`(D-ArchivedReplayPathBoundary)/ `_check_ledger_terminal_proof`(D-LedgerTerminalProof)/ `_check_ledger_forgery_resistance_consistency`(D-FrontmatterAuditConsistency);现有 `_check_dispatch_ledger` 加 v3 分支(import `_forgeue_ledger_crypto.verify_chain_v3` + 整链 + terminal proof + strict schema);现有 `_check_round_fix_continuity` 加 v3 路径(在 v2 cross-check 基础上加 chain + terminal proof) |
| `tools/forgeue_change_state.py` | 修改 | `--writeback-check` 加 `archived_replay_path_violation` 进 4 类 named DRIFT 检测之一(active change evidence 含 `ledger_archived_replay: true` = drift signal) |
| `tests/unit/test_dispatch_ledger.py` | 修改 | 加 v3 case ~30 个(round 1+2 codex inline writeback 后):happy path + forge attack(hand-edit / delete / reorder / tail truncation)+ key boundary(rotation default fail-closed / archived replay opt-in / corrupted)+ canonical 稳定性 + dispatch matrix 4 档(legacy / v1 / v2 / v3 / unknown)+ schema strict 11-field + archived replay path boundary |
| `tests/unit/test_forgeue_finish_gate.py` | 修改 | 加 v3 fence test ~22 个(round 1+2 codex inline writeback 后):4 新 fence 各 ~5 case + dispatch ledger v3 分支 ~6 case + round_fix_continuity v3 路径 ~3 case + audit consistency 4 case |
| `tests/integration/test_v2_e2e_synthetic_change.py` | 修改 | 加 v3 平行 case `test_v3_e2e_cryptographic_synthetic_change` + 4 negative case(hmac_mismatch / tail_truncation / key_id_mismatch_default_fail_closed / audit_inconsistency);用 monkey-patched `Path.home()` 隔离真实 user key |
| `.claude/commands/forgeue/change-apply-subagent.md` | 修改 | evidence frontmatter 模板加 v3 字段(`runtime_enforcement_protocol_version: v3` / `ledger_forgery_resistance: cryptographic` / `ledger_line_count` / `ledger_final_hmac`)+ Step 10a 加"读 wrapper stdout `[LEDGER]` 行 + 复制到 evidence frontmatter"明确指令 |
| `.claude/commands/forgeue/change-apply-parallel.md` | 修改 | 同 subagent(同步 v3 frontmatter + Step 10a stdout 解析) |
| `.claude/commands/forgeue/change-apply-direct.md` | 不动 | 沿现有协议(direct 不走 dispatch ledger;无 v2/v3 evidence) |
| `docs/ai_workflow/forgeue_integrated_ai_workflow.md` | 修改 | §C protocol matrix 扩到 4 档(legacy / v1 / v2 / v3 + unknown BLOCKER);新加 §C.10 "Cryptographic Ledger Binding"(D-decision 摘要 + key 文件 lifecycle + verify 流程 + threat model 边界 + archived replay 路径限定) |
| `CLAUDE.md` | 修改 | Runtime enforcement frontmatter 字段段加 v3 说明(`ledger_line_count` / `ledger_final_hmac` / `ledger_archived_replay` / `ledger_forgery_resistance` 字段约束)+ 4 档 dispatch matrix 更新 + 工具清单 stdlib helper(`_forgeue_ledger_crypto.py`) |
| `docs/ai_workflow/README.md` | 修改 | §4 加 v3 协议摘要(若 §4.4-ter 等位置已经 mention 协议矩阵) |
| `CHANGELOG.md` | 修改 | [Unreleased] 加本 change entry(沿现有 entry 风格) |
| `AGENTS.md` | 修改 | 加 v3 protocol 摘要(沿 `executable-enforcement` v2 摘要同款风格) |
| `README.md` | 不动 | ForgeUE Workflow 表已含工具清单;v3 升级是工具升级而非新工具,无需改 README 表(若 §4 协议矩阵在 README 内 mention,改;通常在 docs/ai_workflow/) |
| `openspec/specs/examples-and-acceptance/spec.md` | archive 时 auto-merge | sync 6 ADDED + 2 MODIFIED Requirement(沿 archived `executable-enforcement` archive 时 auto-merge 同款) |

---

## Phase Map(对应 tasks.md 锚点;13 phase 独立 row,P0 完成,P1-P9 待 implementation)

| Phase | tasks.md 锚点 | scope | 依赖 | 说明 |
|---|---|---|---|---|
| P0 | [P0](../tasks.md#p0--pre-implementation-对抗-review) | codex round 1+2 design challenge + writeback(F1+F2+F3+F4+F5 round 1 + round2-F1+F2+F3 全 inline)+ openspec validate --strict pass | 已 4 制品 valid | **本会话已完成**(commit 81edd63 round 1 + commit d96076f round 2;disputed_open: 0) |
| P1 | [P1](../tasks.md#p1--crypto-helper-module-toolsforgeueledgercrypto.py) | `tools/_forgeue_ledger_crypto.py` 新建 + 单元测试 ~10 case(canonical / compute_hmac / compute_key_id / load_or_init_key lifecycle 6 状态) | P0 closed | 见 micro_tasks.md §P1 |
| P2 | [P2](../tasks.md#p2--toolsforgeue_dispatch_ledger.py-升级-v3) | `forgeue_dispatch_ledger.py` 升级 + 测试 ~22 case(append 11 字段 + chain + stdout `[LEDGER]` + verify 整链 + key rotation fail-closed + archived replay opt-in + schema strict + unknown protocol BLOCKER) | P1 done(import `_forgeue_ledger_crypto`)| 见 micro_tasks.md §P2 |
| P3 | [P3](../tasks.md#p3--toolsforgeue_finish_gate.py-升级-v3-fence) | `forgeue_finish_gate.py` 升级 4 新 fence + dispatch matrix v3 分支 + 测试 ~22 case(4 新 fence 各 ~5 case + dispatch_ledger v3 + round_fix_continuity v3 + audit consistency) | P1 + P2 done(import + cmd_verify 协议)| 见 micro_tasks.md §P3 |
| P4 | [P4](../tasks.md#p4--命令模板-frontmatter-升级--e2e-fixture-v3) | 命令模板 frontmatter 升级 + e2e fixture v3 平行 case(happy + 4 negative) | P3 done | 见 micro_tasks.md §P4 |
| P5 | [P5](../tasks.md#p5--验证-hook--codex-codex-review---base-main) | `/forgeue:change-verify` Level 0/1/2 + codex `/codex:review --base main` 验证 hook + finding 落 review/ + cross-check + inline writeback 闭合 | P4 done | 见 micro_tasks.md §P5 |
| P6 | [P6](../tasks.md#p6--forgeuechange-doc-sync-documentation-sync-gate) | Documentation Sync Gate(10 文档静态扫 + §4.3 提示词 + 应用 [REQUIRED]) | P5 done | 见 micro_tasks.md §P6 |
| P7 | [P7](../tasks.md#p7--final-review--finish-gate) | `/forgeue:change-review` Superpowers + codex adversarial mixed scope finalize + `/forgeue:change-finish` 12-key frontmatter + writeback 真实性 + cross-check disputed_open == 0 | P6 done | 见 micro_tasks.md §P7 |
| P8 | [P8](../tasks.md#p8--archive-change) | `openspec archive enhance-workflow-automation-ledger-binding`(自动 prefix 当前日期)+ archive commit + push 单独请示 user | P7 done | user-required(沿 ADR-010 fence #1 不可逆) |
| P9 | [P9](../tasks.md#p9--memory.md-update--follow-on-tracking后置可选) | MEMORY.md update(15 D-decision + threat model + commit SHA)+ follow-on tracking(P12.8 superseded、P9.5 / P9.6 retire 评估) | P8 done(post-archive)| 后置可选 |

---

## Test Matrix Summary

**Total ~45 test case**(基线 549 + 本 change 新增 ~45 → 594 测试):

| 来源 | scope | case 数 |
|---|---|---|
| `tests/unit/test_dispatch_ledger.py`(新增 v3 部分) | `_forgeue_ledger_crypto` 内部函数 + cmd_append + cmd_verify 全分支 | ~30 |
| `tests/unit/test_forgeue_finish_gate.py`(新增 v3 部分) | 4 新 fence + dispatch_ledger v3 + round_fix_continuity v3 + audit consistency | ~22 |
| `tests/integration/test_v2_e2e_synthetic_change.py`(新增 v3 平行 case) | e2e wrapper 真跑 + finish_gate fence 跑通 + 4 negative | ~5 |

实际上 ~30 + ~22 + ~5 = ~57 case;tasks.md 估算 ~45 是粗估(有重叠,如 unit + integration 都覆盖 happy path);最终以 implementation 实测为准。

---

## Risks during execution

- **R1 self-dogfood gap**:本 change 自身 evidence 沿 v2 advisory(`runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`),不触发 v3 fence。Mitigation:evidence frontmatter 加 audit 注释 `# v3 协议自本 change ship 后才生效;本 change 自身 evidence 沿 v2 self-dogfood`
- **R2 测试 fixture 不污染 user home**:用 `monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)` 隔离;若漏 monkeypatch 测试可能写到真实 `~/.claude/forgeue_ledger_key` 污染。Mitigation:test fixture 在 `conftest.py` 加 `autouse=True` monkey-patch + assert 检测 `Path.home() != Path("~").expanduser()`(在测试运行时)
- **R3 tests/unit/test_dispatch_ledger.py 现有 v2 case 不被 v3 升级 break**:wrapper_version 从 1.0 升到 2.0,现有 v2 测试 fixture 用 1.0 — 仍合法(fence 不强制 wrapper_version 具体值)。Mitigation:运行全套 `python -m pytest -q` 确认基线 549 + 本 change ~45 → 594 全过
- **R4 codex round 3 实证可能 raise 新 finding**:本 change 不主动跑 round 3(disputed_open == 0 已满足 forgeue:change-plan step 9 状态推进)。若 P5 codex `/codex:review --base main` raise 新 finding 进入 round 3 inline writeback 路径
- **R5 ADR-013 worktree consent gate**:本 change framework 层修改(`tools/_forgeue_ledger_crypto.py` 新建 + `forgeue_finish_gate.py` 改);default 走 in_place(`worktree_mode: in_place`,`worktree_consent_outcome: declined`)— 沿 D-DispatchPath direct 路径
- **R6 self-dogfood evidence frontmatter 字段不写 v3 字段**:本 change implementation evidence 沿 v2 协议,不写 `ledger_line_count` / `ledger_final_hmac` / `ledger_archived_replay` / `runtime_enforcement_protocol_version: v3`;只写 `runtime_enforcement_protocol_version: v2` + `ledger_forgery_resistance: advisory`(沿 archived `executable-enforcement` self-dogfood gap 同款)

---

## Dispatch Path Decision

**推荐 `change-apply-direct`**(沿 D-DispatchPath):
- scope 聚焦,3 核心改动文件互相依赖(crypto helper → dispatch_ledger → finish_gate)
- 工程量 6-9h(含 ~57 测试 case)
- subagent overhead 不划算(per-task 4 类 evidence + dispatch ledger 自循环 + worktree 初始化)
- ADR-013 + D-DirectWorktreeRefinement:direct 路径 in_place(`worktree_mode: in_place`)
- 沿 `executing-plans` + `test-driven-development` SKILL 节奏(failing test → minimal impl → regress green → commit)

不推荐:
- `change-apply-subagent`:overhead 不划算
- `change-apply-parallel`:tasks 不独立(crypto helper / dispatch_ledger / finish_gate 互相依赖)
