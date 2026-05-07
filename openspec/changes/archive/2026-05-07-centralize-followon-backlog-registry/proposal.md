## Why

ForgeUE 当前没有集中 follow-on 记录位置 — backlog 分散在 8 个位置(`SRS §7.3 TBD 表` / 各 archived change `tasks.md P11/P12 follow-on tracking` / `proposal.md Out of Scope` / `design.md Alternatives considered` / `verification/baseline.md Followup tracking` / `notes/retrospective.md §3.4` / `docs/design/LLD.md inline` / `CHANGELOG.md`),靠"新 change archive 时人工沿前一 change 的 P11/P12 tracking 抄"链式继承,链一断就漏。本会话 user 提问"还有哪些 follow-on"时,Claude 第一轮漏 6 项实证链断 risk(`enhance-workflow-automation-handoff-persistence` / `add-forgeue-brainstorm-stage` / `enhance-workflow-automation-finishing-branch` / `enhance-workflow-automation-final-review-fence-strictness` / `enhance-workflow-automation-v2-fence-hardening` / `analyze-superpowers-skills-openspec-integration-gaps`),retire-parallel-and-worktree-fully 后回到 v1 advisory baseline 后 backlog continuity 是 v1 应该有的 hygiene 但被漏。

## What Changes

- **新增** 集中 registry `openspec/backlog/active.md` + `openspec/backlog/archived.md`(双源 + 互链架构,沿 user 拍板决策点 1(b);**round 1 codex F1 inline writeback**:active.md 升级为 hard source-of-truth,archive 阶段 fence 守门 git diff 增删改 + tombstone protocol):registry 收 archive-tracking 类(implementation-deferred 9 项 + capability-boundary 6 项),`SRS §7.3 TBD` 仍是需求层 backlog(9 项),两边 cross-link 不重复。Schema:`id` / `source archived change + tasks.md 锚点` / `description` / `trigger condition` / `retire-impact-status` / `category`(workflow-protocol / capability-boundary / requirements-tbd) / `priority` / `status`(active / inherited / cancelled-superseded / cancelled-not-applicable / cancelled-completed)。`archived.md` tombstone schema:`id` / `archived_at_commit`(git sha)/ `archived_in_change`(triggering change id)/ `cancellation_reason`(枚举值或 inherited→completed transition)。
- **新增** `tools/forgeue_finish_gate.py::_check_followon_continuity` blocker fence(沿 user 拍板决策点 2(c) + round 1 codex F1+F2 inline writeback;立场翻转 — 从 archived tasks.md 链式继承升级到 active.md 双源 self-truth + cancel strict validation):
  - **active.md self-truth diff**:archive 阶段 `git diff` active.md 上一 archive commit 与当前版本的增删改;删除/取消必须有 archived.md append-only tombstone(2 字段 `id` + `archived_at_commit` + `archived_in_change`)
  - **archived tasks.md backwards-compat 兜底**:同时扫前一 change `tasks.md P11/P12/Pn (follow-on tracking)` unchecked 项,确保链式继承不断
  - **本 change 必须显式以下其一才能 archive**:(a)`inherited`(标 `status: inherited`)/(b)`cancelled-superseded` 配新 change ID,fence 校验 `Path("openspec/changes/<id>").exists() OR Path("openspec/changes/archive").glob("*-<id>")`/(c)`cancelled-not-applicable` 配 reason,fence 校验 reason 前缀来自 5 类 enum(`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`)+ 允许补充 free-form 文字 / (d)`cancelled-completed` 配 commit,fence 校验 `git rev-parse --verify` exit 0(commit 存在性,不校验触达,留 follow-on)
