## REMOVED Requirements

> **Common Reason**:ForgeUE 协议层全 retire(B 路径激进全面转 Superpowers,见 `proposal.md` + `design.md` D1-D10);整删 9 命令 / 8 工具 / 2 sister skill / 12-key audit frontmatter / cross-check A/B/C/D / 4 类 DRIFT taxonomy / writeback 协议 / Lean Apply Mode / skill cascade / subagent-driven-discipline 28-subtype / budget tracker fence / runtime enforcement protocol version / dispatch wrapper / dispatch ledger / parallel dispatch / backlog 守门 fence。
>
> **Common Migration**:新工作流走 OpenSpec(`/opsx:propose` 立项 + `/opsx:archive` 归档)+ Superpowers(`writing-plans` / `subagent-driven-development` / `executing-plans` / `test-driven-development` / `requesting-code-review` / `verification-before-completion` / `systematic-debugging` / `finishing-a-development-branch`)+ codex CLI opt-in via CLAUDE.md strong convention(`/codex:adversarial-review` design hook + `/codex:review --base main` final hook)。

### Requirement: Active change evidence is captured under OpenSpec change subdirectories with writeback protocol

**Reason**:12-key audit frontmatter / DRIFT taxonomy / writeback 协议是 ForgeUE 自家工作流自我治理协议,audit 数据(business track 14 PROTO-SELF / finish_gate 0/11 BLOCKER)证明边际增量低于代价。

**Migration**:Evidence 自由格式落 `openspec/changes/<id>/{notes,execution,review,verification}/` 即可;Superpowers `requesting-code-review` 与 `verification-before-completion` skill 提供原生 evidence 收口;design / contract drift 直接编辑 `design.md` / `proposal.md` / `tasks.md`,无需 `writeback_commit` 字段强制。

### Requirement: subagent-driven-development per-task evidence schema

**Reason**:4 类 per-task evidence(`subagent_implementer_report` / `subagent_spec_review` / `subagent_code_quality_review` / `subagent_final_review`)+ 12-key frontmatter 是 ForgeUE-specific 协议,与 Superpowers `subagent-driven-development` SKILL 上游协议解耦。

**Migration**:走 Superpowers `subagent-driven-development` SKILL 原生协议(implementer + spec_reviewer + code_quality_reviewer + final_reviewer 上游 prompt 模板),evidence 落盘格式由 SKILL 自管;ForgeUE 不再加 frontmatter audit wrapper。

### Requirement: change-apply-subagent 命令直接 invoke Superpowers skill

**Reason**:`/forgeue:change-apply-subagent` 命令模板 + `subagent-driven-discipline` companion skill 28-subtype × model tier 表 / cascade enforcement 协议是 ForgeUE-specific wrapper,B 路径 retire 9 命令一并 retire。

**Migration**:用户直接 invoke `Skill(superpowers:subagent-driven-development)` SKILL;model tier 选择走 SKILL 自管 default;若用户希望 cost-aware 选 model,可在 dispatch 前手工决定 `Agent(model: "haiku" | "sonnet" | "opus")` 参数。

### Requirement: subagent token-budget tracker 是 informational 不是 enforcement

**Reason**:`tools/forgeue_subagent_budget.py` 工具 + `verification/subagent_budget.log` JSON Lines 协议 + `FORGEUE_SUBAGENT_BUDGET_WARN_USD` 环境变量是 ForgeUE-specific informational tracker,user audit(`audit-archived-subagent-budget-true-cost-vs-discipline-tier` follow-on)显示 controller 经常忽略不传 model 参数,实际 default Opus 与表对不上,tracker 数据不可靠。

**Migration**:用户跑 subagent dispatch 后手工跟踪 cost(Anthropic Console / API usage 报表);若需 budget alert 可在 dispatch 前手工估算 token 预算。

### Requirement: Codex review default background dispatch policy

**Reason**:`/codex:review` background dispatch 策略 + `notes/<review_type>_active_jobs.txt` per change_id + `autonomy_decision: claude_codex_concurred` + `codex_review_ref` 字段 + Round counter `notes/codex_<review_type>_round_counter.txt` 协议绑死 12-key frontmatter,12-key 整删后这些字段不存在。

**Migration**:codex CLI plugin 自身的默认 background / foreground 行为(plugin upstream 自管);用户在 design 或 final 阶段手工调用 `/codex:adversarial-review --background` 或 `/codex:review --background` 即可,不需要 ForgeUE-specific frontmatter 字段强制约束。

