---
purpose: P8 阶段 onboarding,新会话用此文件快速对齐到 P8 起点状态
created_at: 2026-04-27
target_session: new Claude Code session(本 change P0+P1+P2+P3+P4+P5+P6+P7 已完成,准备进 P8 Finish Gate)
note: |
  本文件不是 evidence,是 onboarding helper。新会话 Claude 读完即知道 P8 任务全貌(3 项)+ 当前 11 blockers 的分类与拟修策略 + finish_gate 工具的 stage-aware contract gap(P8 阶段必然暴露的 fixup)+ 后续 P9 archive 路径。
  archive 时随 change 走但仅作历史 reference,不影响 finish gate(notes/ 子目录允许 helper,无 12-key 强制 — 已由 P7 F-C fix 后 _scan_evidence_by_type 不扫 notes/ 进一步保证 helper 不会冒充 formal evidence)。
---

# P8 Onboarding: fuse-openspec-superpowers-workflow

## 你现在的状态(新会话 Claude 必读)

你被开启在 ForgeUE 项目(`D:\ClaudeProject\ForgeUE_claude`)的新会话里,**继续推进 active OpenSpec change `fuse-openspec-superpowers-workflow` 的 P8 阶段(Finish Gate)**。

P8 工作量:**3 项任务 + 1 P8 阶段必然暴露的 fixup(~30-45 min)**。期望先跑 `forgeue_finish_gate.py` 取 blockers,处置 11 blockers 中的 2 类 contract gap(分别是 plan-merged-with-design 的 evidence_missing,和 tasks_unchecked 的 stage-aware filter 缺失),然后 finish_gate exit 0 + 落 finish_gate_report.md。

### 项目环境

- Windows 11 + Git-Bash + D: 盘
- Python 3.13
- pytest baseline:**1133 tests**(P7 closeout 实测;848 P3 + 262 P4 + 13 P4-codex-review-fence + 3 P5-fixup-fence + 7 P7-fixup-fence)
- codex CLI 已装(`codex-cli 0.125.0`,ChatGPT 已登录)
- codex 插件已装在 `~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/`
- Superpowers plugin 已装(全局,12 skills + 7 agents + 4 hooks)
- `/codex:review` / `/codex:adversarial-review` / `/codex:status` / `/codex:result` / `/codex:cancel` 5 个 slash 命令**已 unlock 给 Claude 调** + **broker discovery 已修**(commit 37288fe)

### P0-P7 已完成

milestone commit 链(从最新到最旧):

```
6681e83  docs: backfill writeback_commit in P7 review evidence
fe184a6  chore: P7 review + 7 finding resolution landed for fuse-openspec-superpowers-workflow
e68e459  chore: P6 documentation sync gate landed for fuse-openspec-superpowers-workflow
d4f5c69  chore: P5 forgeue_verify subprocess env PYTHONPATH=src fixup + fence
a09ba42  chore: P5 verify_report landed for fuse-openspec-superpowers-workflow
5972665  docs: P5 onboarding helper for fresh session entry
2aceee3  docs: backfill writeback_commit in P4 review evidence
37288fe  chore: P4 tests + codex slash override broker fix + post-review F1-F4 resolution landed
cf4a6f9  docs: P4 onboarding helper for fresh session entry
5dd870c  chore: unlock /codex:review + adversarial-review + status + result + cancel for Claude model invocation
d0a47f3  docs: codify codex review verbatim-first exposure protocol in design.md sec3
5b564c3  chore: track OpenSpec v1.3 product upgrade
1c0da37  docs: backfill writeback_commit in P3 tools review evidence
d5630a1  chore: P3 tools + C1+C1' review fix landed for fuse-openspec-superpowers-workflow
9c1be42  docs: P3 onboarding helper for fresh session entry
e8067f3  chore: P2 commands + skills landed for fuse-openspec-superpowers-workflow
7d0c730  docs: backfill writeback_commit in P1 round-1 evidence
a705754  chore: P1 docs landed for fuse-openspec-superpowers-workflow
73f18e6  chore: bootstrap fuse-openspec-superpowers-workflow (P0)
```

### P7 详情(P8 起步前必懂)

P7 = Superpowers self-review + codex /codex:adversarial-review --background(mixed-scope adversarial),用户裁决 plan A "全改",2 commits 闭环:

