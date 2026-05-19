---
source: codex-rescue
task_id: forgeue-openspec-superpowers-workflow
model: gpt-5
effort: high
created_at: 2026-04-26T00:00:00+08:00
version: codex-v1
---

# ForgeUE OpenSpec × Superpowers Fusion Analysis (Codex independent proposal)

## 1. Repository Current State

当前主流程已经清楚：ForgeUE 自 2026-04-24 起采用 OpenSpec 作为 AI 主工作流，非平凡需求按 `proposal → design → tasks → implementation → validation → review → Documentation Sync Gate → archive` 走完整 change lifecycle，[README.md:360](D:/ClaudeProject/ForgeUE_claude/README.md:360)、[docs/ai_workflow/README.md:31](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:31)。`openspec/specs/` 是 8 个 capability 的行为契约层，`openspec/changes/` 是未来变更入口，[README.md:366](D:/ClaudeProject/ForgeUE_claude/README.md:366)、[README.md:367](D:/ClaudeProject/ForgeUE_claude/README.md:367)。`docs/` 五件套仍是长期权威，OpenSpec 是契约抽取而非替代，[docs/ai_workflow/README.md:20](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:20)、[docs/ai_workflow/README.md:22](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:22)、[README.md:369](D:/ClaudeProject/ForgeUE_claude/README.md:369)。

当前 Claude commands 是 `.claude/commands/opsx/` 下的 11 个 OpenSpec 默认命令。`/opsx:propose` 创建 change 并生成 proposal/design/tasks，[.claude/commands/opsx/propose.md:3](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/propose.md:3)、[.claude/commands/opsx/propose.md:34](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/propose.md:34)；`/opsx:apply` 实现 tasks 并在发现 design issue 时建议更新 artifact，[.claude/commands/opsx/apply.md:67](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/apply.md:67)、[.claude/commands/opsx/apply.md:78](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/apply.md:78)；`/opsx:verify` 检查 tasks/spec/design 一致性，[.claude/commands/opsx/verify.md:3](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/verify.md:3)、[.claude/commands/opsx/verify.md:94](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/verify.md:94)；`/opsx:archive` 会检查 artifact、task、delta spec sync 并移动目录，[.claude/commands/opsx/archive.md:25](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/archive.md:25)、[.claude/commands/opsx/archive.md:78](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/archive.md:78)。

当前 Claude skills 与 Codex skills 都是 OpenSpec 默认集，各 11 个，语义镜像。比如 `openspec-apply-change` 负责实现 active change tasks，[.claude/skills/openspec-apply-change/SKILL.md:2](D:/ClaudeProject/ForgeUE_claude/.claude/skills/openspec-apply-change/SKILL.md:2)、[.codex/skills/openspec-apply-change/SKILL.md:2](D:/ClaudeProject/ForgeUE_claude/.codex/skills/openspec-apply-change/SKILL.md:2)；`openspec-verify-change` 负责归档前一致性验证，[.claude/skills/openspec-verify-change/SKILL.md:3](D:/ClaudeProject/ForgeUE_claude/.claude/skills/openspec-verify-change/SKILL.md:3)、[.codex/skills/openspec-verify-change/SKILL.md:3](D:/ClaudeProject/ForgeUE_claude/.codex/skills/openspec-verify-change/SKILL.md:3)。这些默认产物不得修改，[docs/ai_workflow/README.md:265](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:265)、[openspec/config.yaml:95](D:/ClaudeProject/ForgeUE_claude/openspec/config.yaml:95)。

当前 validation 入口分三级：Level 0 离线必跑，Level 1 需要 LLM key，Level 2 需要 ComfyUI/UE/真实外部服务，[docs/ai_workflow/validation_matrix.md:3](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/validation_matrix.md:3)。Level 0 是 `python -m pytest -q` 等安全命令，[docs/ai_workflow/validation_matrix.md:30](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/validation_matrix.md:30)、[docs/ai_workflow/validation_matrix.md:38](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/validation_matrix.md:38)；付费调用默认 opt-in，[docs/ai_workflow/validation_matrix.md:11](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/validation_matrix.md:11)。测试全部离线可跑，真实 LLM 与 ComfyUI 在测试里分别由 FakeAdapter / FakeComfyWorker 替换，[README.md:287](D:/ClaudeProject/ForgeUE_claude/README.md:287)、[README.md:288](D:/ClaudeProject/ForgeUE_claude/README.md:288)。

Documentation Sync Gate 已有明确人工流程：每个非平凡 OpenSpec change 在 archive/merge 前必经，[docs/ai_workflow/README.md:111](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:111)；要检查 10 类文档，[docs/ai_workflow/README.md:117](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:117)、[docs/ai_workflow/README.md:126](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:126)；不更新必须记录原因，drift 必须显式化，[docs/ai_workflow/README.md:131](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:131)、[docs/ai_workflow/README.md:132](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:132)。不足是它目前主要靠粘贴提示词执行，[docs/ai_workflow/README.md:138](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:138)，还没有项目级工具把 evidence、writeback、review blocker、finish gate 物理化。

当前自动化不足主要在四处：`/opsx:apply` 只“suggest updating artifacts”，没有强制回写检测，[.claude/commands/opsx/apply.md:78](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/apply.md:78)；`/opsx:archive` 明确“不因 warnings 阻断 archive”，[.claude/commands/opsx/archive.md:152](D:/ClaudeProject/ForgeUE_claude/.claude/commands/opsx/archive.md:152)；Documentation Sync Gate 没有机器可读报告；当前 Superpowers 在主流程中仅是“暂不接入主线 / 未来评估”，[docs/ai_workflow/README.md:213](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:213)。只读目录检查还显示项目根当前没有 `tools/` 与 `scripts/` 目录。

