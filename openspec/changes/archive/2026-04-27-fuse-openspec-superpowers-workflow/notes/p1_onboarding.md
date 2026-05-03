---
purpose: P1 阶段 onboarding,新会话用此文件快速对齐到 P1 起点状态
created_at: 2026-04-26
target_session: new Claude Code session(本 change P0 已完成,准备进 P1)
note: |
  本文件不是 evidence,是 onboarding helper。新会话 Claude 读完此文件即知道 P1 任务全貌 + 必读 contract + 决议 + 禁令。
  archive 时随 change 走但仅作历史 reference,不影响 finish gate。
---

# P1 Onboarding: fuse-openspec-superpowers-workflow

## 你现在的状态(新会话 Claude 必读)

你被开启在 ForgeUE 项目(D:\ClaudeProject\ForgeUE_claude)的新会话里,**继续推进 active OpenSpec change `fuse-openspec-superpowers-workflow` 的 P1 阶段**。

### 项目环境

- Windows 11 + Git-Bash + D: 盘
- Python 3.12+
- `codex` CLI 已装(`codex-cli 0.125.0`)+ 已 ChatGPT 登录
- Superpowers plugin 已装(`~/.claude/plugins/` 全局,12 skills + 7 agents + 4 hooks)
- codex-plugin-cc **未装**(可选,P3+ 才需要;Pre-P0/P0 用 `codex exec` 路径 B 已覆盖)
- pytest baseline 848 passed(2026-04-26 实测)

### Pre-P0 + P0 已完成

- ✅ Pre-P0:plan-level cross-check(`notes/pre_p0/forgeue-fusion-{claude,codex,codex_prompt,cross_check}.md`)— 用户裁决 4 项 disputed:
  - C.1 D-CommandsCount = **8 个 ForgeUE commands**(accepted-claude;不包 OpenSpec contract create/archive)
  - C.2 D-DocsCount = **1 份合并 docs**(accepted-codex;`docs/ai_workflow/forgeue_integrated_ai_workflow.md` 内部分 4 个 section)
  - C.3 D-FutureCapabilitySpec = **当前不抽 ai-workflow**(accepted-claude;design.md §11.3 记未来评估触发条件)
  - C.4 D-FrontmatterSchema = **12 key(11 audit + 1 change_id wrapper)**(accepted-codex)
- ✅ P0:`proposal.md` / `design.md` / `tasks.md` / `specs/examples-and-acceptance/spec.md` 全部落盘 + `openspec validate --strict` PASS
- ✅ P0 codex S2→S3 design review 已跑(`review/codex_design_review.md`,6 blocker + 3 non-blocker)+ Claude 写 cross_check.md(`review/design_cross_check.md`,disputed_open=0,9 项 Resolution 落地)

### 14 个 task done / 77 pending

下一个 task = **P1 阶段第一项 = §2.1**(见 tasks.md)

## 必读文件清单(按顺序读)

读完前 4 项再开始 P1 工作;后 4 项作 reference 按需读。

```bash
# P1 必读(contract + 锁定决议)
cat openspec/changes/fuse-openspec-superpowers-workflow/proposal.md
cat openspec/changes/fuse-openspec-superpowers-workflow/design.md           # 重点:§1-§11 + §11 Reasoning Notes
cat openspec/changes/fuse-openspec-superpowers-workflow/tasks.md            # §2 P1 工作明细
cat openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md

# P0 review 决议(理解为什么 contract 长这样)
cat openspec/changes/fuse-openspec-superpowers-workflow/review/design_cross_check.md   # 9 项 Resolution
cat openspec/changes/fuse-openspec-superpowers-workflow/notes/pre_p0/forgeue-fusion-cross_check.md  # 4 项决议

# P1 改动目标 + reference
cat docs/ai_workflow/README.md                                              # P1 §2.2/§2.3 改 §5 + §8 表格
cat docs/ai_workflow/validation_matrix.md                                   # P1 §2.4 不动,作 reference
```

## P1 阶段任务全貌(tasks.md §2)

### §2.1 新建 `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(中心化契约主文档,**1 份合并**)

**结构**:内部分 4 个 section,合并自 plan v3 §1-§17 关键内容,~600-800 行可控。

- **Section A:Fusion Contract**(中心化架构图 + 三层服务关系 + ForgeUE 守护工具链定位)
  - 核心是 design.md §1 + §2 中心化论述
  - OpenSpec contract 是项目唯一规范锚点
  - Superpowers / codex / ForgeUE tools / docs sync 是服务者(不是并立 layer)
  - "evidence 不能成为新规范源" 协议表达

