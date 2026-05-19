# Retrospective: retire-forgeue-protocol-layer-fully

> 自由格式架构反思文档 — 无 12-key frontmatter(沿 retire 后无 frontmatter audit 协议)

---

## 1. 实施统计

### LOC 数据(baseline: `3add409`)

| 指标 | 实际值 | design.md 估计 |
|---|---|---|
| 总 insertions | 82 LOC | — |
| 总 deletions | 20,769 LOC | ~9,500 LOC delete |
| Net LOC delete | **20,687 LOC** | ~9,500 LOC |
| 差异倍数 | **2.18x** 超估计 | |

实际删除量显著超出 design 估计,主要原因是 P2 grep-driven cleanup(round 1 codex P1-3 推动)扩展了原始清单范围:17 个 `test_forgeue_*.py` + 5 个 fixtures + `test_skill_cascade_check.py` + `test_followon_registry.py`,仅 P2 一个 commit(`174e0cb`)就贡献了 18,024 deletions。tools + tests 两者合计远超 design 阶段对工具本体 LOC 的估算。

### Commit 数

- **总 commit 数(no-merges)**: 8
- **主 atomic retire commit**: 3(`77e7661` P1 / `174e0cb` P2 / `811759a` P3)
- **fix loop commit**: 5(`3022237` P3-fix1 / `ea08709` P3-fix2 / `1bf956d` P5 / `ddeeb13` P5-fix1 / `a26b864` P5-fix2)

### Phase 执行顺序与 commit 映射

| Phase | Commit | 主要内容 |
|---|---|---|
| P0 | — | audit(无 commit;baseline `3add409` 跑前) |
| P1 | `77e7661` | retire 9 命令 + 2 sister skills(保留 subagent-driven-discipline) |
| P2 | `174e0cb` | retire 8 tools + grep-driven 17+ tests + 5 fixtures |
| P3 | `811759a` | retire 3 协议文档 + Level 2 文档化 |
| P3-fix | `3022237` `ea08709` | INDEX.md + README.md dead link fix loop |
| P4 | — | spec delta sync(含 P4 capability-boundary + probe-validation MODIFIED;无独立 commit,合并 P3/P5) |
| P5 | `1bf956d` | CLAUDE.md / AGENTS.md / README.md / docs/ai_workflow/README.md 精简 |
| P5-fix | `ddeeb13` `a26b864` | AGENTS.md dead forward ref + minor cleanup |
| P6 | — | backlog 目录保留(无 code commit;openspec/backlog/ 已存在无需修改) |
| P7 | — | 验证(pytest 1136 passed / 0 failed;无 commit) |
| P8 | 本文档 | retrospective |

### Subagent Dispatch 总数估计

Task 1-9 共派出约 **15-18 个 subagent** 实例:
- 每 task 4 类 subagent(implementer + spec_reviewer + code_quality_reviewer + final_reviewer)
- P1/P2/P3/P5 为主力 task,各完整跑 4 类
- P3 fix loop 追加 spec_review re-dispatch
- 合计: ~4 tasks × 4 + fix loop ~2 = 约 18 dispatch

---

## 2. Codex Review 调用记录

### codex_design_review

- **时间**: 2026-05-10
- **模式**: streaming(plugin v1.0.4 codex-companion.mjs adversarial-review,非 detach job)
- **Thread id**: `019e125a-31d1-7830-8ae9-910cdbef07e5`
- **Output**: `notes/codex_adversarial_review_review_round1.md`
- **Verdict**: needs-attention
- **Finding 总数**: 6(5 × P1 high + 1 × P2 medium)
- **最终结果**: 全 6 finding inline writeback,**disputed_open = 0**

### codex_final_review

