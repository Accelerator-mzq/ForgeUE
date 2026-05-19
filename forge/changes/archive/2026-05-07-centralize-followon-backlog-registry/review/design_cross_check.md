---
change_id: centralize-followon-backlog-registry
stage: S2
evidence_type: design_cross_check
contract_refs:
  - design.md
  - proposal.md
  - specs/examples-and-acceptance/spec.md
aligned_with_contract: true
detected_env: claude-code
triggered_by: forgeue:change-plan
codex_plugin_available: true
autonomy_decision: claude_codex_concurred
codex_review_ref: review/codex_design_review.md
created_at: 2026-05-06T14:50:00Z
resolved_at: 2026-05-07T17:05:00Z
resolution_summary: round 1 + round 2 close;round 1 4 finding accepted-codex (commit 125eae1 + sync adjustments) + round 2 3 finding accepted-codex (commit 5084166;F1-r2 baseline anchor / F2-r2 tombstone 5-point consistency / F3-r2 commit-touches strict + evidence escape hatch);total 2 rounds, 7 findings all closed inline writeback, no disputed-permanent-drift
disputed_open: 0
runtime_enforcement_protocol_version: v1
skill_cascade_audit:
  invoked_skills:
    - superpowers:writing-plans
  cascade_check_pass_at: 2026-05-06T14:50:00Z
---

# Design Cross-Check — centralize-followon-backlog-registry

## A. Decision Summary(Claude 立场冻结;在 codex 调用之前写好)

本 change scope:建集中 follow-on backlog registry(`openspec/backlog/active.md` + `archived.md`)+ `_check_followon_continuity` blocker fence;补"ForgeUE 当前没有集中 follow-on 记录位置"的 systemic gap(实证链断 risk:Claude 第一轮全项目 grep 漏 6 项)。

### A.1 8 个 D-decision 清单(design.md §Decisions)

| ID | Decision | Claude 立场 |
|---|---|---|
| **D-RegistrySchema** | registry 走 Markdown table-of-entries 形式(单文件,H3 标题 + 字段块),非 JSON / YAML | Markdown 优先(.md grep / 人读体验更好;tools 解析复用既有 helper);YAML 单文件 / 多 .md 文件方案被拒 |
| **D-RegistryDualSource** | registry 收 archive-tracking 类(15 项),SRS §7.3 仍是需求层 backlog(9 项),双源 + cross-link | 沿 user 决策 1(b);TBD 是需求层未决 vs follow-on 是已决 deferred,语义不同;强行单源会污染 SRS;双源代价(2 位置)< 收益(语义清晰) |
| **D-FenceStrictness** | `_check_followon_continuity` blocker + 4 类 cancel 协议(`cancelled-superseded` / `cancelled-not-applicable` / `cancelled-completed` + `inherited`) | 沿 user 决策 2(c);advisory 等于没改,blocker 无 cancel 协议会卡死 retire 类;cancel 协议提供合规出口 |
| **D-FenceLocation** | fence 仅在 `/forgeue:change-finish` Preflight 阶段触发,非 propose / plan / apply / verify 阶段 | archive 是 backlog 状态唯一稳定时机;沿 v1 advisory 3 fence 同款 archive-only 思路 |
| **D-BackfillScope** | 24 项一次性 backfill(9 workflow-protocol + 9 SRS pointer + 6 capability-boundary) | 沿 user 决策 3(a);registry 启用即满,边际成本低(数据已整理);分批 backfill 等于"假集中",可见性几乎没改善 |
| **D-EvidenceFrontmatterField** | `followon_continuity` 13th conditional key(仅 archive-stage evidence required),含 4 sub-list | 沿 12-key audit frontmatter conditional pattern(`drift_decision` 同款仅 `aligned_with_contract: false` 时 required) |
| **D-FenceParseStrategy** | stdlib-only Markdown 解析 + checkbox 状态识别,兼容 `## P<N>` / `## P<N> — ` / `## Phase <N>` 三种命名 | 沿 ForgeUE 8 工具 stdlib-only 约束;复用既有 `_parse_yaml_subset` helper |
| **D-CrossLinkSync** | 单向静态 cross-link + fence 守门(本 change 范围内不引入自动化双向 sync 脚本) | 双向 sync 复杂度延到必要时再加;留 follow-on `automate-followon-registry-srs-sync` 兜底 |

### A.2 5 个 ADDED Requirement(specs/examples-and-acceptance/spec.md)

