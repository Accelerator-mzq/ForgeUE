---
purpose: P3 阶段 onboarding,新会话用此文件快速对齐到 P3 起点状态
created_at: 2026-04-26
target_session: new Claude Code session(本 change P0 + P1 + P2 已完成,准备进 P3)
note: |
  本文件不是 evidence,是 onboarding helper。新会话 Claude 读完此文件即知道 P3 任务全貌 + 必读 contract + 决议 + 禁令 + P1/P2 review 教训。
  archive 时随 change 走但仅作历史 reference,不影响 finish gate。
---

# P3 Onboarding: fuse-openspec-superpowers-workflow

## 你现在的状态(新会话 Claude 必读)

你被开启在 ForgeUE 项目(`D:\ClaudeProject\ForgeUE_claude`)的新会话里,**继续推进 active OpenSpec change `fuse-openspec-superpowers-workflow` 的 P3 阶段**。

### 项目环境

- Windows 11 + Git-Bash + D: 盘
- Python 3.12+
- `codex` CLI 已装(`codex-cli 0.125.0`)+ 已 ChatGPT 登录
- Superpowers plugin 已装(`~/.claude/plugins/` 全局,12 skills + 7 agents + 4 hooks)
- codex-plugin-cc **未装**(可选;P3 阶段不强依赖,跑 codex review 走 path B = `codex exec --sandbox read-only` 等价 codex:codex-rescue subagent)
- pytest baseline 848 passed(2026-04-26 实测;P3 写新 tool 后会增,数字以实测为准,不硬编码)

### Pre-P0 + P0 + P1 + P2 已完成(31/91 tasks)

- ✅ Pre-P0:plan-level cross-check(`notes/pre_p0/`)— 4 项用户裁决:D-CommandsCount=8 / D-DocsCount=1(合并)/ D-FrontmatterSchema=12 key / D-FutureCapabilitySpec=defer
- ✅ P0:`proposal.md` / `design.md` / `tasks.md` / `specs/examples-and-acceptance/spec.md` 全部落盘 + strict validate PASS;9 项 codex S2→S3 design review 全 resolved(详 `review/design_cross_check.md`,`disputed_open: 0`)
- ✅ P1:`docs/ai_workflow/forgeue_integrated_ai_workflow.md`(406 行,4 段 A/B/C/D)+ README.md §5/§8 升级 + design.md §3 加 Cross-check Protocol 子段(round-1 H1.1 writeback)
  - round-1:3 findings(H1.1 / H1.2 / M6.1)全 accepted-codex,evidence `review/p1_docs_review_codex.md`
  - round-2:6 findings(H2.1 / H4.1 / H5.1 / M1.1 / M1.2 / L3.1)全 accepted-codex,evidence `review/p1_docs_review_round2_codex.md`
  - milestone commit:`a7057545bb9c5ea7017f0ad7af8c46d030e571cc`(design.md §3 写回)+ backfill commit `7d0c730`(round-1 evidence sha 回填)
- ✅ P2:`.claude/commands/forgeue/change-{status,plan,apply,debug,verify,review,doc-sync,finish}.md`(8 commands)+ `.claude/skills/forgeue-{integrated-change-workflow,doc-sync-gate}/SKILL.md`(2 skills)+ tasks.md §3 全 [x]
  - self-audit:5 SA + P4 fence 5.4.1 prevalidation 全 CONFIRMED(grep 实测)
  - 2 fix iteration(P4 fence-a 字面 + SA-4 backbone 直接引)
  - codex round-1 卡 35min 后被 cancel,broker 自然清理;P2 codex review 推迟到 P4 之后
  - milestone commit:`e8067f3`

### 60 task pending(P3 起点)

下一个 task = **P3 阶段第一项 = §4.1 `tools/__init__.py`**(空文件,sys.path 注册 helper 不需要)。

P3 总共 7 个 task(§4.1-§4.7),全部新增 Python 文件到 `tools/`,**stdlib only,不引 Python runtime dep**。

## 必读文件清单(按顺序读)