现有 8 个 capability spec 已覆盖 runtime、artifact、workflow、review、provider、UE、probe、acceptance 的行为面：[openspec/specs/runtime-core/spec.md:1](D:/ClaudeProject/ForgeUE_claude/openspec/specs/runtime-core/spec.md:1)、[openspec/specs/artifact-contract/spec.md:1](D:/ClaudeProject/ForgeUE_claude/openspec/specs/artifact-contract/spec.md:1)、[openspec/specs/workflow-orchestrator/spec.md:1](D:/ClaudeProject/ForgeUE_claude/openspec/specs/workflow-orchestrator/spec.md:1)、[openspec/specs/review-engine/spec.md:1](D:/ClaudeProject/ForgeUE_claude/openspec/specs/review-engine/spec.md:1)、[openspec/specs/provider-routing/spec.md:1](D:/ClaudeProject/ForgeUE_claude/openspec/specs/provider-routing/spec.md:1)、[openspec/specs/ue-export-bridge/spec.md:1](D:/ClaudeProject/ForgeUE_claude/openspec/specs/ue-export-bridge/spec.md:1)、[openspec/specs/probe-and-validation/spec.md:1](D:/ClaudeProject/ForgeUE_claude/openspec/specs/probe-and-validation/spec.md:1)、[openspec/specs/examples-and-acceptance/spec.md:1](D:/ClaudeProject/ForgeUE_claude/openspec/specs/examples-and-acceptance/spec.md:1)。本融合方案不改变这些 runtime capability 行为。

## 2. Fusion Goal

一句话定位：ForgeUE Integrated AI Change Workflow 是以 OpenSpec contract artifact 为唯一规范锚点，用 Superpowers 方法论执行阶段内工作，用 `/forgeue:change-*` 命令、codex-plugin-cc review、ForgeUE guard tools 和 evidence frontmatter 共同守住 writeback、validation、review、doc sync、finish、archive 的中心化 lifecycle。

中心化结构：

```text
                    OpenSpec Contract Artifact
              proposal.md / design.md / tasks.md / specs/
                              ^
                              | writeback required
        ----------------------------------------------------------
        | Superpowers evidence | codex review evidence | tools DRIFT |
        ----------------------------------------------------------
                              |
              ForgeUE guard tools: state / verify / doc-sync / finish
```

核心目标：
- OpenSpec 管 change lifecycle，不被 Superpowers 或 Codex 架空。
- Superpowers 只作为阶段内 methodology：brainstorm、plan、TDD、debug、review preparation、finish summary。
- Claude commands 只暴露 `/forgeue:change-*` 生命周期入口，命名锁定来自 plan 14.2，[forgeue-fusion-codex_prompt.md:826](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:826)。
- Codex review 直接复用 codex-plugin-cc 的 `/codex:*`，不新增 `.codex/skills/forgeue-*`，依据增量需求 C，[forgeue-fusion-codex_prompt.md:731](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:731)。
- ForgeUE tools 负责状态、验证、doc sync、finish gate、writeback check。
- 所有 execution/review/verification evidence 必须落在 active OpenSpec change 下，不能成为第二事实源。

非目标：
- 不把 Superpowers 做成 ForgeUE runtime dependency；原始约束禁止这一点，[forgeue-fusion-codex_prompt.md:57](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:57)。
- 不修改 `src/framework/**` runtime 核心对象模型。
- 不改 `.claude/commands/opsx/*`、`.claude/skills/openspec-*`、`.codex/skills/openspec-*`。
- 不默认触发 paid provider、UE、ComfyUI、Hunyuan 3D。
- 不把 evidence 提升为长期规范权威。

成功标准：
- 没有 active change 时无法进入 implementation。
- `proposal.md` / `design.md` / `tasks.md` 不完整时无法进入 execution。
- S2/S3/S5/S6 的 Codex review hook 按 env 策略执行或明确 OPTIONAL。
- 每份 evidence frontmatter 都声明 `aligned_with_contract`，drift 只能是 `pending`、`written-back-to-*` 或 `disputed-permanent-drift`。
- `forgeue_finish_gate.py` 阻断未验证、未 review、未 doc sync、未处理 drift、review blocker 未清零的 archive。
- Documentation Sync Gate 输出机器可读 `doc_sync_report.md`。
- `python -m pytest -q` 仍是测试数量真源，[docs/ai_workflow/validation_matrix.md:3](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/validation_matrix.md:3)。

## 3. Integrated State Machine

状态机不包含 Pre-P0；Pre-P0 是本 change 的一次性 dogfooding 附录。通用 S0-S9 如下。

