## ADDED Requirements

### Requirement: Codex review default background dispatch policy

`/codex:review` 与 `/codex:adversarial-review` 命令模板 SHALL default 到 background 模式分发,仅当**全部三个条件同时满足**时才走前台 wait 路径:

- 变更范围 ≤ 2 files **且** 总 diff ≤ 50 lines(`git diff --shortstat` / `git diff --shortstat --cached` 实测)
- 调用模式非 `adversarial-review`(adversarial 永远 background)
- main session 下一动作必须依赖 review 结果(由 controller 显式判断)

命令模板 SHALL 保留 `--wait` / `--background` 显式 flag 作为用户 override 通道,显式 flag 优先于 size estimation。

#### Scenario: 大 scope 变更默认走 background

- **WHEN** 用户 invoke `/codex:review` 且当前 working tree `git diff --shortstat` 显示 ≥ 3 files 或 ≥ 51 lines
- **THEN** 命令直接走 background 路径(`Bash(..., run_in_background: true)`),不弹 `AskUserQuestion`
- **AND** main session 在下一次需要 codex 输出前 SHALL 主动 BashOutput 拉结果

#### Scenario: 极小 scope 变更走前台 wait

- **WHEN** 用户 invoke `/codex:review` 且 working tree ≤ 2 files **且** ≤ 50 lines diff **且** 非 adversarial-review **且** controller 判定下一动作必须等结果
- **THEN** 命令走前台 wait 路径,foreground node 调用 codex-companion.mjs
- **AND** 不弹 `AskUserQuestion` 二选一

#### Scenario: adversarial-review 永远 background

- **WHEN** 用户 invoke `/codex:adversarial-review`(无论 scope 大小)
- **THEN** 命令走 background 路径
- **AND** 不弹 `AskUserQuestion`

#### Scenario: 显式 flag override

- **WHEN** 用户 invoke `/codex:review --wait`(显式要求前台)
- **THEN** 命令走前台 wait,忽略 size estimation 默认
- **AND** 不弹 `AskUserQuestion`

#### Scenario: background launch 必须 capture job id(W4 writeback codex round 1 F4 finding)

- **WHEN** 命令走 background 路径(D-DefaultBackground default 或 `--background` 显式)
- **THEN** job id SHALL 从 codex-companion.mjs stdout 第一行 `Codex review started in the background. Job id: <id>` 解析并写入 `notes/<review_type>_active_jobs.txt`(per change_id)
- **AND** 命令模板告知 main session "Run `/codex:status --wait <job>` and `/codex:result <job>` to consume verdict"

#### Scenario: 未获取 codex result 不得写 concurred evidence(W4 writeback)

- **WHEN** Claude 计划在 evidence frontmatter 写 `autonomy_decision: claude_codex_concurred` + `codex_review_ref: <path>`
- **THEN** controller MUST 先 `/codex:status --wait <job>` 确认 job done **且** `/codex:result <job>` 拿完整 output 落 evidence
- **AND** 若 ref evidence 未 finalize(round counter 未 increment / `disputed_open != 0` / `verdict` 字段缺)→ MUST 改为 `autonomy_decision: user_required` 升级到用户

#### Scenario: 命令模板移除 "Do not call BashOutput" 矛盾文本(W4 writeback)

- **WHEN** 静态扫 `.claude/commands/codex/{review,adversarial-review}.md`
- **THEN** **不**含字符串 `Do not call BashOutput or wait for completion in this turn.`(原 plugin upstream text,与 default background 协议冲突)
- **AND** 含字符串 `Main session MUST poll job before consuming verdict via /codex:status --wait + /codex:result.`(替换文本)

### Requirement: Codex multi-round review same-subject context bridge

Codex 同 `change_id` + 同 `review_type` 的多轮 review 中,round N+1 (N≥1) prompt SHALL 自动注入对 round N evidence 文件的 read 引用,使 codex 在 review 前理解上轮 verdict。**仅 same-task / same-change scope 共享上下文**,跨 task / 跨 change 绝不共享。

实装路径:
- Round 1 codex review 输出 SHALL 落 `openspec/changes/<change_id>/notes/codex_<review_type>_review_round1.md`
- Round 2+ codex review prompt SHALL 包含 fence:`本次 review 是 round {N+1}(继承 round {N} verdict)。**强制要求**:开始 review 前 MUST 先读 openspec/changes/<change_id>/notes/codex_<review_type>_review_round{N}.md`
- Round counter 状态 SHALL 落 `notes/codex_<review_type>_round_counter.txt`(每个 review subject 一份,sticky)