读完前 5 项再开始 P3 工作;后 5 项作 reference 按需读。

```bash
# P3 必读(contract + 锁定决议 + 工具规约)
cat openspec/changes/fuse-openspec-superpowers-workflow/proposal.md            # Why / What Changes / Capabilities
cat openspec/changes/fuse-openspec-superpowers-workflow/design.md              # 重点:§3(12-key + 4 类 DRIFT + writeback + Cross-check Protocol)+ §5(Tool Design 表 + 横切要求)+ §11 Reasoning Notes
cat openspec/changes/fuse-openspec-superpowers-workflow/tasks.md               # §4 P3 工作明细 + §5.6 横切 fence(P3 必满足)+ §5.4.x markdown lint(P3 不动 commands/skills,但需了解)
cat openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md  # ADDED Requirement + 3 Scenarios(writeback 协议 / disputed-permanent-drift 约束 — finish_gate exit 2 真源)
cat openspec/specs/examples-and-acceptance/spec.md                             # 主 spec(archive 后合并;Scenarios 与 delta 一致)

# 历史 review 教训(P3 起草时避免重蹈)
cat openspec/changes/fuse-openspec-superpowers-workflow/review/design_cross_check.md       # P0 9 finding;尤其 B5 (## Reasoning Notes heading level 2)+ B6(< 50 字 阻断非 WARN)
cat openspec/changes/fuse-openspec-superpowers-workflow/review/p1_docs_review_codex.md     # P1 round-1 3 finding;尤其 H1.1(evidence 不能成新规范源)
cat openspec/changes/fuse-openspec-superpowers-workflow/review/p1_docs_review_round2_codex.md  # P1 round-2 6 finding;尤其 H4/H5(hook 描述 verbatim copy 不自由改写)+ M1.1(written-back-* 必有真实 commit)+ L3.1(no emoji)

# P3 user-facing 上下文(不动文件,作 reference)
cat docs/ai_workflow/forgeue_integrated_ai_workflow.md                         # 全局工作流文档,§A-§D
cat docs/ai_workflow/validation_matrix.md                                      # `tools/forgeue_verify.py` 是其机器版

# 代码模板 reference(P3 沿用 CLI / argparse / exit code 风格)
cat src/framework/comparison/cli.py                                            # CLI argparse + exit codes template(design.md §5 写明本 change 5 tool 沿用)
cat probes/README.md                                                           # probe 约定 §5(7 ASCII 标记 / utf-8 reconfigure / opt-in env guard 模式)
cat probes/_output.py                                                          # probe ASCII 标记 helper 实现 reference(可复用思路,但 tools/ 不依赖 probes)
```

## P3 阶段任务全貌(tasks.md §4)

5 个 stdlib-only Python tools + 1 个空 __init__.py + 1 个自检 task。每个 tool 必须实测 `--json --dry-run` 通过。

### §4.1 `tools/__init__.py`(空文件)

`tools/` 是 sys.path 注册 helper 不需要(直接 `python tools/<name>.py` 调用,不 `import tools.xxx`)。空文件即可,行数 0。

### §4.2 `tools/forgeue_env_detect.py`

**功能**(design.md §5 / §8 + plan v3 §3.D):5 层 env 检测 + plugin 可用性启发式。

**5 层检测优先级**(plan §14.3 推荐):
1. CLI flag(`--review-env <override>`)— 最高
2. env var(如 `FORGEUE_REVIEW_ENV=...`)
3. `.forgeue/review_env.json` setting file(沿决议 D-SettingFileInGit,入 git 团队共享)
4. auto-detect heuristic(检测 `~/.claude/plugins/` 目录 / `codex` CLI / Cursor / Aider 等存在性)
5. unknown(沿决议 D-UnknownNoPrompt:不 prompt,直接走 WARN + 引导)

**输出 JSON**(`--json` 时不打 ASCII 标记):
```json
{
  "detected_env": "claude-code",
  "auto_codex_review": true,
  "codex_plugin_available": true,
  "superpowers_plugin_available": true,
  "_unavailable_reason": null
}
```

