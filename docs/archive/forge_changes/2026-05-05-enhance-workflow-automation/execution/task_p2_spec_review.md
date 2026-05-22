---
change_id: enhance-workflow-automation
stage: S4
evidence_type: subagent_spec_review
contract_refs:
  - openspec/changes/enhance-workflow-automation/tasks.md
  - openspec/changes/enhance-workflow-automation/specs/examples-and-acceptance/spec.md
  - openspec/changes/enhance-workflow-automation/design.md
aligned_with_contract: true
drift_decision: null
writeback_commit: null
drift_reason: null
reasoning_notes_anchor: null
detected_env: claude-code
triggered_by: skill_invoke
codex_plugin_available: true
triggered_by_command: change-apply-subagent
autonomy_decision: claude_autonomous
created_at: 2026-05-05T04:30:00+08:00
---

# P2 Spec Review — task_p2_spec_review

Reviewer: spec-review subagent (Claude Sonnet 4.6)
Commit under review: c6913ae
Files reviewed: `.claude/commands/codex/review.md`, `.claude/commands/codex/adversarial-review.md`, `tests/unit/test_codex_command_markdown.py`

---

## 1. review.md 逐项核查

### P2.2 — Execution Mode 默认 background（3-AND gate，无 AskUserQuestion）

- **`## Execution Mode Rules` 段存在**：行 76 起，标题 `## Execution Mode Rules`。
- **默认 background**：行 80 明确写 `**Default: background.**`，满足 spec 要求。
- **3-AND gate 全部在场**：
  - Condition 1（≤2 files AND ≤50 lines）：行 83-84，符合 spec 的"2 files / 50 lines"阈值。
  - Condition 2（Non-adversarial）：行 85-86，明确 adversarial 永远 background。
  - Condition 3（Must-wait）：行 87-88，描述"main session's next action strictly requires"。
- **旧 AskUserQuestion 弹框路径移除**：`AskUserQuestion` 仍在文件中出现（8 处），但全部是"禁止使用"语境（如 `Do NOT use AskUserQuestion to ask the user which mode to use` 行 105）或历史注释（`AskUserQuestion removed from allowed-tools` 行 198），**没有任何路径指示弹框二选一**。旧 upstream 的 `use \`AskUserQuestion\` exactly once with two options`（精确匹配）：**0 命中（已移除）**。
- **`--wait` / `--background` 显式 flag override**：行 93-95 保留两个显式 override 通道，符合 spec。
- **allowed-tools 里 AskUserQuestion 移除**：frontmatter 行 4：`allowed-tools: Read, Glob, Grep, Bash(node:*), Bash(git:*)`，无 AskUserQuestion。

### P2.3 — review_type 5 类枚举

- **`## review_type Enumeration` 段存在**：行 17 起。
- **5 类字符串全部在场**：
  - `codex_design_review` 行 22
  - `codex_plan_review` 行 23
  - `codex_verification_review` 行 24
  - `codex_adversarial_review` 行 25
  - `codex_mixed_scope_review` 行 26
- **review_type 推导规则**：行 28-36，`--stage` hint 传入方式符合 spec P2.3 推导规则（S2/S3/S5 / default → `codex_mixed_scope_review`）。
- **5 个独立 counter 文件路径**（含 review_type 前缀）：行 39-44 全部列出：
  - `notes/codex_design_review_round_counter.txt`
  - `notes/codex_plan_review_round_counter.txt`
  - `notes/codex_verification_review_round_counter.txt`
  - `notes/codex_adversarial_review_round_counter.txt`
  - `notes/codex_mixed_scope_review_round_counter.txt`

### P2.4 — `## Round Counter & Context Bridge` 段

- **段存在**：行 46 起。
- **counter read + N≥1 时前缀注入 fence**：行 50-64，round-bridge fence 内容完整（含 `本次 review 是 round {N+1}` + `强制要求：... MUST 先读 ...`）。
- **counter 写回 + evidence 落盘**：行 65-68，完整描述"increment counter"+ save output 路径。
- **Isolation constraints**：行 70-74，明确 same change_id / same review_type / direct predecessor only，符合 spec 三条约束。

### P2.5 — `## Polling Convention` 段

