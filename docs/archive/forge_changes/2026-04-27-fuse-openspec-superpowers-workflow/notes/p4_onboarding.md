---
purpose: P4 阶段 onboarding,新会话用此文件快速对齐到 P4 起点状态
created_at: 2026-04-27
target_session: new Claude Code session(本 change P0+P1+P2+P3 已完成,准备进 P4)
note: |
  本文件不是 evidence,是 onboarding helper。新会话 Claude 读完即知道 P4 任务全貌 + 必读 contract + P3 review 教训 + C1/C1'/C2/C3 fix history + 已落地的 5 个新协议(verbatim-first / helper-vs-formal / evidence_type 索引 / balanced quote / codex slash unlock)。
  archive 时随 change 走但仅作历史 reference,不影响 finish gate(notes/ 子目录允许 helper,无 12-key 强制)。
---

# P4 Onboarding: fuse-openspec-superpowers-workflow

## 你现在的状态(新会话 Claude 必读)

你被开启在 ForgeUE 项目(`D:\ClaudeProject\ForgeUE_claude`)的新会话里,**继续推进 active OpenSpec change `fuse-openspec-superpowers-workflow` 的 P4 阶段**(测试 / fixture / fence)。

### 项目环境

- Windows 11 + Git-Bash + D: 盘
- Python 3.13(检查:`python --version`)
- pytest baseline:**848 tests**(P3 milestone 后 `python -m pytest --collect-only -q | tail -5` 实测)
- codex CLI 已装(`codex-cli 0.125.0`,ChatGPT 已登录)
- codex 插件已装在 `~/.claude-max/plugins/cache/openai-codex/codex/1.0.4/`
- Superpowers plugin 已装(全局,12 skills + 7 agents + 4 hooks)

### P0+P1+P2+P3 已完成(60 任务 done / 91 总)

milestone commits 链:

```
5dd870c  chore: unlock /codex:review + adversarial-review + status + result + cancel for Claude
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

P3 详情(在 P4 起草 fence test 时必懂):

- **regular review**(151,133 tokens):12 finding,7 blocker + 5 non-blocker,全 verified TRUE
- **adversarial review**(234,370 tokens):14 finding(6 verified-ok 复查 C1 + 5 NEW blocker + 2 non-blocker + 1 nit),全 verified TRUE
- 4 个 fix iteration:
  - **C1**(regular code-only):F1 / F4 / F5 / F7 / F11 / F12 — 6 项纯 code 修
  - **C1'**(adversarial code-only):F7-adv / F8-adv / F9-adv / F10-adv / F11-adv / F12-adv / F13-adv / F14-adv — 8 项纯 code 修
  - **C2**(code + design.md 写回):regular F2 / F3 — 2 项 code+contract
  - **C3**(contract 澄清):regular F6 / F8 / F9 / F10 — 4 项 contract 写回 design.md / tasks.md
- 4 份 evidence:
  - `review/p3_tools_review_codex.md`(regular,verbatim + 验证 + 12 finding)
  - `review/p3_tools_cross_check.md`(regular cross-check A/B/C/D,disputed_open: 0)
  - `review/p3_tools_adversarial_review_codex.md`(adversarial verbatim + 14 finding)
  - `review/p3_tools_adversarial_cross_check.md`(adversarial cross-check 14 + 6 同步处理 = 20 row matrix,disputed_open: 0)
  - 全部 `drift_decision: written-back-to-design`,`writeback_commit: d5630a1050ab1ba3968f443f1064d377d968047d`,`aligned_with_contract: true`

### P4 阶段任务全貌(tasks.md §5)

§5.1-§5.7 共 ~20 个 fence test 文件 + 4 个 fixture(总计约 24 task items)。

**§5.1 fixture(4 项)**:
- 5.1.1 `tests/fixtures/forgeue_workflow/builders.py`(deterministic change-tree builder;构造 evidence + frontmatter + tasks.md 等)
- 5.1.2 `tests/fixtures/forgeue_workflow/fake_change_minimal/`(S1 状态固件:仅 proposal.md,无 design/tasks)
- 5.1.3 `tests/fixtures/forgeue_workflow/fake_change_complete/`(S8 状态固件:全 evidence + frontmatter aligned + writeback_commit 真)
- 5.1.4 `tests/fixtures/forgeue_workflow/fake_change_with_drift/`(各类 DRIFT 固件 — 4 类 named DRIFT 各一个 + frontmatter health issue)

**§5.2 5 tool 单测(5 项,各 ~150-300 行)**:
- 5.2.1 `tests/unit/test_forgeue_env_detect.py`
- 5.2.2 `tests/unit/test_forgeue_change_state.py`
- 5.2.3 `tests/unit/test_forgeue_verify.py`
- 5.2.4 `tests/unit/test_forgeue_doc_sync_check.py`
- 5.2.5 `tests/unit/test_forgeue_finish_gate.py`

**§5.3 回写检测 fence(1 项,核心)**:
- 5.3.1 `tests/unit/test_forgeue_writeback_detection.py` — 4 类 named DRIFT 各 1 fixture + frontmatter health 检查全覆盖(详 spec.md ADDED Requirement Scenarios 1-3)

**§5.4 markdown lint fence(4 项)**:
- 5.4.1 `tests/unit/test_forgeue_workflow_plugin_invocation.py`(8 forgeue cmd md 含 /codex:adversarial-review 或 /codex:review;无 /codex:rescue;无 --enable-review-gate)
- 5.4.2 `tests/unit/test_forgeue_cross_check_format.py`(*_cross_check.md frontmatter disputed_open + body A/B/C/D 段)
- 5.4.3 `tests/unit/test_forgeue_skill_markdown.py`(2 forgeue-* SKILL.md frontmatter 含 name/description/license/compat/metadata)
- 5.4.4 `tests/unit/test_forgeue_command_markdown.py`(8 cmd md 含 frontmatter + Steps + Output + Guardrails 段)

**§5.5 反模式 fence(2 项,防回归)**:
- 5.5.1 `tests/unit/test_forgeue_codex_review_no_skill_files.py`(`.codex/skills/forgeue-*-review/` 必不存在)
- 5.5.2 `tests/unit/test_forgeue_no_duplicated_tdd_skill.py`(`.claude/skills/forgeue-superpowers-tdd-execution/` 必不存在)

**§5.6 横切 fence(3 项)**:
- 5.6.1 `tests/unit/test_forgeue_workflow_no_paid_default.py`(扫 5 tool + 8 cmd md,grep `--level 1` `--level 2` `paid` `live` 默认不开)
- 5.6.2 `tests/unit/test_forgeue_workflow_ascii_markers.py`(扫 5 tool 源,断言 stdout 仅 7 ASCII 标记)
- 5.6.3 `tests/unit/test_forgeue_workflow_no_hardcoded_test_count.py`(扫 5 tool 源,断言无 `== 848` 类硬编码)

**§5.7 全量回归(2 项)**:
- 5.7.1 `pytest -q tests/unit/test_forgeue_*.py` 全绿
- 5.7.2 `python -m pytest -q` 整体回归(数量以实测为准,基线 848 + P4 新增 fence ≈ 880-900)

## 必读文件清单(按顺序读)

读完前 7 项再开始 P4 工作;后 4 项作 reference 按需读。

```bash
# P4 必读(契约 + P3 fix history + 协议)
cat openspec/changes/fuse-openspec-superpowers-workflow/proposal.md
cat openspec/changes/fuse-openspec-superpowers-workflow/design.md  # 重点:§3(全段:12-key + 4 DRIFT taxonomy + Helper-vs-formal + REQUIRED at archive + Cross-check Protocol + Codex Review Output Exposure Protocol verbatim-first)+ §5(Tool Design 表)+ §11 Reasoning Notes
cat openspec/changes/fuse-openspec-superpowers-workflow/tasks.md   # 重点:§5(P4 任务明细)+ §4.3/§4.5/§4.6(P3 写回后的 exit code + finish_gate 详细)
cat openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md  # ADDED Requirement + 3 Scenarios

# P3 review evidence(P4 fence 设计需对齐这些)
cat openspec/changes/fuse-openspec-superpowers-workflow/review/p3_tools_review_codex.md       # 12 finding 详
cat openspec/changes/fuse-openspec-superpowers-workflow/review/p3_tools_adversarial_review_codex.md  # 14 finding 详
cat openspec/changes/fuse-openspec-superpowers-workflow/review/p3_tools_cross_check.md        # 12 cross-check matrix
cat openspec/changes/fuse-openspec-superpowers-workflow/review/p3_tools_adversarial_cross_check.md  # 14+6 cross-check matrix(含 D-XXX 决策点)

# P4 fixture / fence 设计参考
cat openspec/changes/fuse-openspec-superpowers-workflow/notes/p3_self_test.md  # P3 §4.7 5-tool self-test 矩阵
cat docs/ai_workflow/validation_matrix.md                                       # forgeue_verify.py 契约源
cat probes/_output.py + cat src/framework/comparison/cli.py                    # ASCII / argparse 参考