1. **Centralized follow-on backlog registry under `openspec/backlog/`**:active.md + archived.md 双文件 + 8 字段 schema + 24 项 backfill 一次性满
2. **`_check_followon_continuity` blocker fence**:archive 阶段守门 + 4 类 cancel 协议
3. **Evidence frontmatter conditional `followon_continuity`**:13th key,archive-stage required,4 sub-list 结构
4. **`/forgeue:change-status` Output Format `### Followon Backlog` section**:列继承 + cancelled 计数 + diff
5. **Capability boundary 6 LLD-inline 注释 → registry entry**:每条 LLD `留 follow-on <name>` 都有 registry entry

### A.3 4 个已识别 Risk + Mitigation(design.md §Risks)

| Risk | Claude Mitigation |
|---|---|
| backfill 24 项写入易错(数据来源散布在多个文件) | tasks.md 拆 24 个独立 backfill micro-task + git diff 单独 review + test_followon_registry.py schema parse 测试 |
| fence false positive(历史 change tasks.md 命名不统一) | fence 兼容 3 种命名(`## P<N>` / `## P<N> — ` / `## Phase <N>`)+ 与 retire follow-on `fix-finish-gate-section-regex-for-p-prefixed` 解耦(本 change 不依赖该 follow-on 优先 ship) |
| archive 摩擦增加(blocker fence) | cancel 协议 4 类合规出口 + free-form `reason`/`commit` 字段 |
| registry priority 字段为空让用户困惑 | 本 change 不强制 priority(沿 Non-Goal);留 follow-on `prioritize-followon-backlog` |

### A.4 4 个 Open Question(design.md §Open Questions)

| Q | Claude 默认答案 |
|---|---|
| Q1 registry 文件位置(`openspec/backlog/` vs `openspec/changes/_backlog/`) | 选 `openspec/backlog/`(与 `changes/` / `specs/` 平级,语义清楚) |
| Q2 `cancelled-completed` 与 `inherited` 语义重叠 | both;tasks.md 内 `[cancelled-completed]` 显式标记 + registry 移 archived registry |
| Q3 `enhance-workflow-automation-v2-fence-hardening` 进首批 archived registry | 是;协议示范 + 历史 trace |
| Q4 本 change 自身 archive 时是否继承 retire 4 follow-on | 是;tasks.md P12.1-P12.4 已显式声明继承(P12.1 标 cancelled-not-applicable scope-limited;P12.2-P12.4 inherited unchanged) |

### A.5 期望 codex 重点审视的 Risk surface

- **D-FenceStrictness 的 cancel 协议是否过宽**(`cancelled-not-applicable` reason 是 free-form,可能被滥用绕过 fence)— Claude 立场:cancel 协议 free-form 是 trade-off(过严会卡死 retire 类),沿 retire-parallel-and-worktree-fully memory `feedback_partial_vs_whole_retire_audit` 严控 retire scope 边界纪律;若 codex 提出 strict reason enum 建议,Claude 倾向 disputed-pending(reason 类型当前不足够明确,留 follow-on)
- **D-RegistrySchema 的 Markdown 解析鲁棒性**(YAML 内嵌 Markdown vs 独立 .md 表格)— Claude 立场:独立 .md 表格更人友好;若 codex 提出"正交 YAML 索引文件"建议,Claude 评估利弊 — 多文件同步成本高,默认 disputed-pending
- **D-BackfillScope 的 6 capability-boundary 项是否完整**(grep LLD + CLAUDE.md 是否漏 inline 注释)— Claude 立场:本会话已 grep `留 follow-on \`<name>\``,得 6 项;若 codex 提出新候选项(如 `repo-put-streaming-payload` 已属 SRS TBD-012 不重复入 capability-boundary),Claude 倾向 accepted-codex 调整 backfill list
- **D-FenceLocation archive-only 是否够**(propose / plan / apply 阶段是否应该早期 warning)— Claude 立场:archive 唯一稳定;早期 warning 会引入 noise;若 codex 提出"plan 阶段 advisory 提示"建议,Claude 倾向 accepted-codex 加 advisory(non-blocker;沿 v1 风格)— 本立场可能调整

### A.6 Cross-check Process(沿 design.md §3 Cross-check Protocol)

