## Context

ForgeUE 工作流体系自 2026-04-27 `fuse-openspec-superpowers-workflow` 以来形成 OpenSpec(契约锚点)× Superpowers(evidence 生成器)× codex-plugin-cc(stage cross-review hook)中心化 fusion 架构。期间历经 4 轮 workflow automation 迭代(`runtime-enforcement` ADR-011 / `executable-enforcement` ADR-012 / `restore-consent-gate` ADR-013 / `ledger-binding` v3),并于 2026-05-06 全部 retire(`retire-parallel-and-worktree-fully`)回到 ADR-010 baseline + v1 advisory 3 fence。

期间 follow-on backlog 沿 archived change `tasks.md P11/P12 (follow-on tracking)` 段链式继承 — 每个新 change archive 时人工沿前一 change 的 P11/P12 tracking 抄进自己的 P12,链一断就漏。本会话实测 user 提问"还有哪些 follow-on"时,Claude 第一轮全项目 grep 漏 6 项(详见 `proposal.md` Why);此 gap 实证链断 risk 持续存在。retire-parallel-and-worktree-fully 后 v1 advisory baseline 没有任何 backlog continuity 守门,本应是 v1 baseline 起就该有的 hygiene 但被漏。

User 拍板 A + C 组合(`openspec/backlog/active.md` 集中 registry + `_check_followon_continuity` blocker fence),并对 3 个 design 决策点(registry × SRS 关系 / fence 严格度 / backfill scope)选了 1(b) + 2(c) + 3(a)。

## Goals / Non-Goals

**Goals**:

- 提供单一可见的 follow-on backlog 集中位置(`openspec/backlog/active.md`),覆盖所有 archive-tracking 类 follow-on(implementation-deferred + capability-boundary)
- 提供 archive-stage blocker fence 守门 follow-on continuity — 新 change archive 时必须显式继承或 cancel 前一 change 的 unchecked follow-on
- 双源互链:registry 收 archive-tracking 类(15 项),SRS §7.3 仍是需求层 backlog(9 项),cross-link 不重复
- 提供 cancel 协议合规出口(`cancelled-superseded` / `cancelled-not-applicable` / `cancelled-completed`)避免 retire 类被卡死
- 一次性 backfill 24 active 项,registry 启用即满
- 沿 v1 advisory baseline 风格(blocker fence 是 archive 阶段唯一守门,不进 propose / plan / apply / verify 阶段)

**Non-Goals**:

- 不动 `SRS §7.3 TBD 表`(双源,沿决策 1(b);仅加 cross-link 至 registry)
- 不重写历史 archived change 的 `tasks.md P11/P12` 段(归档冻结原则)
- 不改 openspec 上游 CLI(沿 archived `fix-openspec-validate-archived-change-support` follow-on 标记本身;本 change 不解决 CLI 限制)
- 不引入 cryptographic / executable enforcement 层(沿 retire 后 v1 advisory baseline)
- 不强制 `priority` / `effort estimate` 字段(本 change scope 内 priority 字段允许空 — 评估机制留 follow-on,不阻塞 backfill)
- 不引入新 Superpowers / OpenSpec skill — 仅扩既有 `forgeue_finish_gate.py` + `forgeue_change_state.py` + 命令模板

## Decisions

### D-RegistrySchema(registry 文件 schema)

`openspec/backlog/active.md` 单文件,Markdown table-of-entries 形式。每条 entry 由 H3 标题 + 字段块组成:

```markdown
### `<followon-id>`

- **source**: `archived/<change-id>/tasks.md` § P12.X(若来自 SRS §7.3,改为 `docs/requirements/SRS.md` § 7.3 TBD-XXX)
- **description**: <1-2 句 description>
- **trigger**: <触发条件,何时启动 follow-on change>
- **category**: `workflow-protocol` | `capability-boundary` | `requirements-tbd-pointer`
- **retire-impact-status**: `unaffected` | `scope-narrowed` | `partial-superseded`(默认 `unaffected`)
- **priority**: `high` | `medium` | `low` | (空)
- **status**: `active`(active registry 永远只列 active 项)
```

**rationale**:Markdown 形式优先(沿 OpenSpec / ForgeUE 全文档 .md 风格;tools 解析有现成 helper);JSON / YAML 形式被拒(grep / 人读体验差;tools 解析便宜不是核心需求)。