# 已 archived change 的 fence test 范本(参考结构)
ls tests/unit/test_*.py | head -20
cat tests/unit/test_event_bus.py  # 经典 fence test 范本(L4)
cat tests/unit/test_visual_review_image_compress.py  # frontmatter 解析等同思路的 test 范本
```

## P3 落地的 5 个**新协议**(P4 fence test 必对齐这些)

P3 在 design.md §3 + 代码层落地了多个新协议,P4 fence 测的是这些行为:

### 1. **Codex Review Output Exposure Protocol(verbatim-first)** — design.md §3

Claude 调 codex review(slash 或 path B)→ 同回复内必含 4 件:verbatim output + 独立验证表 + finding 分类 + Resolution 提议。**P4 fence 不直接测此协议**(协议是 Claude 行为约束,不是工具行为),但相关 evidence 解析逻辑(`finish_gate` 验 cross-check evidence 的 A/B/C/D)受影响。

### 2. **Helper vs formal evidence subdir** — design.md §3 + `forgeue_finish_gate.py::check_malformed_evidence`

- `notes/`:helper bucket,允许任意 frontmatter shape(p3_onboarding.md / p4_onboarding.md / p3_self_test.md 这类)
- `execution/` / `review/` / `verification/`:formal evidence bucket,**强制**含 `change_id` AND `evidence_type`
- finish_gate 扫 formal 子目录缺 12-key 的文件 → blocker `evidence_malformed`

P4 §5.2.5 finish_gate 单测必覆盖此分支:fixture 中 `notes/` 放 helper(无 frontmatter)+ `review/` 放缺 frontmatter 的 file → finish_gate 仅 `review/` 报 evidence_malformed,`notes/` 不报。

### 3. **REQUIRED evidence indexed by evidence_type**(不绑 file path) — design.md §3

`finish_gate::check_evidence_completeness` 扫所有 evidence,按 frontmatter `evidence_type` 索引,不绑死 file path。`p3_tools_review_codex.md` 与 `codex_verification_review.md` 等价(都是 `evidence_type: codex_verification_review`)。

claude-code+plugin REQUIRED 6 项:codex_design_review / codex_plan_review / codex_verification_review / codex_adversarial_review / design_cross_check / plan_cross_check。base REQUIRED 3 项:verify_report / doc_sync_report / superpowers_review。

P4 §5.2.5 fence:fixture 中放评估 file 用任意名,frontmatter 只要 `evidence_type` 对就视作 fulfill REQUIRED。

### 4. **DRIFT 2 anchor scope 限定** — `forgeue_change_state.py::detect_drift_anchor`

只扫 evidence_type ∈ {`execution_plan`, `micro_tasks`}。其他 evidence(codex_*_review、cross_check 等)quote `tasks.md#X.Y` 作示例不报 DRIFT。

P4 §5.3.1 fence:fixture 中执行该协议:
- `execution/execution_plan.md` 含 `tasks.md#99.1` not in tasks → DRIFT 2(exit 5)
- `review/codex_design_review.md` 同样 quote `tasks.md#99.1`(spec.md 占位例)→ **不报 DRIFT**

### 5. **Frontmatter 严格 12-key(`created_at` 移到 body)** — verify_report + finish_gate_report

- 12-key:`change_id` + 11 audit(`stage` / `evidence_type` / `contract_refs` / `aligned_with_contract` / `drift_decision` / `writeback_commit` / `drift_reason` / `reasoning_notes_anchor` / `detected_env` / `triggered_by` / `codex_plugin_available`)
- `created_at` 在 body `_Generated by ... at <iso>_` 行,不进 frontmatter
- 例外:cross-check evidence 的 frontmatter 必含 `created_at` / `resolved_at` / `disputed_open` / `codex_review_ref`(per design.md §3 cross-check protocol)

P4 §5.2.3 + §5.2.5 fence:验证 verify_report / finish_gate_report frontmatter 严格 12-key,`created_at` 不在 frontmatter。

### 6. **Anchor 平衡 quote + ≥ 20 words / ≥ 60 chars 段落校验** — `_anchor_resolves` + `_is_substantive_paragraph`

- regex 平衡 quote 4 alternation:bare / backtick / single / double;不接受不配对 `'foo` 或 `foo"`
- 段落字数双门槛:`len(text.split()) >= 20`(英文)OR `len(text.replace(' ','').replace('\n',''))-空白计数 >= 60`(中文)

