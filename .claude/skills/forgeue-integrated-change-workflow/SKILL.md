---
name: forgeue-integrated-change-workflow
description: ForgeUE 中心化编排器主 skill;每个 /forgeue:change-* command 引用本 skill 作 backbone。包含中心化架构图 + Superpowers/codex 集成边界 + S0-S9 状态机 + 4 类 DRIFT taxonomy + 12-key frontmatter + writeback 协议 + cross-check A/B/C/D 模板。
license: MIT
compatibility: Requires openspec CLI + Claude Code (Superpowers + codex-plugin-cc 可选,降级 OPTIONAL 不阻断 archive)
metadata:
  author: forgeue
  version: "1.0"
---

ForgeUE Integrated AI Change Workflow 的中心化编排器。本 skill 是 8 个 `/forgeue:change-*` command(`change-{status,plan,apply,debug,verify,review,doc-sync,finish}`)的共享 backbone:统一架构 + 状态机 + 协议,每个 command 只引用本 skill,不重复定义。

**真源**:`openspec/changes/fuse-openspec-superpowers-workflow/design.md` §1-§11 + Reasoning Notes;`docs/ai_workflow/forgeue_integrated_ai_workflow.md`(本 skill 的 user-facing 详表 + 阅读引导)。

## 中心化架构(design.md §1)

```
                    OpenSpec Contract Artifact (唯一锚点)
              proposal.md / design.md / tasks.md / specs/
                              ^
                              | writeback required
        ----------------------------------------------------------
        | Superpowers evidence | codex review evidence | tools DRIFT |
        ----------------------------------------------------------
                              |
              ForgeUE guard tools: state / verify / doc-sync / finish
```

OpenSpec contract artifact 是项目唯一规范锚点;Superpowers / codex / ForgeUE tool 产生的 evidence **服务于这个中心**,不并立。

**evidence 不能成新规范源**:实施暴露的 contract 漏洞**必须回写到 OpenSpec contract**,禁止在 evidence 里宣告"新决策"。

## Superpowers 集成边界(design.md §6 / §8 / forgeue_integrated_ai_workflow.md §B.3)

| Superpowers skill | trigger 时机 | ForgeUE 配置 / 边界 |
|---|---|---|
| `brainstorming` | S0 / S1 起草 proposal 前 | scope 变化是否回写 proposal |
| `writing-plans` | S2(`/forgeue:change-plan` 内) | 输出落 `execution/execution_plan.md` + `execution/micro_tasks.md` |
| `executing-plans` | S3-S4 | 实施时 Claude 主动调,不强制 |
| `test-driven-development` | S4 实施 | tdd_log 追加;**不**重复造 ForgeUE TDD skill |
| `systematic-debugging` | S4 bug 时(`/forgeue:change-debug`)| debug_log 追加 |
| `requesting-code-review` | S5-S6 | superpowers_review 增量 + finalize |
| `verification-before-completion` | S5 | verify_report 输入 |
| `finishing-a-development-branch` | S9 后 | git 层 merge / PR / discard;不进 evidence |
| `using-git-worktrees` | **禁用** | 与 ForgeUE 单-worktree 假设冲突 |
| `subagent-driven-development` | OPTIONAL | paid API 拦截:env guard `{1,true,yes,on}` + ADR-007 |

## codex stage hook(design.md §3 / §4 / forgeue_integrated_ai_workflow.md §B.4)

| stage | hook 命令 | 评审范围 | cross-check 要求 |
|---|---|---|---|
| **S2 design** | `/codex:adversarial-review --background "<design focus>"` | 文档级 | 强制 cross-check(`review/design_cross_check.md`)|
| **S3 plan** | `/codex:adversarial-review --background "<plan focus>"` | 文档级 | 强制 cross-check(`review/plan_cross_check.md`)|
| **S5 verification** | `/codex:review --base <main>` | 代码级 | 单向挑错,**无** cross-check |
| **S6 adversarial** | `/codex:adversarial-review --background "<full focus>"` | mixed scope | blocker 独立验证;**无** cross-check |

**env-conditional + plugin-conditional 双重 enforce**:
- claude-code env + plugin available → REQUIRED
- claude-code env + plugin not available → OPTIONAL,evidence 标 `_unavailable_reason: codex_plugin_unavailable`
- non-claude-code env → OPTIONAL(由 agent 自决)

## State Machine S0-S9(design.md §3)

完整表见 `forgeue_integrated_ai_workflow.md` §B.1。关键横切硬约束:

- 没 active change → `/forgeue:change-{plan,apply,...}` abort
- proposal/design/tasks 不齐 → 不能进 S3
- 测试未跑 / 未解释 SKIP → 不能进 S6
- review blocker 未清 → 不能进 S7
- doc sync DRIFT → 不能进 S8
- **evidence 含 `aligned_with_contract: false` 且未标 drift → 不能进 S9**(中心化最后防线)

## 12-key frontmatter(design.md §3)

每份 evidence 必含 1 wrapper(`change_id`)+ 11 audit fields:

```yaml
---
change_id: <change-id>
stage: S<N>
evidence_type: <enum>
contract_refs: [path#anchor, ...]
aligned_with_contract: <bool>
drift_decision: null | pending | written-back-to-<artifact> | disputed-permanent-drift
writeback_commit: <sha> | null
drift_reason: <string> | null
reasoning_notes_anchor: <anchor> | null
detected_env: claude-code | codex-cli | cursor | aider | unknown
triggered_by: auto | cli-flag | env-var | setting | forced
codex_plugin_available: <bool> | null
---
```

## 4 类 named DRIFT(design.md §3)