| State | 含义与进入/退出 | 命令 | 文件与 evidence | Superpowers 边界 | 失败回退与裁决 |
|---|---|---|---|---|---|
| S0 No Active Change | 无 active change；退出条件是创建 `openspec/changes/<id>/` | 允许 `/forgeue:change-start`、`change-status`；禁止 apply/debug/finish | 无必需 change 文件 | 可做 brainstorming；不可写执行计划替代 proposal | 回退仍为 S0；用户裁决是否创建 change |
| S1 Change Created | change scaffold 已存在；退出条件是 proposal/design/tasks 进入 ready | 允许 `change-plan`、`change-status` | 必需 `proposal.md` 起草；可选 `design.md`、`tasks.md` | 可辅助问题拆解；不可替代 OpenSpec artifact | 缺信息则停在 S1；用户裁决 scope |
| S2 Contract Ready | proposal/design/tasks/delta specs ready；退出条件是 plan cross-check 通过 | 允许 `change-plan`、`change-review` | 必需 proposal/design/tasks；evidence `review/codex_design_review.md`、`review/design_cross_check.md` | 可做 design critique；不可在 execution/ 中引入未回写决策 | `disputed_open > 0` 回 S1/S2；用户裁决 disputed |
| S3 Execution Plan Ready | `execution/execution_plan.md` 与 tasks 对齐；退出条件是 writeback-check 通过 | 允许 `change-apply`、`change-review` | 必需 `execution/execution_plan.md`、`micro_tasks.md`；Codex plan review | 可做 micro-task/TDD 计划；不可把 plan 当长期规范 | DRIFT exit 5 回 S2；用户裁决 permanent drift |
| S4 Implementation In Progress | 正在按 tasks 实现；退出条件是实现完成并落验证材料 | 允许 `change-apply`、`change-debug`、`change-verify` | 必需更新 tasks checkbox；可选 `debug_log.md`、`tdd_log.md` | 可做 TDD/debug；发现 contract gap 必须回写 | 失败回 S3/S4；实现 agent 修复，用户裁决 scope 扩大 |
| S5 Verification Evidence Ready | 测试与验证证据完整；退出条件是 code-level review 完成 | 允许 `change-verify`、`change-review` | 必需 `verification/verify_report.md`；可选 L1/L2 skip reason | 可总结验证，不可跳过测试宣称 done | 测试失败回 S4；实现 agent 修复 |
| S6 Review Evidence Ready | review 完成；退出条件是 blocker 为 0 | 允许 `change-review`、`change-doc-sync` | 必需 `review/superpowers_review.md`、codex review 或 OPTIONAL reason | 可组织 review notes；不可接管 OpenSpec 裁决 | blocker 回 S4/S5；外部 claim 必须独立验证，[docs/ai_workflow/README.md:66](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:66) |
| S7 Documentation Sync Gate Ready | doc sync 报告完成；退出条件是 required doc 更新或 skip reason 完整 | 允许 `change-doc-sync`、`change-finish` | 必需 `verification/doc_sync_report.md` | 可生成同步建议；不可自动改长期 docs 除非命令显式要求 | doc drift 回 S2/S4/S7；用户裁决 drift |
| S8 Finish Gate Passed | finish gate 全绿；退出条件是 OpenSpec archive | 允许 `change-finish`、`/opsx:archive` 或 `openspec archive` | 必需 `verification/finish_gate_report.md` | 可写 finish summary；不可替代 archive | blocker 回对应状态；用户裁决 archive |
| S9 Archived | OpenSpec archive 后只读历史 | 允许查看；禁止继续修改 archived change | 位于 `openspec/changes/archive/YYYY-MM-DD-<id>/` | 不再参与执行 | 新问题开新 change；OpenSpec 拥有 archive 裁决 |

Codex stage review hook：
- S2：document-level design review，强制 cross-check。
- S3：document-level execution plan review，强制 cross-check。
- S5：code-level verification review，单向挑错，不做 cross-check。
- S6：mixed adversarial review，blocker 独立验证，不做文档级双向裁决。

## 4. Artifact Mapping

所有 evidence 使用统一 frontmatter：

```yaml
---
change_id: <change-id>
stage: S3
evidence_type: execution_plan
contract_refs:
  - tasks.md#1.2
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: auto
codex_plugin_available: true
---
```

当 `aligned_with_contract: false` 时：
- `drift_decision: pending` 阻断下一阶段。
- `drift_decision: written-back-to-proposal|written-back-to-design|written-back-to-tasks|written-back-to-spec` 必须有真实 `writeback_commit`。
- `drift_decision: disputed-permanent-drift` 必须有 ≥50 字 `drift_reason`，且 `design.md` 的 `## Reasoning Notes` 有对应 anchor。
- `forgeue_change_state.py --writeback-check` 对四类 DRIFT 返回 exit 5：`evidence_introduces_decision_not_in_contract`、`evidence_references_missing_anchor`、`evidence_contradicts_contract`、`evidence_exposes_contract_gap`。这些类型来自增量需求 D，[forgeue-fusion-codex_prompt.md:801](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:801)。

| Superpowers / review 产物 | 允许 | 必须落盘 | 路径 | 回写规则 | archive 后 |
|---|---:|---:|---|---|---|
| brainstorming notes | 是 | 条件必须 | `execution/brainstorming_notes.md` | 发现 scope 变化回写 proposal | 随 change archive 保留 |
| implementation plan | 是 | 是 | `execution/execution_plan.md` | 任何新决策回写 design/tasks | 只作 evidence |
| micro-tasks | 是 | 是 | `execution/micro_tasks.md` | task anchor 不存在则 DRIFT | 只作 evidence |
| TDD notes | 是 | 是 | `execution/tdd_log.md` | 测试策略变化回写 tasks | 只作 evidence |
| debug log | 是 | 条件必须 | `execution/debug_log.md` | 暴露异常策略缺口回写 design | 只作 evidence |
| code review notes | 是 | 是 | `review/superpowers_review.md` | blocker 必须回写或修复 | 只作 evidence |
| adversarial review notes | 是 | 是/OPTIONAL | `review/codex_<scope>_review.md` | doc 级走 cross-check；code 级独立验证 | 只作 evidence |
| verification evidence | 是 | 是 | `verification/verify_report.md` | skip reason 必须可审计 | 只作 evidence |
| doc sync report | 是 | 是 | `verification/doc_sync_report.md` | required docs 未处理阻断 finish | 只作 evidence |
| finish summary | 是 | 是 | `verification/finish_gate_report.md` | 未处理 drift/review blocker 阻断 archive | 只作 evidence |

避免第二事实源的硬规则：`execution/`、`review/`、`verification/` 下的文件只能解释“执行发生了什么”，不能声明新的需求、接口、约束；一旦出现新决策，必须回写 OpenSpec contract artifact。这个原则来自增量需求 D 的中心化要求，[forgeue-fusion-codex_prompt.md:798](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:798)、[forgeue-fusion-codex_prompt.md:799](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:799)。

## 5. Command Design

命令统一放在 `.claude/commands/forgeue/`，不覆盖 `/opsx:*`。`/forgeue:change-*` 是 facade：对外体现 ForgeUE lifecycle，对内调用 OpenSpec、Superpowers methodology、ForgeUE tools、codex-plugin-cc。