**alternatives considered**:
- (A) 单 YAML 文件(machine-friendly,但 grep 难;sister change 用 .md 同款风格更一致)— 拒绝
- (B) 多 .md 文件(每条 follow-on 一文件,e.g. `openspec/backlog/active/<id>.md`)— 拒绝(24 项太碎,新 change 引用 / cross-check 难)
- (C) 单 .md(选)

### D-RegistryDualSource(与 SRS §7.3 双源 + 互链)

沿 user 拍板决策 1(b)。

- registry 收:archive-tracking 类(本会话整理 9 项 implementation-deferred + 6 项 capability-boundary = 15 项)
- SRS §7.3 仍收:requirements-tbd 类(TBD-001 / 002 / 003 / 004 / 005 / 010 / 011 / 012 / 013 共 9 项)
- registry 中加 9 个 `requirements-tbd-pointer` entry,每条 1 行 pointer 至 SRS §7.3 TBD-XXX(不复制内容)
- SRS §7.3 表加 cross-link header note:"集中 follow-on backlog 见 `openspec/backlog/active.md`(workflow-protocol + capability-boundary 类);本表是 requirements-tbd 类 backlog"

**rationale**:TBD 是需求层未决(评估期长 / 触发条件偏战略);follow-on 是已决 deferred(评估期短 / 触发条件偏战术)。强行单源会污染需求层语义。双源 + cross-link 提供最小化复用 — registry 启用即满,SRS 维护成本不变。

**alternatives considered**:
- (A) 单源(SRS §7.3 全迁入 registry)— 拒绝,SRS 是需求层文档,迁出有"语义降级"嫌疑
- (B) 双源 + 互链(选)
- (C) 全集进 registry,SRS §7.3 改成自动生成 view — 拒绝,加同步脚本复杂度;本 change scope 控制

### D-FenceStrictness(`_check_followon_continuity` blocker + cancel 协议 + strict ref validation)

沿 user 拍板决策 2(c) + **round 1 codex F1+F2 inline writeback**(2026-05-07;立场翻转 — 原"free-form trade-off"立场被 codex challenge 后接受 strict validation;原"扫 archived tasks.md 链式继承"立场被 codex challenge 后升级到 active.md self-truth 双源)。

- **active.md self-truth + archived tasks.md 双源**(round 1 F1):archive 阶段(`/forgeue:change-finish`)触发:
  - 主源:`git diff <last_archive_commit> HEAD -- openspec/backlog/active.md` — 检测增删改;active.md 中 entry 删除 OR `status` 字段变非 active → 必须有对应 `openspec/backlog/archived.md` append-only tombstone 行
  - 兜底源:扫前一 archived change(按 archived 目录最新创建日期 + 最新 commit 配合判定)的 `tasks.md` 内 `## P11` / `## P12` / 其它 `Pn (follow-on tracking)` section 的 unchecked `- [ ]` 项
- 本 change 必须在 `tasks.md` 同名 P-section 显式以下其一(对每个 active.md 增删改 + 兜底源 unchecked 项):
  - **inherited**:`- [x] P12.X (follow-on tracking):**<followon-id>**(沿前一 change 继承)— ...`(checkbox checked + 显式声明继承)
  - **cancelled-superseded**:`- [x] P12.X (follow-on tracking):**<followon-id>** [cancelled-superseded by <new-change-id>] — ...`;**fence 校验**(round 1 F2):`<new-change-id>` 必须解析存在 — `Path("openspec/changes/<id>").exists() OR Path("openspec/changes/archive").glob("*-<id>")` 任一为真,否则 BLOCKER `cancel_ref_not_found`
  - **cancelled-not-applicable**:`- [x] P12.X (follow-on tracking):**<followon-id>** [cancelled-not-applicable: <reason>] — ...`;**fence 校验**(round 1 F2):`<reason>` 必须前缀来自 5 类 enum:`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`;允许冒号后补充 free-form 文字(如 `[cancelled-not-applicable: out-of-scope (本 change 不修无关 bug)]`),否则 BLOCKER `cancel_reason_not_in_enum`
  - **cancelled-completed**:`- [x] P12.X (follow-on tracking):**<followon-id>** [cancelled-completed: <commit-ref>] — ...` OR `[cancelled-completed: <commit-ref> evidence: <path>]`(round 2 F3-r2 fix:加 `evidence:` escape hatch);**fence 校验**(round 1 F2 + round 2 F3-r2):`git rev-parse --verify` 存在性 + `git diff-tree --no-commit-id --name-only -r` 触达文件 vs follow-on `source` / `contract_refs` 集合 intersect;非空 → PASS;否则需 `evidence: <path>` 显式 escape hatch 且 `Path.exists()` → PASS;都不通过 → BLOCKER `cancel_commit_does_not_touch_followon_or_provide_evidence`