- **新增** evidence frontmatter 字段 `followon_continuity` dict,4-list 结构:`inherited` list / `cancelled_superseded` list of `{id, supersedes}` / `cancelled_not_applicable` list of `{id, reason}` / `cancelled_completed` list of `{id, commit}`;仅 archive 阶段(`/forgeue:change-finish` 触发)强制,其它 evidence 类型可空。**[round 1 codex F4 inline writeback]**
- **新增** 一次性 backfill 23 active follow-on 项(沿 user 拍板决策点 3(a);**adapted for fix-finish-gate-archived-replay-compat merge `88a8aec`** — 原 9 workflow-protocol 中 2 项已 closed 进 archived.md;**P0.1 实测加 1 项 `fix-cross-check-format-test-enum-extension`** — retire P5 verify_report.md 标过但未进 retire P12 tracking 的 systemic gap 案例,正是 centralize 协议要 catch 的漏检场景,本 change dogfood 自暴露 + 自纳入):**8** archive tracking + 9 SRS TBD pointer + 6 多模态 capability boundary。详见本 change `tasks.md` P0 backfill 段。
- **修改** `.claude/commands/forgeue/change-finish.md`:`Preflight` 段加 followon continuity check 步骤,调 aggregate `forgeue_finish_gate.py --change <id>`(沿既有 fence dispatch loop;两 fence `_check_followon_continuity` + `_check_srs_registry_consistency` 注册后 build_report 自动跑;**round 3 codex F1-r3 inline writeback** — 删原"专用 flag `--check-followon-continuity`"避免 argparse 失败 + 入口分叉,沿既有 aggregate 调用模式)。
- **修改** `.claude/commands/forgeue/change-status.md`:`Output Format` 段加 `### Followon Backlog` section(列本 change 继承 + cancel 计数 + 与 active registry 的差异)。
- **修改** `.claude/commands/forgeue/change-apply-{subagent,direct}.md`:evidence frontmatter 模板加 `followon_continuity` 字段(可空 — 仅 archive 阶段强制)。
- **修改** `tools/forgeue_change_state.py`:加 `--list-followon-inherited` / `--list-followon-cancelled` 子命令,扫本 change 各 evidence frontmatter `followon_continuity` 字段汇总(供 `change-status` 命令调用)。
- **新增** 测试:`tests/unit/test_forgeue_finish_gate.py` 加 `_check_followon_continuity` fence 测试(7-10 case 覆盖:inherited PASS / cancelled-superseded PASS / cancelled-not-applicable PASS / cancelled-completed PASS / 缺继承声明 BLOCKER / supersedes ref 失效 BLOCKER / not-applicable reason 缺失 BLOCKER 等)。
- **新增** 测试:`tests/unit/test_followon_registry.py` 检验 registry schema parse + archived registry append + cross-link 一致性 + active.md self-diff fence + tombstone schema validation + SRS↔registry consistency。
- **新增**(round 1 codex F3 inline writeback)`tools/forgeue_finish_gate.py::_check_srs_registry_consistency` blocker fence:archive 阶段校验 active.md 中 `category: requirements-tbd-pointer` entries 集合 == SRS §7.3 active TBD 集合(等价集合校验);SRS §7.3 状态字段从 active(❌/⚠️ baseline)变 ✅(complete)→ registry pointer 必须同步 cancelled-completed 移到 archived.md;SRS §7.3 新增 TBD → registry 必须加对应 pointer entry。

## Capabilities

### New Capabilities

(无新 capability — registry 是 ForgeUE workflow 自家 meta-tooling layer,沿 archived `retire-parallel-and-worktree-fully` 同模式归入 `examples-and-acceptance` modified)

### Modified Capabilities

- `examples-and-acceptance`:加 follow-on backlog continuity 协议(active / archived registry 双文件 + `_check_followon_continuity` blocker fence + evidence frontmatter `followon_continuity` 字段);capability 行为新增"跨 change follow-on continuity 守门"层。

## Impact

**代码新增**(~400-600 LOC):
- `tools/forgeue_finish_gate.py`:新 fence `_check_followon_continuity`(~80 LOC)+ helper 解析前一 change tasks.md P11/P12 段(~50 LOC)
- `tools/forgeue_change_state.py`:新子命令 `--list-followon-inherited` / `--list-followon-cancelled`(~60 LOC)
- `tests/unit/test_forgeue_finish_gate.py`:新 fence 测试(~150 LOC)
- `tests/unit/test_followon_registry.py`:registry schema 测试(~100 LOC)

**文档新增**(~24 entries):
- `openspec/backlog/active.md`(~250-400 LOC,24 项 backfill + schema header + cross-link)
- `openspec/backlog/archived.md`(空骨架,等待第一个 cancelled / completed 项)
- `openspec/backlog/README.md`(~80 LOC,registry 协议说明 + 与 SRS §7.3 TBD 双源关系)