- **Round 1**:codex `/codex:adversarial-review --background` against design.md(本段冻结后调用)
- **`## B`**:逐 finding 走 Resolution enum(`aligned` / `accepted-codex` / `accepted-claude` / `disputed-pending` / `disputed-permanent-drift`)
- **`## C`**:`disputed_open: <count>`;> 0 阻断 S3
- **`## D`**:独立验证 file:line(沿 ForgeUE memory `feedback_verify_external_reviews`,不把 codex claim 当结论)
- **预估 round 数**:1-2 round(本 change scope 较 retire-parallel-and-worktree-fully 简单 — 3 deliverable + 8 D-decision;预期 finding 4-8 条,1 round inline writeback close 比例高)

## B. codex Findings × Resolution

Round 1 codex `/codex:adversarial-review` job `bddjc7ohy` verdict `needs-attention`,4 finding。

| ID | P | Finding | file:line | Independent Verify | Resolution | writeback_commit |
|---|---|---|---|---|---|---|
| **F1** | P1 high | Fence 仅扫 latest archived tasks.md,registry 自身丢项不被守门 | `specs/...:22-24` + `design.md:131-146` | ✅ TRUE | **accepted-codex** — user 2026-05-07 拍板 (a);D-FenceStrictness + D-FenceParseStrategy 立场翻转 + 加 D-TombstoneProtocol 新决策;active.md self-diff + archived.md append-only tombstone 4 字段 schema | `125eae1` |
| **F2** | P1 high | Cancel 协议仅识别语法 tag,无 ref/commit/reason enum 校验 | `design.md:76-83` + `specs/...:32-35` | ✅ TRUE | **accepted-codex** — user 2026-05-07 拍板 (a);strict ref validation:5 类 reason enum + Path.exists supersedes id 校验 + git rev-parse commit 校验(commit-touches 留 follow-on `tighten-cancel-completed-commit-touches-validation`) | `125eae1` |
| **F3** | P2 medium | SRS↔registry consistency 在 design 写约定但 spec 无 fence requirement / scenario | `design.md:148-156` vs `specs/...:22-24` | ✅ TRUE | **accepted-codex** — D-CrossLinkSync 升级为 fence enforce(`_check_srs_registry_consistency` 独立 fence);spec 加新 ADDED Requirement + 2 scenarios(SRS 加新 TBD 无 pointer BLOCKER / SRS TBD 完成未同步 BLOCKER) | `125eae1` |
| **F4** | P2 medium | `followon_continuity` schema proposal vs design/spec 冲突 | `proposal.md:9` vs `design.md:117-125` | ✅ TRUE | **accepted-codex** — proposal.md L9 改 4-list canonical schema 沿 design/spec | `125eae1` |

### B.1 与 ## A 期望 codex challenge surface 的对照

| Claude `## A.5` 期望 codex 重点审视 | 实际 codex round 1 命中 | Disposition |
|---|---|---|
| D-FenceStrictness cancel 协议过宽 | ✅ F2 命中 | F2 disputed-pending(立场翻转;Claude 原立场"free-form 是 trade-off"被 codex challenge,需 user 拍板) |
| D-RegistrySchema 单 .md vs 多文件 / YAML | ❌ 未提(round 1 未引入 schema 文件结构 challenge) | n/a;若 user 同意 F1 active.md source-of-truth 改造,可能间接触发 schema 复杂度重新评估 |
| D-RegistryDualSource 反向同步 gap | ✅ F3 命中(更具体) | F3 accepted-codex inline writeback |
| D-FenceLocation archive-only | ❌ 未提(round 1 未 challenge propose/plan/apply 阶段 advisory) | 沿 ## A 立场 archive-only,无 codex pushback,保持原设计 |
| D-BackfillScope 6 capability-boundary 完整性 | ❌ 未提(codex tool 操作含 LLD/CLAUDE.md grep 但未质疑 6 项完整性) | 沿 ## A 立场 6 项,无 codex pushback;P0.4 backfill 时实测 grep 结果若有偏差再回写 |
| D-FenceParseStrategy 兼容 21 archived change | ❌ 未提(codex 看了 retire archived tasks.md 但未 raise 历史 命名 bug) | 沿 ## A 立场,P2.5 unit test 覆盖 3 种命名兼容 |
| scope creep risk 拆 2-3 change | ❌ 未提 | 沿 ## A 立场,3 deliverable 紧耦合 |
| (新)F1 active.md self-truth fence | ❌ Claude `## A.5` 未预期此 surface | 这是 codex 真正贡献:把 fence 真源从 archived tasks.md 升到 active.md;若 accept,fence 实现复杂度 + scope 显著增加 |
| (新)F4 schema mismatch | ❌ Claude `## A.5` 未预期 | obvious fix |