- 无声明 → fence BLOCKER + 列出未声明 follow-on id;archive 阻断
- **同 archive cycle 原子迁移**(round 1 F1):active.md → archived.md 必须在同一 archive cycle 完成,不能留到下一 archive(否则 tombstone 缺失);finish_gate 调用 archive 前必须见到所有 cancelled-* status 已迁移
- registry 中对应 entry status 同步更新(inherited status 在 active.md 不变;cancelled-* 移到 archived.md tombstone)

**rationale**:advisory 太松(本就是为补"链断"的洞,advisory 跟现状没区别);blocker + cancel 协议既守门又灵活;round 1 F2 strict validation 防止 controller hand-edit 写虚假 cancel reason 绕过 fence(若仅 syntactic seal,cancel 路径沦为 controller bypass 漏洞 — 本 change 立项目标是 systemic gap fix,不是换文档位置)。reason 5 类 enum 沿 retire-parallel-and-worktree-fully + ledger-binding + executable-enforcement 期实证典型 cancel 场景:`retire-superseded`(retire 期 P12.8 v2-fence-hardening 模式)/ `out-of-scope`(retire P5 codex F3+F4 模式)/ `scope-changed`(本 change 实施期 scope 边界变化)/ `obsolete`(架构演化使 follow-on 失效)/ `infeasible`(技术不可行)。

**alternatives considered**:
- (A) advisory(沿 v1 风格)— 拒绝(无 enforce 等于没改)
- (B) blocker(无 cancel 协议)— 拒绝(retire 类被卡死)
- (C) blocker + cancel 协议 + free-form reason — 拒绝(round 1 codex F2 challenge:syntactic seal 让 controller hand-edit drift 仍可绕过)
- (D) blocker + cancel 协议 + strict validation(选;round 1 F2 inline writeback)
- commit 触达校验:**round 2 F3-r2 拉回 current scope**(原 round 1 留 follow-on 决策被 codex round 2 challenge:任意 doc-only / unrelated commit 都通过 fence 是语义绕过非 ergonomics;Claude 接受 strict commit-touches + escape hatch 折中;follow-on `tighten-cancel-completed-commit-touches-validation` 标 cancelled-completed-by-this-change)

### D-FenceLocation(fence 触发位置:archive only)

`_check_followon_continuity` 仅在 `/forgeue:change-finish` 命令的 Preflight 阶段触发(archive 前 finish_gate 综合扫描的一部分);**不**在 propose / plan / apply / verify / review / doc-sync 阶段触发。

**rationale**:propose 阶段 backlog 状态尚未 finalize(用户在 brainstorming);apply 阶段 backlog 是动态(继承决定可能延期到 archive 前才定);archive 是唯一稳定时机。沿 v1 advisory 3 fence 同款思路(advisory fence 也都在 archive 阶段)。

### D-BackfillScope(22 项一次性 backfill;adapted for fix-finish-gate-archived-replay-compat merge `88a8aec`)

沿 user 拍板决策 3(a)。**Sync update 2026-05-07**:fix-finish-gate-archived-replay-compat 合入 dev(commit `88a8aec`)关闭原 backfill list 中 2 项;本 change `tasks.md` P0 phase 完成 22 项 active backfill + 3 项 archived.md 首批 tombstone:

- **Workflow protocol active**(7 项,缩自原 9 项;新建 entry 入 active.md):
  1. `fix-video-export-path-split-d12-violation`(retire P5 codex F3)
  2. `fix-run-import-skipped-filter-permission-only`(retire P5 codex F4)
  3. `enhance-workflow-automation-handoff-persistence`(enhance-workflow-automation P5 round 2 F6)
  4. `add-forgeue-brainstorm-stage`(adopt-subagent-driven-development)
  5. `enhance-workflow-automation-finishing-branch`(runtime-enforcement P11.6)
  6. `enhance-workflow-automation-final-review-fence-strictness`(executable-enforcement P12.7;场景变化但 gap 仍存)
  7. `analyze-superpowers-skills-openspec-integration-gaps`(restore-consent-gate P12.4;scope 6→5,剔 dispatching-parallel-agents)