`tools/forgeue_change_state.py --writeback-check` 检测,exit 5 阻断:

1. `evidence_introduces_decision_not_in_contract` — evidence 含 contract 未记录决策
2. `evidence_references_missing_anchor` — plan/micro_tasks 引用 `tasks.md#X.Y` 不存在
3. `evidence_contradicts_contract` — implementation log 与 design.md 接口字段不一致
4. `evidence_exposes_contract_gap` — debug log 揭示 design.md 异常段缺失

附加 frontmatter 校验由 `forgeue_finish_gate.py` exit 2 阻断(spec.md ADDED Requirement Scenario 2-3 protocol)。

## writeback 协议三态(design.md §3)

- `null` — 当前 evidence 无 drift
- `pending` — drift 已识别,未决定;阻断下一阶段
- `written-back-to-<artifact>` — drift 已通过修改 contract artifact 消化;`writeback_commit` 必有真实 sha;finish gate 用 `git rev-parse <sha>` + `git show --stat <sha>` 二次校验
- `disputed-permanent-drift` — 经评估永久不回写;必有 ≥ 50 字 `drift_reason` + `reasoning_notes_anchor` 指向 design.md `## Reasoning Notes` 段实际存在的 anchor

## cross-check A/B/C/D 模板(design.md §3 Cross-check Protocol)

`design_cross_check.md` / `plan_cross_check.md` 必含:

- `## A. Decision Summary` — 冻结于 codex 调用之前;Claude **不**得在写 ## B/C/D 时回填 ## A
- `## B. Cross-check Matrix` — 逐条 codex finding + Resolution
- `## C. Disputed Items Pending Resolution` — `disputed_open: <count>`;> 0 阻断
- `## D. Verification Note` — 独立验证 file:line(沿 `feedback_verify_external_reviews`)

frontmatter 必含:`disputed_open: <int>` / `codex_review_ref: <path>` / `created_at` / `resolved_at`。

**Resolution 6 取值**:`aligned` / `accepted-codex` / `accepted-claude`(reason ≥ 20 字)/ `disputed-blocker`(临时态)/ `disputed-pending`(必含在 ## C)/ `disputed-permanent-drift`(reason ≥ 50 字 + Reasoning Notes anchor)。

**不走 cross-check**(carve-out):S5 verification single-direction review;S6 adversarial mixed scope review。

## 命令边界(design.md §11.1)

- **OpenSpec 默认命令**(强调 contract 中心地位,**不**包 facade):`/opsx:new` / `/opsx:propose` / `/opsx:archive` 等
- **ForgeUE 命令**(`/forgeue:change-*`,8 个):编排 S2-S8 实施 / cross-review / Sync Gate / Finish Gate;**不**做 contract create/archive

## 反模式 fence(design.md §6)

- **不**创建 `.claude/skills/forgeue-superpowers-tdd-execution/`(重复 Superpowers `test-driven-development`;P4 fence `test_forgeue_no_duplicated_tdd_skill.py` 守门)
- **不**新增 `.codex/skills/forgeue-*-review/`(走 codex-plugin-cc `/codex:*`;P4 fence `test_forgeue_codex_review_no_skill_files.py` 守门)

## 禁用项(design.md §4)

- `/codex:rescue` 在 ForgeUE workflow 内(违 review-only 原则;Pre-P0 是本 fusion change 一次性附录例外,未来其他 change 不豁免;markdown lint fence 守门)
- `/codex:setup --enable-review-gate`(plugin 自警告 long loop;`forgeue_finish_gate.py` 检查 `~/.claude/settings.json` 含 review-gate hook → WARN)

## ASCII 标记(design.md §5 / ForgeUE memory `feedback_ascii_only_in_adhoc_scripts`)

stdout / evidence markdown:用 7 种 ASCII 标记 `[OK]` / `[FAIL]` / `[SKIP]` / `[WARN]` / `[DRIFT]` / `[REQUIRED]` / `[OPTIONAL]`;**不**用 emoji(Windows GBK stdout / fence 测试 / lint 都会出问题)。

## Input / Output

**Input**: skill 自身不直接被用户调用;由 `/forgeue:change-*` command 引用作 backbone。

**Output**: skill 提供共享 mental model;实际 evidence 文件由各 command 写入,frontmatter 12-key + 协议遵循本 skill 的描述。

## Guardrails

- **必绑 active change**(所有引用本 skill 的 command 共享此约束)。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**(全局禁令)。
- **不引入 paid provider / live UE / live ComfyUI 默认调用**(env guard 严格;Level 1/2 opt-in)。
- **不让 evidence 成新规范源**(中心化协议物理表达)。
- **不重复造轮子**:Superpowers 已有的 skill 不再做同名 ForgeUE skill。
- **数字以实测为准**:`pytest` 总数等不硬编码,以 `python -m pytest -q` 实际输出为准。

## References

- `openspec/changes/fuse-openspec-superpowers-workflow/design.md` §1-§11 + Reasoning Notes(权威源)
- `openspec/changes/fuse-openspec-superpowers-workflow/specs/examples-and-acceptance/spec.md`(ADDED Requirement + 3 Scenarios + Validation + Non-Goals)
- `docs/ai_workflow/forgeue_integrated_ai_workflow.md`(user-facing 详表 + 阅读引导)
- `docs/ai_workflow/README.md` §4(Documentation Sync Gate 主规则)
- ForgeUE memory:`feedback_verify_external_reviews` / `feedback_no_silent_retry_on_billable_api` / `feedback_decisive_approval` / `feedback_ascii_only_in_adhoc_scripts`