| 命令 | 场景与参数 | 前置条件 | 步骤 | 读取/修改 | 产物 | Done / Fail |
|---|---|---|---|---|---|---|
| `/forgeue:change-start <id>` | S0→S1 | id kebab-case；无同名 active change | 调 OpenSpec 创建 scaffold；写最小 proposal skeleton | 读 `openspec/config.yaml`；改 active change | `proposal.md` 初稿 | Done: S1；Fail: id 冲突 |
| `/forgeue:change-plan <id>` | S1/S2/S3 | active change 存在 | 完成 proposal/design/tasks；生成 execution plan；S2/S3 codex doc review | 改 proposal/design/tasks/execution；禁改 runtime | `execution_plan.md`、cross_check | Done: disputed_open=0；Fail: DRIFT/pending |
| `/forgeue:change-apply <id>` | S3→S4 | S3 通过 | 按 micro_tasks 实现；Superpowers TDD；必要时回写 contract | 改 tasks + scoped code；禁越界 | `tdd_log.md`、`debug_log.md` | Done: tasks 进度更新；Fail: scope drift |
| `/forgeue:change-debug <id>` | S4 修复 | active change + 失败证据 | 复现、定位、记录、修复或回写设计 | 改 scoped code/tasks/design | `debug_log.md` | Done: failure closed；Fail: contract gap pending |
| `/forgeue:change-verify <id> --level 0|1|2` | S4→S5 | tasks 至少部分完成 | 调 `forgeue_verify.py`；L1/L2 guard | 写 `verify_report.md` | JSON + MD report | Done: OK/guarded skip；Fail: real failure |
| `/forgeue:change-review <id>` | S2/S3/S5/S6 | review-env 决策完成 | 文档级用 `/codex:adversarial-review --background`；代码级用 `/codex:review` | 写 review files；禁 `/codex:rescue` | codex review + cross_check | Done: blocker=0；Fail: disputed/blocker |
| `/forgeue:change-doc-sync <id>` | S6→S7 | review blocker=0 | 调 `forgeue_doc_sync_check.py` | 可修改软文档；五件套按本 change 禁修 | `doc_sync_report.md` | Done: required/skip reason 完整 |
| `/forgeue:change-finish <id>` | S7→S8 | verify/review/doc sync ready | 调 `forgeue_finish_gate.py` | 写 finish report；不 archive | `finish_gate_report.md` | Done: S8；Fail: blocker |
| `/forgeue:change-status <id>` | 任意状态 | 可无 id | 调 `forgeue_change_state.py` | 只读 | JSON/status table | Done: state shown |
| `/forgeue:change-archive <id>` | S8→S9 | finish gate passed | 调 OpenSpec archive；不得由 Superpowers 替代 | 移动 change 到 archive | archived dir | Done: S9；Fail: finish gate missing |

codex-plugin-cc 复用规则：
- 允许 `/codex:review` 和 `/codex:adversarial-review`，命令能力来自增量需求 C，[forgeue-fusion-codex_prompt.md:737](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:737)、[forgeue-fusion-codex_prompt.md:738](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:738)。
- 禁止 `/codex:rescue`，因为它可写并会接管实现，[forgeue-fusion-codex_prompt.md:739](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:739)。
- 禁止 `/codex:setup --enable-review-gate`，[forgeue-fusion-codex_prompt.md:743](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:743)、[forgeue-fusion-codex_prompt.md:756](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:756)。

## 6. Tool Design

### `tools/forgeue_change_state.py`

目标：只读判断 active change 状态、artifact 完整性、invalid transition、writeback drift。

CLI：
```bash
python tools/forgeue_change_state.py --change <id> --json --dry-run
python tools/forgeue_change_state.py --change <id> --writeback-check --json
```

输入：`openspec/changes/<id>/proposal.md`、`design.md`、`tasks.md`、`execution/*`、`review/*`、`verification/*`、`.forgeue/review_env.json`。输出：stdout ASCII、可选 JSON。返回码：0 OK，2 usage，3 invalid transition，5 DRIFT。dry-run 不写文件。Windows：stdout 只用 `[OK] [FAIL] [SKIP] [WARN] [DRIFT] [REQUIRED] [OPTIONAL]`，沿 probe ASCII 约定，[probes/README.md:98](D:/ClaudeProject/ForgeUE_claude/probes/README.md:98)、[probes/README.md:113](D:/ClaudeProject/ForgeUE_claude/probes/README.md:113)。

JSON schema：
```json
{
  "change_id": "x",
  "state": "S3",
  "required_missing": [],
  "optional_missing": [],
  "drift": [{"type": "evidence_references_missing_anchor", "file": "execution/execution_plan.md"}],
  "next_allowed": false
}
```

不能做：不能修改 OpenSpec artifact，不能运行 tests，不能触发 provider，不能猜测 drift 归属。

### `tools/forgeue_verify.py`

目标：统一 Level 0/1/2 验证入口，生成 `verification/verify_report.md`。

CLI：
```bash
python tools/forgeue_verify.py --change <id> --level 0 --json
python tools/forgeue_verify.py --change <id> --level 1 --dry-run
python tools/forgeue_verify.py --change <id> --level 2 --allow-live --json
```

Level 0：`python -m pytest -q`、offline bundle smoke、安全本地检查；Level 1：provider/LLM checks，缺 key `[SKIP]`；Level 2：UE/ComfyUI/Hunyuan 3D 必须 `--allow-live` 或 env opt-in。分级依据现有 validation matrix，[docs/ai_workflow/validation_matrix.md:30](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/validation_matrix.md:30)、[docs/ai_workflow/validation_matrix.md:104](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/validation_matrix.md:104)、[docs/ai_workflow/validation_matrix.md:217](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/validation_matrix.md:217)。

返回码：0 全 OK 或 guarded skip，1 real test failure，2 usage，4 validation failed。不能硬编码测试总数；测试数量真源是实际 pytest 输出，[docs/ai_workflow/README.md:52](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:52)。

### `tools/forgeue_doc_sync_check.py`

目标：把现有 Documentation Sync Gate 机器化，输出 required/optional/skip/drift。

CLI：
```bash
python tools/forgeue_doc_sync_check.py --change <id> --json
python tools/forgeue_doc_sync_check.py --change <id> --dry-run
```