- **Requirements TBD pointer**(9 项,1 行 pointer):TBD-001 / TBD-002 / TBD-003 / TBD-004 / TBD-005 / TBD-010 / TBD-011 / TBD-012 / TBD-013
- **Capability boundary**(6 项,新建 entry):`audio-metadata-parser` / `video-metadata-parser` / `comfy-video-webm-adoption` / `comfy-video-v2v-adoption` / `comfy-video-image-sequence-adoption` / `video-bmff-largesize-support`

**3 项 archived.md 首批 tombstone**(协议示范 + 历史 trace,本 change 实施期一并写入 archived.md;直接 append 不经过 active.md):

| id | cancellation_reason | archived_at_commit | archived_in_change |
|---|---|---|---|
| `enhance-workflow-automation-v2-fence-hardening` | cancelled-superseded by enhance-workflow-automation-ledger-binding | `8a42c71` | enhance-workflow-automation-ledger-binding |
| `fix-finish-gate-section-regex-for-p-prefixed` | cancelled-completed: 88a8aec | `88a8aec` | fix-finish-gate-archived-replay-compat |
| `fix-openspec-validate-archived-change-support` | cancelled-completed: 88a8aec | `88a8aec` | fix-finish-gate-archived-replay-compat |

**注**:fix-finish-gate-archived-replay-compat 实际是短期 mitigation skip 路径(F-B);upstream openspec CLI 长期 patch 留 follow-on `enhance-openspec-cli-archived-change-support`(本 change 实施期不引入,留前一 archived change 的 doc-sync report 提及)。

### D-EvidenceFrontmatterField(`followon_continuity` 字段;canonical 4-list schema)

**round 1 codex F4 inline writeback**(2026-05-07;统一 schema):

evidence frontmatter 加 conditional 字段 `followon_continuity`,**canonical 4-list 结构**(覆盖原 proposal.md 早期 3-key dict 草案 — F4 finding 实证 schema mismatch 会让实施期 parser/template 互不兼容):

```yaml
followon_continuity:
  inherited: [<followon-id>, ...]            # 继承前一 change 的 follow-on
  cancelled_superseded: [{id: ..., supersedes: <new-change-id>}, ...]
  cancelled_not_applicable: [{id: ..., reason: ...}, ...]
  cancelled_completed: [{id: ..., commit: <ref>}, ...]
```

**触发**:仅在 archive-stage evidence(`finish_gate_report.md` / `superpowers_review.md` final / `retrospective.md`)required;其它 evidence 类型可空。

**rationale**:沿 12-key audit frontmatter 现有 conditional pattern(`drift_decision` / `writeback_commit` / `drift_reason` / `reasoning_notes_anchor` 仅 `aligned_with_contract: false` 时 required);本字段仅 archive 阶段 required。4-list 结构(vs 3-key dict count 草案)优势:每条 cancellation 可独立验证 supersedes/reason/commit ref + finish_gate fence 能直接 iterate 校验,而 count 形式丢失 ref 细节无法验证。

### D-FenceParseStrategy(fence 实现:active.md self-diff + archived tasks.md 兜底 + cancel ref strict validation)

**round 1 codex F1+F2 inline writeback**(2026-05-07;立场翻转;**adapted for fix-finish-gate-archived-replay-compat 88a8aec merge** — latest archive 是 micro-bugfix 无 P12 section,fence 阶段 2 退化为 no-op;阶段 1 active.md self-truth 主源仍守门 retire 留下的仍 active follow-on 不漏,该 change 实测验证架构):

`_check_followon_continuity` 实现走 stdlib-only(沿 ForgeUE 8 工具同款约束),加 git subprocess 调用(沿 finish_gate 既有 git 调用模式);分 4 阶段:

**阶段 1 — active.md self-diff(主源,round 1 F1 + round 2 F1-r2 fix)**:

> **round 2 F1-r2 fix**(2026-05-07):baseline 不能用 `git log -1 -- active.md`(active.md 最新 path commit)— controller 早期 commit 删 entry 后该 commit 即 baseline,后续 diff 为空,已提交删除被漏检。改用**上一 archive commit**作 baseline(沿 last_archive_commit 正确语义)。

1. `_find_latest_archived_change()` 返回 `openspec/changes/archive/<YYYY-MM-DD>-<id>/` Path(沿 D-FenceParseStrategy 阶段 2 同款 helper 复用)
2. `subprocess.run(["git", "log", "-1", "--format=%H", "--", str(latest_archived_dir)])` 取该 archive 目录最近 touched commit(即上一 ship 的 squash merge commit)作 `<baseline_sha>`
3. `subprocess.run(["git", "show", "<baseline_sha>:openspec/backlog/active.md"])` 读 baseline 版本内容(若 active.md 在 baseline 不存在 — 即首次启用本协议 — 退化为空 dict)
4. 解析当前版本 + baseline 版本各自 H3 entries + status 字段(用 `_parse_registry_md` helper,新写;沿 既有 `_parse_yaml_subset` 同款 stdlib-only 风格)
5. 计算 entry-set diff:added / removed / status_changed
6. 对每个 removed / status_changed-to-cancelled-* entry,在 archived.md 中查 tombstone 行 + 解析 `registry_entry_snapshot` JSON 校验**5 项一致性**(round 2 F2-r2 fix):
   - `id` 与 H3 标题匹配 + 与原 active.md entry id 一致
   - `snapshot` 是 valid JSON object 且含 8 schema 字段(`id` / `source` / `description` / `trigger` / `category` / `retire-impact-status` / `priority` / `status`)
   - `snapshot` 字段值与 baseline active.md 中该 entry 一致(防 controller 写错快照)
   - `archived_in_change` 等于当前 change id
   - `cancellation_reason` 与本 change tasks.md 中该 entry cancel tag 类型 + ref 一致
7. 任一不一致 → BLOCKER + 列具体不一致字段(沿 v1 advisory fence 出错信息风格)

**阶段 2 — archived tasks.md 兜底源**:
1. 找 `openspec/changes/archive/` 下最新 change(沿 archive 目录命名 `YYYY-MM-DD-<id>` + git log 最新 archive commit 双重锁定)
2. 解析其 `tasks.md` 内 `## P11` / `## P12` / 其它 `Pn (follow-on tracking)` section 的 `- [ ]` `<followon-id>` 提取
3. 与本 change `tasks.md` 同名 section 的 checkbox 状态 + 行内 cancel tag 比对;缺漏 → BLOCKER `archived_followon_not_declared_<id>`

**阶段 3 — cancel ref strict validation(round 1 F2,对每个 cancelled-* declaration)**:
1. **cancelled-superseded**:解析 `[cancelled-superseded by <new-change-id>]` tag 提取 id;`Path("openspec/changes/<id>").exists() OR Path("openspec/changes/archive").glob("*-<id>")` 任一 → PASS;否则 BLOCKER `cancel_ref_not_found_<id>_superseded_by_<bad-ref>`
2. **cancelled-not-applicable**:解析 `[cancelled-not-applicable: <reason>]` tag 提取 reason 第一 token(冒号到第一空格 / 行尾 / 括号);match 5 类 enum → PASS;否则 BLOCKER `cancel_reason_not_in_enum_<id>_got_<bad-reason>`
3. **cancelled-completed**(round 1 F2 + round 2 F3-r2 fix):tag 格式扩展为 `[cancelled-completed: <commit-ref>]` OR `[cancelled-completed: <commit-ref> evidence: <path>]`;校验顺序:
   - **Step 3.1**:解析 commit-ref 子段;`subprocess.run(["git", "rev-parse", "--verify", "<commit-ref>"])` exit 0 → 进 step 3.2;否则 BLOCKER `cancel_commit_not_found_<id>_got_<bad-ref>`
   - **Step 3.2**:`subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "<commit-ref>"])` 取 commit 触达文件集合 `touched_files`
   - **Step 3.3**:解析 follow-on entry 的 `source` 字段 + `contract_refs` 字段(从 active.md / archived.md 当时 entry 状态取);构成 `relevant_paths` 集合
   - **Step 3.4**:若 `touched_files ∩ relevant_paths ≠ ∅` → PASS(commit 触达 follow-on 主路径)
   - **Step 3.5**:否则解析 tag 是否含 `evidence: <path>` 子段;`Path("<path>").exists()` → PASS(escape hatch:cross-cutting commit 显式 evidence 路径)
   - **Step 3.6**:都不通过 → BLOCKER `cancel_commit_does_not_touch_followon_or_provide_evidence_<id>_got_<bad-ref>`