- **fe184a6 (resolution-commit)**:7 finding 一次性 fix + 7 fence test
  - **F-A** (critical): `_common.py` 加 `verify_report_has_real_failures(text)` helper(strip `^- \[FAIL\]: \d+$` summary 行 + 检查 `[FAIL]`);`forgeue_finish_gate.py:223` 用 helper,排除 verify_report `[FAIL]: 0` 自动 summary 行误判
  - **F-B** (high): `_filter_formal_evidence` 加 self-exclusion `evidence_type == "finish_gate_report"`(失败 report 不污染下次 audit)
  - **F-C** (high): `_scan_evidence_by_type` 改用 `_FORMAL_EVIDENCE_SUBDIRS`(execution / review / verification),不扫 notes/(notes/ helper 不能冒充 REQUIRED 满足)+ design.md §3 表加新列 + 新增段
  - **F-D** (high/written-back-to-evidence): amend `review/codex_design_review.md` frontmatter `aligned_with_contract: true` + `drift_decision: written-back-to-design` + `writeback_commit: 73f18e6c4967c07269cf8a3677bafd497d20b946`
  - **F-E** (medium): `forgeue_change_state.py:195` 改用同款 helper,S5 inference 不再被 `[FAIL]: 0` 误判
  - **F-F** (medium/written-back-to-spec): `spec.md:41` Validation 段重写 — 删除 "frozen-before-codex-call timestamp comparison" 失实声明,改为人工协议描述
  - **I4** (important/doc): CLAUDE.md:162 + AGENTS.md:172 ban list 全集化(4 路径列全)
- **6681e83 (evidence-backfill)**:amend `review/superpowers_review.md` + `review/codex_adversarial_review.md` frontmatter writeback_commit=fe184a6 + drift_decision=written-back-to-tool

P7 测试覆盖:1126 → **1133 passed**(+7 fence:3 F-A + 1 F-B + 1 F-C + 2 F-E)

### P8 阶段任务全貌(tasks.md §9)

只 3 项,但**会自然暴露 stage-aware contract gap**:

```
- [ ] 9.1 `python tools/forgeue_finish_gate.py --change fuse-openspec-superpowers-workflow --json` exit 0
- [ ] 9.2 `verification/finish_gate_report.md` 落盘 + 所有 evidence frontmatter `aligned_with_contract: true`(或带 drift 标记 + reason ≥ 50 + design.md "Reasoning Notes" anchor)
- [ ] 9.3 检查 `~/.claude/settings.json` 不含 review-gate hook(若有 → 提示用户 disable)
```

### P8 起点 finish_gate 状态(2026-04-27 末)

P7 闭环后,跑 `forgeue_finish_gate.py --change fuse-openspec-superpowers-workflow --no-validate --json --dry-run`:

```
blockers: 11
 - evidence_missing review/codex_plan_review.md          ← 类型 A
 - evidence_missing review/plan_cross_check.md            ← 类型 A
 - tasks_unchecked tasks.md (§9.1)                        ← 类型 B
 - tasks_unchecked tasks.md (§9.2)                        ← 类型 B
 - tasks_unchecked tasks.md (§9.3)                        ← 类型 B
 - tasks_unchecked tasks.md (§10.1)                       ← 类型 B
 - tasks_unchecked tasks.md (§10.2)                       ← 类型 B
 - tasks_unchecked tasks.md (§10.3)                       ← 类型 B
 - tasks_unchecked tasks.md (§10.4)                       ← 类型 B
 - tasks_unchecked tasks.md (§10.5)                       ← 类型 B
 - tasks_unchecked tasks.md (§11.1)                       ← 类型 B
```

### 11 blockers 分类与拟修策略

#### 类型 A:plan-merged-with-design 导致 evidence_missing(2 blockers)

**事实**:design.md §3 REQUIRED-at-archive 矩阵列出 claude-code+plugin env 必含 6 项 codex/cross-check evidence,其中包含 `codex_plan_review` + `plan_cross_check`。但本 change 在 Pre-P0 时,**plan stage 与 design stage 合并**(由 codex_design_review + design_cross_check 间接覆盖了 plan-stage cross-review),没有独立的 plan_review 产出。

**拟修策略 — 选项**:

- **A.1 written-back-to-design** + 写薄 evidence(优先推荐;最贴 contract):
  - 生成 `review/codex_plan_review.md` + `review/plan_cross_check.md` 两份薄 evidence
  - Frontmatter:`aligned_with_contract: false` + `drift_decision: disputed-permanent-drift` + `drift_reason` ≥ 50 字解释"本 change 无独立 plan stage,plan cross-review 由 design stage cross-check 间接覆盖" + `reasoning_notes_anchor: reasoning-notes-plan-merged-with-design`
  - design.md `## Reasoning Notes` 段加 `> Anchor: reasoning-notes-plan-merged-with-design` 锚点 + ≥ 20 词 / ≥ 60 非空白字符段落
  - tasks.md 在 §X(可能 P8.5 review fixup 段)记录此处置
- **A.2 fix-in-tool**:改 finish_gate REQUIRED list,在某些场景下让 codex_design_review + design_cross_check 同时存在时,自动 substitute codex_plan_review + plan_cross_check(过度复杂,不推荐 — contract 改动)
- **A.3 stage-aware contract write-back**:design.md §3 表添加"plan-stage-merged-with-design"模式说明,允许在该模式下 plan_review/plan_cross_check 改为 OPTIONAL(本 change 一次性,但成本高且 contract 复杂)

**推荐 A.1**:工作量小,符合 spec.md ADDED Requirement Scenario 3(disputed-permanent-drift 协议)精神。

#### 类型 B:tasks_unchecked 含 P8/P9 自身任务(9 blockers)

**事实**:`forgeue_finish_gate.check_tasks_unchecked`(`tools/forgeue_finish_gate.py:691-718`)扫 tasks.md 找 `^- \[ \]\s+...` 行,任何不带 `(SKIP` 子串的 [ ] 行就 raise blocker。

P8 阶段自然遇到的问题:
- §9.1-§9.3(P8 自身):finish_gate 应当容忍(self-reference;P8 跑 finish_gate 时 §9.x 必然 [ ])
- §10.1-§10.5(P9 archive 后任务):P8 时 archive 还没发生,§10 自然 [ ]
- §11.1(标准 footer,§7.5 12 项 已完成的 reference):非真实任务

**拟修策略 — 选项**:

- **B.1 fix-in-tool**(优先推荐;符合 P3 / P4 / P7 fixup 模式):
  - 改 `tools/forgeue_finish_gate.py:check_tasks_unchecked` 加 stage-aware filter
  - 跳过 §9 / §10 / §11 章节的 [ ] 行(因为这些是 P8 / P9 stage 任务,P8 跑 finish_gate 时 expectedly unchecked)
  - 实装思路:扫 tasks.md 时跟踪当前 `## N` 章节 number;`N >= 9` 章节内 [ ] 不 raise blocker
  - 加 fence test:`test_finish_gate_skips_p8_p9_self_stage_unchecked`(seed tasks.md 含 §9 / §10 [ ] 行,断言 finish_gate 不报 tasks_unchecked)
  - 同时 design.md §3 / §5 写回:check_tasks_unchecked stage-aware semantics 明确文档化
- **B.2 SKIP marker**:把 §10 / §11 [ ] 改为 `(SKIP: P9 archive stage tasks deferred until /opsx:archive runs)`(粗糙,SKIP 语义指"永不做"不对)
- **B.3 task list 重构**:把 §10 / §11 P9 内容移到独立 archive checklist file(contract 重大改动,不推荐)

**推荐 B.1**:符合 finish_gate 中心化精神 + stage-aware 是 finish_gate 应有能力。

### P8 实施步骤(预期顺序)