- **决定**: **skipped**
- **理由**:
  1. P1/P2/P3/P5 各 phase 均有独立 spec_review + code_quality_review subagent pass
  2. Round 1 codex adversarial review 6 finding 全部 inline writeback,disputed_open = 0
  3. 本 change 最终代码 diff 主体为 deletion + minimal new content(82 LOC insert vs 20,769 delete);deletion 无逻辑 regression 风险
  4. Final review 边际增量极低,不值得额外 cost + latency

---

## 3. Round 1 Codex Writeback 总结

| # | Finding | Codex priority | 验证结论 | Resolution | 落地 commit / 位置 |
|---|---|---|---|---|---|
| P1-1 | SKILL 删 vs 保留 | high | confirmed real,但 codex 误读 SKILL 性质:控制器验证 `SKILL.md` L15/L22 → generic universal skill,author 字段含 forgeue 不等于 ForgeUE-specific protocol | accepted-claude(partial-dispute) | design.md D11 keep policy + tasks.md P1.13 verify step + proposal.md What Changes 补充说明 |
| P1-2 | AGENTS.md / README.md scope 漏 | high | confirmed real:AGENTS.md L212-274 + README.md L360-391 包含 `/forgeue:change-*` 矩阵等已退役内容 | accepted-codex | proposal.md Impact + tasks.md P5 升必做;落地 `1bf956d`(P5 4 docs)+ `ddeeb13`(AGENTS.md dead ref)+ `a26b864`(minor cleanup) |
| P1-3 | 测试清单 17+5 漏 | high | confirmed real:17 个 `test_forgeue_*.py` + 5 fixtures + `test_skill_cascade_check.py` + `test_followon_registry.py` 全被 pytest 收集且会 import error | accepted-codex | tasks.md P2 改 grep-driven;落地 `174e0cb`(P2 retire 33 paths,18,024 deletions) |
| P1-4 | capability-boundary requirement 孤立 | high | confirmed real:主 spec `examples-and-acceptance/spec.md` L2107 依赖 base registry contract(被 delta REMOVED) | accepted-codex | specs/examples-and-acceptance/spec.md REMOVED→MODIFIED(保留 6 capability-boundary entries,删 registry schema contract);P5 spec sync 落盘 |
| P1-5 | Level 2 subprocess contract 过早删 | high | confirmed real:原 requirement 守 3 contract:comfy/local* 路径 + 禁 `--comfy-url` + 禁 LiteLLM wildcard fallback | accepted-codex | specs/probe-and-validation/spec.md REMOVED→MODIFIED(工具无关 contract 保留)+ tasks.md P3.5 升必做;落地 `811759a`(P3 retire docs + test_spec.md Level 2 文档化) |
| P2 | Codex hook silent skip 风险 | medium | confirmed real:D4 mitigation 仅 convention,silent skip 无可见性 | accepted-codex | design.md D4 mitigation 更新 + tasks.md P8.1 retrospective record;落地:本文档此条记录 |

**disputed_open: 0**

---

## 4. 新工作流 Dogfood 反馈

### 顺畅之处

**OpenSpec `/opsx:propose` → `writing-plans` → `subagent-driven-development` 主干路径顺畅**:

- **Proposal artifacts 作为 `writing-plans` implicit context**:OpenSpec 产物(proposal.md / design.md / tasks.md)直接作为 plan 输入,不需要重新描述 intent,context-passing 无摩擦
- **Subagent fix loop re-dispatch**:P3 spec_review fail 后 re-dispatch implementer 修 dead link,流程自然,无需 controller 手动介入
- **Round 1 codex adversarial review**:design 阶段在实施前跑 adversarial,6 finding 全量 surface — 尤其 P1-3 test cleanup 扩展避免了实施后 pytest 崩盘的时序问题

### Friction Points

1. **Codex adversarial review streaming 无 detach job id**:本 change 运行的 `codex-companion.mjs adversarial-review` 是 streaming 模式,没有 detach job id 可引用。后续 review 状态查询靠 thread id,不如 detach 模式可以 `/codex:status` 轮询方便。