**命令 / 配置接口**:
- `/forgeue:change-finish` Preflight 加 followon continuity check(blocker:无显式继承/cancel 声明 → archive 阻断)
- `/forgeue:change-status` Output Format 加 Followon Backlog section
- `/forgeue:change-apply-{subagent,direct}` evidence frontmatter 模板加 `followon_continuity` 字段

**文档同步**(10 文档 Documentation Sync Gate scope):
- `CLAUDE.md` 加 §`Follow-on Backlog Registry` 简短段(协议入口 + 链接 registry)
- `AGENTS.md` 同步
- `README.md` 加 § follow-on tracking section(快速链接)
- `CHANGELOG.md` 加本 change entry
- `docs/ai_workflow/README.md` §4 加 followon continuity 说明(与 Documentation Sync Gate 并列的 archive-stage 守门)
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md` §B.4 / §E 加 `followon_continuity` evidence 字段说明
- `docs/ai_workflow/forgeue_quickstart.md` 加 followon backlog 查询 step
- `docs/requirements/SRS.md` §7.3 TBD 表加 cross-link 至 registry(双源互链)
- `docs/testing/test_spec.md` 加新测试 case 索引
- `docs/acceptance/acceptance_report.md` ADR 表加 ADR-014(若需要)或 update 状态

**Backfill scope**(本 change 一次性,sync with fix-finish-gate-archived-replay-compat `88a8aec`):
- **22 active follow-on 项**,见 `tasks.md` P0 backfill 段。详细分类:
  - **Workflow protocol**(8 项;原 9 - 2 closed by `88a8aec` + 1 P0.1 dogfood 暴露 `fix-cross-check-format-test-enum-extension`):`fix-video-export-path-split-d12-violation` / `fix-run-import-skipped-filter-permission-only` / `enhance-workflow-automation-handoff-persistence` / `add-forgeue-brainstorm-stage` / `enhance-workflow-automation-finishing-branch` / `enhance-workflow-automation-final-review-fence-strictness` / `analyze-superpowers-skills-openspec-integration-gaps` / `fix-cross-check-format-test-enum-extension`
  - **Requirements TBD pointer**(9 项):TBD-001 / TBD-002 / TBD-003 / TBD-004 / TBD-005 / TBD-010 / TBD-011 / TBD-012 / TBD-013(每项 1 行 pointer 至 SRS §7.3,不复制内容)
  - **Capability boundary**(6 项):`audio-metadata-parser` / `video-metadata-parser` / `comfy-video-webm-adoption` / `comfy-video-v2v-adoption` / `comfy-video-image-sequence-adoption` / `video-bmff-largesize-support`
- **3 archived.md 首批 tombstone**(协议示范 + 历史 trace):
  - `enhance-workflow-automation-v2-fence-hardening` cancelled-superseded by `enhance-workflow-automation-ledger-binding`(commit `8a42c71`)
  - `fix-finish-gate-section-regex-for-p-prefixed` cancelled-completed: `88a8aec`(closed by fix-finish-gate-archived-replay-compat)
  - `fix-openspec-validate-archived-change-support` cancelled-completed: `88a8aec`(同上;短期 mitigation skip 路径已实施,upstream openspec CLI patch 留 follow-on `enhance-openspec-cli-archived-change-support`)

**不影响**:
- archived change 不动(归档冻结原则;不重写历史 tasks.md P11/P12 段)
- SRS §7.3 表不动(双源互链,沿决策 1(b);仅加 cross-link 至 registry)
- openspec 上游 CLI 不改

**Trade-off acknowledgement**:
- blocker fence(沿决策 2(c))会增加 archive 摩擦 — 用户可接受,因为这正是补"链断 risk"的目的;cancel 协议(`cancelled-superseded` / `cancelled-not-applicable` / `cancelled-completed`)提供合规出口。
- 双源(沿决策 1(b))保留 SRS §7.3 语义层级 — 代价是仍有两个位置可查,但都结构化 + 互链;比强行单源污染需求层语义更优。