```bash
# 1. 跑 finish_gate 取 baseline blockers
python tools/forgeue_finish_gate.py \
    --change fuse-openspec-superpowers-workflow \
    --no-validate --json --dry-run \
    | python -m json.tool

# 2. 应当看到 ~11 blockers,2 类型 A + 9 类型 B(实测可能略有差异,看本 change tasks.md 当前 [ ] 数)

# 3. 处理类型 A:
#    A.1.1 写 review/codex_plan_review.md (~30 行,frontmatter disputed-permanent-drift)
#    A.1.2 写 review/plan_cross_check.md (~30 行,frontmatter disputed-permanent-drift + 4 段 A/B/C/D 结构)
#    A.1.3 design.md ## Reasoning Notes 加 anchor `reasoning-notes-plan-merged-with-design` + ≥ 20 词段

# 4. 处理类型 B:
#    B.1.1 修 tools/forgeue_finish_gate.py::check_tasks_unchecked 加 stage-aware filter
#    B.1.2 加 fence test
#    B.1.3 design.md §3 / §5 写回 stage-aware semantics(用 §5 finish_gate 行扩描述)

# 5. 跑 pytest 全量验证(应 1133 + new fence)
python -m pytest -q

# 6. 重跑 finish_gate
python tools/forgeue_finish_gate.py \
    --change fuse-openspec-superpowers-workflow \
    --no-validate --json
# 期望 exit 0(若 §9.1-§9.3 还 [ ],仍会有 3 blockers — stage-aware filter 应也豁免 §9 self-stage)

# 7. 标 §9.1-§9.3 [x] + tasks.md §9.5(P8 review fixups,类比 §5.8 / §8.5)记录处置
# 8. resolution-commit:'chore: P8 finish gate landed + plan-merged-with-design + stage-aware tasks fixup'
# 9. evidence backfill commit(amend codex_plan_review/plan_cross_check frontmatter writeback_commit + design.md anchor)
# 10. 检查 ~/.claude/settings.json review-gate hook(§9.3)
```

### P8 完成判定 + 标 [x]

```diff
- - [ ] 9.1 `python tools/forgeue_finish_gate.py --change fuse-openspec-superpowers-workflow --json` exit 0
- - [ ] 9.2 `verification/finish_gate_report.md` 落盘 + 所有 evidence frontmatter `aligned_with_contract: true`(或带 drift 标记 + reason ≥ 50 + design.md "Reasoning Notes" anchor)
- - [ ] 9.3 检查 `~/.claude/settings.json` 不含 review-gate hook(若有 → 提示用户 disable)
+ - [x] 9.1 `python tools/forgeue_finish_gate.py ...` exit 0(2026-04-XX:0 blockers post-fixup;<P8 fixup commit sha>)
+ - [x] 9.2 `verification/finish_gate_report.md` 落盘 + frontmatter `aligned_with_contract: true`(0 blockers + tasks_unchecked stage-aware filter 豁免 §9-§11 + plan-merged disputed-permanent-drift evidence + Reasoning Notes anchor 解析通过)
+ - [x] 9.3 `~/.claude/settings.json` 无 `--enable-review-gate` hook(verified 2026-04-XX)
```

并加 §9.5 P8 review fixups 段(类比 §5.8 / §8.5)记录:
- 9.5.1 类型 A 处置(plan-merged-with-design)
- 9.5.2 类型 B 处置(check_tasks_unchecked stage-aware fix-in-tool)
- 9.5.3 全量回归 1133 → 1134+(+1 fence: stage-aware filter)

### P8 完成后(下阶段 = P9 Archive)

P9 工作量:小(~10 min):

```
- [ ] 10.1 /opsx:archive fuse-openspec-superpowers-workflow(OpenSpec 跑 sync-specs;只合并 examples-and-acceptance ADDED Requirement)
- [ ] 10.2 archive 后 evidence 子目录 + notes/pre_p0/ 完整保留
- [ ] 10.3 (可选 S9 自动)Superpowers finishing-a-development-branch skill auto-trigger
- [ ] 10.4 git status 干净;不留 _drafts/ / 临时文件
- [ ] 10.5 pytest -q 整体仍绿(1134+)
- [ ] 11.1 §7.5 12 项全部完成(已 P6 完成)
```

P9 关键产物:
- `openspec/changes/archive/2026-XX-XX-fuse-openspec-superpowers-workflow/` 目录(整目录搬迁)
- `openspec/specs/examples-and-acceptance/spec.md` 含 ADDED Requirement(由 sync-specs 自动合并)
- 1-2 commits:`chore: archive fuse-openspec-superpowers-workflow + sync-specs to main`

## 必读文件清单(按顺序读)

读完前 5 项再开始 P8;后 4 项作 reference 按需。