**CLI**:
- `--json` — JSON 输出
- `--review-env <override>` — 强制覆盖检测(claude-code / codex-cli / cursor / aider / unknown)
- `--explain` — 人类可读的检测过程
- `--dry-run` — 必无副作用

**exit codes**(design.md §5 表):0(成功) / 2(known unsupported env)/ 1(IO 异常等)。

**P4 fence**:`tests/unit/test_forgeue_env_detect.py`(§5.2.1)— 5 检测路径 + override 优先级 + Windows env 大小写 + plugin 启发式 + dry-run no-write + ASCII only。

### §4.3 `tools/forgeue_change_state.py`(回写检测主力)

**功能**:
- state 推断 S0-S9
- `--writeback-check` 检测 4 类 named DRIFT(对应 design.md §3 taxonomy + tasks.md §4.3):
  - `evidence_introduces_decision_not_in_contract`(evidence 含未记录决策)→ exit 5
  - `evidence_references_missing_anchor`(plan / micro_tasks 引用 `tasks.md#X.Y` 不存在)→ exit 5
  - `evidence_contradicts_contract`(implementation log 与 design.md 接口不一致)→ exit 5
  - `evidence_exposes_contract_gap`(debug log 揭示 design.md 异常段缺失)→ exit 5
- 附加 frontmatter 校验(独立于 4 类 DRIFT,作 finish_gate 输入):
  - `aligned_with_contract: false` 但 `drift_decision: null` → 报告(由 `forgeue_finish_gate.py` exit 2 阻断)
  - `writeback_commit` 标了但 `git rev-parse <sha>` 失败 / `git show --stat <sha>` 未改对应 artifact → 报告

**CLI**:
- `--change <id>` / `--list-active` / `--validate-state <S0..S9>` / `--writeback-check` / `--json` / `--dry-run`

**exit codes**(design.md §5):0(PASS)/ 2(state mismatch with `--validate-state`)/ 3(矛盾 evidence 检出)/ 4(`--validate-state` 期望失败)/ 5(任一 named DRIFT 检出)/ 1(IO 等)。

**P4 fence**:`test_forgeue_change_state.py`(§5.2.2)+ `test_forgeue_writeback_detection.py`(§5.3.1,4 类 named DRIFT 全覆盖)。

### §4.4 `tools/forgeue_verify.py`

**功能**(design.md §5 + `docs/ai_workflow/validation_matrix.md`):Level 0 / 1 / 2 验证编排。

- Level 0(默认必跑,**无 paid**):`python -m pytest -q` + offline bundle 冒烟(`python -m framework.run --task examples/mock_linear.json`)
- Level 1(LLM key 必需,opt-in `FORGEUE_VERIFY_LIVE_LLM={1,true,yes,on}` 严格 case-insensitive):真实 LLM provider + visual review + provider routing live
- Level 2(ComfyUI / UE / 贵族 API,opt-in `FORGEUE_VERIFY_LIVE_MESH=...` / `FORGEUE_VERIFY_LIVE_UE=...`):mesh.generation / UE export / a1_run commandlet
- env guard 严格 truthy 集合 `{1,true,yes,on}`(case-insensitive);不接受 `false` / `0` / `no` / `off` 误开
- 报告输出 `verification/verify_report.md`(12-key frontmatter / `evidence_type: verify_report` / SKIP 必有 reason)

**CLI**:`--change <id>` / `--level 0|1|2` / `--report-out <path>` / `--json` / `--dry-run`。

**exit codes**:0(含 SKIP) / 2([FAIL]) / 3 / 1。

**P4 fence**:`test_forgeue_verify.py`(§5.2.3)+ `test_forgeue_workflow_no_paid_default.py`(§5.6.1 横切 — 扫 5 tool 源码 grep `--level 1` `--level 2` `paid` `live` 默认不开)。

### §4.5 `tools/forgeue_doc_sync_check.py`

**功能**(design.md §7):静态扫 10 份长期文档,标签 `[REQUIRED]` / `[OPTIONAL]` / `[SKIP]` / `[DRIFT]`。