**阶段 4 — 输出汇总**:全 PASS → fence exit 0;任一 BLOCKER → exit 2 + 列所有 BLOCKER reason(沿 v1 advisory fence 出错信息风格)

**rationale**:与既有 forgeue 工具栈一致(stdlib-only / Markdown 解析复用 helper / git subprocess 沿 finish_gate 既有调用 / blocker 输出风格);避免引入新依赖。git diff 主源 + archived tasks.md 兜底源双重防漏(F1 防 active.md hand-edit;archived tasks.md 兜底防本 change 没人记得查 active.md 也能从 archived tasks.md 链补到);cancel ref strict validation 用 stdlib-only Path/git subprocess + reason enum O(1) lookup,实施成本低于 fence 价值。

**alternatives considered**:
- (A) git log 解析 commit message 找 follow-on(脆弱;commit msg 不结构化)— 拒绝
- (B) 独立 SQLite db / JSON registry(违 stdlib-only 约束 + 增加同步成本)— 拒绝
- (C) 仅 archived tasks.md 链式继承 + Markdown 解析(原方案)— 拒绝(round 1 codex F1 challenge,链断 risk 没补)
- (D) active.md self-diff + archived tasks.md 双源 + cancel strict validation(选;round 1 F1+F2 inline writeback)

### D-TombstoneProtocol(archived.md tombstone schema + append-only 协议)

**round 1 codex F1 inline writeback**(2026-05-07;新决策 — F1 F1 fix 衍生):

`openspec/backlog/archived.md` 是 active.md 的"墓碑簿",append-only(只追加,从不删 / 改既有行),记录所有从 active 状态迁出的 entries。schema(每行 H3 + 4 字段块):

```markdown
### `<followon-id>`

- **archived_at_commit**: <git sha,40 字符 lower-case hex>
- **archived_in_change**: <change-id,触发归档的 change>
- **cancellation_reason**: <one of: cancelled-superseded by <ref> | cancelled-not-applicable: <enum>+free-form | cancelled-completed: <commit-ref> | inherited-then-completed>
- **registry_entry_snapshot**: <原 active.md entry 8 字段拷贝,JSON 单行;**fence 解析校验**(round 2 F2-r2 fix):必须 valid JSON object + 含 8 schema 字段 + 字段值与 baseline active.md entry 一致;不一致 → BLOCKER `tombstone_snapshot_mismatch_<id>`>
```

**append-only 强约束**:
- 删除 archived.md 既有行 → fence BLOCKER `archived_md_history_lost`(沿 git diff `git diff <commit> -- openspec/backlog/archived.md` 检测删除行)
- 改 archived.md 既有 entry 字段 → fence BLOCKER `archived_md_immutable_field_modified`(沿 git diff per-line 检测)
- 仅允许新 entry append 到文件末尾

**新 entry 校验**(round 2 F2-r2 fix;沿 D-FenceParseStrategy 阶段 1 第 6 步同款 5 项一致性校验):
- `id` 与 H3 标题匹配 + 与 active.md baseline 中被删除 entry 的 id 一致(若 status_changed-to-cancelled,与 baseline status=active 时的 id 一致)
- `archived_at_commit` 是 valid 40-char hex sha;`subprocess.run(["git", "rev-parse", "--verify", "<sha>"])` exit 0
- `archived_in_change` 等于当前 active change id(防 controller 写错指向别的 change)
- `cancellation_reason` 与本 change tasks.md 中该 entry cancel tag 类型 + ref 一致(防 controller tag 与 tombstone reason 漂移)
- `registry_entry_snapshot` 是 valid JSON object 且 8 字段齐全(`id` / `source` / `description` / `trigger` / `category` / `retire-impact-status` / `priority` / `status`),字段值与 baseline active.md entry 一致