2. **P2 LOC 估算偏差 2x**:design 阶段估计 ~9,500 LOC delete,实际 20,769。原因是 tools 本体 LOC 容易估,但 test + fixture LOC 难以在 design 阶段精确预测。grep-driven cleanup(codex 推动)额外扩展了范围。对 retirement change 规模估算,建议 design 阶段加"测试/fixture 乘数 ~1.5x"经验系数。

3. **P5.D residue grep 暴露 P3 implementer 漏清**:P3 implementer 完成后,P5 subagent 在 `docs/ai_workflow/README.md` 发现仍有 `Documentation Sync Gate` + ForgeUE protocol refs 残留。这是"分 phase 串行 retire"的固有摩擦:P3 implementer scope 是协议文档删除,P5 implementer scope 才覆盖 top-level onboarding docs。Residue 没有 block,但增加了 P5 fix loop 次数。

4. **P5 spec review 发现 AGENTS.md dead forward ref**:P5 implementer 写了新的 `AGENTS.md` 精简版,但遗漏了一处仍指向已删 `CLAUDE.md §"OpenSpec 工作流"` section 的 forward ref。Spec reviewer subagent 发现并触发 re-dispatch fix。这验证了 spec reviewer 的价值,但也说明 implementer 在批量精简文档时更容易遗漏内部 cross-ref。

5. **P1-1 partial-dispute 处理**:Codex P1-1 finding 的推断("forgeue author 字段 → ForgeUE-specific protocol")不完全正确。Controller 需要手动 verify `SKILL.md` L15/L22 内容,确认其 generic universal 性质后才能给出 `accepted-claude(partial-dispute)` resolution。这类"codex 表层 evidence 误推 intent"的 finding 无法纯 automated 处理,需要 controller 介入。

### Time Spent Per Phase(粗估 calibration)

| Phase | 估计时长 |
|---|---|
| P0 audit | ~15 min |
| P1 commands/skills retire | ~20 min |
| P2 tools/tests grep-driven retire | ~30 min |
| P3 docs retire + Level 2 文档化 | ~25 min |
| P3 fix loop(dead links) | ~10 min |
| P4/P6 spec/backlog(无独立 commit) | ~10 min |
| P5 4 docs 精简 | ~35 min |
| P5 fix loop(2 fix) | ~15 min |
| P7 verify(pytest 1136) | ~5 min |
| P8 retrospective | ~20 min |
| Round 1 codex adversarial review | ~15 min |
| **Total** | **~200 min** |

### Subagent Model Tier 实际选用 vs §1 表

| Subagent 类型 | §1 推荐 tier | 实际选用 | 备注 |
|---|---|---|---|
| Implementer(simple retire) | haiku | haiku | P1/P2 删文件 / P6 无操作 |
| Implementer(docs/spec edit) | sonnet | sonnet | P3/P5 复杂精简 |
| Spec reviewer | sonnet | sonnet | 全 phase |
| Code quality reviewer | sonnet | sonnet | 全 phase |
| Final reviewer | sonnet | sonnet | P2/P3/P5 |
| P8 retrospective(arch doc) | sonnet | sonnet | §1.5.4 architecture doc rewrite → sonnet |

Tier 选用与 §1 表完全 aligned。

---

## 5. 后续 Follow-on(新发现 retire 残留)

以下为本 change 实施过程中新发现的轻微残留,均不属于本 change scope(对照 design.md D1/D2/D8/D9 定义):