P4 §5.2.5 fence + §5.3.1 fence:fixture `disputed-permanent-drift` 4 个边界:
- balanced quote → resolves OK
- unmatched quote → `reasoning_notes_anchor_unresolved` blocker
- short paragraph(< 20 words AND < 60 chars)→ `reasoning_notes_anchor_paragraph_too_short` blocker
- substantive paragraph → resolves OK

### 7. **subprocess utf-8 显式 encoding** — `_common.py` + 4 tool

6 处 `subprocess.run(... text=True, encoding="utf-8", errors="replace")`。Windows GBK 默认会 mangle 子进程 utf-8 stdout。

P4 §5.6.2 ASCII fence 顺带覆盖:扫源码 `subprocess.run(.+text=True` 必须紧跟 `encoding=` 设定;不允许 raw `text=True` 不带 encoding。

### 8. **codex slash unlock(.claude/commands/codex/)** — 5 个 local override

新会话默认就生效:`/codex:review` / `/codex:adversarial-review` / `/codex:status` / `/codex:result` / `/codex:cancel` 全部 Claude 可调。在 skills 列表里能看到。

P4 §5.4.1 fence(plugin invocation):8 个 `/forgeue:change-*` 命令文件中**仍然不允出现** `/codex:rescue` 字面(workflow-banned),但 `/codex:adversarial-review` `/codex:review` 等期望出现(stage hook)。fence 测此协议。

## C2/C3 写回到 design.md 的关键内容(P4 fence 设计必对齐)

详 design.md §3 / §5,以下是核心列表:

- **§3 4 类 DRIFT heuristic 限定声明**(F10 regular):每类 DRIFT 显式 scope 限定(D-XXX 标识 / `python` fence 等)
- **§3 Helper vs formal evidence subdir 分类**(F3 regular):`notes/` 允许 helper / 其他子目录强制 12-key
- **§3 REQUIRED at archive 协议**(F2 regular):base 3 项 + claude-code+plugin 6 项
- **§3 Codex Review Output Exposure Protocol verbatim-first**(P3 实证后)
- **§5 Tool Design 表 exit code 统一**(F6 regular + F8 regular):
  - `forgeue_change_state`:0/1/2/3/5(exit 4 deprecated)
  - `forgeue_doc_sync_check`:0/1(IO/git failure)/2(DRIFT)/3(change 不存)
  - `forgeue_verify` / `forgeue_finish_gate`:0/1/2/3 各自语义清晰

P4 §5.2.x 单测的 exit code 断言必须按这版 contract,不按 P3 起草版。

## 决议(P0/P1/P2/P3 不可变,P4 必须遵守)

```yaml
# Pre-P0 锁定
D-CommandsCount: 8           D-DocsCount: 1 份合并
D-FrontmatterSchema: 12 key  D-FutureCapabilitySpec: 当前不抽

# P0 设计决议 + P3 写回更新
14.2 命名 = /forgeue:change-*       14.5 self-host
14.16 codex-plugin-cc 可选          14.17 review-gate 禁用
14.18 design + plan cross-check 强制
D-NoConsoleScripts                  D-EnvDetectLayers(5 层 + codex-cli signal)
D-AdversarialBinding                D-DisputedReason20
D-DocSync10Files                    D-SettingFileInGit
D-UnknownNoPrompt

# P3 写回新增 D-IDs(在 cross-check 内,不进 design.md §11):
D-EnvDetectScanPattern         D-FinishGateEvidenceList
D-FilterFormalEvidence         D-PendingDriftDecision
D-AnchorRegexFormat            D-ValidateStateExit
D-MeshFailureReason            D-DocSyncExit3
D-DriftAnchorScope             D-DriftHeuristicNarrow
D-VerifyReportExtraFields      D-SubprocessEncoding
D-RequiredEvidencePathBound    D-MalformedEvidenceSkipped
```

## 禁令(P4 必须遵守)