### B.2 Resolution scope 评估

- **accepted-codex inline writeback(F3 + F4)**:本 cross-check 段 close 后即可由 Claude 自主回写 design / spec / proposal;不影响 plan stage 推进
- **disputed-pending(F1 + F2)**:user 拍板前不推进 S3;两条都涉及 design 立场翻转 + scope 扩张;若 user accept,本 change scope 从"3 deliverable + 24 backfill"扩到"4 deliverable + 24 backfill"(加 active.md self-truth 协议 + cancel ref strict validation)+ 测试矩阵显著加大

## C. Disputed Count

`disputed_open: 0`(round 1 4 finding 全 accepted-codex inline writeback;commit `125eae1`)

> S3 阻断条件解除。round 1 close;预估总 round 数 2(预期 round 2 codex re-review 验证 F1+F2 大改是否引入新 risk surface)。

## D. Independent Verification(沿 ForgeUE memory `feedback_verify_external_reviews`)

| ID | Codex claim file:line | Claude verify(独立 read 文件实测) | Verdict |
|---|---|---|---|
| F1 | `spec.md:22-24` fence 只扫 archived tasks.md | Read `spec.md:22-24` 实测:requirement L24 步骤"The fence SHALL scan the latest archived change's tasks.md for unchecked items" — codex claim 准确;补查 D-FenceParseStrategy `design.md:131-146` 5 步骤,均未涉及 active.md 自身校验 | ✅ TRUE |
| F2 | `design.md:76-83` cancel 仅 syntax | Read `design.md:76-83` 实测 4 类 cancel tag 列举只展示 literal tag 格式(`[cancelled-superseded by <new-change-id>]` 等),无校验逻辑;`design.md:139` fence 实现步骤 5 仅"cancelled-* 配套 ref 缺失",未实现 ref 真实性校验 | ✅ TRUE |
| F3 | `design.md:148-156` D-CrossLinkSync vs spec fence | Read `design.md:148-156` 实测 D-CrossLinkSync L152 写"由 `_check_followon_continuity` fence 守门 — fence 扩展扫 SRS §7.3 diff"主张;Read `spec.md:22-24` fence requirement L24 仅扫 archived tasks.md;Read `spec.md:1-20` registry requirement 仅一次性 24 项 + cross-link header note,无 SRS 状态变化 scenario | ✅ TRUE |
| F4 | `proposal.md:9-14` schema 冲突 | Read `proposal.md:9` 实测 L9 字段格式 `inherited_count / cancelled_count / cancellation_refs` 3-key dict;Read `design.md:117-125` 实测 4-list YAML 块(`inherited: [...]` / `cancelled_superseded: [{id, supersedes}]` / etc.);Read `spec.md:54-60` 实测 4-list 描述 — 三者字段名直接 mismatch | ✅ TRUE |

**所有 4 finding 独立验证 TRUE,无伪 finding。**

### D.1 Resolution disposition(round 1 close 状态;2026-05-07T14:10:00Z)

- **F1 + F2** accepted-codex by user 拍板 (a);writeback_commit `125eae1`;design.md / proposal.md / specs.md / tasks.md 四件套同步改动入此 commit
- **F3 + F4** accepted-codex inline writeback;writeback_commit `125eae1`(同 batch)

`disputed_open: 0`,S3 阻断解除。

### D.2 Sync adjustments for fix-finish-gate-archived-replay-compat merge(2026-05-07,non-codex 触发)

User 通报 `fix-finish-gate-archived-replay-compat` 已合入 dev(commit `88a8aec`),触发 Claude 主动 sync 4 处:

| File | Adjustment |
|---|---|
| `proposal.md` | Backfill scope 24 → 22 active(7 workflow-protocol + 9 SRS + 6 capability)+ 3 archived.md tombstone 首批 |
| `design.md` D-BackfillScope | List rewrite 9 → 7 + 3 tombstone 表 |
| `design.md` D-FenceParseStrategy | 注脚 latest archive 是 micro-bugfix 无 P12 退化为 no-op,阶段 1 self-truth 主源仍守门 |
| `tasks.md` P0.1 / P1.3 / P1.6 | baseline 1576 → 1753;workflow-protocol 9 → 7 entries;archived.md 3 项 tombstone |
| `tasks.md` P12 inheritance | latest archive 无 P12 → 实质 inherit 自祖父 retire 4 follow-on(2 closed-by-fix-change cancelled-completed:88a8aec / 2 仍 active inherited) |
| `specs/...spec.md` | 24 → 22 entries 描述 + tombstone scenario 用 88a8aec 真 commit + 3 archived 首批 entry list |

