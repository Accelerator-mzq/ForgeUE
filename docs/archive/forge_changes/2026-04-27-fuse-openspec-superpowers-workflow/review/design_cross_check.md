---
change_id: fuse-openspec-superpowers-workflow
stage: S2
evidence_type: design_cross_check
contract_refs:
  - proposal.md
  - design.md
  - tasks.md
  - specs/examples-and-acceptance/spec.md
codex_review_ref: review/codex_design_review.md
plugin_command: "codex exec --sandbox read-only -o ... (path B equivalent of /codex:adversarial-review --background)"
plugin_task_id: codex-s2s3-review-20260426-001
detected_env: claude-code
triggered_by: "forced (manual rehearsal of /forgeue:change-plan codex hook before tool implementation)"
codex_plugin_available: false
created_at: 2026-04-26T22:30:00+08:00
resolved_at: 2026-04-26T22:55:00+08:00
disputed_open: 0
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
note: |
  本 cross-check 是 stage S2→S3 design review hook 的手工预演(plan v3 §10.2)。`/forgeue:change-plan` 未实装,Claude 用 codex exec 路径 B 等价跑。
  ## A. Decision Summary 冻结于 codex 调用之前(即 P0 起草后、跑 codex_design_review 之前)。Claude 看完 codex 后未回填 ## A。
  9 项发现(6 blocker + 3 non-blocker)经独立验证全部成立(verified=true);6 blocker + 2 non-blocker 已 accepted-codex 修 contract,1 non-blocker accepted-claude 保留;disputed_open == 0,可继续 P1。
---

# S2→S3 Design Cross-check: fuse-openspec-superpowers-workflow

## A. Claude's Decision Summary (frozen before codex run, 2026-04-26 P0 草稿状态)

> P0 起草时 Claude 的关键判断(冻结于此刻);Claude 不允许在看完 codex review 后回填本段。

- **D-Capabilities**:`New Capabilities: 无` + `Modified Capabilities: 无` + 不需要 delta spec — proposal.md:25-27(P0 起草版)
- **D-DeltaScope**:design.md §10 "Why no delta spec" — 无 delta(后被 strict validate 强制改为 examples-and-acceptance ADDED;但 proposal/tasks 尚未同步)
- **D-DRIFT-Taxonomy**:design.md §3 已定义 4 类 named DRIFT(`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`),但 tasks.md 4.3 + 5.3.1 拆为"锚点 / diff vs design / aligned 字段 / writeback_commit"(混用 named DRIFT + frontmatter 校验)
- **D-ReasoningNotesHeading**:design.md `### §11 Reasoning Notes`(level 3,带 §11 前缀);spec.md Scenario 3 引用 `## Reasoning Notes`(level 2 字面)— **不一致**
- **D-FrontmatterSize**:文档反复称"11 字段",但实际 frontmatter 含 `change_id` + 11 audit fields = 12 个 key — 措辞与实际不一致
- **D-DocSyncP6-7.5.1**:tasks.md 7.5.1 写"openspec/specs/* SKIP + reason 'no spec delta'"(P0 起草时还没 delta;后强制加 delta 但 7.5.1 未同步)
- **D-DisputedReasonLength-Severity**:tasks.md 5.3.1 写"`< 50 字 → WARN`",但 design.md §3 + spec.md ADDED Requirement 明确"≥ 50 字" 是 MUST(否则 finish gate exit 2 阻断)— 严重程度不一致
- **D-DeltaSpec-Validation/Non-Goals**:specs/examples-and-acceptance/spec.md 仅 ADDED Requirement + 3 Scenario,**缺** `## Validation` + `## Non-Goals` 段(P0 起草时未参考 openspec/config.yaml:84-87 的强制要求)

## B. Cross-check Matrix