- **Section B:Agent Phase Gate Policy**(S0-S9 各 stage 退出条件 + Superpowers 边界 + codex hook 触发)
  - 核心是 design.md §3 状态机表
  - 横切硬约束(没 active change abort / proposal-tasks 不齐不能 S3 / 测试未跑不能 S6 / review blocker 未清不能 S7 / doc sync DRIFT 不能 S8 / **evidence 含 aligned_with_contract: false 且未标 drift 不能 S9** 中心化最后防线)
  - codex stage hook 摘要(S2 design / S3 plan / S5 verification / S6 adversarial)

- **Section C:Documentation Sync Gate**
  - 沿 docs/ai_workflow/README.md §4 主规则不动 + §4.3 提示词不动 + §4.4 12 项 checklist 模板不动
  - 新增 `tools/forgeue_doc_sync_check.py` 静态预扫描([REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT] 标签)
  - 启发式规则:commit-touching → CHANGELOG REQUIRED;runtime/core 改动 → LLD REQUIRED;docs/ai_workflow/ 改动 → CLAUDE+AGENTS REQUIRED

- **Section D:State Machine + Writeback Protocol**
  - 核心是 design.md §3 + §4(状态机 + frontmatter 协议)
  - 12-key frontmatter(1 wrapper change_id + 11 audit fields)
  - 4 类 named DRIFT(`evidence_introduces_decision_not_in_contract` / `evidence_references_missing_anchor` / `evidence_contradicts_contract` / `evidence_exposes_contract_gap`)
  - writeback 协议三态(pending / written-back-to-<artifact> / disputed-permanent-drift)
  - cross-check A/B/C/D 段模板(decision_id 一对一,disputed_open == 0)

### §2.2 修 `docs/ai_workflow/README.md` §5 表格

- Superpowers 行从 "暂不接入主线" 升级为 "作为 OpenSpec evidence 生成器,跨 7 env 装,产物绑 active change 子目录,实施暴露的 contract 漏洞必须回写"
- Codex CLI 行扩展为 "Claude Code 内通过 codex-plugin-cc 自动 stage cross-review,blocker 涉及 contract 必须回写;Claude Code 之外 env 由用户工具自决"

### §2.3 修 `docs/ai_workflow/README.md` §8 表格

- 新增 forgeue: 列(`/forgeue:change-*` 8 个命令的等价说明,与 OpenSpec 默认命令并列展示)

### §2.4 **不动** `docs/ai_workflow/validation_matrix.md`

- `tools/forgeue_verify.py` 是其机器版,文档保留为人类 reference

## 决议(P0 不可变,P1 必须遵守)

```yaml
14.2: 命名 = /forgeue:change-*(与 /opsx:* 平行)
14.5: self-host(本 change 用本 change 定义工作流跑通)
14.16: codex-plugin-cc 可选(不可用降级 OPTIONAL,不阻断 archive)
14.17: review-gate 禁用(/codex:setup --enable-review-gate 不启;long loop 风险)
14.18: design + plan 都强制 cross-check(2 份 cross_check.md finish gate REQUIRED)

D-CommandsCount: 8 个 ForgeUE commands
D-DocsCount: 1 份合并 docs(本 P1 §2.1 体现)
D-FrontmatterSchema: 12 key(11 audit + 1 change_id wrapper)
D-FutureCapabilitySpec: 当前不抽 ai-workflow(design.md §11.3 + Reasoning Notes)
```

## 禁令(必须遵守)

来自 CLAUDE.md / AGENTS.md / openspec/config.yaml / design.md:

- **禁修区**:
  - `.claude/commands/opsx/*` / `.claude/skills/openspec-*/` / `.codex/skills/openspec-*/`(OpenSpec 默认产物)
  - `openspec/specs/*` 主 spec(本 change 仅延伸 examples-and-acceptance,通过 sync-specs 在 archive 时自动合)
  - `openspec/config.yaml`
  - ForgeUE runtime 核心:`src/framework/{core,runtime,providers,review_engine,ue_bridge,workflows,comparison,pricing_probe,artifact_store}/**`
  - 五件套:`docs/{requirements/SRS,design/HLD,design/LLD,testing/test_spec,acceptance/acceptance_report}.md`
  - `pyproject.toml` dependencies(不引 Python runtime dep)
  - `examples/*.json` / `probes/**` / `ue_scripts/**` / `config/models.yaml`
  - 已 archived changes / `docs/archive/claude_unified_architecture_plan_v1.md`(ADR-005)

