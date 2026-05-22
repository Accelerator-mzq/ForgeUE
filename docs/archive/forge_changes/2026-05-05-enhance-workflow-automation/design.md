## Context

ForgeUE Integrated AI Change Workflow 自 2026-04-27 启用,经 `fuse-openspec-superpowers-workflow` + `adopt-subagent-driven-development` 两轮 change 沉淀,工作流闭环已完整(S0-S9 状态机 / 9 个命令 / 12-key audit frontmatter / 4 类 DRIFT / Documentation Sync Gate / Finish Gate)。但运行实证暴露三类自动化短板:

1. **Codex review 默认 wait/background 二选一**:`/codex:review` / `/codex:adversarial-review` 命令模板内嵌 `AskUserQuestion` 强制问用户,即使 review scope 已被 `git diff --shortstat` 实测分级(`adversarial-review` 命令模板 line 47-58 显式说 "in every other case, including unclear size, recommend background"),仍要用户点 OK。本 change 实施期间 codex 单 review 平均 90 秒,前台 wait 90 秒 × 7 轮 = 10 分钟纯等候。

2. **Codex 多轮 review 跨 session 失忆**:`adopt-subagent-driven-development` change 实施期间出现 F8 round 2 false-positive — round 1 codex 已 raise 然后 accepted-codex 缩小 keyword 边界,round 2 codex 重新 raise 同款问题(severity 高,看似 blocker 实则已解决)。原因:codex CLI 每次 invoke 起独立 session,无 prior round verdict context,看到当前 code 状态会重提"看起来是问题"的 finding。

3. **决策权过度上行到用户**:本 change 实施过程统计 25+ 次 "按你推荐的执行,给你授权"(Pre-P0 阶段 1 次 / 5 task 各 ~3 次 / S6 review 阶段 5 次 / S7 doc sync 2 次 / S8 finish gate 2 次 / S9 archive 2 次 / push 1 次 + 各种 sub-decision 等)。其中真正涉及"用户判断与 Claude 推荐不一致"的只有 ~3 次(选 II Round 2 严格 dogfood / 选 Option C tags-aware skip / 选 (III)+(IV) Layer 6 verification combo)— 其余 ~22 次为 rubber-stamp。

**本 change 不动 Superpowers SKILL.md 协议**(沿 D-SkillInvoke `adopt-subagent-driven-development` 决议),仅在 ForgeUE 命令模板层 + finish_gate fence 层降级 user input 频率。

**Stakeholders**:
- ForgeUE 主 user(msc)— 负担方
- Claude(执行方)— 自主权扩展
- Codex(reviewer)— 上下文桥接受益方

## Goals / Non-Goals

**Goals:**
- G1:Codex review 默认 background 模式,size estimation 边界判定明确(避免误判)
- G2:Codex 多轮 same-subject(同 change_id + 同 review type)round N→round N+1 自动注入 round N verdict reference,不跨 task / 不跨 change
- G3:Claude 默认拍板 + 自动 codex 二次验证;Claude+Codex 一致 → 直接执行;6 类 boundary fence 必须升级到用户
- G4:`forgeue_finish_gate.py` 加 `_check_autonomy_boundary` fence 守门 evidence frontmatter `autonomy_decision` 字段
- G5:9 个 forgeue 命令模板 + 2 个 codex 命令模板 加 Decision Delegation section
- G6:文档同步覆盖 11 处(沿 adopt-subagent-driven-development 同款)