10 份必检文档(沿 README §4.1):
- `openspec/specs/*` / `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`

**启发式规则**(design.md §7):
- commit-touching change → CHANGELOG REQUIRED
- `src/framework/core/` 改动 → LLD REQUIRED
- 架构边界改动 → HLD REQUIRED
- 验收新通过 → acceptance_report REQUIRED
- `docs/ai_workflow/` 改动 → CLAUDE+AGENTS REQUIRED
- 无 spec delta → `openspec/specs/*` SKIP
- 无 FR/NFR 变更 → SRS SKIP
- 无 test 策略变更 → test_spec SKIP

**CLI**:`--change <id>` / `--json` / `--dry-run`。

**exit codes**:0(无 DRIFT) / 2(任一 DRIFT) / 1(IO)。

**P4 fence**:`test_forgeue_doc_sync_check.py`(§5.2.4)— commit-touching → CHANGELOG REQUIRED + runtime change → LLD REQUIRED + ai_workflow change → CLAUDE+AGENTS REQUIRED + [DRIFT] → exit 2 + dry-run no-write + JSON 含 10 文件。

### §4.6 `tools/forgeue_finish_gate.py`(中心化最后防线)

**功能**(design.md §5 + spec.md ADDED Requirement Scenarios):
- evidence 完整性(必含 `verification/verify_report.md` / `verification/doc_sync_report.md` / `review/superpowers_review.md` finalize / claude-code+plugin 时含 `review/codex_adversarial_review.md` 等)
- frontmatter 全检:每份 evidence 12-key 完整 + `aligned_with_contract: true`(或带 drift 标记 + reason ≥ 50 字 + Reasoning Notes anchor)
- cross-check disputed_open:`design_cross_check.md` / `plan_cross_check.md` 必 `disputed_open: 0`
- writeback_commit 二次校验:每个 `written-back-to-*` 必有 `git rev-parse <sha>` PASS + `git show --stat <sha>` 触对应 artifact(spec.md ADDED Requirement Scenario 2 protocol 强约束)
- tasks unchecked:`tasks.md` 无 `[ ]` 残留(或带 SKIP reason)
- `openspec validate <id> --strict` PASS
- `~/.claude/settings.json` review-gate hook:含 `--enable-review-gate` → WARN(沿决议 14.17 禁用)

**CLI**:`--change <id>` / `--json` / `--dry-run` / `--no-validate`(测试用,跳 strict validate)。

**exit codes**:0(PASS) / 2(任一 blocker) / 3(目录不存) / 1(IO)。

**P4 fence**:`test_forgeue_finish_gate.py`(§5.2.5)— S8 完整 → exit 0;缺 verify → exit 2;cross-check disputed_open > 0 → exit 2;writeback_commit 假 → exit 2;non-claude-code env 缺 codex → exit 0(降级);`--no-validate` 不 spawn openspec;dry-run no-write。

### §4.7 5 tool 手 `--json --dry-run` 自检通过

每个 tool 实测 `python tools/<name>.py --json --dry-run`(取一个 minimal active change 跑通),输出合规 JSON,无副作用,exit 0。

## 横切要求(design.md §5 footer + tasks.md §4 末段)

所有 5 tool 共同遵守:

- **stdlib only**:不引 Python runtime dep(decimal / json / pathlib / subprocess / argparse / 等 stdlib 即可)
- **stdout utf-8**:`sys.stdout.reconfigure(encoding="utf-8")` + ASCII fallback(沿 probes/README.md §5)
- **7 种 ASCII 标记**:`[OK]` / `[FAIL]` / `[SKIP]` / `[WARN]` / `[DRIFT]` / `[REQUIRED]` / `[OPTIONAL]`,**无 emoji**(P1 round-2 L3.1 教训 + ForgeUE memory `feedback_ascii_only_in_adhoc_scripts`)
- **`--json` 时不打 ASCII 标记**(纯 JSON 输出,便于 agent 解析)
- **`--dry-run` 必无副作用**(无文件写入 / 无 subprocess spawn 关键 / P4 fence 守门)
- **不进 `pyproject.toml` 的 `[project.scripts]`**(用户 `python tools/<name>.py` 调用,体验略繁琐但无 dep 引入,沿决议 D-NoConsoleScripts)
- **不硬编码 pytest 总数**(以 `python -m pytest -q` 实测为准,P4 fence `test_forgeue_workflow_no_hardcoded_test_count.py` 守门)

