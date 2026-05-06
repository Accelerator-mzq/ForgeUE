---
name: "ForgeUE: Change Doc Sync"
description: Documentation Sync Gate;forgeue_doc_sync_check 静态扫描 + README §4.3 提示词 + 应用 [REQUIRED]
category: ForgeUE Workflow
tags: [forgeue, workflow, S6-to-S7, doc-sync]
---

S6→S7 transition:Documentation Sync Gate(沿 `docs/ai_workflow/README.md` §4 主规则不动;新增 `forgeue_doc_sync_check` 静态预扫描作为 §4.3 提示词的 context 输入)。

**Input**: 必须指定 change name(`/forgeue:change-doc-sync <id>`)。

## Preflight Skill Cascade(D-SkillCascadeCheck)

本命令 invoke `forgeue-doc-sync-gate` SKILL(ForgeUE 自家 SKILL,backbone 是 `forgeue-integrated-change-workflow`);实施前 controller MUST 验证主 SKILL declared dependency 全 invoke。

强制项(在 Step 主流程 invoke `forgeue-doc-sync-gate` 之前执行):

```bash
python tools/forgeue_skill_cascade_check.py \
    --skill forgeue-doc-sync-gate \
    --invoked forgeue-integrated-change-workflow
```

- exit 0 → cascade OK
- exit 5 → missing dependency → 命令 abort + 提示主动 invoke 缺失 SKILL 后 retry

evidence frontmatter(`doc_sync_report.md`)MUST 加 `skill_cascade_audit` 字段 + `runtime_enforcement_protocol_version: v1`。

> **跨 plugin 兼容**:`forgeue_skill_cascade_check.py` 多 root probe 链(D-SkillRootMultiSource)在 `.claude/skills` repo-local + Anthropic plugin cache + Codex 自定义路径之间自动 fallback;本命令在不同 IDE / agent 环境跑都能命中正确 SKILL.md。

**Steps**

1. **环境检测** — `python tools/forgeue_env_detect.py --json`。
2. **绑定 active change** — abort if missing。
3. **检查 S6 进入条件**:`review/superpowers_review.md` finalize + `review/codex_adversarial_review.md` 落盘 + blocker 全清。
4. **forgeue_doc_sync_check 静态扫描**:
   - `python tools/forgeue_doc_sync_check.py --change <id> --json`
   - 扫 10 份长期文档(`openspec/specs/*` / `docs/requirements/SRS.md` / `docs/design/HLD.md` / `docs/design/LLD.md` / `docs/testing/test_spec.md` / `docs/acceptance/acceptance_report.md` / `README.md` / `CHANGELOG.md` / `CLAUDE.md` / `AGENTS.md`)
   - 每份打 `[REQUIRED]` / `[OPTIONAL]` / `[SKIP]` / `[DRIFT]` 标签
   - exit 0(无 DRIFT)/ 2(任一 DRIFT)/ 1(IO 异常)
5. **跑 README §4.3 提示词**(以 tool 输出作 context):
   - agent 输出 4 类:`A. 必须更新` / `B. 不需要更新` / `C. 存在 doc drift` / `D. 建议 patch`
   - 启发式规则(沿 design.md §7):commit-touching → CHANGELOG REQUIRED;`src/framework/core/` 改动 → LLD REQUIRED;`docs/ai_workflow/` 改动 → CLAUDE+AGENTS REQUIRED;无 spec delta → `openspec/specs/*` SKIP
6. **用户确认 [REQUIRED]** — agent 不在用户确认前应用任何 patch(README §4.3 末段约束)。
7. **应用 patch**(用户确认后):
   - patch 限本 change scope;不机械同步;不复制 evidence 全文进 docs;不复制 docs 长文进 OpenSpec
8. **写 doc_sync_report** — `verification/doc_sync_report.md`(`evidence_type: doc_sync_report` / 12-key frontmatter):
   - 10 文档每份 [REQUIRED]/[OPTIONAL]/[SKIP]/[DRIFT] 状态
   - SKIP 项 reason 全记
   - DRIFT 0 + REQUIRED 全应用
9. **状态推进** — doc_sync_report exit 0 + DRIFT 0 + REQUIRED 全应用 → 进 S8。

**Output Format**