Sync adjustments 与 codex F1-F4 inline writeback 合 single commit(α 选项;`125eae1`),叙事更紧凑 + ref 单一。

---

## E. Escalation to User(已 close 2026-05-07T14:10:00Z;user 拍板 (a) accept F1 + F2 全集)

### E.1 F1 - active.md source-of-truth fence 改造

**Codex 主张**:fence 真源从 archived tasks.md 升级到 active.md(`openspec/backlog/active.md`);archive 时校验 active.md 上一版本 vs 当前版本的增删改,删除/取消必须有 archived.md append-only tombstone;current tasks.md 声明必须覆盖 active registry 中仍 active 的相关 entry。

**当前 design 立场**(`design.md:131-146` D-FenceParseStrategy):fence 解析 archived tasks.md(`## P11/P12/Pn (follow-on tracking)` section unchecked)+ 与本 change tasks.md 同名 section 比对。

**Claude 评估**:

- 收益:**显著降低链断 risk**(F1 是真核心 risk — 当前 design 仍走链式继承,只是把"分散在 8 位置"改"集中在 active.md",但 fence 仍走 archived tasks.md 链);active.md 删除 / 修改不被守门 = fence 监管漏洞;sister memory `project_retire_parallel_worktree_shipped.md` 实证 retire 过程中 v2/v3 fence schema 复杂度过高被 retire,本 fix 是否会重蹈 over-engineering?
- 代价:**fence 实现复杂度 + scope 显著扩张**;需加 git diff active.md 历史版本逻辑 + tombstone 协议 + active.md schema 测试 + commands(change-finish Preflight)调 git diff 接口;~增加 100-200 LOC;tests 矩阵从 7-10 case → 15-20 case
- Trade-off vector:简化 fence(沿 retire baseline) vs 真正补漏(本 change 核心目标)

**Claude 倾向**:**accept-codex F1**(scope 扩到 4 deliverable),理由:本 change 目标就是补 backlog continuity 的 systemic gap,若 fence 仍走 archived tasks.md 链 = 没补到位,沦为"换可见文档位置"(codex 原话);over-engineering risk 用 stdlib-only `git diff` + 简化 tombstone schema(2 字段:`id` + `archived_at_commit`)控制。

### E.2 F2 - cancel 协议 strict validation

**Codex 主张**:supersedes change id 必须解析到 active/archived change 目录;completed commit 必须 git rev-parse 验证存在 + 触达 source/contract_refs 或 evidence 指向的相关文件;not-applicable reason 使用小枚举并要求 evidence/ref;同一 archive cycle 必须完成 active.md → archived.md 原子迁移。

**当前 design 立场**(`design.md:76-83` D-FenceStrictness):cancel 4 类 tag 仅语法识别;sister memory `feedback_partial_vs_whole_retire_audit.md` 倾向严控 retire scope 边界,但允许 cancel reason free-form。

**Claude 评估**:

- 收益:**防 controller hand-edit drift**(F2 是 cancel 路径的根本漏洞 — 当前 design 4 类 cancel tag 让 controller 写 `[cancelled-not-applicable: 我懒]` 都能绕过 fence;沦为 syntactic seal,不是 semantic guard)
- 代价:**reason enum 列举完整性 risk**(枚举漏覆盖会卡死有效场景);commit 触达校验过严会卡死跨 cutting commit / cross-cutting refactor 场景
- Claude 推荐 5 类 reason enum:`retire-superseded` / `out-of-scope` / `scope-changed` / `obsolete` / `infeasible`(沿 retire-parallel-and-worktree-fully + ledger-binding 期实证 5 类典型 cancel reason 场景);additional reason 文字仍允许作为补充,但必须前缀 enum 值
- supersedes id 校验:`Path("openspec/changes/<id>").exists() OR Path("openspec/changes/archive").glob("*-<id>")` stdlib-only 简单可行
- commit 校验:`subprocess.run(["git", "rev-parse", "--verify", "<commit>"])` exit 0 验证存在;**不**校验 commit 触达特定文件(过严会卡死有效场景);若 user 想要 commit 触达校验,留 follow-on
- atomic active.md → archived.md migration:同 archive cycle 内完成,沿 finish_gate 流程在 archive commit 前实施