约束:
- Round 1 不引用任何上轮(无前置)
- Round N+1 仅引用直接前驱 round N(不引用 round N-1 / N-2)
- 跨 `change_id` 不共享(change A round 1 verdict 不进 change B 任何 round)
- 跨 `review_type` 不共享(同 change 内 design_review round 1 verdict 不进 plan_review round 1)

#### Scenario: round 1 review 不注入任何上轮 reference

- **WHEN** 用户 invoke `/codex:review` 且 `notes/codex_<review_type>_round_counter.txt` 不存在或读出 0
- **THEN** prompt 不包含 round-bridge fence
- **AND** round counter 写入 1
- **AND** codex output 落 `notes/codex_<review_type>_review_round1.md`

#### Scenario: round 2 review 自动注入 round 1 reference

- **WHEN** 用户 invoke `/codex:review` 且同 change_id + 同 review_type 的 round counter 读出 1
- **THEN** prompt 首段包含 fence:`本次 review 是 round 2(继承 round 1 verdict)。**强制要求**:开始 review 前 MUST 先读 openspec/changes/<change_id>/notes/codex_<review_type>_review_round1.md`
- **AND** round counter 增到 2
- **AND** codex output 落 `notes/codex_<review_type>_review_round2.md`

#### Scenario: 跨 change 不共享上下文

- **WHEN** change A 完成 round 1 review 落 `notes/codex_<type>_review_round1.md` + counter=1,然后用户在 change B 第一次 invoke `/codex:review`
- **THEN** change B prompt 不包含 change A round 1 reference
- **AND** change B counter 从 1 起记(独立)
- **AND** change A counter 文件不被 change B 修改

#### Scenario: bridge violation 检测

- **WHEN** round 2 codex output 中 raise 与 round 1 已 accepted finding 重叠的问题但无 `(承 round1-FN)` tag
- **THEN** controller SHALL 在 evidence frontmatter 标注 `bridge_violation: true`
- **AND** controller 评估是否 retry round 2 或升级 D-AutonomyBoundary fence #3(review 冲突)

### Requirement: Workflow autonomy boundary fence

ForgeUE Integrated AI Change Workflow controller(Claude main session) SHALL 默认走自主路径执行 routine workflow step,但 6 类 boundary 触发时 MUST 升级到用户拍板:

1. **不可逆操作** — `git push` / `git push --force` / archive change(`mv openspec/changes/<id> archive/`)/ `git reset --hard` / `git branch -D` / 删除非 `/tmp/` 临时文件 / `git commit --amend` 已 push 的 commit
2. **跨 change 决策** — 修改非本 change scope 的 D-decision / 修改其他 active change 的 contract artifact / 删除其他 change 的 evidence 文件
3. **Claude+Codex review verdict 冲突** — verdict 不一致(blocker vs non-blocker)/ severity 评估不一致(critical vs minor)/ 推荐方向相反
4. **用户先验显式约束** — `~/.claude/CLAUDE.md` / project `CLAUDE.md` / `MEMORY.md` 内 explicit fence rule 触发场景
5. **钱** — 任何 vendor API paid call(ADR-007 边界:Hunyuan3D / Tripo3D / 远端付费 LLM live 调用 / `--live-llm` flag dispatch)
6. **Secret / 安全** — `.env` 写入 / `*api_key*` / `*credential*` / `*secret*` 文件操作 / mock production credentials 写文件系统

每条 implementation evidence frontmatter MUST 含 `autonomy_decision` 字段,枚举:
- `claude_autonomous` — 完全自主(无 codex 验证的极小 step)
- `claude_codex_concurred` — Claude + Codex 一致 → 自主执行
- `user_required` — 边界 fence 触发 / Claude+Codex 冲突 → 用户拍板
- `user_overrode` — 用户主动否决 Claude 推荐

`autonomy_decision: claude_codex_concurred` 字段值 MUST 配套 `codex_review_ref` 字段(指向具体 round N evidence 文件)。

`forgeue_finish_gate.py` SHALL 含 `_check_autonomy_boundary` fence 守门 evidence frontmatter `autonomy_decision` 字段必填且值合法。