- **禁修区**:
  - `.claude/commands/opsx/*` / `.claude/skills/openspec-*/` / `.codex/skills/openspec-*/`(已 commit OpenSpec v1.3 产物,不再动)
  - `tools/` 已 5 tool + _common 完成,P4 **不修改 tools/**(只写 tests/);除非 P4 fence test 暴露 tool bug 才回写
  - 五件套(SRS/HLD/LLD/test_spec/acceptance_report)
  - `pyproject.toml` deps(stdlib only 是硬契约)
  - 已 archived changes
- **禁创**:
  - 不创 `.codex/skills/forgeue-*-review/`(P4 §5.5.1 fence 守门)
  - 不创 `.claude/skills/forgeue-superpowers-tdd-execution/`(P4 §5.5.2 fence 守门)
- **行为约束**:
  - 不引 paid provider / live UE / live ComfyUI 默认调用(env guard `{1,true,yes,on}`)
  - fence test 必须 stdlib + tmp_path,不依赖真实 codex / API
  - 不 mock 关键边界 — 用 fixture 真材实料
  - 不硬编码 pytest 总数(`== 848` 类)
  - 7 ASCII 标记(`[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]`),无 emoji

## ForgeUE memory 精神(P4 必遵守)

- `feedback_verify_external_reviews`:codex / 外部 review 的 claim 必独立 file:line 验证
- `feedback_decisive_approval`:给论证 + 选项 + tradeoffs up-front,等用户绿灯后 execute fully
- `feedback_no_silent_retry_on_billable_api`:贵族 API 失败 surface job_id,不 silent retry
- `feedback_no_fabricate_external_data`:pricing/endpoint 必有 sourced_on 或 null + TODO
- `feedback_ascii_only_in_adhoc_scripts`:Windows GBK 不允 emoji,只用 7 ASCII
- `feedback_contract_vs_quality_separation`:contract 测试用 fixture + FakeAdapter,real-provider 走 opt-in probe
- `env_windows`:`/tmp/...` 是 C: 系统目录,产物落 `./demo_artifacts/` / `./artifacts/`
- `user_language_chinese`:中文沟通,技术名词保留英文

## P4 启动指引

读完上述上下文后,**直接开始 §5.1**:

1. **§5.1 fixtures 先行**(builder + 3 fake_change 模板)— 这是后面所有单测和 fence 的 foundation
2. **§5.2 5 tool 单测**(env_detect / change_state / verify / doc_sync_check / finish_gate)
3. **§5.3 回写检测 fence**(核心,4 类 named DRIFT + frontmatter health 全覆盖)
4. **§5.4 markdown lint fence**(4 项)
5. **§5.5 反模式 fence**(2 项防回归)
6. **§5.6 横切 fence**(3 项 cross-cutting)
7. **§5.7 全量回归**(pytest 无 regression)
8. tasks.md §5.1-§5.7 全 [x]
9. P4 完成 = 所有 fence 全绿 + 用户认可 + (可选)P4 codex review

**起草顺序建议**(最小依赖链):
- 先 builder.py(其他 fixture 都用它)
- 再 fake_change_minimal/(测 S0/S1)
- 再 fake_change_complete/(测 S5-S8)
- 再 fake_change_with_drift/(测 4 类 DRIFT)
- 然后 5 tool 单测各自(各依赖对应 fixture)
- 最后 fence(横切 + lint + 反模式)

**self-host loop**:每次 fence 写完跑一遍 `pytest -q tests/unit/test_forgeue_*.py`,**5 tool self-test 不能回归**(env_detect / change_state / verify exit 0;doc_sync / finish_gate exit 2 是 self-host 真实 DRIFT)。

## P4 完成后(下阶段)

P4 完成后进 P5(`tasks.md §6`),走 `forgeue_verify` Level 0 验证 + 写 verify_report evidence(可选 P4 之后跑 codex `/codex:review --base main` 补一道 review,**用 unlock 后的 slash 命令真正走 broker**,不再 path B)。

P5-P9 流程:Level 0/1/2 verify → Documentation Sync Gate(`/forgeue:change-doc-sync`)→ Superpowers requesting-code-review finalize + codex `/codex:adversarial-review` → finish gate → archive。

## 当前 git 状态(P4 起点)

```
HEAD: 5dd870c (chore: unlock /codex:review + ...)
本地领先 origin/chore/openspec-superpowers: 6 commits
working tree:
  ?? openspec/changes/fuse-openspec-superpowers-workflow/verification/(P3 self-test 中间态产物,可清)
```

清 stale verification(可选):`rm -rf openspec/changes/fuse-openspec-superpowers-workflow/verification/`

P4 起步后产物落:
- `tests/fixtures/forgeue_workflow/builders.py` + `fake_change_*/`
- `tests/unit/test_forgeue_*.py`(~16 个新文件)
- `openspec/changes/fuse-openspec-superpowers-workflow/tasks.md` §5.1-§5.7 全 [x]
- 视情况:`review/p4_*_review_codex.md`(P4 完成后跑 codex review;走 slash 命令)+ cross-check