**Claude 倾向**:**accept-codex F2 部分**(reason enum + supersedes id Path 校验 + commit rev-parse 校验;**不**接受 commit 触达校验过严部分,留 follow-on),理由:strict validation 与本 change "防 controller drift"目标一致;fence 严而不死(reason enum 5 类 + escape hatch follow-on)。

### E.3 接受 F1 + F2 后的 scope 影响

| 维度 | 原 scope(disputed close 前) | 加 F1 + F2 修复后 |
|---|---|---|
| Deliverable 数 | 3(registry + fence + 命令模板) | 4(+ active.md self-truth diff/tombstone 协议) |
| 24 项 backfill | 不变 | 不变 |
| Fence LOC | ~80 | ~150-200(加 git diff + tombstone + cancel ref 校验) |
| Test case 数 | 7-10 | 15-20 |
| Schema 文件 | 1(active.md) | 2(active.md + archived.md tombstone schema) |
| Spec scenario 数 | 9 | ~14-16(加 F1/F2/F3 scenarios) |
| Migration plan | P0-P8 | P0-P8 + P2 拆 P2.a/P2.b/P2.c(F1/F2/F3 实施 sub-phase) |
| Cancel reason 协议 | free-form | 5 类 enum + free-form 补充 |
| 工作量 | ~1 day | ~2-3 day |

### E.4 给 user 的 3 个选项

**(a) Accept F1 + F2 全集**(Claude 倾向):
- scope 扩到 4 deliverable,fence 实现复杂度 +100%,但**真正补到 systemic gap**(否则本 change 沦为"换文档位置")
- 接受 retire 后 over-engineering risk 重现的小概率,用 stdlib-only + 简化 schema 控制
- 进 round 2 codex review 验证 fix 是否充分

**(b) Accept F2 only,拆 F1 到独立 follow-on**`fortify-followon-active-registry-as-source-of-truth`:
- 本 change 先 ship 协议雏形 + cancel strict validation,后续 follow-on 升级 active.md 为 hard source-of-truth
- 优点:scope 控制 + 渐进式 ship
- 缺点:雏形期 fence 仍可被绕过(F1 漏洞悬置 1 cycle 以上)

**(c) Reject F1 + F2 全集**:
- 沿原设计 ship 3 deliverable 雏形;F1+F2 留 follow-on
- 优点:scope 最小;最快 ship
- 缺点:本 change 实质"换文档位置";链断 risk 没补到位 — 一开始 user 提的 systemic gap 没解决;沦为伪 fix

**Claude 倾向**:**(a) Accept F1 + F2 全集**

**User 决议(2026-05-07T14:10:00Z)**:**(a) Accept F1 + F2 全集**

writeback 实施完成 commit `125eae1`(单 batch;含 sync adjustments for fix-finish-gate-archived-replay-compat `88a8aec` merge)。

`## A` 冻结的 5 期望 codex challenge surface 中,F1 + F2 是 codex 真贡献(`## A.5` Claude 未预期 surface);F3 + F4 也命中 obvious fix。round 1 验证 codex review hook 价值 — 若没跑 codex,本 change 会以"换文档位置"伪 fix 状态 ship。

---

## F. Round 2 codex Findings × Resolution

Round 2 codex `/codex:adversarial-review` job `b876734jn`(2026-05-07T16:48:00Z)verdict `needs-attention`,3 finding 全 [承 round1-F1] / [承 round1-F2] 标识(显式承接 round 1 同源,不重复 raise)。