#### Scenario: routine step Claude 自主执行

- **WHEN** Claude 提案修改 evidence file + invoke `/codex:review` background + Codex verdict 与 Claude 一致(都 accept 或都 reject)
- **THEN** Claude 直接执行修改不弹 `AskUserQuestion`
- **AND** evidence frontmatter 写入 `autonomy_decision: claude_codex_concurred` + `codex_review_ref: notes/codex_<type>_review_roundN.md`

#### Scenario: 不可逆操作必须用户授权

- **WHEN** Claude 计划走 `git push origin dev` / `archive change` / `git reset --hard`
- **THEN** Claude MUST 先用 `AskUserQuestion` 请求授权
- **AND** evidence frontmatter 标 `autonomy_decision: user_required`

#### Scenario: Claude+Codex verdict 冲突升级用户

- **WHEN** Claude 推荐 accept finding F1,Codex review 推荐 reject F1(verdict 不一致)
- **THEN** Claude MUST 弹 `AskUserQuestion` 列出冲突的 verdict + 推荐 + Codex reasoning
- **AND** 等用户拍板后再继续
- **AND** evidence frontmatter 标 `autonomy_decision: user_required` + `conflict_summary: <one-line>`

#### Scenario: vendor API paid call 必须用户授权

- **WHEN** Claude 计划走 `--live-llm` 启 mesh.generation / Hunyuan3D / Tripo3D / 任何 vendor API paid call
- **THEN** Claude MUST 用 `AskUserQuestion` 列出预估 cost + provider + 失败回退
- **AND** evidence frontmatter 标 `autonomy_decision: user_required`

#### Scenario: secret 文件操作必须用户授权

- **WHEN** Claude 计划写入 `.env` / `*api_key*` / `*credential*` / `*secret*` 类文件
- **THEN** Claude MUST 用 `AskUserQuestion` 请求授权(包括 read-and-update)
- **AND** evidence frontmatter 标 `autonomy_decision: user_required`

#### Scenario: finish_gate 守门 autonomy_decision 字段(W2 writeback 加深 ref 硬校验)

- **WHEN** `forgeue_finish_gate.py` 扫描 `execution/` / `review/` / `verification/` 内 evidence frontmatter
- **THEN** 任意 evidence 缺 `autonomy_decision` 字段 → exit 非 0 + 错误指明缺字段的 evidence 文件
- **AND** `autonomy_decision: claude_codex_concurred` 缺 `codex_review_ref` → exit 非 0
- **AND** `autonomy_decision` 值不在合法枚举内 → exit 非 0
- **AND** `claude_codex_concurred` 配套 `codex_review_ref` 路径不存在(`(change_root / codex_review_ref).is_file() == False`)→ exit 非 0
- **AND** `codex_review_ref` 跨 change(不在当前 change_root 下,如 ref `archive/<other>/notes/...`)→ exit 非 0
- **AND** `codex_review_ref` 自身 frontmatter `evidence_type` 不在 `{codex_adversarial_review, codex_design_review, codex_plan_review, codex_verification_review, codex_mixed_scope_review}` 之一 → exit 非 0
- **AND** `codex_review_ref` 自身 frontmatter `disputed_open != 0`(round 未 finalize)→ exit 非 0

#### Scenario: verdict normalization 判定 conflict(W3 writeback codex round 1 F3 finding)

- **WHEN** controller 准备写 `autonomy_decision: claude_codex_concurred` evidence,先调用 `_check_verdict_normalization(claude_resolution_list, codex_top_verdict, codex_findings)` helper
- **THEN** 按 design.md `D-FenceTaxonomy` Fence #3 Verdict Normalization 8 row 表 + 2 个 per-finding 维度判定 conflict
- **AND** 不冲突路径(`approve` × `accepted-codex` / `approve` × `accepted-claude` / `approve` × `rejected` / `needs-attention` × `accepted-codex`)→ 自主路径,写 `claude_codex_concurred`
- **AND** 冲突路径(`approve` × `disputed-open` / `needs-attention` × `accepted-claude` / `needs-attention` × `rejected` / `needs-attention` × `disputed-open` / 任何 finding `severity ∈ {critical, high}` × Claude `rejected` / writeback diff 与 codex 推荐方向相反)→ 升级 fence #3 用户,写 `user_required`
