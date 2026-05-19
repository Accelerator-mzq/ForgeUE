## Why

60 天 audit 数据(business-track 13 changes / protocol-track 8 self-modify changes / hybrid-track 3 recent changes)证明 ForgeUE 自家协议层在 produce 协议自我治理 > 业务价值。具体证据:

- **Business track**:`finish_gate` BLOCKER 跨 11 个 archived business change 触发率 = 0;76 finding 中 14 个是 PROTO-SELF;47/51 BUS-BUG 由 codex review hook 抓到(协议自家 cross-check ## D 独立 verify 边际仅 ~2-3 DES-GAP / 13 changes)。
- **Protocol track**:5 个 ADR-level change ship→retire 平均 lifetime 0.5 天(ADR-011 / ADR-012 / ADR-013 / ledger-binding 平均 0-1 天就 retire);82+ finding ~98% 协议自身 / ~2% 业务;ForgeUE 业务代码净输出 0 行。
- **Hybrid track**:`centralize-followon-backlog-registry` 留 5 个新协议 follow-on 给下一 change(完美 self-referential closure);business value=0;`enforce-subagent-discipline-cascade` ship 一天后即决定 retire。

**核心结论**:Superpowers + codex CLI 已是 BUS-BUG capture 主力;ForgeUE-specific 协议层独立增量 = 2-3 DES-GAP / 13 changes,代价是 14 PROTO-SELF + 平均 2-3 倍 review round + 9 份 placeholder evidence 每 trivial change。整 retire 切换到 OpenSpec(contract anchor)+ Superpowers(evidence 流)+ codex CLI(opt-in via convention)三层精简栈。

## What Changes

- **BREAKING** retire 9 个 `/forgeue:change-*` slash 命令(`.claude/commands/forgeue/*`):change-status / change-plan / change-apply / change-apply-subagent / change-apply-direct / change-debug / change-verify / change-review / change-doc-sync / change-finish。
- **BREAKING** retire 2 个 sister skill(`.claude/skills/forgeue-integrated-change-workflow/` + `.claude/skills/forgeue-doc-sync-gate/`)。
- **保留** `.claude/skills/subagent-driven-discipline/SKILL.md`(round 1 codex writeback 后 partial-dispute codex P1-1):该 SKILL 实际是 **generic universal Subagent Discipline**(L15 "Universal controller-side discipline for `superpowers:subagent-driven-development` workflows" / L22 "任何项目使用 ... 时"),可独立给任何 superpowers 用户使用;`author: forgeue` 只是 origin label 不是 binding。ForgeUE-specific hard-wire 在 9 命令 / 8 工具 / 12-key frontmatter retire 时自然消失,SKILL 自身保留作 generic advice。详见 `design.md` D11。
- **BREAKING** retire 8 个 stdlib 工具(`tools/forgeue_*.py` + 配套测试 `tests/unit/test_forgeue_*.py`):forgeue_finish_gate / forgeue_change_state / forgeue_verify / forgeue_doc_sync_check / forgeue_subagent_budget / forgeue_skill_cascade_check / forgeue_enum_cross_ref_check / forgeue_env_detect。
- **BREAKING** retire 3 个协议文档:`docs/ai_workflow/forgeue_integrated_ai_workflow.md`(整删)+ `docs/ai_workflow/forgeue_quickstart.md`(整删)+ `docs/ai_workflow/README.md` Documentation Sync Gate 段(段删)。
- **BREAKING** retire 协议机制:cross-check A/B/C/D 模板 + 12-key audit frontmatter(随 finish_gate 整删)+ 4 类 DRIFT taxonomy + writeback 协议 + Lean Apply Mode 9 placeholder + skill cascade check + subagent-driven-discipline 28-subtype 强制 + budget tracker fence。
- **BREAKING** retire backlog 守门 fence(只砍 fence,**目录保留**):`_check_followon_continuity` / `_check_srs_registry_consistency` / 4 类 cancel tag fence / tombstone consistency fence / archived.md append-only fence / 13th `followon_continuity` frontmatter 字段。
- 精简 CLAUDE.md "OpenSpec 工作流" / "Follow-on Backlog Registry" / "ForgeUE Integrated AI Change Workflow" 三大段到 ≤ 30 行(只留:OpenSpec 何时用 + Superpowers 流程参考 + codex 调用 convention)。
- 加 CLAUDE.md 一行 strong convention:**"design 阶段先跑 `/codex:adversarial-review`,final review 跑 `/codex:review --base main`"**(preserve audit ~30-40% latent smell catch,沿 cluster-2 类 cross-archive scope 业务 catch leverage)。
- 13 个 active workflow-protocol follow-on 留在 `openspec/backlog/active.md` 自然演化(**不**转 GitHub Issues),大半未来按需 `cancelled-not-applicable: scope-changed`。

**保留不动**(沿"归档即冻结"+ 业务 / 长期权威分层):
- `openspec/changes/archive/*` 24 changes evidence(沿 D-ArchivedReplayCompat)
- `openspec/specs/*` 8 capability spec(contract reference 仍保留;本 change 修改 2 个 spec 的 retire 段:见下)
- `openspec/backlog/{active,archived,README}.md` schema 与 5 个 tombstones audit trail
- `docs/{requirements,design,testing,acceptance}/` 五件套(SRS / HLD / LLD / test_spec / acceptance_report)
- `src/framework/*` ForgeUE 业务运行时
- Superpowers 全套 skill(走 upstream Anthropic plugin 维护)
- codex CLI plugin(opt-in via CLAUDE.md convention)

## Capabilities

### New Capabilities

(无新增 capability。本 change 是 retire 性质,主要修改既有 capability 的协议层 requirement。)

### Modified Capabilities

- `examples-and-acceptance`:retire 全部 ForgeUE 协议层 Requirements(5+ 个 Requirement 段:12-key frontmatter / cross-check protocol / `/forgeue:change-*` 命令系列 / forgeue_finish_gate fence / forgeue_subagent_budget tracker / Preflight Worktree / parallel dispatch / runtime enforcement protocol version / task granularity / dispatch wrapper / dispatch ledger / 等),回归到原始 OpenSpec 工作流 + Superpowers evidence 流 + codex convention 描述。
- `probe-and-validation`:retire `Requirement: forgeue_verify.py Level 2 ComfyUI steps SHALL exercise the agent CLI subprocess path` 段(因 `forgeue_verify.py` 整删);Level 2 验证由用户手工跑 `python -m pytest tests/integration/test_p*.py` + `examples/comfy_local_smoke*.json` smoke 替代,要求文档化到 `docs/testing/test_spec.md`。

## Impact

- **Affected files (delete)**:~50+ 文件
  - `.claude/commands/forgeue/*.md`(9 命令模板)
  - `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` + `.claude/skills/forgeue-doc-sync-gate/SKILL.md`
  - `tools/forgeue_*.py`(8 工具)+ `tests/unit/test_forgeue_*.py`(配套测试,`subagent-driven-discipline` skill ForgeUE companion 部分)
  - `docs/ai_workflow/forgeue_integrated_ai_workflow.md` + `docs/ai_workflow/forgeue_quickstart.md`(2 个协议文档整删)
- **Affected files (modify)**:
  - `CLAUDE.md`(三大段精简到 ≤ 30 行 + 加 codex convention 一行)
  - `AGENTS.md`(精简 ForgeUE 协议层引用 — `/forgeue:change-*` 命令矩阵 + `forgeue_finish_gate` + `12-key frontmatter` + `Documentation Sync Gate` 等;round 1 codex writeback P1-2 accept)
  - `README.md`(精简 9 命令矩阵 + Documentation Sync Gate / OpenSpec 工作流段;round 1 codex writeback P1-2 accept)
  - `docs/ai_workflow/README.md`(Documentation Sync Gate 段删)
  - `openspec/specs/examples-and-acceptance/spec.md`(retire 协议层 Requirements;`Centralized follow-on backlog registry` 改 REMOVED→MODIFIED 保留最小 schema,round 1 codex writeback P1-4 accept)
  - `openspec/specs/probe-and-validation/spec.md`(`forgeue_verify.py Level 2` 改 REMOVED→MODIFIED 保留工具无关 subprocess-path validation contract,round 1 codex writeback P1-5 accept)
  - `docs/testing/test_spec.md`(Level 2 验证章节加 user 手工跑命令矩阵;round 1 codex writeback P1-5 accept,从 P9 optional 升 P3 必做)
- **Affected files (unchanged)**:`src/framework/*` / `docs/{requirements,design,testing,acceptance}/*` / `openspec/changes/archive/*` / `openspec/backlog/{active,archived,README}.md` / `tests/integration/*` / `examples/*` / `probes/*`
- **量级估计**:LOC delete ~9500(比 retire-parallel-and-worktree-fully 5066 大近 2 倍);文件 delete ~50+;工作流命令 9 → 0 / 自家工具 8 → 0 / 自家 skill 2 → 0 / 自家协议文档 3 → 0;CLAUDE.md retire 后 ~30 行(原 ~200 行 ForgeUE 协议段)。
- **Sunk cost 显式 accept**:`centralize-followon-backlog-registry`(2026-05-07 ship,3 天前)+ `enforce-subagent-discipline-cascade`(2026-05-08 ship,2 天前)按"激进全面转 Superpowers"决策一并 retire。
- **此 change 自身就是新工作流的第一个 dogfood sample**:不走自家 9 命令(因这些命令本身就是 retire 目标),走 OpenSpec `/opsx:propose` + Superpowers writing-plans + subagent-driven-development + codex CLI opt-in。