- **段存在**：行 108 起。
- **job id capture 路径**：行 113-117，从 `codex-companion.mjs` stdout 第一行解析，写入 `notes/<review_type>_active_jobs.txt`，符合 spec。
- **用户告知文本**：行 119-121，包含 `/codex:status --wait <job>` 和 `/codex:result <job>`。
- **`Main session MUST poll job before consuming verdict`**：行 123，精确匹配 spec 要求字符串（含后缀 `via /codex:status --wait + /codex:result.`）。
- **旧矛盾文本移除**：`Do not call BashOutput or wait for completion in this turn.`（精确匹配）：**0 命中**。文件行 207-209 出现在注释块内 `Removed "Do not call BashOutput or wait for` — 这是 `completion in this turn."` 跨行拆开的 HTML 注释描述，不是旧逻辑文本本身，精确字符串不命中，符合 spec 要求。

### P2.6 — ForgeUE local override 头注释

- **原注释"Two changes vs upstream"扩展为"Five changes"**：行 187 起，`Five changes vs upstream plugin source (enhance-workflow-automation P2)`。
- **5 项 override 全部列出**：change 3 = default background / change 4 = Round Counter & Context Bridge / change 5 = Polling Convention，与 spec P2.6 要求一致。

---

## 2. adversarial-review.md 逐项核查

### P2.2 — adversarial 永远 background

- **`## Execution Mode Rules` 段存在**：行 73 起。
- **"永远 background"明确表述**：行 77 `**Adversarial always runs in background.**`，满足 spec "adversarial 永远 background"要求。
- **无 size estimation 逻辑**：整段无 `git diff --shortstat` / 文件数判断路径，符合 spec（不需要 size estimation）。
- **旧 AskUserQuestion 弹框路径移除**：精确匹配 `use \`AskUserQuestion\` exactly once with two options`：**0 命中**。
- **allowed-tools frontmatter**：行 4 `allowed-tools: Read, Glob, Grep, Bash(node:*), Bash(git:*)`，AskUserQuestion 已移除。

### P2.3 — review_type 5 类枚举（adversarial-review.md）

- **`## review_type Enumeration` 段存在**：行 17 起，5 类全部在场（行 22-26）。
- **adversarial 固定 review_type**：行 28-29，`For this command: review_type is always codex_adversarial_review — no derivation needed.`
- **5 个独立 counter 文件路径**：行 37-41，全部列出，符合 spec。

### P2.4 — `## Round Counter & Context Bridge` 段（adversarial-review.md）

- **段存在**：行 46 起。
- **review_type 固定为 `codex_adversarial_review`**：行 47，简化了推导步骤。
- **round-bridge fence 注入**：行 50-62，内容与 review.md 对称（counter 文件路径硬写为 `codex_adversarial_review_round_counter.txt`），符合 spec。
- **Isolation constraints**：行 67-72，明确 `codex_adversarial_review` counter 不与其他 4 类共享。

### P2.5 — `## Polling Convention` 段（adversarial-review.md）

- **段存在**：行 87 起。
- **job id 写入 `codex_adversarial_review_active_jobs.txt`**：行 90-93，路径带 review_type 前缀，与 review.md 统一模式。
- **`Main session MUST poll job before consuming verdict`**：行 102，精确命中。
- **旧矛盾文本**：`Do not call BashOutput or wait for completion in this turn.`：**0 命中**。

### P2.6 — ForgeUE local override 头注释（adversarial-review.md）

- **"Five changes vs upstream"**：行 163，扩展了原有注释，3/4/5 项完整覆盖 spec P2.6 要求。

---

## 3. tests/unit/test_codex_command_markdown.py 逐项核查

测试文件新建（188 行），8 个 fence test：

| # | Test name | spec 场景 | 状态 |
|---|-----------|-----------|------|
| 1 | `test_review_default_background` | P2.2：含 `default background` + 不含旧 AskUserQuestion 二选一文本 | PASS |
| 2 | `test_adversarial_always_background` | P2.2：adversarial 永远 background，不含旧 AskUserQuestion 二选一文本 | PASS |
| 3 | `test_round_counter_reference_section_exists` | P2.4：两个模板含 `## Round Counter & Context Bridge` | PASS |
| 4 | `test_review_type_5_enumeration_present` | P2.3 W1：5 类 `codex_*_review` 字符串全部在场 | PASS |
| 5 | `test_review_type_counter_isolation` | P2.3 W1：5 个独立 counter 路径 `notes/<rt>_round_counter.txt` 全部在场 | PASS |
| 6 | `test_polling_convention_section_exists` | P2.5 W4：两个模板含 `## Polling Convention` | PASS |
| 7 | `test_no_do_not_call_bashoutput_text` | P2.5 W4：旧矛盾文本 0 命中 | PASS |
| 8 | `test_polling_must_directive_present` | P2.5 W4：含 `Main session MUST poll job before consuming verdict` | PASS |