| ID | P | Finding | file:line | Independent Verify | Resolution | writeback_commit |
|---|---|---|---|---|---|---|
| **F1-r2** | P1 high | active.md self-diff 基线选错 | `execution/micro_tasks.md:342` (helper `_get_prior_archive_commit_for_active_md`) + `design.md` D-FenceParseStrategy 阶段 1 步骤 1 | ✅ TRUE | **accepted-codex** — design.md D-FenceParseStrategy 阶段 1 改 baseline 锚定上一 archive commit;helper 重命名 `_get_change_baseline_commit`;spec.md 加 scenario "baseline anchors to last archive commit not active.md path commit" | `5084166` |
| **F2-r2** | P1 high | tombstone snapshot 不解析,controller 任意 placeholder 通过 | `design.md:189` (`留 trace 用,fence 不解析`)+ `specs/...` 4 字段 scenario | ✅ TRUE | **accepted-codex** — design.md D-TombstoneProtocol 新增"5 项一致性校验"(id + snapshot 8 字段 + 字段值匹配 baseline + archived_in_change + cancellation_reason ↔ tasks tag);spec.md 加 4 scenarios(snapshot 字段错 BLOCKER / archived_in_change 不匹配 BLOCKER / snapshot 字段值不一致 BLOCKER / cancellation_reason 不一致 BLOCKER) | `5084166` |
| **F3-r2** | P2 med | cancelled-completed 仅 git rev-parse,任何 doc-only / unrelated commit 都通过 | `design.md:81 + 93` (`留 follow-on tighten-...`)+ `specs/...:25-28` | ✅ TRUE | **accepted-codex** — user 2026-05-07 拍板 (α);拉回 current scope:tag 格式扩展 `[cancelled-completed: <commit> evidence: <path>]`;fence Step 3.4 commit-touches intersect + Step 3.5 escape hatch;P12.8 follow-on cancelled-completed-by-this-change | `5084166` |

### F.1 Independent file:line verification

| ID | Codex claim | Claude verify | Verdict |
|---|---|---|---|
| F1-r2 | micro_tasks.md baseline = `git log -1 -- active.md` | Read `execution/micro_tasks.md:342` 实测 helper 实装 `_get_prior_archive_commit_for_active_md` body `["git", "log", "-1", "--format=%H", "--", "openspec/backlog/active.md"]` — codex claim 准确;design.md L138 写了 baseline 概念但 micro_tasks 实施漂偏 | ✅ TRUE |
| F2-r2 | design.md `registry_entry_snapshot ... 留 trace 用,fence 不解析` | Read `design.md:189` 实测原文一致;spec.md tombstone scenario 只校 4 字段存在,无 snapshot 解析 + 一致性校验 | ✅ TRUE |
| F3-r2 | design.md `不校验 commit 触达特定文件` + 留 follow-on | Read `design.md:81 + 93` 实测原文一致;spec.md scenario `valid commit ref passes`(L25-28)只校 git rev-parse exit 0 | ✅ TRUE |

### F.2 Resolution disposition

- **F1-r2 + F2-r2 accepted-codex**(Claude 自主):design implementation correctness fix,**非 scope 调整**;round 1 F1 立场翻转主体(active.md hard source-of-truth + tombstone protocol)成立,只是补 implementation 漏洞(baseline anchoring + snapshot 校验)— 自主 inline writeback
- **F3-r2 disputed-pending**(升级 user):虽然是 design implementation issue,但承 round 1 F2 我推荐"commit-touches 留 follow-on"是 Claude implementation choice;user round 1 (a) accept 时未显式 dispose 此 trade-off。Codex round 2 给两个 fix option:
  - **(α) 拉回 current scope:strict commit-touches + evidence escape hatch**(commit 触达 follow-on `source` / `contract_refs` / `registry entry` / `evidence: <path>` 之一即 PASS;后者用 escape hatch 处理 cross-cutting commit)
  - **(β) cancelled-completed 降级 advisory-only**(不阻断 fence,变 WARN)
  - **(γ) 沿 round 1 决议保留 follow-on**(disputed-permanent-drift,需 ≥50 字 reason + design.md `## Reasoning Notes` anchor)

### F.3 Round 2 disputed_open

- F1-r2 + F2-r2 + F3-r2 全 accept inline writeback(commit `5084166`)→ **disputed_open: 0**
- Round 2 close 2026-05-07T17:05:00Z;S3 推 apply 阻断条件解除
- 总 round 数:2(round 1 close + round 2 close;预估 round 3 不需要 — F1-r2/F2-r2 是 implementation correctness fix 无新 design 立场翻转,F3-r2 已实施 strict + escape hatch 沿 round 1 F2 立场延伸完整守门)

### F.4 升级 user 拍板请求(F3-r2 scope decision)

详见 `## G. Escalation to User round 2` 段。

---

## G. Escalation to User — round 2 F3-r2(`cancelled-completed` commit-touches scope)

### G.1 现状