检查对象：`openspec/specs/*`、五件套、`README.md`、`CHANGELOG.md`、`CLAUDE.md`、`AGENTS.md`，与现有 Sync Gate 清单一致，[docs/ai_workflow/README.md:117](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:117)、[docs/ai_workflow/README.md:126](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:126)。输出 `verification/doc_sync_report.md`。只默认报告，不自动改长期 docs；显式命令才允许修改软性文档。返回码：0 OK，5 doc drift unresolved，2 usage。

### `tools/forgeue_finish_gate.py`

目标：archive 前最后防线。

CLI：
```bash
python tools/forgeue_finish_gate.py --change <id> --json
python tools/forgeue_finish_gate.py --change <id> --dry-run
```

检查：
- tasks 完成或有明确 skipped reason。
- `verify_report.md` 存在且无 real failure。
- review blocker 为 0。
- doc sync report 已完成。
- 所有 evidence frontmatter `aligned_with_contract: true`，或 false 但 drift decision 合法。
- claude-code env 且 codex-plugin 可用且 auto review 开启时，S2/S3/S5/S6 evidence 齐全。
- 禁止 `/codex:rescue` 与 review-gate 字面出现在 ForgeUE commands/skills。

输出 `verification/finish_gate_report.md`。返回码：0 pass，1 blocker，5 drift，2 usage。不能执行 archive；archive 仍由 OpenSpec 负责，[docs/ai_workflow/README.md:86](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:86)、[docs/ai_workflow/README.md:87](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:87)。

## 7. File-Level Change Plan

A. OpenSpec change files  
P0 才创建：
```text
openspec/changes/fuse-openspec-superpowers-workflow/
  proposal.md
  design.md
  tasks.md
  execution/
  review/
  verification/
```
不新增 delta specs，除非用户裁决要把 AI workflow 本身抽成新的 OpenSpec capability。

B. docs files  
Codex alternative：不要一次新增 4 份长文档，先新增 1 份中心契约，降低 drift 面。
```text
docs/ai_workflow/forgeue_integrated_ai_workflow.md
```
并更新既有 `docs/ai_workflow/README.md` 与 `validation_matrix.md` 的入口链接。五件套本 change 禁修。

C. Claude commands  
新增，不覆盖：
```text
.claude/commands/forgeue/change-start.md
.claude/commands/forgeue/change-plan.md
.claude/commands/forgeue/change-apply.md
.claude/commands/forgeue/change-debug.md
.claude/commands/forgeue/change-verify.md
.claude/commands/forgeue/change-review.md
.claude/commands/forgeue/change-doc-sync.md
.claude/commands/forgeue/change-finish.md
.claude/commands/forgeue/change-status.md
.claude/commands/forgeue/change-archive.md
```

D. Claude skills  
按 plan 推荐 14.3 “skills 数量锁 2”执行，[forgeue-fusion-codex_prompt.md:832](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:832)：
```text
.claude/skills/forgeue-integrated-change-workflow/SKILL.md
.claude/skills/forgeue-evidence-and-sync-gates/SKILL.md
```
不单独新增 `forgeue-superpowers-tdd-execution`，TDD/debug 作为第一个 skill 内部阶段，避免生成第三套流程。

E. Codex skills  
不新增 `.codex/skills/forgeue-change-adversarial-review/`。直接使用 codex-plugin-cc slash commands，这是增量需求 C 明确要求，[forgeue-fusion-codex_prompt.md:731](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:731)。

F. tools  
新增 4 个脚本，不进 `console_scripts`：
```text
tools/forgeue_change_state.py
tools/forgeue_verify.py
tools/forgeue_doc_sync_check.py
tools/forgeue_finish_gate.py
```

G. tests  
新增：
```text
tests/unit/test_forgeue_change_state.py
tests/unit/test_forgeue_verify.py
tests/unit/test_forgeue_doc_sync_check.py
tests/unit/test_forgeue_finish_gate.py
tests/unit/test_forgeue_workflow_markdown_guards.py
```

H. README / CHANGELOG / CLAUDE.md / AGENTS.md  
按 Documentation Sync Gate 评估后更新。`CLAUDE.md` 与 `AGENTS.md` 必须同步，因为两者语义同步约定存在，[AGENTS.md:3](D:/ClaudeProject/ForgeUE_claude/AGENTS.md:3)。

I. 不应修改  
`.claude/commands/opsx/*`、`.claude/skills/openspec-*`、`.codex/skills/openspec-*`、`openspec/specs/*`、`openspec/config.yaml`、`src/framework/**` runtime 核心、五件套、`examples/*.json`、`probes/**`、`ue_scripts/**`、`config/models.yaml`、archived changes。

## 8. OpenSpec Change Draft (proposal/design/tasks 草案)

### `proposal.md` 草案

```markdown
# Proposal: fuse-openspec-superpowers-workflow

## Why
ForgeUE 已有 OpenSpec 主流程，但 implementation/debug/review/finish 阶段仍依赖人工纪律。现有 `/opsx:*` 可创建和推进 OpenSpec artifact，但没有把 Superpowers execution methodology、Codex cross-review、validation evidence、Documentation Sync Gate、finish gate 统一成可检查的中心化 lifecycle。

## What
新增 ForgeUE Integrated AI Change Workflow：
- `/forgeue:change-*` 生命周期命令。
- active change 下的 `execution/`、`review/`、`verification/` evidence 子目录。
- evidence frontmatter + writeback drift 协议。
- env-aware codex stage review。
- 4 个 ForgeUE guard tools。
- 2 个 Claude skills。
- markdown guard tests 与 tool unit tests。

## Non-Goals
不修改 ForgeUE runtime 对象模型；不引入 Superpowers runtime dependency；不默认触发 paid provider / UE / ComfyUI；不修改 OpenSpec 默认 commands/skills；不创建 `.codex/skills/forgeue-*`。

## Scope
AI workflow、Claude command markdown、Claude skill markdown、tools、tests、docs/ai_workflow、README/CHANGELOG/CLAUDE/AGENTS sync。

## Success Criteria
S0-S9 状态机可由工具判定；finish gate 能阻断未验证、未 review、未 doc sync、未 writeback 的 archive；Codex review evidence 按 env 策略落盘；Documentation Sync Gate 生成可读可机读报告。

## Risks
第二事实源、误触发付费调用、review blocker 被忽略、doc drift 未显式化、工具复杂化。

## Rollback Plan
删除新增 `/forgeue:*` commands、2 个 skills、4 个 tools、对应 tests 与 docs/ai_workflow 新文档；保留 `/opsx:*` 原流程不受影响。
```