## 决议(P0 / P1 不可变,P3 必须遵守)

```yaml
# Pre-P0 锁定 4 项(用户裁决)
D-CommandsCount: 8(已实施 P2,P3 不动)
D-DocsCount: 1 份合并(已实施 P1,P3 不动)
D-FrontmatterSchema: 12 key(11 audit + 1 change_id wrapper;P3 finish_gate / change_state 解析此 schema)
D-FutureCapabilitySpec: 当前不抽

# P0 设计决议
14.2: 命名 = /forgeue:change-*(已实施 P2)
14.5: self-host(本 change 用本 change 工作流;P1 + P2 已自证)
14.16: codex-plugin-cc 可选(P3 工具不强依赖 plugin;非 claude-code env 时 codex review evidence 降级 OPTIONAL,不阻断 archive)
14.17: review-gate 禁用(/codex:setup --enable-review-gate 不启;forgeue_finish_gate.py 必须检 ~/.claude/settings.json,含 → WARN)
14.18: design + plan 都强制 cross-check(P3 不直接产 cross-check,但 forgeue_change_state.py 解析这两份 evidence 的 disputed_open)
D-NoConsoleScripts: 5 tool 不进 console_scripts
D-EnvDetectLayers: 5 层优先级(forgeue_env_detect.py 实施)
D-AdversarialBinding: adversarial REQUIRED 与 plugin available + auto_codex_review 绑(env 解耦)
D-DisputedReason20: accepted-claude reason ≥ 20 字
D-DocSync10Files: doc-sync 10 文档清单
```

## 禁令(P3 必须遵守)

来自 CLAUDE.md / AGENTS.md / openspec/config.yaml / design.md:

- **禁修区**:
  - `.claude/commands/opsx/*` / `.claude/skills/openspec-*/` / `.codex/skills/openspec-*/`(OpenSpec 默认产物)
  - `openspec/specs/*` 主 spec(本 change 仅延伸 examples-and-acceptance,通过 archive sync-specs 自动合)
  - `openspec/config.yaml`
  - **ForgeUE runtime 核心**:`src/framework/{core,runtime,providers,review_engine,ue_bridge,workflows,comparison,pricing_probe,artifact_store}/**`(P3 工具是工具层,**不**触 framework runtime)
  - **五件套**:`docs/{requirements/SRS,design/HLD,design/LLD,testing/test_spec,acceptance/acceptance_report}.md`
  - `pyproject.toml` 的 `[project.dependencies]` / `[project.optional-dependencies]`(P3 stdlib only,绝不引新 dep)
  - `examples/*.json` / `probes/**` / `ue_scripts/**` / `config/models.yaml`
  - 已 archived changes / `docs/archive/claude_unified_architecture_plan_v1.md`(ADR-005)

- **工作流内禁用**:
  - `/codex:rescue` 在 ForgeUE workflow 内(违 review-only;Pre-P0 是本 change 一次性附录例外,P3 不豁免)
  - `/codex:setup --enable-review-gate`(plugin 自警告 long loop;markdown lint fence 守门)