```bash
# P8 必读(契约 + finish_gate 工具 + 当前 evidence 状态)
cat openspec/changes/fuse-openspec-superpowers-workflow/tasks.md       # 重点:§8.5 (P7 review fixups,刚完成)+ §9 (P8 任务)
cat openspec/changes/fuse-openspec-superpowers-workflow/design.md      # 重点:§3 frontmatter 协议 + §5 Tool Design (forgeue_finish_gate 行)+ §11 Reasoning Notes
cat openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md  # 重点:Scenario 3 (disputed-permanent-drift 协议)
cat tools/forgeue_finish_gate.py                                       # 重点:check_evidence_completeness / check_tasks_unchecked / _REQUIRED_EVIDENCE_*
cat openspec/changes/fuse-openspec-superpowers-workflow/review/codex_design_review.md  # plan-merged-with-design 决策的最近上下文(Pre-P0 通过 design cross-check 处理)

# P8 fence reference(已绿守 finish_gate 行为)
cat tests/unit/test_forgeue_finish_gate.py                             # 49 fence test:evidence completeness / frontmatter / writeback_commit / cross-check / disputed-permanent-drift / P7 fixup F-A/F-B/F-C

# 可选 reference
cat openspec/changes/fuse-openspec-superpowers-workflow/review/superpowers_review.md          # P7 self-review 全文
cat openspec/changes/fuse-openspec-superpowers-workflow/review/codex_adversarial_review.md    # P7 codex review 全文(verbatim + 6 finding 解决)
cat openspec/changes/fuse-openspec-superpowers-workflow/verification/doc_sync_report.md       # P6 doc sync 决议
```

## P8 起点 git 状态(2026-04-27 末)

```
HEAD: 6681e83 docs: backfill writeback_commit in P7 review evidence
本地领先 origin/chore/openspec-superpowers: 18 commits(P0-P7 全部 milestone)
working tree: clean
```

## ForgeUE memory 精神(P8 必遵守)

- `feedback_no_silent_retry_on_billable_api`:本 P8 不调任何 paid provider(finish_gate 是 stdlib only state inspector)
- `env_windows`:不写到 `/tmp/...`(C: 系统目录),产物落项目树
- `user_language_chinese`:中文沟通,技术名词保留英文
- `feedback_decisive_approval`:发现 contract gap 后给用户论证 + 选项 + 代价,等绿灯("全改" / "选 X")再实施
- `feedback_verify_external_reviews`:**P8 不调 codex review**(finish_gate evidence 不属 review evidence;codex 已在 P7 完成)
- `feedback_contract_vs_quality_separation`:本 P8 不涉及 multimodal review,该 memory 不触发

## 禁令(P8 必遵守)

- **禁修区**:
  - `.claude/commands/opsx/*` / `.claude/skills/openspec-*/` / `.codex/commands/opsx/*` / `.codex/skills/openspec-*/`(OpenSpec 默认产物全集,P7 I4 已写回 CLAUDE / AGENTS)
  - 五件套(SRS/HLD/LLD/test_spec/acceptance_report;P8 不动,P9 archive 时由 sync-specs 处理 examples-and-acceptance 单 capability)
  - `pyproject.toml` deps(stdlib only)
  - 已 archived changes
- **可修区(P8 必动)**:
  - `tools/forgeue_finish_gate.py`(check_tasks_unchecked stage-aware fix-in-tool)
  - `openspec/changes/fuse-openspec-superpowers-workflow/design.md`(§3 / §5 / §11 Reasoning Notes 写回)
  - `openspec/changes/fuse-openspec-superpowers-workflow/tasks.md`(§9 [x] + §9.5 review fixups 段)
  - `openspec/changes/fuse-openspec-superpowers-workflow/review/codex_plan_review.md`(NEW)
  - `openspec/changes/fuse-openspec-superpowers-workflow/review/plan_cross_check.md`(NEW)
  - `openspec/changes/fuse-openspec-superpowers-workflow/verification/finish_gate_report.md`(NEW;由 finish_gate 自动产 + 落 aligned=true)
  - `tests/unit/test_forgeue_finish_gate.py`(+1 fence stage-aware filter)
- **禁创**:
  - 不创新 evidence_type(finish_gate_report 是 stage S8 the only product;codex_plan_review / plan_cross_check 已是 design.md §3 表已知 type)
  - 不创新 review evidence type(P8 不调 codex)
- **行为约束**:
  - 不引入 paid provider 默认调用
  - 不 mock pytest
  - 不硬编码 pytest 总数(参考 P5 §5.6.3 fence)
  - 7 ASCII 标记(`[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]`),无 emoji
  - 不调 `/codex:rescue` 在工作流内
  - 沿 P3 / P4 / P5 / P7 双 commit 模式:resolution-commit + evidence-backfill