### `design.md` 草案

```markdown
# Design: ForgeUE Integrated AI Change Workflow

## Current State
OpenSpec 已是主流程；Superpowers 目前未接入主线；Codex review 经验存在但不是统一 stage gate。

## Target State
OpenSpec contract artifact 居中。Superpowers/codex/tools 都只产 evidence，任何 contract gap 必须回写 proposal/design/tasks/specs。

## Integrated Workflow State Machine
S0-S9，Pre-P0 不纳入通用状态机。

## Artifact Mapping
execution/review/verification 均为 evidence，不是规范源。

## Command Design
新增 `/forgeue:change-*`，作为 OpenSpec + Superpowers + ForgeUE tools + codex-plugin-cc facade。

## Tool Design
`forgeue_change_state.py`、`forgeue_verify.py`、`forgeue_doc_sync_check.py`、`forgeue_finish_gate.py`。

## Phase Gates
S2/S3 文档级 Codex cross-check；S5/S6 review/verification gate；S7 doc sync；S8 finish。

## Documentation Sync Gate
复用现有 10 文档清单，但输出 `doc_sync_report.md`。

## Finish Gate
解析 evidence frontmatter，阻断 pending drift / blocker / missing verification。

## Risk Controls
ASCII stdout、dry-run、json、opt-in live、no hardcoded test totals、no rescue、no review-gate。

## Compatibility
不修改 runtime；不改 OpenSpec 默认产物；不新增 runtime dependency。

## Migration Plan
P0 dogfood 本 change；P1 文档；P2 commands/skills；P3 tools；P4 tests；P5 validation；P6 sync；P7 finish；P8 archive readiness。

## Reasoning Notes
记录任何 `disputed-permanent-drift` anchor。
```

### `tasks.md` 草案

```markdown
# Tasks

## P0 OpenSpec change setup
- [ ] Create active change `fuse-openspec-superpowers-workflow`
- [ ] Add proposal/design/tasks
- [ ] Record no runtime capability delta specs unless user decides otherwise

## P1 Workflow docs
- [ ] Add `docs/ai_workflow/forgeue_integrated_ai_workflow.md`
- [ ] Link from README / docs/ai_workflow/README.md
- [ ] Update validation_matrix references if needed

## P2 Claude commands and skills
- [ ] Add `/forgeue:change-*` command markdown
- [ ] Add 2 Claude skills
- [ ] Add markdown guard rules forbidding `/codex:rescue` and review-gate

## P3 Tools
- [ ] Implement `forgeue_change_state.py`
- [ ] Implement `forgeue_verify.py`
- [ ] Implement `forgeue_doc_sync_check.py`
- [ ] Implement `forgeue_finish_gate.py`

## P4 Tests
- [ ] Add unit tests for each tool
- [ ] Add markdown guard tests
- [ ] Add JSON/dry-run/ASCII/skip/no-paid-provider tests

## P5 Validation
- [ ] Run Level 0
- [ ] Record L1/L2 skip or opt-in evidence

## P6 Documentation Sync
- [ ] Generate doc sync report
- [ ] Update soft docs or record skip reasons

## P7 Finish Gate
- [ ] Generate finish gate report
- [ ] Resolve blockers

## P8 Archive readiness
- [ ] Confirm finish gate passed
- [ ] Archive via OpenSpec only

## Documentation Sync
- [ ] Check whether openspec/specs/* needs update after archive
- [ ] Check whether docs/requirements/SRS.md needs update
- [ ] Check whether docs/design/HLD.md needs update
- [ ] Check whether docs/design/LLD.md needs update
- [ ] Check whether docs/testing/test_spec.md needs update
- [ ] Check whether docs/acceptance/acceptance_report.md needs update
- [ ] Check whether README.md needs update
- [ ] Check whether CHANGELOG.md needs update
- [ ] Check whether CLAUDE.md needs update
- [ ] Check whether AGENTS.md needs update
- [ ] Record skipped docs with reason
- [ ] Mark doc drift for human confirmation if sources conflict
```

## 9. Claude Skills Design

### `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`

目标：驱动 S0-S6 的 OpenSpec-centered execution。  
触发：用户调用 `/forgeue:change-start|plan|apply|debug|review`，或明确要求推进 ForgeUE change workflow。  
必读：`CLAUDE.md`、`docs/ai_workflow/README.md`、active change proposal/design/tasks、`execution/*`、`review/*`。  
输入 artifact：OpenSpec contract artifacts。  
输出 artifact：`execution/brainstorming_notes.md`、`execution_plan.md`、`micro_tasks.md`、`tdd_log.md`、`debug_log.md`、`review/superpowers_review.md`。  
禁止动作：无 active change 不实现；不修改 `/opsx:*`；不调用 paid provider；不使用 `/codex:rescue`；不把 Superpowers plan 变成规范源。  
与 OpenSpec 关系：OpenSpec 是唯一 contract；skill 只辅助执行。  
与 Superpowers 关系：只吸收 methodology，不引入 runtime dependency。  
与 tools 关系：阶段切换前必须读取 `forgeue_change_state.py` 结果。  
完成标准：evidence frontmatter 完整，DRIFT 为 0 或已回写。  
失败处理：发现 contract gap 时停止执行并回写 proposal/design/tasks。

### `.claude/skills/forgeue-evidence-and-sync-gates/SKILL.md`