```
## ForgeUE Change Doc Sync: <change-id> (S6→S7)

### Static scan
- forgeue_doc_sync_check exit code: <0|2|1>
- 10 docs: REQUIRED=<N> / OPTIONAL=<N> / SKIP=<N> / DRIFT=<N>

### Agent classification (README §4.3)
- A. 必须更新: <list of files + reason>
- B. 不需要更新: <list + reason>
- C. doc drift: <list + 建议 source-of-truth>
- D. 建议 patch: <summary>

### Applied
- REQUIRED applied: <count>
- DRIFT resolved: <count>
- doc_sync_report.md: <path>

next: <S8 ready | blocked + reason>
```

**Guardrails**

- **必绑 active change**。
- **不调 `/codex:rescue`** / **不启 `--enable-review-gate`**。
- **不机械同步**(README §4.2):很多 change 只触动 2-3 份;不更新的必须 reason 落 doc_sync_report。
- **不让 evidence 成新规范源**:不允许把 evidence 内容回写主 docs(`forgeue_doc_sync_check` 默认源仅 contract artifact)。
- **数字以实测为准**(README §4.2):涉及测试总数等以 `python -m pytest -q` 实际输出为准;**不硬编码**。
- **DRIFT 显式化**:docs / tests / code / CHANGELOG 冲突 → 标 [DRIFT] 让用户裁决,**不自行猜测**哪个对(README §4.2)。
- **必跑 doc_sync_check**;DRIFT 阻断 S8。
- **本命令不直接触发 `/codex:adversarial-review` / `/codex:review`**(本命令是 docs 同步 gate,不属 stage review;若需 review 走 `/forgeue:change-{plan,apply,verify,review}` 对应 stage hook)。

## Decision Delegation

本命令在 ForgeUE Integrated AI Change Workflow **S6→S7(doc sync)** 阶段触发。Claude controller 默认按 design.md `D-AutonomyBoundary` + `D-FenceTaxonomy`(Fence #1-#6 trigger keyword 真源)决策升级路径:

**默认自主路径**(`autonomy_decision: claude_autonomous`):
- 跑 `forgeue_doc_sync_check.py --change <id>` 静态扫描 10 份长期文档
- 按 README §4.3 提示词分类 A/B/C/D;[REQUIRED] 项在用户确认后应用 patch
- 写 `verification/doc_sync_report.md`;DRIFT 0 + REQUIRED 全应用 → 自主推进 S8

**必须升级用户的 boundary fence**:
- **Fence #1 不可逆**:本命令不涉及 archive / git push 等不可逆操作
- **Fence #2 跨 change**:doc sync 涉及修改其他 active change 正在编辑的文档(如 `CLAUDE.md` / `HLD.md`)→ 升级确认;[REQUIRED] patch 涉及跨 change scope → 升级裁决
- **Fence #3 review 冲突**:本命令不触发 codex review hook(无冲突场景)
- **Fence #4 用户约束**:用户指定 [REQUIRED] patch 不应用 / 排除某文档 → 升级确认
- **Fence #5 钱**:本命令不引入 vendor API paid call,无需升级
- **Fence #6 安全**:本命令不 read `.env` 或敏感凭证

evidence frontmatter MUST 含 `autonomy_decision` 字段,值取自 `{claude_autonomous, claude_codex_concurred, user_required, user_overrode}`。`claude_codex_concurred` MUST 配套 `codex_review_ref` 字段。

**References**

- `design.md` §4 commands 表(`/forgeue:change-doc-sync` 行)— hook 真源:`forgeue_doc_sync_check + §4.3 提示词 + 应用 [REQUIRED]`
- `docs/ai_workflow/README.md` §4(主规则不动)+ §4.3(固定提示词)+ §4.4(决策权下放与 Autonomy Boundary;enhance-workflow-automation 新增)+ §4.5(tasks.md 必含段模板;原 §4.4 顺延)
- `design.md` §7 Documentation Sync Gate Integration(启发式规则)
- `forgeue_integrated_ai_workflow.md` §D(Documentation Sync Gate 应用流程;原 §C 在 enhance-workflow-automation change 后顺延)
- primary skill: `.claude/skills/forgeue-doc-sync-gate/SKILL.md`
- backbone skill: `.claude/skills/forgeue-integrated-change-workflow/SKILL.md`(中心化编排,与其他 7 个 ForgeUE commands 共享)