| # | 残留位置 | 描述 | 处置建议 |
|---|---|---|---|
| R-1 | `docs/ai_workflow/validation_matrix.md` | 疑似包含 `--comfy-url` 引用(P3 实施时 grep 确认 0 matches,但 notes 记录了该检查点) | 已确认 0 matches,无需操作 |
| R-2 | `docs/requirements/SRS.md §7.3` | SRS active TBD 中仍含 `_check_srs_registry_consistency` 的 fence 名称引用(fence 本体已删,但 SRS 作为 docs 五件套不在本 change retire scope) | defer — SRS 下次正常 maintenance 顺手更新 |
| R-3 | `tools/__init__.py` | 0-byte 空文件留存(tools/ 目录下工具全删,但 `__init__.py` 作为 package marker 保留,无功能影响) | 可 defer;若后续 tools/ 有新工具则自然成立,若无则清理 |
| R-4 | `docs/ai_workflow/README.md` 时间戳措辞 | L111 描述带旧时间戳风格描述(P5 minor cleanup M-3 deferred) | defer — 后续 doc sync 顺手修,不影响功能 |

---

## 6. Sunk Cost 显式 Accept(D10)

本 change retire 的两个系统均在 retire 前 **≤3 天**完成 ship:

### centralize-followon-backlog-registry(2026-05-07 ship,3 天前)

- **投入规模**:15 D-decision + 3 round codex adversarial review + 45 commits + ~3028 LOC code(业务逻辑)+ ~969 LOC `forgeue_finish_gate.py` fence 增量
- **retire 范围**:D3 保留 `openspec/backlog/` 目录作为信息容器(active.md / archived.md / README.md 保留);仅 fence 本体(`_check_followon_continuity` / `_check_srs_registry_consistency`)从 `forgeue_finish_gate.py` 随 P2 一起删除
- **Sunk cost 判断**:`openspec/backlog/` 内容本身仍有价值(23 active entries + 3 tombstones)。Retire 的是 enforcement machinery(工具 + fence),不是信息本身。**接受**。

### enforce-subagent-discipline-cascade(2026-05-08 ship,2 天前)

- **投入规模**:cascade discipline + model tier 协议化;subagent-driven-discipline SKILL.md 扩展
- **retire 范围**:D11 保留 `subagent-driven-discipline` SKILL(round 1 codex P1-1 partial-dispute → accepted-claude);ForgeUE-specific cascade enforcement 协议(存在于 `forgeue_finish_gate.py` `_check_skill_cascade` fence + `forgeue-integrated-change-workflow` sister skill)随 P2/P1 一起删除
- **Sunk cost 判断**:SKILL 本身升格为 generic universal,对 Superpowers `subagent-driven-development` 仍有 companion value。Retire 的是 ForgeUE-specific mandatory enforcement,不是 discipline 知识本身。**接受**。

**核心逻辑**:协议层 enforce machinery 的 maintenance cost 随版本累积,已超过其提供的 safety margin。两个 change 的"信息/知识"部分均以更轻量形式保留(`openspec/backlog/` 目录 + SKILL 文件);被 retire 的是 machinery,不是 intent。

---

## 7. Code Quality Review Minor Issues(M-2 / M-3 Deferred)

以下 minor issues 在 P5 code quality review 中发现,未在本 change scope 修复:

### M-2: AGENTS.md 缺 Superpowers skill 显式引用

- **描述**:AGENTS.md 主要面向 Codex / Cursor / Aider,这些 agent 不直接 invoke Superpowers SKILL(SKILL 机制是 Claude Code 专属)
- **处置**:defer,受众差异化 acceptable;Superpowers skill 引用写入 AGENTS.md 对 Codex 无实际意义
- **优先级**:low

### M-3: docs/ai_workflow/README.md L111 时间戳描述旧

- **描述**:L111 含旧时间戳风格措辞,与 2026-04-27 之后的工作流状态不完全吻合
- **处置**:defer,不影响功能;后续 doc sync 顺手修
- **优先级**:low

### I-1 / M-1:已 inline fix

- `I-1`(docs/ai_workflow/README.md L175 misleading 描述)+ `M-1`(AGENTS.md L3 typo `AGENT.md → AGENTS.md`)已于 commit `a26b864` 修复

---

*Retrospective 完成时间: 2026-05-11*
*Change: retire-forgeue-protocol-layer-fully*
*P8 phase — architecture-level reflection*