- **行为约束**:
  - 不引入 paid provider / live UE / live ComfyUI 默认调用(env guard 严格 `{1,true,yes,on}`,大小写不敏感)
  - 不让 evidence 成为新规范源(P3 工具的 help text / docstring **不得**引入 contract 未写过的"规则";如实现暴露 contract 漏洞 → 回写到 design.md / proposal.md / tasks.md / spec.md)
  - 不重复造轮子(stdlib 已有的功能不引第三方 lib,argparse / json / pathlib / subprocess / yaml(stdlib 没?用 manual parse))
  - **不伪造外部数据**(沿 ForgeUE memory `feedback_no_fabricate_external_data`):工具的默认值 / endpoint / version 等必有 sourced_on 注释或 null + TODO,不允许"看似合理"的伪造数字
  - **不静默重试贵族 API**(沿 ADR-007 + ForgeUE memory `feedback_no_silent_retry_on_billable_api`):若 forgeue_verify Level 2 涉及 mesh.generation 等,失败时 surface job_id,**不**自动 `--resume`

## ForgeUE memory 精神(P3 必遵守)

来自 `~/.claude-max/projects/D--ClaudeProject-ForgeUE-claude/memory/`:

- **`feedback_verify_external_reviews`**:Codex / 外部 review 的 claim 必须独立对照代码验证(P3 起草工具时,若 codex review 提"该函数应该如此",先 file:line 实测确认)
- **`feedback_decisive_approval`**:给论证 + 选项 + tradeoffs up-front,等用户绿灯后 execute fully,不中途微确认
- **`feedback_no_silent_retry_on_billable_api`**:贵族 API(mesh.generation 等)失败不 silent retry,surface job_id(forgeue_verify Level 2 体现)
- **`feedback_no_fabricate_external_data`**:pricing/endpoint/version 字段必须有 sourced_on 或 null + TODO,不允许伪造("看似合理"的数字)
- **`feedback_ascii_only_in_adhoc_scripts`**:Windows GBK stdout 不允许 emoji,只用 7 种 ASCII 标记(P3 工具 stdout + report markdown 全应用此)
- **`feedback_contract_vs_quality_separation`**:contract 测试用 fixture + FakeAdapter,real-provider 走 opt-in probe(P3 forgeue_verify 区分清:Level 0 用 fixture / Level 1+2 opt-in)
- **`env_windows`**:`/tmp/...` 是 C: 系统目录,产物落 `./artifacts/<YYYY-MM-DD>/<run_id>/` 或 `./demo_artifacts/<YYYY-MM-DD>/`(P3 工具默认报告路径如有,落 `verification/<file>.md`,不落 /tmp)
- **`user_language_chinese`**:中文沟通,技术名词保留英文

## P3 启动指引

读完上述上下文后,**直接开始 §4.1**:

1. 创建 `tools/__init__.py`(空文件)
2. 起草 `tools/forgeue_env_detect.py`(最简单,5 层检测 + JSON 输出 + ASCII fallback;~150 行)
3. 起草 `tools/forgeue_change_state.py`(回写检测主力,4 类 named DRIFT;~250 行)
4. 起草 `tools/forgeue_verify.py`(Level 0/1/2 编排 + env guard;~180 行)
5. 起草 `tools/forgeue_doc_sync_check.py`(10 文档静态扫描;~200 行)
6. 起草 `tools/forgeue_finish_gate.py`(中心化最后防线;~250 行)
7. **5 tool 手 `--json --dry-run` 自检**(§4.7,实测 5 次)
8. tasks.md §4.1-§4.7 全 [x]
9. P3 完成 = 7 个 task 全 done + strict validate PASS + 用户认可

**起草顺序建议**(最小依赖链):
- 先 `forgeue_env_detect.py`(无依赖,基础块)
- 再 `forgeue_change_state.py`(可独立,与 env_detect 解耦)
- 再 `forgeue_doc_sync_check.py`(独立,只扫文件)
- 再 `forgeue_verify.py`(独立,subprocess pytest)
- 最后 `forgeue_finish_gate.py`(依赖前 4 个的输出格式 contract)

**共享 helper 抽离**(可选,看体量):
- ASCII 标记 + utf-8 reconfigure boilerplate 可考虑抽到 `tools/_output.py`(类似 `probes/_output.py`)
- 但**不强制**;每个 tool 自带 boilerplate 也行(P4 fence `test_forgeue_workflow_ascii_markers.py` §5.6.2 扫 5 tool 源码确认 stdout 仅 7 种 ASCII)