**rationale**:tombstone protocol 是 F1 fix 的关键支撑 — active.md 删 entry 必须有 archived.md 对应行,否则 fence 不能区分"controller hand-edit drift 偷偷删"vs "正当 cancel 已记录";append-only 保证历史完整性(沿 ledger-binding 期 append-only 语义同款,但简化无 HMAC chain — retire 后回到 v1 advisory baseline,本 change 不引入 cryptographic enforcement);schema 4 字段控制简洁,实施成本低。

**alternatives considered**:
- (A) 无 tombstone,active.md 删 entry 即生效 — 拒绝(沦为 hand-edit drift bypass)
- (B) tombstone 走 git history 隐式记录(grep git log) — 拒绝(脆弱,grep commit msg 不结构化)
- (C) tombstone 用独立 schema 文件 + cryptographic chain — 拒绝(沿 retire 后 v1 advisory 简化精神;过度工程化)
- (D) 4 字段 append-only schema(选;简洁 + 显式 + git diff 守门)

### D-CrossLinkSync(registry ↔ SRS §7.3 同步策略 + fence enforce)

**round 1 codex F3 inline writeback**(2026-05-07;立场升级 — 原"约定同步无 enforce"被 codex challenge 后加独立 fence enforce):

- registry 与 SRS §7.3 双源 cross-link(沿 D-RegistryDualSource);加独立 fence `_check_srs_registry_consistency` 守门:
  - **等价集合校验**:active.md 中 `category: requirements-tbd-pointer` entries 集合 必须 == SRS §7.3 表中 `状态 ∈ {❌, ⚠️ baseline, ⏳}`(active 状态)的 TBD-XXX 行 id 集合;不等 → BLOCKER `srs_registry_set_mismatch` + 列出 added/removed
  - **状态变化同步**:SRS §7.3 状态 active → ✅(complete)→ registry pointer 必须同步标 `cancelled-completed` 移到 archived.md tombstone;否则 BLOCKER `srs_completed_tbd_still_active_in_registry`
  - **新增同步**:SRS §7.3 加新 TBD → registry 必须加对应 pointer entry(本 change 后由 cross-cutting follow-on change 自管,沿 archive cycle 同步)
- fence 触发位置:archive 阶段(沿 D-FenceLocation)与 `_check_followon_continuity` 并列调用
- registry 中 entry status 变 cancelled-* → 移到 `archived.md` 永久归档(沿 archive cycle 单向流);本 change 实施期 SRS §7.3 加 cross-link header note 指向 active.md

**rationale**:原"约定同步"是 D-CrossLinkSync 第一版(本会话 2026-05-06 拍板),但 round 1 codex F3 challenge:无 enforce 约定 = 文档协议,实际 controller 易漏。加独立 fence `_check_srs_registry_consistency` 把 SRS↔registry sync 升级为可执行守门;实现成本低(stdlib-only Markdown 解析 SRS §7.3 表 + active.md entries diff)。

**alternatives considered**:
- (A) 自动化双向 sync 脚本 — 拒绝(过度自动化;archive-stage fence 已够)
- (B) 仅约定同步无 enforce(原方案)— 拒绝(round 1 codex F3 challenge,实际易漏)
- (C) fence enforce(选;round 1 F3 inline writeback)
- (B) registry 单源 SRS auto-generate view — 与 D-RegistryDualSource 已拒绝
- (C) 单向静态 cross-link + fence 守门(选)

## Risks / Trade-offs