| ID | Claude's choice | Codex's verdict | Codex's reasoning(摘要 + 引用) | Resolution | 修复操作 |
|---|---|---|---|---|---|
| **B1 D-Capabilities** | `New=无 / Modified=无 / 无 delta` (proposal.md:25-27) | dispute (blocker) | proposal 与 design/spec 不一致;design.md §10 + specs/examples-and-acceptance/spec.md 已加 ADDED Requirement 但 proposal 未同步;[proposal.md:25-27](file:proposal.md), [design.md:216](file:design.md), [spec.md:11](file:spec.md) | **accepted-codex** | proposal.md Capabilities 段已重写:`Modified Capabilities: examples-and-acceptance(加 ADDED Requirement)`;新增"为什么是 capability 行为延伸"段;删 §13 旧引用 |
| **B2 D-DocSyncP6-7.5.1** | `openspec/specs/* SKIP + reason "no spec delta"` (tasks.md:158) | dispute (blocker) | P6 7.5.1 仍写 SKIP,会漏掉 archive 后 sync-specs 把 ADDED Requirement 合入主 spec;[tasks.md:158](file:tasks.md), [design.md:228-230](file:design.md) | **accepted-codex** | tasks.md 7.5.1 改为:`REQUIRED for openspec/specs/examples-and-acceptance/spec.md`;7 个不动 capability 仍 SKIP |
| **B3 D-DeltaSpec-Validation/Non-Goals** | 仅 ADDED Requirement + 3 Scenario (spec.md:1-32) | dispute (blocker) | openspec/config.yaml:84-87 强制 delta spec 必含 `Validation`(指向具体测试文件)+ `Non-Goals`;spec.md 缺这 2 段;[openspec/config.yaml:84-87](file:openspec/config.yaml) | **accepted-codex** | spec.md 末尾追加 `## Validation` 段(指向 5.3.1 / 5.2.5 / 5.2.2 / 5.4.2 等测试文件)+ `## Non-Goals` 段(明列不改 runtime acceptance / 不改其他 7 个 capability / 不抽 ai-workflow / 不引 Python dep / 不默认 paid / 不修禁修区) |
| **B4 D-DRIFT-Taxonomy** | tasks 4.3 / 5.3.1 拆"锚点 / diff vs design / aligned / writeback"(混用) (tasks.md:74) | dispute (blocker) | design.md §3 是 4 类 named taxonomy(`evidence_introduces_*` 等),tasks 后两项是 frontmatter 校验,不是 named DRIFT;[design.md:120-125](file:design.md), [tasks.md:74](file:tasks.md), [tasks.md:113](file:tasks.md) | **accepted-codex** | tasks 4.3 + 5.3.1 重写:4 类 named DRIFT 显式列出对应 fixture/test;`aligned=false` 与 `writeback_commit` 真实性独立成"附加 frontmatter 校验",由 `forgeue_finish_gate` exit 2 阻断 |
| **B5 D-ReasoningNotesHeading** | design.md `### §11 Reasoning Notes`(level 3) vs spec.md `## Reasoning Notes`(level 2) | dispute (blocker) | 字面查会误报缺 anchor;两个修复路径:(a) 改 design.md heading 为 `## Reasoning Notes` 或 (b) 改 spec/tool 协议为模糊匹配;[spec.md:31-32](file:spec.md), [design.md:232-238](file:design.md) | **accepted-codex (path a 用户裁决)** | 改 design.md heading `## Reasoning Notes`(level 2)+ §11.1-§11.4 子 section 同步降为 `### §11.X`(level 3);spec.md heading 引用顺移到与 design.md 一致 |
| **B6 D-DisputedReasonLength-Severity** | tasks 5.3.1 `< 50 字 → WARN` (tasks.md:118) | dispute (blocker) | contract(design.md §3 + spec.md ADDED Requirement)说 ≥ 50 字 是 must;WARN 会让不合格 permanent drift 进 finish gate;[design.md:118](file:design.md), [spec.md:13](file:spec.md), [tasks.md:118](file:tasks.md) | **accepted-codex** | tasks 5.3.1 改为:`disputed-permanent-drift 但 drift_reason < 50 字 → finish_gate exit 2 阻断`(非 WARN) |
| **N1 §10 桥接段** | 没桥接(直接说"acceptance evidence 是 capability 延伸")(design.md:216) | recommend (non-blocker) | 主 spec Purpose 偏 examples/ bundle acceptance;未来 reviewer 可能质疑应抽 ai-workflow;§10 加桥接段更稳;[openspec/specs/examples-and-acceptance/spec.md:5](file:main-spec), [design.md:216](file:design.md), [design.md:262](file:design.md) | **accepted-codex** | design.md §10 末尾追加桥接段:本 delta **临时归** examples-and-acceptance(因该 capability 已有 acceptance artifact 概念,最低成本可达);**不等于建立长期 ai-workflow capability**;未来按 §11.3 触发条件另起 change 抽迁移 |
| **N2 micro_tasks 独立 Scenario** | 不加(用 mapping 表覆盖) | recommend (non-blocker) | state machine 把 `execution_plan.md` + `micro_tasks.md` 都列为 S3 必需,但 spec Scenario 1 + P4 fence 仅显式覆盖 `execution_plan.md`;[design.md:72](file:design.md), [tasks.md:114](file:tasks.md) | **accepted-claude** | reason: design.md §3 mapping 表已把 `micro_tasks.md` 与 `execution_plan.md` 列为同源,共用 `tasks.md#X.Y` 锚点;`forgeue_change_state.py --writeback-check` 同一 parser 扫两文件,不需独立 Scenario(spec.md Scenario 1 覆盖 plan + tasks 锚点协议;tool 实现层共用,fence test 5.3.1 type 2 已隐含覆盖 micro_tasks)— 25 字 ✓ |
| **N3 11 字段 vs 12 key** | 文档反复称"11 字段"(proposal/design/tasks/spec) | recommend (non-blocker) | 实际 frontmatter 含 `change_id` 是 12 个 key;工具按数量写死会出错;[proposal.md:20](file:proposal.md), [design.md:94](file:design.md), [forgeue-fusion-cross_check.md:130](file:notes) | **accepted-codex** | proposal/design/tasks/spec 全部改为"12 key(11 audit + 1 change_id wrapper)"统一措辞 |

## C. Disputed Items Pending Resolution

`disputed_open: 0`。9 项发现全部已解决:6 blocker + 2 non-blocker accepted-codex(已修 contract);1 non-blocker(N2)accepted-claude(reason ≥ 20 字)。