- **工作流内禁用**:
  - `/codex:rescue` 在 ForgeUE workflow 内(违反 review-only;Pre-P0 是本 change 一次性例外,未来 change 不适用)
  - `/codex:setup --enable-review-gate`(plugin 自警告 long loop;markdown lint fence 扫禁用字面)

- **行为约束**:
  - 不引入 paid provider / UE / ComfyUI 默认调用(env guard 严格 `{1,true,yes,on}`)
  - 不让 evidence 成为新规范源(evidence 暴露的 contract 漏洞必须**回写到 OpenSpec contract**)
  - 不重复造轮子(Superpowers 已有 skill 不再做同名 ForgeUE skill)

## ForgeUE memory 精神(必遵守)

来自 `~/.claude-max/projects/D--ClaudeProject-ForgeUE-claude/memory/`:

- **`feedback_verify_external_reviews`**:Codex / 外部 review 的 claim 必须独立对照代码验证,不把 claim 当结论
- **`feedback_decisive_approval`**:给论证 + 选项 + tradeoffs up-front,等用户绿灯后 execute fully,不中途微确认
- **`feedback_no_silent_retry_on_billable_api`**:贵族 API(如 mesh.generation)失败不 silent retry,surface job_id
- **`feedback_no_fabricate_external_data`**:pricing/endpoint/version 字段必须有 sourced_on 或 null + TODO,不允许伪造
- **`feedback_ascii_only_in_adhoc_scripts`**:Windows GBK stdout 不允许 emoji,只用 7 种 ASCII 标记 `[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]`
- **`feedback_contract_vs_quality_separation`**:contract 测试用 fixture + FakeAdapter,real-provider 走 opt-in probe
- **`env_windows`**:`/tmp/...` 是 C: 系统目录,产物落 `./artifacts/<YYYY-MM-DD>/<run_id>/` 或 `./demo_artifacts/<YYYY-MM-DD>/`
- **`user_language_chinese`**:中文沟通,技术名词保留英文

## P1 启动指引

读完上述上下文后,**直接开始 §2.1**:

1. 读 `docs/ai_workflow/README.md` 了解现状的语调 / 措辞 / 章节风格(新文档要与之协调)
2. 起草 `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(4 个 section)
3. 用户确认后再做 §2.2 / §2.3(README.md 表格修改 — 走 Documentation Sync Gate 精神)
4. §2.4 不动 validation_matrix.md
5. P1 完成 = 4 个 task 全 done + 用户认可

## 下一阶段提示

P1 完成后进 P2(`tasks.md §3`,8 commands + 2 skills);P2 完成后 P3 实装 5 个 stdlib-only tools。

任何阶段发现 contract 漏洞 → 回写到 proposal/design/tasks/spec.md(plan §4.2 协议),不在 evidence 里自己合理化。

任何阶段发现 review blocker → 沿 `feedback_verify_external_reviews` 独立验证 file:line 真实性后才接受。

## 已完成的 review 决议(本 change 已修过的事,不要重做)

P0 codex S2→S3 design review 9 项发现已全部解决(详 `review/design_cross_check.md`):

| ID | 修复点 | 已落地 |
|---|---|---|
| B1 | proposal.md Capabilities 段 | Modified=examples-and-acceptance + 解释 capability 行为延伸 |
| B2 | tasks.md 7.5.1 | REQUIRED for openspec/specs/examples-and-acceptance |
| B3 | spec.md 末尾 | 加 Validation + Non-Goals 段 |
| B4 | tasks.md 4.3 / 5.3.1 | 4 类 named DRIFT taxonomy + 附加 frontmatter 校验 |
| B5 | design.md heading | `### §11 Reasoning Notes` → `## Reasoning Notes` + §11.1-§11.4 改 level 3 |
| B6 | tasks.md 5.3.1 reason | < 50 字 → finish_gate exit 2 阻断(非 WARN) |
| N1 | design.md §10 末尾 | 桥接段:本 delta 临时归 examples-and-acceptance,不等于建立 ai-workflow capability |
| N2 | (保留 accepted-claude) | mapping 表已覆盖 micro_tasks |
| N3 | 全文 | "11 字段" → "12 key(11 audit + 1 change_id wrapper)" |

P1 工作不要再触动这些已修部分。