## 下一阶段提示

P3 完成后进 P4(`tasks.md §5`,fixture + 单测 + fence,~30 个 test file);P4 完成后 P5 验证 + P6 doc-sync + P7 review + P8 finish gate + P9 archive。

任何阶段发现 contract 漏洞 → 回写到 proposal/design/tasks/spec.md(plan §4.2 + design.md §3 协议),不在 evidence 里自己合理化(P1 round-1 H1.1 教训)。

任何阶段发现 review blocker → 沿 `feedback_verify_external_reviews` 独立验证 file:line 真实性后才接受(P1 + P2 9 项 finding 全 verified true 的范式)。

## 已完成的 review 决议(本 change 已修过的事,P3 不要重做)

P0 codex S2→S3 design review 9 项发现已全部解决(详 `review/design_cross_check.md`):
- B1-B6(blocker):proposal.md Capabilities / tasks.md 7.5.1 REQUIRED / spec.md Validation+Non-Goals / 4 类 named DRIFT taxonomy / Reasoning Notes heading level / < 50 字阻断非 WARN
- N1-N3(non-blocker):§10 桥接段 / micro_tasks 共用 anchor / 12 key 措辞统一

P1 round-1 codex review 3 项发现已全部解决(详 `review/p1_docs_review_codex.md`):
- H1.1(blocker):forgeue_integrated_ai_workflow.md §D.5/§D.6 prescriptive over-reach → 写回 design.md §3 加 Cross-check Protocol 子段
- H1.2(non-blocker):§A.5 内联 skill 清单 → 改引 §B.3
- M6.1(nit):§A.6 8 commands 名 trade-off accepted

P1 round-2 codex review 6 项发现已全部解决(详 `review/p1_docs_review_round2_codex.md`):
- H2.1(blocker):"唯一来源" overclaim → 改 §B.3 详表 + design.md §8 同款边界并存
- H4.1(blocker):README.md §8 change-apply 行漏 "越界检测" → 加回
- H5.1(blocker):README.md §8 change-status 行漏 forgeue_change_state 调用 → 加回
- M1.1(non-blocker):round-1 evidence frontmatter 矛盾 → 改 pending 后 commit + 回填
- M1.2(non-blocker):硬编码行号失效 → 改 semantic §X 引用
- L3.1(nit):emoji ✅/⚠️ → [OK]/[WARN]

P2 self-audit + 2 fix iteration 已全部解决(详 P2 milestone commit `e8067f3` + 自审计 grep 实测):
- P4 fence 5.4.1-a:4 commands 漏 /codex:adversarial-review|/codex:review 字面 → 加 Guardrails 末尾 "本命令不直接触发" 句
- SA-4 PARTIAL:change-doc-sync References 漏直接 backbone 引用 → 加 integrated-change-workflow 直接引

P3 工作不要再触动这些已修部分。

## 当前 git 状态

```
e8067f3 chore: P2 commands + skills landed for fuse-openspec-superpowers-workflow
7d0c730 docs: backfill writeback_commit in P1 round-1 evidence
a705754 chore: P1 docs landed for fuse-openspec-superpowers-workflow
73f18e6 chore: bootstrap fuse-openspec-superpowers-workflow (P0 + Pre-P0 cross-check + S2 codex review)
```

Branch:`chore/openspec-superpowers`(已 up to date with origin)。

工作树干净,仅 `.claude/.codex` 21 项 OpenSpec 默认 untracked(P0 之前就在,本 change 不动)。

P3 启动后产物落:
- `tools/__init__.py` + `tools/forgeue_*.py`(5 个新 Python 文件)
- `openspec/changes/fuse-openspec-superpowers-workflow/tasks.md`(§4.1-§4.7 全 [x])
- 视情况:`openspec/changes/fuse-openspec-superpowers-workflow/review/p3_tools_review_codex.md`(若 P3 走 codex review;P2 卡死 35min 后推迟到 P4 之后整体 adversarial)
- 视情况:`tools/_output.py`(共享 helper,可选)