目标：驱动 S5-S8 的 verify/doc-sync/finish gate。  
触发：`/forgeue:change-verify|doc-sync|finish|archive`。  
必读：validation matrix、active change evidence、Documentation Sync Gate 规则。  
输入 artifact：`verify_report.md`、review reports、doc sync state。  
输出 artifact：`verification/doc_sync_report.md`、`verification/finish_gate_report.md`。  
禁止动作：不 archive；不自动修改五件套；不忽略 blocker；不硬编码测试总数。  
与 OpenSpec 关系：archive 前守门；archive 仍由 OpenSpec 完成。  
与 Superpowers 关系：可总结 finish，不可裁决 contract。  
与 tools 关系：必须调用 4 个 tools 中对应工具。  
完成标准：finish gate pass，所有 skip 有 reason。  
失败处理：定位 blocker 所属状态并回退。

## 10. Codex Review Skill Design

不新增 `.codex/skills/forgeue-change-adversarial-review/SKILL.md`。这是对原模板的有意修正：增量需求 C 明确 Codex 在 Claude Code 内通过 codex-plugin-cc 接入，不是在 repo `.codex/skills/` 下造文件，[forgeue-fusion-codex_prompt.md:731](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:731)。

替代设计：`Codex Review Protocol`。

触发场景：
- S2 design document review。
- S3 execution plan review。
- S5 code verification review。
- S6 mixed adversarial review。

必读文件：
- active change proposal/design/tasks。
- `execution/execution_plan.md`。
- `verification/verify_report.md`。
- git diff / changed file list。
- relevant tests and docs with line references。

文档级 review 输出：
```yaml
---
review_scope: design|plan
detected_env: claude-code
triggered_by: auto
disputed_open: 0
codex_plugin_available: true
---
```

文档级 cross-check 格式：
```markdown
## A. Decision Summary
冻结在调用 Codex 前。

## B. Cross-Check Matrix
| id | codex claim | status | reason | action |
|---|---|---|---|---|
| C1 | ... | aligned / accepted-codex / accepted-claude / disputed-blocker | ≥20 字 | ... |

## C. Accepted Changes
列出写回 proposal/design/tasks 的项。

## D. Disputed Blockers
`disputed_open == 0` 才能进入下一阶段。
```

代码级 review 输出：`review/codex_verification_review.md`。Codex 只找 bug；Claude 必须独立对照代码验证后修复或拒收，现有项目规则已要求不把外部 review claim 当结论，[docs/ai_workflow/README.md:66](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:66)、[openspec/config.yaml:91](D:/ClaudeProject/ForgeUE_claude/openspec/config.yaml:91)。代码级不做双向 cross-check，避免把 bug triage 变成设计投票。

## 11. Risk Controls

| 风险 | 位置 | 预防规则 | 工具检查 | 命令检查 | 失败处理 | 人工确认 |
|---|---|---|---|---|---|---|
| OpenSpec 被 Superpowers 架空 | S3/S4 | evidence 不能声明新规范 | writeback-check | plan/apply 前检查 | 回写 contract | 是 |
| 第二事实源 | execution/review | frontmatter + contract_refs | DRIFT exit 5 | 禁止进入下一阶段 | pending blocks | 是 |
| 只在聊天里 plan | S2/S3 | plan 必须落盘 | state missing evidence | change-plan done gate | 停 S3 | 否 |
| execution_plan 与 tasks drift | S3 | task anchor 必须存在 | missing_anchor | change-plan gate | 回写 tasks | 是 |
| design 与代码 drift | S4/S5 | verify design adherence | verify_report | change-verify | 修代码或改 design | 是 |
| docs/ai_workflow 与 CLAUDE/AGENTS drift | S7 | Sync Gate 清单 | doc_sync_check | change-doc-sync | 更新或 skip reason | 是 |
| 跳过测试 finish | S8 | verify_report required | finish_gate | change-finish | 回 S5 | 否 |
| review blocker 被忽略 | S6/S8 | blocker=0 | finish_gate | change-review | 回 S4/S5 | 是 |
| doc sync 未完成 archive | S7/S8 | doc_sync_report required | finish_gate | change-finish | 回 S7 | 是 |
| 误触发 paid provider | verify/probe | L1/L2 opt-in | verify guard | command flag | `[SKIP]` 或 fail | 是 |
| 误触发 UE/ComfyUI live | Level 2 | `--allow-live` | verify guard | command flag | `[SKIP]` | 是 |
| 越界重构 | S4 | active change scope only | state scope hints | apply checklist | revert own changes | 是 |
| 修改 OpenSpec 默认 commands/skills | P2 | 新增 forgeue namespace | markdown guard | command review | fail test | 否 |
| 修改 runtime 核心对象模型 | P3/P4 | 本 change 禁修 runtime | file allowlist test | apply guard | block PR | 是 |
| Windows stdout 编码 | tools/probes | ASCII markers | unit test | command template | fail test | 否 |
| tools 变复杂框架 | P3 | 4 scripts only，无 console_scripts | test import boundary | design review | 拆减功能 | 是 |

## 12. Test Plan

测试不依赖真实 API key、不触发 paid provider、不触发 UE、不触发 ComfyUI。测试工具逻辑，不测试 Claude 是否聪明。

- `test_forgeue_change_state.py`：active change list、S0-S9 判定、invalid transition、missing artifact、writeback DRIFT exit 5。
- `test_forgeue_verify.py`：Level 0 命令计划、Level 1 缺 key `[SKIP]`、Level 2 无 `--allow-live` 阻断、真实失败非零、无硬编码测试总数。
- `test_forgeue_doc_sync_check.py`：10 文档清单、required/optional/skip/drift 分类、skip reason 必填。
- `test_forgeue_finish_gate.py`：缺 verify/review/doc sync 阻断、review blocker 阻断、pending drift 阻断、`disputed-permanent-drift` reason 长度与 Reasoning Notes anchor。
- `test_forgeue_workflow_markdown_guards.py`：commands/skills 不含 `/codex:rescue`、不含 `/codex:setup --enable-review-gate`、stdout marker ASCII-only、所有 commands 有 active change 前置条件。
- JSON schema tests：4 个 tools 的 `--json` 字段稳定。
- dry-run tests：不写文件、不运行外部命令。
- env detection tests：CLI flag → env var → `.forgeue/review_env.json` → heuristic → unknown；`--review-env=none` 强关；`--force-codex-review` 强开。
- codex optional tests：plugin unavailable 时 OPTIONAL，不阻断 archive，符合 14.16，[forgeue-fusion-codex_prompt.md:828](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/_drafts/forgeue-fusion-codex_prompt.md:828)。
- no paid provider default tests：沿现有 probe opt-in 精神，[probes/README.md:124](D:/ClaudeProject/ForgeUE_claude/probes/README.md:124)、[probes/README.md:126](D:/ClaudeProject/ForgeUE_claude/probes/README.md:126)。