**Non-Goals:**
- 不引入 codex CLI session continuation 协议(`--continue` 未确认 plugin 支持;采用文件 reference 路径)
- 不修改 ADR-007 vendor API 双扣保护(D-AutonomyBoundary fence #5 钱 = ADR-007 边界复用)
- 不动 Superpowers SKILL.md 内部协议(prompt template / dispatch flow 仍 Superpowers 自管)
- 不接入 brainstorming(留 follow-on `add-forgeue-brainstorm-stage`)
- 不实现 cross-change context bridge(明确禁止跨 change 共享 codex 上下文)
- 不重写既有 26 examples-and-acceptance Requirement(纯 ADD)

## Decisions

### D-DefaultBackground:Codex review 默认 background dispatch

**Statement**:`/codex:review` / `/codex:adversarial-review` 默认 background 模式。仅当**全部 3 条满足**时才前台 wait:
1. 变更 ≤ 2 files **且** 总 diff ≤ 50 lines(`git diff --shortstat` / `git diff --shortstat --cached`)
2. 非 `adversarial-review` 模式(adversarial 永远 background — 涉及挑战式深度分析)
3. main session 下一动作必须等 review 结果(由 controller 判断,如 round 1 finding 决定是否需要 round 2)

**Alternatives considered:**
- (a) Always background — 简单但极小 scope 浪费 +1 turn 拉结果
- (b) Always wait — 沿现状,大 scope 阻塞 main session
- (c) Size-based + 边界 fence — **选用**,平衡延迟与并行性

**Why (c):**
- 大 scope review(如本 change 整体 adversarial)前台 wait 90+ 秒,主 session 无法并行准备 cross-check 表 / writeback 草稿 / 下一 task context — 浪费明显
- 极小 scope review(单文件 typo fix)启 background 后还要 BashOutput 拉结果,延迟反而增加
- 边界明确(2 files / 50 lines / 非 adversarial)→ 误判风险低,降级到默认 background 路径不会显著伤害 UX

**Tradeoff:**
- (+)平均单 change codex review 总等候时间从 ~10 分钟降到 ~30 秒(BashOutput 总和)
- (+)main session 上下文连贯,Claude 可在 codex 跑时并行编辑 evidence
- (-)size estimation 逻辑增加复杂度;边界判定 fail 时回退路径需要(沿现 `--wait` / `--background` flag,user 仍可显式 override)
- (-)BashOutput 拉结果时机 — Claude 必须主动检查;若忘记 wait 完成,可能 race condition(先用 round 1 verdict,但 round 1 还没产出)

**Mitigation**:codex 命令模板加 `## Polling Convention` — 启动 background 后 main session 必须在下一次需要 codex 输出前 BashOutput / Monitor。

### D-CodexContextBridge:同 review subject 多轮 round N→round N+1 文件 reference

**Statement**:Codex 同 `change_id` + 同 `review_type` 的 round N→round N+1,自动在 round N+1 prompt **首段** 注入:

```
本次 review 是 round {N+1}(继承 round {N} verdict)。
**强制要求**:开始 review 前 MUST 先读 `openspec/changes/<change_id>/notes/codex_<scope>_review_round{N}.md`,
理解上轮已 raise + accepted/rejected 的 finding 与 Claude 决议,避免重复 raise 已解决问题。
若有引用上轮 finding ID(F1/F2/...),请显式标记 `(承 round{N}-FN)`。
```

**约束**:
- **同 change_id only** — 跨 change(如 change A round 1 → change B round 1)绝不共享
- **同 review_type only** — 同 change 内 design_review round 1 与 plan_review round 1 不共享(review subject 不同)
- **直接前驱 only** — round N+1 仅引用 round N(不引用 round N-1 / N-2);避免 prompt 膨胀

**Round counter 状态**:落在 `notes/codex_<review_type>_round_counter.txt`(每个 review subject 一份,sticky 跨 controller session)。Round 1 不引用任何上轮(无前置)。

**Alternatives considered:**
- (a) round N+1 prompt 完整 paste round N finding 表 — 直观但 prompt 重(round N findings 可能 N×K char)+ controller 也要存这份历史
- (b) `codex --continue <session-id>` — 依赖 codex CLI plugin 内部 session 持久化(未确认 v1.0.4 支持;codex-companion.mjs broker 看不到 session-id 暴露接口)
- (c) 文件 reference 路径(round N 落 `notes/codex_<scope>_review_round{N}.md`,round N+1 prompt 加 read 引用)— **选用**,沿现 evidence 流不引入新依赖

**Why (c):**
- round 1 evidence 本来就在 `notes/codex_*_review_round{N}.md`(沿 adopt-subagent-driven-development F8 round 2 sequence 已确认 evidence 落地命名约定)
- 不依赖 codex CLI 内部 state — 任何 codex version 都支持 `Read tool` first 行为
- prompt 增量小(2-3 行 fence + 文件路径),不污染 controller 上下文

**Tradeoff:**
- (+)解决 F8 类 false-positive(round 2 重提 round 1 已 accepted finding)
- (+)零依赖外部 plugin 协议
- (-)依赖 codex 实际遵守"先读文件再 review"指令;若 codex 直接 start review without reading,bridge 失效
- (-)需要 prompt 模板 explicit fence("MUST first read ... before raising any finding")

**Mitigation**:
- 在 codex round N+1 输出 verification 阶段(controller 收到 codex output 后),Claude 检查输出是否引用 `(承 round{N}-FN)` 格式 tag;若 round N+1 raise 与 round N 重叠 finding 但无 `承` tag → flag 为 "bridge violation",controller 决定是否 retry
- Round 1 → Round 2 实测后(本 change 自身 dogfood 期间)若 violation 率 > 30%,降级到 (a) paste 路径

### D-AutonomyBoundary:Claude 默认自主 + 简化 6 类升级 fence(2026-05-05 user feedback simplification)

**Statement**:Claude 默认按推荐自主执行;不再 ping-pong codex review verdict 作 fence 触发。仅以下 6 类必须升级用户。

**自主路径**(default,不弹 `AskUserQuestion`):
1. Claude 提案 + 推荐方案
2. 可选 codex review(D-DefaultBackground 选 background)— 仅作 second opinion 参考,**不影响默认拍板**
3. Claude **独立 verify** codex finding(不附和 / 不重提)→ 生成 verdict 矩阵
4. 写 evidence,frontmatter `autonomy_decision: claude_autonomous`(routine)或 `claude_codex_concurred`(显式 codex 二次验证 + 一致)

**6 类必须升级用户的 boundary fence**(2026-05-05 user feedback simplification — 原 fence #3 "Claude+Codex review 冲突" 已删除,替换为 framework / design.md mismatch 边界):
1. **不可逆操作** — `git push` / `git push --force` / `archive change`(`mv openspec/changes/<id> archive/`)/ `git reset --hard` / `git branch -D` / `rm <非临时文件>` / `git commit --amend`(已 push 的 commit)
2. **跨 change 决策** — 修改非本 change scope 的 D-decision / 修改其他 active change 的 contract artifact / 删除其他 change 的 evidence
3. **框架修改(framework modification)** — 修改 D-decision content / fence taxonomy / autonomy 协议自身 / Superpowers 集成边界 / codex 集成边界 / S0-S9 状态机定义
4. **design.md 不匹配(design.md mismatch)** — 实施暴露的 contract 漏洞与 design.md text 矛盾(原 4 类 DRIFT 中的 `evidence_contradicts_contract` / `evidence_introduces_decision_not_in_contract` / `evidence_exposes_contract_gap` 类)
5. **钱** — 任何 vendor API paid call(ADR-007 边界:Hunyuan3D / Tripo3D / 远端付费 LLM live 调用 / `--live-llm` flag 解锁的 dispatch)
6. **Secret / 安全** — 涉及 `.env` / API key / `*credentials*` / `*secret*` 文件 / mock production credentials 写入文件系统

(原 fence "用户先验显式约束" 隐含到 memory 触发 — Claude controller 每 step 主动 read MEMORY.md / `<feedback>` saved memory + 遵守;不作为独立 fence list 项,但效果等价)

`autonomy_decision` 枚举(2026-05-05 简化):
- `claude_autonomous` — **default**(routine step / Claude 独立 verify codex finding 后拍板)
- `claude_codex_concurred` — 显式 codex 二次验证 + 一致(可选 verify path,不强制)
- `user_required` — 6 类 fence 触发(framework / design mismatch / 不可逆 / 跨 change / 钱 / 安全)
- `user_overrode` — 用户主动否决 Claude 推荐(rare)

**Alternatives considered:**
- (i) 全自动 Claude(无 codex 验证 + 无 user fence)— 最快但错误归因责任完全在 Claude 一方;Layer 6 finding 揭示用户 deeper review 是必要的最深 layer,完全省略 user 不安全
- (ii) 全人工(沿现状)— 进度噪声大,本 change 已实证 25+ 次 rubber-stamp
- (iii) **2026-05-05 user feedback** — Claude 自主 + 简化 6 fence(framework / design mismatch + 不可逆 / 跨 change / 钱 / 安全)— **选用**;原 (iii) "6 fence 含 codex 冲突" 在 user feedback 后 evolved

**Why (iii v2):**
- 本 change 实证 25+ 次问询,~88% rubber-stamp(22/25),自动化空间巨大
- User feedback (2026-05-05) 强调 "大部分选择按你推荐的方案就行";Claude+Codex review 冲突作为升级 trigger 实践中触发率低,但 codex hop 本身慢,给 user 体感是 ping-pong
- 6 fence 简化版覆盖真正的 high-cost 错误源(不可逆 / 跨 change / framework / 钱 / 安全)+ design.md 一致性边界
- Codex review 退化为可选 second opinion;Claude 独立 verify 拍板默认路径

**Tradeoff:**
- (+)user 问询从 25+ → 5-10 次(仅 6 类 fence 触发,且不再走 codex hop)
- (+)main session token 节省(不必 sync 等 codex BashOutput)
- (-)Claude 独立 verify 责任更重 — 共谋失败时 user 错过早期 catch 机会(Layer 6 finding 揭示);mitigation:framework / design.md 修改强制升级,这是最高 leverage 的 catch 点
- (-)`claude_autonomous` 大量场景使用,需要 finish gate 不再强制 `codex_review_ref` 字段(已 reflect in spec.md scenario)

**Mitigation:**
- evidence frontmatter `autonomy_decision: claude_autonomous` 不强制 `codex_review_ref`(默认路径不需要 codex hop)
- evidence frontmatter `autonomy_decision: claude_codex_concurred` 仍必须配 `codex_review_ref` 字段(显式 codex verify path)
- 每条 implementation evidence 必须填 `autonomy_decision`(self-host bootstrap exemption 同 D-SelfHost 模式)
- 后续 change 若发现共谋失败 / framework 漂移可补充 fence — 本 change 不预设全部边缘 case,留迭代空间

### D-FenceTaxonomy:6 类 fence 的具体 trigger 字符串(实装层 — 2026-05-05 简化)

**Statement**:每个 forgeue / codex 命令模板的 `## Decision Delegation` section 显式列出 trigger keyword,供 Claude controller scan 自身意图时匹配。

| Fence # | Trigger keyword(命令意图层)| 触发示例 |
|---|---|---|
| 1 不可逆 | `git push` / `archive` / `git reset --hard` / `git branch -D` / `rm <not /tmp/>` / `commit --amend` | "推到 origin" / "归档 change" / "强制重置" |
| 2 跨 change | `修改 D-<id>` 且 `<id>` 不在当前 active change scope / `修改 archive/<other>/` | "改 ADR-007 协议" / "动 fuse-openspec contract" |
| 3 framework modification | `修改 D-decision content` / `加新 fence` / `改 autonomy 协议` / `改 fence taxonomy` / `改 Superpowers 集成边界` / `改 codex 集成边界` / `改 S0-S9 状态机` | "改 D-AutonomyBoundary fence list" / "加新 D-decision" / "改 Superpowers SKILL.md 协议" |
| 4 design.md mismatch | 实施暴露 contract 漏洞与 design.md text 矛盾(原 4 类 DRIFT 子集:`contradicts_contract` / `introduces_decision_not_in_contract` / `exposes_contract_gap`) | "实施添加了 design.md 没说的字段" / "实施行为与 design.md 表 row N 矛盾" |
| 5 钱 | `--live-llm` / `paid call` / `mesh.generation` / `Hunyuan3D` / `Tripo3D` / vendor API key 实际拨号 | "开 live mesh smoke" / "拨 hunyuan API" |
| 6 安全 | `.env` 写入 / `*api_key*` / `*credential*` / `*secret*` 文件操作 | "更新 .env" / "落 API key 配置" |

(原 fence #3 "Claude+Codex review 冲突" 在 2026-05-05 user feedback 后 **删除**;Claude 独立 verify codex finding 后自主拍板,不再升级用户作中间裁判)

(原 fence #4 "用户先验显式约束" 隐含到 memory read 行为 — Claude controller 每 step 主动 read MEMORY.md / `<feedback>` saved memory + 遵守;不作为独立 fence trigger,但效果等价)

Claude controller 在每个 step 自检意图时 grep 自身计划描述,任意 hit → 升级用户。

**可选 Verdict Normalization(原 fence #3 — 2026-05-05 user feedback 后 deprecated 作 fence trigger;helper 保留作 controller 可选工具)**:

> **协议变更**(2026-05-05):原 fence #3 "Claude+Codex review verdict 冲突 → 升级用户" 已**删除**。Codex review 退化为可选 second opinion;Claude 独立 verify 后自主拍板。`_check_verdict_normalization` helper 仍保留(P0 已实装 + 测试覆盖),但**不再作为 finish_gate fence enforcement**;controller 可显式调用作 second opinion 工具,不影响默认 `claude_autonomous` 路径。
>
> 下表保留作历史参考(W3 writeback codex round 1 F3 finding 的实装映射):

Codex round N 输出顶层 `verdict ∈ {approve, needs-attention}`,Claude cross-check `## B Matrix` 给每个 finding 一个 `resolution ∈ {accepted-codex, accepted-claude, rejected, disputed-open}`。两层 schema 不可直接字符串比较(原 F3 finding `accept != reject` 字面匹配会在 90% 正常流程误报)。冲突判定按下表归一化映射:

| Codex top-level verdict | Claude resolution(任一 finding 行)| 判定 | 推荐操作 |
|---|---|---|---|
| `approve` | `accepted-codex` | 不冲突(双方都 OK)| Claude 自主 → `claude_codex_concurred` |
| `approve` | `accepted-claude` | 不冲突(Claude 接 codex 推荐 + 主动改进)| 自主 → `concurred` |
| `approve` | `rejected` | 不冲突(Claude 拒绝接 codex 提议但 codex 顶层批准)| 自主 → `concurred` |
| `approve` | `disputed-open` | **冲突**(codex OK 但 Claude 觉得有问题未解决)| 升级 fence #3 用户 |
| `needs-attention` | `accepted-codex` | 不冲突(Claude 接 codex finding)| 自主 + writeback → `concurred` |
| `needs-attention` | `accepted-claude` | **冲突**(意见相反:codex 觉得有问题但 Claude 否决 codex finding)| 升级 fence #3 用户 |
| `needs-attention` | `rejected` | **冲突**(Claude 拒绝接 finding 但 codex 持续推 verdict needs-attention)| 升级 fence #3 用户 |
| `needs-attention` | `disputed-open` | **冲突**(双方 unfinalized)| 升级 fence #3 用户 |

**Per-finding 维度归一化**(顶层 verdict 一致仍可能冲突的边缘 case):
- 若 codex finding `severity ∈ {critical, high}` 且 Claude resolution `rejected` → 冲突 + 升级(高优先 finding 不接受拒绝)
- 若 codex finding 推荐方向(text "MUST add X")与 Claude writeback 实际改动方向相反(text "remove X")→ 冲突 + 升级(需要 Claude self-check writeback diff)

**实装层**:`_check_verdict_normalization` helper 解析 `codex_review_ref` evidence 的 frontmatter `verdict` + body 内 finding 列表 + cross_check `## B Matrix` 的 resolution 列,按上表 8 row + 2 个 per-finding 维度判定;表驱动测试覆盖全 8 个组合 row + 2 个 edge case。

## Risks / Trade-offs

- **R1**:**D-DefaultBackground size estimation 误判** → 大 scope 误判极小(前台 wait 阻塞)/ 极小 scope 误判大 scope(background 浪费)。**Mitigation**:命令模板保留 `--wait` / `--background` 显式 flag,用户可 override;边界 fence 含 3 条 AND 关系(2 files / 50 lines / 非 adversarial),误判窗口窄
- **R2**:**D-CodexContextBridge 文件 reference 不被 codex 遵守** → round N+1 重提 round N 已解决 finding。**Mitigation**:prompt 模板加 explicit `MUST first read ... before raising any finding`;controller 后置检查 `(承 round{N}-FN)` tag;若 violation 率 > 30%,降级到 (a) paste 路径
- **R3**:**D-AutonomyBoundary Claude+Codex 共谋失败** → 同 prompt bias 双盲(F8 round 2 实证)。**Mitigation**:对抗式 review 走 `/codex:adversarial-review` 而非 `/codex:review`(挑战式视角降低同盲风险);6 类 fence 涵盖 high-cost 错误源,共谋 routine step 失败损失可控
- **R4**:**Self-host bootstrap 期** → 本 change 实施期间 D-AutonomyBoundary fence 还没 land 命令模板,Claude 需要在 controller layer 临时遵守 fence(沿 D-SelfHost 模式)。**Mitigation**:Pre-P0 cross-check 内显式声明本 change 临时 fence(每条 implementation step 自检 6 类 trigger);archived 后 fence 直接走命令模板
- **R5**:**6 类 fence 列举式定义,边缘场景遗漏** — 不可逆 vs 部分可逆(如 `git revert` 是 reverse-able 但 history rewriting)?**Mitigation**:design.md 明确 fence 是"列举式 + 兜底"(任何 Claude 无 high confidence 判定的 step 默认升级用户);后续 change 迭代补充

## Migration Plan

**Phase 1 - propose / design / specs / tasks 落 contract**(本次 propose stage):
- 写 proposal.md / design.md / specs/examples-and-acceptance/spec.md(3 ADDED Requirement)/ tasks.md
- Pre-P0 codex adversarial review 挑战 D-AutonomyBoundary fence 完整性
- Pre-P0 plan_cross_check writeback(沿 self-host 模式)

**Phase 2 - 实装**(apply stage,subagent-driven-development):
- P0:`forgeue_finish_gate.py` 加 `_check_autonomy_boundary` fence + `autonomy_decision` 字段 enum + `tests/unit/test_forgeue_finish_gate.py` 守门测试
- P1:9 个 forgeue 命令模板加 `## Decision Delegation` section + `tests/unit/test_forgeue_command_markdown.py` fence
- P2:`.claude/commands/codex/{review,adversarial-review}.md` ForgeUE local override 改 size estimation 默认 background + round-N reference 注入逻辑 + `tests/unit/test_codex_command_markdown.py`(新建)守门
- P3:11 处文档同步(`docs/ai_workflow/forgeue_integrated_ai_workflow.md` §C 新增 / `docs/ai_workflow/README.md` / `docs/ai_workflow/forgeue_quickstart.md` / `CLAUDE.md` / `README.md` / `AGENTS.md` / `CHANGELOG.md` / `.claude/skills/forgeue-integrated-change-workflow/SKILL.md` / `openspec/specs/examples-and-acceptance/spec.md`)
- P4:Pre-P0 final review + Pre-P0 plan_cross_check writeback finalize

**Phase 3 - verify / review / doc-sync / finish**:
- S5 verify:Level 0/1/2 + codex S5 verification round
- S6 review:codex S6 mixed-scope review + writeback
- S7 doc sync:10 文档静态扫
- S8 finish gate:12-key frontmatter 全检 + cross-check disputed_open: 0 + autonomy_decision 字段全填
- S9 archive:`openspec archive --skip-specs` + manual sync openspec/specs/examples-and-acceptance/spec.md

**Rollback strategy**:每个 phase 落独立 commit,任意 phase 失败可 `git revert <commit>` 恢复;archive 前不动 main branch;archive 后 `git revert` archive commit + `git mv archive/<id> changes/<id>` 恢复 active 状态(沿现 OpenSpec workflow)。

## Open Questions

**OQ-1**:D-CodexContextBridge round counter 状态文件(`notes/codex_<review_type>_round_counter.txt`)是否应该 git-tracked?
- 倾向:**git-tracked**(evidence 一部分,审计需要;.gitignore 不加)
- 留 codex adversarial review 挑战

**OQ-2**:D-AutonomyBoundary fence #4 "用户先验显式约束" 的实装识别 — Claude 如何 reliably grep `<feedback>` saved memory 内 fence?
- 倾向:命令模板加 `## Pre-Execution Memory Scan` 段,Claude controller 每步 self-check 时 read `MEMORY.md` + relevant feedback file → keyword match
- 留 codex adversarial review 挑战

**OQ-3**:本 change archive 后,backporting 类似 fence 到既有已 archive change 是否必要?
- 倾向:**不必要**(archived change 不再修改,沿"归档即冻结"原则);但若 archived change 中有 contract artifact 触发后续 change 的 fence #2(跨 change 决策),Claude 仍需走 boundary