### Requirement: Codex multi-round review same-subject context bridge

**Reason**:Round counter sticky 协议 + round N+1 prompt 自动注入 round N reference + `bridge_violation` frontmatter 字段 + `notes/codex_<review_type>_round_counter.txt` 是 ForgeUE-specific 多轮 review 协议,绑死 12-key frontmatter。

**Migration**:用户在多轮 review 时手工告知 codex(`/codex:adversarial-review --background "round 2,please first read notes/codex_<review_type>_review_round1.md ..."`);codex CLI plugin 已支持多轮 prompt 注入,无需 ForgeUE-specific bridge 协议。

### Requirement: Workflow autonomy boundary fence

**Reason**:6 类 boundary fence(不可逆 / 跨 change / Codex 冲突 / 用户约束 / 钱 / 安全)+ `autonomy_decision` frontmatter 4-enum 字段(`claude_autonomous` / `claude_codex_concurred` / `user_required` / `user_overrode`)是 ForgeUE-specific 协议,绑死 12-key frontmatter;memory `feedback_autonomy_boundary_simplified`(2026-05-05)已记录 user 拍板 simplified autonomy boundary。

**Migration**:Claude controller 默认按用户决策风格"先给论证再请求授权"自主拍板;不可逆操作(git push / git reset --hard / archive change / delete file)永远升级用户;其他场景按上下文判断,不需要 frontmatter 字段强制审计。

### Requirement: Preflight Worktree runtime enforcement

**Reason**:Preflight Worktree 协议(W1 wrapper / W2 actual diff / W3 ledger / `worktree_consent_outcome` × `worktree_mode` 状态机)是 ForgeUE-specific 强制层,已在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 进一步整删 spec Requirement 段。

**Migration**:走 Superpowers upstream `using-git-worktrees` SKILL OPTIONAL invoke;controller 在 dispatch 前自由决定 isolation;default decline → main repo cwd。

### Requirement: Implementation parallel dispatch via `/forgeue:change-apply-parallel`

**Reason**:`/forgeue:change-apply-parallel` 命令在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire(沿 D-HardRetireScope + user 拍板 wide retire B option),本 change 整删 spec Requirement 段。

**Migration**:不再支持 parallel dispatch;multi-task 走 Superpowers `subagent-driven-development` SKILL sequential default;若未来需要 parallel 走独立 change re-propose。

### Requirement: Round 2+ fix subagent continuity

**Reason**:`subagent_continuity` frontmatter 字段 + round 1 / round 2 agent ID 一致性 fence 是 ForgeUE-specific 协议,绑死 12-key frontmatter。

**Migration**:Claude controller 自由决定 round 2 fix 是否复用 round 1 agent(无 fence 守门);Superpowers SKILL 协议自管 fresh subagent per task default。

### Requirement: Task granularity declaration

**Reason**:`task_granularity` frontmatter 字段(`phase` / `per-file` / `sub-task` 3-enum)+ `_check_task_granularity` fence 是 ForgeUE-specific 协议,绑死 12-key frontmatter。

**Migration**:Claude controller 自由决定 task 粒度,无 fence 守门;Superpowers `subagent-driven-development` SKILL 协议默认 per-task fresh subagent,粒度由 plan 自身决定。

### Requirement: Preflight wrapper receipt JSON contract

**Reason**:`tools/forgeue_preflight_wrapper.py` + receipt JSON 13-field schema 在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — wrapper 已删,receipt 协议不存在。

### Requirement: Dispatch ledger append-only contract

**Reason**:`tools/forgeue_dispatch_ledger.py` + ledger append-only 协议 + 7-field v1 / 11-field v3 schema 在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — ledger 已删,append-only 协议不存在。

### Requirement: Parallel dispatch actual file overlap detection

**Reason**:Parallel dispatch 在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — parallel dispatch 不再支持;sequential dispatch 无 file overlap detection 需求(natural by definition)。

### Requirement: v2 e2e integration test fixture(F5 round 1 codex inline writeback)

**Reason**:v2 协议在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — v2 协议已删,fixture 不存在。

### Requirement: Runtime enforcement protocol version v2 migration

**Reason**:v2 协议在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — v2 协议已删,migration 协议不存在。

### Requirement: HMAC key lifecycle for v3 cryptographic ledger binding