## 13. Implementation Phases

| Phase | 目标 | 修改文件 | 验收标准 | 风险 | 回滚 | 人工确认 |
|---|---|---|---|---|---|---|
| P0 | 创建 OpenSpec change 并 dogfood | `openspec/changes/fuse-*` | proposal/design/tasks ready | self-host 递归 | 删除 active change | 是 |
| P1 | 中心化 workflow doc | `docs/ai_workflow/*` | 文档含 state/evidence/writeback | doc drift | revert docs | 是 |
| P2 | commands/skills | `.claude/commands/forgeue/*`、2 skills | markdown guard pass | 命令绕过 OpenSpec | 删除新增命令 | 是 |
| P3 | tools | `tools/*.py` | dry-run/json/ASCII pass | 工具过度设计 | 删除 tools | 是 |
| P4 | tests | `tests/unit/test_forgeue_*` | unit pass | 测试过脆 | revert tests | 否 |
| P5 | validation | reports | Level 0 pass，L1/L2 skip reason | live 误触发 | 清报告重跑 | 是 |
| P6 | Documentation Sync Gate | soft docs | doc_sync_report complete | 五件套误改 | revert own docs | 是 |
| P7 | finish gate | finish report | blocker=0 | false positive | 调整 tool | 是 |
| P8 | archive readiness | OpenSpec archive | archived path exists | archive 前漏 sync | 回滚 archive commit | 是 |

## 14. Human Confirmation Needed

- 是否接受 Codex alternative：只新增 1 份 `docs/ai_workflow/forgeue_integrated_ai_workflow.md`，而不是原模板建议的 4 份 docs。
- 是否接受 Claude skills 数量锁 2，并把 Superpowers TDD/debug 合并进 integrated workflow skill。
- 是否确认 `.codex/skills/forgeue-*` 不创建，完全复用 codex-plugin-cc。
- 是否确认 codex evidence required 条件采用“env 触发 + plugin 可用 + auto review 开启”；plugin 不可用时 OPTIONAL，不阻断 archive。
- 是否确认 `written-back-to-*` 必须有真实 commit；未 commit 的 artifact 修改只能保持 `pending`，阻断 finish。
- 是否确认本 change 不改 `openspec/specs/*` 主 spec；AI workflow 先放在 `docs/ai_workflow/` 与 command/tool tests 中约束。

## 15. Do-Not-Modify List

- `.claude/commands/opsx/*`：OpenSpec 默认 commands，不修改，[CLAUDE.md:162](D:/ClaudeProject/ForgeUE_claude/CLAUDE.md:162)、[docs/ai_workflow/README.md:265](D:/ClaudeProject/ForgeUE_claude/docs/ai_workflow/README.md:265)。
- `.claude/skills/openspec-*` 与 `.codex/skills/openspec-*`：OpenSpec 默认 skills，不修改，[openspec/config.yaml:95](D:/ClaudeProject/ForgeUE_claude/openspec/config.yaml:95)。
- `openspec/specs/*`：本 change 不改变 runtime capability 行为，不动。
- `openspec/config.yaml`：项目 OpenSpec 规则源，不动；其已记录 spec-driven schema 和 ForgeUE 规则，[openspec/config.yaml:1](D:/ClaudeProject/ForgeUE_claude/openspec/config.yaml:1)、[openspec/config.yaml:57](D:/ClaudeProject/ForgeUE_claude/openspec/config.yaml:57)。
- `src/framework/{core,runtime,providers,review_engine,ue_bridge,workflows,comparison,pricing_probe,artifact_store}/**`：runtime 核心不动。
- 五件套：`docs/requirements/SRS.md`、`docs/design/HLD.md`、`docs/design/LLD.md`、`docs/testing/test_spec.md`、`docs/acceptance/acceptance_report.md`，本 Pre-P0/P0 不动。
- `pyproject.toml` dependencies / optional-dependencies：不引入 Superpowers 或新 runtime dependency；现有 runtime/optional deps 在 [pyproject.toml:12](D:/ClaudeProject/ForgeUE_claude/pyproject.toml:12)、[pyproject.toml:23](D:/ClaudeProject/ForgeUE_claude/pyproject.toml:23)。
- `examples/*.json`、`probes/**`、`ue_scripts/**`、`config/models.yaml`：不动。
- `docs/archive/claude_unified_architecture_plan_v1.md` 与已 archived changes：不动。
- `artifacts/`、`demo_artifacts/`、`.env`、API key、本机绝对路径：不提交。

## Final Judgment

- 这个方案是真正的流程融合，不是拼装：中心是 OpenSpec contract artifact；Superpowers、codex、ForgeUE tools 都只是 evidence 和 guard，且 writeback 不可绕过。
- 仍只是桥接的部分：codex-plugin-cc 本身仍是外部 slash command；Superpowers 本身仍是 Claude Code methodology/plugin，ForgeUE 只能通过 command/skill/evidence 协议约束它，不能把它变成 runtime 内生能力。
- 已达到 lifecycle fusion 的部分：S0-S9 状态机、evidence frontmatter、DRIFT/writeback 协议、env-aware review hook、Documentation Sync Gate report、finish gate blocker，是同一条 OpenSpec lifecycle 的阶段门。
- 需要人工裁决的地方：docs 数量、skills 数量、codex optional blocker 语义、`writeback_commit` 是否必须真实 commit、以及是否未来把 AI workflow 抽成新的 OpenSpec capability spec。