无 `disputed-pending` / `disputed-blocker` / `disputed-permanent-drift` 项。

## D. Verification Note

### D.1 独立验证(沿 ForgeUE memory `feedback_verify_external_reviews`)

Claude 对 codex review 提的 9 项发现逐条独立验证 file:line evidence(2026-04-26 22:30):

| ID | Codex claim 引用 | Claude verify 结果 | 结论 |
|---|---|---|---|
| B1 | proposal.md:25-27 写 "无 delta" + design.md:216 / spec.md:11 写有 delta | 实测 `sed -n '23,32p' proposal.md` 显示三行确实写 "无";design.md:216 / spec.md:11 实测有 delta | **真实 contract drift** |
| B2 | tasks.md:158 7.5.1 SKIP + design.md:228-230 写有 delta | 实测 `sed -n '155,165p' tasks.md` 显示 7.5.1 SKIP;design.md:228 实测有 delta | **真实 contract drift** |
| B3 | openspec/config.yaml:84-87 强制 Validation/Non-Goals | 实测 `sed -n '80,95p' openspec/config.yaml` 显示行 84/86/87 确实是 "Delta spec MUST" 这两个 section | **真实 (config 强制 + spec 缺)** |
| B4 | design.md:120-125 4 类 named DRIFT vs tasks.md:74 拆错 | 实测 design.md:120-128 显示 4 类 named taxonomy;tasks.md:74-78 显示拆为"锚点 / diff / aligned / writeback"非 named | **真实不一致** |
| B5 | design.md heading `### §11 Reasoning Notes` vs spec.md Scenario 3 引用 `## Reasoning Notes` | 实测 design.md:232 是 `### §11 Reasoning Notes`;spec.md:31 是 `## Reasoning Notes` | **真实 heading level 不一致** |
| B6 | tasks.md:118 WARN vs design.md:118 / spec.md:13 must ≥ 50 | 实测 design.md:118 是"必有 ≥ 50 字 drift_reason";tasks.md:118 是"< 50 → WARN" | **真实 severity 不一致** |
| N1 | design.md:216 §10 + 主 spec Purpose | 主 spec 实际偏 bundle acceptance;§10 论证可加桥接 | **建议合理** |
| N2 | design.md:72 / tasks.md:114 | mapping 表确实包含 micro_tasks.md;fence 仅显式 plan | **建议合理但已覆盖** |
| N3 | proposal/design/tasks/spec 多处"11 字段" | grep 实测 9 处出现"11 字段";frontmatter 实际 12 key | **真实措辞不准** |

**全部 verified = true**。无 codex 虚构 claim。

### D.2 修复完整性

修复后:

- ✅ `proposal.md` Capabilities 段已重写,显式 Modified=examples-and-acceptance + 解释为 capability 行为延伸
- ✅ `design.md` heading 改 `## Reasoning Notes` + §11.1-§11.4 改 level 3 + §10 加桥接段 + N3 12 key 改完(4 处 replace_all)
- ✅ `specs/examples-and-acceptance/spec.md` 末尾加 `## Validation`(指向 5 个测试文件)+ `## Non-Goals`(6 条不做 + heading 引用顺移到 `## Reasoning Notes` 已与 design.md 一致 + N3 12 key 改完)
- ✅ `tasks.md` 7.5.1 改 REQUIRED + 4.3 / 5.3.1 用 4 类 named DRIFT + reason < 50 改 blocker + N3 12 key 改完(replace_all + 1 处)
- ✅ `openspec validate fuse-openspec-superpowers-workflow --strict` exit 0 PASS

### D.3 进 P1 前置

- `disputed_open: 0` ✓
- contract 与 design/spec/tasks 内部一致(无 drift) ✓
- frontmatter `aligned_with_contract: true`(本 cross-check 自身已 align) ✓
- strict validate PASS ✓
- 可继续 P1(workflow docs)

### D.4 与 §17 正式 cross-check 协议的关系

本次是 **stage S2→S3 design review hook 的手工预演**(`/forgeue:change-plan` P2 才实装)。与 §A1 Pre-P0 plan-level cross-check 类似但不同 layer:

- Pre-P0 cross-check(`notes/pre_p0/forgeue-fusion-cross_check.md`):plan-level;在 OpenSpec lifecycle 之前;Codex 独立产 alternative 方案;cross-check 4 项裁决全 A
- 本次 design cross-check(`review/design_cross_check.md`):contract-level;在 P0 contract artifact 起草之后、P1 docs 之前;Codex 评 P0 contract 自身一致性;cross-check 9 项全部 accepted-codex/claude

archive 时两次 cross-check evidence 都保留(整 change 目录随 archive 走),作完整 review 历史。

未来其他 change 走 `/forgeue:change-plan` 正式 cross-check 时:tools 实装后(P3),`forgeue_change_state.py --writeback-check` 自动跑 4 类 named DRIFT 检测;`forgeue_finish_gate.py` 自动跑 frontmatter 全检 + writeback_commit `git rev-parse` 二次校验;disputed_open 由工具机器化跟踪不依赖手工。