**Reason**:v3 HMAC ledger 协议在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — v3 协议已删,HMAC key 不存在。

### Requirement: v3 ledger schema with HMAC chain

**Reason**:v3 schema 协议在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — v3 schema 已删。

### Requirement: v3 fence dispatch matrix and HMAC chain verification

**Reason**:v3 fence 协议在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — v3 fence 已删。

### Requirement: ledger_forgery_resistance frontmatter field upgrade to cryptographic with strict gate

**Reason**:`ledger_forgery_resistance` frontmatter 字段在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — 字段已删。

### Requirement: v3 ledger terminal proof (line_count + final_hmac frontmatter audit)

**Reason**:v3 ledger terminal proof 协议在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — terminal proof 协议已删。

### Requirement: v3 ledger strict 11-field schema validation

**Reason**:v3 11-field schema 协议在 `retire-parallel-and-worktree-fully`(2026-05-06)整 retire,本 change 整删 spec Requirement 段。

**Migration**:无 — 11-field schema 已删。

### Requirement: Runtime enforcement protocol_version validity gate

**Reason**:`runtime_enforcement_protocol_version` frontmatter 字段(`v1` / `v2` / `v3` / unknown 4-enum)+ Active vs Archived dispatch 守门是 ForgeUE-specific 协议,本 change 全 retire 12-key frontmatter 后字段不存在。

**Migration**:无 — frontmatter 字段已删。Archived 24 changes evidence 沿 D-ArchivedReplayCompat,fence 整删后 archived 路径自动 pass(no fence to dispatch on)。

### Requirement: Archived replay path boundary

**Reason**:Active vs Archived 路径 boundary 是 ForgeUE-specific dispatch 协议,本 change 全 retire `forgeue_finish_gate.py` 后 dispatch 不存在,boundary 自然消失。

**Migration**:Archived 24 changes evidence 不动(沿"归档即冻结"原则);若未来 replay 需求出现,走 git history 重现而非 fence dispatch。

### Requirement: `_check_tasks_unchecked` 双格式 section heading 识别 + per-format threshold

**Reason**:`_check_tasks_unchecked` fence 是 `forgeue_finish_gate.py` 内部 fence,本 change 整删 finish_gate 后 fence 不存在。

**Migration**:走 OpenSpec `/opsx:archive` 内置 tasks.md 完整性检查(若 OpenSpec 提供);否则 user 在 archive 前手工 grep `^- \[ \]` 检查 unchecked tasks。

### Requirement: `forgeue_finish_gate.py` openspec validate archive 路径分流 skip

**Reason**:`forgeue_finish_gate.py` 在 archived change replay 时分流 skip openspec validate 是 finish_gate 内部 dispatch 行为,本 change 整删 finish_gate 后行为不存在。

**Migration**:`/opsx:archive` 自身处理 archived change validate(走 OpenSpec CLI upstream);若 archived path 仍报 Unknown item,沿 follow-on `enhance-openspec-cli-archived-change-support`(留 OpenSpec CLI upstream patch)。

(`Centralized follow-on backlog registry under openspec/backlog/` 改 REMOVED→MODIFIED;round 1 codex P1-4 accept;见本文件下方 `## MODIFIED Requirements` 段。)

### Requirement: `_check_followon_continuity` blocker fence enforces inheritance or cancel declaration with active.md self-truth diff and cancel ref strict validation

**Reason**:`_check_followon_continuity` fence 是 `forgeue_finish_gate.py` 内部 fence,本 change 整删 finish_gate 后 fence 不存在。

**Migration**:无 fence 守门 follow-on continuity;user 在 archive 前手工 review prior change tasks.md unchecked items + active.md / archived.md diff;沿 D5 follow-on 自然 lifecycle。

### Requirement: `_check_srs_registry_consistency` blocker fence enforces SRS §7.3 ↔ active.md set equivalence

**Reason**:`_check_srs_registry_consistency` fence 是 `forgeue_finish_gate.py` 内部 fence,本 change 整删 finish_gate 后 fence 不存在。

**Migration**:无 fence 守门 SRS-registry consistency;user 在 active.md / SRS §7.3 改动时手工 sync。

### Requirement: `archived.md` tombstone follows append-only schema with 4 fields per entry

**Reason**:Tombstone append-only schema 4-field 协议 + `_check_archived_md_append_only` fence 是 `forgeue_finish_gate.py` 内部 fence,本 change 整删 finish_gate 后 fence 不存在。