**实测结果**：`pytest -q tests/unit/test_codex_command_markdown.py` → `8 passed in 0.08s`

**全套 regress**：`pytest -q` → `1481 passed, 1 skipped in 49.14s`（1 skip = Windows symlink admin 权限限制，与本 change 无关，pre-existing）

---

## 4. 实施者两项单方面决策审计

### 决策 A：fence test 精确匹配字符串 `use \`AskUserQuestion\` exactly once with two options`

**规范要求**（tasks.md P2.7 原文）：`不含旧 AskUserQuestion exactly once 字符串`

实施者解释：旧 upstream 的完整字符串是 `use \`AskUserQuestion\` exactly once with two options`，单纯匹配 `AskUserQuestion` 过于宽松（会错误命中注释和禁止语，如 `Do NOT use AskUserQuestion...`）。

**独立验证结论**：
- 读取 `~/.claude/plugins/cache/openai-codex/codex/1.0.4/commands/review.md` 上游 plugin 原文，第 31 行：`- Then use \`AskUserQuestion\` exactly once with two options, putting the recommended option first and suffixing its label with \`(Recommended)\`:`
- 实施者使用的精确字符串 `use \`AskUserQuestion\` exactly once with two options` **完全匹配上游原文**，是旧逻辑的唯一标志性文本。
- 现有文件中 `AskUserQuestion` 的所有 8 处出现均为"禁止使用"说明或 changelog 注释，无一为旧逻辑路径，测试精确匹配**不存在弱化风险**。
- **判定：精确匹配决策正确，语义更准确，非弱化。**

### 决策 B：修改 `allowed-tools` frontmatter 移除 AskUserQuestion

**规范描述**：P2.2 要求移除 AskUserQuestion 调用路径（"不弹 AskUserQuestion"），P2.7 要求 test 检查 `不含旧 AskUserQuestion exactly once 字符串`。P2 task 未明确提 `allowed-tools` frontmatter 修改。

**独立验证**：
- 上游 plugin `allowed-tools` 原含 `AskUserQuestion`，commit c6913ae diff 行 4 从 `AskUserQuestion` 移除。
- `allowed-tools` 是 Claude Code 技术级 capability 声明，列出 `AskUserQuestion` 意味着命令被赋予弹框权限。若移除调用路径但保留 tool 声明，存在残留权限风险（未来 regression 更难发现）。
- P2.2 的契约意图（default background = no AskUserQuestion path）隐含要求权限声明一致：allowed-tools 保留 `AskUserQuestion` 与"Do NOT use AskUserQuestion"指令互相矛盾。
- commit message 明确记录了这一修改：`Both: remove AskUserQuestion from allowed-tools frontmatter`，不是隐藏变更。
- **判定：属于 P2.2 目标的隐含必要结果，非 scope creep。allowed-tools 声明与执行路径应保持一致，移除合理。**

---

## 5. 总体 Verdict

**aligned_with_contract: true**

P2.1-P2.8 全部任务逐项通过核查：

| Task | 描述 | 状态 |
|------|------|------|
| P2.1 | 读取 review.md（ForgeUE 本地已有 override） | 已完成（commit 前置工作） |
| P2.2 | Execution mode 默认 background + 3-AND gate + 无 AskUserQuestion | ✅ 符合规范 |
| P2.3 | 5 类 review_type 枚举 + 独立 counter/evidence 命名 | ✅ 符合规范 |
| P2.4 | `## Round Counter & Context Bridge` 段（两文件） | ✅ 符合规范 |
| P2.5 | `## Polling Convention` 段 + 矛盾文本移除 + MUST directive | ✅ 符合规范 |
| P2.6 | ForgeUE local override 注释扩展至 5 项变更 | ✅ 符合规范 |
| P2.7 | 8 个 fence test 全覆盖规范 scenario | ✅ 符合规范 |
| P2.8 | `pytest -q tests/unit/test_codex_command_markdown.py` 8 passed | ✅ 实测验证 |

两项单方面决策均属合理判断，无 scope creep，无 spec 弱化。

---

**Audit note (2026-05-05 simplified protocol)**: This evidence's frontmatter was migrated from `claude_codex_concurred` + Pre-P0 round 1 codex_review_ref to default `claude_autonomous` after user simplified D-AutonomyBoundary protocol. Routine implementation step does not require codex hop verification under simplified protocol; original Pre-P0 round 1 ref is for propose stage scope (S2), not implementation stage (S4). See `feedback_autonomy_boundary_simplified` saved memory + design.md D-AutonomyBoundary 2026-05-05 simplification.