- **[Risk] backfill 24 项写入易错**(命令模板 / 命令脚本各 1 文件 + registry + SRS 加 cross-link + 6 类多模态 capability-boundary 来源散布在 LLD/CLAUDE.md 不同段)→ **Mitigation**:tasks.md 拆 24 个独立 backfill micro-task(每项独立 verify);每项写入后 git diff 单独 review;test_followon_registry.py 加 schema parse 测试 + 24 entry count 测试。
- **[Risk] fence false positive**(前一 archived change 的 tasks.md 没标准化 P11/P12 命名 — 历史 change 如 `comfy-agent-cli-video-adoption` 的 tasks.md 可能用 `## Phase 5` 而非 `## P5`)→ **Mitigation**:fence 实现兼容 `## P<N>` / `## P<N> — ` / `## Phase <N>` 等 3 种命名(沿 retire follow-on `fix-finish-gate-section-regex-for-p-prefixed` 同款扩展;本 change `tasks.md` 显式声明依赖该 follow-on 是否优先 ship 不影响本 change archive — 本 change tasks.md 用统一 `## P<N>` 命名)。
- **[Risk] archive 摩擦增加**(blocker fence)→ **Mitigation**:cancel 协议(3 类 cancelled-* + 1 类 inherited)提供合规出口;`cancelled-not-applicable` 允许 `reason: out-of-scope` / `reason: retire-superseded` / `reason: scope-changed` 等 free-form reason;沿 retire-parallel-and-worktree-fully 期实证的"严控 retire scope 边界"(memory `feedback_partial_vs_whole_retire_audit`)纪律。
- **[Risk] registry 中 priority 字段为空可能让用户觉得"什么时候做不清楚"**→ **Mitigation**:本 change 不强制 priority(沿 Non-Goal);留 follow-on `prioritize-followon-backlog`(若 user 实证手工挑 follow-on 困难时启动)。
- **[Risk] cross-link header note 在 SRS §7.3 中可能被忽略**(SRS 读者多关注 TBD 表本体)→ **Mitigation**:header note 用粗体 + 显式 reference 路径,跟 SRS 现有"详情见 docs/design/LLD.md §X.Y"风格一致;本 change Documentation Sync Gate(P6)显式 audit SRS §7.3 改动是否被读者注意到(留 retrospective 跟踪)。
- **[Trade-off] 双源(registry + SRS §7.3)而非单源**:沿决策 1(b),保留 SRS 需求层语义但代价是仍有 2 个位置可查;实测决策 1(a) 单源会污染 SRS 语义,(b) 收益(语义清晰 + cross-link 互链)>代价(2 位置)。

## Migration Plan

**部署顺序**(沿 archived `retire-parallel-and-worktree-fully` 同款 phase):

1. **P0** baseline + 24 项 backfill 准备(读 archived `tasks.md` + LLD + SRS 提取 follow-on 描述,写入新 registry)
2. **P1** registry 文件创建 + cross-link 写入 SRS §7.3 + README 更新
3. **P2** `_check_followon_continuity` fence 实装 + helper 扩展 + unit 测试
4. **P3** `forgeue_change_state.py` 加 `--list-followon-{inherited,cancelled}` 子命令
5. **P4** 命令模板更新(`/forgeue:change-finish` Preflight + `/forgeue:change-status` Output Format + `/forgeue:change-apply-{subagent,direct}` evidence frontmatter 模板)
6. **P5** verify(L0/L1/L2 + codex `/codex:review --base main` verification hook)
7. **P6** Documentation Sync Gate(10 文档检查)
8. **P7** retrospective + cross-check + finish_gate
9. **P8** archive(USER 范围;Fence #1 不可逆操作)

**Rollback strategy**:本 change 在 `dev` branch 实施(沿 ForgeUE 流程),archive 前可 `git reset --hard` 回滚到本 change 启动 commit `f14e581`(retire-parallel-and-worktree-fully archive commit)或后续。若 archive 后发现 `_check_followon_continuity` fence 误报阻断历史 change replay → 走新 follow-on `fix-followon-continuity-fence-historical-replay`(归档不动原则)。

## Open Questions

- **Q1**:registry 文件位置 `openspec/backlog/active.md` vs `openspec/changes/_backlog/active.md` 哪个更符合 OpenSpec 上游约定?**默认选 `openspec/backlog/`**(单独子目录,与 `changes/` / `specs/` 平级,语义清楚)。
- **Q2**:cancel 协议第 4 类 `cancelled-completed` 是否与 `inherited`(继承延续)语义重叠 — 完成的 follow-on 应该归到 archived registry 还是本 change tasks.md 标 `[x]` 即可?**默认**:both;tasks.md 内 `[cancelled-completed]` 显式标记 + registry status 变更为 `cancelled-completed` 后 1 cycle 移 archived registry。
- **Q3**:`enhance-workflow-automation-v2-fence-hardening` 是否当首批 archived registry 历史记录(沿 D-BackfillScope 注释)— **默认是**;协议示范 + 历史 trace。
- **Q4**:本 change 自身完成时,自身 archive 是否需要"继承"前一 archived change(retire-parallel-and-worktree-fully)的 follow-on?— **是**:本 change tasks.md P12 段必须列 retire 4 follow-on(自动 inherited 4 项,沿 D-FenceStrictness)+ 加 SRS / 多模态 backfill 项的 cancellation handling。