**Migration**:`archived.md` schema 描述保留在 `openspec/backlog/README.md` 作 reference(若 user 维护 tombstone 沿用 4-field convention);无 fence 守门 append-only,user 不删 tombstone 是 git history 自然守门即可。

### Requirement: Evidence frontmatter conditional field `followon_continuity` summarizes archive-stage backlog inheritance

**Reason**:`followon_continuity` 13th conditional 字段是 12-key frontmatter 扩展,本 change 全 retire 12-key frontmatter 后字段不存在。

**Migration**:无 — 字段已删;follow-on inheritance 信息可在 archive-stage retrospective.md 文档(自由格式)中描述。

### Requirement: `/forgeue:change-status` command Output Format includes Followon Backlog section

**Reason**:`/forgeue:change-status` 命令 + Followon Backlog section 输出格式是 ForgeUE-specific 命令协议,本 change 整删 9 命令一并 retire。

**Migration**:user 走 `/opsx:status` + 手工 `Read openspec/backlog/active.md` 查 follow-on 状态。

## MODIFIED Requirements

### Requirement: Centralized follow-on backlog registry under `openspec/backlog/`

The system SHALL maintain a centralized follow-on backlog registry at `openspec/backlog/active.md` (active items) and `openspec/backlog/archived.md` (cancelled / completed items). The active registry SHALL collect archive-tracking class follow-ons (workflow-protocol class + capability-boundary class) and pointer entries to `docs/requirements/SRS.md` §7.3 TBD entries (requirements-tbd-pointer class). The active registry SHALL NOT duplicate full TBD content from SRS §7.3 (dual-source cross-link, not single-source). Each registry entry SHALL carry the following fields: `id` (kebab-case), `source` (archived change tasks.md anchor or SRS §7.3 TBD-XXX pointer), `description`, `trigger` (trigger condition for promotion to a real change), `category` (one of `workflow-protocol` / `capability-boundary` / `requirements-tbd-pointer`), `retire-impact-status` (one of `unaffected` / `scope-narrowed` / `partial-superseded`), `priority` (one of `high` / `medium` / `low` / empty), `status` (active registry entries SHALL always carry `status: active`). The schema SHALL be documented in `openspec/backlog/README.md` for reader reference; no automated fence (e.g., `_check_followon_continuity` / `_check_srs_registry_consistency` / 4 类 cancel tag fence / `_validate_tombstone_consistency` / `_check_archived_md_append_only`) SHALL enforce schema integrity (round 1 codex P1-4 writeback: schema 描述保留作 reference,fence enforcement 整删随 finish_gate retire 一并消失;沿 design.md D3:目录保留 + 砍 fence)。Schema drift 由 user 自由维护,git history 提供 audit trail 替代 append-only fence。

#### Scenario: registry file exists with 8-field schema documented

- **GIVEN** the change `retire-forgeue-protocol-layer-fully` has shipped
- **WHEN** a reader opens `openspec/backlog/active.md` and `openspec/backlog/README.md`
- **THEN** `active.md` SHALL contain entries each carrying the 8 schema fields (priority MAY be empty)
- **AND** `README.md` SHALL document the 8-field schema as reader reference
- **AND** **no automated fence** SHALL run on schema integrity (`_check_followon_continuity` / `_check_srs_registry_consistency` / 4 类 cancel tag fence / `_validate_tombstone_consistency` / `_check_archived_md_append_only` 全部随 `forgeue_finish_gate.py` retire 整删)
- **AND** SRS §7.3 TBD table SHALL carry a cross-link header note pointing to `openspec/backlog/active.md` for workflow-protocol + capability-boundary class follow-ons

#### Scenario: archived.md tombstone schema documented but append-only by convention only

- **GIVEN** `openspec/backlog/archived.md` contains tombstone entries each with 4 fields (`archived_at_commit` / `archived_in_change` / `cancellation_reason` / `registry_entry_snapshot`)
- **WHEN** a user manually edits `archived.md` (e.g., 修 typo / 补漏 entry / 删错 entry)
- **THEN** **no fence** SHALL block the edit; git history(`git log --follow openspec/backlog/archived.md`)是 audit trail 唯一来源
- **AND** README.md SHALL note "tombstone is append-only by convention, enforced by git review only (no programmatic fence post-`retire-forgeue-protocol-layer-fully`)"