Round 1 决议留 follow-on `tighten-cancel-completed-commit-touches-validation`(scope expansion 顾虑:过严卡死 cross-cutting commit)。Round 2 codex 复议:任何 doc-only / unrelated commit 都通过 fence,round 1 strict validation 在 cancelled-completed 路径仍是语义绕过。

### G.2 3 个 option

**(α) 拉回 current scope:strict commit-touches + evidence escape hatch**

实现:
- 解析 follow-on entry `source` / `contract_refs` 字段
- `subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_ref])` 取 commit 触达文件
- 与 follow-on `source` / `contract_refs` 集合 intersect;非空 → PASS
- 否则检 tag 是否含 `evidence: <path>` 子段(如 `[cancelled-completed: <commit-ref> evidence: notes/cross-cutting-rationale.md]`),`Path.exists()` → PASS
- 都不通过 → BLOCKER `cancel_commit_does_not_touch_followon_or_provide_evidence`

成本:~30-50 LOC fence + 1 helper + 2 spec scenario;tag 格式语法扩展(`evidence:` sub-tag)

**(β) cancelled-completed 降级 advisory-only**

实现:
- fence 校 git rev-parse 存在 → PASS;不存在 → WARN(advisory)而非 BLOCKER
- 不引入 commit-touches 校验
- spec 改 `cancelled-completed` 描述为 advisory-only

成本:~10 LOC fence 调整 + 1 spec edit;不引入新校验逻辑

**(γ) 沿 round 1 决议保留 follow-on(disputed-permanent-drift)**

实现:
- design.md 加 `## Reasoning Notes` `cancel-completed-commit-touches-deferred` anchor + ≥50 字 rationale
- evidence frontmatter `drift_decision: disputed-permanent-drift`
- 实施 follow-on `tighten-cancel-completed-commit-touches-validation`(沿原计划)

成本:无 fence 改动;evidence 额外字段 + Reasoning Notes anchor 写作

### G.3 Trade-off 对比

| 维度 | (α) strict + escape | (β) advisory | (γ) defer follow-on |
|---|---|---|---|
| 防 controller drift | 强(commit 必须触达相关文件 + escape hatch 显式) | 弱(advisory 不阻断) | 弱(沿 round 1 现状) |
| 实施成本 | 中(~30-50 LOC + escape hatch parser) | 低(~10 LOC) | 0(本 change 内) |
| Cross-cutting commit 兼容 | 好(escape hatch 显式说 evidence) | 好(无校验) | 不适用 |
| Scope 扩张 | +1 fence helper + 1 spec field + 2 scenario | 0(只是降级语义) | 0 |
| 与 round 1 F2 立场协调 | 强化(strict 完整) | 削弱(strict 退一步) | 保留(strict 留 follow-on 实施) |

### G.4 Claude 推荐:**(α)**

**User 决议(2026-05-07T17:05:00Z)**:**(α) strict commit-touches + evidence escape hatch**(commit `5084166`;同 batch 含 F1-r2 + F2-r2 inline writeback)。



理由:
- round 1 F2 立场已是"strict validation 防 hand-edit drift",(β) advisory 退一步会让 round 1 F2 决议自相矛盾
- (γ) 留 follow-on 实证不耐 — round 2 codex 再次 challenge,说明守门 gap 在 hand-edit cancelled-completed 路径上仍开放
- (α) escape hatch 处理 cross-cutting commit 风险 — 用户必须显式提供 evidence path,而非"任意 commit ref 都通过"
- 实施成本 ~30-50 LOC 在本 change scope 可控
- 沿 round 1 同款 stdlib-only(`git diff-tree --name-only` + `Path.exists()`)

### G.5 接受 (α) 后的 scope 影响

| 维度 | F1-r2 + F2-r2 accept 后 | + F3-r2 (α) accept |
|---|---|---|
| 4 deliverable 数 | 4(不变) | 4(不变;commit-touches 是 fence 内部强化) |
| Fence LOC | +50(F1-r2 baseline fix + F2-r2 snapshot validation) | +30-50(F3-r2 commit-touches + escape hatch) |
| Test case | +3-5(F1-r2 baseline + F2-r2 snapshot scenarios) | +2(F3-r2 commit-touches + escape hatch scenarios) |
| Spec scenario | +3 | +2 |
| Tag schema 扩展 | 0 | `evidence: <path>` sub-tag |
| 工作量 | +0.3 day | +0.3-0.5 day |

请你拍 (α) / (β) / (γ)。


